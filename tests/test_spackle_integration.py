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


def test_spackle_build_creates_slash_commands(temp_project_dir, test_user_code_file):
  """Test that spackle build creates slash command files from @prompt decorators"""
  
  # Create a test file with prompt decorators
  test_code = """#!/usr/bin/env python

import spackle

@spackle.load
def setup_prompts():
    @spackle.prompt
    def compact():
        return "Make the code more compact and remove unnecessary whitespace."
    
    @spackle.prompt
    def verbose():
        return "Add detailed comments and explanations to make the code more verbose."
"""

  test_file = temp_project_dir / 'test_prompts.py'
  test_file.write_text(test_code)

  # Run spackle build with the test file
  success, stdout, stderr = run_command(f'spackle build --file {test_file.name}', cwd=temp_project_dir)
  assert success, f'spackle build with prompts failed: {stderr}'
  
  # Check that .claude/commands directory is created
  commands_dir = temp_project_dir / '.claude' / 'commands'
  assert commands_dir.exists(), '.claude/commands directory should be created'
  
  # Check that slash command files are generated
  compact_file = commands_dir / 'compact.md'
  assert compact_file.exists(), 'compact.md should be created in .claude/commands'
  
  verbose_file = commands_dir / 'verbose.md'
  assert verbose_file.exists(), 'verbose.md should be created in .claude/commands'
  
  # Verify the content of the generated files
  compact_content = compact_file.read_text()
  assert compact_content == "Make the code more compact and remove unnecessary whitespace."
  
  verbose_content = verbose_file.read_text()
  assert verbose_content == "Add detailed comments and explanations to make the code more verbose."


def test_prompt_decorator_without_build():
  """Test that the prompt decorator stores functions correctly"""
  import spackle
  
  # Clear any existing prompts
  spackle.spackle.prompts.clear()
  
  @spackle.prompt
  def test_command():
    return "This is a test prompt."
  
  # Verify the function was stored
  assert 'test_command' in spackle.spackle.prompts
  assert spackle.spackle.prompts['test_command'] == test_command
  
  # Verify calling the function returns the expected string
  result = spackle.spackle.prompts['test_command']()
  assert result == "This is a test prompt."


def test_spackle_config_includes_provider(temp_project_dir):
  """Test that the spackle config includes the provider information"""
  
  # Run spackle build with default (claude) provider
  success, stdout, stderr = run_command('spackle build', cwd=temp_project_dir)
  assert success, f'spackle build failed: {stderr}'
  
  # Check that the config file contains the provider
  config_file = temp_project_dir / '.spackle' / 'settings.json'
  assert config_file.exists(), '.spackle/settings.json should exist'
  
  with open(config_file, 'r') as f:
    config = json.load(f)
    assert 'provider' in config, 'Config should contain provider field'
    assert config['provider'] == 'claude', 'Default provider should be claude'


def test_spackle_config_includes_foo_provider(temp_project_dir):
  """Test that the spackle config includes the foo provider when specified"""
  
  # Run spackle build with foo provider
  success, stdout, stderr = run_command('spackle build --provider foo', cwd=temp_project_dir)
  assert success, f'spackle build --provider foo failed: {stderr}'
  
  # Check that the config file contains the provider
  config_file = temp_project_dir / '.spackle' / 'settings.json'
  assert config_file.exists(), '.spackle/settings.json should exist'
  
  with open(config_file, 'r') as f:
    config = json.load(f)
    assert 'provider' in config, 'Config should contain provider field'
    assert config['provider'] == 'foo', 'Provider should be foo when specified'


def test_spackle_build_creates_prompt_files(temp_project_dir):
  """Test that spackle build copies prompt files from filesystem"""
  
  # Create test prompt files in the project root
  prompt_content = "This is a custom prompt from a file."
  another_content = "# Another Custom Prompt\n\nThis prompt is in markdown format."
  
  prompt_file = temp_project_dir / 'custom_prompt.md'
  prompt_file.write_text(prompt_content)
  
  another_file = temp_project_dir / 'docs' / 'another.txt'
  another_file.parent.mkdir(exist_ok=True)
  another_file.write_text(another_content)
  
  # Create a test file with prompt_file decorators
  test_code = f"""#!/usr/bin/env python

import spackle

@spackle.load
def setup_prompt_files():
    @spackle.prompt_file
    def custom():
        return 'custom_prompt.md'
    
    @spackle.prompt_file
    def another():
        return 'docs/another.txt'
"""

  test_file = temp_project_dir / 'test_prompt_files.py'
  test_file.write_text(test_code)

  # Run spackle build with the test file
  success, stdout, stderr = run_command(f'spackle build --file {test_file.name}', cwd=temp_project_dir)
  assert success, f'spackle build with prompt files failed: {stderr}'
  
  # Check that .claude/commands directory is created
  commands_dir = temp_project_dir / '.claude' / 'commands'
  assert commands_dir.exists(), '.claude/commands directory should be created'
  
  # Check that prompt files are copied
  custom_file = commands_dir / 'custom.md'
  assert custom_file.exists(), 'custom.md should be created in .claude/commands'
  
  another_file_copy = commands_dir / 'another.md'
  assert another_file_copy.exists(), 'another.md should be created in .claude/commands'
  
  # Verify the content of the copied files
  custom_content = custom_file.read_text()
  assert custom_content == prompt_content
  
  another_content_copied = another_file_copy.read_text()
  assert another_content_copied == another_content


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
