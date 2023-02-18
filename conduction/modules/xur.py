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

import hikari as h
import lightbulb as lb

from .. import cfg, utils
from .autoposts import autopost_command_group, follow_control_command_maker

FOLLOWABLE_CHANNEL = cfg.followables["xur"]


async def get_basic_xur_embed():
    return h.Embed(
        title="Xur",
        url=await utils.follow_link_single_step("https://kyberscorner.com/"),
        color=cfg.kyber_pink,
    ).set_image("https://kyber3000.com/Xur")


@lb.command("xur", "Find out what Xur has and where Xur isup")
@lb.implements(lb.SlashCommand)
async def xur_command(ctx: lb.Context):
    await ctx.respond(await get_basic_xur_embed())


def register(bot):
    for command in [
        xur_command,
    ]:
        bot.command(command)

    autopost_command_group.child(
        follow_control_command_maker(FOLLOWABLE_CHANNEL, "xur", "Xur", "Xur auto posts")
    )
