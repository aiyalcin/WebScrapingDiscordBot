# Main entry point for the Discord price tracking bot
# Imports required libraries and modules
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
import ipaddress
import socket
import shutil
import json
from urllib.parse import urlparse
import datetime
import importlib.util
import AutoDetectPrice
import asyncio
import sys

#TODO remove private tracks enabled, messaging, automatic price finder algorithm


# Default intervals and debug flags
DEBUG = True
delay_seconds = 0 # delay scanning for debug mode in seconds

# Path to the guild configuration file
CONFIG_PATH = "config/guild_config.json"

# Loads the guild configuration from JSON file
def load_guild_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

# Saves the guild configuration to JSON file
def save_guild_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

# Retrieves a specific setting for a guild
def get_guild_setting(guild_id, key, default=None):
    config = load_guild_config()
    return config.get(str(guild_id), {}).get(key, default)

# Sets a specific setting for a guild
def set_guild_setting(guild_id, key, value, guild_name=None):
    config = load_guild_config()
    if str(guild_id) not in config:
        config[str(guild_id)] = {}
    config[str(guild_id)][key] = value
    if guild_name:
        config[str(guild_id)]["server_name"] = guild_name
    save_guild_config(config)

# Setup debug data file if in debug mode
time.sleep(1)
if DEBUG:
    lh.log("Debug mode is enabled. Prices will now be written to the debug json file.", "warn")
    if not os.path.exists("Data/debug_data.json"):
        shutil.copyfile("data/data.json", "data/debug_data.json")
else:
    if os.path.exists("Data/debug_data.json"):
        os.remove("Data/debug_data.json")

# Load environment variables
load_dotenv()

# Get Discord bot token from environment
try:
    discordBotKey = os.getenv("discordBotToken")
except Exception as e:
    lh.log(f"Error: {e}", "error")

