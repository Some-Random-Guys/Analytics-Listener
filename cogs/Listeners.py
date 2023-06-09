from discord.ext import commands, tasks
from backend import log, db_creds
from srg_analytics import DB



class Listeners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = DB(db_creds)

        self.channel_ignores = {}
        self.user_ignores = {}

        self.aliased_users = {}

        self.cached_messages = {}

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Listeners.py Loaded")
        self.cache.start()

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await self.db.edit_message(guild_id=before.guild.id, message_id=before.id, new_content=after.content)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.db.add_guild(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.db.delete_guild(guild.id)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        await self.db.delete_message(guild_id=message.guild.id, message_id=message.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return

        if not self.db.is_connected:
            await self.db.connect()

        # If the message's channel is ignored, return
        try:
            if self.channel_ignores[message.channel.guild.id]:
                if message.channel.id in self.channel_ignores[message.channel.guild.id]:
                    return
        except KeyError:
            pass

        # If the message's author is ignored, return
        try:
            if self.user_ignores[message.channel.guild.id]:
                if message.author.id in self.user_ignores[message.channel.guild.id]:
                    return
        except KeyError:
            pass

        mentions = [str(mention.id) for mention in message.mentions]
        author = message.author.id

        # if message.author.id is an alias, set author to the alias' id
        guild_id = message.channel.guild.id
        if guild_id in self.aliased_users:

            # make a flat list of all aliases
            aliases = [alias for alias_list in self.aliased_users[guild_id].values() for alias in alias_list]

            # if the author is an alias, set author to the alias' id
            if author in aliases:
                for alias, alias_list in self.aliased_users[guild_id].items():
                    if author in alias_list:
                        author = alias
                        break

        msg = tuple(
            [
                message.id, # message_id
                message.channel.id,  # channel_id
                author, # author_id

                message.content,  # message_content

                message.created_at.timestamp(),  # epoch
                message.author.bot,  # is_bot
                len(message.embeds) > 0,  # has_embed
                len(message.attachments),  # num_attachments
                int(message.reference.message_id) if message.reference is not None and type(message.reference.message_id) == int else None,  # ctx_id
                ",".join(mentions) if mentions else None, # mentions

                # reactions with format {emoji_id: (count, [user_ids]), ...}
                # ",".join([f"{reaction.emoji.id}:{reaction.count}:{','.join([str(user.id) for user in reaction.users])}" for reaction in message.reactions]) if message.reactions else None

            ]
        )
        print(msg)

        try:
            await self.db.add_message(guild_id=message.guild.id, data=msg)
            log.debug(f"Added message: {msg}")
        except Exception as e:
            try:
                await self.db.connect()
                await self.db.add_message(guild_id=message.guild.id, data=msg)
            except Exception as e:
                log.error(f"Error while adding message: {e}")

                if not self.cached_messages.get(message.guild.id):
                    self.cached_messages[message.guild.id] = []

                self.cached_messages[message.guild.id].append(msg)

    @tasks.loop(seconds=60)
    async def cache(self):
        # Connect the DB if it isn't already connected
        if not self.db.is_connected:
            await self.db.connect()

        # Attempt to get channel ignores and user ignores
        try:
            self.channel_ignores = await self.db.get_ignore_list("channel")
            self.user_ignores = await self.db.get_ignore_list("user")

            self.aliased_users = await self.db.get_user_aliases()
            log.debug(self.aliased_users)
        except Exception as e:
            log.error(f"Error while fetching cache: {e}")

        # Attempt to add cached messages to the DB
        if self.cached_messages == {}:
            return

        try:
            for guild_id in self.cached_messages:
                await self.db.add_messages_bulk(guild_id=guild_id, data=self.cached_messages[guild_id])

                log.info(f"Added {len(self.cached_messages[guild_id])} cached messages to guild {guild_id}")
                self.cached_messages[guild_id] = []

        except Exception as e:
            log.error(f"Error while adding cached messages: {e}")



    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        raise error


async def setup(client):
    await client.add_cog(Listeners(client))
