FROM python:3.12-slim

WORKDIR /app/code

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY rag/ ./rag/
COPY llm/ ./llm/
COPY agentic/ ./agentic/
COPY backend/ ./backend/

ENV PYTHONPATH=/app/code

EXPOSE 8080

CMD ["uvicorn", "backend.main:api", "--host", "0.0.0.0", "--port", "8080"]
