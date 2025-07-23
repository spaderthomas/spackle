#!/usr/bin/env python

import os
import subprocess

import spackle


@spackle.mcp(name='probe')
class ProbeServer:
  def __init__(self):
    pass

  def serve(self):
    # Get the project root directory
    project_paths = spackle.ProjectPaths()

    # Set up environment variables for ProbeAI
    env = os.environ.copy()
    env['PROBE_DEFAULT_PATHS'] = project_paths.root
    env['PROBE_MAX_TOKENS'] = '100'

    # Run probe with the configured environment
    # subprocess.run(["npx", "-y", "@buger/probe-mcp"], check=True)
    subprocess.run(['npx', '-y', '@buger/probe-mcp'], env=env, check=True)


def main():
  server = ProbeServer()
  server.run()


if __name__ == '__main__':
  main()
