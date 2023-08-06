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

from .. import cfg
from ..nav import NavigatorView, NavPages, NO_DATA_HERE_EMBED
from .autoposts import autopost_command_group, follow_control_command_maker

REFERENCE_DATE = dt.datetime(2023, 7, 14, 17, tzinfo=dt.timezone.utc)

FOLLOWABLE_CHANNEL = cfg.followables["ada"]

SINGLE_PAGE_MODE = True


async def on_start(event: h.StartedEvent):
    global ada_pages
    ada_pages = await NavPages.from_channel(
        event.app,
        FOLLOWABLE_CHANNEL,
        history_len=12,
        period=dt.timedelta(days=7),
        reference_date=REFERENCE_DATE,
        suppress_content_autoembeds=False,
    )


if SINGLE_PAGE_MODE:

    @lb.command("ada", "Find out about ada's weekly items", auto_defer=True)
    @lb.implements(lb.SlashCommand)
    async def ada_command(ctx: lb.Context):
        page_no = 0
        while True:
            try:
                page = ada_pages[page_no]
            except IndexError:
                return await ctx.respond(NO_DATA_HERE_EMBED)
            except:
                page_no -= 1
                continue

            if page.embeds and page.embeds[0] == NO_DATA_HERE_EMBED:
                page_no -= 1
                continue
            else:
                return await ctx.respond(**page.to_message_kwargs())

else:

    @lb.command("ada", "Find out about ada's weekly items")
    @lb.implements(lb.SlashCommand)
    async def ada_command(ctx: lb.Context):
        navigator = NavigatorView(pages=ada_pages, timeout=60)
        await navigator.send(ctx.interaction)


def register(bot):
    bot.command(ada_command)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL, "ada", "Ada", "Ada's weekly item auto posts"
        )
    )
