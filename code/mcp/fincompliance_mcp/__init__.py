"""MCP server exposing the compliance assistant's tools (search, transaction
lookup, full screening) over the Model Context Protocol, so any MCP-capable
client — Claude Desktop, another agent — can drive the same functions the
backend API and the LangGraph agent use internally.

Note on package layout: this package is named `fincompliance_mcp`, not
`mcp`, even though it lives in a directory called `mcp/` (see the parent
`mcp/README.md`). Naming the importable package itself `mcp` would shadow
the real `mcp` SDK dependency this server is built on.
"""
