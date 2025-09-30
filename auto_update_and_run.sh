#!/bin/bash

REPO_DIR=/app
DATA_DIR=${REPO_DIR}/data
BRANCH=main

# Ensure data directory exists
mkdir -p ${DATA_DIR}

# Setup data files in the persistent data directory
for file in groups.json authorized_users.json checkin_messages.json telegram_users.json; do
  # If the file exists in the repo but not in data dir, copy it
  if [ -f "${REPO_DIR}/${file}" ] && [ ! -f "${DATA_DIR}/${file}" ]; then
    echo "Initializing ${file} in data directory..."
    cp "${REPO_DIR}/${file}" "${DATA_DIR}/${file}"
  fi
  
  # Create symbolic links from repo to data dir
  if [ -f "${DATA_DIR}/${file}" ]; then
    echo "Linking ${file} from data directory..."
    ln -sf "${DATA_DIR}/${file}" "${REPO_DIR}/${file}"
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
python bot.py &
BOT_PID=$!

# Check if bot started successfully
if [ $? -ne 0 ]; then
  echo "Failed to start bot.py"
  exit 1
fi

echo "Bot started with PID: $BOT_PID"

while true; do
  # Check if the bot process is still running
  if ! ps -p $BOT_PID > /dev/null; then
    echo "Bot process died, restarting..."
    python bot.py &
    BOT_PID=$!
    echo "Bot restarted with PID: $BOT_PID"
  fi
  
  # Check for updates
  if git fetch origin $BRANCH 2>/dev/null; then
    LOCAL=$(git rev-parse $BRANCH 2>/dev/null)
    REMOTE=$(git rev-parse origin/$BRANCH 2>/dev/null)
    if [ "$LOCAL" != "$REMOTE" ]; then
      echo "New changes detected. Pulling and restarting bot..."
      if git pull origin $BRANCH; then
        echo "Successfully pulled updates"
        if [ ! -z "$BOT_PID" ]; then
          kill $BOT_PID
          sleep 2
        fi
        python bot.py &
        BOT_PID=$!
        echo "Bot restarted with PID: $BOT_PID"
      else
        echo "Failed to pull updates"
      fi
    fi
  else
    echo "Failed to fetch from git repository"
  fi
  
  sleep 60
done
