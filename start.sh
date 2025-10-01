#!/bin/bash

# Set variables
DATA_DIR=/app/data
LOGS_DIR=/app/logs

# Ensure directories exist
mkdir -p ${DATA_DIR} ${LOGS_DIR}

# Initialize data files if they don't exist
for file in groups.json authorized_users.json checkin_messages.json telegram_users.json; do
  if [ -f "/app/${file}" ] && [ ! -f "${DATA_DIR}/${file}" ]; then
    echo "Initializing ${file} in data directory..."
    cp "/app/${file}" "${DATA_DIR}/${file}"
  fi
done

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

# Set Telegram to continue on error
export TELEGRAM_MAX_RETRIES=3
export TELEGRAM_RETRY_DELAY=5
export TELEGRAM_CONTINUE_ON_ERROR=true

# Start the bot
echo "Starting bot.py..."
python bot.py > ${LOGS_DIR}/bot.log 2>&1 &
BOT_PID=$!

# Check if bot started successfully
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

# Monitor the bot and restart if it crashes
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