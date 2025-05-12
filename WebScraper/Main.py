import discord
from discord.ext import commands
import PriceTracker
from dotenv import load_dotenv
import os
import validators
from WebScraper import Scraper
from discord.ext import tasks
import JsonHandler
load_dotenv()

try:
    discordBotKey = os.getenv("discordBotToken")
except:
    print(f"Error: {Exception}")


class Client(commands.Bot):
    async def on_ready(self):
        print(f"loggen on as {self.user}!")
        self.hourly_price_check.start()
        try:
            guild = discord.Object(id=1371213848518070282)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild: {guild.id}")
        except:
            print(f"Could not sync commands to guild with guild id {guild.id}")
    async def on_message(self, message):
        if message.author == "Boja.":
            await message.channel.send("Homo")

    @tasks.loop(hours=12)
    async def hourly_price_check(self):
        # Get the channel where you want to send messages
        channel = self.get_channel(1371577580611960933)  # Replace with actual channel ID

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
    prices = Scraper.getAllPrices()
    message = ""
    for price_object in prices:
        message += f"\nName: {price_object['name']} - Prices: {price_object['price']}"
    await interaction.response.send_message(message)


@client.tree.command(name="showcurrenttracks", description="Return list of all current trackers and their URL's", guild=GUILD_ID)
async def showcurrenttracks(interaction: discord.Interaction):
    loaded_data = JsonHandler.getAllJsonData()
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
