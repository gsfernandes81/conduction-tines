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

import typing as t

import hikari as h
import lightbulb as lb

from .. import cfg, schemas
from ..bot import CachedFetchBot


@lb.command("stats", "Bot statistics command group", auto_defer=True, hidden=True)
@lb.implements(lb.SlashCommandGroup)
async def stats_command_group(ctx: lb.Context):
    pass


@stats_command_group.child
@lb.command(
    "populations",
    "Sum of all server populations (Not real time)",
    auto_defer=True,
    hidden=True,
)
@lb.implements(lb.SlashSubCommand)
async def populations_command(ctx: lb.Context):
    bot: CachedFetchBot = ctx.bot

    populations: list = await schemas.ServerStatistics.fetch_server_populations()
    populations.sort(key=lambda x: x[1], reverse=True)
    top_7 = populations[:7]
    rest = sum(map(lambda x: x[1], populations[7:]))

    for server_id, population in top_7:
        try:
            server = await bot.fetch_guild(server_id)
            top_7[top_7.index((server_id, population))] = (server.name, population)
        except:
            top_7[top_7.index((server_id, population))] = (server_id, population)

    await ctx.respond(
        h.Embed(
            title="Server populations",
            description=f"**Top 7 servers by population**\n"
            + "\n".join(
                f"{i+1}. **{server_name}**: {population}"
                for i, (server_name, population) in enumerate(top_7)
            )
            + f"\n**Other servers**: {rest}"
            + f"\n\nTotal: {sum(map(lambda x: x[1], populations))}",
            color=cfg.embed_default_color,
        )
    )


@stats_command_group.child
@lb.command("autoposts", "Mirror statistics", auto_defer=True, hidden=True)
@lb.implements(lb.SlashSubCommand)
async def mirror_stats_command(ctx: lb.Context):
    """Get the number of destinations for each cfg.followables channel"""
    dest_legacy_statistics: t.Dict[str, int] = {}
    dest_non_legacy_statistics: t.Dict[str, int] = {}

    for name, channel_id in cfg.followables.items():
        dest_legacy_statistics[name] = await schemas.MirroredChannel.count_dests(
            channel_id, legacy_only=True
        )
        dest_non_legacy_statistics[name] = await schemas.MirroredChannel.count_dests(
            channel_id, legacy_only=False
        )

    embed = h.Embed(
        title="Autopost statistics",
        description="These stats track all autoposts the bot is aware of. "
        + "It will only be aware of autoposts for servers it is in "
        + "and for channels it can see.",
        color=cfg.embed_default_color,
    )

    for name in dest_legacy_statistics.keys():
        embed.add_field(
            name=name.capitalize(),
            value=f"```Followers : {dest_non_legacy_statistics[name]}\n"
            + f"Mirrors   : {dest_legacy_statistics[name]}```",
            inline=True,
        )

    await ctx.respond(embed)


def register(bot: lb.BotApp):
    bot.command(stats_command_group)
