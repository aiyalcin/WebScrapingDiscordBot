import discord
from discord.ext import commands
import PriceTracker
from dotenv import load_dotenv
import os
import Scraper
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
import AutoDetectPrice
import asyncio

DEBUG = False
initialWaitTimeGuild = 1
initialWaitTimePrivate = 1

if DEBUG:
    lh.log("Debug mode is enabled. Prices will now be written to the debug json file.", "warn")
    if not os.path.exists("Data/debug_data.json"):
        shutil.copyfile("data/data.json", "data/debug_data.json")
else:
    if os.path.exists("Data/debug_data.json"):
        os.remove("Data/debug_data.json")

load_dotenv()

try:
    discordBotKey = os.getenv("discordBotToken")
except Exception as e:
    lh.log(f"Error: {e}", "error")


class Client(commands.Bot):
    async def on_ready(self):
        lh.log(f"Logged in as {self.user}!", "success")
        lh.log("Bot is online.", "log")
        self.guild_config = JsonHandler.load_guild_config()
        try:
            lh.log("Synching global commands", "log")
            synced = await self.tree.sync()
            lh.log(f"Synced {len(synced)} commands globally.", "success")
            for guild in self.guilds:
                await self.tree.sync(guild=guild)
        except Exception as e:
            lh.log(e, "error")
        for guild in self.guilds:
            await self.start_guild_tasks(guild)
        self.loop.create_task(self.private_trackers_task())

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

    async def on_guild_remove(self, guild):
        guild_id = str(guild.id)
        config = JsonHandler.load_guild_config()
        if guild_id in config:
            del config[guild_id]
            JsonHandler.save_guild_config(config)
            lh.log(f"Bot removed from guild: {guild_id}. Config deleted.", "log")

    async def start_guild_tasks(self, guild):
        guild_id = str(guild.id)
        config = JsonHandler.load_guild_config()
        channel_id = config.get(guild_id, {}).get("channel_id")
        checkin_interval = config.get(guild_id, {}).get("checkin_interval", 12)
        scan_interval = config.get(guild_id, {}).get("scan_interval", 1)
        if channel_id:
            channel = self.get_channel(channel_id)
            if channel:
                self.loop.create_task(self.guild_checkin_task(guild, channel, checkin_interval))
                self.loop.create_task(self.guild_price_check_task(guild, channel, scan_interval))

    async def guild_checkin_task(self, guild, channel, interval):
        while True:
            lh.log(f"Checkin for guild {guild.id}", "log")
            if not DEBUG:
                log_channel_id = get_guild_setting(str(guild.id), "log_channel_id")
                log_channel = self.get_channel(log_channel_id) if log_channel_id else channel
                await log_channel.send(f"@Pricewatch is still running! Last check was at {time.strftime('%H:%M:%S', time.localtime())}")
            next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=interval)
            await discord.utils.sleep_until(next_run)

    async def guild_price_check_task(self, guild, channel, interval):
        await asyncio.sleep(initialWaitTimeGuild)
        while True:
            lh.log(f"Price check for guild {guild.id}", "log")
            changed_prices_global = await PriceTracker.CheckGlobalTrackers(DEBUG, str(guild.id), discord_notify=notify_selector_issue)
            pricewatch_role = discord.utils.get(channel.guild.roles, name="Pricewatch")
            pricewatch_mention = pricewatch_role.mention if pricewatch_role else "@Pricewatch"
            if changed_prices_global:
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

    async def private_trackers_task(self):
        await asyncio.sleep(initialWaitTimePrivate)
        interval = 1
        while True:
            lh.log("Private tracker scan (single task for all guilds)", "log")
            changed_prices_private = await PriceTracker.CheckPrivateTrackers(DEBUG, discord_notify=notify_selector_issue)
            if changed_prices_private:
                for price in changed_prices_private:
                    if price is None:
                        continue
                    user_id = price.get('user_id')
                    if user_id:
                        try:
                            user = await self.fetch_user(user_id)
                            JsonHandler.update_user_tracker_name(user_id, price['id'], user.name)
                            embed = discord.Embed(
                                title=f"Price Change for '{price['name']}'",
                                description="Your tracker has detected a price change!",
                                color=discord.Color.dark_green()
                            )
                            embed.add_field(name="Old Price", value=f"**{price['Old price']}**", inline=True)
                            embed.add_field(name="New Price", value=f"**{price['New price']}**", inline=True)
                            embed.set_footer(text="Price Watcher Bot")
                            await user.send(embed=embed)
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

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.interaction = interaction
        self.stop()
        await interaction.response.edit_message(content="❌ Tracker not added. Please add it manually.", view=None)

intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="/", intents=intents)

def get_guild_setting(guild_id, key, default=None):
    config = JsonHandler.load_guild_config()
    return config.get(str(guild_id), {}).get(key, default)

def set_guild_setting(guild_id, key, value, guild_name=None):
    config = JsonHandler.load_guild_config()
    if str(guild_id) not in config:
        config[str(guild_id)] = {}
    config[str(guild_id)][key] = value
    if guild_name:
        config[str(guild_id)]["server_name"] = guild_name
    JsonHandler.save_guild_config(config)

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

def get_user_display(user):
    username = user.name
    discriminator = getattr(user, 'discriminator', None)
    if discriminator and discriminator != 0:
        return f"{username}#{discriminator}"
    else:
        return username

def is_valid_tracker_name(name):
    if not isinstance(name, str):
        return False
    if not (3 <= len(name) <= 50):
        return False
    if not all(c.isalnum() or c in " -_" for c in name):
        return False
    return True

async def notify_selector_issue(tracker, user_id=None, guild_id=None):
    if user_id:
        try:
            user = await client.fetch_user(user_id)
            await user.send(
                f"❌ Price for '{tracker['name']}' could not be found. "
                "The item might be sold out or the selector has changed. "
                "Please update the selector or let the bot know if the item is on sale."
            )
        except Exception as e:
            lh.log(f"Failed to notify user {user_id}: {e}", "error")
    elif guild_id:
        try:
            guild = client.get_guild(int(guild_id))
            if guild:
                admin_members = [m for m in guild.members if m.guild_permissions.administrator]
                for admin in admin_members:
                    try:
                        await admin.send(
                            f"❌ Global tracker '{tracker['name']}' was checked but no price was found!"
                            "The item might be sold out or the selector has changed. "
                            "Please update the selector or re add the tracker."
                        )
                    except Exception as e:
                        lh.log(f"Failed to notify admin {admin.id} in guild {guild_id}: {e}", "error")
        except Exception as e:
            lh.log(f"Failed to notify admins for guild {guild_id}: {e}", "error")

