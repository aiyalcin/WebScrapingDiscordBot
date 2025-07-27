import discord
from discord.ext import commands
import PriceTracker
from dotenv import load_dotenv
import os
import Scraper
from discord.ext import tasks
import JsonHandler
import LogHandler as lh
import time
import validators
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import ipaddress
import socket
import shutil
import json
import datetime

CONFIG_PATH = "config/guild_config.json"

def load_guild_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_guild_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

# Helper to get config for a guild
def get_guild_setting(guild_id, key, default=None):
    config = load_guild_config()
    return config.get(str(guild_id), {}).get(key, default)

def set_guild_setting(guild_id, key, value):
    config = load_guild_config()
    if str(guild_id) not in config:
        config[str(guild_id)] = {}
    config[str(guild_id)][key] = value
    save_guild_config(config)

# Interval settings for check-in and price scan tasks (in hours) these can be adjusted as needed through the slash commands
checkinInterval = 12
scanInterval= 1
DEBUG = True  # Enable debug mode to prevent writing prices to the JSON file
PRIVATE_TRACKS_ENABLED = True  # Set to True to enable per-user private tracking

time.sleep(1)
if DEBUG:
    lh.log("Debug mode is enabled. Prices will now be written to the debug json file.", "warn")
    # Copy data.json to debug_data.json if not already present
    if not os.path.exists("Data/debug_data.json"):
        shutil.copyfile("Data/data.json", "Data/debug_data.json")
else:
    # Remove debug_data.json if it exists
    if os.path.exists("Data/debug_data.json"):
        os.remove("Data/debug_data.json")

# Load environmentvariables from .env file
load_dotenv()

# Retrieve Discord bot credentials only
try:
    discordBotKey = os.getenv("discordBotToken")
except Exception as e:
    print(f"Error: {e}")


# Custom Discord bot client with scheduled tasks
class Client(commands.Bot):
    # Called when the bot is ready and connected to Discord
    async def on_ready(self):
        print(f"Logged in as {self.user}!")
        lh.log("Bot is online.", "log")
        self.guild_config = load_guild_config()
        # Sync commands globally
        try:
            lh.log("Synching global commands", "log")
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} commands globally.")
        except Exception as e:
            print(e)
        # Start scheduled tasks for each guild
        for guild in self.guilds:
            await self.start_guild_tasks(guild)

    async def on_guild_join(self, guild):
        guild_id = str(guild.id)
        # Set default values for the new guild
        set_guild_setting(guild_id, "channel_id", None)
        set_guild_setting(guild_id, "checkin_interval", 12)
        set_guild_setting(guild_id, "scan_interval", 1)
        lh.log(f"Bot added to new guild: {guild_id}. Default config created.", "log")
        # Sync commands for this guild
        try:
            await self.tree.sync(guild=guild)
            lh.log(f"Commands synced for guild {guild_id}.", "log")
        except Exception as e:
            lh.log(f"Error syncing commands for guild {guild_id}: {e}", "error")

    async def on_guild_remove(self, guild):
        guild_id = str(guild.id)
        config = load_guild_config()
        if guild_id in config:
            del config[guild_id]
            save_guild_config(config)
            lh.log(f"Bot removed from guild: {guild_id}. Config deleted.", "log")

    async def start_guild_tasks(self, guild):
        guild_id = str(guild.id)
        config = load_guild_config()
        channel_id = config.get(guild_id, {}).get("channel_id")
        checkin_interval = config.get(guild_id, {}).get("checkin_interval", 12)
        scan_interval = config.get(guild_id, {}).get("scan_interval", 1)
        if channel_id:
            channel = self.get_channel(channel_id)
            if channel:
                # Run a global price check immediately when bot starts
                lh.log(f"Initial price check for guild {guild_id}", "log")
                changed_prices_global = PriceTracker.CheckPrices(DEBUG, False)
                changed_prices_private = PriceTracker.CheckPrices(DEBUG, True)
                pricewatch_role = discord.utils.get(channel.guild.roles, name="Pricewatch")
                pricewatch_mention = pricewatch_role.mention if pricewatch_role else "@Pricewatch"
                # Send global tracker changes to channel
                if changed_prices_global:
                    message = ""
                    for price in changed_prices_global:
                        if price is None:
                            message += "Price could not be retrieved for one of the items. Item might be sold out.\n"
                        else:
                            if DEBUG:
                                mention = "Pricewatch"
                            else:
                                mention = pricewatch_mention
                            message += f"{mention} - Name: {price['name']} OLD price: {price['Old price']} --> NEW price {price['New price']}\n"
                    await channel.send(message)
                # Send private tracker changes as DMs
                if changed_prices_private:
                    for price in changed_prices_private:
                        if price is None:
                            continue
                        username = price.get('user')
                        if username:
                            member = discord.utils.find(lambda m: m.name.lower() == username, guild.members)
                            if member:
                                dm_message = f"Your tracker '{price['name']}' changed price: OLD price: {price['Old price']} --> NEW price {price['New price']}"
                                try:
                                    await member.send(dm_message)
                                except Exception as e:
                                    lh.log(f"Failed to DM {username}: {e}", "error")
                # Start tasks for this guild
                self.loop.create_task(self.guild_checkin_task(guild, channel, checkin_interval))
                self.loop.create_task(self.guild_price_check_task(guild, channel, scan_interval))

    async def guild_checkin_task(self, guild, channel, interval):
        while True:
            lh.log(f"Checkin for guild {guild.id}", "log")
            if not DEBUG:
                # Use log channel if set, otherwise fallback to public channel
                log_channel_id = get_guild_setting(str(guild.id), "log_channel_id")
                log_channel = self.get_channel(log_channel_id) if log_channel_id else channel
                await log_channel.send(f"@Pricewatch is still running! Last check was at {time.strftime('%H:%M:%S', time.localtime())}")
            next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=interval)
            await discord.utils.sleep_until(next_run)

    async def guild_price_check_task(self, guild, channel, interval):
        while True:
            lh.log(f"Price check for guild {guild.id}", "log")
            changed_prices_global = PriceTracker.CheckPrices(DEBUG, False)
            changed_prices_private = PriceTracker.CheckPrices(DEBUG, True)
            pricewatch_role = discord.utils.get(channel.guild.roles, name="Pricewatch")
            pricewatch_mention = pricewatch_role.mention if pricewatch_role else "@Pricewatch"
            # Send global tracker changes to channel
            if changed_prices_global:
                message = ""
                for price in changed_prices_global:
                    if price is None:
                        message += "Price could not be retrieved for one of the items. Item might be sold out.\n"
                    else:
                        if DEBUG:
                            mention = "Pricewatch"
                        else:
                            mention = pricewatch_mention
                        message += f"{mention} - Name: {price['name']} OLD price: {price['Old price']} --> NEW price {price['New price']}\n"
                await channel.send(message)
            # Send private tracker changes as DMs
            if changed_prices_private:
                for price in changed_prices_private:
                    if price is None:
                        continue
                    username = price.get('user')
                    if username:
                        member = discord.utils.find(lambda m: m.name.lower() == username, guild.members)
                        if member:
                            dm_message = f"Your tracker '{price['name']}' changed price: OLD price: {price['Old price']} --> NEW price {price['New price']}"
                            try:
                                await member.send(dm_message)
                            except Exception as e:
                                lh.log(f"Failed to DM {username}: {e}", "error")
            next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=interval)
            await discord.utils.sleep_until(next_run)

