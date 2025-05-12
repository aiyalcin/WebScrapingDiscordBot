from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os

load_dotenv()

discordBotKey = os.getenv("discordBotToken")

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
        print(f"Message from {message.author}: {message.content}")
        if message.content.startswith('/pricetrack'):
            await message.channel.send('test: Tracking prices')


intents = discord.Intents.default()
intents.message_content = True
GUILD_ID = discord.Object(id=1371213848518070282)
client = Client(command_prefix="/", intents=intents)
@client.tree.command(name="pricetrack", description="Return list of tracked gear prices", guild=GUILD_ID)
async def pricetrack(interaction: discord.Interaction):
    await interaction.response.send_message("Test: pricetrack")


client.run(discordBotKey)
