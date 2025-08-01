#!/usr/bin/env python

import os
import subprocess
from typing import List
import fastmcp


def get_project_root() -> str:
    """Get the project root directory by looking up from cwd until finding spackle.py"""
    current_dir = os.getcwd()
    
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        spackle_py_path = os.path.join(current_dir, '.spackle', 'spackle.py')
        if os.path.exists(spackle_py_path):
            return current_dir
        current_dir = os.path.dirname(current_dir)
    
    # If we can't find spackle.py, fall back to current working directory
    return os.getcwd()


def get_validated_path(subpath: str = None) -> str:
    """Get the full path by combining project root with optional subpath, with validation"""
    project_root = get_project_root()
    
    if not subpath:
        return project_root
    
    # Build the full path
    full_path = os.path.join(project_root, subpath)
    full_path = os.path.normpath(full_path)  # Normalize the path
    
    # Validate that the path exists
    if not os.path.exists(full_path):
        raise ValueError(f"Path does not exist: {full_path}")
    
    # Validate that it's a directory
    if not os.path.isdir(full_path):
        raise ValueError(f"Path is not a directory: {full_path}")
    
    # Ensure the path is within the project root (prevent directory traversal)
    if not os.path.commonpath([full_path, project_root]) == project_root:
        raise ValueError(f"Path is outside of project root: {full_path}")
    
    return full_path


def run_probe_command(command: List[str]) -> str:
    """Run a probe command and return the output"""
    try:
        result = subprocess.run(
            command,
            cwd=get_project_root(),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            error_msg = f"Probe command failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"
            raise Exception(error_msg)
        
        return result.stdout
    except subprocess.TimeoutExpired:
        raise Exception("Probe command timed out after 30 seconds")
    except Exception as e:
        raise Exception(f"Error running probe command: {str(e)}")


def probe_server():
    """Create and run the probe MCP server"""
    mcp = fastmcp.FastMCP("spackle-probe", on_duplicate_tools="replace")
    
    @mcp.tool()
    def search_code(
        query: str,
        subpath: str = None,
        session: str = "new"
    ) -> str:
        """Search code in the repository using ElasticSearch. Use this tool first for any code-related questions.
        
        Args:
            query: The search query
            subpath: Relative path within project root to search in
            session: Session identifier for caching
        """
        
        # Determine search path
        if subpath:
            try:
                search_path = get_validated_path(subpath)
            except ValueError as e:
                return f"Error: {str(e)}"
        else:
            search_path = get_project_root()
        
        # Build the probe search command
        cmd = ["npx", "-y", "@buger/probe", "search", query, search_path]
        
        # Hardcoded limits and format
        cmd.extend(["--max-tokens", "750"])
        cmd.extend(["--max-results", "4"])
        cmd.extend(["--format", "markdown"])
        
        # Add session if provided
        if session and session != "new":
            cmd.extend(["--session", session])
        
        return run_probe_command(cmd)
    
    @mcp.tool()
    def query_code(
        pattern: str,
        subpath: str = None,
        language: str = None
    ) -> str:
        """Search code using ast-grep structural pattern matching. Use this tool to find specific code structures like functions, classes, or methods.
        
        Args:
            pattern: The ast-grep pattern to search for
            subpath: Relative path within project root to search in
            language: Programming language to search in
        """
        
        # Determine search path
        if subpath:
            try:
                search_path = get_validated_path(subpath)
            except ValueError as e:
                return f"Error: {str(e)}"
        else:
            search_path = get_project_root()
        
        # Build the probe query command
        cmd = ["npx", "-y", "@buger/probe", "query", pattern, search_path]
        
        # Hardcoded limits and format
        cmd.extend(["--max-results", "4"])
        cmd.extend(["--format", "markdown"])
        
        # Add language if specified
        if language:
            cmd.extend(["--language", language])
        
        return run_probe_command(cmd)
    
    @mcp.tool()
    def extract_code(
        files: List[str],
        contextLines: int = 0
    ) -> str:
        """Extract code blocks from files based on line number, or symbol name. Fetch full file when line number is not provided.
        
        Args:
            files: Files and lines or symbols to extract from
            contextLines: Number of context lines to include
        """
        
        # Build the probe extract command
        cmd = ["npx", "-y", "@buger/probe", "extract"]
        
        # Add files as positional arguments
        cmd.extend(files)
        
        # Hardcoded format
        cmd.extend(["--format", "markdown"])
        
        # Add context lines if specified
        if contextLines > 0:
            cmd.extend(["--context", str(contextLines)])
        
        return run_probe_command(cmd)
    
    # Run the server
    mcp.run()


if __name__ == "__main__":
    probe_server()