# Set up Discord bot intents and client
intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="/", intents=intents)

# Simple class to represent a tracked website (not used in main logic)
class TrackedWebsite:
    def __init__(self, Id, Url, CurrentPrice):
        self.id = Id
        self.url = Url
        self.currentPrice = CurrentPrice

# Helper function to validate URLs
def isValidUrl(URL):
    if not (validators.url(URL) and URL.startswith(("http://", "https://"))):
        return False
    try:
        parsed = urlparse(URL)
        hostname = parsed.hostname
        if hostname is None:
            return False
        # Try to resolve the hostname to an IP address
        ip = None
        try:
            ip = socket.gethostbyname(hostname)
        except Exception:
            return False
        # Check if the IP is private or loopback
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_multicast:
            return False
    except Exception:
        return False
    return True

# Helper function to get user display string
def get_user_display(user):
    username = user.name
    discriminator = getattr(user, 'discriminator', None)
    if discriminator and discriminator != 0:
        return f"{username}#{discriminator}"
    else:
        return username

# Slash command: show current tracked prices
@client.tree.command(name="pricetrackglobal", description="Return list of tracked prices for all global trackers")
async def priceTrackGlobal(interaction: discord.Interaction):
    lh.log(f"{get_user_display(interaction.user)} ran the pricetrackglobal command.", "log")
    lh.log("Starting pricetrackglobal command.", "log")
    try:
        await interaction.response.send_message("Processing global tracked prices. One moment...")
        msg = await interaction.original_response()
        lh.log("Scraping global prices", "log")
        guild_id = str(interaction.guild.id)
        prices = Scraper.getAllPrices(DEBUG, False, guild_id)
        lh.log_done
        message = ""
        lh.log("Creating message", "log")
        for price_object in prices:
            message += f"\nID: {price_object['id']} Name: {price_object['name']} - Prices: {price_object['price']}"
        lh.log_done
        MAX_MESSAGE_LENGTH = 2000
        if len(message) > MAX_MESSAGE_LENGTH:
            from io import StringIO
            file = discord.File(fp=StringIO(message), filename="tracked_prices_global.txt")
            lh.log("Sending message as file due to length", "log")
            await msg.edit(content="📄 The list of global tracked prices is too long for a message. See the attached file:", attachments=[file])
        else:
            lh.log("Sending message", "log")
            await msg.edit(content=message)
        lh.log_done
    except Exception as e:
        lh.log(f"Error in pricetrackglobal: {str(e)}", "error")
        await interaction.followup.send("An error occurred while processing your request.")

