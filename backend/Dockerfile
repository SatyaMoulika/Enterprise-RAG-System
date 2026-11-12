FROM python:3.12-slim
WORKDIR /app
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir uv==0.13.5
COPY pyproject.toml uv.lock ./
ARG RAG_INSTALL_RERANKING=false
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    if [ "$RAG_INSTALL_RERANKING" = "true" ]; then uv sync --locked --no-dev --extra reranking; \
    elif [ "$RAG_INSTALL_RERANKING" = "false" ]; then uv sync --locked --no-dev; else exit 1; fi
COPY . .
RUN groupadd --gid 10001 rag && useradd --uid 10001 --gid rag --create-home rag \
    && mkdir -p /app/uploads /app/model-cache && chown -R rag:rag /app
ENV HF_HOME=/app/model-cache
USER rag
EXPOSE 8000
CMD ["sh", "-c", ".venv/bin/alembic upgrade head && exec .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000"]
