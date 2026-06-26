import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import time
import asyncio
from datetime import datetime
import io

# ══════════════════════════════════════════════════════════════
# BOT CONFIGURATION
# ══════════════════════════════════════════════════════════════
TOKEN = "MTUwNDE1MzgwMDcxMjEzMDYwMg.G9nIFR.9LYtme4g5EQ0fJFhbk17LU6EinjPD1verB7VxQ"  # Replace with your actual bot token
DB_FILE = "bot_data.db"
USER_CHANNEL_ID = 1520027159429648525  # Replace with the normal user channel ID
ADMIN_CHANNEL_ID = 1520027810289156206 # Replace with the admin channel ID

# Intent setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Needed for DMing users

class UIDBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.whitelist_enabled = True # Default state for user channel

    async def setup_hook(self):
        await self.tree.sync()
        self.loop.create_task(self.check_expirations())
        print("Bot setup complete and commands synced.")

    async def check_expirations(self):
        await self.wait_until_ready()
        while not self.is_closed():
            db = sqlite3.connect(DB_FILE)
            cur = db.cursor()
            
            current_time = int(time.time())
            # Find expired entries that haven't been notified yet
            cur.execute("""
                SELECT uid, discord_id, expires_at 
                FROM whitelist 
                WHERE expires_at > 0 AND expires_at <= ? AND notified = 0
            """, (current_time,))
            
            expired_users = cur.fetchall()
            
            for uid, discord_id, expires_at in expired_users:
                if discord_id:
                    try:
                        user = await self.fetch_user(int(discord_id))
                        if user:
                            await user.send(
                                f"Your UID `{uid}` is no longer whitelisted in the database. "
                                f"Please click the link below to whitelist it again:\n"
                                f"https://your-discord-invite-link-here" # REPLACE THIS
                            )
                    except Exception as e:
                        print(f"Could not DM user {discord_id}: {e}")
                
                # Mark as notified so we don't spam them, but leave in DB for history or remove as needed.
                # In standard setups, you might want to delete them. Here we mark notified.
                cur.execute("UPDATE whitelist SET notified = 1 WHERE uid = ?", (uid,))
                
            db.commit()
            db.close()
            await asyncio.sleep(60) # Check every minute

bot = UIDBot()

# ══════════════════════════════════════════════════════════════
# DATABASE INITIALIZATION
# ══════════════════════════════════════════════════════════════
def init_db():
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    # Modify existing table or create new if not exists to include discord_id and notified flag
    cur.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            uid TEXT PRIMARY KEY,
            region TEXT DEFAULT 'GLOBAL',
            expires_at INTEGER DEFAULT 0,
            discord_id TEXT,
            notified INTEGER DEFAULT 0,
            original_duration_days INTEGER DEFAULT 0
        )
    """)
    
    # Table for bot admins
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_admins (
            discord_id TEXT PRIMARY KEY
        )
    """)
    db.commit()
    db.close()

init_db()

# ══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════
def is_bot_admin(discord_id: int) -> bool:
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("SELECT 1 FROM bot_admins WHERE discord_id = ?", (str(discord_id),))
    result = cur.fetchone() is not None
    db.close()
    return result

def add_bot_admin(discord_id: int):
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO bot_admins (discord_id) VALUES (?)", (str(discord_id),))
    db.commit()
    db.close()

async def admin_check(interaction: discord.Interaction) -> bool:
    if interaction.channel_id != ADMIN_CHANNEL_ID:
        await interaction.response.send_message("This command can only be used in the admin channel.", ephemeral=True)
        return False
    
    # Allow server owner or people explicitly added to the admin table
    if interaction.user.id == interaction.guild.owner_id or is_bot_admin(interaction.user.id) or interaction.user.guild_permissions.administrator:
        return True
    
    await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    return False

# ══════════════════════════════════════════════════════════════
# NORMAL USER COMMANDS
# ══════════════════════════════════════════════════════════════
@bot.tree.command(name="add", description="Add your UID to the whitelist for 24 hours")
@app_commands.describe(uid="Your FreeFire UID")
async def add_uid(interaction: discord.Interaction, uid: str):
    if interaction.channel_id != USER_CHANNEL_ID:
        await interaction.response.send_message("This command can only be used in the designated user channel.", ephemeral=True)
        return

    if not bot.whitelist_enabled:
        await interaction.response.send_message("The whitelist system is currently offline. The UID bypass is under maintenance.", ephemeral=True)
        return

    if not uid.isdigit() or len(uid) < 5:
        await interaction.response.send_message("Invalid UID format.", ephemeral=True)
        return

    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    
    # Check if already whitelisted
    cur.execute("SELECT expires_at FROM whitelist WHERE uid = ?", (uid,))
    result = cur.fetchone()
    
    current_time = int(time.time())
    
    if result:
        expires_at = result[0]
        if expires_at == 0 or expires_at > current_time:
            await interaction.response.send_message(f"UID `{uid}` is already whitelisted.", ephemeral=True)
            db.close()
            return

    # Add for 24 hours (86400 seconds)
    expiry = current_time + 86400
    
    cur.execute("""
        INSERT OR REPLACE INTO whitelist (uid, region, expires_at, discord_id, notified, original_duration_days) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (uid, 'GLOBAL', expiry, str(interaction.user.id), 0, 1))
    
    db.commit()
    db.close()
    
    await interaction.response.send_message(f"✅ UID `{uid}` has been whitelisted for 24 hours!", ephemeral=False)

# ══════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="whitelist", description="[ADMIN] Whitelist a UID for a specific number of days")
@app_commands.describe(uid="The FreeFire UID", days="Number of days to whitelist")
async def admin_whitelist(interaction: discord.Interaction, uid: str, days: int):
    if not await admin_check(interaction): return
    
    if not uid.isdigit() or len(uid) < 5:
        await interaction.response.send_message("Invalid UID format.", ephemeral=True)
        return

    if days <= 0:
        await interaction.response.send_message("Days must be greater than 0.", ephemeral=True)
        return

    expiry = int(time.time()) + (days * 86400)
    
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO whitelist (uid, region, expires_at, notified, original_duration_days) 
        VALUES (?, ?, ?, ?, ?)
    """, (uid, 'GLOBAL', expiry, 0, days))
    db.commit()
    db.close()
    
    await interaction.response.send_message(f"✅ Admin: UID `{uid}` whitelisted for {days} days.", ephemeral=False)

