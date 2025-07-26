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

checkinInterval = 12
scanInterval= 1
DEBUG = False  
time.sleep(1)
if DEBUG:
    lh.log("Debug mode is enabled. Prices will not be written to the json file.", "warn")

load_dotenv()


try:
    discordBotKey = os.getenv("discordBotToken")
    guildID = os.getenv("guildID")
    channelID = int(os.getenv("channelID"))
except:
    print(f"Error: {Exception}")


class Client(commands.Bot):

    async def on_ready(self):
        channel = self.get_channel(channelID)
        print(f"loggen on as {self.user}!")

        if not self.hourly_price_check.is_running():
            self.hourly_price_check.start()
        
        try:
            lh.log("Synching guild commands", "log")
            guild = discord.Object(id=guildID)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild: {guild.id}")
        except Exception as e:
            print(e)
        if DEBUG:
            await channel.send("DEBUG mode enabled")
    
    @tasks.loop(hours=checkinInterval)
    async def hourly_checkin(self):
        channel = self.get_channel(channelID)
        if channel is None:
            print("Channel not found!")
            return
        lh.log("Starting checkin", "log")
        await channel.send(f"@Pricewatch is still running! Last check was at {time.strftime('%H:%M:%S', time.localtime())}")
        lh.log_done

    @tasks.loop(hours=scanInterval)
    async def hourly_price_check(self):
   
        channel = self.get_channel(channelID)

        if channel is None:
            print("Channel not found!")
            return

        lh.log("Starting hourly price check", "log")
        changed_prices = PriceTracker.CheckPrices(DEBUG)

        if changed_prices:
            message = "@Pricewatch prices have changed!\nChanged prices are:\n"

            for price in changed_prices:
                if price == None:
                    message += "Price could not be retrieved for one of the items. Item might be sold out.\n"
                else:
                    message += f"Name: {price['name']} OLD price: {price['Old price']} --> NEW price {price['New price']}\n"

            await channel.send(message)


    @hourly_price_check.before_loop
    async def before_hourly_check(self):
        await self.wait_until_ready()


class TrackedWebsite:
    def __init__(self, Id, Url, CurrentPrice):
        self.id = Id
        self.url = Url
        self.currentPrice = CurrentPrice


intents = discord.Intents.default()
intents.message_content = True
GuildObject = discord.Object(id=guildID)
client = Client(command_prefix="/", intents=intents)




def isValidUrl(URL):
    return validators.url(URL) and URL.startswith(("http://", "https://"))


@client.tree.command(name="pricetrack", description="Return list of tracked prices", guild=GuildObject)
async def priceTrack(interaction: discord.Interaction):

    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the priceTrack command.", "log")
    lh.log("Starting priceTrack command.", "log")

    try:
        await interaction.response.defer()

        lh.log("Scraping prices", "log")
        prices = Scraper.getAllPrices(DEBUG)
        lh.log_done

        message = ""
        lh.log("Creating message", "log")
        for price_object in prices:
            message += f"\nName: {price_object['name']} - Prices: {price_object['price']}"
        lh.log_done

        lh.log("Sending message", "log")
        await interaction.followup.send(message)
        lh.log_done

    except Exception as e:
        lh.log(f"Error in pricetrack: {str(e)}", "error")
        await interaction.followup.send("An error occurred while processing your request.")


@client.tree.command(name="showcurrenttracks", description="Return list of all current trackers and their URL's", guild=GuildObject)
async def showCurrentTracks(interaction: discord.Interaction):
    
    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the showcurrenttracks command.", "log")
    lh.log("Starting showcurrenttracks command.", "log")
    

    lh.log("Loading json data", "log")
    loaded_data = JsonHandler.getAllJsonData()
    lh.log_done

    # Build the message content
    message = "Current Trackers:\n"
    for data in loaded_data:
        message += f"ID: {data['id']} | Name: {data['name']} | URL: {data['url']}\n"
    # Convert message string into a file
    from io import StringIO
    file = discord.File(fp=StringIO(message), filename="current_trackers.txt")
    lh.log("Sending message as file", "log")
    await interaction.response.send_message(content="📄 Here is the list of current trackers:", file=file)
    lh.log_done

@client.tree.command(name="addtracker", description="Adds a new tracker to the list", guild=GuildObject)
async def addtracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    await interaction.response.defer()
    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the addtracker command.", "log")
    lh.log("Starting addtracker command.", "log")

    if isValidUrl(url):
        try:
            html_text = requests.get(url, timeout=20).text  # Increased timeout
            soup = BeautifulSoup(html_text, "lxml")
            price_element = soup.select_one(css_selector)
            js_required = price_element is None
        except requests.exceptions.Timeout:
            lh.log(f"Timeout checking JS requirement for {url}", "error")
            js_required = True
            await interaction.followup.send(f"⚠️ Timeout while checking {url}. Assuming JavaScript is required.")
        except Exception as e:
            lh.log(f"Error checking JS requirement: {e}", "error")
            js_required = True
        new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": "0", "js": js_required}
        JsonHandler.addTracker(new_tracker)
        await interaction.followup.send(f"✅ Now tracking: {name} (JavaScript required: {js_required})")
    else:
        await interaction.followup.send("❌ Invalid url!")

@client.tree.command(name="removetracker", description="Deletes a tracker by it's id", guild=GuildObject)
async def removeTracker(interaction: discord.Interaction, id: int):
    await interaction.response.defer()

    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the removeTracker command.", "log")
    lh.log("Starting removeTracker command.", "log")
    try:
        JsonHandler.removeTracker(id)
        await interaction.followup.send(f"✅ Tracker with ID {id} has been removed.", suppress_embeds=True)
    except Exception as e:
        lh.log(f"Error removing tracker: {str(e)}", "error")
        await interaction.followup.send("❌ An error occurred while trying to remove the tracker.", suppress_embeds=True)

@client.tree.command(name="setcheckininterval", description="Sets the interval at which the bot lets you know its still running. (Hours)", guild=GuildObject)
async def setCheckinInterval(interaction: discord.Interaction, interval_in_hours: int):
    await interaction.response.defer()
    checkinInterval = interval_in_hours
    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} set the checkin interval to {checkinInterval} hours.", "log")
    await interaction.followup.send(f"✅ Checkin interval has been set to {checkinInterval} hours.")

@client.tree.command(name="setscaninterval", description="Sets the interval at which the bot scans the prices to check for changes. (Hours)", guild=GuildObject)
async def setScanInterval(interaction: discord.Interaction, interval_in_hours: int):
    await interaction.response.defer()
    scanInterval = interval_in_hours
    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} set the scan interval to {scanInterval} hours.", "log")
    await interaction.followup.send(f"✅ Scan interval has been set to {scanInterval} hours.")
        

client.run(discordBotKey)