@client.tree.command(name="showalltracks", description="(Admin only)")
async def showAllTracks(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can run this command.")
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
        await msg.edit(content="❌ The list of current trackers is too long for a message. See the attached file:", attachments=[file])
    else:
        lh.log("Sending message as text", "log")
        await msg.edit(content=message)
    lh.log_done

@client.tree.command(name="showmytrackers", description="Show all your tracked items")
async def showMyTrackers(interaction: discord.Interaction):
    lh.log(f"{get_user_display(interaction.user)} ran the showmytrackers command.", "log")
    await interaction.response.send_message("Processing your tracks. One moment...")
    msg = await interaction.original_response()
    user_id = str(interaction.user.id)
    user_tracks = JsonHandler.getUserTrackers(user_id)
    if not user_tracks:
        await msg.edit(content="❌ You have no trackers yet.")
        return
    user_name = get_user_display(interaction.user)
    message = f"Trackers for {user_name}:\n"
    for data in user_tracks:
        message += f"ID: {data['id']} | Name: {data['name']} | URL: {data['url']}\n"
    MAX_MESSAGE_LENGTH = 2000
    if len(message) > MAX_MESSAGE_LENGTH:
        from io import StringIO
        file = discord.File(fp=StringIO(message), filename="my_trackers.txt")
        await msg.edit(content="❌ Your list of trackers is too long for a message. See the attached file:", attachments=[file])
    else:
        await msg.edit(content=message)

@client.tree.command(name="addglobaltracker", description="(Admin only)")
async def addGlobalTracker(interaction: discord.Interaction, name: str, url: str):
    if not is_valid_tracker_name(name):
        await interaction.response.send_message("❌ Invalid tracker name! Name must be 3-50 characters and only contain letters, numbers, spaces, dashes, or underscores.")
        return
    try:
        guild_id = str(interaction.guild.id)
    except Exception:
        await interaction.response.send_message("❌ This command can only be run in a server (guild).", ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can add global trackers.", ephemeral=True)
        return
    await interaction.response.send_message("Auto-detecting price. One moment...")
    msg = await interaction.original_response()
    if not isValidUrl(url):
        await msg.edit(content="❌ Invalid URL!")
        return
    price, selector, js_used = AutoDetectPrice.auto_detect_price(url)
    if price and selector:
        view = ConfirmPriceView()
        await msg.edit(content=f"Is this the correct price for **{name}**? `{price}`", view=view)
        timeout = await view.wait()
        if view.value is True:
            js_required = True
            try:
                if Scraper.selector_works_without_js(url, selector, price):
                    js_required = False
            except Exception:
                pass
            # Buffer new selector if domain is not in selector_data
            domain = AutoDetectPrice.get_domain(url)
            selector_data = JsonHandler.get_selector_data()
            if domain not in selector_data:
                JsonHandler.add_selector_to_buffer(domain, selector, js_required)
            new_tracker = {
                "name": name,
                "url": url,
                "selector": selector,
                "currentPrice": price,
                "js": js_required
            }
            result = JsonHandler.addTracker(new_tracker, guild_id)
            if result is False:
                await interaction.followup.send("❌ This server has reached the maximum number of global trackers allowed.", ephemeral=True)
                return
            await interaction.followup.send(f"✅ Global tracker added.")
            return
        elif view.value is False:
            await interaction.followup.send("❌ Tracker not added. Please add manually.")
            return
        else:
            await interaction.followup.send("❌ No response. Please add the tracker manually.")
            return
    else:
        await msg.edit(content="❌ Could not auto-detect a price. Please add the tracker manually.")

@client.tree.command(name="addprivatetracker", description="Adds a new private tracker.")
async def addPrivateTracker(interaction: discord.Interaction, name: str, url: str):
    if not is_valid_tracker_name(name):
        await interaction.response.send_message("❌ Invalid tracker name! Name must be 3-50 characters and only contain letters, numbers, spaces, dashes, or underscores.")
        return
    lh.log(f"{get_user_display(interaction.user)} ran the addtrackerauto command.", "log")
    await interaction.response.send_message("Auto-detecting price. One moment...")
    msg = await interaction.original_response()
    user_id = str(interaction.user.id)
    if not isValidUrl(url):
        await msg.edit(content="❌ Invalid URL!")
        return
    price, selector, js_used = AutoDetectPrice.auto_detect_price(url)
    if price and selector:
        view = ConfirmPriceView()
        await msg.edit(content=f"Is this the correct price for **{name}**? `{price}`", view=view)
        timeout = await view.wait()
        if view.value is True:
            js_required = True
            try:
                if Scraper.selector_works_without_js(url, selector, price):
                    js_required = False
            except Exception:
                pass
            # Buffer new selector if domain is not in selector_data
            domain = AutoDetectPrice.get_domain(url)
            selector_data = JsonHandler.get_selector_data()
            if domain not in selector_data:
                JsonHandler.add_selector_to_buffer(domain, selector, js_required)
            new_tracker = {
                "name": name,
                "url": url,
                "selector": selector,
                "currentPrice": price,
                "js": js_required
            }
            result = JsonHandler.addUserTracker(user_id, new_tracker)
            if result is False:
                await interaction.followup.send("❌ You have reached the maximum number of private trackers allowed.", ephemeral=True)
                return
            await interaction.followup.send(f"✅ Tracker added.")
            return
        elif view.value is False:
            await interaction.followup.send("❌ Tracker not added. Please add manually.")
            return
        else:
            await interaction.followup.send("❌ No response. Please add the tracker manually.")
            return
    else:
        await msg.edit(content="❌ Could not auto-detect a price. Please add the tracker manually.")


@client.tree.command(name="addprivatetrackermanual", description="Adds a new private tracker to your list using css selector")
async def addPrivateTracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    lh.log(f"{get_user_display(interaction.user)} ran the addprivatetracker command.", "log")
    lh.log("Starting addprivatetracker command.", "log")
    user_id = str(interaction.user.id)
    await interaction.response.send_message("Checking JavaScript requirements. One moment...")
    msg = await interaction.original_response()
    if isValidUrl(url):
        js_required = False
        found_price = None
        try:
            html_text = requests.get(url, timeout=10).text
            soup = BeautifulSoup(html_text, "lxml")
            price_element = soup.select_one(css_selector)
            if price_element:
                found_price = price_element.get_text(strip=True)
            js_required = price_element is None
        except requests.exceptions.Timeout:
            lh.log(f"Timeout checking JS requirement for {url}", "error")
            js_required = True
            await msg.edit(content=f"✅ Timeout while checking {url}. Assuming JavaScript is required.")
        except Exception as e:
            lh.log(f"Error checking JS requirement: {e}", "error")
            js_required = True
        if found_price:
            view = ConfirmPriceView()
            await msg.edit(content=f"Is this the correct price for **{name}**? `{found_price}`", view=view)
            timeout = await view.wait()
            if view.value is True:
                new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": found_price, "js": js_required}
                JsonHandler.addUserTracker(user_id, new_tracker)
                return
            elif view.value is False:
                return
            else:
                await interaction.followup.send("❌ No response. Please add the tracker manually.")
                return
        new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": "0", "js": js_required}
        JsonHandler.addUserTracker(user_id, new_tracker)
        await msg.edit(content=f"✅ Now tracking for you: {name} (JavaScript required: {js_required})")
    else:
        await msg.edit(content="❌ Invalid url!")

@client.tree.command(name="removetracker", description="Deletes a tracker by its id")
async def removeTracker(interaction: discord.Interaction, id: int):
    await interaction.response.defer()
    lh.log(f"{get_user_display(interaction.user)} ran the removeTracker command.", "log")
    lh.log("Starting removeTracker command.", "log")
    lh.log("Checking if command is being ran in guild", "log")
    try:
        guild_id = str(interaction.guild.id)
        lh.log("TRUE Guild id saved in memory", "log")
    except:
        lh.log("FALSE Guild id skipped", "log")
        guild_id = None
    lh.log("Getting user id", "log")
    user_id = str(interaction.user.id)
    lh.log_done()
    lh.log("Loading user and global trackers from data.json", "log")
    with open(JsonHandler.get_active_json_path(), "r") as file:
        data = json.load(file)
    lh.log_done()
    if guild_id is None:
        lh.log("Not in a guild only checking user's own trackers", "log")
        user_trackers = data.get('users', {}).get(user_id, [])
        if any(t['id'] == id for t in user_trackers):
            result = JsonHandler.removeUserTracker(user_id, id)
            if result:
                lh.log(f"Private tracker with ID {id} removed by user {user_id} (DM context)", "success")
                await interaction.followup.send(f"✅ Your private tracker with ID {id} has been removed.", suppress_embeds=True)
            else:
                lh.log(f"Failed to remove tracker with ID {id} for user {user_id} (DM context)", "error")
                await interaction.followup.send("❌ Invalid tracker id.", suppress_embeds=True)
        else:
            lh.log(f"Invalid tracker id {id} for user {user_id} (DM context)", "warn")
            await interaction.followup.send("❌ Invalid tracker id.", suppress_embeds=True)
        return
    global_trackers = data.get('global', {}).get(guild_id, [])
    is_global = any(t['id'] == id for t in global_trackers)
    owner = None
    for uid, trackers in data.get('users', {}).items():
        if any(t['id'] == id for t in trackers):
            owner = uid
            break
    if is_global and not interaction.user.guild_permissions.administrator:
        lh.log(f"User {user_id} tried to remove global tracker {id} without admin rights", "warn")
        await interaction.followup.send("❌ Only administrators can remove global trackers.", suppress_embeds=True)
        return
    if interaction.user.guild_permissions.administrator:
        lh.log("User is administrator" , "log")
        if is_global:
            JsonHandler.removeTracker(id, guild_id)
            lh.log(f"Global tracker with ID {id} has been removed by admin {user_id}", "success")
            await interaction.followup.send(f"✅ Global tracker with ID {id} has been removed by admin.", suppress_embeds=True)
            return
        if owner:
            result = JsonHandler.removeUserTracker(owner, id)
            if result:
                lh.log(f"Private tracker with ID {id} has been removed by admin {user_id}", "success")
                await interaction.followup.send(f"✅ Private tracker with ID {id} has been removed by admin.", suppress_embeds=True)
            else:
                lh.log(f"Admin {user_id} failed to remove private tracker {id} (not found)", "warn")
                await interaction.followup.send("❌ Private tracker not found.", suppress_embeds=True)
            return
        lh.log(f"Admin {user_id} tried to remove invalid tracker id {id}", "warn")
        await interaction.followup.send("❌ Tracker not found.", suppress_embeds=True)
        return
    if owner == user_id:
        result = JsonHandler.removeUserTracker(user_id, id)
        if result:
            lh.log(f"User {user_id} removed their private tracker with ID {id}", "success")
            await interaction.followup.send(f"✅ Your private tracker with ID {id} has been removed.", suppress_embeds=True)
        else:
            lh.log(f"User {user_id} failed to remove their private tracker with ID {id} (not found)", "warn")
            await interaction.followup.send("❌ Private tracker not found.", suppress_embeds=True)
        return
    lh.log(f"User {user_id} tried to remove invalid or unauthorized tracker id {id})", "warn")
    await interaction.followup.send("❌ Invalid tracker id.", suppress_embeds=True)

@client.tree.command(name="setpublicchannel", description="(Admin only)")
async def set_public_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can set the public channel.")
        return
    guild_id = str(interaction.guild.id)
    channel_id = interaction.channel.id
    guild_name = interaction.guild.name
    set_guild_setting(guild_id, "channel_id", channel_id, guild_name)
    await interaction.response.send_message("✅ This channel is now set for public price and tracker notifications.")

@client.tree.command(name="setlogchannel", description="(Admin only)")
async def set_log_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can set the log channel.")
        return
    guild_id = str(interaction.guild.id)
    channel_id = interaction.channel.id
    guild_name = interaction.guild.name
    set_guild_setting(guild_id, "log_channel_id", channel_id, guild_name)
    await interaction.response.send_message("✅ This channel is now set for bot status updates.")

@client.tree.command(name="setcheckininterval", description="(Admin only)")
async def set_checkin_interval(interaction: discord.Interaction, interval: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can set the check-in interval.")
        return
    guild_id = str(interaction.guild.id)
    set_guild_setting(guild_id, "checkin_interval", interval)
    await interaction.response.send_message(f"✅ Check-in interval set to {interval} hours.")

@client.tree.command(name="setscaninterval", description="(Admin only)")
async def set_scan_interval(interaction: discord.Interaction, interval: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can set the scan interval.")
        return
    guild_id = str(interaction.guild.id)
    set_guild_setting(guild_id, "scan_interval", interval)
    await interaction.response.send_message(f"✅ Scan interval set to {interval} hours.")

client.run(discordBotKey)
