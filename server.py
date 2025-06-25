import io
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from mcp.server.fastmcp import FastMCP
from pathlib import Path
from typing import Dict, List, Optional, Union

# Get configuration from environment variables with defaults
WORKDIR = os.environ.get("WORKDIR", str(Path.home()))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8000))

# Create an MCP server with environment variable configuration
mcp = FastMCP("python", stateless_http=True, host=HOST, port=PORT, path="/python")


@mcp.resource("active-project://")
def get_active_project() -> str:
    """
    Get the active project.

    Returns:
        str: The name of the active project or a message indicating no active project.
    """
    if os.getcwd() == WORKDIR:
        return "No active project"
    return os.path.basename(os.getcwd())  # Using basename instead of split[-1]

@mcp.tool()
def set_active_project(project: str) -> dict:
    """
    Change the active project.

    Args:
        project (str): The name of the project to set as active.

    Raises:
        FileNotFoundError: If the specified project does not exist.
    """
    project_path = os.path.join(WORKDIR, project)
    if not os.path.isdir(project_path):
        raise FileNotFoundError(f"Project '{project}' does not exist")
    if not project_path.startswith(WORKDIR):
        raise FileNotFoundError(f"Please provide a relative path")

    os.chdir(project_path)

@mcp.resource("projects://")
def list_projects() -> List[str]:
    """
    List all directories in the workdir.

    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the operation was successful
            - message (str): An informative message about the result
            - current_project (str): The name of the current project 
            - error (str, optional): Error details (if unsuccessful)
    """
    # Get the current project before any changes
    current_project = os.path.basename(os.getcwd())
    
    try:
        project_path = os.path.join(WORKDIR, project)
        if not os.path.isdir(project_path):
            return {
                "success": False,
                "message": f"Project '{project}' does not exist",
                "current_project": current_project,
                "error": "FileNotFoundError"
            }
        
        os.chdir(project_path)
        return {
            "success": True,
            "message": f"Successfully changed to project '{project}'",
            "current_project": project
        }
    except Exception as e:
        # Get the current project again after the exception
        # (it might have changed during the attempt)
        current_project = os.path.basename(os.getcwd())
        return {
            "success": False,
            "message": f"Failed to change to project '{project}'",
            "current_project": current_project,
            "error": str(e)
        }

    Args:
        code (str): Python code to execute

    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
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

    except Exception as e:
        result["success"] = False
        result["stderr"] = f"{stderr_buffer.getvalue()}\nException: {str(e)}"

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
        return result
        
    # Check if it's a file (not a directory)
    if not os.path.isfile(file_path):
        result["success"] = False
        result["stderr"] = f"Error: '{filename}' is not a file."
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
        
    except Exception as e:
        result["success"] = False
        result["stderr"] = f"{stderr_buffer.getvalue()}\nException: {str(e)}"
        
    return result

@mcp.tool()
def shell_exec(command: str) -> Dict[str, Union[str, bool]]:
    """
    Execute a shell command and return its output.
    
    Args:
        command (str): The shell command to execute
        
    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
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
        
    except Exception as e:
        result["success"] = False
        result["stderr"] = f"Error executing command: {str(e)}"
    
    return result

def initialize_workspace():
    """Initialize the workspace by setting an active project"""
    # Get list of available projects
    projects = list_projects()
    
    # If no projects exist, the default directory should already exist from entrypoint
    if not projects:
        print("No projects found. This should not happen as entrypoint creates default.")
        # We won't create it here as the entrypoint should have done this with proper permissions
        return
        
    # Use the first available project
    first_project = projects[0]
    os.chdir(os.path.join(WORKDIR, first_project))
    print(f"Setting '{first_project}' as the active project")

if __name__ == "__main__":
    try:
        initialize_workspace()
        print(f"Starting MCP server on {HOST}:{PORT}")
        print(f"Active project: {get_active_project()}")
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("\nShutting down MCP server...")
        sys.exit(0)