# Slash command: show all current trackers as a .txt file
@client.tree.command(name="showcurrenttracks", description="Return list of all current trackers and their URL's")
async def showCurrentTracks(interaction: discord.Interaction):
    lh.log(f"{get_user_display(interaction.user)} ran the showcurrenttracks command.", "log")
    lh.log("Starting showcurrenttracks command.", "log")
    lh.log("Loading json data", "log")
    await interaction.response.send_message("Processing current trackers. One moment...")
    msg = await interaction.original_response()
    guild_id = str(interaction.guild.id)
    # Get all global and user trackers
    global_tracks = JsonHandler.getAllJsonData(False, guild_id)
    # Get all user trackers as a flat list
    user_tracks = JsonHandler.getAllJsonData(True)
    message = "Global Trackers:\n"
    for data in global_tracks:
        message += f"ID: {data['id']} | Name: {data['name']} | URL: {data['url']}\n"
    message += "\nUser Trackers:\n"
    for data in user_tracks:
        message += f"ID: {data['id']} | Name: {data['name']} | URL: {data['url']}\n"
    MAX_MESSAGE_LENGTH = 2000
    if len(message) > MAX_MESSAGE_LENGTH:
        from io import StringIO
        file = discord.File(fp=StringIO(message), filename="current_trackers.txt")
        lh.log("Sending message as file due to length", "log")
        await msg.edit(content="📄 The list of current trackers is too long for a message. See the attached file:", attachments=[file])
    else:
        lh.log("Sending message as text", "log")
        await msg.edit(content=message)
    lh.log_done

# Slash command: show all your tracked items
@client.tree.command(name="showmytracks", description="Show all your tracked items")
async def showMyTracks(interaction: discord.Interaction):
    lh.log(f"{get_user_display(interaction.user)} ran the showMytracks command.", "log")
    await interaction.response.send_message("Processing your tracks. One moment...")
    msg = await interaction.original_response()
    username = interaction.user.name.lower()
    user_tracks = JsonHandler.getUserTrackers(username)
    if not user_tracks:
        await msg.edit(content="You have no tracks yet.")
        return
    message = f"Tracks for {username}:\n"
    for data in user_tracks:
        message += f"ID: {data['id']} | Name: {data['name']} | URL: {data['url']}\n"
    MAX_MESSAGE_LENGTH = 2000
    if len(message) > MAX_MESSAGE_LENGTH:
        from io import StringIO
        file = discord.File(fp=StringIO(message), filename="my_tracks.txt")
        await msg.edit(content="📄 Your list of tracks is too long for a message. See the attached file:", attachments=[file])
    else:
        await msg.edit(content=message)

# Slash command: add a new global tracker
@client.tree.command(name="addglobaltracker", description="Adds a new global tracker to the list")
async def addGlobalTracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    lh.log(f"{get_user_display(interaction.user)} ran the addglobaltracker command.", "log")
    lh.log("Starting addglobaltracker command.", "log")
    # Send initial message
    await interaction.response.send_message("Checking JavaScript requirements. One moment...")
    msg = await interaction.original_response()
    guild_id = str(interaction.guild.id)
    if isValidUrl(url):
        try:
            html_text = requests.get(url, timeout=10).text
            soup = BeautifulSoup(html_text, "lxml")
            price_element = soup.select_one(css_selector)
            js_required = price_element is None
        except requests.exceptions.Timeout:
            lh.log(f"Timeout checking JS requirement for {url}", "error")
            js_required = True
            await msg.edit(content=f"⚠️ Timeout while checking {url}. Assuming JavaScript is required.")
            return
        except Exception as e:
            lh.log(f"Error checking JS requirement: {e}", "error")
            js_required = True
        new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": "0", "js": js_required}
        JsonHandler.addTracker(new_tracker, guild_id)
        await msg.edit(content=f"✅ Now tracking globally: {name} (JavaScript required: {js_required})")
    else:
        await msg.edit(content="❌ Invalid url!")

