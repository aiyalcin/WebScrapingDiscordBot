import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import validators
import json
from WebScraper import Scraper

load_dotenv()

try:
    discordBotKey = os.getenv("discordBotToken")
except:
    print(f"Error: {Exception}")


class Client(commands.Bot):
    async def on_ready(self):
        print(f"loggen on as {self.user}!")
        try:
            guild = discord.Object(id=1371213848518070282)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild: {guild.id}")
        except:
            print(f"Could not sync commands to guild with guild id {guild.id}")
    async def on_message(self, message):
        if message.author == "Boja.":
            await message.channel.send("Homo")


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
    prices = Scraper.getAllPrices()
    message = ""
    for price_object in prices:
        message += f"\nName: {price_object['name']} - Prices: {price_object['price']}"
    await interaction.response.send_message(message)


@client.tree.command(name="showcurrenttracks", description="Return list of all current trackers and their URL's", guild=GUILD_ID)
async def showcurrenttracks(interaction: discord.Interaction):
    loaded_data = Scraper.getAllJsonData()
    message = ""
    for data in loaded_data:
        message += f"\nID: {data['id']} Name: {data['name']} - Website URL: {data['url']}"
    await interaction.response.send_message(message)


@client.tree.command(name="addtracker", description="Add a price tracker by supplying a site URL", guild=GUILD_ID)
async def addtracker(interaction: discord.Interaction, addtracker:str):
    if isValidUrl(addtracker):
        Scraper.addTracker(addtracker)
        await interaction.response.send_message(f"✅ Now tracking: {addtracker}")
    else:
        await interaction.response.send_message("❌ Invalid url!")


client.run(discordBotKey)
