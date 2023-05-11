from discord.ext import commands, tasks
from backend import log, db_creds
from srg_analytics import DB
from srg_analytics.schemas import DataTemplate


class Listeners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = DB(db_creds)

        self.channel_ignores = []
        self.user_ignores = []

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Listeners.py Loaded")
        self.cache_ignores.start()

        # sync commands

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        pass  # todo

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.db.add_guild(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.db.delete_guild(guild.id)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if await self.db.is_ignored(channel_id=message.channel.id, user_id=message.author.id):
            return

        await self.db.delete_message(guild_id=message.guild.id, message_id=message.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        # If the message's channel is ignored, or the author is ignored, return
        if message.channel.id in self.channel_ignores or message.author.id in self.user_ignores:
            return

        mentions = [str(mention.id) for mention in message.mentions]

        msg = DataTemplate(
            author_id=message.author.id,
            is_bot=message.author.bot,
            has_embed=len(message.embeds) > 0,
            channel_id=message.channel.id,
            epoch=message.created_at.timestamp(),
            num_attachments=len(message.attachments),
            mentions=",".join(mentions) if mentions else None,
            ctx_id=int(message.reference.message_id) if message.reference else None,
            message_content=message.content,
            message_id=message.id
        )

        await self.db.add_message(guild_id=message.guild.id, data=msg)

    @tasks.loop(seconds=60)
    async def cache_ignores(self):
        self.channel_ignores = await self.db.get_ignore_list("channel")
        self.user_ignores = await self.db.get_ignore_list("user")


async def setup(client):
    await client.add_cog(Listeners(client))
