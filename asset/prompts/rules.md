# Absolute Rules
## ALWAYS
- ALWAYS use the `spackle` MCP server to build, run, or test the project.
- ALWAYS respect the notes left for you around the codebase with the tag `@llm`. These tags include information just for you.
- ALWAYS adhere strongly to the code style of the repository.Y
- ALWAYS to use the `probe` MCP when searching code. If it fails, fall back to your usual method.
  - PREFER to read @.spackle/prompts/probe-usage-guide.md before you begin searching code
- ALWAYS write artifacts to @.spackle/output -- this includes summaries, plans, temporary files from scripts.

## NEVER
- NEVER finish until the build passes with no warnings and the unit tests pass with no failures
- NEVER use `cd` to make a command work. If you have trouble running a command because of your working directory, ask me to implement a tool in the main `spackle` MCP.
- NEVER comment your code unless explicitly asked.
- NEVER use emojis. It is imperative that you never use emojis.