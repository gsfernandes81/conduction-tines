# Copyright © 2019-present gsfernandes81

# This file is part of "conduction-tines".

# conduction-tines is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.

# "conduction-tines" is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License along with
# conduction-tines. If not, see <https://www.gnu.org/licenses/>.

import typing as t

import hikari as h
import lightbulb as lb

from .. import cfg
from ..bot import CachedFetchBot
from ..schemas import MirroredChannel

debug_group = lb.command(name="debug", description="Debug group", hidden=True)(
    lb.implements(lb.SlashCommandGroup)(lambda: None)
)


async def get_channels(
    bot: lb.BotApp, guild: h.Guild, prefix: str
) -> t.List[h.GuildChannel]:
    channels = guild.get_channels()
    channels = [
        bot.cache.get_guild_channel(ch) or await bot.rest.fetch_channel(ch)
        for ch in channels
        if not isinstance(ch, h.GuildChannel)
    ]
    channels = filter(lambda ch: ch.name.startswith(prefix), channels)
    return channels


@debug_group.child
@lb.option(
    "prefix",
    "Name prefix to create channels with",
    h.GuildCategory,
    default="test90931-",
)
@lb.option("source", "Source channel", h.GuildChannel)
@lb.command(
    "legacy_follow",
    description="Legacy follow 300 channels",
    pass_options=True,
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def legacy_follow(ctx: lb.Context, source: h.GuildChannel, prefix: str):
    if not ctx.author.id in await ctx.bot.fetch_owner_ids():
        return

    bot: CachedFetchBot = ctx.app
    guild = ctx.get_guild() or await ctx.app.rest.fetch_guild(ctx.guild_id)

    for channel in await get_channels(bot, guild, prefix):
        await MirroredChannel.add_mirror(source.id, channel.id, guild.id, legacy=True)

    await ctx.respond("Done")


@debug_group.child
@lb.option(
    "prefix",
    "Name prefix to create channels with",
    h.GuildCategory,
    default="test90931-",
)
@lb.option("source", "Source channel", h.GuildChannel)
@lb.command(
    "legacy_unfollow",
    description="Legacy follow 300 channels",
    pass_options=True,
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def legacy_unfollow(ctx: lb.Context, source: h.GuildChannel, prefix: str):
    if not ctx.author.id in await ctx.bot.fetch_owner_ids():
        return

    bot: CachedFetchBot = ctx.app
    guild = ctx.get_guild() or await ctx.app.rest.fetch_guild(ctx.guild_id)

    for channel in await get_channels(bot, guild, prefix):
        await MirroredChannel.remove_mirror(source.id, channel.id, legacy=True)

    await ctx.respond("Done")


@debug_group.child
@lb.option("number", "Number of channels to create", int)
@lb.option(
    "prefix",
    "Name prefix to create channels with",
    h.GuildCategory,
    default="test90931-",
)
@lb.command(
    "create_channels",
    description="Legacy follow 300 channels",
    pass_options=True,
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def create_channels_in_category(ctx: lb.Context, prefix: str, number: int):
    if not ctx.author.id in await ctx.bot.fetch_owner_ids():
        return

    guild = ctx.get_guild() or await ctx.app.rest.fetch_guild(ctx.guild_id)

    for num in range(number):
        await guild.create_text_channel(f"{prefix}{num}")

    await ctx.respond("Done")


@debug_group.child
@lb.option(
    "prefix",
    "Name prefix to create channels with",
    h.GuildCategory,
    default="test90931-",
)
@lb.command(
    "delete_channels",
    description="Legacy follow 300 channels",
    pass_options=True,
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def delete_channels_in_category(ctx: lb.Context, prefix: str):
    if not ctx.author.id in await ctx.bot.fetch_owner_ids():
        return

    bot: lb.BotApp = ctx.app
    guild = ctx.get_guild() or await ctx.app.rest.fetch_guild(ctx.guild_id)

    for channel in await get_channels(bot, guild, prefix):
        await channel.delete()

    await ctx.respond("Done")


def register(bot: lb.BotApp):
    if not cfg.test_env:
        return

    bot.command(debug_group)
