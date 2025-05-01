import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
import json

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

def load_groups():
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r") as f:
            data = json.load(f)
            return data.get("product_managers", []), data.get("developers", [])
    return [], []

def save_groups():
    with open(GROUPS_FILE, "w") as f:
        json.dump({
            "product_managers": product_managers,
            "developers": developers
        }, f)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

# Manual lists for group members
product_managers, developers = load_groups()  # Discord user IDs

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
    # Defer so we can send a followup after DMing users
    await interaction.response.defer(ephemeral=True)
    for user_id in developers:
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await user.send(checkin_messages["developers"])
        except Exception:
            pass
    await interaction.followup.send("Developer check-in sent.", ephemeral=True)

# Slash command: Send check-in to product managers

@tree.command(name="pm_checkin", description="Send the product manager check-in message to all PMs (admin only)")
async def pm_checkin_slash(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    # Defer so we can send a followup after DMing users
    await interaction.response.defer(ephemeral=True)
    for user_id in product_managers:
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await user.send(checkin_messages["product_managers"])
        except Exception:
            pass
    await interaction.followup.send("Product manager check-in sent.", ephemeral=True)

# Record responses

@bot.event
async def on_message(message):
    if message.author == bot.user or not isinstance(message.channel, discord.DMChannel):
        return
    user_id = message.author.id
    week_str = get_week_str()
    # Determine group
    if user_id in product_managers:
        tab = SHEET_PM_TAB
    elif user_id in developers:
        tab = SHEET_DEV_TAB
    else:
        return
    # Save to Google Sheets
    try:
        sheet = get_gsheet(tab)
        # Find or add user row by Discord username (not ID)
        username = str(message.author)
        # Ensure username is always in column 1 (A)
        # Ensure header row exists
        header_row = sheet.row_values(1)
        if not header_row or (header_row and (len(header_row) == 0 or header_row[0].strip().lower() != "username")):
            sheet.update_cell(1, 1, "Username")
            header_row = sheet.row_values(1)

        # Always write usernames in col 1, rows 2+
        usernames = sheet.col_values(1)[1:]  # skip header row
        if username in usernames:
            row = usernames.index(username) + 2  # +2: skip header, 1-based
        else:
            row = len(usernames) + 2
            sheet.update_cell(row, 1, username)
            print("New row added for user:", username)

        # Find or add week column (headers start from col 2)
        header_row = sheet.row_values(1)
        if week_str in header_row:
            col = header_row.index(week_str) + 1  # 1-based index
        else:
            col = len(header_row) + 1  # Next empty column
            sheet.update_cell(1, col, week_str)

        # Only write message content in week columns (never username or week header row)
        if col == 1 or row == 1:
            await message.channel.send("Internal error: refusing to write message to username column or header row.")
            return
        existing = sheet.cell(row, col).value
        if existing:
            new_value = existing + "\n" + message.content
        else:
            new_value = message.content
        sheet.update_cell(row, col, new_value)
        # React with a check mark instead of sending a message
        await message.add_reaction("✅")
    except gspread.SpreadsheetNotFound:
        await message.channel.send("Sorry, the check-in spreadsheet could not be found. Please contact the admin.")
        return

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

# --- Slash Command: Add to Group ---
@tree.command(name="add_to_group", description="Add a user to a group (admin only)")
@app_commands.describe(group="Group name: product_managers or developers", user="User to add")
async def add_to_group_slash(interaction: discord.Interaction, group: Literal["product_managers", "developers"], user: discord.User):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    group_list = product_managers if group == "product_managers" else developers
    if user.id not in group_list:
        group_list.append(user.id)
        save_groups()
        await interaction.response.send_message(f"Added {user.mention} to {group}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} is already in {group}.", ephemeral=True)
    # Only one response per interaction

# --- Slash Command: Remove from Group ---
@tree.command(name="remove_from_group", description="Remove a user from a group (admin only)")
@app_commands.describe(group="Group name: product_managers or developers", user="User to remove")
async def remove_from_group_slash(interaction: discord.Interaction, group: Literal["product_managers", "developers"], user: discord.User):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    group_list = product_managers if group == "product_managers" else developers
    if user.id in group_list:
        group_list.remove(user.id)
        save_groups()
        await interaction.response.send_message(f"Removed {user.mention} from {group}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} is not in {group}.", ephemeral=True)
    # Only one response per interaction


# --- Slash Command: List PM Group ---
@tree.command(name="list_pm_group", description="List all users in the Product Managers group (admin only)")
async def list_pm_group_slash(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    if not product_managers:
        await interaction.response.send_message("No users in the Product Managers group.", ephemeral=True)
        return
    mentions = []
    for uid in product_managers:
        user = await bot.fetch_user(uid)
        if user:
            mentions.append(user.mention)
        else:
            mentions.append(f"<@{uid}>")
    await interaction.response.send_message("Product Managers group: " + ", ".join(mentions), ephemeral=True)
    # Only one response per interaction

# --- Slash Command: List Developer Group ---
@tree.command(name="list_developer_group", description="List all users in the Developers group (admin only)")
async def list_developer_group_slash(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
        return
    if not developers:
        await interaction.response.send_message("No users in the Developers group.", ephemeral=True)
        return
    mentions = []
    for uid in developers:
        user = await bot.fetch_user(uid)
        if user:
            mentions.append(user.mention)
        else:
            mentions.append(f"<@{uid}>")
    await interaction.response.send_message("Developers group: " + ", ".join(mentions), ephemeral=True)
    # Only one response per interaction

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
    bot.run(DISCORD_BOT_TOKEN)
