#!/usr/bin/env python

import argparse
import enum
import importlib
import json
import os
import platform
import time
import shutil
import sqlite3
import subprocess
import sys

import colorama
import pydantic
import fastmcp

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
    self.file    = os.path.dirname(os.path.abspath(__file__))
    self.project = os.path.realpath(os.path.join(self.file, '..'))
    self.source    = os.path.join(self.project, 'spackle')
    self.asset     = os.path.join(self.project, 'asset')
    self.claude      = os.path.join(self.asset, 'claude')
    self.claude_md     = os.path.join(self.claude, 'CLAUDE.md')
    self.mcp_config    = os.path.join(self.claude, '.mcp.json')
    self.prompts      = os.path.join(self.asset, 'prompts')
    self.tasks        = os.path.join(self.asset, 'tasks')
    self.templates    = os.path.join(self.asset, 'templates')


class ProjectPaths:
  def __init__(self):
    self.root: str = os.getcwd()
    self.claude_md: str  = os.path.join(self.root, 'CLAUDE.md')
    self.mcp_config: str = os.path.join(self.root, '.mcp.json')
    self.claude: str     = os.path.join(self.root, '.claude')
    self.settings: str     = os.path.join(self.claude, 'settings.local.json')
    self.spackle: str    = os.path.join(self.root, '.spackle')
    self.tasks: str        = os.path.join(self.spackle, 'tasks')
    self.templates: str    = os.path.join(self.spackle, 'templates')
    self.config: str       = os.path.join(self.spackle, 'settings.json')


#######
# MCP #
#######
class Server:
  @abstractmethod
  def serve(self):
    pass


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

