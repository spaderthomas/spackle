<p align="center">
    <img src="asset/github/boon_bane.png" alt="Always check the alt text!" width="210">
</p>

<p align="center">
  <i>made by the good folks at boon/bane games</i>
</p>

# Shill
[Deep Copy](https://store.steampowered.com/app/2639990/Deep_Copy/) is a top down point-and-click literary adventure set in a hand-painted science fiction world. [Click here to wishlist or play the free demo on Steam!](https://store.steampowered.com/app/2639990/Deep_Copy/)

# Motivation
*[quit yapping and take me to the examples](#Installation)*

**Problem #1**: Coding agents need to be able to easily build a project and run its tests to be effective. **If you boot up an agent with no configuration, no tooling, and no knowledge of how to test the code it produces, you will fail.**

**Problem #2**: Unfortunately, agents often forget how to run all but the simplest commands given in prompts. 

**Problem #3**: Adding functionality to Claude (MCPs, hooks, tools) should be as close to trivially easy as possible, and yet it often isn't

**Problem #4**: Agents need to be instructed to iterate on a plan before writing code, or else slop is guaranteed.

# What does it do?
`spackle` lets you expose your MCPs, hooks, and tools to Claude across projects with zero futzing. It uses those same capabilities to bundle some highly useful MCPs, and provides a default MCP that an agent can use to build, run, and test your project with zero points of failure.

A motivating example:
```python
# my-spackle-stuff.py
import spackle

@spackle.hook(event=spackle.HookEvent.PreToolUse, tools=[spackle.HookTool.Write])
def deny_everything(context: spackle.HookContext):
  context.deny('I have no permissions and I must code')
```

```bash
# In a new project, rebuild your Claude configuration files
spackle build --file my-spackle-stuff.py
```

Claude will now call your Python function as a hook at the appropriate time. That's it.

# Overview
- `spackle.hook` decorates a plain Python function and adds it to Claude's hooks
- `spackle.mcp` decorates a plain Python class and add it to the Claude's MCP configuration
- `spackle.tool` decorates a plain Python function and adds it to the built-in `spackle` MCP, without needing to configure a server or figure out the exact command to allow Claude to invoke it
- Run one command, `spackle build`, to instantly set up Claude with all your stuff in any directory. 

In addition to allowing you to write your own Claude extensions, `spackle` also:
- Vendors or implements (and will continue to add) useful MCP servers and
  - Exposes them through a CLI (e.g. `spackle serve sqlite`) for easy usage anywhere
  - Automatically configures Claude to know about them.
- Adds consistent instructions to every project (e.g. `You're not done until all the tests pass` or `Use the Spackle MCP to build the project`)
- Adds a three step planning process (design, make a software spec, write code) backed by a single directory and a few lines to `CLAUDE.md`
- Provides permission profiles, so you don't have to keep copying a blessed `settings.local.json`

## Caveat Emptor!
This is my personal stuff. There are definitely bugs. There are use cases which aren't implemented correctly. But it works, and it's very useful. **PRs are welcome!**

Largest such issue: `spackle` expects to own `CLAUDE.md`, `.mcp.json`, and `.claude`. By default, `spackle build` won't touch any file that already exists, so your project won't get overwritten. Use `--force` to rebuild after adding a decorated item (merely updating the code of an existing item doesn't require anything).

I'm sorry it works this way. For me, this is perfectly fine, but I wouldn't want to use a third party library that did this. I am fixing it -- the project is still very young. However, `spackle` works *great* for me, and if you sink into its cold embrace you may find it does for you too.


# Installation
```bash
# Clone Spackle anywhere and install it globally. If your project is already a UV project, you can install spackle with uv add like any other package.
git clone git@github.com:spaderthomas/spackle.git 
uv.exe tool install --editable ./spackle
```

# Usage
## Minimal
Initialize a bare project with the stuff `spackle` provides. Run `spackle` from the directory you're running Claude.
```bash
spackle build
```

## Example: Add build, run, and test commands
Initialize a project that'll tell Claude how to build, run, and test your project. Use the names `build`, `run`, and `test`, since `spackle` instructs the agent to use these tools. Rebuild your configuration after you add (not just modify) anything.
```python
# my-spackle-stuff.py
import spackle
import subprocess

# These are just FastMCP tools. Zero difference.
@spackle.tool
def build() -> str:
  subprocess.run(['npm', 'run', 'build'], check=True)
  return 'Anything you want to tell the agent after a successful build'

@spackle.tool
def run() -> str:
  subprocess.run(['npm', 'run', 'dev'], check=True)
  return 'Likewise'

@spackle.tool
def test() -> str:
  subprocess.run(['npm', 'run', 'test'], check=True)
  return 'Ditto'
```

```bash
spackle build --file my-spackle-stuff.py
claude /mcp
```

## Example: Add a hook
```python
# my-spackle-stuff.py
import spackle

@spackle.hook(event=spackle.HookEvent.PreToolUse, tools=[spackle.HookTool.Write])
def deny_everything(context: spackle.HookContext):
  context.deny('I have no permissions and I must code')
```

```bash
spackle build --file my-spackle-stuff.py
claude "

```


## Example: Spin up an MCP server
It is no easier to write the *code* compared to using FastMCP directly, but `spackle serve foo` is really easy compared to trying to get the right path to your Python script and ensuring dependencies are installed in the environment.
```python
import spackle
import fastmcp

@spackle.mcp
class Foo():
  def __init__(self):
    self.mcp = fastmcp.FastMCP('foo')
  
  def serve(self):
    self.mcp.run()
```

```bash
spackle build --file my-spackle-stuff.py
spackle serve foo
```

## Example: Add a quick MCP tool without a server
Add a tool to the default MCP server. `spackle build` omitted for brevity.
```python
@spackle.tool
def foo(task_name: str) -> str:
  '''The foo tool is critical. You must call it before any action whatsoever.'''
  return 'bar'
```

## Example: Run one of `spackle`'s vendored MCPs
```bash
uv run spackle serve sqlite
uv run spackle serve probe
```

## Example: Use `spackle` with the MCP inspector
```bash
npx @modelcontextprotocol/inspector
# command: "uv:
# args: "run spackle serve main"
```