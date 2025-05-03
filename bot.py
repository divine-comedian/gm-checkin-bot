import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
import json
from dotenv import load_dotenv
from typing import Literal
# --- Telegram imports ---
from telegram import Update, Bot as TelegramBot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

GROUPS_FILE = "groups.json"
AUTHORIZED_USERS_FILE = "authorized_users.json"

def load_authorized_users():
    if os.path.exists(AUTHORIZED_USERS_FILE):
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            data = json.load(f)
            return data.get("users", [])
    return []

def save_authorized_users(users):
    with open(AUTHORIZED_USERS_FILE, "w") as f:
        json.dump({"users": users}, f)

authorized_users = load_authorized_users()

# --- Group Handling: Support Discord and Telegram users as objects ---
def load_groups():
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r") as f:
            data = json.load(f)
            # Ensure both Discord and Telegram lists exist
            for group in ["product_managers", "developers"]:
                if group not in data:
                    data[group] = {"discord": [], "telegram": []}
                else:
                    if "discord" not in data[group]:
                        data[group]["discord"] = []
                    if "telegram" not in data[group]:
                        data[group]["telegram"] = []
            return data
    # Default structure
    return {
        "product_managers": {"discord": [], "telegram": []},
        "developers": {"discord": [], "telegram": []}
    }

def save_groups(groups):
    with open(GROUPS_FILE, "w") as f:
        json.dump(groups, f, indent=2)

# --- Telegram user mapping ---
TELEGRAM_USERS_FILE = "telegram_users.json"
def load_telegram_users():
    if os.path.exists(TELEGRAM_USERS_FILE):
        with open(TELEGRAM_USERS_FILE, "r") as f:
            return json.load(f)
    return {}
