#!/usr/bin/env python

import subprocess

import spackle

from fastmcp import FastMCP

@spackle.mcp(name = 'probe')
class ProbeServer:
  def __init__(self):
    self.mcp = FastMCP("spackle-probe")
    
  def serve(self):
    subprocess.run(["npx", "-y", "@buger/probe-mcp@latest"], check=True)


def main():
  server = ProbeServer()
  server.run()


if __name__ == "__main__":
  main()