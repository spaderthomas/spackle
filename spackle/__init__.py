#!/usr/bin/env python

import argparse
import os
import platform
import time
import shutil
import sqlite3
import subprocess
import sys

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
    self.sqlite      = os.path.join(self.source, 'sqlite.py')
    self.probe       = os.path.join(self.source, 'probe.py')
    self.agent     = os.path.join(self.project, 'agent')
    self.profiles    = os.path.join(self.agent, 'profiles')
    self.template    = os.path.join(self.agent, 'spackle')


class InitPaths():
  def __init__(self):
    self.root: str = os.getcwd()
    self.claude_md: str = os.path.join(self.root, 'CLAUDE.md')
    self.mcp_json: str = os.path.join(self.root, '.mcp.json')
    self.claude: str = os.path.join(self.root, '.claude')
    self.settings: str = os.path.join(self.claude, 'settings.local.json')
    
    self.spackle: str = os.path.join(self.claude, 'spackle')

class Server:
  def __init__(self):
    self.mcp = FastMCP('spackle', on_duplicate_tools='replace')
  
  def serve(self):
    self.mcp.run()

class Spackle:
  def __init__(self):
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
  def init(self):
    init = InitPaths()
    os.makedirs(init.claude, exist_ok=True)
    self._copy_tree(self.paths.template,                                  init.spackle)
    self._copy_file(os.path.join(self.paths.profiles, 'everything.json'), init.settings)
    self._copy_file(os.path.join(self.paths.agent, 'CLAUDE.md'),          init.claude_md)
    self._copy_file(os.path.join(self.paths.agent, 'CLAUDE.md'),          init.claude_md)
  
  def serve(self):
    spackle._build_mcp(name).serve()

  # Utilities
  def _copy_tree(self, source, dest):
    print(f'Copying {source} -> {dest}')
    shutil.copytree(source, dest)

  def _copy_file(self, source, dest):
    print(f'Copying {source} -> {dest}')
    shutil.copy2(source, dest)

  def _build_mcp(self, name: str):
    if name not in self.mcps:
      self.mcps[name] = self.mcp_registry[name]()
    return self.mcps[name]

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


@spackle.command
def init():
  spackle.init()

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
    for arg_name, arg_type, arg_help in cmd_info.get('args', []):
      subparser.add_argument(arg_name, type=arg_type, help=arg_help)
  
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
