# GM Check-in Bot Dockerfile
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Create a non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Install dependencies and git
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates procps \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create data and log directories and set permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R botuser:botuser /app

# Copy source code and update script
COPY --chown=botuser:botuser . .
COPY --chown=botuser:botuser auto_update_and_run.sh ./auto_update_and_run.sh
RUN chmod +x ./auto_update_and_run.sh

# Switch to non-root user
USER botuser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ps aux | grep -q "[p]ython bot.py" || exit 1

# Default command (runs the updater/runner script)
CMD ["./auto_update_and_run.sh"]
