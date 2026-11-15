FROM python:3.14-slim

# git is required to clone repositories
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Run as a non-root user, since we handle untrusted repositories
RUN useradd --create-home appuser && mkdir -p /app/workspace && chown appuser /app/workspace
USER appuser

ENV APP_ENV=production
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