# Custom Discord bot client class
class Client(commands.Bot):
    # Called when the bot is ready and online
    async def on_ready(self):
        lh.log(f"Logged in as {self.user}!", "success")
        lh.log("Bot is online.", "log")
        self.guild_config = load_guild_config()
        try:
            lh.log("Synching global commands", "log")
            synced = await self.tree.sync()
            lh.log(f"Synced {len(synced)} commands globally.", "success")
            for guild in self.guilds:
                await self.tree.sync(guild=guild)
        except Exception as e:
            lh.log(e, "error")
        # Only delay if DEBUG is True
        if DEBUG:
            lh.log(f"DEBUG mode: delaying start of scrapers by {delay_seconds} seconds...", "warn")
            await asyncio.sleep(delay_seconds)
        for guild in self.guilds:
            await self.start_guild_tasks(guild)
        # Start a single background task for private trackers
        self.loop.create_task(self.private_trackers_task())

    # Called when the bot joins a new guild
    async def on_guild_join(self, guild):
        guild_id = str(guild.id)
        set_guild_setting(guild_id, "channel_id", None, guild.name)
        set_guild_setting(guild_id, "checkin_interval", 12)
        set_guild_setting(guild_id, "scan_interval", 1)
        lh.log(f"Bot added to new guild: {guild_id}. Default config created.", "log")
        try:
            await self.tree.sync(guild=guild)
            lh.log(f"Commands synced for guild {guild_id}.", "log")
        except Exception as e:
            lh.log(f"Error syncing commands for guild {guild_id}: {e}", "error")

    # Called when the bot is removed from a guild
    async def on_guild_remove(self, guild):
        guild_id = str(guild.id)
        config = load_guild_config()
        if guild_id in config:
            del config[guild_id]
            save_guild_config(config)
            lh.log(f"Bot removed from guild: {guild_id}. Config deleted.", "log")

    # Starts periodic tasks for a guild
    async def start_guild_tasks(self, guild):
        guild_id = str(guild.id)
        config = load_guild_config()
        channel_id = config.get(guild_id, {}).get("channel_id")
        checkin_interval = config.get(guild_id, {}).get("checkin_interval", 12)
        scan_interval = config.get(guild_id, {}).get("scan_interval", 1)
        if channel_id:
            channel = self.get_channel(channel_id)
            if channel:
                self.loop.create_task(self.guild_checkin_task(guild, channel, checkin_interval))
                self.loop.create_task(self.guild_price_check_task(guild, channel, scan_interval))

    # Periodic check-in task for a guild
    async def guild_checkin_task(self, guild, channel, interval):
        while True:
            lh.log(f"Checkin for guild {guild.id}", "log")
            if not DEBUG:
                log_channel_id = get_guild_setting(str(guild.id), "log_channel_id")
                log_channel = self.get_channel(log_channel_id) if log_channel_id else channel
                await log_channel.send(f"@Pricewatch is still running! Last check was at {time.strftime('%H:%M:%S', time.localtime())}")
            next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=interval)
            await discord.utils.sleep_until(next_run)

    # Periodic price check task for a guild
    async def guild_price_check_task(self, guild, channel, interval):
        while True:
            lh.log(f"Price check for guild {guild.id}", "log")
            changed_prices_global = await PriceTracker.CheckGlobalTrackers(DEBUG, str(guild.id), discord_notify=notify_selector_issue)
            pricewatch_role = discord.utils.get(channel.guild.roles, name="Pricewatch")
            pricewatch_mention = pricewatch_role.mention if pricewatch_role else "@Pricewatch"
            if changed_prices_global:
                # Only ping once if multiple prices changed
                if DEBUG:
                    mention = "Pricewatch"
                else:
                    mention = pricewatch_mention
                message_lines = []
                for price in changed_prices_global:
                    if price is None:
                        message_lines.append("Price could not be retrieved for one of the items. Item might be sold out.")
                    elif price['New price'] is None:
                        message_lines.append(f"Name: {price['name']} OLD price: {price['Old price']} --> NEW price: Sold out or selector changed")
                    else:
                        message_lines.append(f"Name: {price['name']} OLD price: {price['Old price']} --> NEW price {price['New price']}")
                message = f"{mention} - The following global prices have changed:\n" + "\n".join(message_lines)
                await channel.send(message)
            next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=interval)
            await discord.utils.sleep_until(next_run)

    # New: Single background task for private trackers
    async def private_trackers_task(self):
        interval = 1  # Default interval in hours, can be made configurable
        while True:
            lh.log("Private tracker scan (single task for all guilds)", "log")
            changed_prices_private = await PriceTracker.CheckPrivateTrackers(DEBUG, discord_notify=notify_selector_issue)
            if changed_prices_private:
                # Send DM to users for changed private trackers
                for price in changed_prices_private:
                    if price is None:
                        continue
                    user_id = price.get('user_id')
                    if user_id:
                        try:
                            user = await self.fetch_user(user_id)
                            # Remove tracker name update, do not overwrite item name with username
                            dm_message = f"Your tracker '{price['name']}' changed price: OLD price: {price['Old price']} --> NEW price {price['New price']}"
                            await user.send(dm_message)
                            lh.log(f"DM sent to user_id {user_id}", "success")
                        except Exception as e:
                            lh.log(f"Failed to DM user_id {user_id}: {e}", "error")
                    else:
                        lh.log(f"No user_id found for tracker {price['name']}", "error")
            next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=interval)
            await discord.utils.sleep_until(next_run)

class ConfirmPriceView(discord.ui.View):
    def __init__(self, timeout=30):
        super().__init__(timeout=timeout)
        self.value = None
        self.interaction = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.interaction = interaction
        self.stop()
        await interaction.response.edit_message(content="✅ Price confirmed. Tracker added.", view=None)

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.interaction = interaction
        self.stop()
        await interaction.response.edit_message(content="? Tracker not added. Please add it manually.", view=None)

# Set up Discord bot intents and client
intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="/", intents=intents)

# Notification callback for selector issues
async def notify_selector_issue(tracker, user_id=None, guild_id=None):
    # For private trackers, user_id is set
    if user_id:
        try:
            user = await client.fetch_user(user_id)
            await user.send(
                f"?? Price for '{tracker['name']}' could not be found. "
                "The item might be sold out or the selector has changed. "
                "Please update the selector or let the bot know if the item is on sale."
            )
        except Exception as e:
            lh.log(f"Failed to notify user {user_id}: {e}", "error")
    # For global trackers, notify all admins in the guild
    elif guild_id:
        try:
            guild = client.get_guild(int(guild_id))
            if guild:
                admin_members = [m for m in guild.members if m.guild_permissions.administrator]
                for admin in admin_members:
                    try:
                        await admin.send(
                            f"?? Global tracker '{tracker['name']}' in '{guild.name}' could not find a price. "
                            "The item might be sold out or the selector has changed. "
                            "Please update the selector or let the bot know if the item is on sale."
                        )
                    except Exception as e:
                        lh.log(f"Failed to notify admin {admin.id} in guild {guild_id}: {e}", "error")
        except Exception as e:
            lh.log(f"Failed to notify admins for guild {guild_id}: {e}", "error")

