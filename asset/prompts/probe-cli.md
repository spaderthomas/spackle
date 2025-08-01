# CLI Reference (Commands & Flags)

Complete reference documentation for all Probe command-line interface commands, options, and usage examples.

## Search Command

Find code across your entire codebase:

```bash
probe search <QUERY> [PATH] [OPTIONS]
```

### Core Options

| Option | Function |
|--------|----------|
| `<QUERY>` | **Required**: What to search for |
| `[PATH]` | Where to search (default: current directory) |
| `--files-only` | List matching files without code blocks |
| `--ignore <PATTERN>` | Additional patterns to ignore |
| `--exclude-filenames, -n` | Exclude filenames from matching |
| `--reranker, -r <TYPE>` | Algorithm: `hybrid`, `hybrid2`, `bm25`, `tfidf` |
| `--frequency, -s` | Enable smart token matching (default) |
| `--max-results <N>` | Limit number of results |
| `--max-bytes <N>` | Limit total bytes of code |
| `--max-tokens <N>` | Limit total tokens (for AI) |
| `--allow-tests` | Include test files and code |
| `--any-term` | Match any search term (OR logic) |
| `--no-merge` | Keep code blocks separate |
| `--merge-threshold <N>` | Max lines between blocks to merge (default: 5) |
| `--session <ID>` | Session ID for caching results |
| `-o, --format <TYPE>` | Output as: `color` (default), `terminal`, `markdown`, `plain`, `json`, `xml` |

### Command Examples

```bash
# Basic search - current directory
probe search "authentication flow"

# Search in specific folder
probe search "updateUser" ./src/api

# Limit for AI context windows
probe search "error handling" --max-tokens 8000

# Find raw files without parsing
probe search "config" --files-only

# Elastic search queries
# Use AND operator for terms that must appear together
probe search "error AND handling" ./

# Use OR operator for alternative terms
probe search "login OR authentication OR auth" ./src

# Group terms with parentheses for complex queries
probe search "(error OR exception) AND (handle OR process)" ./

# Use wildcards for partial matching
probe search "auth* connect*" ./

# Exclude terms with NOT operator
probe search "database NOT sqlite" ./

# Output as JSON for programmatic use
probe search "authentication" --format json

# Output as XML
probe search "authentication" --format xml
```

## Extract Command

Pull complete code blocks from specific files and lines:

```bash
probe extract <FILES> [OPTIONS]
```

### Extract Options
| Option | Function |
|--------|----------|
| `<FILES>` | Files to extract from (e.g., `main.rs:42` or `main.rs#function_name`) |
| `-c, --context <N>` | Add N context lines |
| `-k, --keep-input` | Preserve and display original input content |
| `--prompt <TEMPLATE>` | System prompt template for LLM models (`engineer`, `architect`, or path to file) |
| `--instructions <TEXT>` | User instructions for LLM models |
| `-o, --format <TYPE>` | Output as: `color` (default), `terminal`, `markdown`, `plain`, `json`, `xml` |
| `-o, --format <TYPE>` | Output as: `color` (default), `terminal`, `markdown`, `plain`, `json`, `xml` |

### Extraction Examples

```bash
# Get function containing line 42
probe extract src/main.rs:42

# Extract multiple blocks
probe extract src/auth.js:15 src/api.js:27

# Extract by symbol name
probe extract src/main.rs#handle_extract

# Extract a specific line range
probe extract src/main.rs:10-20

# Output as JSON
probe extract src/handlers.rs:108 --format json

# Output as XML
probe extract src/handlers.rs:108 --format xml

# Add surrounding context
probe extract src/utils.rs:72 --context 5

# Preserve original input alongside extracted code
probe extract src/main.rs:42 --keep-input

# Extract from error output while preserving original messages
rustc main.rs 2>&1 | probe extract -k

# Extract code with LLM prompt and instructions
probe extract src/auth.rs#authenticate --prompt engineer --instructions "Explain this authentication function"

# Extract code with custom prompt template
probe extract src/api.js:42 --prompt /path/to/custom/prompt.txt --instructions "Refactor this code"
```

