#!/bin/bash

REPO_DIR=/app
DATA_DIR=${REPO_DIR}/data
LOGS_DIR=${REPO_DIR}/logs
BRANCH=main

# Ensure data directory exists
mkdir -p ${DATA_DIR} ${LOGS_DIR}

# Setup data files in the persistent data directory
for file in groups.json authorized_users.json checkin_messages.json telegram_users.json; do
  # If the file exists in the repo but not in data dir, copy it
  if [ -f "${REPO_DIR}/${file}" ] && [ ! -f "${DATA_DIR}/${file}" ]; then
    echo "Initializing ${file} in data directory..."
    cp "${REPO_DIR}/${file}" "${DATA_DIR}/${file}"
  fi
  
  # Create symbolic links from data dir to repo files
  # This ensures the bot reads from the repo files directly
  if [ -f "${REPO_DIR}/${file}" ]; then
    echo "Using ${file} from repository..."
    # Make sure data directory has a backup copy
    cp "${REPO_DIR}/${file}" "${DATA_DIR}/${file}.backup"
  fi
done

cd $REPO_DIR

# Function to handle exit
cleanup() {
  echo "Shutting down bot..."
  if [ ! -z "$BOT_PID" ]; then
    kill $BOT_PID 2>/dev/null || true
  fi
  exit 0
}

# Register the cleanup function for these signals
trap cleanup SIGTERM SIGINT SIGHUP

# Start the bot initially
echo "Starting bot.py..."
export TELEGRAM_MAX_RETRIES=3
export TELEGRAM_RETRY_DELAY=5
export TELEGRAM_CONTINUE_ON_ERROR=true

# Use the logs directory for output
python bot.py > ${LOGS_DIR}/bot.log 2>&1 &
BOT_PID=$!

sleep 5
if ! ps -p $BOT_PID > /dev/null; then
  echo "Failed to start bot.py, checking logs..."
  tail -n 20 ${LOGS_DIR}/bot.log
  echo "Attempting to start without Telegram..."
  export DISABLE_TELEGRAM=true
  python bot.py > ${LOGS_DIR}/bot.log 2>&1 &
  BOT_PID=$!
  
  sleep 3
  if ! ps -p $BOT_PID > /dev/null; then
    echo "Failed to start bot even with Telegram disabled. Exiting."
    tail -n 20 ${LOGS_DIR}/bot.log
    exit 1
  fi
fi

echo "Bot started with PID: $BOT_PID"

while true; do
  # Check if the bot process is still running
  if ! ps -p $BOT_PID > /dev/null; then
    echo "Bot process died, restarting..."
    python bot.py > ${LOGS_DIR}/bot.log 2>&1 &
    BOT_PID=$!
    echo "Bot restarted with PID: $BOT_PID"
  fi
  
  # Sleep for a minute before checking again
  sleep 60
done