# Represents a tracked website for price monitoring
class TrackedWebsite:
    def __init__(self, Id, Url, CurrentPrice):
        self.id = Id
        self.url = Url
        self.currentPrice = CurrentPrice

# Validates a URL for tracking (checks format and public IP)
def isValidUrl(URL):
    if not (validators.url(URL) and URL.startswith(("http://", "https://"))):
        return False
    try:
        parsed = urlparse(URL)
        hostname = parsed.hostname
        if hostname is None:
            return False
        ip = None
        try:
            ip = socket.gethostbyname(hostname)
        except Exception:
            return False
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_multicast:
            return False
    except Exception:
        return False
    return True

# Returns the display name for a Discord user
def get_user_display(user):
    username = user.name
    discriminator = getattr(user, 'discriminator', None)
    if discriminator and discriminator != 0:
        return f"{username}#{discriminator}"
    else:
        return username

def get_known_selectors(url):
    domain = urlparse(url).netloc.replace('www.', '')
    try:
        with open('selector_data.json', 'r') as f:
            selector_data = json.load(f)
        return selector_data.get(domain, [])
    except Exception:
        return []

# Command: Show all global tracked prices
@client.tree.command(name="pricetrackglobal", description="Return list of tracked prices for all global trackers")
async def priceTrackGlobal(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be run in a server, not in DMs.",
            ephemeral=True
        )
        return
    lh.log(f"{get_user_display(interaction.user)} ran the pricetrackglobal command.", "log")
    lh.log("Starting pricetrackglobal command.", "log")
    try:
        await interaction.response.send_message("Processing global tracked prices. One moment...")
        msg = await interaction.original_response()
        lh.log("Scraping global prices", "log")
        guild_id = str(interaction.guild.id)
        lh.log(guild_id, "log")
        prices = Scraper.getAllPrices(DEBUG, False, guild_id)
        lh.log_done
        message = ""
        lh.log("Creating message", "log")
        for price_object in prices:
            message += f"\nID: {price_object['id']} Name: {price_object['name']} - Prices: {price_object['price']}"
        lh.log_done
        MAX_MESSAGE_LENGTH = 2000
        if not message.strip():
            lh.log("No prices could be retrieved for global trackers.", "warn")
            await msg.edit(content="? No prices could be retrieved for global trackers.")
        elif len(message) > MAX_MESSAGE_LENGTH:
            from io import StringIO
            file = discord.File(fp=StringIO(message), filename="tracked_prices_global.txt")
            lh.log("Sending message as file due to length", "log")
            await msg.edit(content="?? The list of global tracked prices is too long for a message. See the attached file:", attachments=[file])
        else:
            lh.log("Sending message", "log")
            await msg.edit(content=message)
        lh.log_done
    except Exception as e:
        lh.log(f"Error in pricetrackglobal: {str(e)}", "error")
        await interaction.followup.send("An error occurred while processing your request.")

