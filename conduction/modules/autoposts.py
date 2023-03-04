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

import logging
import traceback as tb
import typing as t
from random import randint

import hikari as h
import lightbulb as lb

from .. import cfg, utils
from ..bot import CachedFetchBot, UserCommandBot
from ..schemas import MirroredChannel, db_session

# Permissions that allow users to manage autoposts in a guild
end_user_allowed_perms = (
    h.Permissions.MANAGE_WEBHOOKS,
    h.Permissions.MANAGE_GUILD,
    h.Permissions.MANAGE_CHANNELS,
    h.Permissions.ADMINISTRATOR,
)

autopost_command_group = lb.command(name="autoposts", description="Autopost control")(
    lb.implements(lb.SlashCommandGroup)(lambda: None)
)


async def pre_start(event: h.StartingEvent):
    event.app.command(autopost_command_group)


def follow_control_command_maker(
    followable_channel: int,
    autoposts_name: str,
    autoposts_friendly_name: str,
    autoposts_desc: str,
):
    """Create a follow control command for a given followable channel

    Args:
        followable_channel (int): The channel ID of the followable channel
        autoposts_name (str): The name of the autoposts command
        autoposts_friendly_name (str): The friendly name to show users for
            the autoposts command. Must be singular and correctly capitalized
            ie first letter capitalized, rest lower case
        autoposts_desc (str): The description for the autoposts command
    """

    @lb.option(
        "option",
        "Enabled or disabled",
        choices=[
            h.CommandChoice(name="Enable", value=1),
            h.CommandChoice(name="Disable", value=0),
        ],
        default=True,
        # Note: Type bool does not allow the choice names to appear for
        # the user, so we use int instead, unsure if this is a lightbulb bug
        type=int,
    )
    @lb.command(autoposts_name, autoposts_desc, pass_options=True)
    @lb.implements(lb.SlashSubCommand)
    @utils.ensure_session(db_session)
    async def follow_control(ctx: lb.Context, option: int, session=None):
        option = bool(option)
        bot: t.Union[CachedFetchBot, UserCommandBot] = ctx.bot
        # Defer the response manually, as auto defer is bugged for subcommands
        await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)

        try:

            if not (
                await utils.check_invoker_is_owner(ctx)
                or await utils.check_invoker_has_perms(ctx, end_user_allowed_perms)
            ):
                owner = await bot.fetch_owner()
                await ctx.respond(
                    h.Embed(
                        title="Insufficient permissions",
                        description="You have insufficient permissions to use this command.\n"
                        + "Any one of the following permissions is needed:\n```\n"
                        + "- Manage Webhooks\n"
                        + "- Manage Guild\n"
                        + "- Manage Channel\n"
                        + "- Administrator\n```\n"
                        + "Make sure that you have this permission in this channel and not "
                        + "just in this guild\n"
                        + "Feel free to contact me on discord if you are having issues!\n",
                        color=cfg.embed_default_color,
                    ).set_footer(
                        f"{owner.username}#{owner.discriminator}",
                        icon=owner.avatar_url or owner.default_avatar_url,
                    )
                )
                return

            try:
                if option:
                    # If we are enabling autoposts:
                    try:
                        await bot.rest.follow_channel(
                            followable_channel, ctx.channel_id
                        )
                        await MirroredChannel.add_mirror(
                            followable_channel, ctx.channel_id, False, session=session
                        )
                    except h.BadRequestError as e:
                        if (
                            "cannot execute action on this channel type"
                            in str(e.args).lower()
                        ):
                            # If this is an announce channel, then the above error is thrown
                            # In this case, add a legacy mirror instead

                            # Test sending a message to the channel before adding the mirror
                            await (
                                await (
                                    await bot.fetch_channel(
                                        ctx.channel_id,
                                    )
                                ).send("Test message :)")
                            ).delete()

                            await MirroredChannel.add_mirror(
                                followable_channel,
                                ctx.channel_id,
                                True,
                                session=session,
                            )

                        else:
                            raise e
                else:
                    # If we are disabling autoposts:

                    # Check if this is a legacy mirror, and if so, remove it and return
                    if int(ctx.channel_id) in (
                        await MirroredChannel.get_or_fetch_dests(followable_channel),
                    ):
                        await MirroredChannel.remove_mirror(
                            followable_channel, ctx.channel_id, session=session
                        )
                        return

                    # If this is not a legacy mirror, then we need to delete the webhook for it

                    # Fetch and delete follow based webhooks and filter for our channel as a
                    # source
                    for hook in await bot.rest.fetch_channel_webhooks(
                        await bot.fetch_channel(ctx.channel_id)
                    ):
                        if (
                            isinstance(hook, h.ChannelFollowerWebhook)
                            and hook.source_channel.id == followable_channel
                        ):
                            await bot.rest.delete_webhook(hook)

                    # Also remove the mirror
                    await MirroredChannel.remove_mirror(
                        followable_channel, ctx.channel_id, session=session
                    )

            except h.ForbiddenError as e:
                if (
                    "missing permissions" in str(e.args).lower()
                    or "missing access" in str(e.args).lower()
                ):
                    # If we are missing permissions, then we can't delete the webhook
                    # In this case, notify the user with a list of possibly missing
                    # permissions
                    bot_owner = await bot.fetch_user((await bot.fetch_owner_ids())[0])
                    await ctx.respond(
                        h.Embed(
                            title="Missing Permissions",
                            description="The bot is missing permissions in this channel.\n"
                            + "Please make sure it has the following permissions:"
                            + "```\n"
                            + "- View Channel\n"
                            + "- Manage Webhooks\n"
                            + "- Send Messages\n"
                            + "```\n"
                            + "If you are still having issues, please contact "
                            + f"**{bot_owner.username}#{bot_owner.discriminator}**",
                            color=cfg.embed_default_color,
                        )
                    )
                raise e
        except Exception as e:
            error_reference = randint(1000000, 9999999)
            bot_owner = await bot.fetch_user((await bot.fetch_owner_ids())[0])
            await ctx.respond(
                h.Embed(
                    title="Pardon our dust!",
                    description="An error occurred while trying to update autopost settings. "
                    + "Please contact "
                    + f"**{bot_owner.username}#{bot_owner.discriminator}** with the "
                    + f"error reference `{error_reference}` and we will fix this "
                    + "for you.",
                    color=cfg.embed_default_color,
                )
            )
            await utils.discord_error_logger(bot, e, error_reference)
            raise e
        else:
            await ctx.respond(
                h.Embed(
                    title=f"{autoposts_friendly_name} autoposts "
                    + ("enabled" if option else "disabled")
                    + "!",
                    color=cfg.embed_default_color,
                )
            )

    return follow_control


def register(bot: lb.BotApp):
    bot.listen()(pre_start)
