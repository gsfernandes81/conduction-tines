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

import sys

import hikari as h
import lightbulb as lb

from .. import cfg


@lb.command(
    "process_control",
    "Shutdown and restart commands",
    guilds=[cfg.control_discord_server_id],
)
@lb.implements(lb.SlashCommandGroup)
def process_control_command_group():
    pass


@process_control_command_group.child
@lb.command(
    "shutdown",
    "USE WITH CAUTION: Shuts down the bot! Cannot be restarted from discord!",
)
@lb.implements(lb.SlashSubCommand)
async def shutdown_command(ctx: lb.Context):
    await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)
    if ctx.author.id not in await ctx.bot.fetch_owner_ids():
        await ctx.respond("Only a bot owner can use this command")
    else:
        try:
            await ctx.respond("Bot is going down **now**")
            await ctx.bot.close()
        except:
            pass
        finally:
            sys.exit(0)


@process_control_command_group.child
@lb.command("restart", "Restarts the bot")
@lb.implements(lb.SlashSubCommand)
async def restart_command(ctx: lb.Context):
    await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)
    if ctx.author.id not in await ctx.bot.fetch_owner_ids():
        await ctx.respond("Only a bot owner can use this command")
    else:
        try:
            await ctx.respond("Bot is restarting **now**")
            await ctx.bot.close()
        except:
            pass
        finally:
            sys.exit(1)


def register(bot: lb.BotApp):
    bot.command(process_control_command_group)
