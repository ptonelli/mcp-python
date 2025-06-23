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
def set_active_project(project: str) -> None:
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
    os.chdir(project_path)

@mcp.resource("projects://")
def list_projects() -> List[str]:
    """
    List all directories in the workdir.

    Returns:
        List[str]: A list of directory names in the workdir.
    """
    return [item for item in os.listdir(WORKDIR) 
            if os.path.isdir(os.path.join(WORKDIR, item))]

@mcp.tool()
def run_code(code: str) -> Dict[str, Union[str, bool]]:
    """
    Execute Python code and capture stdout and stderr.

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

mcp.tool()
def add_file(filename: str, content: str) -> dict:
    """
    Create a new file with the specified content in the active project.
    
    Args:
        filename: The name of the file to create
        content: The content to write to the file
    
    Returns:
        Dictionary with success status and message
    """
    result = {
        "success": False,
        "message": ""
    }
    
    file_path = os.path.join(os.getcwd(), filename)
    
    try:
        # Create directories if needed (handles nested paths)
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        # Check if file exists and create or overwrite accordingly
        file_existed = os.path.exists(file_path)
        
        # Write the content to the file
        with open(file_path, 'w') as f:
            f.write(content)
        
        result["success"] = True
        if file_existed:
            result["message"] = f"File '{filename}' overwritten."
        else:
            result["message"] = f"File '{filename}' created successfully."
        
    except Exception as e:
        result["message"] = f"Error creating file: {str(e)}"
    
    return result

@mcp.tool()
def remove_file(filename: str) -> dict:
    """
    Remove a file from the active project.
    
    Args:
        filename: The name of the file to remove
    
    Returns:
        Dictionary with success status and message
    """
    result = {
        "success": False,
        "message": ""
    }
    
    file_path = os.path.join(os.getcwd(), filename)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        result["message"] = f"File '{filename}' does not exist."
        return result
    
    # Check if it's a file (not a directory)
    if not os.path.isfile(file_path):
        result["message"] = f"'{filename}' is not a file."
        return result
    
    try:
        # Remove the file
        os.remove(file_path)
        
        result["success"] = True
        result["message"] = f"File '{filename}' removed successfully."
        
    except Exception as e:
        result["message"] = f"Error removing file: {str(e)}"
    
    return result

@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """
    Get a personalized greeting.

    Args:
        name (str): The name to include in the greeting.

    Returns:
        str: A personalized greeting message.
    """
    return f"Hello, {name}!"

def initialize_workspace():
    """Initialize the workspace by setting an active project"""
    # Get list of available projects
    projects = list_projects()
    
    # If no projects exist, create a "default" directory
    if not projects:
        default_dir = os.path.join(WORKDIR, "default")
        os.makedirs(default_dir, exist_ok=True)
        print(f"Created 'default' directory at {default_dir}")
        os.chdir(default_dir)  # Set as active
    else:
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
