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

REFERENCE_DATE = dt.datetime(2024, 1, 9, 17, tzinfo=dt.timezone.utc)

FOLLOWABLE_CHANNEL = cfg.followables["trials"]


async def on_start(event: h.StartedEvent):
    global trials_pages
    trials_pages = await NavPages.from_channel(
        event.app,
        FOLLOWABLE_CHANNEL,
        history_len=12,
        period=dt.timedelta(days=7),
        reference_date=REFERENCE_DATE,
        suppress_content_autoembeds=False,
        no_data_message=MessagePrototype(
            content="Trials is unavailable for this week."
        ),
    )


@lb.command("trials", "Find out about this weeks Trials weapon and map")
@lb.implements(lb.SlashCommand)
async def trials_command(ctx: lb.Context):
    navigator = NavigatorView(
        pages=trials_pages,
        allow_start_on_blank_page=True,
    )
    await navigator.send(ctx.interaction)


def register(bot):
    bot.command(trials_command)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL, "trials", "Trials", "Trials weekly auto posts"
        )
    )
