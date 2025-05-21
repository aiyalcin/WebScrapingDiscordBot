import discord
from discord.ext import commands
import JsonHandler
import Scraper
import PriceTracker
import validators
import json
import os

bot_config = {}

try:
    with open("config.json", "r") as f:
        bot_config = json.load(f)
except:
    pass

class SlashCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="setbotchannel", description="Configureer het kanaal voor meldingen")
    async def setbotchannel(self, interaction: discord.Interaction):
        bot_config["guild_id"] = interaction.guild.id
        bot_config["channel_id"] = interaction.channel.id

        with open("config.json", "w") as f:
            json.dump(bot_config, f)

        await interaction.response.send_message(f"✅ Bot channel set to {interaction.channel.mention}")
        await self.bot.tree.sync(guild=interaction.guild)

    @discord.app_commands.command(name="addtracker", description="Add a price tracker")
    async def addtracker(self, interaction: discord.Interaction, name: str, url: str, css_selector: str):
        if validators.url(url) and url.startswith(("http://", "https://")):
            new_tracker = {"name": name, "url": url, "selector": css_selector, "currentPrice": 0}
            JsonHandler.addTracker(new_tracker)
            await interaction.response.send_message(f"✅ Now tracking: {name}")
        else:
            await interaction.response.send_message("❌ Invalid url!")

    @discord.app_commands.command(name="showcurrenttracks", description="Return list of all current trackers")
    async def showcurrenttracks(self, interaction: discord.Interaction):
        loaded_data = JsonHandler.getAllJsonData()
        message = ""
        for data in loaded_data:
            message += f"\nID: {data['id']} Name: {data['name']} - Website URL: {data['url']}"
        await interaction.response.send_message(message)

    @discord.app_commands.command(name="pricetrack", description="Return list of tracked prices")
    async def pricetrack(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            prices = Scraper.getAllPrices()
            message = ""
            for price_object in prices:
                message += f"\nName: {price_object['name']} - Prices: {price_object['price']}"
            await interaction.followup.send(message)
        except Exception as e:
            await interaction.followup.send("An error occurred while processing your request.")
