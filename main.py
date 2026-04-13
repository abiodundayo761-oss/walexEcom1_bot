import os
import asyncio
import logging
import json
from datetime import datetime
from flask import Flask, jsonify, request
from threading import Thread
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import InputPeerUser, InputPeerChannel

# ==================== CONFIGURATION ====================
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE_NUMBER = os.getenv('PHONE_NUMBER', '')
SOURCE_GROUP = os.getenv('SOURCE_GROUP', '')
TARGET_GROUP = os.getenv('TARGET_GROUP', '')
DELAY_BETWEEN_ADDS = int(os.getenv('DELAY_BETWEEN_ADDS', '60'))
MAX_MEMBERS_PER_SESSION = int(os.getenv('MAX_MEMBERS_PER_SESSION', '50'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')  # Optional: For notifications

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP ====================
app = Flask(__name__)

# Global status tracking
migration_status = {
    "is_running": False,
    "total_added": 0,
    "total_failed": 0,
    "current_member": "",
    "progress": "0/0",
    "last_run": None,
    "last_error": None,
    "members_processed": []
}

# ==================== TELEGRAM CLIENT ====================
client = TelegramClient('migration_session', API_ID, API_HASH)

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    """Homepage with bot status"""
    return jsonify({
        "name": "Telegram Member Migration Bot",
        "version": "1.0.0",
        "status": "Online",
        "migration_status": migration_status,
        "endpoints": {
            "/start": "Start migration process",
            "/stop": "Stop current migration",
            "/status": "Get detailed status",
            "/logs": "View recent migration logs"
        }
    })

@app.route('/start', methods=['GET', 'POST'])
def start_migration():
    """Start the member migration process"""
    if migration_status["is_running"]:
        return jsonify({
            "success": False,
            "message": "Migration is already running",
            "progress": migration_status["progress"]
        }), 409
    
    # Reset status
    migration_status["total_added"] = 0
    migration_status["total_failed"] = 0
    migration_status["members_processed"] = []
    migration_status["last_error"] = None
    
    # Start migration in background thread
    thread = Thread(target=run_migration_async)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Migration started successfully",
        "source": SOURCE_GROUP,
        "target": TARGET_GROUP
    })

@app.route('/stop', methods=['POST'])
def stop_migration():
    """Stop the current migration"""
    if not migration_status["is_running"]:
        return jsonify({
            "success": False,
            "message": "No migration is currently running"
        }), 400
    
    migration_status["is_running"] = False
    return jsonify({
        "success": True,
        "message": "Migration stopped",
        "total_added": migration_status["total_added"]
    })

@app.route('/status')
def get_status():
    """Get detailed migration status"""
    return jsonify(migration_status)

