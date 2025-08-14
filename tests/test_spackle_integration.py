#!/usr/bin/env python

import json
import subprocess
from pathlib import Path
import pytest
import tempfile
import shutil
import os

import spackle


@pytest.fixture
def temp_project_dir():
  temp_dir = tempfile.mkdtemp()
  yield Path(temp_dir)
  # Cleanup after test
  shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_user_code_file(tmp_path):
  # Create the .spackle directory first
  spackle_dir = tmp_path / '.spackle'
  spackle_dir.mkdir(exist_ok=True)
  
  test_code = """#!/usr/bin/env python

import spackle

@spackle.load
def initialize_test_tools():
    @spackle.tool
    def test_tool():
        return spackle.McpResult(
            return_code=0,
            response="Test tool executed successfully!",
            stderr="",
            stdout=""
        )

    @spackle.tool
    def another_test_tool():
        return spackle.McpResult(
            return_code=0,
            response="Another tool works too!",
            stderr="",
            stdout=""
        )
"""

  test_file = tmp_path / '.spackle' / 'spackle.py'
  test_file.write_text(test_code)
  return test_file


def run_command(cmd, cwd=None):
  result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
  return result.returncode == 0, result.stdout, result.stderr


def test_spackle_build_with_user_code(temp_project_dir, test_user_code_file):
  # Setup project
  spackle_dir = temp_project_dir / '.spackle'
  spackle_dir.mkdir(exist_ok=True)
  
  # Copy the test user code file to the temp project directory
  project_spackle_dir = temp_project_dir / '.spackle'
  project_spackle_dir.mkdir(exist_ok=True)
  project_spackle_py = project_spackle_dir / 'spackle.py'
  shutil.copy(test_user_code_file, project_spackle_py)

  # Run spackle build directly through the API
  original_cwd = Path.cwd()
  try:
    os.chdir(temp_project_dir)
    spackle.spackle.build()
  finally:
    os.chdir(original_cwd)

  # Test spackle tool command through the API
  original_cwd = Path.cwd()
  try:
    os.chdir(temp_project_dir)
    result = spackle.spackle.run_tool('test_tool')
    assert result.return_code == 0
    assert 'Test tool executed successfully!' in result.response
  finally:
    os.chdir(original_cwd)

  # Test another tool through the API
  original_cwd = Path.cwd()
  try:
    os.chdir(temp_project_dir)
    result = spackle.spackle.run_tool('another_test_tool')
    assert result.return_code == 0
    assert 'Another tool works too!' in result.response
  finally:
    os.chdir(original_cwd)


def test_load_decorator_executes_immediately():
  executed = False

  @spackle.load
  def test_function():
    nonlocal executed
    executed = True

  assert executed, '@load decorator should execute the function immediately'


def test_load_decorator_with_nested_decorators():
  tools_defined = []

  @spackle.load
  def setup_tools():
    @spackle.tool
    def my_test_tool():
      return spackle.McpResult(
        return_code=0, response='Tool defined inside @load', stderr='', stdout=''
      )

    tools_defined.append('my_test_tool')

  assert len(tools_defined) == 1, 'Tool should be defined inside @load function'


def test_spackle_build_creates_claude_files(temp_project_dir):
  """Test that spackle build creates the necessary Claude configuration files"""

  # Run spackle build directly through the API
  original_cwd = Path.cwd()
  try:
    os.chdir(temp_project_dir)
    spackle.spackle.build()
  finally:
    os.chdir(original_cwd)

  # Check that CLAUDE.md is created
  claude_md = temp_project_dir / 'CLAUDE.md'
  assert claude_md.exists(), 'CLAUDE.md should be created by spackle build'

  # Check that .claude directory and settings.local.json are created
  claude_dir = temp_project_dir / '.claude'
  assert claude_dir.exists(), '.claude directory should be created by spackle build'

  settings_file = claude_dir / 'settings.local.json'
  assert settings_file.exists(), (
    '.claude/settings.local.json should be created by spackle build'
  )

  # Verify the settings file contains expected structure
  with open(settings_file, 'r') as f:
    settings = json.load(f)
    assert 'permissions' in settings, 'settings should contain permissions'
    assert 'enabledMcpjsonServers' in settings, (
      'settings should contain enabledMcpjsonServers'
    )
    assert 'spackle-main' in settings['enabledMcpjsonServers'], (
      'spackle-main should be enabled'
    )
    assert 'spackle-probe' in settings['enabledMcpjsonServers'], (
      'spackle-probe should be enabled'
    )

  # Check that .mcp.json is created
  mcp_config = temp_project_dir / '.mcp.json'
  assert mcp_config.exists(), '.mcp.json should be created by spackle build'


def test_prompt_decorator_without_build():
  """Test that the prompt decorator stores functions correctly"""
  import spackle

  # Clear any existing prompts
  spackle.spackle.prompts.clear()

  @spackle.prompt
  def test_command():
    return 'This is a test prompt.'

  # Verify the function was stored
  assert 'test_command' in spackle.spackle.prompts
  assert spackle.spackle.prompts['test_command'] == test_command

  # Verify calling the function returns the expected string
  result = spackle.spackle.prompts['test_command']()
  assert result == 'This is a test prompt.'


def test_prompt_file_decorator_without_build():
  """Test that the prompt_file decorator stores file paths correctly"""
  import spackle

  # Clear any existing prompt files
  spackle.spackle.prompt_files.clear()

  @spackle.prompt_file
  def test_file_command():
    return 'test/path.md'

  # Verify the function was stored
  assert 'test_file_command' in spackle.spackle.prompt_files
  assert spackle.spackle.prompt_files['test_file_command'] == test_file_command

  # Verify calling the function returns the expected filename
  result = spackle.spackle.prompt_files['test_file_command']()
  assert result == 'test/path.md'
