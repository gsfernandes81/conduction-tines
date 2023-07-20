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
from hmessage import HMessage as MessagePrototype

from .. import cfg, utils
from ..nav import NavigatorView, NavPages
from .autoposts import autopost_command_group, follow_control_command_maker

REFERENCE_DATE = dt.datetime(2023, 7, 18, 17, tzinfo=dt.timezone.utc)

EVERVERSE_WEEKLY = cfg.followables["eververse"]


class EVWeeklyPages(NavPages):
    @classmethod
    def preprocess_messages(
        cls, messages: t.List[MessagePrototype | h.Message]
    ) -> MessagePrototype:
        processed_messages = []
        for n, m in enumerate(messages):
            msg = MessagePrototype.from_message(m)
            msg.embeds = []
            msg.merge_content_into_embed(0)
            msg.merge_attachements_into_embed(embed_no=0, default_url=cfg.default_url)
            processed_messages.append(msg)

        return utils.accumulate(processed_messages)


async def on_start(event: h.StartedEvent):
    global evweekly
    evweekly = await EVWeeklyPages.from_channel(
        event.app,
        EVERVERSE_WEEKLY,
        history_len=4,
        period=dt.timedelta(days=7),
        reference_date=REFERENCE_DATE,
    )


@lb.command("eververse", "Find out about the eververse items")
@lb.implements(lb.SlashCommandGroup)
async def eververse_group(ctx: lb.Context):
    pass


@eververse_group.child
@lb.command("weekly", "Find out about this weeks eververse items")
@lb.implements(lb.SlashSubCommand)
async def eververse_weekly(ctx: lb.Context):
    navigator = NavigatorView(pages=evweekly, timeout=60, autodefer=True)
    await navigator.send(ctx.interaction)


def register(bot):
    bot.command(eververse_group)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            EVERVERSE_WEEKLY,
            "eververse_weekly",
            "Eververse weekly",
            "Eververse weekly auto posts",
        )
    )
