# APEX SIGNAL™ - Production Dockerfile
# Optimized for python:3.11-slim with minimal runtime dependencies
# No compiler toolchains or build-essential installed

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# Set working directory
WORKDIR /app

# Install minimal runtime dependencies only
# No build-essential or compiler toolchains
# Clean up apt cache to keep image small
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces image size
# All packages have pre-built wheels - no compilation needed
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories for logs and data
RUN mkdir -p /app/logs /app/data

# Expose port (Railway will set PORT env var automatically)
EXPOSE ${PORT}

# Health check
# Uses local loopback to check /healthz endpoint
# Interval: 10s, Timeout: 5s, Retries: 3
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8000}/healthz || exit 1

# Run the application using the new main.py entry point
# Railway will provide PORT environment variable
CMD ["python", "main.py"]