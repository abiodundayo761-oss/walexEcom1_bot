# Telegram Member Migration Bot

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YOUR_USERNAME/telegram-migration-bot)

A robust Telegram bot for migrating members between groups with web monitoring interface.

## ✨ Features

- 🚀 **Member Migration**: Extract members from source group to target group
- 🌐 **Web Dashboard**: Monitor progress in real-time via web interface
- 🛡️ **Smart Error Handling**: Auto-handles flood waits, privacy restrictions
- 🔄 **Resume Capability**: Can stop/resume migration anytime
- 📊 **Detailed Logging**: Track every member addition with status
- ⚡ **24/7 Operation**: Runs continuously on Render cloud platform

## 📋 Prerequisites

1. Telegram API credentials from [my.telegram.org](https://my.telegram.org)
2. Telegram account that's a member of both groups
3. GitHub account
4. Render account (free tier works)

## 🚀 Quick Deploy (One-Click)

1. Click the "Deploy to Render" button above
2. Fill in your environment variables:
   - `API_ID`: Your Telegram API ID
   - `API_HASH`: Your Telegram API Hash  
   - `PHONE_NUMBER`: Your phone number with country code
   - `SOURCE_GROUP`: Source group username (e.g., @mygroup)
   - `TARGET_GROUP`: Target group username
3. Click "Apply" and wait for deployment
4. Your bot will be live at `https://your-app.onrender.com`

## 🛠️ Manual Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/telegram-migration-bot.git
cd telegram-migration-bot