def save_telegram_users(users):
    with open(TELEGRAM_USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
telegram_users = load_telegram_users()

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Load groups structure ---
groups = load_groups()

# Persistent check-in messages
CHECKIN_MESSAGES_FILE = "checkin_messages.json"
def load_checkin_messages():
    import json
    if os.path.exists(CHECKIN_MESSAGES_FILE):
        with open(CHECKIN_MESSAGES_FILE, "r") as f:
            return json.load(f)
    return {
        "product_managers": "Hey Product Managers! Please provide your weekly update:",
        "developers": "Hey Developers! Please share your weekly progress:"
    }
def save_checkin_messages():
    import json
    with open(CHECKIN_MESSAGES_FILE, "w") as f:
        json.dump(checkin_messages, f)

checkin_messages = load_checkin_messages()

# Google Sheets setup using env variables
SHEET_NAME = "Weekly Checkins"
SHEET_PM_TAB = "Product Managers"
SHEET_DEV_TAB = "Developers"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- Telegram bot setup ---
telegram_bot = TelegramBot(token=TELEGRAM_BOT_TOKEN)
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# --- Telegram message handler for check-ins ---
async def telegram_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    text = update.message.text
    print(f"[TELEGRAM CHECKIN] Received from {tg_id} (@{user.username}): {text}")
    # No auto-registration here
    # Find group membership (now objects)
    tab = None
    user_obj_pm = next((u for u in groups["product_managers"]["telegram"] if u["id"] == tg_id), None)
    user_obj_dev = next((u for u in groups["developers"]["telegram"] if u["id"] == tg_id), None)
    if user_obj_pm:
        tab = SHEET_PM_TAB
        username = f"telegram:{user.username or tg_id}"
    elif user_obj_dev:
        tab = SHEET_DEV_TAB
        username = f"telegram:{user.username or tg_id}"
    else:
        await context.bot.send_message(chat_id=tg_id, text="You are not in a group.")
        print(f"[TELEGRAM CHECKIN] User {tg_id} not in any group.")
        return
    try:
        sheet = get_gsheet(tab)
        week_str = get_week_str()
        print(f"[TELEGRAM CHECKIN] Recording for {username} in {tab} at {week_str}")
        # Find row for user
        cell = sheet.find(username)
        if not cell:
            print(f"[TELEGRAM CHECKIN] Username {username} not found in sheet {tab}, adding new row.")
            # Find first empty row
            rows = sheet.get_all_values()
            row = len(rows) + 1
            # Insert username in first column
            sheet.update_cell(row, 1, username)
        else:
            row = cell.row
        # Find column for week
        week_cell = sheet.find(week_str)
        if not week_cell:
            print(f"[TELEGRAM CHECKIN] Week {week_str} not found in sheet {tab}, adding new column.")
            # Get all values to determine where to add the new column
            values = sheet.get_all_values()
            header = values[0] if values else []
            col = len(header) + 1
            sheet.update_cell(1, col, week_str)
        else:
            col = week_cell.col
        existing = sheet.cell(row, col).value
        if existing:
            new_value = existing + "\n" + text
        else:
            new_value = text
        sheet.update_cell(row, col, new_value)
        # React to the user's message with the 👌 emoji using set_message_reaction (python-telegram-bot v20+)
        from telegram import ReactionTypeEmoji
        reacted = False
        for emoji in ["👌", "👀"]:
            try:
                await context.bot.set_message_reaction(
                    chat_id=update.effective_message.chat_id,
                    message_id=update.effective_message.message_id,
                    reaction=[ReactionTypeEmoji(emoji)],
                    is_big=False
                )
                reacted = True
                break
            except Exception as e:
                print(f"[TELEGRAM CHECKIN] Failed to react with {emoji}: {e}")
                continue
        if not reacted:
            try:
                await update.message.reply_text("Check-in recorded!")
            except Exception:
                pass
        print(f"[TELEGRAM CHECKIN] Successfully recorded check-in for {username} in {tab}")
    except Exception as e:
        print(f"[TELEGRAM CHECKIN] Failed to record check-in for {username}: {e}")
        try:
            await update.message.reply_text("There was an error recording your check-in. Please contact the admin.")
        except Exception:
            pass

# --- Telegram /register command handler ---
async def telegram_register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    username = user.username
    global telegram_users
    print(f"[TELEGRAM REGISTER] User: {username}, ID: {tg_id}")
    if not username:
        print(f"[TELEGRAM REGISTER] User {tg_id} has no username set.")
        await context.bot.send_message(chat_id=tg_id, text="You must set a Telegram username in your profile to register with the bot.")
        return
    telegram_users[str(tg_id)] = username
    save_telegram_users(telegram_users)
    try:
        print(f"[TELEGRAM REGISTER] Sending confirmation to {tg_id} (@{username})")
        await context.bot.send_message(chat_id=tg_id, text=f"Registered! Username: @{username}, ID: {tg_id}")
    except Exception as e:
        print(f"[TELEGRAM REGISTER] Failed to send confirmation to {tg_id}: {e}")

# Register /register command for Telegram
from telegram.ext import CommandHandler, MessageHandler, filters
telegram_app.add_handler(CommandHandler("register", telegram_register_handler))
# Register message handler for Telegram check-ins (non-command messages)
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_message_handler))

# Helper: Get week string

def get_week_str():
    today = datetime.now()
    return today.strftime("%Y-%m-%d")

# Google Sheets Helper

def get_gsheet(tab_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
        "type": os.getenv("GOOGLE_TYPE"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL"),
        "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN")
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).worksheet(tab_name)
    return sheet

# Slash command: Send check-in to developers