## Query Command

Find specific code structures using tree-sitter patterns:

```bash
probe query <PATTERN> <PATH> [OPTIONS]
```

### Query Options

| Option | Function |
|--------|----------|
| `<PATTERN>` | Tree-sitter pattern to search for |
| `<PATH>` | Where to search |
| `--language <LANG>` | Specify language (inferred from files if omitted) |
| `--ignore <PATTERN>` | Additional patterns to ignore |
| `--allow-tests` | Include test code blocks |
| `--max-results <N>` | Limit number of results |
| `-o, --format <TYPE>` | Output as: `color` (default), `terminal`, `markdown`, `plain`, `json`, `xml` |

### Query Examples

```bash
# Find Rust functions
probe query "fn $NAME($$$PARAMS) $$$BODY" ./src --language rust

# Find Python functions
probe query "def $NAME($$$PARAMS): $$$BODY" ./src --language python

# Find Go structs
probe query "type $NAME struct { $$$FIELDS }" ./src --language go

# Find C++ classes
probe query "class $NAME { $$$METHODS };" ./src --language cpp

# Output as JSON for programmatic use
probe query "fn $NAME($$$PARAMS) $$$BODY" ./src --language rust --format json
```

## Output Formats

Probe supports multiple output formats to suit different needs:

| Format | Description |
|--------|-------------|
| `color` | Colorized terminal output (default) |
| `terminal` | Plain terminal output without colors |
| `markdown` | Markdown-formatted output |
| `plain` | Plain text output without formatting |
| `json` | JSON-formatted output for programmatic use |
| `xml` | XML-formatted output for programmatic use |

For detailed information about the JSON and XML output formats, see the [Output Formats](./output-formats.md) documentation.

## Power Techniques

### From Compiler Errors

Feed error output directly to extract relevant code:

```bash
# Extract code from compiler errors
rustc main.rs 2>&1 | probe extract

# Pull code from test failures
go test ./... | probe extract
```

### Unix Pipeline Integration

Chain with other tools for maximum effect:

```bash
# Find then filter
probe search "database" | grep "connection"

# Process & format
probe search "api" --format json | jq '.results[0]'
```

## Command Combinations

Create powerful workflows by combining features:

```bash
# Find authentication code without tests
probe search "authenticate" --max-results 10 --ignore "test" --no-merge

# Extract specific functions with context
grep -n "handleRequest" ./src/*.js | cut -d':' -f1,2 | probe extract --context 3

# Find and extract error handlers
probe search "error handling" --files-only | xargs -I{} probe extract {} --format markdown
```

## Session-Based Caching

Avoid seeing the same code blocks multiple times in a session:

