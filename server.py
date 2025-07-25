import io
import os
import base64
import mimetypes
import sys
import datetime
from contextlib import redirect_stdout, redirect_stderr
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image
from pathlib import Path
from typing import Dict, List, Optional, Union, Annotated
from pydantic import Field

# Get configuration from environment variables with defaults
WORKDIR = os.environ.get("WORKDIR", str(Path.home()))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8000))

# Environment variable to control command logging
# Use lower() to handle case-insensitivity
LOG_COMMANDS = os.environ.get("MCP_LOG_COMMANDS", "0").lower() in ("1", "true", "yes")

def log_command(command_type, command_data, result_success=None):
    """Log command execution to stdout if logging is enabled
    
    Args:
        command_type (str): Type of command (e.g., 'shell', 'python')
        command_data (str): The actual command that was executed
        result_success (bool, optional): Whether the command was successful
    """
    if LOG_COMMANDS:
        timestamp = datetime.datetime.now().isoformat()
        status = f"[{'SUCCESS' if result_success else 'FAILED'}]" if result_success is not None else ""
        print(f"[{timestamp}] [MCP-LOG] [{command_type}] {status} {command_data}", file=sys.stdout)
        sys.stdout.flush()  # Ensure logs are flushed immediately

# Create an MCP server with environment variable configuration
mcp = FastMCP("python", stateless_http=True, host=HOST, port=PORT, path="/python")

@mcp.resource("projects://")
def list_projects() -> List[str]:
    """
    List all directories in the workdir.

    Returns:
        List[str]: A list of directory names in the workdir.
    """
    log_command("resource", "list_projects")
    return [item for item in os.listdir(WORKDIR)
            if os.path.isdir(os.path.join(WORKDIR, item))]

@mcp.resource("active-project://")
def get_active_project() -> str:
    """
    Get the active project.

    Returns:
        str: The name of the active project or a message indicating no active project.
    """
    log_command("resource", "get_active_project")
    if os.getcwd() == WORKDIR:
        return "No active project"
    return os.path.basename(os.getcwd())  # Using basename instead of split[-1]

@mcp.tool()
def cd(directory: str) -> dict:
    """
    Change the current working directory.

    Args:
        directory (str): The directory path to change to.

    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the operation was successful
            - message (str): An informative message about the result
            - current_directory (str): The current directory path
            - error (str, optional): Error details (if unsuccessful)
    """
    log_command("cd", f"directory={directory}")

    # Get the current directory before any changes
    current_dir = os.getcwd()

    try:
        # Handle absolute paths
        if os.path.isabs(directory):
            target_path = directory
            # Ensure the path is within WORKDIR for security
            if not target_path.startswith(WORKDIR):
                result = {
                    "success": False,
                    "message": f"Please provide either a relative path or a path in {WORKDIR}",
                    "current_directory": current_dir,
                    "error": "Unauthorized Path"
                }
                log_command("cd", f"directory={directory}", False)
                return result
        else:
            # Handle relative paths by resolving against current directory
            target_path = os.path.abspath(os.path.join(current_dir, directory))
            # Ensure the path is within WORKDIR for security
            if not target_path.startswith(WORKDIR):
                result = {
                    "success": False,
                    "message": f"The resulting path would be outside {WORKDIR}",
                    "current_directory": current_dir,
                    "error": "Unauthorized Path"
                }
                log_command("cd", f"directory={directory}", False)
                return result

        # Check if directory exists
        if not os.path.isdir(target_path):
            result = {
                "success": False,
                "message": f"Directory '{directory}' does not exist",
                "current_directory": current_dir,
                "error": "FileNotFoundError"
            }
            log_command("cd", f"directory={directory}", False)
            return result

        # Change to the directory
        os.chdir(target_path)
        result = {
            "success": True,
            "message": f"Successfully changed to directory '{directory}'",
            "current_directory": target_path
        }
        log_command("cd", f"directory={directory}", True)
        return result
    except Exception as e:
        # Get the current directory again after the exception
        # (it might have changed during the attempt)
        current_dir = os.getcwd()
        result = {
            "success": False,
            "message": f"Failed to change to directory '{directory}'",
            "current_directory": current_dir,
            "error": str(e)
        }
        log_command("cd", f"directory={directory}", False)
        return result