class HookContext():
  def __init__(self, hook: Hook, request_str: str):
    self.hook = hook
    self.request_str = request_str

    try:
      self.request = json.loads(self.request_str)
    except json.JSONDecodeError as e:
      self.deny(f'Failed to decode JSON request for hook: {self.request_str}')

    if not hook.event.match(self.request['hook_event_name']):
      self.deny(f'The hook {hook.name} was invoked for {self.request["hook_event_name"]}, but is registered for {hook.event.value}. This is an error.')

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
    item =  colorama.Fore.LIGHTBLUE_EX
    shell = colorama.Fore.LIGHTYELLOW_EX
    arrow = colorama.Fore.LIGHTGREEN_EX
    error = colorama.Fore.LIGHTRED_EX

  def __init__(self):
    colorama.init()
    self.colors = Spackle.Colors()

    self.paths = Paths()

    self.mcp_registry = {
    }

    self.mcps = {}
    self.tools = {}
    self.commands = {}
    self.hooks = {}

  ##############
  # DECORATORS #
  ##############
  def tool(self, fn):
    self.tools[fn.__name__] = fn
    self.mcps['main'].mcp.tool(fn)
    return fn
  
  def command(self, name=None, args=None):
    def decorator(fn):
      command = {
        'func': fn,
        'name': name or fn.__name__,
        'args': args or []
      }
      self.commands[command['name']] = command
      return fn
      
    return decorator

  def mcp(self, name: str):
    def decorator(cls):
      mcp_name = name or cls.__name__
      if mcp_name in self.mcp_registry:
        raise Exception(f'{mcp_name} is already registered with spackle')

      self.mcp_registry[mcp_name] = cls

      if len(self.mcp_registry) == 1:
        self._build_mcp(mcp_name)

      return cls

    return decorator

  def hook(self, event: HookEvent, tools: Optional[List[HookTool]] = None):
    def decorator(fn):
      hook = Hook(
        name = fn.__name__,
        event = event,
        tools = tools or [],
        fn = fn
      )
      self.hooks[hook.name] = hook

    return decorator

  ############
  # COMMANDS #
  ############
  def build(self, force: bool = False, file: str = None):
    project = ProjectPaths()

    # Build the Spackle config file first, so the user file is loaded if present
    config = {
      'file_path': ''
    }

    if file:
      file_path = os.path.join(project.root, file)
      config['file_path'] = file_path
      module_name = 'spackle_user'

      if not self._load_user_file_from_path(file_path):
        print(f'{self._color(file_path, self.colors.error)} does not exist; exiting')

    # Build the Claude config file
    settings = {
      'permissions': profiles['permissive'],
      'enabledMcpjsonServers': [
        'spackle-main',
        'spackle-probe'
      ],
      'disabledMcpjsonServers': [
        'spackle-sqlite'
      ],
      'hooks': self._build_hooks()
    }    

    # Set up the filesystem
    os.makedirs(project.claude, exist_ok=True)
    os.makedirs(project.spackle, exist_ok=True)
    self._copy_tree(self.paths.templates, project.templates, force=force)
    self._copy_file(self.paths.claude_md, project.claude_md, force=force)
    self._copy_file(self.paths.mcp_config, project.mcp_config, force=force)

    # Don't stomp on existing tasks if we're just trying to reinitialize after, say, adding a hook
    if not os.path.exists(project.tasks):
      self._copy_tree(self.paths.tasks, project.tasks, force=force)

    with open(project.settings, 'w') as file:
      json.dump(settings, file, indent=2)

    with open(project.config, 'w') as file:
      json.dump(config, file, indent=2)

  
  def serve(self, name: str):
    self._load_user_file_from_config()

    spackle._build_mcp(name).serve()

  def run_tool(self, name: str):
    self._load_user_file_from_config()

    self.tools[name]()

  def run_hook(self, name: str, request: str):
    self._load_user_file_from_config()

    context = HookContext(spackle.hooks[name], request)
    context.run()
    context.deny('Tell the user that the hook exited without making a decision')

  #########
  # TOOLS #
  #########
  def create_task(self, task_name: str):
    paths = ProjectPaths()
    os.makedirs(paths.tasks, exist_ok=True)
    
    max_number = 0
    if os.path.exists(paths.tasks):
      for filename in os.listdir(paths.tasks):
        if filename[:3].isdigit() and filename[3:4] == '_':
          try:
            number = int(filename[:3])
            max_number = max(max_number, number)
          except ValueError:
            pass
    
    next_number = max_number + 1
    task_path = os.path.join(paths.tasks, f"{next_number:03d}_{task_name}")

    os.makedirs(task_path, exist_ok=True)

    files = ['plan.md', 'spec.md', 'scratch.md']
    for file in files:
      self._copy_file(os.path.join(self.paths.templates, file), os.path.join(task_path, file), force=True)

    return task_path

  #############
  # UTILITIES #
  #############
  def _log_copy_action(self, source, dest, force):
    message = f'{self._color(source, self.colors.item)} {self._color("->", self.colors.arrow)} {self._color(dest, self.colors.item)}'

    if os.path.exists(dest):
      if force:
        message = f'{message} ({self._color("--force", self.colors.shell)} specified; overwriting)'
      else:
        message = f'{message} ({self._color("--force", self.colors.shell)} not specified; skipping)'

    print(message)

  def _copy_tree(self, source, dest, force=False):
    self._log_copy_action(source, dest, force)

    if os.path.exists(dest):
      if force:
        shutil.rmtree(dest)
      else:
        return

    shutil.copytree(source, dest)

  def _copy_file(self, source, dest, force=False):
    self._log_copy_action(source, dest, force)

    if os.path.exists(dest):
      if force:
        os.remove(dest)
      else:
        return

    shutil.copy2(source, dest)

  def _build_mcp(self, name: str):
    if name not in self.mcps:
      self.mcps[name] = self.mcp_registry[name]()
    return self.mcps[name]
  
  def _color(self, text: str, color) -> str:
    return f"{color}{text}{colorama.Style.RESET_ALL}"

  def _build_hooks(self) -> Dict:
    hooks = {}
    for hook in self.hooks.values():
      entry = self._ensure_hook(hooks, hook)
      entry['hooks'].append({
        'type': 'command',
        'command': f'uv run spackle hook {hook.name}'
      })    

    return hooks

  def _ensure_hook(self, hooks, hook: Hook) -> Dict:
    if hook.event.value not in hooks:
      hooks[hook.event.value] = []

    matcher = "|".join(tool.value for tool in hook.tools)

    for entry in hooks[hook.event.value]:
      if entry['matcher'] == matcher:
        return entry

    hooks[hook.event.value].append({
      'matcher': matcher,
      'hooks': []
    })
    return hooks[hook.event.value][-1]

  def _load_user_file_from_path(self, file_path: str) -> bool:
    module_name = 'spackle_user'

    if not os.path.exists(file_path):
      return False

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return True

  def _load_user_file_from_config(self) -> bool:
    project = ProjectPaths()

    if not os.path.exists(project.config):
      return False

    with open(project.config, 'r') as file:
      config = json.load(file)
      return self._load_user_file_from_path(config['file_path'])
  
