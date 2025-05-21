import discord
from discord.ext import commands
import PriceTracker
from dotenv import load_dotenv
import os
import validators
import Scraper
from discord.ext import tasks
import JsonHandler
import LogHandler as logHandler
import asyncio
setup_event = asyncio.Event()
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
load_dotenv()


try:
    discordBotKey = os.getenv("discordBotToken")

except:
    logHandler.log(f"Could not get bot token from .env file. \n"
                    f"Please check that you have a valid .env file and your token is saved in format: "
                    f"discordBotToken = '<your token here>'", "error")


class Client(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define the setbotchannel command
        @self.command(name="setbotchannel")
        async def set_bot_channel(ctx):
            global bot_config
            bot_config["guild_id"] = ctx.guild.id
            bot_config["channel_id"] = ctx.channel.id

            await ctx.send(
                f"✅ Bot channel set to {ctx.channel.mention}\n"
                f"Guild ID: `{ctx.guild.id}`"
            )
            setup_event.set()

    async def on_ready(self):
        if not os.getenv("setupDone"):
            await setup()

        if "guild_id" in bot_config:
            target_guild = self.get_guild(bot_config["guild_id"])
            if not target_guild:
                logHandler.log("Error: Bot is not in the configured guild!", "error")
                return
        else:
            logHandler.log("No guild configured yet!", "warning")

        logHandler.log(f"Logged on as {self.user}!", "log")
        self.hourly_price_check.start()

        if "guild_id" in bot_config:
            try:
                guild = discord.Object(id=bot_config["guild_id"])
                synced = await self.tree.sync(guild=guild)
                logHandler.log(f"Synced {len(synced)} commands to guild: {guild.id}", "log")
            except Exception as e:
                logHandler.log(f"Could not sync commands to guild: {str(e)}", "error")

    @tasks.loop(hours=12)
    async def hourly_price_check(self):

        channel = self.get_channel(bot_config["channel_id"])

        if channel is None:
            logHandler.log("Channel not found!", "error")
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
GUILD_ID = discord.Object(id=bot_config["guild_id"])
client = Client(command_prefix="/", intents=intents)


@bot.command(name="setbotchannel")
async def set_bot_channel(ctx):
    guild_id = ctx.guild.id  # Get the guild ID
    channel_id = ctx.channel.id  # Get the channel ID

    await ctx.send(f"✅ Bot channel set to {ctx.channel.mention} (Guild ID: `{guild_id}`)")

    # Save guild_id and channel_id (e.g., to a JSON config file)
    import json
    config = {
        "guild_id": guild_id,
        "channel_id": channel_id
    }
    with open("config.json", "w") as f:
        json.dump(config, f)


async def setup():
    logHandler.log("Bot setup started.", "log")
    logHandler.log("Please supply bot token. The token will be saved to a hidden .env file. "
                   "To find the file turn on hidden file view in your file explorer.", "log")
    token = input("$ ")
    logHandler.log("Saving token to .env file", "log")
    try:
        os.putenv("discordBotToken", token)
        logHandler.log_done()
    except:
        logHandler.log(f"Could not save token to env file. {Exception}", "error")
    logHandler.log("Use the /setbotchannel command in discord to add the bot to your desired discord channel. "
                   "The bot will do all of its public messaging in the channel where you run the command. "
                   "If you wish to change the channel, run the command in the new desired channel.", "log")
    logHandler.log("Waiting for discord command", "log")
    bot_task = asyncio.create_task(bot.start(token))
    await setup_event.wait()
    logHandler.log_done()


    logHandler.log("Setup complete!", "log")

    # Keep the bot running
    await bot_task  # Prevents the script from exiting






def isValidUrl(URL):
    return validators.url(URL) and URL.startswith(("http://", "https://"))


@client.tree.command(name="pricetrack", description="Return list of tracked prices", guild=GUILD_ID)
async def pricetrack(interaction: discord.Interaction):
    try:
        # Immediately acknowledge the interaction
        await interaction.response.defer()

        logHandler.log("Scraping prices", "log")
        prices = Scraper.getAllPrices()
        logHandler.log_done()

        message = ""
        logHandler.log("Creating message", "log")
        for price_object in prices:
            message += f"\nName: {price_object['name']} - Prices: {price_object['price']}"
        logHandler.log_done()

        logHandler.log("Sending message", "log")

        await interaction.followup.send(message)
        logHandler.log_done()

    except Exception as e:
        logHandler.log(f"Error in pricetrack: {str(e)}", "error")
        await interaction.followup.send("An error occurred while processing your request.")


@client.tree.command(name="showcurrenttracks", description="Return list of all current trackers and their URL's", guild=GUILD_ID)
async def showcurrenttracks(interaction: discord.Interaction):
    logHandler.log("Loading json data", "log")
    loaded_data = JsonHandler.getAllJsonData()
    logHandler.log_done()
    message = ""
    logHandler.log("Creating message", "log")
    for data in loaded_data:
        message += f"\nID: {data['id']} Name: {data['name']} - Website URL: {data['url']}"
    logHandler.log_done()
    logHandler.log("Sending message", "log")
    await interaction.response.send_message(message)
    logHandler.log_done()


@client.tree.command(name="addtracker", description="Add a price tracker by supplying a name, site URL and css selector", guild=GUILD_ID)
async def addtracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    if isValidUrl(url):
        new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": 0}
        JsonHandler.addTracker(new_tracker)
        await interaction.response.send_message(f"✅ Now tracking: {addtracker}")
    else:
        await interaction.response.send_message("❌ Invalid url!")

client.run(discordBotKey)
