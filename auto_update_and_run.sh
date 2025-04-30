#!/bin/bash

REPO_DIR=/app
BRANCH=main

cd $REPO_DIR

# Start the bot initially
echo "Starting bot.py..."
python bot.py &
BOT_PID=$!

while true; do
  git fetch origin $BRANCH
  LOCAL=$(git rev-parse $BRANCH)
  REMOTE=$(git rev-parse origin/$BRANCH)
  if [ "$LOCAL" != "$REMOTE" ]; then
    echo "New changes detected. Pulling and restarting bot..."
    git pull origin $BRANCH
    kill $BOT_PID
    python bot.py &
    BOT_PID=$!
  fi
  sleep 60
done