spackle = Spackle()


##############
# DECORATORS #
##############
tool = spackle.tool
hook = spackle.hook
mcp = spackle.mcp


#################
# BUILT IN MCPS #
#################
@spackle.mcp(name = 'main')
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
def build() -> str:
  """Build the project"""
  return 'The build command has not been implemented in this project. Do not try to build the project through other means; instead, ask what to do.'

@spackle.tool
def run() -> str:
  """Run the project"""
  return 'The run command has not been implemented in this project. Do not try to run the project through other means; instead, ask what to do.'

@spackle.tool
def test() -> str:
  """Run tests"""
  return 'The test command has not been implemented in this project. Do not try to run the tests through other means; instead, ask what to do.'

@spackle.tool
def create_task(task_name: str) -> str:
  """Builds the scaffolding for a new task using the plan -> spec -> code method"""
  task_path = spackle.create_task(task_name)
  return f'{task_path} was created for the task {task_name}. Your plan, spec, and to-do file are inside. Read them to familiarize yourself and follow any given instruction.'


##################
# BUILT IN HOOKS #
##################
@spackle.hook(event=HookEvent.PreToolUse, tools=[HookTool.Edit, HookTool.MultiEdit, HookTool.Write])
def ensure_spackle_templates_are_read_only(context: HookContext):
  project = ProjectPaths()
  file_path = context.request['tool_input']['file_path']
  is_within_spackle = os.path.commonpath([project.spackle, file_path]) == project.spackle
  is_within_tasks = os.path.commonpath([project.tasks, file_path]) == project.tasks

  if is_within_spackle and not is_within_tasks:
    context.deny(f'You are not allowed to edit files in {project.spackle}, except for your {project.tasks}')

  context.allow()


#######
# CLI #
#######
# spackle build
@spackle.command(
  name = 'build',
  args = [
    ('--force', 'store_true', 'Overwrite existing files with a clean copy from spackle'),
    ('--file', str, 'Python file to copy to the project')
  ]
)
def run_build(force=False, file: str = None):
  spackle.build(force=force, file=file)

# spackle tool
@spackle.command(
  name = 'tool',
  args = [
    ('name', str, 'Name of the tool to call')
  ]
)
def run_tool(name: str):
  return spackle.run_tool(name)

# spackle hook
@spackle.command(
  name = 'hook',
  args = [
    ('name', str, 'Name of the hook to invoke')
  ]
)
def run_hook(name: str):
  if sys.stdin.isatty():
    example_command = spackle._color(f'echo foo | spackle hook {name}', spackle.colors.shell)
    print(f"Since hooks are only useful insofar as they are called by Claude, you can't invoke a hook without passing the JSON request via stdin (e.g. {example_command})")
    return

  spackle.run_hook(name, sys.stdin.read())

# spackle serve
@spackle.command(
  args = [
    ('name', str, 'Name of the MCP server to run')
  ]
)
def serve(name: str = None):
  spackle.serve(name)

# spackle debug
@spackle.command()
def debug():
  create_task('asdf')


########
# MAIN #
########
def main():
  parser = argparse.ArgumentParser(description='Spackle - MCP server for build, test, and run tools')
  subparsers = parser.add_subparsers(dest='command', help='Available commands')
  
  # Create subparser for each command
  for cmd_name, cmd_info in spackle.commands.items():
    cmd_fn = cmd_info['func']
    subparser = subparsers.add_parser(cmd_name, help=cmd_fn.__doc__)
    for arg_spec in cmd_info.get('args', []):
      if len(arg_spec) == 3:
        arg_name, arg_type, arg_help = arg_spec
        if arg_type == 'store_true':
          subparser.add_argument(arg_name, action='store_true', help=arg_help)
        else:
          subparser.add_argument(arg_name, type=arg_type, help=arg_help)
      else:
        subparser.add_argument(*arg_spec)
  
  args = parser.parse_args()

  if args.command in spackle.commands:
    cmd_info = spackle.commands[args.command]
    # Extract command-specific arguments
    cmd_args = {k: v for k, v in vars(args).items() if k != 'command'}

    cmd_info['func'](**cmd_args)
  else:
    parser.print_help()