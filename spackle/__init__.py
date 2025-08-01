#!/usr/bin/env python

import click
import enum
import importlib
import json
import os
import pathlib
import platform
import time
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import colorama
import pydantic
import fastmcp
import requests


##########
# ENUMS  #
##########
class Provider(enum.Enum):
  Claude = "claude"
  Foo = "foo"

from .jira import parse_jira_to_markdown, fetch_jira_xml_from_url

from abc import abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Optional, List, Callable, Dict

from .profiles import profiles


#########
# PATHS #
#########
class SpacklePaths:
  def __init__(self):
    self.file = os.path.dirname(os.path.abspath(__file__))
    self.project = os.path.realpath(os.path.join(self.file, '..'))
    self.source = os.path.join(self.project, 'spackle')
    self.asset = os.path.join(self.project, 'asset')
    self.prompts = os.path.join(self.asset, 'prompts')
    self.templates = os.path.join(self.asset, 'templates')
    self.user_md: str = os.path.join(self.templates, 'spackle.md')
    self.user_py: str = os.path.join(self.templates, 'spackle.py')
    self.claude = os.path.join(self.templates, 'claude')
    self.claude_md = os.path.join(self.claude, 'CLAUDE.md')
    self.mcp_config = os.path.join(self.claude, '.mcp.json')

class InstallPaths:
  def __init__(self):
    self.root: str = self._find_project_root()
    self.spackle: str = os.path.join(self.root, '.spackle')
    self.output = os.path.join(self.spackle, 'output')
    self.prompts: str = os.path.join(self.spackle, 'prompts')
    self.user_md: str = os.path.join(self.spackle, 'spackle.md')
    self.user_py: str = os.path.join(self.spackle, 'spackle.py')

  def _find_project_root(self) -> str:
    """Find project root by looking up from cwd until finding spackle.py, then go up from .spackle"""
    current_dir = os.getcwd()
    
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
      spackle_py_path = os.path.join(current_dir, '.spackle', 'spackle.py')
      if os.path.exists(spackle_py_path):
        spackle_dir = os.path.join(current_dir, '.spackle')
        assert os.path.exists(spackle_dir), f"Expected .spackle directory at {spackle_dir}"
        return current_dir
      current_dir = os.path.dirname(current_dir)
    
    # If we can't find spackle.py, fall back to current working directory
    return os.getcwd()


class ClaudePaths:
  def __init__(self):
    self.root: str = self._find_project_root()
    self.claude_md: str = os.path.join(self.root, 'CLAUDE.md')
    self.mcp_config: str = os.path.join(self.root, '.mcp.json')
    self.claude: str = os.path.join(self.root, '.claude')
    self.settings: str = os.path.join(self.claude, 'settings.local.json')
    self.commands: str = os.path.join(self.claude, 'commands')

  def _find_project_root(self) -> str:
    """Find project root by looking up from cwd until finding spackle.py, then go up from .spackle"""
    current_dir = os.getcwd()
    
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
      spackle_py_path = os.path.join(current_dir, '.spackle', 'spackle.py')
      if os.path.exists(spackle_py_path):
        spackle_dir = os.path.join(current_dir, '.spackle')
        assert os.path.exists(spackle_dir), f"Expected .spackle directory at {spackle_dir}"
        return current_dir
      current_dir = os.path.dirname(current_dir)
    
    # If we can't find spackle.py, fall back to current working directory
    return os.getcwd()


#######
# MCP #
#######
class Server:
  @abstractmethod
  def serve(self):
    pass


class McpResult(pydantic.BaseModel):
  return_code: int
  response: str
  stderr: str
  stdout: str

  @staticmethod
  def Ok(response: str):
    return McpResult(
      return_code = 0,
      response = response,
      stderr = '',
      stdout = ''
    )



#########
# HOOKS #
#########
class HookTool(enum.Enum):
  Task = 'Task'
  Bash = 'Bash'
  Glob = 'Glob'
  Grep = 'Grep'
  Read = 'Read'
  Edit = 'Edit'
  MultiEdit = 'MultiEdit'
  Write = 'Write'
  WebFetch = 'WebFetch'
  WebSearch = 'WebSearch'


