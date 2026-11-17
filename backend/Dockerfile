FROM ghcr.io/astral-sh/uv:0.13.9 AS uv

FROM python:3.12.16-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
ARG DEV=false
RUN if [ "$DEV" = "true" ]; then uv sync --frozen; else uv sync --frozen --no-dev; fi

FROM python:3.12.16-slim-trixie AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 baithak
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --chown=baithak:baithak . .
USER baithak
EXPOSE 8000
CMD ["daphne", "--bind", "0.0.0.0", "--port", "8000", "config.asgi:application"]
