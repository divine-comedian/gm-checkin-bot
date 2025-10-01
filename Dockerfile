# GM Check-in Bot Dockerfile
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies
COPY requirements.txt ./
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates procps && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /app/data /app/logs

# Copy source code
COPY . .

# Make the startup script executable
RUN chmod +x /app/start.sh

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ps aux | grep -q "[p]ython bot.py" || exit 1

# Default command
CMD ["/app/start.sh"]