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
    self.tools = {}
    self.tool(Spackle.build)
    self.tool(Spackle.run)
    self.tool(Spackle.test)

  def tool(self, fn):
    self.tools[fn.__name__] = fn
    self.mcp.tool(fn)

  @staticmethod
  def build() -> str:
    return 'build'

  @staticmethod
  def run() -> str:
    return 'run'

  @staticmethod
  def test() -> str:
    return 'test'


server = Spackle()    

def tool(fn):
  server.tool(fn)

def run():
  server.mcp.run()

def call(tool: str):
  return server.tools[tool]()

def find_msbuild():
  
    export SP_VSWHERE=$(wslpath -a -u "C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe")
  export SP_MSBUILD_DIR_WINDOWS=$("$SP_VSWHERE" -find "msbuild" | tr -d '\r')
  export SP_MSBUILD_DIR_WSL="$(wslpath -a -u "$SP_MSBUILD_DIR_WINDOWS")"
  export SP_MSBUILD="$SP_MSBUILD_DIR_WSL/Current/Bin/MSBuild.exe"; 