@tree.command(name="developer_checkin", description="Send the developer check-in message to all developers (admin only)")
async def developer_checkin_slash(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    delivery_report = []
    # Discord delivery
    for user_id in groups["developers"]["discord"]:
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await user.send(checkin_messages["developers"])
                delivery_report.append(f"Discord {user_id}: ✅")
            else:
                delivery_report.append(f"Discord {user_id}: ❌")
        except Exception:
            delivery_report.append(f"Discord {user_id}: ❌")
    # Telegram delivery
    for tg_user in groups["developers"]["telegram"]:
        tg_id = tg_user["id"] if isinstance(tg_user, dict) else tg_user
        username = tg_user["username"] if isinstance(tg_user, dict) else None
        try:
            print(f"[TELEGRAM DEV CHECKIN] Sending to {tg_id} (@{username})")
            await telegram_bot.send_message(chat_id=tg_id, text=checkin_messages["developers"])
            delivery_report.append(f"Telegram @{username if username else tg_id}: ✅")
        except Exception as e:
            print(f"[TELEGRAM DEV CHECKIN] Failed to send to {tg_id} (@{username}): {e}")
            delivery_report.append(f"Telegram @{username if username else tg_id}: ❌")
    await interaction.followup.send("Developer check-in sent.\n" + "\n".join(delivery_report), ephemeral=True)


# Slash command: Send check-in to product managers

@tree.command(name="pm_checkin", description="Send the product manager check-in message to all PMs (admin only)")
async def pm_checkin_slash(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    delivery_report = []
    # Discord delivery
    for user_id in groups["product_managers"]["discord"]:
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await user.send(checkin_messages["product_managers"])
                delivery_report.append(f"Discord {user_id}: ✅")
            else:
                delivery_report.append(f"Discord {user_id}: ❌")
        except Exception:
            delivery_report.append(f"Discord {user_id}: ❌")
    # Telegram delivery
    for tg_user in groups["product_managers"]["telegram"]:
        tg_id = tg_user["id"] if isinstance(tg_user, dict) else tg_user
        username = tg_user["username"] if isinstance(tg_user, dict) else None
        try:
            print(f"[TELEGRAM PM CHECKIN] Sending to {tg_id} (@{username})")
            await telegram_bot.send_message(chat_id=tg_id, text=checkin_messages["product_managers"])
            delivery_report.append(f"Telegram @{username if username else tg_id}: ✅")
        except Exception as e:
            print(f"[TELEGRAM PM CHECKIN] Failed to send to {tg_id} (@{username}): {e}")
            delivery_report.append(f"Telegram @{username if username else tg_id}: ❌")
    await interaction.followup.send("Product manager check-in sent.\n" + "\n".join(delivery_report), ephemeral=True)


# Record responses

@bot.event
async def on_message(message):
    # Only handle DMs from users (not the bot itself)
    if message.author == bot.user or not isinstance(message.channel, discord.DMChannel):
        return
    user_id = message.author.id
    week_str = get_week_str()
    # Determine group and readable username
    tab = None
    username = None
    if user_id in groups["product_managers"]["discord"]:
        tab = SHEET_PM_TAB
    elif user_id in groups["developers"]["discord"]:
        tab = SHEET_DEV_TAB
    else:
        return
    # Use username#discriminator for readability, but treat #0 as equivalent to no discriminator
    raw_username = message.author.name
    discriminator = str(getattr(message.author, 'discriminator', ''))
    # If discriminator is '0', treat as no discriminator
    if discriminator == '0' or discriminator == '' or discriminator is None:
        username = raw_username
    else:
        username = f"{raw_username}#{discriminator}"
    print(f"[DISCORD CHECKIN] DM from {username} (id={user_id}) for week '{week_str}': {message.content}")
    try:
        sheet = get_gsheet(tab)
        # Find or add user row
        values = sheet.get_all_values()
        header = values[0] if values else []
        row = None
        for i in range(1, len(values)):
            sheet_name = values[i][0] if values[i] else ""
            # Compare ignoring '#0' discriminator
            sheet_name_trimmed = sheet_name if not sheet_name.endswith('#0') else sheet_name[:-2]
            if sheet_name_trimmed == raw_username or sheet_name == username:
                row = i + 1  # 1-based
                print(f"[DISCORD CHECKIN] Found row {row} for user {sheet_name}")
                break
        if row is None:
            row = len(values) + 1
            sheet.update_cell(row, 1, username)
            print(f"[DISCORD CHECKIN] Added new row {row} for user {username}")
        # Find or add week column
        col = None
        if week_str in header:
            col = header.index(week_str) + 1
            print(f"[DISCORD CHECKIN] Found column {col} for week {week_str}")
        else:
            col = len(header) + 1
            sheet.update_cell(1, col, week_str)
            print(f"[DISCORD CHECKIN] Added new column {col} for week {week_str}")
        # Write message content
        if col == 1 or row == 1:
            await message.channel.send("Internal error: refusing to write message to username column or header row.")
            print(f"[DISCORD CHECKIN] Refused to write to col={col}, row={row}")
            return
        existing = sheet.cell(row, col).value
        if existing:
            new_value = existing + "\n" + message.content
        else:
            new_value = message.content
        sheet.update_cell(row, col, new_value)
        print(f"[DISCORD CHECKIN] Updated cell ({row}, {col}) for {username}")
        await message.add_reaction("✅")
    except gspread.SpreadsheetNotFound:
        await message.channel.send("Sorry, the check-in spreadsheet could not be found. Please contact the admin.")
        print(f"[DISCORD CHECKIN] Spreadsheet not found for {username}")
        return
    except Exception as e:
        await message.channel.send("There was an error recording your check-in. Please contact the admin.")
        print(f"[DISCORD CHECKIN] Error for {username}: {e}")
    await bot.process_commands(message)


# Slash commands (application commands) for group management and check-in customization

def is_authorized(interaction: discord.Interaction) -> bool:
    return (
        interaction.user.guild_permissions.administrator or
        interaction.user.id in authorized_users
    )





from typing import Literal

# --- Slash Command: Set Check-in Message (with dropdown) ---

# --- Slash Command: Add Authorized User ---
@tree.command(name="add_authorized_user", description="Add a user as an authorized command user (admin only)")
@app_commands.describe(user="User to authorize")
async def add_authorized_user_slash(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only admins can add authorized users.", ephemeral=True)
        return
    if user.id in authorized_users:
        await interaction.response.send_message(f"{user.mention} is already authorized.", ephemeral=True)
        return
    authorized_users.append(user.id)
    save_authorized_users(authorized_users)
    await interaction.response.send_message(f"{user.mention} added as an authorized user.", ephemeral=True)

# --- Slash Command: Remove Authorized User ---
@tree.command(name="remove_authorized_user", description="Remove a user from authorized command users (admin only)")
@app_commands.describe(user="User to de-authorize")
async def remove_authorized_user_slash(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only admins can remove authorized users.", ephemeral=True)
        return
    if user.id not in authorized_users:
        await interaction.response.send_message(f"{user.mention} is not an authorized user.", ephemeral=True)
        return
    authorized_users.remove(user.id)
    save_authorized_users(authorized_users)
    await interaction.response.send_message(f"{user.mention} removed from authorized users.", ephemeral=True)

# --- Slash Command: List Authorized Users ---
@tree.command(name="list_authorized_users", description="List all authorized command users (admin only)")
async def list_authorized_users_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only admins can view authorized users.", ephemeral=True)
        return
    if not authorized_users:
        await interaction.response.send_message("No authorized users set.", ephemeral=True)
        return
    mentions = []
    for uid in authorized_users:
        user = await bot.fetch_user(uid)
        if user:
            mentions.append(user.mention)
        else:
            mentions.append(f"<@{uid}>")
    await interaction.response.send_message("Authorized users: " + ", ".join(mentions), ephemeral=True)

@tree.command(name="set_checkin_message", description="Set the check-in message for a group (admin only)")
@app_commands.describe(group="Which group to set the check-in message for", message="Check-in message text")
async def set_checkin_message_slash(
    interaction: discord.Interaction,
    group: Literal["Product Manager", "Developer"],
    message: str
):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    group_map = {"Product Manager": "product_managers", "Developer": "developers"}
    group_key = group_map.get(group)
    if group_key is None:
        await interaction.response.send_message("Invalid group name.", ephemeral=True)
        return
    checkin_messages[group_key] = message
    save_checkin_messages()
    await interaction.response.send_message(f"Check-in message for {group} updated.", ephemeral=True)
    # Only one response per interaction

# --- Slash Command: Add Discord/Telegram User to Group ---
@tree.command(name="add_to_group", description="Add a user to a group (admin only)")
@app_commands.describe(group="Group name: product_managers or developers", user_type="discord or telegram", user="Discord or Telegram username to add (for Telegram, use @username)")
async def add_to_group_slash(interaction: discord.Interaction, group: Literal["product_managers", "developers"], user_type: Literal["discord", "telegram"], user: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    if user_type == "discord":
        try:
            # Support Discord mentions (e.g. <@123456789>)
            found_id = None
            log_lines = [f"[DISCORD ADD] Raw user argument: '{user}'"]
            if user.startswith('<@') and user.endswith('>'):
                # Extract user ID from mention
                mention_id = user.strip('<@!>')
                log_lines.append(f"[DISCORD ADD] Detected mention, extracted ID: {mention_id}")
                try:
                    found_id = int(mention_id)
                except Exception as e:
                    log_lines.append(f"[DISCORD ADD] Could not parse mention ID: {e}")
            if not found_id:
                username = user.lstrip("@")
                log_lines.append(f"[DISCORD ADD] Searching for Discord user '{username}' in guild '{interaction.guild.name}' ({interaction.guild.id})")
                # Try exact username and display_name
                for member in interaction.guild.members:
                    log_lines.append(f"[DISCORD ADD] Checking member: {member} (name={member.name}, display_name={member.display_name}, discriminator={getattr(member, 'discriminator', None)})")
                    if member.name == username or member.display_name == username or f"{member.name}#{getattr(member, 'discriminator', '')}" == username:
                        found_id = member.id
                        log_lines.append(f"[DISCORD ADD] Found user: {member} (id={found_id})")
                        break
                # If not found, try to fetch from API
                if not found_id:
                    log_lines.append(f"[DISCORD ADD] User not found in cache. Trying to fetch from API...")
                    # Try to fetch by username#discriminator if provided
                    if '#' in username:
                        uname, discrim = username.split('#', 1)
                        for member in await interaction.guild.query_members(query=uname, limit=100):
                            if member.name == uname and str(getattr(member, 'discriminator', '')) == discrim:
                                found_id = member.id
                                log_lines.append(f"[DISCORD ADD] Found by API: {member} (id={found_id})")
                                break
            for line in log_lines:
                print(line)
            if not found_id:
                await interaction.response.send_message(f"Discord user '{user}' not found in this server.", ephemeral=True)
                return
            already = found_id in groups[group]["discord"]
            if not already:
                groups[group]["discord"].append(found_id)
                save_groups(groups)
                await interaction.response.send_message(f"Added Discord user to {group}.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Discord user is already in {group}.", ephemeral=True)
        except Exception as e:
            print(f"[DISCORD ADD] Exception: {e}")
            await interaction.response.send_message(f"Error adding Discord user: {e}", ephemeral=True)
    elif user_type == "telegram":
        username = user.lstrip("@")
        found_id = None
        for u in telegram_users:
            if telegram_users[u] == username:
                found_id = int(u)
                break
        if not found_id:
            await interaction.response.send_message(f"Telegram user @{username} not found. They must register first.", ephemeral=True)
            return
        already = any(u["id"] == found_id for u in groups[group]["telegram"])
        if not already:
            groups[group]["telegram"].append({"id": found_id, "username": username})
            save_groups(groups)
            await interaction.response.send_message(f"Added Telegram user @{username} to {group}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Telegram user @{username} is already in {group}.", ephemeral=True)
    else:
        await interaction.response.send_message("Unknown user_type. Use 'discord' or 'telegram'.", ephemeral=True)


# --- Slash Command: Remove Discord/Telegram User from Group ---
@tree.command(name="remove_from_group", description="Remove a user from a group (admin only)")
@app_commands.describe(group="Group name: product_managers or developers", user_type="discord or telegram", user="Discord or Telegram username to remove (for Telegram, use @username)")
async def remove_from_group_slash(interaction: discord.Interaction, group: Literal["product_managers", "developers"], user_type: Literal["discord", "telegram"], user: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    if user_type == "discord":
        found_id = None
        log_lines = [f"[DISCORD REMOVE] Raw user argument: '{user}'"]
        if user.startswith('<@') and user.endswith('>'):
            mention_id = user.strip('<@!>')
            log_lines.append(f"[DISCORD REMOVE] Detected mention, extracted ID: {mention_id}")
            try:
                found_id = int(mention_id)
            except Exception as e:
                log_lines.append(f"[DISCORD REMOVE] Could not parse mention ID: {e}")
        if not found_id:
            username = user.lstrip("@")
            log_lines.append(f"[DISCORD REMOVE] Searching for Discord user '{username}' in guild '{interaction.guild.name}' ({interaction.guild.id})")
            for member in interaction.guild.members:
                log_lines.append(f"[DISCORD REMOVE] Checking member: {member} (name={member.name}, display_name={member.display_name}, discriminator={getattr(member, 'discriminator', None)})")
                if member.name == username or member.display_name == username or f"{member.name}#{getattr(member, 'discriminator', '')}" == username:
                    found_id = member.id
                    log_lines.append(f"[DISCORD REMOVE] Found user: {member} (id={found_id})")
                    break
            # If not found, try to fetch by username#discriminator
            if not found_id and '#' in username:
                uname, discrim = username.split('#', 1)
                for member in await interaction.guild.query_members(query=uname, limit=100):
                    if member.name == uname and str(getattr(member, 'discriminator', '')) == discrim:
                        found_id = member.id
                        log_lines.append(f"[DISCORD REMOVE] Found by API: {member} (id={found_id})")
                        break
        for line in log_lines:
            print(line)
        if not found_id:
            await interaction.response.send_message(f"Discord user '{user}' not found in this server.", ephemeral=True)
            return
        if found_id in groups[group]["discord"]:
            groups[group]["discord"].remove(found_id)
            save_groups(groups)
            await interaction.response.send_message(f"Removed Discord user from {group}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Discord user is not in {group}.", ephemeral=True)
    elif user_type == "telegram":
        username = user.lstrip("@")
        found_id = None
        for u in telegram_users:
            if telegram_users[u] == username:
                found_id = int(u)
                break
        if not found_id:
            await interaction.response.send_message(f"Telegram user @{username} not found.", ephemeral=True)
            return
        orig_len = len(groups[group]["telegram"])
        groups[group]["telegram"] = [u for u in groups[group]["telegram"] if u["id"] != found_id]
        if len(groups[group]["telegram"]) < orig_len:
            save_groups(groups)
            await interaction.response.send_message(f"Removed Telegram user @{username} from {group}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Telegram user @{username} is not in {group}.", ephemeral=True)
    else:
        await interaction.response.send_message("Unknown user_type. Use 'discord' or 'telegram'.", ephemeral=True)


# --- Slash Command: List Group ---
@tree.command(name="list_group", description="List all users in a group (admin only)")
@app_commands.describe(group="Group name: product_managers or developers")
async def list_group_slash(interaction: discord.Interaction, group: Literal["product_managers", "developers"]):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    out = []
    # Discord usernames
    discord_usernames = []
    for uid in groups[group]["discord"]:
        try:
            user = await bot.fetch_user(uid)
            if user and user.name:
                discord_usernames.append(f"@{user.name}")
            else:
                discord_usernames.append("(unknown)")
        except Exception:
            discord_usernames.append("(unknown)")
    out.append("discord: " + (", ".join(discord_usernames) if discord_usernames else "None"))
    # Telegram usernames
    telegram_usernames = [f"@{u['username']}" for u in groups[group]["telegram"] if u.get('username')]
    out.append("telegram: " + (", ".join(telegram_usernames) if telegram_usernames else "None"))
    await interaction.response.send_message(f"{group} group users:\n" + "\n".join(out), ephemeral=True)


# Update the on_ready event
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        # Try global sync first
        await tree.sync()
        print("Synced commands globally.")
        
        # Then sync to your specific guild if needed
        guild = discord.Object(id=GUILD_ID)
        synced = await tree.sync(guild=guild)
        print(f"Synced {len(synced)} slash commands to guild {GUILD_ID}.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

if __name__ == "__main__":
    import asyncio
    async def main():
        # Start Discord bot as a task
        discord_task = asyncio.create_task(bot.start(DISCORD_BOT_TOKEN))
        # Start Telegram bot using async API (no run_polling)
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        try:
            await discord_task  # Run Discord bot until it exits
        finally:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
    asyncio.run(main())
