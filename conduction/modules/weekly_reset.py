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
import regex as re
from hmessage import HMessage as MessagePrototype

from .. import cfg, utils
from ..nav import NavigatorView, NavPages
from .autoposts import autopost_command_group, follow_control_command_maker

REFERENCE_DATE = dt.datetime(2023, 7, 18, 17, tzinfo=dt.timezone.utc)

FOLLOWABLE_CHANNEL = cfg.followables["weekly_reset"]

# This regex finds the lines that start with
# "From" or "Till"
# These lines are intended to be removed in code
rgx_find_from_till_text = re.compile(r"\n\*\*(From|Till)\*\*[^\n]*")


class ResetPages(NavPages):
    def preprocess_messages(
        self, messages: t.List[MessagePrototype | h.Message]
    ) -> MessagePrototype:
        msg_proto = (
            utils.accumulate([MessagePrototype.from_message(m) for m in messages])
            .merge_content_into_embed()
            .merge_attachements_into_embed(default_url=cfg.default_url)
        )

        # Remove duplicate From/Till text from polarity embed
        for embed in msg_proto.embeds:
            embed.description = rgx_find_from_till_text.sub("", embed.description or "")

        return msg_proto


async def on_start(event: h.StartedEvent):
    global reset_pages
    reset_pages = await ResetPages.from_channel(
        event.app,
        FOLLOWABLE_CHANNEL,
        history_len=12,
        period=dt.timedelta(days=7),
        reference_date=REFERENCE_DATE,
    )


@lb.command("weekly", "Weekly reset")
@lb.implements(lb.SlashCommandGroup)
async def weekly_reset_command_group(ctx: lb.Context):
    pass


@weekly_reset_command_group.child
@lb.command("reset", "Find out about this weeks reset")
@lb.implements(lb.SlashSubCommand)
async def weekly_reset_command(ctx: lb.Context):
    navigator = NavigatorView(pages=reset_pages)
    await navigator.send(ctx.interaction)


def register(bot):
    bot.command(weekly_reset_command_group)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL,
            "weekly_reset",
            "Weekly reset",
            "Weekly reset auto posts",
        )
    )
