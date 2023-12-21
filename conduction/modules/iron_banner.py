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

import hikari as h
import lightbulb as lb
from hmessage import HMessage as MessagePrototype

from .. import cfg
from ..nav import NavigatorView, NavPages
from .autoposts import autopost_command_group, follow_control_command_maker

REFERENCE_DATE = dt.datetime(2023, 12, 12, 17, tzinfo=dt.timezone.utc)

FOLLOWABLE_CHANNEL = cfg.followables["iron_banner"]


async def on_start(event: h.StartedEvent):
    global iron_banner_pages
    iron_banner_pages = await NavPages.from_channel(
        event.app,
        FOLLOWABLE_CHANNEL,
        history_len=1,
        period=dt.timedelta(days=7),
        reference_date=REFERENCE_DATE,
        suppress_content_autoembeds=False,
        no_data_message=MessagePrototype(content="No Iron Banner this week : ("),
    )


@lb.command("iron", "Iron banner infographic for when it's active")
@lb.implements(lb.SlashCommandGroup)
async def iron(ctx: lb.Context):
    pass


@iron.child
@lb.command("banner", "Iron banner infographic for when it's active")
@lb.implements(lb.SlashSubCommand)
async def banner(ctx: lb.Context):
    navigator = NavigatorView(
        pages=iron_banner_pages,
        allow_start_on_blank_page=True,
    )
    await navigator.send(ctx.interaction)


def register(bot):
    bot.command(iron)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL, "iron_banner", "Iron Banner", "Iron Banner auto posts"
        )
    )
