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

import datetime as dt
import typing as t

import hikari as h
import lightbulb as lb
from lightbulb.ext import tasks
from pytz import utc

from .. import cfg, utils
from ..bot import CachedFetchBot
from .autoposts import autopost_command_group, follow_control_command_maker
from . import autocmd

EVERVERSE_WEEKLY = cfg.followables["eververse"]
EVERVERSE_DAILY = cfg.followables["daily_reset"]


def weekly_reset_period(now: dt.datetime = None) -> t.Tuple[dt.datetime]:
    now = now or dt.datetime.now(tz=utc) - dt.timedelta(hours=17)
    now = dt.datetime(now.year, now.month, now.day, 17, 0, 0, tzinfo=utc)
    start = now - dt.timedelta(days=(now.weekday() - 1) % 7)
    # Ends at the same day and time next week
    end = start + dt.timedelta(days=7)
    return start, end


def daily_reset_period(now: dt.datetime = None) -> t.Tuple[dt.datetime]:
    now = now or dt.datetime.now(tz=utc) - dt.timedelta(hours=17)
    now = dt.datetime(now.year, now.month, now.day, 17, 0, 0, tzinfo=utc)
    start = now
    end = start + dt.timedelta(days=1)
    return start, end


@tasks.task(m=1, auto_start=True, wait_before_execution=False, pass_app=True)
async def refresh_eververse_weekly_data(bot: CachedFetchBot) -> None:
    global eververse_weekly_message_kwargs

    messages = await autocmd.pull_messages_from_channel(
        bot, after=weekly_reset_period()[0], channel_id=EVERVERSE_WEEKLY
    )

    # Merge all the images into the last embed for each message
    # and all the content into the first embed for each message
    msg_protos: autocmd.MessagePrototype = []
    try:
        for message_no, message in enumerate(messages):
            # Merge content into the first embed if it exists
            # else make a new embed and do the same
            msg_proto = autocmd.MessagePrototype.from_message(message)
            msg_proto.merge_content_into_embed(0)
            msg_proto.merge_attachements_into_embed(designator=message_no)
            msg_protos.append(msg_proto)
    except Exception as e:
        utils.discord_error_logger(bot, e)
        raise e

    eververse_weekly_message_kwargs = utils.accumulate(msg_protos).to_message_kwargs()


@tasks.task(m=1, auto_start=True, wait_before_execution=False, pass_app=True)
async def refresh_eververse_daily_data(bot: CachedFetchBot) -> None:
    global eververse_daily_message_kwargs

    messages = await autocmd.pull_messages_from_channel(
        bot, after=daily_reset_period()[0], channel_id=EVERVERSE_DAILY
    )

    # Merge all the images into the last embed for each message
    # and all the content into the first embed for each message
    msg_protos: autocmd.MessagePrototype = []
    try:
        for message_no, message in enumerate(messages):
            # Merge content into the first embed if it exists
            # else make a new embed and do the same
            msg_proto = autocmd.MessagePrototype.from_message(message)
            msg_proto.merge_content_into_embed(0)
            msg_proto.merge_attachements_into_embed(designator=message_no)
            msg_protos.append(msg_proto)
    except Exception as e:
        utils.discord_error_logger(bot, e)
        raise e

    eververse_daily_message_kwargs = utils.accumulate(msg_protos).to_message_kwargs()


@lb.command("eververse", "Find out about the eververse items")
@lb.implements(lb.SlashCommandGroup)
async def eververse_group(ctx: lb.Context):
    pass


@eververse_group.child
@lb.command("weekly", "Find out about this weeks eververse items")
@lb.implements(lb.SlashSubCommand)
async def eververse_weekly(ctx: lb.Context):
    await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)
    await ctx.respond(**eververse_weekly_message_kwargs)


@eververse_group.child
@lb.command("daily", "Find out about today's eververse offer")
@lb.implements(lb.SlashSubCommand)
async def eververse_daily(ctx: lb.Context):
    await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)
    await ctx.respond(**eververse_daily_message_kwargs)


def register(bot):
    for command in [
        eververse_group,
    ]:
        bot.command(command)

    autopost_command_group.child(
        follow_control_command_maker(
            EVERVERSE_WEEKLY,
            "eververse_weekly",
            "Eververse weekly",
            "Eververse weekly auto posts",
        )
    )

    autopost_command_group.child(
        follow_control_command_maker(
            EVERVERSE_DAILY,
            "eververse_daily",
            "Eververse daily",
            "Eververse daily auto posts",
        )
    )
