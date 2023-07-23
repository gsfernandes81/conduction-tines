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

import aiohttp
import hikari as h
import lightbulb as lb
import sector_accounting
from hmessage import HMessage as MessagePrototype

from .. import cfg, utils
from ..bot import CachedFetchBot, UserCommandBot
from ..nav import NavigatorView, NavPages
from ..utils import space
from .autoposts import autopost_command_group, follow_control_command_maker

REFERENCE_DATE = dt.datetime(2023, 7, 20, 17, tzinfo=dt.timezone.utc)

FOLLOWABLE_CHANNEL = cfg.followables["lost_sector"]


def _fmt_count(emoji: str, count: int, width: int) -> str:
    if count:
        return "{} x `{}`".format(
            emoji,
            str(count if count != -1 else "?").rjust(width, " "),
        )
    else:
        return ""


def format_counts(
    legend_data: sector_accounting.sector_accounting.DifficultySpecificSectorData,
    master_data: sector_accounting.sector_accounting.DifficultySpecificSectorData,
) -> str:
    len_bar = len(
        str(max(legend_data.barrier_champions, master_data.barrier_champions, key=abs))
    )
    len_oload = len(
        str(
            max(legend_data.overload_champions, master_data.overload_champions, key=abs)
        )
    )
    len_unstop = len(
        str(
            max(
                legend_data.unstoppable_champions,
                master_data.unstoppable_champions,
                key=abs,
            )
        )
    )
    len_arc = len(str(max(legend_data.arc_shields, master_data.arc_shields, key=abs)))
    len_void = len(
        str(max(legend_data.void_shields, master_data.void_shields, key=abs))
    )
    len_solar = len(
        str(max(legend_data.solar_shields, master_data.solar_shields, key=abs))
    )
    len_stasis = len(
        str(max(legend_data.stasis_shields, master_data.stasis_shields, key=abs))
    )
    len_strand = len(
        str(max(legend_data.strand_shields, master_data.strand_shields, key=abs))
    )

    data_strings = []

    for data in [legend_data, master_data]:
        champs_string = space.figure.join(
            filter(
                None,
                [
                    _fmt_count(cfg.emoji["barrier"], data.barrier_champions, len_bar),
                    _fmt_count(
                        cfg.emoji["overload"], data.overload_champions, len_oload
                    ),
                    _fmt_count(
                        cfg.emoji["unstoppable"], data.unstoppable_champions, len_unstop
                    ),
                ],
            )
        )
        shields_string = space.figure.join(
            filter(
                None,
                [
                    _fmt_count(cfg.emoji["arc"], data.arc_shields, len_arc),
                    _fmt_count(cfg.emoji["void"], data.void_shields, len_void),
                    _fmt_count(cfg.emoji["solar"], data.solar_shields, len_solar),
                    _fmt_count(cfg.emoji["stasis"], data.stasis_shields, len_stasis),
                    _fmt_count(cfg.emoji["strand"], data.strand_shields, len_strand),
                ],
            )
        )
        data_string = f"{space.figure}|{space.figure}".join(
            filter(
                None,
                [
                    champs_string,
                    shields_string,
                ],
            )
        )
        data_strings.append(data_string)

    return (
        f"Legend:{space.figure}"
        + data_strings[0]
        + f"\nMaster:{space.hair}{space.figure}"
        + data_strings[1]
    )


