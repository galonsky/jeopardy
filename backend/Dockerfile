FROM node:24.15-slim AS frontend
WORKDIR /app/frontend
RUN corepack enable && corepack prepare pnpm@11.0.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.14-slim-trixie
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid 10001 --home-dir /app app
COPY pyproject.toml uv.lock ./
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/backend
RUN DJANGO_SETTINGS_MODULE=config.settings.local uv run --no-sync python backend/manage.py collectstatic --noinput
COPY backend/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R app:app /app
USER app
WORKDIR /app/backend
ENTRYPOINT ["/entrypoint.sh"]
CMD ["server"]

