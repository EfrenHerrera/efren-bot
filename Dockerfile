FROM python:3.14.6-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Código y migraciones empaquetados, sin bind mounts.
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --no-editable \
    && useradd --system --uid 10001 --create-home efrenbot

USER efrenbot
EXPOSE 8000
CMD ["uvicorn", "efren_bot.api:app", "--host", "0.0.0.0", "--port", "8000"]
