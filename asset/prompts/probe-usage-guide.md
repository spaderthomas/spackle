## Available Tools
The Probe MCP server provides the following tools. For all tools, you may omit "path" and "maxTokens", since they are defaulted by our tooling. 

### search_code
Search code in a specified directory using Elasticsearch-like query syntax with session-based caching.

```json
{
  "path": "/path/to/your/project",
  "query": "authentication flow",
  "maxTokens": 20000
}
```

The search tool supports Elasticsearch-like query syntax with the following features:
- Basic term searching: "config" or "search"
- Field-specific searching: "field:value" (e.g., "function:parse")
- Required terms with + prefix: "+required"
- Excluded terms with - prefix: "-excluded"
- Logical operators: "term1 AND term2", "term1 OR term2"
- Grouping with parentheses: "(term1 OR term2) AND term3"

### query_code
Find specific code structures (functions, classes, etc.) using tree-sitter patterns.

```json
{
  "path": "/path/to/your/project",
  "pattern": "fn $NAME($$$PARAMS) $$$BODY",
  "language": "rust"
}
```

Pattern syntax:
- `$NAME`: Matches an identifier (e.g., function name)
- `$$$PARAMS`: Matches parameter lists
- `$$$BODY`: Matches function bodies
- `$$$FIELDS`: Matches struct/class fields
- `$$$METHODS`: Matches class methods

### extract_code
Extract code blocks from files based on file paths and optional line numbers.

```json
{
  "path": "/path/to/your/project",
  "files": ["/path/to/your/project/src/main.rs:42"],
  "prompt": "engineer",
  "instructions": "Explain this function"
}
```

The extract_code tool supports the following parameters:
- `path`: The base directory to search in
- `files`: Array of file paths to extract from (can include line numbers with colon, e.g., "file.rs:42")
- `prompt`: Optional system prompt template for LLM models ("engineer", "architect", or path to file)
- `instructions`: Optional user instructions for LLM models
- `contextLines`: Number of context lines to include (default: 0)
- `format`: Output format (default: "json")

## Best Practices
1. **Be Specific**: More specific queries yield better results
2. **Mention File Types**: If you're looking for code in specific file types, mention them
3. **Mention Directories**: If you know which directory contains the code, include it in your query
4. **Use Multiple Queries**: If you don't find what you're looking for, try reformulating your query
5. **Combine with Other Tools**: Use Probe alongside other tools for a more comprehensive understanding of your codebase
6. **Use Session IDs**: For related searches, use the same session ID to avoid seeing duplicate code blocks