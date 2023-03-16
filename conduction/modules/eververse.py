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

from .. import cfg, utils
from .autocmd import MessagePrototype, NavigatorView, NavPages
from .autoposts import autopost_command_group, follow_control_command_maker

EVERVERSE_WEEKLY = cfg.followables["eververse"]
EVERVERSE_DAILY = cfg.followables["daily_reset"]


class EVWeeklyPages(NavPages):
    @classmethod
    def preprocess_messages(
        cls, messages: t.List[MessagePrototype | h.Message]
    ) -> MessagePrototype:

        processed_messages = [
            MessagePrototype.from_message(m)
            .merge_content_into_embed(0)
            .merge_attachements_into_embed(designator=n)
            for n, m in enumerate(messages)
        ]
        return utils.accumulate(processed_messages)

    @classmethod
    def period_around(cls, date: dt.datetime = None) -> t.Tuple[dt.datetime]:
        return utils.weekly_reset_period(date)


class EVDailyPages(NavPages):
    @classmethod
    def preprocess_messages(
        cls, messages: t.List[MessagePrototype | h.Message]
    ) -> MessagePrototype:
        processed_messages = [
            MessagePrototype.from_message(m)
            .merge_content_into_embed(0)
            .merge_attachements_into_embed(designator=n)
            for n, m in enumerate(messages)
        ]
        return utils.accumulate(processed_messages)

    @classmethod
    def period_around(cls, date: dt.datetime = None) -> t.Tuple[dt.datetime]:
        return utils.daily_reset_period(date)


async def on_start(event: h.StartedEvent):
    global evweekly
    evweekly = await EVWeeklyPages.from_channel(
        event.app, EVERVERSE_WEEKLY, history_len=4
    )
    global evdaily
    evdaily = await EVDailyPages.from_channel(
        event.app, EVERVERSE_DAILY, history_len=14
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


@eververse_group.child
@lb.command("daily", "Find out about today's eververse offer")
@lb.implements(lb.SlashSubCommand)
async def eververse_daily(ctx: lb.Context):
    navigator = NavigatorView(pages=evdaily, timeout=60, autodefer=True)
    await navigator.send(ctx.interaction)


def register(bot):
    bot.command(eververse_group),
    bot.listen()(on_start)

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
