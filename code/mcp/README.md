# MCP Server

Exposes the compliance assistant's tools over the [Model Context
Protocol](https://modelcontextprotocol.io) so any MCP client (Claude Desktop, another
agent, a test harness) can call them directly — the same functions the LangGraph agent
(`agentic/graph/`) and the backend API use internally.

| MCP tool | Wraps | Requirement |
|---|---|---|
| `search_regulations` | `agentic/tools/search_regulations.py` | AGENT-1.2 |
| `answer_compliance_question` | `agentic/qa.py` (FR-1 fast path) | FR-1 |
| `get_transaction_details` | `agentic/tools/get_transaction_details.py` | AGENT-1.3 |
| `screen_transaction` | `agentic/graph/build_graph.py::run_screening` | AGENT-1, FR-2 |
| `screen_seeded_transaction` | lookup + `run_screening` in one call | demo convenience |

## Why the package is `fincompliance_mcp`, not `mcp`

This directory is named `mcp/` for repo organization, but the importable Python package
inside it is `fincompliance_mcp` (`mcp/fincompliance_mcp/`), and the directory itself has
**no** `__init__.py`. If it did, `code/mcp` would become a regular package literally named
`mcp`, which would shadow the real `mcp` PyPI SDK this server is built on the moment
`code/` is on `sys.path` — a subtle, hard-to-diagnose bug. Keeping `code/mcp/` as a plain
folder avoids it entirely; see `agentic-development` note in the root README for the same
pattern applied to other packages.

This is also why the process needs **two** path entries, not one:
`PYTHONPATH=<repo>/code:<repo>/code/mcp` — the first resolves `shared`/`rag`/`llm`/`agentic`,
the second resolves `fincompliance_mcp` itself. `docker-compose.yml` / `Dockerfile` set this
for you; for local runs see below.

## Run it locally (stdio — for Claude Desktop / a local MCP client)

From the `code/` directory, with the venv active:

```bash
PYTHONPATH=.:./mcp MCP_TRANSPORT=stdio python -m fincompliance_mcp.server
```

Point a client's MCP config at that command, e.g. Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "finserv-compliance-assistant": {
      "command": "python",
      "args": ["-m", "fincompliance_mcp.server"],
      "cwd": "<repo>/code",
      "env": { "PYTHONPATH": ".:./mcp", "MCP_TRANSPORT": "stdio" }
    }
  }
}
```

## Run it via docker-compose (SSE, alongside the rest of the stack)

```bash
docker compose up mcp-server
```

Serves over SSE at `http://localhost:8090`.

## Try it without any MCP client

```bash
PYTHONPATH=.:./mcp python -c "
from fincompliance_mcp.server import screen_seeded_transaction
from agentic.tools.get_transaction_details import seed_transactions
from shared.db.base import init_db
init_db(); seed_transactions()
import json; print(json.dumps(screen_seeded_transaction('TXN-1001'), indent=2, default=str))
"
```
