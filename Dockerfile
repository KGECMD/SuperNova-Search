# SuperNova Search Dockerfile - Production Ready
FROM python:3.12-slim

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Force stdout/stderr to be unbuffered
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY atomic_search/ ./atomic_search/
COPY main.py .

# Create directories for session and cache
RUN mkdir -p /tmp/atomic_search && chmod 777 /tmp/atomic_search

# Create non-root user for security
RUN adduser --disabled-password --gecos "" --uid 1000 appuser || true
RUN mkdir -p /home/appuser && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (Railway sets PORT env var)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run with gunicorn
CMD ["gunicorn", "atomic_search.main:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120"]
