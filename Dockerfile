# See https://docs.docker.com/engine/reference/builder/ for details
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install dependencies and git
COPY requirements.txt ./
RUN apt-get update && apt-get install -y git \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy source code and update script
COPY . .
COPY auto_update_and_run.sh ./auto_update_and_run.sh
RUN chmod +x ./auto_update_and_run.sh

# Expose port (if your app runs a server, adjust as needed)
# EXPOSE 8080

# Default command (runs the updater/runner script)
CMD ["./auto_update_and_run.sh"]
