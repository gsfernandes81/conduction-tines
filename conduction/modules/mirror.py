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

import json
import logging
from asyncio import sleep, TimeoutError

import hikari as h
import lightbulb as lb

from .. import utils
from ..bot import CachedFetchBot
from ..schemas import MirroredChannel, MirroredMessage, db_session


async def message_create_repeater(event: h.MessageCreateEvent):
    msg = event.message
    bot = event.app

    backoff_timer = 30
    while True:
        try:
            mirrors = await MirroredChannel.get_or_fetch_dests(msg.channel_id)
            if not mirrors:
                # Return if this channel is not to be mirrored
                # ie if no mirror list found for it
                return

            logging.info(
                f"MessageCreateEvent received for messge in <#{msg.channel_id}>"
            )

            if not h.MessageFlag.CROSSPOSTED in msg.flags:
                logging.info(
                    f"Message in <#{msg.channel_id}> not crossposted, waiting..."
                )
                await bot.wait_for(
                    h.MessageUpdateEvent,
                    timeout=12 * 60 * 60,
                    predicate=lambda e: e.message.id == msg.id
                    and e.message.flags
                    and h.MessageFlag.CROSSPOSTED in e.message.flags,
                )
                logging.info(
                    f"Crosspost event received for messge in in <#{msg.channel_id}>, "
                    + "continuing..."
                )
        except TimeoutError:
            break
        except Exception as e:
            utils.discord_error_logger(bot, e)
            await sleep(backoff_timer)
            backoff_timer += 30 / backoff_timer
        else:
            break

    async with db_session() as session:
        for mirror_ch_id in mirrors:
            async with session.begin():
                for _ in range(3):  # Retry 3 times at most
                    try:
                        channel: h.TextableChannel = await bot.fetch_channel(
                            mirror_ch_id
                        )

                        if not isinstance(channel, h.TextableChannel):
                            # Ignore non textable channels
                            continue

                        # Send the message
                        mirrored_msg = await channel.send(
                            msg.content,
                            attachments=msg.attachments,
                            components=msg.components,
                            embeds=msg.embeds,
                        )
                    except Exception as e:
                        logging.error(
                            f"Retrying message send in {mirror_ch_id} due to error:"
                        )
                        utils.discord_error_logger(bot, e)
                        continue
                    else:
                        break
                else:
                    logging.error(
                        "Failed to send message in {mirror_ch_id} after 3 tries"
                    )
                    break
                # Record the ids in the db
                await MirroredMessage.add_msg(
                    dest_msg=mirrored_msg.id,
                    dest_channel=mirrored_msg.channel_id,
                    source_msg=msg.id,
                    source_channel=event.channel_id,
                    session=session,
                )


async def message_update_repeater(event: h.MessageUpdateEvent):
    msg = event.message
    bot = event.app

    backoff_timer = 30
    while True:
        try:
            if not await MirroredChannel.get_or_fetch_dests(msg.channel_id):
                # Return if this channel is not to be mirrored
                # ie if no mirror list found for it
                return

            msgs_to_update = await MirroredMessage.get_dest_msgs_and_channels(msg.id)

        except Exception as e:
            utils.discord_error_logger(bot, e)
            await sleep(backoff_timer)
            backoff_timer += 30 / backoff_timer
        else:
            break

    for msg_id, channel_id in msgs_to_update:
        for _ in range(3):  # Retry 3 times at most
            try:
                dest_msg = await bot.fetch_message(channel_id, msg_id)
                await dest_msg.edit(
                    msg.content,
                    attachments=msg.attachments,
                    components=msg.components,
                    embeds=msg.embeds,
                )
            except Exception as e:
                utils.discord_error_logger(bot, e)
            else:
                break
        else:
            logging.error(
                f"Failed to update message {msg_id} in {channel_id} after 3 tries"
            )


@lb.command(name="repeater", description="Repeater control commands")
@lb.implements(lb.SlashCommandGroup)
async def repeater_control_group(ctx: lb.Context):
    pass


@repeater_control_group.child
@lb.option("data", "JSON data to import", str)
@lb.command("json_import", "Add a channels to repeater from json", pass_options=True)
@lb.implements(lb.SlashSubCommand)
async def from_json(ctx: lb.Context, data: str):
    await ctx.respond(h.ResponseType.DEFERRED_MESSAGE_CREATE)
    if not ctx.author.id in await ctx.bot.fetch_owner_ids():
        return

    data = json.loads(data, parse_int=int)
    bot: CachedFetchBot = ctx.bot

    async with db_session() as session:
        async with session.begin():
            for source, dests in data.items():
                for dest in dests:
                    await MirroredChannel.add_mirror(
                        int(source),
                        int(dest),
                        legacy=True,
                        session=session,
                    )

    await ctx.respond(
        "Added mirrors to repeater:\n```\n"
        + "\n".join(
            [
                f"{(await bot.fetch_channel(src_id)).name}: "
                + f"{await MirroredChannel.count_dests(src_id)} mirrors"
                for src_id in data.keys()
            ]
        )
        + "\n```"
    )


def register(bot):
    for event_handler in [
        message_create_repeater,
        message_update_repeater,
    ]:
        bot.listen()(event_handler)

    bot.command(repeater_control_group)