# Command: Show all current trackers (global and user)
@client.tree.command(name="showalltracks", description="Return list of all current trackers and their URL's")
async def showAllTracks(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("? Only administrators can run this command.")
        return
    lh.log(f"{get_user_display(interaction.user)} ran the showcurrenttracks command.", "log")
    lh.log("Starting showalltracks command.", "log")
    lh.log("Loading json data", "log")
    await interaction.response.send_message("Processing current trackers. One moment...")
    msg = await interaction.original_response()
    guild_id = str(interaction.guild.id)
    global_tracks = JsonHandler.getAllJsonData(guild_id)
    user_tracks = JsonHandler.getAllJsonData()
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
        await msg.edit(content="?? The list of current trackers is too long for a message. See the attached file:", attachments=[file])
    else:
        lh.log("Sending message as text", "log")
        await msg.edit(content=message)
    lh.log_done

# Command: Show all tracks for the current user
@client.tree.command(name="showmytracks", description="Show all your tracked items")
async def showMyTracks(interaction: discord.Interaction):
    lh.log(f"{get_user_display(interaction.user)} ran the showMytracks command.", "log")
    await interaction.response.send_message("Processing your tracks. One moment...")
    msg = await interaction.original_response()
    user_id = str(interaction.user.id)
    user_tracks = JsonHandler.getUserTrackers(user_id)
    if not user_tracks:
        await msg.edit(content="You have no tracks yet.")
        return
    display_name = get_user_display(interaction.user)
    message = f"Tracks for {display_name}:\n"
    for data in user_tracks:
        message += f"ID: {data['id']} | Name: {data['name']} | URL: {data['url']}\n"
    MAX_MESSAGE_LENGTH = 2000
    if len(message) > MAX_MESSAGE_LENGTH:
        from io import StringIO
        file = discord.File(fp=StringIO(message), filename="my_tracks.txt")
        await msg.edit(content="?? Your list of tracks is too long for a message. See the attached file:", attachments=[file])
    else:
        await msg.edit(content=message)

# Command: Add a new global tracker
@client.tree.command(name="addglobaltracker", description="Adds a new global tracker to the list")
async def addGlobalTracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    if interaction.guild is None or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ This command can only be used by server administrators in a server channel.",
            ephemeral=True
        )
        return
    lh.log(f"{get_user_display(interaction.user)} ran the addglobaltracker command.", "log")
    lh.log("Starting addglobaltracker command.", "log")
    await interaction.response.send_message("Checking JavaScript requirements. One moment...")
    msg = await interaction.original_response()
    guild_id = str(interaction.guild.id)
    if isValidUrl(url):
        js_required = False
        found_price = None
        known_selectors = get_known_selectors(url)
        selectors = [css_selector] + [s for s in known_selectors if s != css_selector]
        try:
            html_text = requests.get(url, timeout=5).text
            soup = BeautifulSoup(html_text, "lxml")
            price_element = None
            active_selector = None
            for sel in selectors:
                price_element = soup.select_one(sel)
                if price_element:
                    active_selector = sel
                    break
            if price_element:
                found_price = price_element.get_text(strip=True)
            js_required = price_element is None
        except requests.exceptions.Timeout:
            lh.log(f"Timeout checking JS requirement for {url}", "error")
            js_required = True
            await msg.edit(content=f"⚠️ Timeout while checking {url}. Assuming JavaScript is required.")
        except Exception as e:
            lh.log(f"Error checking JS requirement: {e}", "error")
            js_required = True
        if found_price:
            view = ConfirmPriceView()
            await msg.edit(content=f"Is this the correct price for **{name}**? `{found_price}`", view=view)
            timeout = await view.wait()
            if view.value is True:
                new_tracker = {"name": name, "url": url, "selectors": selectors, "active_selector": active_selector, "currentPrice": found_price, "js": js_required}
                JsonHandler.addTracker(new_tracker, guild_id)
                return
            elif view.value is False:
                return
            else:
                await interaction.followup.send("⏰ No response. Please add the tracker manually.")
                return
        # If no price found, fall back to manual
        new_tracker = {"name": name, "url": url, "selectors": selectors, "active_selector": None, "currentPrice": "0", "js": js_required}
        JsonHandler.addTracker(new_tracker, guild_id)
        await msg.edit(content=f"✅ Now tracking globally: {name} (JavaScript required: {js_required})")
    else:
        await msg.edit(content="❌ Invalid url!")

