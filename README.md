# GM Check-in Bot

A multi-platform bot for managing weekly check-ins from team members across Discord and Telegram. The bot sends check-in prompts to specified groups, collects responses, and records them in Google Sheets for easy tracking and review.

## Features

- **Multi-Platform Support**: Works with both Discord and Telegram
- **Group Management**: Organize team members into customizable groups (e.g., Product Managers, Developers)
- **Automated Check-ins**: Send scheduled check-in messages to group members
- **Response Collection**: Automatically record responses in Google Sheets
- **Admin Controls**: Slash commands for managing users, groups, and messages
- **Auto-Update**: Self-updating deployment via Docker

## Setup

### Prerequisites

- Python 3.11+
- Discord Bot Token
- Telegram Bot Token
- Google Sheets API credentials

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/gm-checkin-bot.git
   cd gm-checkin-bot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file using the provided example:
   ```bash
   cp .env.example .env
   # Edit the .env file with your actual credentials
   nano .env  # or use your preferred text editor
   ```
   
   The `.env` file should contain the following variables:
   ```
   # Discord Bot Configuration
   DISCORD_BOT_TOKEN=your_discord_bot_token
   DISCORD_GUILD_ID=your_discord_guild_id
   
   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   
   # Google Sheets API credentials
   GOOGLE_TYPE=service_account
   GOOGLE_PROJECT_ID=your_project_id
   GOOGLE_PRIVATE_KEY_ID=your_private_key_id
   GOOGLE_PRIVATE_KEY=your_private_key
   GOOGLE_CLIENT_EMAIL=your_client_email
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
   GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
   GOOGLE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
   GOOGLE_CLIENT_X509_CERT_URL=your_client_cert_url
   GOOGLE_UNIVERSE_DOMAIN=googleapis.com
   ```

4. Set up your Google Sheet with tabs named "Product Managers" and "Developers"

### Running the Bot

```bash
python bot.py
```

### Docker Deployment

#### Using Docker

```bash
# Build the Docker image
docker build -t gm-checkin-bot .

# Run the container with environment variables from .env file
docker run -d --name gm-checkin-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  gm-checkin-bot
```

#### Using Docker Compose (Recommended)

A `docker-compose.yml` file is provided for easier deployment:

```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

#### Persistent Data

The bot stores all its data files in a `data/` directory which is mounted as a volume in the Docker container. This ensures that your configuration and user data persist even if the container is recreated or updated.

Data files that are persisted:
- `groups.json`
- `authorized_users.json`
- `checkin_messages.json`
- `telegram_users.json`

## Usage

### Discord Commands

| Command | Description |
|---------|-------------|
| `/developer_checkin` | Send check-in message to all developers |
| `/pm_checkin` | Send check-in message to all product managers |
| `/add_to_group` | Add a user to a group |
| `/remove_from_group` | Remove a user from a group |
| `/list_group` | List all users in a group |
| `/set_checkin_message` | Set the check-in message for a group |
| `/add_authorized_user` | Add a user as an authorized command user |
| `/remove_authorized_user` | Remove a user from authorized command users |
| `/list_authorized_users` | List all authorized command users |

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/register` | Register with the bot to receive check-ins |

### Check-in Flow

1. Admin sends check-in messages to a group using the appropriate slash command
2. Bot DMs each group member on their preferred platform (Discord or Telegram)
3. Members respond to the DM with their check-in update
4. Bot records responses in Google Sheets with the current date
5. Bot reacts to the message to confirm receipt

## Configuration Files

- `groups.json`: Stores group member information for Discord and Telegram
- `authorized_users.json`: Stores Discord IDs of users authorized to use admin commands
- `checkin_messages.json`: Stores customizable check-in messages for each group
- `telegram_users.json`: Maps Telegram user IDs to usernames

## Known Issues

- Does not automatically add columns to Google Sheets when a new response date is recorded; columns must be added manually
- Admin user is set globally, so the same user is always the admin regardless of which server the bot is in

## Future Enhancements

- Supabase integration for database storage instead of JSON files
- AI integration to summarize check-in responses
- Follow-up reminders for users who don't respond
- Dynamic group creation via Discord commands
- Automatic column creation in Google Sheets


## License

[MIT](LICENSE)
