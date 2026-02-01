# Multi-stage Dockerfile for Django Max Bots

# Stage 1: Base image with dependencies
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage 2: Production image
FROM base as production

# Copy project files
COPY max_project /app/max_project/

# Create logs directory
RUN mkdir -p /app/logs

# Collect static files (will be run in entrypoint)
# RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Default command (can be overridden in docker-compose.yml)
CMD ["gunicorn", "max_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]