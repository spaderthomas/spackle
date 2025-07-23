#!/usr/bin/env python

import json
import subprocess
from pathlib import Path
import pytest
import tempfile
import shutil

import spackle


@pytest.fixture
def temp_project_dir():
  temp_dir = tempfile.mkdtemp()
  yield Path(temp_dir)
  # Cleanup after test
  shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_user_code_file(tmp_path):
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

  test_file = tmp_path / 'test_user_code.py'
  test_file.write_text(test_code)
  return test_file


def run_command(cmd, cwd=None):
  result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
  return result.returncode == 0, result.stdout, result.stderr


def test_spackle_build_with_user_code(temp_project_dir, test_user_code_file):
  # Setup project
  spackle_dir = temp_project_dir / '.spackle'
  spackle_dir.mkdir(exist_ok=True)

  # Create settings.json with the test user code file
  settings = {'file_path': str(test_user_code_file)}

  settings_file = spackle_dir / 'settings.json'
  with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)

  # Run spackle build
  success, stdout, stderr = run_command('spackle build', cwd=temp_project_dir)
  assert success, f'spackle build failed: {stderr}'

  # Verify settings.json still has the correct path
  with open(settings_file, 'r') as f:
    loaded_settings = json.load(f)
    assert loaded_settings['file_path'] == str(test_user_code_file)

  # Test spackle tool command
  success, stdout, stderr = run_command('spackle tool test_tool', cwd=temp_project_dir)
  assert success, f'spackle tool test_tool failed: {stderr}'
  assert 'Test tool executed successfully!' in stdout

  # Test another tool
  success, stdout, stderr = run_command(
    'spackle tool another_test_tool', cwd=temp_project_dir
  )
  assert success, f'spackle tool another_test_tool failed: {stderr}'
  assert 'Another tool works too!' in stdout


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


def test_spackle_build_with_function_specification(temp_project_dir):
  # Create a test file with a specific function to load
  test_code = """#!/usr/bin/env python

import spackle

def load_specific_tools():
    @spackle.tool
    def specific_tool():
        return spackle.McpResult(
            return_code=0,
            response="Specific tool loaded!",
            stderr="",
            stdout=""
        )

def load_other_tools():
    @spackle.tool
    def other_tool():
        return spackle.McpResult(
            return_code=0,
            response="Other tool loaded!",
            stderr="",
            stdout=""
        )
"""

  test_file = temp_project_dir / 'test_functions.py'
  test_file.write_text(test_code)

  # Run spackle build with file:function format
  success, stdout, stderr = run_command(
    f'spackle build --file test_functions.py:load_specific_tools', cwd=temp_project_dir
  )
  assert success, f'spackle build with function spec failed: {stderr}'

  # Verify settings.json has the correct path and function
  spackle_dir = temp_project_dir / '.spackle'
  settings_file = spackle_dir / 'settings.json'
  with open(settings_file, 'r') as f:
    loaded_settings = json.load(f)
    assert loaded_settings['file_path'] == str(test_file)
    assert loaded_settings['function_name'] == 'load_specific_tools'

  # Test that only the specific tool was loaded
  success, stdout, stderr = run_command(
    'spackle tool specific_tool', cwd=temp_project_dir
  )
  assert success, f'spackle tool specific_tool failed: {stderr}'
  assert 'Specific tool loaded!' in stdout


def test_spackle_build_creates_claude_files(temp_project_dir):
  """Test that spackle build creates the necessary Claude configuration files"""
  
  # Run spackle build
  success, stdout, stderr = run_command('spackle build', cwd=temp_project_dir)
  assert success, f'spackle build failed: {stderr}'
  
  # Check that CLAUDE.md is created
  claude_md = temp_project_dir / 'CLAUDE.md'
  assert claude_md.exists(), 'CLAUDE.md should be created by spackle build'
  
  # Check that .claude directory and settings.local.json are created
  claude_dir = temp_project_dir / '.claude'
  assert claude_dir.exists(), '.claude directory should be created by spackle build'
  
  settings_file = claude_dir / 'settings.local.json'
  assert settings_file.exists(), '.claude/settings.local.json should be created by spackle build'
  
  # Verify the settings file contains expected structure
  with open(settings_file, 'r') as f:
    settings = json.load(f)
    assert 'permissions' in settings, 'settings should contain permissions'
    assert 'enabledMcpjsonServers' in settings, 'settings should contain enabledMcpjsonServers'
    assert 'spackle-main' in settings['enabledMcpjsonServers'], 'spackle-main should be enabled'
    assert 'spackle-probe' in settings['enabledMcpjsonServers'], 'spackle-probe should be enabled'
  
  # Check that .mcp.json is created  
  mcp_config = temp_project_dir / '.mcp.json'
  assert mcp_config.exists(), '.mcp.json should be created by spackle build'


def test_spackle_build_with_foo_provider(temp_project_dir):
  """Test that spackle build with --provider foo creates minimal structure"""
  
  # Run spackle build with foo provider
  success, stdout, stderr = run_command('spackle build --provider foo', cwd=temp_project_dir)
  assert success, f'spackle build --provider foo failed: {stderr}'
  
  # Check that .spackle directory is created
  spackle_dir = temp_project_dir / '.spackle'
  assert spackle_dir.exists(), '.spackle directory should be created by spackle build --provider foo'
  
  # Check that settings.json is created
  settings_file = spackle_dir / 'settings.json'
  assert settings_file.exists(), '.spackle/settings.json should be created by spackle build --provider foo'
  
  # Check that Claude-specific files are NOT created
  claude_md = temp_project_dir / 'CLAUDE.md'
  assert not claude_md.exists(), 'CLAUDE.md should NOT be created for foo provider'
  
  claude_dir = temp_project_dir / '.claude'
  assert not claude_dir.exists(), '.claude directory should NOT be created for foo provider'
  
  mcp_config = temp_project_dir / '.mcp.json'
  assert not mcp_config.exists(), '.mcp.json should NOT be created for foo provider'
