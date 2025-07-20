#!/usr/bin/env python

import argparse
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
from typing import Protocol

from pydantic import BaseModel
from fastmcp import FastMCP

from .probe import ProbeServer
from .sqlite import SqliteServer

@dataclass
class Paths:
  file: str = field(init=False)
  project: str = field(init=False)
  source: str = field(init=False)
  mcp: str = field(init=False)
  spackle_mcp: str = field(init=False)
  sqlite_mcp: str = field(init=False)
  probe_mcp: str = field(init=False)

  def __post_init__(self):
    self.file    = os.path.dirname(os.path.abspath(__file__))
    self.project = os.path.realpath(os.path.join(self.file, '..'))
    self.source    = os.path.join(self.project, 'spackle')
    self.asset     = os.path.join(self.project, 'asset')
    self.agent       = os.path.join(self.asset, 'agent')
    self.profiles      = os.path.join(self.agent, 'profiles')
    self.template      = os.path.join(self.agent, 'spackle')


class InitPaths():
  def __init__(self):
    self.root: str = os.getcwd()
    self.claude_md: str = os.path.join(self.root, 'CLAUDE.md')
    self.mcp_config: str = os.path.join(self.root, '.mcp.json')
    self.claude: str = os.path.join(self.root, '.claude')
    self.settings: str = os.path.join(self.claude, 'settings.local.json')
    
    self.spackle: str = os.path.join(self.claude, 'spackle')

class Server:
  def __init__(self):
    self.mcp = FastMCP('spackle', on_duplicate_tools='replace')
  
  def serve(self):
    self.mcp.run()

class Spackle:
  @dataclass
  class Colors:
    item = Fore.LIGHTBLUE_EX
    argument = Fore.LIGHTYELLOW_EX
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

  # Decorators
  def tool(self, fn):
    self.tools[fn.__name__] = fn
    self.mcps['main'].mcp.tool(fn)
  
  def command(self, *args, **kwargs):
    # Handle both @command and @command(...) usage
    def decorator(fn):
      # Store function with its argument specs
      self.commands[fn.__name__] = {
        'func': fn,
        'args': kwargs.get('args', [])
      }
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
  
  # Commands
  def init(self, force=False):
    init = InitPaths()
    os.makedirs(init.claude, exist_ok=True)
    self._copy_tree(self.paths.template, init.spackle, force=force)
    self._copy_file(os.path.join(self.paths.profiles, 'default.json'), init.settings, force=force)
    self._copy_file(os.path.join(self.paths.agent, 'CLAUDE.md'), init.claude_md, force=force)
    self._copy_file(os.path.join(self.paths.agent, '.mcp.json'), init.mcp_config, force=force)
  
  def serve(self):
    spackle._build_mcp(name).serve()

  # Utilities
  def _log_copy_action(self, source, dest, force):
    print(f'{self._color(source, self.colors.item)} {self._color("->", self.colors.arrow)} {self._color(dest, self.colors.item)}')

    if os.path.exists(dest):
      if force:
        print(f'Directory exists and {self._color("--force", self.colors.argument)} was specified; removing')
      else:
        print(f'Directory exists, but {self._color("--force", self.colors.argument)} was not specified; skipping')

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


@spackle.command(args=[
  ('--force', 'store_true', 'Overwrite existing files with a clean copy from spackle')
])
def init(force=False):
  spackle.init(force=force)

@spackle.command(args=[
  ('tool', str, 'Name of the tool to call')
])
def call(tool: str):
  return spackle.tools[tool]()

@spackle.command(args=[
  ('name', str, 'Name of the MCP server to run')
])
def serve(name: str = None):
  spackle._build_mcp(name).serve()


def tool(fn):
  spackle.tool(fn)


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
