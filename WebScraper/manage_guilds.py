import discord
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
discordBotKey = os.getenv("discordBotToken")

class GuildManagerClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}!\n")
        print("Servers the bot is in:")
        for guild in self.guilds:
            print(f"- {guild.name} (ID: {guild.id})")
        print("\nEnter the ID of the server you want the bot to leave, or press Enter to exit.")
        guild_id = input("Guild ID to leave: ").strip()
        if guild_id:
            guild = discord.utils.get(self.guilds, id=int(guild_id))
            if guild:
                await guild.leave()
                print(f"Left guild: {guild.name} (ID: {guild.id})")
            else:
                print("Guild not found.")
        await self.close()

intents = discord.Intents.default()
client = GuildManagerClient(intents=intents)
client.run(discordBotKey)
