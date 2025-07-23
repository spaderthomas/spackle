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
class Paths:
  def __init__(self):
    self.file = os.path.dirname(os.path.abspath(__file__))
    self.project = os.path.realpath(os.path.join(self.file, '..'))
    self.source = os.path.join(self.project, 'spackle')
    self.asset = os.path.join(self.project, 'asset')
    self.claude = os.path.join(self.asset, 'claude')
    self.claude_md = os.path.join(self.claude, 'CLAUDE.md')
    self.mcp_config = os.path.join(self.claude, '.mcp.json')
    self.prompts = os.path.join(self.asset, 'prompts')
    self.tasks = os.path.join(self.asset, 'tasks')
    self.templates = os.path.join(self.asset, 'templates')


class ClaudePaths:
  def __init__(self):
    self.root: str = os.getcwd()
    self.claude_md: str = os.path.join(self.root, 'CLAUDE.md')
    self.mcp_config: str = os.path.join(self.root, '.mcp.json')
    self.claude: str = os.path.join(self.root, '.claude')
    self.settings: str = os.path.join(self.claude, 'settings.local.json')
    self.spackle: str = os.path.join(self.root, '.spackle')
    self.tasks: str = os.path.join(self.spackle, 'tasks')
    self.templates: str = os.path.join(self.spackle, 'templates')
    self.prompts: str = os.path.join(self.spackle, 'prompts')
    self.user_prompt: str = os.path.join(self.prompts, 'user.md')
    self.claude_prompt: str = os.path.join(self.prompts, 'claude.md')
    self.spackle_prompt: str = os.path.join(self.prompts, 'spackle.md')
    self.config: str = os.path.join(self.spackle, 'settings.json')


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

  def __init__(self):
    colorama.init()
    self.colors = Spackle.Colors()

    self.paths = Paths()

    self.mcp_registry = {}

    self.mcps = {}
    self.tools = {}
    self.hooks = {}

  ##############
  # DECORATORS #
  ##############
  def tool(self, fn: Callable) -> Callable:
    self.tools[fn.__name__] = fn
    self.mcps['main'].mcp.tool(fn)
    return fn

  def mcp(self, name: str) -> Callable:
    def decorator(cls):
      mcp_name = name or cls.__name__
      if mcp_name in self.mcp_registry:
        raise Exception(f'{mcp_name} is already registered with spackle')

      self.mcp_registry[mcp_name] = cls

      if len(self.mcp_registry) == 1:
        self._build_mcp(mcp_name)

      return cls

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

  ############
  # COMMANDS #
  ############
  def build(self, force: bool = False, file: Optional[str] = None, provider: Provider = Provider.Claude) -> None:
    # Build the Spackle config file first, so the user file is loaded if present
    config = {'file_path': '', 'function_name': ''}

    match provider:
      case Provider.Claude:
        self._build_claude(force, file, config)
      case Provider.Foo:
        self._build_foo(force, file, config)
      case _:
        raise ValueError(f"Unsupported provider: {provider}")

  def _build_claude(self, force: bool, file: str | None, config: dict) -> None:
    project = ClaudePaths()

    # Load existing config if present
    if os.path.exists(project.config) and not file:
      with open(project.config, 'r') as f:
        existing_config = json.load(f)
        config['file_path'] = existing_config.get('file_path', '')
        config['function_name'] = existing_config.get('function_name', '')
        config['foo'] = existing_config.get('function_name', '')

    if file:
      # Parse file:function format
      function_name = None
      if ':' in file:
        file_path, function_name = file.split(':', 1)
      else:
        file_path = file

      file_path = os.path.join(project.root, file_path)
      config['file_path'] = file_path
      config['function_name'] = function_name or ''

      if not self._load_user_file_from_path(file_path, function_name):
        print(f'{self._color(file_path, self.colors.error)} does not exist; exiting')
        exit(1)

    # Build the Claude config file
    settings = {
      'permissions': profiles['permissive'],
      'enabledMcpjsonServers': ['spackle-main', 'spackle-probe'],
      'disabledMcpjsonServers': ['spackle-sqlite'],
      'hooks': self._build_hooks(),
    }

    # Set up the filesystem
    is_new_project = not os.path.exists(project.spackle)
    is_existing_claude_config = os.path.exists(project.claude_md) or os.path.exists(
      project.settings
    )
    if is_new_project and is_existing_claude_config and not force:
      print(
        f'You are initializing a new project, but already have Claude configurations. spackle needs to own (i.e. have overwrite access):'
      )
      print(f'  - {self._color(project.mcp_config, self.colors.item)}')
      print(f'  - {self._color(project.settings, self.colors.item)}')

      rerun = ['spackle'] + sys.argv[1:]
      print(
        f'Rerun with {self._color(" ".join(rerun), self.colors.item)} {self._color("--force", self.colors.shell)}'
      )
      exit()

    os.makedirs(project.claude, exist_ok=True)
    os.makedirs(project.spackle, exist_ok=True)
    os.makedirs(project.prompts, exist_ok=True)

    # Never overwrite the stuff that Claude uses at runtime
    self._copy_dir_file(self.paths.prompts, project.prompts, 'user.md')
    self._copy_dir_file(self.paths.prompts, project.prompts, 'claude.md')
    self._copy_tree(self.paths.tasks, project.tasks)

    # Always overwrite our internal read only stuff
    self._copy_dir_file(self.paths.prompts, project.prompts, 'spackle.md', force=True)
    self._copy_tree(self.paths.templates, project.templates, force=True)

    with open(project.config, 'w') as file:
      json.dump(config, file, indent=2)

    # Overwrite configuration files if we're asked to
    self._copy_file(self.paths.mcp_config, project.mcp_config, force=force, log=True)
    self._copy_file(self.paths.claude_md, project.claude_md, force=force, log=True)

    overwrite_settings = True
    if os.path.exists(project.settings):
      overwrite_settings = force

    self._log_copy_action('generated file', project.settings, overwrite_settings)
    if overwrite_settings:
      with open(project.settings, 'w') as file:
        json.dump(settings, file, indent=2)

  def _build_foo(self, force: bool, file: str | None, config: dict) -> None:
    # Default provider implementation - just creates .spackle directory structure
    project_root = os.getcwd()
    spackle_dir = os.path.join(project_root, '.spackle')
    
    os.makedirs(spackle_dir, exist_ok=True)
    config_file = os.path.join(spackle_dir, 'settings.json')
    
    with open(config_file, 'w') as f:
      json.dump(config, f, indent=2)
    
    print(f"Created basic .spackle structure for provider 'foo'")

  def run_server(self, name: str) -> None:
    self._load_user_file_from_config()

    self._build_mcp(name).serve()

  def run_tool(self, name: str) -> McpResult:
    self._load_user_file_from_config()

    return self.tools[name]()

  def run_hook(self, name: str, request: str) -> None:
    self._load_user_file_from_config()

    context = HookContext(self.hooks[name], request)
    context.run()
    context.deny('Tell the user that the hook exited without making a decision')

  def wrap_subprocess(self, *args, **kwargs):
    kwargs['stdin'] = subprocess.DEVNULL
    return subprocess.run(*args, **kwargs)

  #############
  # UTILITIES #
  #############
  def _log_copy_action(self, source, dest, force):
    message = ''
    if os.path.exists(dest):
      if force:
        message = f'{message} ({self._color("--force", self.colors.shell)} specified; overwriting)'
      else:
        message = f'{message} ({self._color("--force", self.colors.shell)} not specified; skipping)'

    message = f'{message} {self._color(source, self.colors.item)} {self._color("->", self.colors.arrow)} {self._color(dest, self.colors.item)}'

    print(message)

  def _copy_tree(self, source, dest, force=False, log=False):
    if log:
      self._log_copy_action(source, dest, force)

    if os.path.exists(dest):
      if force:
        shutil.rmtree(dest)
      else:
        return

    shutil.copytree(source, dest)

  def _copy_file(self, source, dest, force=False, log=False):
    if log:
      self._log_copy_action(source, dest, force)

    if os.path.exists(dest):
      if force:
        os.remove(dest)
      else:
        return

    shutil.copy2(source, dest)

  def _copy_dir_file(self, source, dest, file_name, force=False, log=False):
    self._copy_file(
      os.path.join(source, file_name), os.path.join(dest, file_name), force, log
    )

  def _build_mcp(self, name: str):
    if name not in self.mcps:
      self.mcps[name] = self.mcp_registry[name]()
    return self.mcps[name]

  def _color(self, text: str, color) -> str:
    return f'{color}{text}{colorama.Style.RESET_ALL}'

  def _build_hooks(self) -> Dict:
    hooks = {}
    for hook in self.hooks.values():
      entry = self._ensure_hook(hooks, hook)
      entry['hooks'].append(
        {'type': 'command', 'command': f'uv run spackle hook {hook.name}'}
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

  def _load_user_file_from_path(
    self, file_path: str, function_name: Optional[str] = None
  ) -> bool:
    module_name = 'spackle_user'

    if not os.path.exists(file_path):
      return False

    try:
      spec = importlib.util.spec_from_file_location(module_name, file_path)
      module = importlib.util.module_from_spec(spec)
      sys.modules[module_name] = module
      spec.loader.exec_module(module)

      # If a specific function is specified, call it
      if function_name:
        func = getattr(module, function_name, None)
        if func is None:
          print(
            f"Function '{function_name}' not found in '{file_path}'",
            file=sys.stderr,
          )
          exit(1)
        func()
    except Exception as e:
      print(e, file=sys.stderr)
      exit(1)

    return True

  def _load_user_file_from_config(self) -> bool:
    project = ClaudePaths()

    if not os.path.exists(project.config):
      return False

    with open(project.config, 'r') as file:
      config = json.load(file)
      function_name = config.get('function_name', None)
      return self._load_user_file_from_path(
        config['file_path'], function_name if function_name else None
      )

  def _canonicalize_path(self, path: str) -> str:
    return pathlib.Path(path).resolve()

  def _is_file_path_within(self, file_path: str, directory: str) -> bool:
    return os.path.commonpath([directory, file_path]) == directory

  def _is_file_path_equal(self, a: str, b: str) -> bool:
    return self._canonicalize_path(a) == self._canonicalize_path(b)


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
wrap_subprocess = spackle.wrap_subprocess


#################
# BUILT IN MCPS #
#################
@spackle.mcp(name='main')
class DefaultServer(Server):
  def __init__(self):
    self.mcp = fastmcp.FastMCP('spackle-main', on_duplicate_tools='replace')

  def serve(self):
    self.mcp.run()


from .probe import ProbeServer
from .sqlite import SqliteServer


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
  project = ProjectPaths()
  file_path = context.request['tool_input']['file_path']
  file_path = spackle._canonicalize_path(file_path)

  message = f'You are not allowed to edit that file in {project.spackle}. Do not make a copy with your edits in a different location; ask me what you should do.'

  if spackle._is_file_path_within(file_path, project.templates):
    context.deny(message)

  if spackle._is_file_path_equal(file_path, project.user_prompt):
    context.deny(message)

  if spackle._is_file_path_equal(file_path, project.spackle_prompt):
    context.deny(message)

  if spackle._is_file_path_equal(file_path, project.settings):
    context.deny(message)

  context.allow()


#######
# CLI #
#######
class CLI:
  @staticmethod
  @click.command()
  @click.option(
    '--force',
    is_flag=True,
    help='Overwrite existing files with a clean copy from spackle',
  )
  @click.option('--file', type=str, help='Python file to copy to the project')
  @click.option(
    '--provider',
    type=click.Choice(['claude', 'foo']),
    default='claude',
    help='Provider to build for (default: claude)'
  )
  def build(force, file, provider):
    """Build the project"""
    provider_enum = Provider(provider)
    result = spackle.build(force=force, file=file, provider=provider_enum)
    print(result)

  @staticmethod
  @click.command()
  @click.argument('name')
  def tool(name):
    """Run a tool"""
    result = spackle.run_tool(name)
    print(result.response)

  @staticmethod
  @click.command()
  @click.argument('name')
  def hook(name):
    """Run a hook"""
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
