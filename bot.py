import asyncio
import os
import sys
import discord.app_commands
from backend import client, discord_token, log
import discord.utils


# This is what gets run when the bot stars
@client.event
async def on_ready():
    print("Started")
    log.info(f"Bot is ready. Logged in as {client.user}")
    log.info("Ping: " + str(round(client.latency * 1000, 2)) + "ms")


async def on_tree_error(interaction, error):
    if isinstance(error, discord.app_commands.CommandNotFound):
        return
    raise error


client.tree.on_error = on_tree_error


async def load_cogs():
    for file in os.listdir('./cogs'):
        if file.endswith('.py'):
            await client.load_extension(f'cogs.{file[:-3]}')


asyncio.run(load_cogs())

# Run the actual bot
try:
    client.run(discord_token)
except discord.LoginFailure:
    log.critical("Invalid Discord Token. Please check your config file.")
    sys.exit()
except Exception as err:
    log.critical(f"Error while connecting to Discord. Error: {err}")
    sys.exit()