```bash
# First search - generates a session ID
probe search "authentication" --session ""
# Session: a1b2 (example output)

# Subsequent searches - reuse the session ID
probe search "login" --session "a1b2"
# Will skip code blocks already shown in the previous search

## Chat Command (`probe-chat`)

Engage in an interactive chat session with the Probe AI agent or send single messages for non-interactive use.

```bash
probe-chat [PATH] [OPTIONS]
```

### Chat Options

| Option | Function |
|--------|----------|
| `[PATH]` | Path to the codebase to search (overrides `ALLOWED_FOLDERS` env var) |
| `-d, --debug` | Enable debug mode for verbose logging |
| `--model-name <model>` | Specify the AI model to use (e.g., `claude-3-opus-20240229`, `gpt-4o`) |
| `-f, --force-provider <provider>` | Force a specific provider (`anthropic`, `openai`, `google`) |
| `-w, --web` | Run in web interface mode instead of CLI |
| `-p, --port <port>` | Port for web server (default: 8080) |
| `-m, --message <message>` | Send a single message and exit (non-interactive) |
| `-s, --session-id <sessionId>` | Specify a session ID for the chat |
| `--json` | Output response as JSON in non-interactive mode |
| `--max-iterations <number>` | Max tool iterations allowed (default: 30) |
| `--prompt <value>` | Use a custom prompt (`architect`, `code-review`, `support`, `engineer`, path to file, or string) |
| `--allow-edit` | **Enable code editing via the `implement` tool (uses Aider)** |
| `--trace-file [path]` | Enable file-based tracing (default: ./probe-traces.jsonl) |
| `--trace-remote <url>` | Enable remote tracing to OpenTelemetry collector |
| `--trace-console` | Enable console tracing for debugging |

### Code Editing (`--allow-edit`)

The `--allow-edit` flag lets Probe make changes to your code files.

#### How It Works

When you enable editing, Probe can modify your code when you ask it to:
- "Fix this bug in main.py"
- "Add error handling to this function"
- "Refactor this code to be cleaner"

#### What You Need

1. **Install Aider**: Probe uses a tool called Aider to make code changes.
   ```bash
   pip install aider-chat
   ```

2. **File Permissions**: Make sure Probe can write to your project files.

#### Usage Examples

```bash
# Start chat with editing enabled
probe-chat --allow-edit

# Ask for a specific change
probe-chat --allow-edit --message "Add comments to the main function"
```

#### Important Safety Notes

- **Always review changes** before keeping them
- **Test your code** after Probe makes changes
- **Start small** - try simple changes first to see how it works

#### GitHub Actions Alternative

If you're using Probe in GitHub Actions, you can use `allow_suggestions` instead, which creates reviewable suggestions rather than direct changes. See the [GitHub Actions Integration](./integrations/github-actions.md#code-modification-options) guide for details.

### OpenTelemetry Tracing

The `--trace-file`, `--trace-remote`, and `--trace-console` flags enable comprehensive monitoring and observability for AI interactions.

#### Tracing Options

**File Tracing (`--trace-file`)**
- Saves traces to a JSON Lines format file for offline analysis
- Default file path: `./probe-traces.jsonl`
- Custom path: `--trace-file ./my-traces.jsonl`

**Remote Tracing (`--trace-remote`)**
- Sends traces to OpenTelemetry collectors (Jaeger, Zipkin, etc.)
- Requires collector URL: `--trace-remote http://localhost:4318/v1/traces`

**Console Tracing (`--trace-console`)**
- Outputs traces to console for debugging
- Useful for development and troubleshooting

#### Usage Examples

```bash
# Enable file-based tracing
probe-chat --trace-file

# Enable remote tracing to Jaeger
probe-chat --trace-remote http://localhost:4318/v1/traces

# Enable console tracing for debugging
probe-chat --trace-console

# Combine multiple tracing options
probe-chat --trace-file --trace-remote --trace-console

# Use custom file path
probe-chat --trace-file ./debug-traces.jsonl
```

#### What Gets Traced

The tracing system captures detailed information about AI interactions:

- **Performance Metrics**: Response times, request durations, and throughput
- **Token Usage**: Prompt tokens, completion tokens, and total consumption
- **Model Information**: Provider, model name, and configuration
- **Session Data**: Session IDs, iteration counts, and conversation flow
- **Error Tracking**: Failed requests, timeouts, and error details

For more details on tracing, see the [AI Chat documentation](./ai-chat.md#opentelemetry-tracing).

### Chat Examples

```bash
# Start interactive chat in the current directory
probe-chat

# Start interactive chat targeting a specific project path
probe-chat /path/to/my/project

# Use the 'engineer' persona
probe-chat --prompt engineer

# Send a single question and get a JSON response
probe-chat --message "Explain the auth flow in main.go" --json

# Start chat with editing enabled (requires Aider)
probe-chat /path/to/project --allow-edit

# Start chat with tracing enabled
probe-chat --trace-file ./session-traces.jsonl

# Start chat with full observability
probe-chat --trace-file --trace-remote http://localhost:4318/v1/traces --allow-edit
```