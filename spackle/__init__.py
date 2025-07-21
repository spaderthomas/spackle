#!/usr/bin/env python

import argparse
import enum
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

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Optional, List, Callable, Dict

from .profiles import profiles
from .probe import ProbeServer
from .sqlite import SqliteServer

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


class ProjectPaths():
  def __init__(self):
    self.root: str = os.getcwd()
    self.claude_md: str  = os.path.join(self.root, 'CLAUDE.md')
    self.mcp_config: str = os.path.join(self.root, '.mcp.json')
    self.claude: str     = os.path.join(self.root, '.claude')
    self.settings: str     = os.path.join(self.claude, 'settings.local.json')
    self.spackle: str      = os.path.join(self.claude, 'spackle')
    self.tasks: str          = os.path.join(self.spackle, 'tasks')
    self.templates: str      = os.path.join(self.spackle, 'templates')
    
    self.spackle: str = os.path.join(self.claude, 'spackle')

####################
# SPACKLE-MAIN MCP #
####################
class Server:
  def __init__(self):
    self.mcp = fastmcp.FastMCP('spackle-main', on_duplicate_tools='replace')
  
  def serve(self):
    self.mcp.run()

#########
# HOOKS #
#########
class ClaudeKey(enum.Enum):
  Tool = 'tool_name'

class ClaudeTool(enum.Enum):
  Edit = 'Edit'
  MultiEdit = 'MultiEdit'
  Write = 'Write'

class ClaudeHook(enum.Enum):
  PreToolUse = 'PreToolUse'

@dataclass
class Hook:
  name: str
  kind: ClaudeHook
  tools: List[ClaudeTool]
  fn: Callable


class HookContext():
  def __init__(self, hook: Hook, request_str: str):
    self.hook = hook
    self.request_str = request_str

    try:
      self.request = json.loads(self.request_str)
    except json.JSONDecodeError as e:
      self.deny(f'Failed to decode JSON request for hook: {self.request_str}')

  def run(self):
    self.hook.fn(self)

  def allow(self):
    sys.exit(0)

  def deny(self, message: Optional[str] = None):
    if message:
      print(message, file=sys.stderr)
      sys.exit(2)
    else:
      sys.exit(1)

  def contains(self, key: ClaudeKey)-> bool:
    return key.value in self.request

  def get(self, key: ClaudeKey):
    if key.value not in self.request:
      return None

    return self.request[key.value]

  def match(self, tools: List[ClaudeTool]) -> bool:
    requested_tool = self.get(ClaudeKey.Tool)
    for tool in tools:
      if tool == requested_tool:
        return True

    return False

class Spackle:
  @dataclass
  class Colors:
    item =  colorama.Fore.LIGHTBLUE_EX
    shell = colorama.Fore.LIGHTYELLOW_EX
    arrow = colorama.Fore.LIGHTGREEN_EX

  def __init__(self):
    colorama.init()
    self.colors = Spackle.Colors()

    self.paths = Paths()

    self.mcp_registry = {
      'main': Server,
      'probe': ProbeServer,
      'sqlite': SqliteServer,
    }
    self.mcps = {}
    self._build_mcp('main')

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

  def mcp(self, cls):
    self.mcp_registry[cls.__name__] = cls
    return cls

  def hook(self, kind: ClaudeHook, tools: List[ClaudeTool]):
    def decorator(fn):
      hook = Hook(
        name = fn.__name__,
        kind = kind,
        tools = tools,
        fn = fn
      )
      self.hooks[hook.name] = hook

    return decorator

  ############
  # COMMANDS #
  ############
  def init(self, force=False):
    project = ProjectPaths()
    os.makedirs(project.claude, exist_ok=True)
    os.makedirs(project.spackle, exist_ok=True)
    self._copy_tree(self.paths.templates, project.templates, force=force)
    self._copy_tree(self.paths.tasks, project.tasks, force=force)
    self._copy_file(self.paths.claude_md, project.claude_md, force=force)
    self._copy_file(self.paths.mcp_config, project.mcp_config, force=force)


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

    with open(project.settings, 'w') as file:
      json.dump(settings, file, indent=2)

  
  def serve(self):
    spackle._build_mcp(name).serve()

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
    if hook.kind.value not in hooks:
      hooks[hook.kind.value] = []

    matcher = "|".join(tool.value for tool in hook.tools)

    for entry in hooks[hook.kind.value]:
      if entry['matcher'] == matcher:
        return entry

    hooks[hook.kind.value].append({
      'matcher': matcher,
      'hooks': []
    })
    return hooks[hook.kind.value][-1]

  
spackle = Spackle()


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
@spackle.hook(kind=ClaudeHook.PreToolUse, tools=[ClaudeTool.Edit, ClaudeTool.MultiEdit, ClaudeTool.Write])
def ensure_spackle_templates_are_read_only(context: HookContext):
  context.deny("Not today, big guy")

#######
# CLI #
#######
@spackle.command(
  args = [
    ('--force', 'store_true', 'Overwrite existing files with a clean copy from spackle')
  ]
)
def init(force=False):
  spackle.init(force=force)


@spackle.command(
  name = 'tool',
  args = [
    ('tool', str, 'Name of the tool to call')
  ]
)
def run_tool(tool: str):
  return spackle.tools[tool]()


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

  context = HookContext(spackle.hooks[name], sys.stdin.read())
  context.run()
  context.deny('Tell the user that the hook exited without making a decision')

@spackle.command(
  args = [
    ('name', str, 'Name of the MCP server to run')
  ]
)
def serve(name: str = None):
  spackle._build_mcp(name).serve()


@spackle.command()
def debug():
  create_task('asdf')


##############
# DECORATORS #
##############
def tool(fn):
  spackle.tool(fn)

def hook(fn):
  spackle.hook(fn)


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