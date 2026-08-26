"""AGENT-1.2..1.6: the agent's tools. Each is a plain, independently testable
function — the graph nodes in agentic/graph/nodes.py call these, and
mcp/fincompliance_mcp/tool_adapters.py exposes the same functions over MCP,
so there is exactly one implementation of each tool, not one per caller.
"""
