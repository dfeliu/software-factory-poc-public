# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14
ARG UV_VERSION=0.12.6

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim-trixie AS builder

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project

COPY application ./application
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen

FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/application /app/application
COPY --from=builder --chown=app:app /app/migrations /app/migrations
COPY --from=builder --chown=app:app /app/alembic.ini /app/alembic.ini

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=2).read()"

CMD ["uvicorn", "application.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM builder AS test

ENV PATH="/app/.venv/bin:${PATH}" \
    UV_NO_DEV=0

COPY tests ./tests
RUN uv sync --frozen --all-groups

CMD ["pytest"]