@bot.tree.command(name="uids", description="[ADMIN] Get a list of all whitelisted UIDs")
async def admin_uids(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("SELECT uid, expires_at, original_duration_days FROM whitelist")
    rows = cur.fetchall()
    db.close()
    
    if not rows:
        await interaction.response.send_message("No UIDs are currently whitelisted.", ephemeral=True)
        return
    
    content = "Whitelist Report:\n\n"
    active_count = 0
    current_time = int(time.time())
    
    for uid, expires_at, orig_days in rows:
        if expires_at == 0:
            status = "LIFETIME"
            active_count += 1
        elif expires_at > current_time:
            end_date = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')
            start_date = datetime.fromtimestamp(expires_at - (orig_days * 86400)).strftime('%Y-%m-%d %H:%M:%S') if orig_days else "Unknown"
            status = f"Active | Start: {start_date} | End: {end_date}"
            active_count += 1
        else:
            status = "EXPIRED"
            
        content += f"UID: {uid} - {status}\n"
    
    content_bytes = content.encode('utf-8')
    file = discord.File(fp=io.BytesIO(content_bytes), filename="whitelisted_uids.txt")
    
    await interaction.response.send_message(f"Total entries: {len(rows)} | Active: {active_count}", file=file, ephemeral=True)


@bot.tree.command(name="remove", description="[ADMIN] Remove a UID from the whitelist")
@app_commands.describe(uid="The FreeFire UID to remove")
async def admin_remove(interaction: discord.Interaction, uid: str):
    if not await admin_check(interaction): return
    
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("DELETE FROM whitelist WHERE uid = ?", (uid,))
    deleted = cur.rowcount
    db.commit()
    db.close()
    
    if deleted > 0:
        await interaction.response.send_message(f"🗑️ UID `{uid}` removed from the whitelist.", ephemeral=False)
    else:
        await interaction.response.send_message(f"UID `{uid}` was not found in the whitelist.", ephemeral=True)


@bot.tree.command(name="admin", description="[ADMIN] Give admin access to another user for this bot")
@app_commands.describe(user="The Discord user to grant admin access to")
async def admin_add_admin(interaction: discord.Interaction, user: discord.Member):
    # Only allow server owner or existing admins to add new admins
    if not await admin_check(interaction): return
    
    add_bot_admin(user.id)
    await interaction.response.send_message(f"✅ {user.mention} has been granted bot admin access.", ephemeral=False)


@bot.tree.command(name="on", description="[ADMIN] Turn ON the public whitelist system")
async def admin_on(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    bot.whitelist_enabled = True
    await interaction.response.send_message("🟢 The public whitelist system has been turned ON.", ephemeral=False)


@bot.tree.command(name="off", description="[ADMIN] Turn OFF the public whitelist system")
async def admin_off(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    bot.whitelist_enabled = False
    await interaction.response.send_message("🔴 The public whitelist system has been turned OFF. Users cannot add UIDs.", ephemeral=False)


# View for RemoveAll Confirmation
class ConfirmRemoveAll(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @discord.ui.button(label="Confirm 💥", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        
        db = sqlite3.connect(DB_FILE)
        cur = db.cursor()
        cur.execute("DELETE FROM whitelist")
        db.commit()
        db.close()
        
        await interaction.response.edit_message(content="💥 ALL UIDs have been wiped from the whitelist database.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.edit_message(content="Operation cancelled.", view=None)

@bot.tree.command(name="removeall", description="[ADMIN] Remove ALL UIDs from the whitelist database")
async def admin_removeall(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    view = ConfirmRemoveAll()
    await interaction.response.send_message(
        "⚠️ **SECURITY CHECK** ⚠️\nAre you absolutely sure you want to delete EVERY UID from the database?", 
        view=view, 
        ephemeral=True
    )

@bot.tree.command(name="reset", description="[ADMIN] Renew the time for all currently active UIDs")
async def admin_reset(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    
    # Find all UIDs that have a duration attached to them
    cur.execute("SELECT uid, original_duration_days FROM whitelist WHERE original_duration_days > 0")
    rows = cur.fetchall()
    
    current_time = int(time.time())
    updated_count = 0
    
    for uid, orig_days in rows:
        new_expiry = current_time + (orig_days * 86400)
        cur.execute("UPDATE whitelist SET expires_at = ?, notified = 0 WHERE uid = ?", (new_expiry, uid))
        updated_count += 1
        
    db.commit()
    db.close()
    
    await interaction.response.send_message(f"🔄 Reset complete! Renewed durations for {updated_count} UIDs.", ephemeral=False)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

if __name__ == "__main__":
    bot.run(TOKEN)
