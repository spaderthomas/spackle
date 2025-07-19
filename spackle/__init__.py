#!/usr/bin/env python

import os
import platform
import time
import sys
import subprocess
import sqlite3

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
    self.file = os.path.dirname(os.path.abspath(__file__))
    self.project = os.path.realpath(os.path.join(self.file, '..', '..', '..'))
    self.spackle_mcp = os.path.join(self.project, 'spackle')
    self.source = os.path.join(self.project, 'source')
    self.mcp = os.path.join(self.source, 'mcp')
    self.sqlite_mcp = os.path.join(self.mcp, 'sqlite')
    self.probe_mcp = os.path.join(self.mcp, 'probe')

class Spackle:
  def __init__(self):
    self.paths = Paths()

    self.mcp = FastMCP("spackle")
    self.mcps = {}

    self.tools = {}
    self.tool(Spackle.build)
    self.tool(Spackle.run)
    self.tool(Spackle.test)

  def tool(self, fn):
    self.tools[fn.__name__] = fn
    self.mcp.tool(fn)

  def call(self, tool: str):
    return self.tools[tool]()

  def serve(self):
    self.mcp.run()

  @staticmethod
  def build() -> str:
    """Build the project"""
    return 'build_project'

  @staticmethod
  def run() -> str:
    """Run the project"""
    return 'run_project'

  @staticmethod
  def test() -> str:
    """Run tests"""
    return 'test'
    
  @property
  def probe(self):
    if 'probe' not in self.mcps:
      self.mcps['probe'] = ProbeServer()
    return self.mcps['probe']
  
  @property
  def sqlite(self):
    if 'sqlite' not in self.mcps:
      self.mcps['sqlite'] = SQLiteServer()
    return self.mcps['sqlite']


spackle = Spackle()

import sys
sys.modules[__name__] = spackle

def main():
  spackle.serve()

if __name__ == "__main__":
  main()
