import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import validators

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


intents = discord.Intents.default()
intents.message_content = True
GUILD_ID = discord.Object(id=1371213848518070282)
client = Client(command_prefix="/", intents=intents)

def isValidUrl(URL):
    return validators.url(URL) and URL.startswith(("http://", "https://"))

@client.tree.command(name="pricetrack", description="Return list of tracked gear prices", guild=GUILD_ID)
async def pricetrack(interaction: discord.Interaction):
    await interaction.response.send_message("Test: pricetrack")

@client.tree.command(name="addtracker", description="Add a price tracker by supplying a site URL", guild=GUILD_ID)
async def addtracker(interaction: discord.Interaction, addtracker:str):
    if isValidUrl(addtracker):
        await interaction.response.send_message(addtracker)
    else:
        await interaction.response.send_message("Invalid url!")


client.run(discordBotKey)