async def format_sector(
    sector: sector_accounting.Sector,
    thumbnail: h.Attachment | None = None,
    secondary_image: h.Attachment | None = None,
    secondary_embed_title: str | None = "",
    secondary_embed_description: str | None = "",
) -> MessagePrototype:
    # Follow the hyperlink to have the newest image embedded
    try:
        ls_gfx_url = await utils.follow_link_single_step(sector.shortlink_gfx)
    except aiohttp.InvalidURL:
        ls_gfx_url = None

    # Surges to emojis
    _surges = [surge.lower() for surge in sector.surges]
    surges = []
    if "solar" in _surges:
        surges += [cfg.emoji["solar"]]
    if "arc" in _surges:
        surges += [cfg.emoji["arc"]]
    if "void" in _surges:
        surges += [cfg.emoji["void"]]
    if "stasis" in _surges:
        surges += [cfg.emoji["stasis"]]
    if "strand" in _surges:
        surges += [cfg.emoji["strand"]]

    # Threat to emoji
    threat = sector.threat.lower()
    if threat == "solar":
        threat = cfg.emoji["solar"]
    elif threat == "arc":
        threat = cfg.emoji["arc"]
    elif threat == "void":
        threat = cfg.emoji["void"]
    elif threat == "stasis":
        threat = cfg.emoji["stasis"]
    elif threat == "strand":
        threat = cfg.emoji["strand"]

    overcharged_weapon_emoji = (
        "⚔️" if sector.overcharged_weapon.lower() in ["sword", "glaive"] else "🔫"
    )

    if "(" in sector.name or ")" in sector.name:
        sector_name = sector.name.split("(")[0].strip()
        sector_location = sector.name.split("(")[1].split(")")[0].strip()
    else:
        sector_name = sector.name
        sector_location = None

    embed = (
        h.Embed(
            title="**Lost Sector Today**",
            description=(
                f"{cfg.emoji['ls']}{space.three_per_em}{sector_name}\n"
                + (
                    f"{cfg.emoji['location']}{space.three_per_em}{sector_location}\n"
                    if sector_location
                    else ""
                )
                + f"\n"
            ),
            color=cfg.embed_default_color,
            url="https://lostsectortoday.com/",
        )
        .add_field(
            name=f"Reward",
            value=f"{cfg.emoji['exotic_engram']}{space.three_per_em}Exotic {sector.reward} (If-Solo)",
        )
        .add_field(
            name=f"Champs and Shields",
            value=format_counts(sector.legend_data, sector.master_data),
        )
        .add_field(
            name=f"Elementals",
            value=f"Surge: {space.punctuation}{space.hair}{space.hair}"
            + " ".join(surges)
            + f"\nThreat: {threat}",
        )
        .add_field(
            name=f"Modifiers",
            value=f"{cfg.emoji['swords']}{space.three_per_em}{sector.to_sector_v1().modifiers}"
            + f"\n{overcharged_weapon_emoji}{space.three_per_em}Overcharged {sector.overcharged_weapon}",
        )
    )

    if ls_gfx_url:
        embed.set_image(ls_gfx_url)

    if thumbnail:
        embed.set_thumbnail(thumbnail)

    if secondary_image:
        embed2 = h.Embed(
            title=secondary_embed_title,
            description=secondary_embed_description,
            color=cfg.kyber_pink,
        )
        embed2.set_image(secondary_image)
        embeds = [embed, embed2]
    else:
        embeds = [embed]

    return MessagePrototype(embeds=embeds)


class SectorMessages(NavPages):
    @classmethod
    def preprocess_messages(cls, messages: t.List[h.Message | MessagePrototype]):
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

    async def lookahead(
        self, after: dt.datetime
    ) -> t.Dict[dt.datetime, MessagePrototype]:
        start_date = after
        sector_on = sector_accounting.Rotation.from_gspread_url(
            cfg.sheets_ls_url, cfg.gsheets_credentials, buffer=1
        )

        lookahead_dict = {}

        for date in [start_date + self.period * n for n in range(self.lookahead_len)]:
            sector = sector_on(date)

            # Follow the hyperlink to have the newest image embedded
            lookahead_dict = {
                **lookahead_dict,
                date: await format_sector(sector),
            }

        return lookahead_dict


async def on_start(event: h.StartedEvent):
    global sectors
    sectors = await SectorMessages.from_channel(
        event.app,
        FOLLOWABLE_CHANNEL,
        history_len=14,
        lookahead_len=7,
        period=dt.timedelta(days=1),
        reference_date=REFERENCE_DATE,
    )


@lb.command("ls", "Find out about today's lost sector")
@lb.implements(lb.SlashCommandGroup)
async def ls_group():
    pass


@ls_group.child
@lb.command("today", "Find out about today's lost sector")
@lb.implements(lb.SlashSubCommand)
async def ls_today_command(ctx: lb.Context):
    navigator = NavigatorView(pages=sectors, timeout=60)
    await navigator.send(ctx.interaction)


@lb.command("lost", "Find out about today's lost sector")
@lb.implements(lb.SlashCommandGroup)
async def ls_group_2():
    pass


@ls_group_2.child
@lb.command("sector", "Find out about today's lost sector")
@lb.implements(lb.SlashSubCommand)
async def lost_sector_command(ctx: lb.Context):
    navigator = NavigatorView(pages=sectors, timeout=60)
    await navigator.send(ctx.interaction)


def register(bot: t.Union[CachedFetchBot, UserCommandBot]):
    bot.command(ls_group)
    bot.command(ls_group_2)
    bot.listen()(on_start)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL, "lost_sector", "Lost sector", "Lost sector auto posts"
        )
    )
