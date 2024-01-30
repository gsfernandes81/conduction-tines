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
import logging
import typing as t

import aiohttp
import hikari as h
import lightbulb as lb
import regex as re
import sector_accounting
from hmessage import HMessage as MessagePrototype

from .. import cfg, utils
from ..bot import CachedFetchBot, ServerEmojiEnabledBot, UserCommandBot
from ..nav import NO_DATA_HERE_EMBED, NavigatorView, NavPages
from ..utils import space
from .autoposts import autopost_command_group, follow_control_command_maker

REFERENCE_DATE = dt.datetime(2023, 7, 20, 17, tzinfo=dt.timezone.utc)

FOLLOWABLE_CHANNEL = cfg.followables["lost_sector"]

re_user_side_emoji = re.compile("(<a?)?:(\w+)(~\d)*:(\d+>)?")


def construct_emoji_substituter(
    emoji_dict: t.Dict[str, h.Emoji],
) -> t.Callable[[re.Match], str]:
    """Constructs a substituter for user-side emoji to be used in re.sub"""

    def func(match: re.Match) -> str:
        maybe_emoji_name = str(match.group(2))
        return str(
            emoji_dict.get(maybe_emoji_name)
            or emoji_dict.get(maybe_emoji_name.lower())
            or match.group(0)
        )

    return func


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
    emoji_dict: t.Dict[str, h.Emoji],
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
                    _fmt_count(emoji_dict["barrier"], data.barrier_champions, len_bar),
                    _fmt_count(
                        emoji_dict["overload"], data.overload_champions, len_oload
                    ),
                    _fmt_count(
                        emoji_dict["unstoppable"],
                        data.unstoppable_champions,
                        len_unstop,
                    ),
                ],
            )
        )
        shields_string = space.figure.join(
            filter(
                None,
                [
                    _fmt_count(emoji_dict["arc"], data.arc_shields, len_arc),
                    _fmt_count(emoji_dict["void"], data.void_shields, len_void),
                    _fmt_count(emoji_dict["solar"], data.solar_shields, len_solar),
                    _fmt_count(emoji_dict["stasis"], data.stasis_shields, len_stasis),
                    _fmt_count(emoji_dict["strand"], data.strand_shields, len_strand),
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
    date: dt.datetime = None,
    emoji_dict: t.Dict[str, h.Emoji] = None,
) -> MessagePrototype:
    # Follow the hyperlink to have the newest image embedded
    try:
        ls_gfx_url = await utils.follow_link_single_step(sector.shortlink_gfx)
    except aiohttp.InvalidURL:
        ls_gfx_url = None

    # Surges to emojis
    surges = []
    for surge in sector.surges:
        surges += [str(emoji_dict.get(surge) or emoji_dict.get(surge.lower()))]

    # Threat to emoji
    threat = emoji_dict.get(sector.threat) or emoji_dict.get(sector.threat.lower())

    overcharged_weapon_emoji = (
        "⚔️" if sector.overcharged_weapon.lower() in ["sword", "glaive"] else "🔫"
    )

    if "(" in sector.name or ")" in sector.name:
        sector_name = sector.name.split("(")[0].strip()
        sector_location = sector.name.split("(")[1].split(")")[0].strip()
    else:
        sector_name = sector.name
        sector_location = None

    # Legendary weapon rewards
    legendary_weapon_rewards = sector.legendary_rewards

    legendary_weapon_rewards = re_user_side_emoji.sub(
        construct_emoji_substituter(emoji_dict), legendary_weapon_rewards
    )

    if date:
        suffix = utils.get_ordinal_suffix(date.day)
        title = f"Lost Sector for {date.strftime('%B %-d')}{suffix}"
    else:
        title = "Lost Sector Today"

    embed = (
        h.Embed(
            title=f"**{title}**",
            description=(
                f"{emoji_dict['LS']}{space.three_per_em}{sector_name}\n"
                + (
                    f"{emoji_dict['location']}{space.three_per_em}{sector_location}\n"
                    if sector_location
                    else ""
                )
                + "\n"
            ),
            color=cfg.embed_default_color,
            url="https://lostsectortoday.com/",
        )
        .add_field(
            name="Reward",
            value=f"{emoji_dict['exotic_engram']}{space.three_per_em}Exotic {sector.reward} (If-Solo)",
        )
        .add_field(
            name="Champs and Shields",
            value=format_counts(sector.legend_data, sector.master_data, emoji_dict),
        )
        .add_field(
            name="Elementals",
            value=f"Surge: {space.punctuation}{space.hair}{space.hair}"
            + " ".join(surges)
            + f"\nThreat: {threat}",
        )
        .add_field(
            name="Modifiers",
            value=f"{emoji_dict['swords']}{space.three_per_em}{sector.to_sector_v1().modifiers}"
            + f"\n{overcharged_weapon_emoji}{space.three_per_em}Overcharged {sector.overcharged_weapon}",
        )
        .add_field(
            "Legendary Weapons (If-Solo)",
            legendary_weapon_rewards,
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
    bot: ServerEmojiEnabledBot

    def preprocess_messages(self, messages: t.List[h.Message | MessagePrototype]):
        for m in messages:
            m.embeds = utils.filter_discord_autoembeds(m)
        processed_messages = [
            MessagePrototype.from_message(m)
            .merge_content_into_embed(prepend=False)
            .merge_attachements_into_embed(default_url=cfg.default_url)
            for m in messages
        ]

        processed_message = utils.accumulate(processed_messages)

        # Date correction
        try:
            title = str(processed_message.embeds[0].title)
            if "Lost Sector Today" in title:
                date = messages[0].timestamp
                suffix = utils.get_ordinal_suffix(date.day)
                title = title.replace(
                    "Today", f"for {date.strftime('%B %-d')}{suffix}", 1
                )
                processed_message.embeds[0].title = title
        except Exception as e:
            e.add_note("Exception trying to replace date in lost sector title")
            logging.exception(e)

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
            try:
                sector = sector_on(date)
            except KeyError:
                # A KeyError will be raised if TBC is selected for the google sheet
                # In this case, we will just return a message saying that there is no data
                lookahead_dict = {
                    **lookahead_dict,
                    date: MessagePrototype(embeds=[NO_DATA_HERE_EMBED]),
                }
            else:
                # Follow the hyperlink to have the newest image embedded
                lookahead_dict = {
                    **lookahead_dict,
                    date: await format_sector(
                        sector, date=date, emoji_dict=self.bot.emoji
                    ),
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
    navigator = NavigatorView(pages=sectors)
    await navigator.send(ctx.interaction)


@lb.command("lost", "Find out about today's lost sector")
@lb.implements(lb.SlashCommandGroup)
async def ls_group_2():
    pass


@ls_group_2.child
@lb.command("sector", "Find out about today's lost sector")
@lb.implements(lb.SlashSubCommand)
async def lost_sector_command(ctx: lb.Context):
    navigator = NavigatorView(pages=sectors)
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
