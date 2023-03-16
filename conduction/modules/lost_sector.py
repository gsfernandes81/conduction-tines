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
from calendar import month_name

import hikari as h
import lightbulb as lb
import sector_accounting

from .. import cfg, utils
from ..bot import CachedFetchBot, UserCommandBot
from .autocmd import MessagePrototype, NavigatorView, NavPages
from .autoposts import autopost_command_group, follow_control_command_maker

FOLLOWABLE_CHANNEL = cfg.followables["lost_sector"]
sectors = []


class SectorMessages(NavPages):
    @classmethod
    def preprocess_messages(self, messages: t.List[h.Message | MessagePrototype]):
        processed_messages = [
            MessagePrototype.from_message(m)
            .merge_content_into_embed(prepend=False)
            .merge_attachements_into_embed()
            for m in messages
        ]

        processed_message = utils.accumulate(processed_messages)

        # Date correction
        title = processed_message.embeds[0].title
        if "Lost Sector Today" in title:
            date = messages[0].timestamp
            suffix = utils.get_ordinal_suffix(date.day)
            title = title.replace("Today", f"for {date.strftime('%B %-d')}{suffix}", 1)
            processed_message.embeds[0].title = title

        return processed_message

    @classmethod
    def period_around(self, date: dt.datetime = None) -> t.Tuple[dt.datetime]:
        return utils.daily_reset_period(date)

    async def lookahead(
        self, after: dt.datetime
    ) -> t.Dict[dt.datetime, MessagePrototype]:
        start_date = self.period_around(dt.datetime.now(tz=dt.timezone.utc))[1]
        sector_on = sector_accounting.Rotation.from_gspread_url(
            cfg.sheets_ls_url, cfg.gsheets_credentials, buffer=1
        )

        lookahead_dict = {}

        for date in [start_date + self.period * n for n in range(self.lookahead_len)]:
            sector = sector_on(date)

            # Follow the hyperlink to have the newest image embedded
            ls_gfx_url = await utils.follow_link_single_step(sector.shortlink_gfx)

            format_dict = {
                "month": month_name[date.month],
                "day": date.day,
                "sector": sector,
                "ls_url": ls_gfx_url,
            }

            suffix = utils.get_ordinal_suffix(date.day)
            embed_title = f"Lost Sector for {date.strftime('%B %-d')}{suffix}"

            embed = h.Embed(
                title=embed_title,
                description=(
                    "⠀\n<:LS:849727805994565662> **{sector.name}\n\n".format(
                        **format_dict
                    ).replace(" (", "** (", 1)
                    + "• **Reward (If-Solo)**: {sector.reward}\n"
                    + "• **Champs**: {sector.champions}\n"
                    + "• **Shields**: {sector.shields}\n"
                    + "• **Burn**: {sector.burn}\n"
                    + "• **Modifiers**: {sector.modifiers}\n"
                    + "\n"
                    + "ℹ️ : <https://lostsectortoday.com/>"
                ).format(**format_dict),
                color=cfg.embed_default_color,
            ).set_image(ls_gfx_url)

            lookahead_dict = {**lookahead_dict, date: MessagePrototype(embeds=[embed])}

        return lookahead_dict


async def on_start(event: h.StartedEvent):
    global sectors
    sectors = await SectorMessages.from_channel(
        event.app, FOLLOWABLE_CHANNEL, history_len=9, lookahead_len=5
    )


@lb.command("ls", "Find out about today's lost sector")
@lb.implements(lb.SlashCommandGroup)
async def ls_group():
    pass


@ls_group.child
@lb.command("today", "Find out about today's lost sector")
@lb.implements(lb.SlashSubCommand)
async def lost_sector_today_command(ctx: lb.Context):
    navigator = NavigatorView(pages=sectors, timeout=60)
    await navigator.send(ctx.interaction)


def register(bot: t.Union[CachedFetchBot, UserCommandBot]):
    bot.command(ls_group)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL, "lost_sector", "Lost sector", "Lost sector auto posts"
        )
    )
