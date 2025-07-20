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
from colorama import Fore, Style

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Optional, List

from pydantic import BaseModel
from fastmcp import FastMCP

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
    self.agent       = os.path.join(self.asset, 'agent')
    self.spackle       = os.path.join(self.agent, 'spackle')
    self.profiles        = os.path.join(self.spackle, 'profiles')
    self.tasks           = os.path.join(self.spackle, 'tasks')
    self.templates       = os.path.join(self.spackle, 'templates')


class InitPaths():
  def __init__(self):
    self.root: str = os.getcwd()
    self.claude_md: str  = os.path.join(self.root, 'CLAUDE.md')
    self.mcp_config: str = os.path.join(self.root, '.mcp.json')
    self.claude: str     = os.path.join(self.root, '.claude')
    self.settings: str     = os.path.join(self.claude, 'settings.local.json')
    self.spackle: str      = os.path.join(self.claude, 'spackle')
    self.profiles: str       = os.path.join(self.spackle, 'profiles')
    self.tasks: str          = os.path.join(self.spackle, 'tasks')
    self.templates: str      = os.path.join(self.spackle, 'templates')
    
    self.spackle: str = os.path.join(self.claude, 'spackle')

####################
# SPACKLE-MAIN MCP #
####################
class Server:
  def __init__(self):
    self.mcp = FastMCP('spackle-main', on_duplicate_tools='replace')
  
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

class ClaudeHook():
  def __init__(self, request_str: str):
    self.request_str = request_str
    pass

  def __enter__(self):
    try:
      self.request = json.loads(self.request_str)
    except json.JSONDecodeError as e:
      self.deny(f'Failed to decode JSON request for hook: {self.request_str}')

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.deny('Tell the user that the hook exited without making a decision')

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
    item = Fore.LIGHTBLUE_EX
    shell = Fore.LIGHTYELLOW_EX
    arrow = Fore.LIGHTGREEN_EX

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
  
  def command(self, *args, **kwargs):
    # Handle both @command and @command(...) usage
    def decorator(fn):
      command = {
        'func': fn,
        'name': kwargs.get('name', fn.__name__),
        'args': kwargs.get('args', [])
      }
      self.commands[command['name']] = command
      return fn
    
    # If called with a function directly (@command)
    if len(args) == 1 and callable(args[0]) and not kwargs:
      fn = args[0]
      self.commands[fn.__name__] = {'func': fn, 'args': []}
      return fn
    # If called with arguments (@command(...))
    else:
      return decorator

  def mcp(self, cls):
    self.mcp_registry[cls.__name__] = cls
  
  def hook(self, fn):
    self.hooks[fn.__name__] = fn

  ############
  # COMMANDS #
  ############
  def init(self, force=False):
    init = InitPaths()
    os.makedirs(init.claude, exist_ok=True)
    os.makedirs(init.spackle, exist_ok=True)
    self._copy_tree(self.paths.spackle, init.spackle, force=force)
    self._copy_file(os.path.join(self.paths.profiles, 'default.json'), init.settings, force=force)
    self._copy_file(os.path.join(self.paths.agent, 'CLAUDE.md'), init.claude_md, force=force)
    self._copy_file(os.path.join(self.paths.agent, '.mcp.json'), init.mcp_config, force=force)
  
  def serve(self):
    spackle._build_mcp(name).serve()

  #############
  # UTILITIES #
  #############
  def _log_copy_action(self, source, dest, force):
    print(f'{self._color(source, self.colors.item)} {self._color("->", self.colors.arrow)} {self._color(dest, self.colors.item)}')

    if os.path.exists(dest):
      if force:
        print(f'Directory exists and {self._color("--force", self.colors.shell)} was specified; removing')
      else:
        print(f'Directory exists, but {self._color("--force", self.colors.shell)} was not specified; skipping')

  def _copy_tree(self, source, dest, force=False):
    self._log_copy_action(source, dest, force)

    if os.path.exists(dest):
      if force:
        shutil.rmtree(dest)
      else:
        return

    shutil.copytree(source, dest)
    print('OK!')

  def _copy_file(self, source, dest, force=False):
    self._log_copy_action(source, dest, force)

    if os.path.exists(dest):
      if force:
        os.remove(dest)
      else:
        return

    shutil.copy2(source, dest)
    print('OK!')

  def _build_mcp(self, name: str):
    if name not in self.mcps:
      self.mcps[name] = self.mcp_registry[name]()
    return self.mcps[name]
  
  def _color(self, text: str, color) -> str:
    return f"{color}{text}{Style.RESET_ALL}"

spackle = Spackle()


#########
# TOOLS #
#########
@spackle.tool
def build() -> str:
  """Build the project"""
  return 'build'

@spackle.tool
def run() -> str:
  """Run the project"""
  return 'run'

@spackle.tool
def test() -> str:
  """Run tests"""
  return 'test'

#########
# HOOKS #
#########
@spackle.hook
def ensure_spackle_templates_are_read_only(request_str: str):
  with ClaudeHook(request_str) as hook:
    tools = [ClaudeTool.Edit, ClaudeTool.MultiEdit, ClaudeTool.Write]

    if hook.match(tools):
      hook.deny()


#######
# CLI #
#######
# The CLI is also exposed through the Python API (e.g. spackle.call('build') from your code)
@spackle.command(args=[
  ('--force', 'store_true', 'Overwrite existing files with a clean copy from spackle')
])
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
    ('hook', str, 'Name of the hook to invoke')
  ]
)
def run_hook(hook: str):
  if sys.stdin.isatty():
    example_command = spackle._color(f'echo foo | spackle hook {hook}', spackle.colors.shell)
    print(f"Since hooks are only useful insofar as they are called by Claude, you can't invoke a hook without passing the JSON request via stdin (e.g. {example_command})")
    return

  return spackle.hooks[hook](sys.stdin.read())

@spackle.command(args=[
  ('name', str, 'Name of the MCP server to run')
])
def serve(name: str = None):
  spackle._build_mcp(name).serve()


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

if __name__ == "__main__":
  main()
