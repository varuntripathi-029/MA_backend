FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# The base image's pre-installed browsers are pinned to its own tag's
# Playwright version — pyproject.toml only floors playwright at >=1.48, so
# whatever version pip actually resolves can drift from that. Re-running
# `playwright install` after the pip install guarantees the browser build on
# disk always matches whatever playwright version is actually installed,
# regardless of base image staleness.
RUN python -m playwright install --with-deps chromium

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Render (and most Docker hosts) inject $PORT and expect the container to
# listen on it; defaults to 8000 for local `docker run` / docker-compose.
EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
