import discord
from discord.ext import commands
import PriceTracker
from dotenv import load_dotenv
import os
from discord.ext import tasks
import LogHandler as logHandler
import asyncio
import json
from SlashCommands import SlashCommands
setup_event = asyncio.Event()
bot_config = {}
load_dotenv()


class Client(commands.Bot):
    def __init__(self, *args, **kwargs):
        if 'command_prefix' not in kwargs:
            kwargs['command_prefix'] = '!'
        if 'intents' not in kwargs:
            kwargs['intents'] = discord.Intents.all()

        super().__init__(
            help_command=None,
            **kwargs
        )
        self._setup_complete = False

        # Add the command properly
        self.add_command(commands.Command(
            name='setbotchannel',
            callback=self.setbotchannel,
            help='Sets the bot channel'
        ))

        try:
            with open("config.json", "r") as f:
                global bot_config
                bot_config = json.load(f)
        except:
            pass

    async def setbotchannel(self, ctx):
        """Sets the bot's channel for all communications"""
        bot_config["guild_id"] = ctx.guild.id
        bot_config["channel_id"] = ctx.channel.id

        with open("config.json", "w") as f:
            json.dump(bot_config, f)

        await ctx.send(f"✅ Bot channel set to {ctx.channel.mention}")
        setup_event.set()
        await self.sync_commands_to_guild()

    async def setup_hook(self):
        # Add the command before loading cogs
        self.add_command(self.setbotchannel)
        await self.add_cog(SlashCommands(self))

        if "guild_id" in bot_config:
            guild = discord.Object(id=bot_config["guild_id"])
            await self.tree.sync(guild=guild)
            logHandler.log(f"Synced commands to guild: {guild.id}", "log")

    async def sync_commands_to_guild(self):
        """Helper method to sync commands to the configured guild"""
        guild = discord.Object(id=bot_config["guild_id"])
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logHandler.log(f"Synced commands to guild: {guild.id}", "log")

    async def on_ready(self):
        if not self._setup_complete and not os.getenv("setupDone"):
            self._setup_complete = True
            logHandler.log(f"Logged on as {self.user}!", "log")

            # Explicitly add the command

            logHandler.log("Prefix command registered. Use !setbotchannel in your server.", "log")
            logHandler.log("Please use !setbotchannel in your server to configure the bot.", "log")
        else:
            # Normal operation
            if "guild_id" in bot_config:
                target_guild = self.get_guild(bot_config["guild_id"])
                if not target_guild:
                    logHandler.log("Error: Bot is not in the configured guild!", "error")
                    return

                # Sync commands to specific guild
                try:
                    await self.sync_commands_to_guild()
                except Exception as e:
                    logHandler.log(f"Error syncing guild commands: {str(e)}", "error")
            else:
                logHandler.log("No guild configured yet!", "warning")

            logHandler.log(f"Logged on as {self.user}!", "log")
            self.hourly_price_check.start()

    @tasks.loop(hours=12)
    async def hourly_price_check(self):
        if "channel_id" not in bot_config:
            return

        channel = self.get_channel(bot_config["channel_id"])
        if channel is None:
            return

        changed_prices = PriceTracker.CheckPrices()
        if changed_prices:
            message = "@Pricewatch prices have changed!\nChanged prices are:\n"
            for price in changed_prices:
                message += f"Name: {price['name']} OLD price: {price['Old price']} --> NEW price {price['New price']}\n"
            await channel.send(message)
        else:
            await channel.send("Check in. Prices have not changed.")

    @hourly_price_check.before_loop
    async def before_hourly_check(self):
        await self.wait_until_ready()


async def setup():
    logHandler.log("Bot setup started.", "log")
    token = input("Enter bot token: ").strip('"')

    with open(".env", "w") as f:
        f.write(f"discordBotToken={token}\n")
    os.environ["setupDone"] = "true"

    logHandler.log("Waiting for !setbotchannel command...", "log")
    # Create client without duplicate prefix
    client = Client(intents=discord.Intents.all())

    try:
        await client.start(token)
    except Exception as e:
        logHandler.log(f"Failed to start bot: {str(e)}", "error")
    finally:
        await client.close()

if __name__ == "__main__":
    try:
        discordBotKey = os.getenv("discordBotToken")
        if discordBotKey:
            client = Client(intents=discord.Intents.all())
            client.run(discordBotKey)
        else:
            asyncio.run(setup())
    except Exception as e:
        logHandler.log(f"Fatal error: {str(e)}", "error")