class HookEvent(enum.Enum):
  PreToolUse = 'PreToolUse'
  PostToolUse = 'PostToolUse'
  Notification = 'Notification'
  UserPromptSubmit = 'UserPromptSubmit'
  Stop = 'Stop'
  SubagentStop = 'SubagentStop'
  PreCompact = 'PreCompact'

  def match(self, value: str):
    return self.value == value


@dataclass
class Hook:
  name: str
  event: HookEvent
  tools: Optional[List[HookTool]]
  fn: Callable


class HookContext:
  def __init__(self, hook: Hook, request_str: str):
    self.hook = hook
    self.request_str = request_str

    try:
      self.request = json.loads(self.request_str)
    except json.JSONDecodeError as e:
      self.deny(f'Failed to decode JSON request for hook: {self.request_str}')

    if not hook.event.match(self.request['hook_event_name']):
      self.deny(
        f'The hook {hook.name} was invoked for {self.request["hook_event_name"]}, but is registered for {hook.event.value}. This is an error.'
      )

  def run(self):
    self.hook.fn(self)

  def allow(self, message: Optional[str] = None):
    if message:
      print(message, file=sys.stderr)
      sys.exit(1)

    sys.exit(0)

  def deny(self, message: Optional[str] = None):
    if message:
      print(message, file=sys.stderr)

    sys.exit(2)