@mcp.tool()
def get_image(
    path: Annotated[str, Field(description="Path to the image file. If relative, resolves from current directory")]
) -> dict:
    """
    Get an image from the specified path.

    Returns the image as base64 data with appropriate metadata.
    Relative paths are resolved from the current working directory.
    """
    # Convert relative path to absolute path
    abs_path = os.path.abspath(path)

    # Check if the path exists
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"Path '{path}' not found"}

    # Check if it's a file
    if not os.path.isfile(abs_path):
        return {"success": False, "error": f"Path '{path}' is not a file"}

    try:
        # Get file size in bytes
        file_size = os.path.getsize(abs_path)

        # Get the MIME type
        mime_type, _ = mimetypes.guess_type(abs_path)
        if not mime_type or not mime_type.startswith('image/'):
            return {"success": False, "error": f"File '{path}' is not a recognized image format"}

        # If file is larger than ~1MB, compress it
        if file_size > 1000000:
            buffer = io.BytesIO()

            # Open and compress the image
            img = Image.open(abs_path)
            img.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)

            # Use the compressed data
            img_data = buffer.getvalue()
            mime_type = "image/jpeg"  # Update mime type since we converted to JPEG
        else:
            # For smaller images, just read the file directly
            with open(abs_path, 'rb') as img_file:
                img_data = img_file.read()

        # Encode the image as base64
        img_base64 = base64.b64encode(img_data).decode('utf-8')

        # Determine format from the file extension
        format = os.path.splitext(abs_path)[1].lower().lstrip('.')
        if format in ('jpg', 'jpeg'):
            format = 'jpeg'

        # Return the Image object directly
        return Image(data=img_data, format=format)

    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def run_code(code: str) -> Dict[str, Union[str, bool]]:
    """
    Execute Python code and capture stdout and stderr.

    Args:
        code (str): Python code to execute

    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
    # Log the code execution (truncate long code snippets for the log)
    code_preview = (code[:100] + '...') if len(code) > 100 else code
    code_preview = code_preview.replace('\n', ' ').strip()
    log_command("python", f"code=\"{code_preview}\"")
    
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    result = {
        "stdout": "",
        "stderr": "",
        "success": True
    }

    # Create a safe globals dictionary with limited built-ins
    safe_globals = {
        "__builtins__": {
            name: getattr(__builtins__, name)
            for name in dir(__builtins__)
            # Exclude potentially dangerous builtins
            if name not in ['open', 'exec', 'eval', '__import__']
        }
    }

    try:
        # Redirect both stdout and stderr to our buffers
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, safe_globals, {})

        # Get the captured output
        result["stdout"] = stdout_buffer.getvalue()
        result["stderr"] = stderr_buffer.getvalue()
        log_command("python", f"code=\"{code_preview}\"", True)

    except Exception as e:
        result["success"] = False
        result["stderr"] = f"{stderr_buffer.getvalue()}\nException: {str(e)}"
        log_command("python", f"code=\"{code_preview}\"", False)

    return result

@mcp.tool()
def run_file(filename: str) -> Dict[str, Union[str, bool]]:
    """
    Execute a Python file and capture stdout and stderr.
    
    Args:
        filename (str): Name of the Python file to execute in the active project
        
    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
    log_command("python_file", f"filename={filename}")
    
    result = {
        "stdout": "",
        "stderr": "",
        "success": True
    }
    
    file_path = os.path.join(os.getcwd(), filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        result["success"] = False
        result["stderr"] = f"Error: File '{filename}' does not exist."
        log_command("python_file", f"filename={filename}", False)
        return result
        
    # Check if it's a file (not a directory)
    if not os.path.isfile(file_path):
        result["success"] = False
        result["stderr"] = f"Error: '{filename}' is not a file."
        log_command("python_file", f"filename={filename}", False)
        return result
        
    # Create a safe globals dictionary similar to run_code
    safe_globals = {
        "__builtins__": {
            name: getattr(__builtins__, name)
            for name in dir(__builtins__)
            # Exclude potentially dangerous builtins
            if name not in ['open', 'exec', 'eval', '__import__']
        }
    }
    
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    
    try:
        # Read the file content
        with open(file_path, 'r') as f:
            code = f.read()
            
        # Redirect both stdout and stderr to our buffers
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, safe_globals, {})
        
        # Get the captured output
        result["stdout"] = stdout_buffer.getvalue()
        result["stderr"] = stderr_buffer.getvalue()
        log_command("python_file", f"filename={filename}", True)
        
    except Exception as e:
        result["success"] = False
        result["stderr"] = f"{stderr_buffer.getvalue()}\nException: {str(e)}"
        log_command("python_file", f"filename={filename}", False)
        
    return result

