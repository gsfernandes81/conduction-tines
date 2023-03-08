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

import flare
import hikari as h
import lightbulb as lb
import sector_accounting
from lightbulb.ext import tasks
from pytz import utc

from .. import cfg, utils
from ..bot import CachedFetchBot, UserCommandBot
from .autoposts import autopost_command_group, follow_control_command_maker

FOLLOWABLE_CHANNEL = cfg.followables["lost_sector"]


@tasks.task(s=30, auto_start=True, wait_before_execution=False)
async def refresh_lost_sector_data():
    # Call sector_on(datetime) to get the sector on that datetime (utc)
    global sector_on
    sector_on = sector_accounting.Rotation.from_gspread_url(
        cfg.sheets_ls_url, cfg.gsheets_credentials, buffer=1
    )


@lb.command("ls", "Find out about today's lost sector")
@lb.implements(lb.SlashCommandGroup)
async def ls_group():
    pass


@ls_group.child
@lb.command("today", "Find out about today's lost sector")
@lb.implements(lb.SlashSubCommand)
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

    full_rotation = flare.LinkButton(cfg.ls_rotation_webpage, label="Full Rotation")
    all_infogfx = flare.LinkButton(cfg.ls_infogfx_webpage, label="All Infographics")
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
            color=cfg.embed_default_color,
        ).set_image(ls_gfx_url),
        component=(await flare.Row(full_rotation, all_infogfx)),
    )


def register(bot: t.Union[CachedFetchBot, UserCommandBot]):
    for command in [
        ls_group,
    ]:
        bot.command(command)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL, "lost_sector", "Lost sector", "Lost sector auto posts"
        )
    )