###########
# SPACKLE #
###########
class Spackle:
  @dataclass
  class Colors:
    item = colorama.Fore.LIGHTBLUE_EX
    shell = colorama.Fore.LIGHTYELLOW_EX
    arrow = colorama.Fore.LIGHTGREEN_EX
    error = colorama.Fore.LIGHTRED_EX
    add = colorama.Fore.LIGHTGREEN_EX

  def __init__(self):
    colorama.init()
    self.colors = Spackle.Colors()

    self.paths = SpacklePaths()
    self.install = InstallPaths()

    self.mcp_registry = {}

    self.tools = {}
    self.hooks = {}
    self.prompts = {}
    self.prompt_files = {}

  ##############
  # DECORATORS #
  ##############
  def tool(self, fn: Callable) -> Callable:
    self.tools[fn.__name__] = fn
    return fn

  def mcp(self, name: str) -> Callable:
    def decorator(func):
      mcp_name = name or func.__name__
      if mcp_name in self.mcp_registry:
        raise Exception(f'{mcp_name} is already registered with spackle')

      self.mcp_registry[mcp_name] = func

      return func

    return decorator

  def hook(self, event: HookEvent, tools: Optional[List[HookTool]] = None) -> Callable:
    def decorator(fn: Callable) -> Callable:
      hook = Hook(name=fn.__name__, event=event, tools=tools or [], fn=fn)
      self.hooks[hook.name] = hook
      return fn

    return decorator

  def load(self, fn: Callable) -> Callable:
    fn()
    return fn

  def prompt(self, fn: Callable) -> Callable:
    self.prompts[fn.__name__] = fn
    return fn

  def prompt_file(self, fn: Callable) -> Callable:
    self.prompt_files[fn.__name__] = fn
    return fn

  ############
  # COMMANDS #
  ############
  def clean(self):
    claude = ClaudePaths()
    install = InstallPaths()

    self._remove_dir_except_files(install.spackle, [install.user_md, install.user_py])

    shutil.rmtree(claude.claude, ignore_errors=True)
    
    # Clean CLAUDE.md non-destructively
    if os.path.exists(claude.claude_md):
      self._clean_claude_md(claude.claude_md)
    
    # Clean .mcp.json non-destructively
    if os.path.exists(claude.mcp_config):
      self._clean_mcp_config(claude.mcp_config)
  
  def build(self, overwrite_provider: bool = False, provider: Provider = Provider.Claude) -> None:        
    match provider:
      case Provider.Claude:
        self._build_claude(overwrite_provider)
      case _:
        raise ValueError(f"Unsupported provider: {provider}")

  def _build_claude(self, overwrite_provider: bool) -> None:
    claude = ClaudePaths()
    install = InstallPaths()

    # Don't raw overwrite some popr soul's existing configuration
    is_claude_md = os.path.exists(claude.claude_md)
    is_claude_settings = os.path.exists(claude.settings)
    is_claude_mcp = os.path.exists(claude.mcp_config)
    is_existing_claude = is_claude_md or is_claude_settings or is_claude_mcp
    if is_existing_claude and not overwrite_provider:
      print(f'You ran {self._color("spackle build", self.colors.shell)}, but already have Claude configurations. spackle needs to own (i.e. have overwrite access) \n  - {self._color(claude.mcp_config, self.colors.item)}\n  - {self._color(claude.settings, self.colors.item)}')
      print(f'Rerun with {self._color("spackle " + " ".join(sys.argv[1:]), self.colors.shell)} {self._color("--overwrite-provider", self.colors.add)}')
      exit()


    # Make the .spackle subtree, where all of our stuff will go
    os.makedirs(install.spackle, exist_ok=True)

    # Make the .claude subtree, which follows how Claude expects to be set up
    os.makedirs(claude.claude, exist_ok=True)
    os.makedirs(claude.commands, exist_ok=True)

    # Run the user's Python file
    if os.path.exists(install.user_py):
      self._load_user_file()

    # @spackle.prompt
    for name, fn in self.prompts.items():
      try:
        content = fn()        
        command_file = os.path.join(claude.commands, f'{name}.md')
        with open(command_file, 'w') as f:
          f.write(content)
          
      except Exception as e:
        print(f'Error generating prompt file for {name}: {e}')

    # @spackle.prompt_file
    for name, fn in self.prompt_files.items():
      try:
        file_path = fn()
        file_path = os.path.join(install.root, file_path)
        if not os.path.exists(file_path):
          raise ValueError(f'Warning: Prompt file {file_path} not found, skipping {name}')

        shutil.copy2(file_path, os.path.join(claude.commands, f'{name}.md'))
          
      except Exception as e:
        print(f'Error copying prompt file for {name}: {e}')

    # .claude/commands
    self._copy_tree(self.paths.prompts, install.prompts)

    # Overwrite configuration files if we're asked to
    # .spackle/spackle.*
    self._copy_file(self.paths.user_md, install.user_md, force=False, log=True, flag='--overwrite-spackle')
    self._copy_file(self.paths.user_py, install.user_py, force=False, log=True, flag='--overwrite-spackle')

    # CLAUDE.md - create or update non-destructively
    self._update_claude_md(claude.claude_md, overwrite_provider)

    # .mcp.json - create or update non-destructively
    self._update_mcp_config(claude.mcp_config, overwrite_provider)

    # .claude/settings.local.json
    overwrite_settings = True
    if os.path.exists(claude.settings):
      overwrite_settings = overwrite_provider

    self._log_copy_action(claude.settings, force=overwrite_settings, flag='--overwrite-provider')
    if overwrite_settings:
      # .claude/settings/local.json
      settings = {
        'permissions': profiles['permissive'],
        'enabledMcpjsonServers': ['spackle-main', 'spackle-probe'],
        'disabledMcpjsonServers': ['spackle-sqlite'],
        'hooks': self._build_hooks(),
      }

      with open(claude.settings, 'w') as file:
        json.dump(settings, file, indent=2)

  def run_server(self, name: str) -> None:
    self._load_user_file()

    print(name, file = sys.stderr)
    if name not in self.mcp_registry:
      raise ValueError(f'MCP with name {name} was not registered with spackle')
    
    self.mcp_registry[name]()

  def run_tool(self, name: str) -> McpResult:
    self._load_user_file()

    return self.tools[name]()

  def run_hook(self, name: str, request: str) -> None:
    self._load_user_file()

    context = HookContext(self.hooks[name], request)
    context.run()
    context.deny('Tell the user that the hook exited without making a decision')

  def wrap_subprocess(self, *args, **kwargs):
    kwargs['stdin'] = subprocess.DEVNULL
    return subprocess.run(*args, **kwargs)

  #############
  # UTILITIES #
  #############
  def _log_copy_action(self, dest: str, force: bool, flag: str):
    install = InstallPaths()

    # Add a colored source and destination
    message = self._color(pathlib.Path(dest).relative_to(pathlib.Path(install.root)), self.colors.item)


    # Show whether --overwrite-provider was used
    if os.path.exists(dest):
      if force:
        message += f' ({self._color(flag, self.colors.shell)} specified; overwriting)'
      else:
        message += f' ({self._color(flag, self.colors.shell)} not specified; skipping)'

    print(message)

  def _copy_tree(self, source, dest, force: bool = False, log: bool = False, flag: str = None):
    if log:
      self._log_copy_action(dest, force, flag)

    if os.path.exists(dest):
      if force:
        shutil.rmtree(dest)
      else:
        return

    shutil.copytree(source, dest)

  def _copy_file(self, source, dest, force: bool = False, log: bool = False, flag: str = None):
    if log:
      self._log_copy_action(dest, force, flag)

    if os.path.exists(dest):
      if force:
        os.remove(dest)
      else:
        return

    shutil.copy2(source, dest)

  def _copy_dir_file(self, source, dest, file_name: str, force: bool = False, log: bool = False, flag: str = None):
    self._copy_file(
      os.path.join(source, file_name), os.path.join(dest, file_name), force, log
    )

  def _color(self, text: str, color) -> str:
    return f'{color}{text}{colorama.Style.RESET_ALL}'

  def _build_hooks(self) -> Dict:
    hooks = {}
    for hook in self.hooks.values():
      entry = self._ensure_hook(hooks, hook)
      entry['hooks'].append(
        {'type': 'command', 'command': f'spackle hook {hook.name}'}
      )

    return hooks

  def _ensure_hook(self, hooks, hook: Hook) -> Dict:
    if hook.event.value not in hooks:
      hooks[hook.event.value] = []

    matcher = '|'.join(tool.value for tool in hook.tools)

    for entry in hooks[hook.event.value]:
      if entry['matcher'] == matcher:
        return entry

    hooks[hook.event.value].append({'matcher': matcher, 'hooks': []})
    return hooks[hook.event.value][-1]

  def _load_user_file(self) -> bool:
    install = InstallPaths()
    module_name = 'spackle_user"'

    try:
      spec = importlib.util.spec_from_file_location(module_name, install.user_py)
      module = importlib.util.module_from_spec(spec)
      sys.modules[module_name] = module
      spec.loader.exec_module(module)
    except Exception as e:
      print(e, file=sys.stderr)
      exit(1)

    return True

  def _canonicalize_path(self, path: str) -> str:
    return pathlib.Path(path).resolve()

  def _is_file_path_within(self, file_path: str, directory: str) -> bool:
    return os.path.commonpath([directory, file_path]) == directory

  def _is_file_path_equal(self, a: str, b: str) -> bool:
    return self._canonicalize_path(a) == self._canonicalize_path(b)

  def _remove_dir_except_files(self, dir_path, keep_files):
    dir_path = pathlib.Path(dir_path)
    
    # Save files that exist
    saved_files = {}
    for filename in keep_files:
        file_path = dir_path / filename
        if file_path.exists():
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = pathlib.Path(tmp.name)
            shutil.copy2(file_path, tmp_path)  # preserves metadata
            saved_files[filename] = tmp_path
    
    # Nuke the directory
    shutil.rmtree(dir_path)
    
    # Restore saved files
    if saved_files:
        dir_path.mkdir(parents=True, exist_ok=True)
        for filename, tmp_path in saved_files.items():
            shutil.copy2(tmp_path, dir_path / filename)
            tmp_path.unlink()

  def _update_claude_md(self, claude_md_path: str, overwrite: bool) -> None:
    """Update CLAUDE.md non-destructively by adding spackle reference if not present"""
    self._log_copy_action(claude_md_path, force=overwrite, flag='--overwrite-provider')
    
    spackle_reference = "@.spackle/prompts/spackle.md"
    
    if os.path.exists(claude_md_path):
      if overwrite:
        # Overwrite mode - just create the file with our reference
        with open(claude_md_path, 'w') as f:
          f.write(f"{spackle_reference}\n")
      else:
        # Non-destructive mode - check if reference exists
        with open(claude_md_path, 'r') as f:
          lines = [line.rstrip('\n') for line in f]
        
        # Check if our reference already exists
        reference_exists = any(spackle_reference in line for line in lines)
        
        if not reference_exists:
          # Add our reference
          lines.append(spackle_reference)
          with open(claude_md_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    else:
      # File doesn't exist - create it with our reference
      with open(claude_md_path, 'w') as f:
        f.write(f"{spackle_reference}\n")

  def _update_mcp_config(self, mcp_config_path: str, overwrite: bool) -> None:
    """Update .mcp.json non-destructively by adding spackle servers if not present"""
    self._log_copy_action(mcp_config_path, force=overwrite, flag='--overwrite-provider')
    
    spackle_servers = {
      "spackle-main": {
        "command": "spackle",
        "args": ["serve", "main"]
      },
      "spackle-probe": {
        "command": "spackle",
        "args": ["serve", "probe"]
      },
      "spackle-sqlite": {
        "command": "spackle",
        "args": ["serve", "sqlite"]
      }
    }
    
    if os.path.exists(mcp_config_path):
      if overwrite:
        # Overwrite mode - create with just our servers
        config = {"mcpServers": spackle_servers}
        with open(mcp_config_path, 'w') as f:
          json.dump(config, f, indent=2)
      else:
        # Non-destructive mode - merge servers
        with open(mcp_config_path, 'r') as f:
          try:
            config = json.load(f)
          except json.JSONDecodeError:
            config = {}
        
        if "mcpServers" not in config:
          config["mcpServers"] = {}
        
        # Add spackle servers if they don't exist
        for server_name, server_config in spackle_servers.items():
          if server_name not in config["mcpServers"]:
            config["mcpServers"][server_name] = server_config
        
        with open(mcp_config_path, 'w') as f:
          json.dump(config, f, indent=2)
    else:
      # File doesn't exist - create it with our servers
      config = {"mcpServers": spackle_servers}
      with open(mcp_config_path, 'w') as f:
        json.dump(config, f, indent=2)

  def _clean_claude_md(self, claude_md_path: str) -> None:
    """Remove spackle reference from CLAUDE.md"""
    spackle_reference = "@.spackle/prompts/spackle.md"
    
    with open(claude_md_path, 'r') as f:
      lines = [line.rstrip('\n') for line in f]
    
    # Remove lines containing our reference
    cleaned_lines = [line for line in lines if spackle_reference not in line]
    
    if len(cleaned_lines) != len(lines):
      # Only rewrite if we removed something
      if cleaned_lines:
        with open(claude_md_path, 'w') as f:
          f.write('\n'.join(cleaned_lines) + '\n')
      else:
        # File would be empty, remove it
        os.remove(claude_md_path)

  def _clean_mcp_config(self, mcp_config_path: str) -> None:
    """Remove spackle servers from .mcp.json"""
    spackle_server_names = ["spackle-main", "spackle-probe", "spackle-sqlite"]
    
    with open(mcp_config_path, 'r') as f:
      try:
        config = json.load(f)
      except json.JSONDecodeError:
        return
    
    if "mcpServers" in config:
      # Remove spackle servers
      for server_name in spackle_server_names:
        config["mcpServers"].pop(server_name, None)
      
      # If mcpServers is now empty, remove it
      if not config["mcpServers"]:
        del config["mcpServers"]
    
    # If config is now empty, remove the file
    if not config:
      os.remove(mcp_config_path)
    else:
      with open(mcp_config_path, 'w') as f:
        json.dump(config, f, indent=2)


spackle = Spackle()


###########
# EXPORTS #
###########
def windows_to_wsl(windows_path: str) -> str:
  command = ['wslpath', '-a', '-u', windows_path]
  result = spackle.wrap_subprocess(command, capture_output=True, text=True)
  return result.stdout.strip()


def wsl_to_windows(wsl_path: str) -> str:
  command = ['wslpath', '-a', '-w', wsl_path]
  result = spackle.wrap_subprocess(command, capture_output=True, text=True)
  return result.stdout.strip()


tool = spackle.tool
hook = spackle.hook
mcp = spackle.mcp
load = spackle.load
prompt = spackle.prompt
prompt_file = spackle.prompt_file
wrap_subprocess = spackle.wrap_subprocess


#################
# BUILT IN MCPS #
#################
class SpackleMcps:
  @staticmethod
  @spackle.mcp(name='main')
  def main():
    mcp = fastmcp.FastMCP('spackle-main', on_duplicate_tools='replace')
    for name, fn in spackle.tools.items():
      print(name)
      mcp.tool(fn)

    mcp.run()


  @staticmethod
  @spackle.mcp(name='probe')
  def probe():
    from .probe import probe_server
    probe_server()


from .sqlite import sqlite_server


####################
# BUILT IN PROMPTS #
####################
@spackle.prompt_file
def spackle__refresh():
  return spackle.paths.prompts + '/spackle.md'

@spackle.prompt_file
def spackle__refresh_user():
  return spackle.paths.prompts + '/refresh-user-instructions.md'

@spackle.prompt_file
def spackle__refresh_rules():
  return spackle.paths.prompts + '/rules.md'

@spackle.prompt_file
def spackle__sketch():
  return spackle.paths.prompts + '/sketch.md'


##################
# BUILT IN TOOLS #
##################
@spackle.tool
def build() -> McpResult:
  """Build the project"""
  return McpResult(
    return_code=0,
    response='The build command has not been implemented in this project. It is imperative that you do not try to build the project through other means; instead, ask what to do.',
    stderr='',
    stdout='',
  )


@spackle.tool
def run() -> McpResult:
  """Run the project"""
  return McpResult(
    return_code=0,
    response='The run command has not been implemented in this project. It is imperative that you do not try to run the project through other means; instead, ask what to do.',
    stderr='',
    stdout='',
  )


@spackle.tool
def test() -> McpResult:
  """Run tests"""
  return McpResult(
    return_code=0,
    response='The test command has not been implemented in this project. Ask the user what to do.',
    stderr='',
    stdout='',
  )


##################
# BUILT IN HOOKS #
##################
@spackle.hook(
  event=HookEvent.PreToolUse,
  tools=[HookTool.Edit, HookTool.MultiEdit, HookTool.Write],
)
def ensure_spackle_templates_are_read_only(context: HookContext):
  context.allow()
  install = InstallPaths()
  file_path = context.request['tool_input']['file_path']
  file_path = spackle._canonicalize_path(file_path)

  message = f'You are not allowed to edit that file in {install.spackle}. Do not make a copy with your edits in a different location; ask me what you should do.'

  if spackle._is_file_path_within(file_path, install.prompts):
    context.deny(message)

  if spackle._is_file_path_equal(file_path, install.user_md):
    context.deny(message)

  if spackle._is_file_path_equal(file_path, install.user_py):
    context.deny(message)

  context.allow()


#######
# CLI #
#######
class CLI:
  @staticmethod
  @click.command()
  @click.option(
    '--overwrite-provider',
    is_flag=True,
    help='Overwrite existing files with a clean copy from spackle',
  )
  @click.option(
    '--provider',
    type=click.Choice(['claude']),
    default='claude',
    help='Provider to build for'
  )
  def build(overwrite_provider, provider):
    """Build configuration for provider and install spackle into ./spackle"""
    provider_enum = Provider(provider)
    spackle.build(overwrite_provider=overwrite_provider, provider=provider_enum)

  @staticmethod
  @click.command()
  def clean():
    """Remove all files generated by spackle"""
    spackle.clean()

  @staticmethod
  @click.command()
  @click.argument('name')
  def tool(name):
    """Run a tool defined in the main spackle MCP with @spackle.tool"""
    spackle.run_tool(name)

  @staticmethod
  @click.command()
  @click.argument('name')
  def hook(name):
    """Run a function declared with @spackle.hook"""
    if sys.stdin.isatty():
      example_command = spackle._color(
        f'echo foo | spackle hook {name}', spackle.colors.shell
      )
      print(
        f"Since hooks are only useful insofar as they are called by Claude, you can't invoke a hook without passing the JSON request via stdin (e.g. {example_command})"
      )
      return

    spackle.run_hook(name, sys.stdin.read())

  @staticmethod
  @click.command()
  @click.argument('name')
  def serve(name):
    """Serve an MCP server"""
    spackle.run_server(name)

  @staticmethod
  @click.command()
  @click.argument('url', required=False, default='https://httpbin.org/get')
  def debug(url):
    """Debug command to test HTTP requests"""
    try:
      print(f'Making request to: {url}')
      response = requests.get(url, timeout=10)
      print(f'Status Code: {response.status_code}')
      print(f'Response Headers: {dict(response.headers)}')
      print(f'Response Content:')
      print(response.text)
    except requests.RequestException as e:
      print(f'Request failed: {e}', file=sys.stderr)
    except Exception as e:
      print(f'Unexpected error: {e}', file=sys.stderr)

  @staticmethod
  @click.command()
  @click.argument('source', required=False)
  @click.option(
    '-o', '--output', type=click.Path(), help='Output file (default: stdout)'
  )
  def jira(source, output):
    """Parse Jira RSS/XML export to markdown

    SOURCE can be:
    - A file path to an XML file
    - A Jira URL (browse or XML format)
    - If omitted, reads from stdin
    """

    xml_content = None

    if source:
      # Check if source looks like a URL
      if source.startswith(('http://', 'https://')):
        # It's a URL - fetch it
        try:
          xml_content = fetch_jira_xml_from_url(source, timeout=10)
        except requests.RequestException as e:
          print(f'Error fetching URL: {e}', file=sys.stderr)
          return
        except Exception as e:
          print(f'Error processing URL: {e}', file=sys.stderr)
          return
      else:
        # It's a file path
        try:
          with open(source, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        except FileNotFoundError:
          print(f"Error: File '{source}' not found", file=sys.stderr)
          return
        except Exception as e:
          print(f'Error reading file: {e}', file=sys.stderr)
          return
    elif not sys.stdin.isatty():
      # Read from stdin
      xml_content = sys.stdin.read()
    else:
      print('Error: Please provide a file path, URL, or pipe XML data to stdin')
      print('Usage: spackle jira <file.xml> [-o output.md]')
      print('   or: spackle jira <jira-url> [-o output.md]')
      print('   or: cat file.xml | spackle jira [-o output.md]')
      return

    if not xml_content:
      print('Error: No XML content to process', file=sys.stderr)
      return

    try:
      result = parse_jira_to_markdown(xml_content)
      if output:
        with open(output, 'w', encoding='utf-8') as f:
          f.write(result)
        print(f'Output written to {output}')
      else:
        print(result)
    except Exception as e:
      print(f'Error parsing Jira XML: {e}', file=sys.stderr)


@click.group()
def cli():
  """Spackle - MCP server for build, test, and run tools"""
  pass


# Register commands
cli.add_command(CLI.build)
cli.add_command(CLI.clean)
cli.add_command(CLI.tool)
cli.add_command(CLI.hook)
cli.add_command(CLI.serve)
cli.add_command(CLI.debug)
cli.add_command(CLI.jira)


########
# MAIN #
########
def main():
  cli()