# Slash command: add a new private tracker
@client.tree.command(name="addprivatetracker", description="Adds a new private tracker to your list")
async def addPrivateTracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    lh.log(f"{get_user_display(interaction.user)} ran the addprivatetracker command.", "log")
    lh.log("Starting addprivatetracker command.", "log")
    username = interaction.user.name.lower()
    # Send initial message
    await interaction.response.send_message("Checking JavaScript requirements. One moment...")
    msg = await interaction.original_response()
    if isValidUrl(url):
        try:
            html_text = requests.get(url, timeout=10).text
            soup = BeautifulSoup(html_text, "lxml")
            price_element = soup.select_one(css_selector)
            js_required = price_element is None
        except requests.exceptions.Timeout:
            lh.log(f"Timeout checking JS requirement for {url}", "error")
            js_required = True
            await msg.edit(content=f"⚠️ Timeout while checking {url}. Assuming JavaScript is required.")
            return
        except Exception as e:
            lh.log(f"Error checking JS requirement: {e}", "error")
            js_required = True
        new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": "0", "js": js_required}
        JsonHandler.addUserTracker(username, new_tracker)
        await msg.edit(content=f"✅ Now tracking for you: {name} (JavaScript required: {js_required})")
    else:
        await msg.edit(content="❌ Invalid url!")

# Slash command: remove a tracker by its ID
@client.tree.command(name="removetracker", description="Deletes a tracker by its id (global or private)")
async def removeTracker(interaction: discord.Interaction, id: int):
    await interaction.response.defer()
    lh.log(f"{get_user_display(interaction.user)} ran the removeTracker command.", "log")
    lh.log("Starting removeTracker command.", "log")
    username = interaction.user.name.lower()
    guild_id = str(interaction.guild.id)
    # Get all global trackers
    global_trackers = JsonHandler.getAllJsonData(False, guild_id)
    # Get user trackers as a dict
    import json
    user_trackers_dict = {}
    with open(JsonHandler.get_active_json_path(), "r") as file:
        data = json.load(file)
        user_trackers_dict = data.get('users', {})
    # Check if tracker is global
    is_global = any(t['id'] == id for t in global_trackers)
    # Find owner if private
    owner = None
    for user, trackers in user_trackers_dict.items():
        if any(t['id'] == id for t in trackers):
            owner = user
            break
    # Admins can delete any tracker
    if interaction.user.guild_permissions.administrator:
        if is_global:
            JsonHandler.removeTracker(id, guild_id)
            await interaction.followup.send(f"✅ Global tracker with ID {id} has been removed by admin.", suppress_embeds=True)
            return
        if owner:
            result = JsonHandler.removeUserTracker(owner, id)
            if result:
                await interaction.followup.send(f"✅ Private tracker with ID {id} has been removed by admin.", suppress_embeds=True)
            else:
                await interaction.followup.send("❌ Private tracker not found.", suppress_embeds=True)
            return
        await interaction.followup.send("❌ Tracker not found.", suppress_embeds=True)
        return
    # Non-admins: can delete global trackers or their own private trackers
    if is_global:
        JsonHandler.removeTracker(id, guild_id)
        await interaction.followup.send(f"✅ Global tracker with ID {id} has been removed.", suppress_embeds=True)
        return
    # Non-admins: can only delete their own private trackers
    if owner == username:
        result = JsonHandler.removeUserTracker(username, id)
        if result:
            await interaction.followup.send(f"✅ Your private tracker with ID {id} has been removed.", suppress_embeds=True)
        else:
            await interaction.followup.send("❌ Private tracker not found.", suppress_embeds=True)
        return
    await interaction.followup.send("❌ You can only remove global trackers or your own private trackers.", suppress_embeds=True)

# Slash command: set the public channel for price updates
@client.tree.command(name="setpublicchannel", description="Set the public channel for price and tracker updates")
async def set_public_channel(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    channel_id = interaction.channel.id
    set_guild_setting(guild_id, "channel_id", channel_id)
    await interaction.response.send_message("✅ This channel is now set for public price and tracker notifications.")

# Slash command: set the log channel for bot status updates
@client.tree.command(name="setlogchannel", description="Set the log channel for bot status updates (still running messages)")
async def set_log_channel(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    channel_id = interaction.channel.id
    set_guild_setting(guild_id, "log_channel_id", channel_id)
    await interaction.response.send_message("✅ This channel is now set for bot status updates.")

# Slash command: set the check-in interval (hours)
@client.tree.command(name="setcheckininterval", description="Set check-in interval (hours)")
async def set_checkin_interval(interaction: discord.Interaction, interval: int):
    guild_id = str(interaction.guild.id)
    set_guild_setting(guild_id, "checkin_interval", interval)
    await interaction.response.send_message(f"✅ Check-in interval set to {interval} hours.")

# Slash command: set the scan interval (hours)
@client.tree.command(name="setscaninterval", description="Set scan interval (hours)")
async def set_scan_interval(interaction: discord.Interaction, interval: int):
    guild_id = str(interaction.guild.id)
    set_guild_setting(guild_id, "scan_interval", interval)
    await interaction.response.send_message(f"✅ Scan interval set to {interval} hours.")
        
# Start the Discord bot
client.run(discordBotKey)
