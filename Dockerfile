# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:debian-slim

WORKDIR /app
COPY . /app
RUN uv sync
CMD ["uv", "run", "python", "main.py"]
