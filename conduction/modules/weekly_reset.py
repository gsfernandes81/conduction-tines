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
from lightbulb.ext import tasks

from .. import cfg, utils
from ..bot import CachedFetchBot
from .autoposts import autopost_command_group, follow_control_command_maker
from . import autocmd

FOLLOWABLE_CHANNEL = cfg.followables["weekly_reset"]


@tasks.task(m=1, auto_start=True, wait_before_execution=False, pass_app=True)
async def refresh_weekly_reset_data(bot: CachedFetchBot) -> None:
    global weekly_reset_message_kwargs

    messages = await autocmd.pull_messages_from_channel(
        bot, after=utils.weekly_reset_period()[0], channel_id=FOLLOWABLE_CHANNEL
    )

    msg_proto = autocmd.MessagePrototype()
    for message_no, message in enumerate(messages):
        msg_proto = msg_proto + autocmd.MessagePrototype.from_message(message)

    msg_proto.merge_content_into_embed()
    msg_proto.merge_attachements_into_embed(designator=message_no)

    weekly_reset_message_kwargs = msg_proto.to_message_kwargs()


async def get_basic_weekly_reset_embed():
    return h.Embed(
        title="Weekly Reset",
        url=await utils.follow_link_single_step("https://kyberscorner.com/"),
        color=cfg.default_embed_color,
    ).set_image("https://kyber3000.com/Reset")


@lb.command("weekly", "Weekly reset")
@lb.implements(lb.SlashCommandGroup)
async def weekly_reset_command_group(ctx: lb.Context):
    pass


@weekly_reset_command_group.child
@lb.command("reset", "Find out about this weeks reset")
@lb.implements(lb.SlashSubCommand)
async def weekly_reset_command(ctx: lb.Context):
    await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)

    try:
        await ctx.respond(**weekly_reset_message_kwargs)
    except NameError:
        await ctx.respond(await get_basic_weekly_reset_embed())


def register(bot):
    for command in [
        weekly_reset_command_group,
    ]:
        bot.command(command)

    autopost_command_group.child(
        follow_control_command_maker(
            FOLLOWABLE_CHANNEL,
            "weekly_reset",
            "Weekly reset",
            "Weekly reset auto posts",
        )
    )
