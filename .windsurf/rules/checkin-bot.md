---
trigger: always_on
---

# gm-checkin-bot: Product Spec & Capabilities

## Overview  
gm-checkin-bot is a multi-platform asynchronous bot that facilitates daily check-ins and team coordination across Telegram and Discord. It supports user check-in logging, team role tracking, and integrations with Supabase for robust backend operations.

## Core Features

### 1. Integrations  
- **Telegram Bot** (`python-telegram-bot`)  
  - Async command handling  
  - Uses `telegram.ext` for simplified architecture  

- **Discord Bot** (`discord.py`)  
  - Handles both commands and events  
  - Integrates with server roles and users  

### 2. Environment & Configuration  
- Manages secrets and keys via `.env` (`python-dotenv`)  
- Isolated config layer for multiple environments (dev, prod)

### 3. Supabase Integration (Migrated from Google Sheets/JSON)  
- Full backend handled through Supabase  
- Async DB interaction via `supabase-py`  
- Structured tables for users, check-ins, and groups  

### 4. User Interaction & Check-In  
- Logs check-ins per user with timestamp and message content  
- Supports both Discord and Telegram users  
- Admin-triggered group assignments

### 5. Modular Architecture  
- Clear separation of concerns:  
  - Bot logic  
  - DB operations  
  - Config management  
- Built for extensibility and multi-service integration

## Dependencies  
- `discord.py`  
- `python-telegram-bot`  
- `python-dotenv`  
- `supabase-py`  
- `python-dateutil`  

## Feature Update: Supabase Migration & User Data Modeling

### Migration Goals  
- Deprecate all usage of Google Sheets and JSON file storage  
- Centralize all data storage and queries via Supabase  

### Supabase Schema Requirements  

#### Tables

**users**  
- `id` (UUID, primary key)  
- `discord_handle` (string, unique)  
- `telegram_handle` (string, nullable)  
- `groups` (array of strings, e.g. ['admin', 'developer'])  
- `created_at` (timestamp)

**checkins**  
- `id` (UUID, primary key)  
- `user_id` (foreign key to users.id)  
- `platform` (enum: 'discord', 'telegram')  
- `message_content` (text)  
- `timestamp` (timestamp)

### New Functionality  
- On first check-in or admin assignment, detect new users and create corresponding records  
- Allow admins to assign or update group membership dynamically  
- Provide admin tooling (via bot commands) to list or filter users by group  
- Display recent check-ins with timestamps and content on request  
