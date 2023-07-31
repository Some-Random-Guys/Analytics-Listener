import configparser
import sys
import discord
import logging
from discord.ext import commands
from colorlog import ColoredFormatter
from srg_analytics import DbCreds
import warnings

warnings.filterwarnings("ignore")
intents = discord.Intents()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.reactions = True




# Initializing the logger
def colorlogger(name: str = 'my-discord-bot') -> logging.log:
    logger = logging.getLogger(name)
    stream = logging.StreamHandler()

    stream.setFormatter(ColoredFormatter("%(reset)s%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s"))
    logger.addHandler(stream)
    return logger  # Return the logger


log = colorlogger()

# Loading config.ini
config = configparser.ConfigParser()

try:
    config.read('./data/config.ini')
except Exception as e:
    log.critical("Error reading the config.ini file. Error: " + str(e))
    sys.exit()

# Getting variables from config.ini
try:
    # Getting the variables from `[general]`
    log_level: str = config.get('general', 'log_level')

    # Getting the variables from `[secret]`
    discord_token: str = config.get('secret', 'discord_token')
    db_host: str = config.get('secret', 'db_host')
    db_port: int = config.getint('secret', 'db_port')
    db_user: str = config.get('secret', 'db_user')
    db_password: str = config.get('secret', 'db_password')
    db_name: str = config.get('secret', 'db_name')

except Exception as err:
    log.critical("Error getting variables from the config file. Error: " + str(err))
    sys.exit()

# Set the logger's log level to the one in the config file
if log_level.upper().strip() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    log.setLevel(log_level.upper().strip())
else:
    log.setLevel("INFO")
    log.warning(f"Invalid log level `{log_level.upper().strip()}`. Defaulting to INFO.")

# Initializing the client
client = commands.Bot(intents=intents, command_prefix="!")  # Setting prefix

db_creds: DbCreds = DbCreds(db_host, db_port, db_user, db_password, db_name)

guild_join_message = discord.Embed(
    title="Thank you for adding me to your server!",
    description="I am a bot that can help you with your server's analytics.")
guild_join_message.add_field(name="How to use me?",
                                value="To use me, you can use the `!help` command to see all the commands I have.")
guild_join_message.add_field(name="How to get support?",
                                value="If you need support, you can join my support server [here](https://discord.gg/2YjJ2XV).")
guild_join_message.add_field(name="Get started!",
                                value="Run /admin harvest to start collecting data.")
guild_join_message.add_field(name="Note",
                             value="This bot will save every single message sent in your server, for analytics purposes. If you do not want this, please remove the bot from your server."
                                   "Kicking the bot from the server will delete all data collected by the bot.")