# Command: Add a new private tracker for the user
@client.tree.command(name="addprivatetrackermanual", description="Adds a new private tracker to your list")
async def addPrivateTracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    lh.log(f"{get_user_display(interaction.user)} ran the addprivatetracker command.", "log")
    lh.log("Starting addprivatetracker command.", "log")
    user_id = str(interaction.user.id)
    await interaction.response.send_message("Checking JavaScript requirements. One moment...")
    msg = await interaction.original_response()
    if isValidUrl(url):
        js_required = False
        found_price = None
        known_selectors = get_known_selectors(url)
        selectors = [css_selector] + [s for s in known_selectors if s != css_selector]
        try:
            html_text = requests.get(url, timeout=10).text
            soup = BeautifulSoup(html_text, "lxml")
            price_element = None
            active_selector = None
            for sel in selectors:
                price_element = soup.select_one(sel)
                if price_element:
                    active_selector = sel
                    break
            if price_element:
                found_price = price_element.get_text(strip=True)
            js_required = price_element is None
        except requests.exceptions.Timeout:
            lh.log(f"Timeout checking JS requirement for {url}", "error")
            js_required = True
            await msg.edit(content=f"?? Timeout while checking {url}. Assuming JavaScript is required.")
        except Exception as e:
            lh.log(f"Error checking JS requirement: {e}", "error")
            js_required = True
        if found_price:
            view = ConfirmPriceView()
            await msg.edit(content=f"Is this the correct price for **{name}**? `{found_price}`", view=view)
            timeout = await view.wait()
            if view.value is True:
                new_tracker = {"name": name, "url": url, "selectors": selectors, "active_selector": active_selector, "currentPrice": found_price, "js": js_required}
                JsonHandler.addUserTracker(user_id, new_tracker)
                return
            elif view.value is False:
                return
            else:
                await interaction.followup.send("? No response. Please add the tracker manually.")
                return
        # If no price found, fall back to manual
        new_tracker = {"name": name, "url": url, "selectors": selectors, "active_selector": None, "currentPrice": "0", "js": js_required}
        JsonHandler.addUserTracker(user_id, new_tracker)
        await msg.edit(content=f"? Now tracking for you: {name} (JavaScript required: {js_required})")
    else:
        await msg.edit(content="? Invalid url!")

# Command: Remove a tracker by its ID
@client.tree.command(name="removetracker", description="Deletes a tracker by its id")
async def removeTracker(interaction: discord.Interaction, id: int):
    await interaction.response.defer()
    lh.log(f"{get_user_display(interaction.user)} ran the removeTracker command.", "log")
    lh.log("Starting removeTracker command.", "log")
    lh.log("Getting data from data.json", "log")
    user_id = str(interaction.user.id)

    # If in DM, only allow removal of user's own private trackers
    if interaction.guild is None:
        result = JsonHandler.removeUserTracker(user_id, id)
        if result:
            await interaction.followup.send(f"✅ Your private tracker with ID {id} has been removed.", suppress_embeds=True)
        else:
            await interaction.followup.send("❌ Private tracker not found.", suppress_embeds=True)
        return

    # Guild context: original logic
    guild_id = str(interaction.guild.id)
    global_trackers = JsonHandler.getAllJsonData(guild_id)
    user_trackers_dict = {}
    with open(JsonHandler.get_active_json_path(), "r") as file:
        data = json.load(file)
        user_trackers_dict = data.get('users', {})
    is_global = any(t['id'] == id for t in global_trackers)
    owner = None
    for uid, trackers in user_trackers_dict.items():
        if any(t['id'] == id for t in trackers):
            owner = uid
            break
    lh.log("Checking permissions", "log")
    # Only admins can remove global trackers
    if is_global and not interaction.user.guild_permissions.administrator:
        await interaction.followup.send("❌ Only administrators can remove global trackers.", suppress_embeds=True)
        return
    # Admins can remove any tracker
    if interaction.user.guild_permissions.administrator:
        lh.log("User is administrator" , "log")
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
    # Non-admins can only remove their own private trackers
    if owner == user_id:
        result = JsonHandler.removeUserTracker(user_id, id)
        if result:
            await interaction.followup.send(f"✅ Your private tracker with ID {id} has been removed.", suppress_embeds=True)
        else:
            await interaction.followup.send("❌ Private tracker not found.", suppress_embeds=True)
        return
    await interaction.followup.send("❌ You can only remove your own private trackers.", suppress_embeds=True)

# Command: Set the public channel for notifications
@client.tree.command(name="setpublicchannel", description="Set the public channel for price and tracker updates")
async def set_public_channel(interaction: discord.Interaction):
    if interaction.guild is None or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ This command can only be used by server administrators in a server channel.",
            ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    channel_id = interaction.channel.id
    guild_name = interaction.guild.name
    set_guild_setting(guild_id, "channel_id", channel_id, guild_name)
    await interaction.response.send_message("✅ This channel is now set for public price and tracker notifications.")

# Command: Set the log channel for bot status updates
@client.tree.command(name="setlogchannel", description="Set the log channel for bot status updates (still running messages)")
async def set_log_channel(interaction: discord.Interaction):
    if interaction.guild is None or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ This command can only be used by server administrators in a server channel.",
            ephemeral=True
        )
        return
    guild_id = str(interaction.guild.id)
    channel_id = interaction.channel.id
    guild_name = interaction.guild.name
    set_guild_setting(guild_id, "log_channel_id", channel_id, guild_name)
    await interaction.response.send_message("✅ This channel is now set for bot status updates.")

