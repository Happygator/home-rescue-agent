FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime dependencies + the package itself. Source is copied first so the
# hatchling build backend can find the home_rescue and app packages.
COPY pyproject.toml ./
COPY home_rescue ./home_rescue
COPY app ./app
RUN pip install --no-cache-dir .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Bind to 0.0.0.0 and honor the platform's $PORT (Cloud Run sets it, default 8080);
# fall back to 8000 for local runs. `exec` so uvicorn gets SIGTERM directly for clean shutdown.
CMD ["sh", "-c", "exec uvicorn app.fast_api_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
