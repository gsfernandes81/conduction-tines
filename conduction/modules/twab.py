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

FOLLOWABLE_CHANNEL = cfg.followables["twab"]


def weekly_reset_period(now: dt.datetime = None) -> t.Tuple[dt.datetime]:
    now = now or dt.datetime.now(tz=utc) - dt.timedelta(hours=17)
    now = dt.datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=utc)
    start = now - dt.timedelta(days=(now.weekday() - 3) % 7)
    # Ends at the same day and time next week
    end = start + dt.timedelta(days=7)
    return start, end


@tasks.task(m=1, auto_start=True, wait_before_execution=False, pass_app=True)
async def refresh_twab_data(bot: CachedFetchBot) -> None:
    global twab_message_kwargs

    messages = await autocmd.pull_messages_from_channel(
        bot, after=weekly_reset_period()[0], channel_id=FOLLOWABLE_CHANNEL
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
            msg_proto.merge_embed_url_as_embed_image_into_embed(designator=message_no)
            msg_protos.append(msg_proto)
        if not msg_protos:
            msg_protos.append(
                autocmd.MessagePrototype(
                    embeds=(
                        h.Embed(
                            description="No TWAB this week!",
                            color=cfg.embed_default_color,
                        ),
                    )
                )
            )
    except Exception as e:
        utils.discord_error_logger(bot, e)
        raise e

    twab_message_kwargs = utils.accumulate(msg_protos).to_message_kwargs()


@lb.command("twab", "Find out about this weeks twab")
@lb.implements(lb.SlashCommand)
async def eververse_weekly(ctx: lb.Context):
    await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)
    await ctx.respond(**twab_message_kwargs)


def register(bot):
    for command in [
        eververse_weekly,
    ]:
        bot.command(command)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL,
            "twab",
            "TWAB",
            "TWAB auto posts",
        )
    )
