import discord
from discord.ext import commands
import PriceTracker
from dotenv import load_dotenv
import os
import validators
import Scraper
from discord.ext import tasks
import JsonHandler
import LogHandler as lh
load_dotenv()

try:
    discordBotKey = os.getenv("discordBotToken")
    guildID = os.getenv("guildID")
    channelID = os.getenv("channelID")
except:
    print(f"Error: {Exception}")


class Client(commands.Bot):

    async def on_ready(self):

        print(f"loggen on as {self.user}!")
        
        self.hourly_price_check.start()
        
        try:
            guild = discord.Object(id=guildID)
            synced = await self.tree.sync(guild=guild)

            print(f"Synced {len(synced)} commands to guild: {guild.id}")
        except:
            print(f"Could not sync commands to guild with guild id {guild.id}")

    @tasks.loop(hours=12)
    async def hourly_price_check(self):
   
        channel = self.get_channel(channelID)

        if channel is None:
            print("Channel not found!")
            return

        changed_prices = PriceTracker.CheckPrices()

        if changed_prices:
            message = "@Pricewatch prices have changed!\nChanged prices are:\n"

            for price in changed_prices:
                if price == None:
                    message += "Price could not be retrieved for one of the items. Item might be sold out.\n"
                else:
                    message += f"Name: {price['name']} OLD price: {price['Old price']} --> NEW price {price['New price']}\n"

            await channel.send(message)
        else:
            await channel.send("Check in. Prices have not changed. Use /showcurrenttracks for a list of currently tracked items")

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


@client.tree.command(name="priceTrack", description="Return list of tracked prices", guild=GuildObject)
async def priceTrack(interaction: discord.Interaction):

    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the priceTrack command.", "log")
    lh.log("Starting priceTrack command.", "log")

    try:
        await interaction.response.defer()

        lh.log("Scraping prices", "log")
        prices = Scraper.getAllPrices()
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


@client.tree.command(name="showCurrentTracks", description="Return list of all current trackers and their URL's", guild=GuildObject)
async def showCurrentTracks(interaction: discord.Interaction):
    
    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the showcurrenttracks command.", "log")
    lh.log("Starting showcurrenttracks command.", "log")
    

    lh.log("Loading json data", "log")
    loaded_data = JsonHandler.getAllJsonData()
    lh.log_done

    message = ""
    lh.log("Creating message", "log")
    for data in loaded_data:
        message += f"\nID: {data['id']} Name: {data['name']} - Website URL: {data['url']}"
    lh.log_done

    lh.log("Sending message", "log")
    await interaction.response.send_message(message)
    lh.log_done

@client.tree.command(name="=addTracker", description="Return list of all current trackers and their URL's", guild=GuildObject)
async def addtracker(interaction: discord.Interaction, name: str, url: str, css_selector: str):
    
    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the addtracker command.", "log")
    lh.log("Starting addtracker command.", "log")

    if isValidUrl(url):
        new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": 0}
        JsonHandler.addTracker(new_tracker)

        await interaction.response.send_message(f"✅ Now tracking: {name}")

    else:
        await interaction.response.send_message("❌ Invalid url!")

@client.tree.command(name="=removeTracker", description="Deletes a tracker by it's id", guild=GuildObject)
async def removeTracker(interaction: discord.Interaction, id: int):
    
    lh.log(f"{interaction.user.name}#{interaction.user.discriminator} ran the removeTracker command.", "log")
    lh.log("Starting removeTracker command.", "log")
    try:
        JsonHandler.removeTracker(id)
        await interaction.response.send_message(f"✅ Tracker with ID {id} has been removed.")
    except Exception as e:
        lh.log(f"Error removing tracker: {str(e)}", "error")
        await interaction.response.send_message("❌ An error occurred while trying to remove the tracker.")

    

client.run(discordBotKey)
