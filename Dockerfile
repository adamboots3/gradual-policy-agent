FROM python:3.12.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
RUN uv sync --locked --no-dev --all-extras
COPY corpus.lock.json ./
COPY evals ./evals
RUN useradd --create-home --uid 10001 appuser && mkdir /app/data && chown appuser /app/data
USER appuser
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "policy_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