# Command: Set the check-in interval (hours)
@client.tree.command(name="setcheckininterval", description="Set check-in interval (hours)")
async def set_checkin_interval(interaction: discord.Interaction, interval: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("? Only administrators can set the check-in interval.")
        return
    guild_id = str(interaction.guild.id)
    set_guild_setting(guild_id, "checkin_interval", interval)
    await interaction.response.send_message(f"? Check-in interval set to {interval} hours.")

# Command: Set the scan interval (hours)
@client.tree.command(name="setscaninterval", description="Set scan interval (hours)")
async def set_scan_interval(interaction: discord.Interaction, interval: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("? Only administrators can set the scan interval.")
        return
    guild_id = str(interaction.guild.id)
    set_guild_setting(guild_id, "scan_interval", interval)
    await interaction.response.send_message(f"? Scan interval set to {interval} hours.")
        
# Command: Automatically add a tracker by auto-detecting the price and confirming with the user
@client.tree.command(name="addprivatetracker", description="Adds a new private tracker.")
async def addPrivateTracker(interaction: discord.Interaction, name: str, url: str):
    lh.log(f"{get_user_display(interaction.user)} ran the addprivatetracker command.", "log")
    await interaction.response.send_message("Auto-detecting price. One moment...")
    msg = await interaction.original_response()

    found_price, found_selector = AutoDetectPrice.auto_detect_price(url)
    lh.log(f"Auto-detect found selector: {found_selector}", "log")  # Log found selector

    if found_price and found_selector:
        view = ConfirmPriceView()
        await msg.edit(content=f"Is this the correct price for **{name}**? `{found_price}`", view=view)
        timeout = await view.wait()
        if view.value is True:
            lh.log(f"User confirmed selector: {found_selector}", "success")  # Log confirmation
            user_id = str(interaction.user.id)
            new_tracker = {
                "name": name,
                "url": url,
                "selectors": [found_selector],
                "active_selector": found_selector,
                "currentPrice": found_price,
                "js": False
            }
            JsonHandler.addUserTracker(user_id, new_tracker)
            return
        elif view.value is False:
            lh.log(f"User rejected selector: {found_selector}", "warn")  # Log rejection
            return
        else:
            lh.log(f"User did not respond to selector confirmation: {found_selector}", "warn")  # Log no response
            await interaction.followup.send("? No response. Please add the tracker manually.")
            return
    else:
        lh.log("Auto-detect could not find a price or selector.", "error")  # Log failure
        await msg.edit(content="? Could not auto-detect a price. Please add the tracker manually.")

# Command: Show all global trackers for this guild (admins only)
@client.tree.command(name="showglobaltracks", description="Show all global trackers for this guild (admins only)")
async def showGlobalTracks(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be run in a server, not in DMs.",
            ephemeral=True
        )
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("? Only administrators can run this command.")
        return
    lh.log(f"{get_user_display(interaction.user)} ran the showglobaltracks command.", "log")
    await interaction.response.send_message("Processing global trackers. One moment...")
    msg = await interaction.original_response()
    guild_id = str(interaction.guild.id)
    global_tracks = JsonHandler.getAllJsonData(guild_id)
    if not global_tracks:
        await msg.edit(content="No global trackers found for this guild.")
        return
    message = "Global Trackers:\n"
    for data in global_tracks:
        message += f"ID: {data['id']} | Name: {data['name']} | URL: {data['url']}\n"
    MAX_MESSAGE_LENGTH = 2000
    if len(message) > MAX_MESSAGE_LENGTH:
        from io import StringIO
        file = discord.File(fp=StringIO(message), filename="global_trackers.txt")
        await msg.edit(content="?? The list of global trackers is too long for a message. See the attached file:", attachments=[file])
    else:
        await msg.edit(content=message)

# Error handling for unhandled exceptions
def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    lh.log(f"Unhandled exception: {exc_value}", "error")
    # You can add more actions here (e.g., notify admins, cleanup, etc.)

sys.excepthook = global_exception_handler

# Start the Discord bot
client.run(discordBotKey)
