"""Shared domain models, enums, config, and logging used by every service.

Kept dependency-light (pydantic/pyyaml/structlog only) since rag/, llm/,
agentic/, backend/, mcp/, and eval/ all import from here.
"""
