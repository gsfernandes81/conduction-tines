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


FOLLOWABLE_CHANNEL = cfg.followables["nwid"]


class NWIDPages(NavPages):
    @classmethod
    def _preprocess_messages(
        cls, messages: t.List[MessagePrototype | h.Message]
    ) -> MessagePrototype:
        msg = utils.accumulate([MessagePrototype.from_message(m) for m in messages])

        urls = cfg.url_regex.findall(msg.content)

        autoembeds_from_discord = list(
            filter(lambda embed: embed.url in urls, msg.embeds)
        )
        image_autoembeds_from_discord = list(
            filter(
                lambda embed: any(
                    [
                        embed.url.lower().endswith(extension)
                        for extension in cfg.IMAGE_EXTENSIONS_LIST
                    ]
                ),
                autoembeds_from_discord,
            )
        )
        non_image_autoembeds_from_discord = list(
            filter(
                lambda embed: embed not in image_autoembeds_from_discord,
                autoembeds_from_discord,
            )
        )

        msg.embeds = list(
            filter(
                lambda embed: embed not in non_image_autoembeds_from_discord, msg.embeds
            )
        )

        msg.merge_content_into_embed(0)

        for embed in list(image_autoembeds_from_discord):
            msg.merge_url_as_image_into_embed(embed.url, 0)

        msg.remove_all_embed_thumbnails()
        msg.embeds = list(filter(lambda embed: embed.description, msg.embeds))

        return msg


async def on_start(event: h.StartedEvent):
    global evweekly
    evweekly = await NWIDPages.from_channel(
        event.app,
        FOLLOWABLE_CHANNEL,
        history_len=4,
        period=dt.timedelta(days=7),
        reference_date=REFERENCE_DATE,
        suppress_content_autoembeds=False,
    )


@lb.command("nwid", "Find out about This Week In Destinty (formerly the TWAB)")
@lb.implements(lb.SlashCommand)
async def nwid(ctx: lb.Context):
    navigator = NavigatorView(pages=evweekly, autodefer=True)
    await navigator.send(ctx.interaction)


def register(bot):
    bot.command(nwid)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL,
            "nwid",
            "NWID",
            "Next Week In Destiny weekly auto posts",
        )
    )
