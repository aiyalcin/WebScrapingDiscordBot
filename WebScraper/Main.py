import discord
from discord.ext import commands
import PriceTracker
from dotenv import load_dotenv
import os
import validators
import Scraper
from discord.ext import tasks
import JsonHandler
import LogHandler
load_dotenv()

try:
    discordBotKey = os.getenv("discordBotToken")
    guild_ID = os.getenv("guildID")
    channelID = os.getenv("channelID")
except:
    print(f"Error: {Exception}")


class Client(commands.Bot):
    async def on_ready(self):
        print(f"loggen on as {self.user}!")
        self.hourly_price_check.start()
        try:
            guild = discord.Object(id=GUILD_ID)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild: {guild.id}")
        except:
            print(f"Could not sync commands to guild with guild id {guild.id}")

    @tasks.loop(hours=12)
    async def hourly_price_check(self):
        # Get the channel where you want to send messages
        channel = self.get_channel(channelID)

        if channel is None:
            print("Channel not found!")
            return

        changed_prices = PriceTracker.CheckPrices()

        if changed_prices:
            message = "@Pricewatch prices have changed!\nChanged prices are:\n"
            for price in changed_prices:
                message += f"Name: {price['name']} OLD price: {price['Old price']} --> NEW price {price['New price']}\n"
            await channel.send(message)
        else:
            await channel.send("Check in. Prices have not changed. Use /showcurrenttracks for a list of currently tracked items")

    @hourly_price_check.before_loop
    async def before_hourly_check(self):
        await self.wait_until_ready()  # Wait until the bot is logged in


class TrackedWebsite:
    def __init__(self, Id, Url, CurrentPrice):
        self.id = Id
        self.url = Url
        self.currentPrice = CurrentPrice


intents = discord.Intents.default()
intents.message_content = True
GUILD_ID = discord.Object(id=1371213848518070282)
client = Client(command_prefix="/", intents=intents)




def isValidUrl(URL):
    return validators.url(URL) and URL.startswith(("http://", "https://"))


@client.tree.command(name="pricetrack", description="Return list of tracked prices", guild=GUILD_ID)
async def pricetrack(interaction: discord.Interaction):
    try:
        # Immediately acknowledge the interaction
        await interaction.response.defer()

        LogHandler.log_handler("Scraping prices", "log")
        prices = Scraper.getAllPrices()
        LogHandler.log_handler("Scraping prices - DONE", "log")

        message = ""
        LogHandler.log_handler("Creating message", "log")
        for price_object in prices:
            message += f"\nName: {price_object['name']} - Prices: {price_object['price']}"
        LogHandler.log_handler("Creating message - DONE", "log")

        LogHandler.log_handler("Sending message", "log")
        # Use followup.send instead of interaction.response.send_message
        await interaction.followup.send(message)
        LogHandler.log_handler("Sending message - DONE", "log")

    except Exception as e:
        LogHandler.log_handler(f"Error in pricetrack: {str(e)}", "error")
        await interaction.followup.send("An error occurred while processing your request.")


@client.tree.command(name="showcurrenttracks", description="Return list of all current trackers and their URL's", guild=GUILD_ID)
async def showcurrenttracks(interaction: discord.Interaction):
    LogHandler.log_handler("Loading json data", "log")
    loaded_data = JsonHandler.getAllJsonData()
    LogHandler.log_handler("Loading json data - DONE", "log")
    message = ""
    LogHandler.log_handler("Creating message", "log")
    for data in loaded_data:
        message += f"\nID: {data['id']} Name: {data['name']} - Website URL: {data['url']}"
    LogHandler.log_handler("Creating message - DONE", "log")
    LogHandler.log_handler("Sending message", "log")
    await interaction.response.send_message(message)
    LogHandler.log_handler("Sending message - DONE", "log")


@client.tree.command(name="addtracker", description="Add a price tracker by supplying a site URL", guild=GUILD_ID)
async def addtracker(interaction: discord.Interaction, addtracker:str):
    if isValidUrl(addtracker):
        Scraper.addTracker(addtracker)
        await interaction.response.send_message(f"✅ Now tracking: {addtracker}")
    else:
        await interaction.response.send_message("❌ Invalid url!")

client.run(discordBotKey)
