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
TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"  # Replace with your actual bot token
USER_CHANNEL_ID = 1520027159429648525  # Replace with the normal user channel ID
ADMIN_CHANNEL_ID = 1520027810289156206 # Replace with the admin channel ID
OWNER_ID = 810846292364361728         # Put your real Discord ID here!

DB_FILE = "bot_data.db"

# ══════════════════════════════════════════════════════════════
# CUSTOM EMOJIS (FROM RAPID PANEL)
# ══════════════════════════════════════════════════════════════
E_SHIELD = "<:shield:1434400777157218325>"
E_DIAMOND = "<:diamond:1434400446990123038>"
E_CODE = "<:code:1426201077077905428>"
E_DOT = "<:dot:1426201074045292715>"
E_THUMBSUP = "<:thumbsup:1434763557555277925>"
E_HANDSHAKE = "<:handshake:1468980809599025243>"
E_DEVIL = "<:devil:1434400383912120400>"

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
                            embed = discord.Embed(
                                title=f"{E_DEVIL} WHITELIST EXPIRED",
                                description=f"Your UID bypass access has officially ended.\n\n{E_DOT} **UID:** `{uid}`\n{E_DOT} **Status:** `REVOKED`",
                                color=0xff0000
                            )
                            embed.add_field(name=f"{E_SHIELD} Action Required", value="You are no longer protected. Please click the link below to generate a new whitelist request and regain your bypass access immediately.", inline=False)
                            embed.add_field(name=f"{E_DIAMOND} Rapid Panel", value="[Click here to re-whitelist](https://your-discord-invite-link-here)", inline=False) # REPLACE THIS
                            embed.set_footer(text="RAPID PANEL • Automated Security Alert")
                            
                            await user.send(embed=embed)
                    except Exception as e:
                        print(f"Could not DM user {discord_id}: {e}")
                
                # Mark as notified so we don't spam them
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
        embed = discord.Embed(title=f"{E_DEVIL} Access Denied", description=f"{E_DOT} This command can only be used in the secure admin channel.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
    
    # Explicitly check for OWNER_ID first!
    if interaction.user.id == OWNER_ID or interaction.user.id == interaction.guild.owner_id or is_bot_admin(interaction.user.id) or interaction.user.guild_permissions.administrator:
        return True
    
    embed = discord.Embed(title=f"{E_DEVIL} Permission Denied", description=f"{E_DOT} You do not have the required clearance to execute admin commands.", color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    return False

# ══════════════════════════════════════════════════════════════
# NORMAL USER COMMANDS
# ══════════════════════════════════════════════════════════════
@bot.tree.command(name="add", description="Add your UID to the whitelist for 24 hours")
@app_commands.describe(uid="Your FreeFire UID")
async def add_uid(interaction: discord.Interaction, uid: str):
    if interaction.channel_id != USER_CHANNEL_ID:
        embed = discord.Embed(title=f"{E_DEVIL} Wrong Channel", description=f"{E_DOT} Please use the designated user channel to submit your UID.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not bot.whitelist_enabled:
        embed = discord.Embed(title=f"{E_SHIELD} System Offline", description=f"{E_DOT} The public whitelist system is currently offline for maintenance.", color=0xffaa00)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not uid.isdigit() or len(uid) < 5:
        embed = discord.Embed(title=f"{E_DEVIL} Invalid Format", description=f"{E_DOT} UID must contain only numbers and be valid.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    
    cur.execute("SELECT expires_at FROM whitelist WHERE uid = ?", (uid,))
    result = cur.fetchone()
    
    current_time = int(time.time())
    
    if result:
        expires_at = result[0]
        if expires_at == 0 or expires_at > current_time:
            embed = discord.Embed(title=f"{E_SHIELD} Already Whitelisted", description=f"{E_DOT} UID **`{uid}`** is already active in the Rapid Panel.", color=0xffaa00)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            db.close()
            return

    expiry = current_time + 86400
    
    cur.execute("""
        INSERT OR REPLACE INTO whitelist (uid, region, expires_at, discord_id, notified, original_duration_days) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (uid, 'GLOBAL', expiry, str(interaction.user.id), 0, 1))
    
    db.commit()
    db.close()
    
    # INSANELY PREMIUM SUCCESS EMBED
    embed = discord.Embed(
        title=f"{E_DIAMOND} RAPID PANEL • WHITELIST ACTIVE",
        description=f"Your bypass access has been securely activated. You are now protected by the Rapid Panel infrastructure.",
        color=0xff0000 # Red aesthetic
    )
    embed.add_field(name=f"{E_HANDSHAKE} Authorized User", value=f"> {interaction.user.mention}", inline=True)
    embed.add_field(name=f"{E_CODE} Target UID", value=f"> `{uid}`", inline=True)
    embed.add_field(name=f"{E_SHIELD} Duration", value="> `24 Hours`", inline=True)
    
    embed.add_field(name=f"{E_THUMBSUP} Start Time", value=f"> <t:{current_time}:F>", inline=False)
    embed.add_field(name=f"{E_DEVIL} Expiration Time", value=f"> <t:{expiry}:F> (<t:{expiry}:R>)", inline=False)
    
    embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
    embed.set_footer(text="RAPID PANEL • Secure Connection Established")
    
    await interaction.response.send_message(content=f"{interaction.user.mention} {E_THUMBSUP} Your request was processed!", embed=embed, ephemeral=False)

# ══════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="whitelist", description="[ADMIN] Whitelist a UID for a specific number of days")
@app_commands.describe(uid="The FreeFire UID", days="Number of days to whitelist")
async def admin_whitelist(interaction: discord.Interaction, uid: str, days: int):
    if not await admin_check(interaction): return
    
    if not uid.isdigit() or len(uid) < 5:
        embed = discord.Embed(title=f"{E_DEVIL} Invalid Format", description=f"{E_DOT} UID must contain only numbers.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if days <= 0:
        embed = discord.Embed(title=f"{E_DEVIL} Invalid Duration", description=f"{E_DOT} Days must be greater than 0.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    current_time = int(time.time())
    expiry = current_time + (days * 86400)
    
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO whitelist (uid, region, expires_at, notified, original_duration_days) 
        VALUES (?, ?, ?, ?, ?)
    """, (uid, 'GLOBAL', expiry, 0, days))
    db.commit()
    db.close()
    
    embed = discord.Embed(title=f"{E_DIAMOND} ADMIN WHITELIST APPLIED", color=0xff0000)
    embed.add_field(name=f"{E_SHIELD} Admin", value=f"> {interaction.user.mention}", inline=True)
    embed.add_field(name=f"{E_CODE} UID", value=f"> `{uid}`", inline=True)
    embed.add_field(name=f"{E_HANDSHAKE} Duration", value=f"> `{days} Days`", inline=True)
    embed.add_field(name=f"{E_DEVIL} Expiration", value=f"> <t:{expiry}:F>", inline=False)
    embed.set_footer(text="RAPID PANEL • ADMIN OVERRIDE SUCCESSFUL")
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.tree.command(name="uids", description="[ADMIN] Get a list of all whitelisted UIDs")
async def admin_uids(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("SELECT uid, expires_at, original_duration_days FROM whitelist")
    rows = cur.fetchall()
    db.close()
    
    if not rows:
        embed = discord.Embed(title=f"{E_SHIELD} Database Empty", description=f"{E_DOT} No UIDs are currently whitelisted.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    content = "Rapid Panel Whitelist Report:\n\n"
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
    file = discord.File(fp=io.BytesIO(content_bytes), filename="rapid_panel_uids.txt")
    
    embed = discord.Embed(title=f"{E_DIAMOND} WHITELIST DATABASE REPORT", color=0xff0000)
    embed.add_field(name=f"{E_CODE} Total Entries", value=f"> `{len(rows)}`", inline=True)
    embed.add_field(name=f"{E_SHIELD} Active Bypassers", value=f"> `{active_count}`", inline=True)
    embed.set_footer(text="See attached .txt file for full details")
    
    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)


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
        embed = discord.Embed(title=f"{E_DEVIL} UID REVOKED", description=f"{E_DOT} UID **`{uid}`** has been permanently removed from the Rapid Panel database.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=False)
    else:
        embed = discord.Embed(title=f"{E_SHIELD} Not Found", description=f"{E_DOT} UID **`{uid}`** does not exist in the database.", color=0xffaa00)
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="admin", description="[ADMIN] Give admin access to another user for this bot")
@app_commands.describe(user="The Discord user to grant admin access to")
async def admin_add_admin(interaction: discord.Interaction, user: discord.Member):
    if not await admin_check(interaction): return
    
    add_bot_admin(user.id)
    embed = discord.Embed(title=f"{E_DIAMOND} ADMIN GRANTED", description=f"{E_DOT} {user.mention} has been promoted to Rapid Panel Admin.", color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=False)


@bot.tree.command(name="on", description="[ADMIN] Turn ON the public whitelist system")
async def admin_on(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    bot.whitelist_enabled = True
    embed = discord.Embed(title=f"{E_THUMBSUP} SYSTEM ONLINE", description=f"{E_DOT} The public whitelist system is now **ACTIVE**. Users can submit UIDs.", color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=False)


@bot.tree.command(name="off", description="[ADMIN] Turn OFF the public whitelist system")
async def admin_off(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    bot.whitelist_enabled = False
    embed = discord.Embed(title=f"{E_DEVIL} SYSTEM OFFLINE", description=f"{E_DOT} The public whitelist system is now **DISABLED**. Submissions are paused.", color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=False)


class ConfirmRemoveAll(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @discord.ui.button(label="CONFIRM WIPE 💥", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        
        db = sqlite3.connect(DB_FILE)
        cur = db.cursor()
        cur.execute("DELETE FROM whitelist")
        db.commit()
        db.close()
        
        embed = discord.Embed(title=f"{E_DEVIL} DATABASE WIPED", description=f"{E_DOT} ALL UIDs have been successfully eradicated from the Rapid Panel system.", color=0x000000)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        embed = discord.Embed(title=f"{E_SHIELD} Operation Cancelled", description=f"{E_DOT} Database wipe aborted.", color=0xff0000)
        await interaction.response.edit_message(embed=embed, view=None)

@bot.tree.command(name="removeall", description="[ADMIN] Remove ALL UIDs from the whitelist database")
async def admin_removeall(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    view = ConfirmRemoveAll()
    embed = discord.Embed(title=f"{E_DEVIL} CRITICAL SECURITY OVERRIDE", description=f"**Are you absolutely sure you want to delete EVERY UID from the database?**\nThis action cannot be undone.", color=0xff0000)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="reset", description="[ADMIN] Renew the time for all currently active UIDs")
async def admin_reset(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    
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
    
    embed = discord.Embed(title=f"{E_HANDSHAKE} Mass Renewal Complete", description=f"{E_DOT} Successfully renewed the duration for **`{updated_count}`** UIDs.", color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=False)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

if __name__ == "__main__":
    bot.run(TOKEN)
