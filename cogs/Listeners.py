from discord.ext import commands, tasks
from backend import log, db_creds
from srg_analytics import DB
from srg_analytics.schemas import Message


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
        user_mentions = None if after.raw_mentions == [] else str(after.raw_mentions),
        channel_mentions = None if after.raw_channel_mentions == [] else str(after.raw_channel_mentions),
        role_mentions = None if after.raw_role_mentions == [] else str(after.raw_role_mentions),

        num_attachments = len(after.attachments)
        edit_epoch = after.edited_at.timestamp() if after.edited_at else None

        if self.cached_messages.get(before.guild.id):
            for msg in self.cached_messages[before.guild.id]:
                if msg.id == after.id:
                    msg.content = after.content
                    msg.user_mentions = user_mentions
                    msg.channel_mentions = channel_mentions
                    msg.role_mentions = role_mentions
                    msg.num_attachments = num_attachments
                    msg.edit_epoch = edit_epoch

        else:

            await self.db.edit_message(
                guild_id=before.guild.id, message_id=before.id, content=after.content, user_mentions=user_mentions,
                channel_mentions=channel_mentions, role_mentions=role_mentions, num_attachments=num_attachments,
                edit_epoch=edit_epoch
            )

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.db.add_guild(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # When the bot is removed from a guild, delete all data associated with that guild
        await self.db.delete_guild(guild.id)
        await self.db.execute(f"DELETE FROM `config` WHERE `data1` = {guild.id}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if self.cached_messages.get(message.guild.id):
            for msg in self.cached_messages[message.guild.id]:
                if msg.message_id == message.id:
                    self.cached_messages[message.guild.id].remove(msg)
                    break

        else:
            await self.db.delete_message(guild_id=message.guild.id, message_id=message.id)

    @commands.Cog.listener()
    # # on reaction add
    async def on_raw_reaction_add(self, payload):
        message = await self.client.get_channel(payload.channel_id).fetch_message(payload.message_id)
        guild = self.client.get_guild(payload.guild_id)

        reactions = {}

        for reaction in message.reactions:
            key = reaction.emoji.id if reaction.is_custom_emoji() else reaction.emoji
            reactions[key] = reaction.count

        if self.cached_messages.get(guild.id):
            for msg in self.cached_messages[guild.id]:
                if msg.message_id == payload.message_id:
                    msg.reactions = reactions
                    break

        else:
            while True:
                try:
                    await self.db.execute(f"UPDATE `{guild.id}` SET `reactions` = %s WHERE `message_id` = %s",
                                          (str(reactions), payload.message_id))
                    break
                except Exception as e:
                    print(e)
                    await self.db.connect()

    @commands.Cog.listener()
    # # on reaction remove
    async def on_raw_reaction_remove(self, payload):
        message = await self.client.get_channel(payload.channel_id).fetch_message(payload.message_id)
        guild = self.client.get_guild(payload.guild_id)

        reactions = {}

        for reaction in message.reactions:
            key = reaction.emoji.id if reaction.is_custom_emoji() else reaction.emoji
            reactions[key] = reaction.count

        if reactions == {}:
            reactions = None

        if self.cached_messages.get(guild.id):
            for msg in self.cached_messages[guild.id]:
                if msg.message_id == payload.message_id:
                    msg.reactions = reactions
                    break

        else:
            while True:
                try:
                    await self.db.execute(f"UPDATE `{guild.id}` SET `reactions` = %s WHERE `message_id` = %s",
                                          (str(reactions) if reactions is not None else None, payload.message_id))

                    break
                except Exception as e:
                    print(e)
                    await self.db.connect()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        channel_id = channel.id
        guild_id = channel.guild.id

        # delete all messages in that channel from database
        await self.db.execute(f"DELETE FROM `{guild_id}` WHERE `channel_id` = {channel_id}")

        # delete all messages in that channel from cache
        if self.cached_messages.get(guild_id):
            for msg in self.cached_messages[guild_id]:
                if msg.channel_id == channel_id:
                    self.cached_messages[guild_id].remove(msg)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.is_system():
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

        msg = Message(
            guild_id=message.guild.id,
            message_id=message.id,
            channel_id=message.channel.id,
            author_id=message.author.id,
            aliased_author_id=author,
            message_content=message.content if message.content != "" else None,
            epoch=message.created_at.timestamp(),
            edit_epoch=message.edited_at.timestamp() if message.edited_at is not None else None,
            is_bot=message.author.bot,
            has_embed=message.embeds != [],
            num_attachments=len(message.attachments),
            ctx_id=int(message.reference.message_id) if message.reference is not None and type(
                message.reference.message_id) == int else None,
            user_mentions=None if message.raw_mentions == [] else str(message.raw_mentions),
            channel_mentions=None if message.raw_channel_mentions == [] else str(message.raw_channel_mentions),
            role_mentions=None if message.raw_role_mentions == [] else str(message.raw_role_mentions),
            reactions=None
        )

        try:

            await self.db.add_message(guild_id=message.guild.id, data=msg)
            log.debug(f"Added message: {msg.message_id}")
        except Exception as e:
            try:
                await self.db.connect()
                await self.db.add_message(guild_id=message.guild.id, data=msg)
            except Exception as e:
                log.error(f"Error while adding message: {e}")

                if not self.cached_messages.get(message.guild.id):
                    self.cached_messages[message.guild.id]: list[Message] = []

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
                if not self.cached_messages[guild_id]:
                    continue

                await self.db.add_messages_bulk(guild_id, self.cached_messages[guild_id])

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
