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
import sys
from calendar import month_name

import hikari as h
import lightbulb as lb
import sector_accounting
from lightbulb.ext import tasks
from pytz import utc

from .. import cfg, utils


@tasks.task(s=30, auto_start=True, wait_before_execution=False)
async def refresh_lost_sector_data():
    # Call sector_on(datetime) to get the sector on that datetime (utc)
    global sector_on
    sector_on = sector_accounting.Rotation.from_gspread_url(
        cfg.sheets_ls_url, cfg.gsheets_credentials, buffer=1
    )


@lb.command("lstoday", "Find out about today's lost sector")
@lb.implements(lb.SlashCommand)
async def lost_sector_today_command(ctx: lb.Context):
    date = dt.datetime.now(tz=utc)
    sector = sector_on(date)
    bot = ctx.bot

    # Follow the hyperlink to have the newest image embedded
    ls_gfx_url = await utils.follow_link_single_step(sector.shortlink_gfx)

    format_dict = {
        "month": month_name[date.month],
        "day": date.day,
        "sector": sector,
        "ls_url": ls_gfx_url,
    }

    await ctx.respond(
        embed=h.Embed(
            title="**Lost Sector Today**".format(**format_dict),
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
            color=cfg.kyber_pink,
        ).set_image(ls_gfx_url),
        components=(
            bot.rest.build_message_action_row()
            .add_button(h.ButtonStyle.LINK, cfg.ls_rotation_webpage)
            .set_label("Full rotation")
            .add_to_container()
            .add_button(h.ButtonStyle.LINK, cfg.ls_infogfx_webpages)
            .set_label("All infographics")
            .add_to_container(),
        ),
    )


def register(bot):
    for command in [
        lost_sector_today_command,
    ]:
        bot.command(command)
