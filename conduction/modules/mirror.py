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
from asyncio import Semaphore, TimeoutError, gather, sleep
from random import randint
from types import TracebackType
from typing import Any, Coroutine, Type

import dateparser
import hikari as h
import lightbulb as lb

from .. import cfg, utils
from ..schemas import MirroredChannel, MirroredMessage, db_session


class TimedSemaphore(Semaphore):
    """Semaphore to ensure no more than value requests per period are made

    This is to stay well within discord api rate limits while avoiding errors"""

    def __init__(self, value: int = 30, period=1):
        super().__init__(value)
        self.period = period

    async def release(self) -> None:
        """Delay release until period has passed"""
        await sleep(self.period)
        return super().release()

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Coroutine[Any, Any, None]:
        return await self.release()


discord_api_semaphore = TimedSemaphore()


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
                    f"Crosspost event received for message in in <#{msg.channel_id}>, "
                    + "continuing..."
                )
        except TimeoutError:
            return
        except Exception as e:
            await utils.discord_error_logger(bot, e)
            await sleep(backoff_timer)
            backoff_timer += 30 / backoff_timer
        else:
            break

    async with db_session() as session:
        async with session.begin():

            async def kernel(mirror_ch_id: int):
                for _ in range(3):  # Retry 3 times at most
                    try:
                        channel: h.TextableChannel = await bot.fetch_channel(
                            mirror_ch_id
                        )

                        if not isinstance(channel, h.TextableChannel):
                            # Ignore non textable channels
                            continue

                        async with discord_api_semaphore:
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
                        await utils.discord_error_logger(bot, e)
                        # Wait for between 3 and 5 minutes before retrying
                        # to allow for momentary discord outages of particular
                        # servers
                        await sleep(randint(180, 300))
                        continue
                    else:
                        break
                else:
                    logging.error(
                        f"Failed to send message in {mirror_ch_id} after 3 tries"
                    )
                    # Log failure in case auto disable is needed
                    await MirroredChannel.log_legacy_mirror_failure(
                        msg.channel_id, mirror_ch_id, session=session
                    )
                    return

                # Record the ids in the db
                await MirroredMessage.add_msg(
                    dest_msg=mirrored_msg.id,
                    dest_channel=mirrored_msg.channel_id,
                    source_msg=msg.id,
                    source_channel=event.channel_id,
                    session=session,
                )

                # Log success to prevent auto disable
                await MirroredChannel.log_legacy_mirror_success(
                    msg.channel_id, mirror_ch_id, session=session
                )

            await gather(
                *[kernel(mirror_ch_id) for mirror_ch_id in mirrors],
                return_exceptions=True,
            )

            # Auto disable persistently failing mirrors
            if cfg.disable_bad_channels:
                disabled_mirrors = await MirroredChannel.disable_legacy_failing_mirrors(
                    session=session
                )

            if disabled_mirrors:
                logging.warning(
                    ("Disabled " if cfg.disable_bad_channels else "Would disable ")
                    + str(len(disabled_mirrors))
                    + " mirrors: "
                    + ", ".join(
                        [
                            f"{mirror.src_id}: {mirror.dest_id}"
                            for mirror in disabled_mirrors
                        ]
                    )
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
            await utils.discord_error_logger(bot, e)
            await sleep(backoff_timer)
            backoff_timer += 30 / backoff_timer
        else:
            break

    async def kernel(msg_id: int, channel_id: int):
        for _ in range(3):  # Retry 3 times at most
            try:
                async with discord_api_semaphore:
                    dest_msg = await bot.fetch_message(channel_id, msg_id)
                async with discord_api_semaphore:
                    await dest_msg.edit(
                        msg.content,
                        attachments=msg.attachments,
                        components=msg.components,
                        embeds=msg.embeds,
                    )
            except Exception as e:
                await utils.discord_error_logger(bot, e)
                # Wait for between 3 and 5 minutes before retrying
                # to allow for momentary discord outages of particular
                # servers
                await sleep(randint(180, 300))
            else:
                break
        else:
            logging.error(
                f"Failed to update message {msg_id} in {channel_id} after 3 tries"
            )

    await gather(
        *[kernel(msg_id, channel_id) for msg_id, channel_id in msgs_to_update],
        return_exceptions=True,
    )


# Command group for all mirror commands
mirror_group = lb.command(
    "mirror",
    description="Command group for all mirror control/administration commands",
    guilds=[cfg.control_discord_server_id],
)(
    lb.implements(
        lb.SlashCommandGroup,
    )(lambda: None)
)


@mirror_group.child
@lb.option("from_date", description="Date to start from", type=str)
@lb.command(
    "undo_auto_disable",
    description="Undo auto disable of a channel due to repeated post failures",
    guilds=[cfg.control_discord_server_id],
    pass_options=True,
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def undo_auto_disable(ctx: lb.Context, from_date: str):
    if not ctx.author.id in await ctx.bot.fetch_owner_ids():
        return

    from_date = dateparser.parse(from_date)

    mirrors = await MirroredChannel.undo_auto_disable_for_failure(since=from_date)
    response = f"Undid auto disable since {from_date} for channels {mirrors}"
    logging.info(response)
    await ctx.respond(response)


def register(bot):
    for event_handler in [
        message_create_repeater,
        message_update_repeater,
    ]:
        bot.listen()(event_handler)

    bot.command(mirror_group)
