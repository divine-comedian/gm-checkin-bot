from supabase import create_client, Client
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Table names
USERS_TABLE = "users"
CHECKINS_TABLE = "checkins"
GROUPS_TABLE = "groups"
USER_GROUPS_TABLE = "user_groups"

def get_user_by_discord_id(discord_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by their Discord ID"""
    if not discord_id:
        return None
        
    result = supabase.table(USERS_TABLE)\
        .select("*")\
        .eq("discord_id", str(discord_id))\
        .execute()
    
    return result.data[0] if result.data and len(result.data) > 0 else None


def get_user_by_telegram_id(telegram_id: str, by_username: bool = False) -> Optional[Dict[str, Any]]:
    """Get a user by their Telegram ID or username"""
    if not telegram_id:
        return None
        
    query = supabase.table(USERS_TABLE).select("*")
    
    if by_username:
        query = query.eq("telegram_username", str(telegram_id).lstrip('@'))
    else:
        query = query.eq("telegram_id", str(telegram_id))
    
    result = query.execute()
    return result.data[0] if result.data and len(result.data) > 0 else None

def get_or_create_user(
    discord_id: str = None, 
    discord_username: str = None,
    telegram_id: str = None, 
    telegram_username: str = None
) -> Dict[str, Any]:
    """Get or create a user in the database"""
    user_data = {}
    if discord_id:
        user_data["discord_id"] = str(discord_id)
    if discord_username:
        user_data["discord_username"] = discord_username
    if telegram_id:
        user_data["telegram_id"] = str(telegram_id)
    if telegram_username:
        user_data["telegram_username"] = telegram_username
    
    try:
        # Try to find existing user by any of the provided IDs
        query = supabase.table(USERS_TABLE).select("*")
        if discord_id:
            query = query.or_(f"discord_id.eq.{discord_id}")
        if telegram_id:
            query = query.or_(f"telegram_id.eq.{telegram_id}")
        
        result = query.execute()
        
        if result.data and len(result.data) > 0:
            # Update existing user with any new information
            user_id = result.data[0]['id']
            supabase.table(USERS_TABLE).update(user_data).eq('id', user_id).execute()
            return {**result.data[0], **user_data, 'id': user_id}
        else:
            # Create new user
            result = supabase.table(USERS_TABLE).insert(user_data).execute()
            return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error in get_or_create_user: {e}")
        return None

def add_checkin(
    user_id: str,
    group_id: str,
    content: str,
    week_str: str
) -> Dict[str, Any]:
    """Add a new check-in for a user, handles duplicates. Only valid columns are inserted."""
    try:
        # Check for existing check-in
        checkin_result = supabase.table(CHECKINS_TABLE)\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("group_id", group_id)\
            .eq("week", week_str)\
            .execute()
        if checkin_result.data:
            return {"status": "duplicate", "message": "Check-in already exists for this week."}
        
        # Add new check-in
        checkin_data = {
            "user_id": user_id,
            "group_id": group_id,
            "content": content,
            "week": week_str,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table(CHECKINS_TABLE).insert(checkin_data).execute()
        return {"status": "created", "data": result.data[0]} if result.data else None
        
    except Exception as e:
        print(f"Error in add_checkin: {e}")
        return {"status": "error", "message": str(e)}

def add_user_to_group(user_id: str, group_name: str) -> bool:
    """Add a user to a group"""
    try:
        # Check if group exists, create if not
        group_result = (supabase.table(GROUPS_TABLE)
                       .select("*")
                       .eq("name", group_name)
                       .execute())
        
        if not group_result.data:
            # Create the group
            group_result = (supabase.table(GROUPS_TABLE)
                          .insert({"name": group_name})
                          .execute())
            group_id = group_result.data[0]['id']
        else:
            group_id = group_result.data[0]['id']
        
        # Add user to group (no user_type)
        supabase.table(USER_GROUPS_TABLE).upsert({
            "user_id": user_id,
            "group_id": group_id
        }).execute()
        
        return True
    except Exception as e:
        print(f"Error in add_user_to_group: {e}")
        return False

def get_user_groups(user_id: str) -> List[Dict[str, Any]]:
    """Get all groups a user belongs to"""
    try:
        result = (supabase.table(USER_GROUPS_TABLE)
                 .select("groups(*), user_type")
                 .eq("user_id", user_id)
                 .execute())
        return result.data
    except Exception as e:
        print(f"Error in get_user_groups: {e}")
        return []

def is_user_in_group(user_id: str, group_name: str) -> bool:
    """Check if a user is in a specific group"""
    try:
        result = (supabase.table(USER_GROUPS_TABLE)
                 .select("*")
                 .eq("user_id", user_id)
                 .eq("groups.name", group_name)
                 .execute())
        return len(result.data) > 0
    except Exception as e:
        print(f"Error in is_user_in_group: {e}")
        return False

def set_checkin_message(group_name: str, message: str) -> bool:
    """Set the check-in message for a group"""
    try:
        supabase.table(GROUPS_TABLE).upsert({
            "name": group_name,
            "checkin_message": message
        }).execute()
        return True
    except Exception as e:
        print(f"Error in set_checkin_message: {e}")
        return False

def get_checkin_messages() -> Dict[str, str]:
    """Get check-in messages for all groups"""
    try:
        result = supabase.table(GROUPS_TABLE).select("name,checkin_message").execute()
        return {group['name']: group.get('checkin_message', '') for group in result.data}
    except Exception as e:
        print(f"Error in get_checkin_messages: {e}")
        return {}

def migrate_from_json():
    """Migrate data from JSON files to Supabase"""
    import json
    from pathlib import Path
    
    # Migrate authorized users
    if Path('authorized_users.json').exists():
        with open('authorized_users.json', 'r') as f:
            auth_users = json.load(f).get('users', [])
            for user_id in auth_users:
                get_or_create_user(discord_id=str(user_id))
    
    # Migrate groups and memberships
    if Path('groups.json').exists():
        with open('groups.json', 'r') as f:
            groups_data = json.load(f)
            for group_name, platforms in groups_data.items():
                # Add group members
                for platform, users in platforms.items():
                    if platform in ['discord', 'telegram']:
                        for user in users:
                            user_id = user.get('id')
                            username = user.get('username', '')
                            if platform == 'discord':
                                user_data = get_or_create_user(
                                    discord_id=str(user_id),
                                    discord_username=username
                                )
                            else:  # telegram
                                user_data = get_or_create_user(
                                    telegram_id=str(user_id),
                                    telegram_username=username
                                )
                            if user_data:
                                add_user_to_group(user_data['id'], group_name, platform)
    
    # Migrate check-in messages
    if Path('checkin_messages.json').exists():
        with open('checkin_messages.json', 'r') as f:
            messages = json.load(f)
            for group_name, message in messages.items():
                set_checkin_message(group_name, message)
    
    print("Migration completed successfully")
