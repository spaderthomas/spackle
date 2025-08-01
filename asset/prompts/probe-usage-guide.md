## Probe MCP Tools

The Probe MCP server provides three simple tools for searching and extracting code from your project. All tools automatically:
- Return results in markdown format
- Limit results to 4 items (for search/query)
- Limit tokens to 750 (for search)
- Work from your project root by default

### search_code

Search code using Elasticsearch-like query syntax.

**Parameters:**
- `query` (required): The search query
- `subpath` (optional): Relative path within project to search in
- `session` (optional): Session ID for caching (default: "new")

**Examples:**
```json
{
  "query": "authentication flow"
}

{
  "query": "updateUser",
  "subpath": "src/api"
}

{
  "query": "error AND handling",
  "session": "abc123"
}
```

**Query Syntax:**
- Basic terms: `"config"` or `"search"`
- AND operator: `"error AND handling"`
- OR operator: `"login OR authentication"`
- Grouping: `"(error OR exception) AND handle"`
- Wildcards: `"auth* connect*"`
- Exclusion: `"database NOT sqlite"`

### query_code

Find specific code structures using ast-grep patterns.

**Parameters:**
- `pattern` (required): The ast-grep pattern
- `subpath` (optional): Relative path within project to search in  
- `language` (optional): Programming language (e.g., "rust", "python")

**Examples:**
```json
{
  "pattern": "fn $NAME($$$PARAMS) $$$BODY",
  "language": "rust"
}

{
  "pattern": "def $NAME($$$PARAMS): $$$BODY",
  "subpath": "src",
  "language": "python"
}
```

**Pattern Syntax:**
- `$NAME`: Matches an identifier
- `$$$PARAMS`: Matches parameter lists
- `$$$BODY`: Matches function/method bodies
- `$$$FIELDS`: Matches struct/class fields

### extract_code

Extract code blocks from specific files and locations.

**Parameters:**
- `files` (required): List of files to extract from
- `contextLines` (optional): Number of context lines (default: 0)

**Examples:**
```json
{
  "files": ["src/main.rs:42"]
}

{
  "files": ["src/auth.js:15", "src/api.js:27"],
  "contextLines": 5
}

{
  "files": ["src/main.rs#handle_extract"]
}
```

**File Formats:**
- Line number: `"file.rs:42"`
- Line range: `"file.rs:10-20"`
- Symbol name: `"file.rs#function_name"`

## Usage Notes

1. **Subpath Validation**: The `subpath` parameter must be a valid directory within your project root. It cannot use `..` to go outside the project.

2. **Session Caching**: Use the same session ID across related searches to avoid seeing duplicate code blocks.

3. **Language Detection**: For `query_code`, if language is not specified, it will be inferred from file extensions.

4. **File Paths**: For `extract_code`, file paths should be relative to the project root.