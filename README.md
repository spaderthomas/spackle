# Overview
Coding agents are quite good, but if you expect to hop into a session with no configuration or tooling and start ripping out good code, you'll be disappointed. The agents are like us; they need to be able to easily build their code and run its tests to form a feedback loop. Unfortunately, providing scripts to do this is often brittle from the agent's perspective (e.g. needing to be run from a certain directory, needing to source a file containing build commands, etc).

More, there are a lot of excellent MCPs which make them more powerful in nearly any project, but setting them up for every new project is tedious.

Hence, `spackle`. It's a simple project which:
- Vendors or implements MCP servers, and exposes them through a CLI (`uv run spackle serve some_mcp`) as well as `.mcp.json`
- Adds consistent instructions to every project (e.g. `You're not done until all the tests pass` or `Use the Spackle MCP to build the project`)
- Adds a three step planning process (design, make a software spec, write code) backed by markdown files
- Provides permission profiles, so you don't have to keep copying a blessed `settings.local.json`
- Scaffolds a new project; for example, a new Claude project will contain:
  - `.mcp.json`, pointing to `spackle`'s MCP servers
  - `CLAUDE.md`, which points to `.claude/spackle/instructions.md`
  - `.claude/settings.local.json`, copied from one of our profiles

# Installation
```bash
mkdir project
cd project
uv init

# Clone Spackle anywhere; for example, inside the project
git clone git@github.com:spaderthomas/spackle.git 
uv add --editable ./spackle
```

# Usage
Run some MCP servers with UV from the command line
```bash
uv run spackle serve main 
uv run spackle serve probe
```

You can run the MCP servers in the MCP inspector
```bash
npx @modelcontextprotocol/inspector
# Use "uv" as the command and "run spackle serve main" as the arguments
```

You're going to want a thin Python script which can build, run, and test your project. This will probably just call whatever build tools you already use as a subprocess and return the output and result.
```python
## main.py
import spackle

# Use this exactly the same as you'd use FastMCP's tool decorator
@spackle.tool
def build() -> str:
  print('Project build successfully!')
  pass

spackle.serve('main')
```

Invoke it like this (for example, in the MCP inspector)
```bash
uv run main.py
```

You can serve MCPs from Python the same as the CLI
```python
import spackle

spackle.serve('probe')
```