@app.route('/logs')
def get_logs():
    """Get recent migration logs"""
    limit = request.args.get('limit', default=50, type=int)
    logs = migration_status["members_processed"][-limit:]
    return jsonify({
        "total": len(migration_status["members_processed"]),
        "logs": logs
    })

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ==================== MIGRATION LOGIC ====================
async def migrate_members_async():
    """Main migration logic"""
    global migration_status
    
    try:
        # Connect to Telegram
        await client.start(phone=PHONE_NUMBER)
        logger.info("✅ Connected to Telegram")
        
        # Get group entities
        logger.info(f"📥 Fetching source group: {SOURCE_GROUP}")
        source_entity = await client.get_entity(SOURCE_GROUP)
        
        logger.info(f"📤 Fetching target group: {TARGET_GROUP}")
        target_entity = await client.get_entity(TARGET_GROUP)
        
        logger.info(f"Source: {source_entity.title} (ID: {source_entity.id})")
        logger.info(f"Target: {target_entity.title} (ID: {target_entity.id})")
        
        # Fetch members from source
        logger.info("🔍 Fetching members from source group...")
        members = []
        
        async for user in client.iter_participants(source_entity):
            # Skip bots and deleted accounts
            if user.bot:
                logger.info(f"⏭️ Skipping bot: @{user.username or user.id}")
                continue
            if user.deleted:
                logger.info(f"⏭️ Skipping deleted account: {user.id}")
                continue
                
            members.append(user)
            
            # Stop if we reached the limit
            if len(members) >= MAX_MEMBERS_PER_SESSION:
                break
        
        total_members = len(members)
        logger.info(f"👥 Found {total_members} eligible members to add")
        
        # Process each member
        for index, user in enumerate(members, 1):
            if not migration_status["is_running"]:
                logger.info("⏹️ Migration stopped by user")
                break
            
            try:
                # Update status
                user_display = f"{user.first_name or ''} {user.last_name or ''}".strip()
                if not user_display:
                    user_display = f"User_{user.id}"
                
                migration_status["current_member"] = user_display
                migration_status["progress"] = f"{index}/{total_members}"
                
                logger.info(f"[{index}/{total_members}] Adding {user_display}...")
                
                # Add user to target group
                await client(InviteToChannelRequest(
                    channel=InputPeerChannel(target_entity.id, target_entity.access_hash),
                    users=[InputPeerUser(user.id, user.access_hash)]
                ))
                
                # Success
                migration_status["total_added"] += 1
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user": user_display,
                    "status": "success",
                    "index": f"{index}/{total_members}"
                }
                migration_status["members_processed"].append(log_entry)
                
                logger.info(f"✅ Successfully added {user_display}")
                
                # Delay between adds (avoid flood limits)
                if index < total_members and migration_status["is_running"]:
                    logger.info(f"⏳ Waiting {DELAY_BETWEEN_ADDS} seconds...")
                    await asyncio.sleep(DELAY_BETWEEN_ADDS)
                    
            except errors.UserPrivacyRestrictedError:
                # User doesn't allow being added to groups
                migration_status["total_failed"] += 1
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user": user_display,
                    "status": "privacy_restricted",
                    "index": f"{index}/{total_members}"
                }
                migration_status["members_processed"].append(log_entry)
                logger.warning(f"⚠️ {user_display} has privacy restrictions")
                
            except errors.UserAlreadyParticipantError:
                # User already in target group
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user": user_display,
                    "status": "already_member",
                    "index": f"{index}/{total_members}"
                }
                migration_status["members_processed"].append(log_entry)
                logger.info(f"ℹ️ {user_display} is already in the target group")
                
            except errors.FloodWaitError as e:
                # Rate limit hit
                wait_time = e.seconds
                logger.warning(f"⚠️ Flood wait triggered. Waiting {wait_time} seconds...")
                
                migration_status["last_error"] = f"Flood wait: {wait_time}s"
                await asyncio.sleep(wait_time)
                
                # Retry after waiting
                try:
                    await client(InviteToChannelRequest(
                        channel=InputPeerChannel(target_entity.id, target_entity.access_hash),
                        users=[InputPeerUser(user.id, user.access_hash)]
                    ))
                    migration_status["total_added"] += 1
                    logger.info(f"✅ Successfully added {user_display} after flood wait")
                except Exception as retry_error:
                    migration_status["total_failed"] += 1
                    logger.error(f"❌ Failed after flood wait: {retry_error}")
                    
            except Exception as e:
                # Other errors
                migration_status["total_failed"] += 1
                error_msg = str(e)
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user": user_display,
                    "status": "error",
                    "error": error_msg,
                    "index": f"{index}/{total_members}"
                }
                migration_status["members_processed"].append(log_entry)
                logger.error(f"❌ Failed to add {user_display}: {error_msg}")
        
        # Migration complete
        migration_status["last_run"] = datetime.now().isoformat()
        logger.info(f"🎯 Migration session complete!")
        logger.info(f"   ✅ Total added: {migration_status['total_added']}")
        logger.info(f"   ❌ Total failed: {migration_status['total_failed']}")
        
        # Optional: Send webhook notification
        if WEBHOOK_URL:
            await send_webhook_notification()
        
    except Exception as e:
        error_msg = f"Fatal error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        migration_status["last_error"] = error_msg
        
    finally:
        migration_status["is_running"] = False
        migration_status["current_member"] = ""
        migration_status["progress"] = "Completed"
        await client.disconnect()

async def send_webhook_notification():
    """Send completion notification to webhook"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            payload = {
                "event": "migration_complete",
                "total_added": migration_status["total_added"],
                "total_failed": migration_status["total_failed"],
                "timestamp": datetime.now().isoformat()
            }
            await session.post(WEBHOOK_URL, json=payload)
            logger.info("📤 Webhook notification sent")
    except Exception as e:
        logger.error(f"Failed to send webhook: {e}")

def run_migration_async():
    """Wrapper to run async migration in thread"""
    migration_status["is_running"] = True
    
    # Create new event loop for the thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(migrate_members_async())
    except Exception as e:
        logger.error(f"Thread error: {e}")
        migration_status["last_error"] = str(e)
        migration_status["is_running"] = False
    finally:
        loop.close()

# ==================== AUTO-START (OPTIONAL) ====================
def auto_start_migration():
    """Auto-start migration on bot startup (optional)"""
    import time
    time.sleep(5)  # Wait for everything to initialize
    if os.getenv('AUTO_START', 'false').lower() == 'true':
        logger.info("🚀 Auto-starting migration...")
        Thread(target=run_migration_async).start()

# ==================== MAIN ====================
if __name__ == '__main__':
    # Auto-start if configured
    if os.getenv('AUTO_START', 'false').lower() == 'true':
        Thread(target=auto_start_migration, daemon=True).start()
    
    # Start Flask server
    port = int(os.getenv('PORT', 10000))
    logger.info(f"🌐 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
