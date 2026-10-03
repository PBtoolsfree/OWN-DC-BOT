# Multi-stage build: Frontend + Python Backend
FROM node:20-slim AS frontend-builder
WORKDIR /app/web

COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# Python Runtime
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/
COPY alembic.ini pyproject.toml ./
COPY .env.example ./

# Copy built frontend assets
COPY --from=frontend-builder /app/web/dist ./web/dist

# Expose Dashboard Port
EXPOSE 8000

CMD ["python", "-m", "app.main"]
