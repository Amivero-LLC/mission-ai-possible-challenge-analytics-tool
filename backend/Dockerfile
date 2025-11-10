# Builder for the FastAPI backend. Slim base keeps image size minimal.
FROM python:3.11-slim

# Work inside /app so compose volume mounts line up with local tree.
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    BACKEND_PORT=8000

# Install dependencies separately to leverage Docker layer caching.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Start uvicorn in autoreload mode for local development.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000} --reload"]
