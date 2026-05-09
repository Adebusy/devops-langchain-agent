# Stage 1: pull the UV binaries
FROM ghcr.io/astral-sh/uv:latest AS uv

# Stage 2: app image
FROM python:3.12-slim-bookworm AS app

# Copy uv & uvx
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=uv /uvx /usr/local/bin/uvx

WORKDIR /app

# Copy project metadata
COPY pyproject.toml ./
COPY uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy app source
COPY server.py .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

CMD ["uv", "run", "server.py"]
