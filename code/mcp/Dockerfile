FROM python:3.12-slim

WORKDIR /app/code

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY rag/ ./rag/
COPY llm/ ./llm/
COPY agentic/ ./agentic/
COPY mcp/ ./mcp/

# Both /app/code (for shared/rag/llm/agentic) and /app/code/mcp (for the
# fincompliance_mcp package itself) must be on the path — see mcp/README.md.
ENV PYTHONPATH=/app/code:/app/code/mcp
ENV MCP_TRANSPORT=sse

EXPOSE 8090

CMD ["python", "-m", "fincompliance_mcp.server"]