# Helper function to detect virtual environments
def detect_venv() -> str:
    """
    Detect if a Python virtual environment exists in the current directory.
    
    Returns:
        str: Path to the virtual environment if found, empty string otherwise
    """
    import os
    import sys
    
    # Common virtual environment directory names
    venv_names = ["venv", ".venv", "env", ".env", "virtualenv"]
    
    # Check current directory for common venv folders
    current_dir = os.getcwd()
    for venv_name in venv_names:
        venv_path = os.path.join(current_dir, venv_name)
        if os.path.isdir(venv_path):
            # Verify it's a valid venv by checking for activate script
            is_windows = sys.platform == "win32"
            if is_windows:
                activate_path = os.path.join(venv_path, "Scripts", "activate.bat")
            else:
                activate_path = os.path.join(venv_path, "bin", "activate")
            if os.path.exists(activate_path):
                return venv_path
    
    # No valid venv found
    return ""

def shell_exec_with_venv(venv_path: str, command: str) -> Dict[str, Union[str, bool]]:
    """
    Execute a shell command within an activated Python virtual environment.
    
    Args:
        venv_path (str): Path to the virtual environment directory
        command (str): The shell command to execute in the activated environment
        
    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
    log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"")
    
    import subprocess
    import os
    import sys
    
    result = {
        "stdout": "",
        "stderr": "",
        "success": True
    }
    
    # Validate the venv path
    if not os.path.isdir(venv_path):
        result["success"] = False
        result["stderr"] = f"Error: Virtual environment directory '{venv_path}' does not exist."
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", False)
        return result
    
    # Check if it looks like a valid venv (has bin/activate or Scripts/activate.bat)
    is_windows = sys.platform == "win32"
    if is_windows:
        activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
    else:
        activate_script = os.path.join(venv_path, "bin", "activate")

    if not os.path.exists(activate_script):
        result["success"] = False
        result["stderr"] = f"Error: '{venv_path}' does not appear to be a valid virtual environment."
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", False)
        return result
    
    try:
        # Construct the activation command based on OS
        if is_windows:
            cmd = f'call "{activate_script}" && {command}'
        else:  # Unix-like systems (Linux, macOS)
            cmd = f'. "{activate_script}" && {command}'
        
        # Run the command and capture output
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Get output and error streams
        stdout, stderr = process.communicate()
        
        # Populate result
        result["stdout"] = stdout
        result["stderr"] = stderr
        result["success"] = process.returncode == 0
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", result["success"])
        
    except Exception as e:
        result["success"] = False
        result["stderr"] = f"Error executing command in virtual environment: {str(e)}"
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", False)
    
    return result

@mcp.tool()
def shell_exec(command: str, auto_env: bool = True) -> Dict[str, Union[str, bool]]:
    """
    Execute a shell command and return its output.
    Automatically uses virtual environment if detected and auto_env is True.
    
    Args:
        command (str): The shell command to execute
        auto_env (bool, optional): Whether to automatically use detected environments. Defaults to True.
        
    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
    log_command("shell", f"command=\"{command}\", auto_env={auto_env}")
    
    # If auto_env is True, check for virtual environment
    if auto_env:
        venv_path = detect_venv()
        if venv_path:
            log_command("shell", f"Virtual environment detected at {venv_path}, using shell_exec_with_venv")
            return shell_exec_with_venv(venv_path, command)
    
    # Original shell_exec implementation
    import subprocess
    
    result = {
        "stdout": "",
        "stderr": "",
        "success": True
    }
    
    try:
        # Run the command and capture output
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Get output and error streams
        stdout, stderr = process.communicate()
        
        # Populate result
        result["stdout"] = stdout
        result["stderr"] = stderr
        result["success"] = process.returncode == 0
        log_command("shell", f"command=\"{command}\"", result["success"])
        
    except Exception as e:
        result["success"] = False
        result["stderr"] = f"Error executing command: {str(e)}"
        log_command("shell", f"command=\"{command}\"", False)
    
    return result

def initialize_workspace():
    """Initialize the workspace by setting an active project"""
    log_command("system", "initialize_workspace")

    # Get list of available projects
    projects = list_projects()

    os.chdir(WORKDIR)
    print(f"Setting '{WORKDIR}' as the active project")

if __name__ == "__main__":
    try:
        # Log startup information
        print(f"Command logging is {'ENABLED' if LOG_COMMANDS else 'DISABLED'}")

        initialize_workspace()
        print(f"Starting MCP server on {HOST}:{PORT}")
        print(f"Active project: {get_active_project()}")
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("\nShutting down MCP server...")
        log_command("system", "shutdown", True)
        sys.exit(0)
