import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import gspread
from db import supabase, GROUPS_TABLE, get_or_create_user, add_user_to_group, set_checkin_message, add_checkin

# Load environment variables
load_dotenv()

# Google Sheets setup
gs_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
SHEET_NAME = "Weekly Checkins"
SHEET_PM_TAB = "Product Managers"
SHEET_DEV_TAB = "Developers"

# Legacy files
AUTHORIZED_USERS_FILE = "authorized_users.json"
GROUPS_FILE = "groups.json"
CHECKIN_MESSAGES_FILE = "checkin_messages.json"
TELEGRAM_USERS_FILE = "telegram_users.json"


def migrate_users_and_groups():
    """Migrate data from JSON files to Supabase (updated for new schema)"""
    # Migrate authorized users (Discord only)
    if Path(AUTHORIZED_USERS_FILE).exists():
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            auth_users = json.load(f).get("users", [])
            for user_id in auth_users:
                get_or_create_user(discord_id=str(user_id))
    
    # Migrate groups and memberships
    if Path(GROUPS_FILE).exists():
        with open(GROUPS_FILE, "r") as f:
            groups_data = json.load(f)
            for group_name, group_info in groups_data.items():
                # Ensure group exists
                group_result = supabase.table(GROUPS_TABLE).select("id").eq("name", group_name).execute()
                if not group_result.data:
                    group_row = supabase.table(GROUPS_TABLE).insert({"name": group_name}).execute().data[0]
                    group_id = group_row['id']
                else:
                    group_id = group_result.data[0]['id']
                # Collect all user IDs for this group
                user_ids = []
                # Add Discord users
                for discord_user in group_info.get("discord", []):
                    user_row = get_or_create_user(discord_id=str(discord_user))
                    if user_row:
                        user_ids.append(user_row['id'])
                # Add Telegram users
                for tg_user in group_info.get("telegram", []):
                    if isinstance(tg_user, dict):
                        tg_id = tg_user.get("id")
                        username = tg_user.get("username")
                    else:
                        tg_id = tg_user
                        username = None
                    user_row = get_or_create_user(telegram_id=str(tg_id), telegram_username=username)
                    if user_row:
                        user_ids.append(user_row['id'])
                # Update group with user_ids array
                supabase.table(GROUPS_TABLE).update({"user_ids": user_ids}).eq("id", group_id).execute()
    
    # Migrate check-in messages
    if Path(CHECKIN_MESSAGES_FILE).exists():
        with open(CHECKIN_MESSAGES_FILE, "r") as f:
            messages = json.load(f)
            for group_name, message in messages.items():
                set_checkin_message(group_name, message)
    
    print("Migration completed successfully (new schema)")


def migrate_checkins_from_gsheets():
    # Build credentials dict from environment variables
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
        "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN"),
    }
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open(SHEET_NAME)
    for tab, group_name in [(SHEET_PM_TAB, "product_managers"), (SHEET_DEV_TAB, "developers")]:
        worksheet = sh.worksheet(tab)
        header = worksheet.row_values(1)
        week_cols = {col: idx+1 for idx, col in enumerate(header) if col.lower().startswith('202') or col.lower().startswith('week')}
        all_rows = worksheet.get_all_values()
        for row_idx, row in enumerate(all_rows[1:], start=2):
            username = row[0].strip()
            if not username:
                continue
            # Try to find user in Supabase (by username)
            user_row = None
            if '#' in username:
                # Discord
                discord_username = username
                user_row = get_or_create_user(discordName=discord_username)
            elif username.startswith('telegram:'):
                telegram_username = username.replace('telegram:', '').strip()
                user_row = get_or_create_user(telegram_username=telegram_username)
            else:
                # Try both
                user_row = get_or_create_user(discord_username=username)
                if not user_row:
                    user_row = get_or_create_user(telegram_username=username)
            if not user_row:
                print(f"[MIGRATE] Could not find/create user for username: {username}")
                continue
            for week, col in week_cols.items():
                message = row[col-1] if col-1 < len(row) else ''
                if message:
                    week_str = week
                    # Look up group_id from Supabase
                    group_result = supabase.table(GROUPS_TABLE).select("id").eq("name", group_name).execute()
                    if not group_result.data:
                        print(f"[MIGRATE] Group {group_name} not found for user {username}, skipping check-in.")
                        continue
                    group_id = group_result.data[0]['id']
                    checkin_result = add_checkin(
                        user_id=user_row['id'],
                        group_id=group_id,
                        content=message,
                        week_str=week_str
                    )
                    print(f"[MIGRATE] Added check-in for {username} in {group_name}, week {week_str}.")


def main():
    print("=== Migrating users, groups, and check-in messages... ===")
    migrate_users_and_groups()
    print("=== Migrating check-ins from Google Sheets... ===")
    migrate_checkins_from_gsheets()
    print("=== Migration complete! ===")

if __name__ == "__main__":
    main()
