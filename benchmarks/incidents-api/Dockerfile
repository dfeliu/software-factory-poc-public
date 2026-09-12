# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.14-alpine3.22@sha256:6b91e66ab2a880ce9ca5a1b91c70f45963ff71ff68268df056336e1a657d5efd
ARG UV_VERSION=0.12.6

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM ${PYTHON_IMAGE} AS base

RUN apk upgrade --no-cache

FROM base AS builder

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

FROM base AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

RUN rm -rf \
    /usr/local/bin/pip \
    /usr/local/bin/pip3 \
    /usr/local/bin/pip3.14 \
    /usr/local/lib/python3.14/site-packages/pip \
    /usr/local/lib/python3.14/site-packages/pip-*.dist-info

RUN addgroup --system --gid 10001 app \
    && adduser --system --disabled-password --no-create-home --uid 10001 --ingroup app --shell /sbin/nologin app

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
