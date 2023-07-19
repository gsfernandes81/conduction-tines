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

import asyncio as aio
import logging
import sys
from random import randint
from time import perf_counter
from types import TracebackType
from typing import Any, Coroutine, Optional, Type

import attr
import dateparser
import hikari as h
import lightbulb as lb

from .. import bot, cfg, utils
from ..schemas import MirroredChannel, MirroredMessage, db_session


class TimedSemaphore(aio.Semaphore):
    """Semaphore to ensure no more than value requests per period are made

    This is to stay well within discord api rate limits while avoiding errors"""

    def __init__(self, value: int = 30, period=1):
        super().__init__(value)
        self.period = period

    async def release(self) -> None:
        """Delay release until period has passed"""
        await aio.sleep(self.period)
        return super().release()

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Coroutine[Any, Any, None]:
        return await self.release()


discord_api_semaphore = TimedSemaphore()


@attr.s
class KernelWorkDone:
    """Class to hold the result of a creation kernel"""

    source_message_id: int = attr.ib(converter=int)
    dest_channel_id: int = attr.ib(converter=int)
    dest_message_id: int = attr.ib(default=0, converter=int)
    exception: Exception = attr.ib(default=None)
    retries: int = attr.ib(default=0, converter=int)


async def log_mirror_progress_to_discord(
    bot: bot.CachedFetchBot,
    successes: int,
    retries: int,
    failures: int,
    pending: int,
    source_message: h.Message,
    start_time: float,
    title: Optional[str] = "Mirror progress",
    existing_message: Optional[int | h.Message] = None,
    is_completed: Optional[bool] = False,
):
    log_channel: h.TextableGuildChannel = await bot.fetch_channel(cfg.log_channel)

    COMPLETED = 2
    RETRYING = 3
    FAILED = 4
    REMAINING = 5
    TIME_TAKEN = 6

    if isinstance(existing_message, int):
        existing_message = await bot.fetch_message(log_channel, existing_message)

    time_taken = round(perf_counter() - start_time, 2)
    time_taken = (
        f"{time_taken} seconds"
        if time_taken < 60
        else f"{time_taken // 60} minutes {round(time_taken % 60, 2)} seconds"
    )

    if not existing_message:
        source_channel: h.TextableGuildChannel = await bot.fetch_channel(
            source_message.channel_id
        )
        source_guild = await bot.fetch_guild(source_channel.guild_id)

        source_message_summary = (
            source_message.content.split("\n")[0] if source_message.content else False
        ) or (
            (
                source_message.embeds[0].title
                or source_message.embeds[0].description.split()[0],
            )
            if source_message.embeds
            else "Link"
        )
        source_message_link = source_message.make_link(source_guild)
        source_channel_link = (
            "https://discord.com/channels/"
            + str(source_channel.guild_id)
            + "/"
            + str(source_channel.id)
        )

        embed = h.Embed(color=cfg.embed_default_color, title=title)
        embed.add_field(
            "Source message", f"[{source_message_summary}]({source_message_link})"
        ).add_field(
            "Source channel", f"[{source_channel.name}]({source_channel_link})"
        ).add_field(
            "Completed", str(successes)
        ).add_field(
            "Retrying", str(retries)
        ).add_field(
            "Failed", str(failures)
        ).add_field(
            "Remaining", str(pending)
        ).add_field(
            "Time taken", f"{time_taken} seconds"
        )

        if source_message.embeds and source_message.embeds[0].image:
            embed.set_thumbnail(source_message.embeds[0].image.url)
        elif source_message.attachments and source_message.attachments[
            0
        ].media_type.startswith("image"):
            embed.set_thumbnail(source_message.attachments[0].url)

        if is_completed:
            embed.set_footer(
                text="✅ Completed",
            )
        else:
            embed.set_footer(
                text="⏳ In progress",
            )

        return await log_channel.send(embed)
    else:
        embed = existing_message.embeds[0]
        embed.edit_field(COMPLETED, h.UNDEFINED, str(successes))
        embed.edit_field(RETRYING, h.UNDEFINED, str(retries))
        embed.edit_field(FAILED, h.UNDEFINED, str(failures))
        embed.edit_field(REMAINING, h.UNDEFINED, str(pending))
        embed.edit_field(TIME_TAKEN, h.UNDEFINED, str(time_taken))

        if is_completed:
            embed.set_footer(
                text="✅ Completed",
            )

        return await existing_message.edit(embeds=[embed])


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
        except aio.TimeoutError:
            return
        except Exception as e:
            await utils.discord_error_logger(bot, e)
            await aio.sleep(backoff_timer)
            backoff_timer += 30 / backoff_timer
        else:
            break

    mirror_start_time = perf_counter()

    async with db_session() as session:
        async with session.begin():

            async def kernel(
                mirror_ch_id: int, current_retries: int = 0, delay: int = 0
            ) -> KernelWorkDone:
                await aio.sleep(delay)

                try:
                    channel: h.TextableChannel = await bot.fetch_channel(mirror_ch_id)

                    if not isinstance(channel, h.TextableChannel):
                        # Ignore non textable channels
                        raise ValueError("Channel is not textable")

                    async with discord_api_semaphore:
                        # Send the message
                        mirrored_msg = await channel.send(
                            msg.content,
                            attachments=msg.attachments,
                            components=msg.components,
                            embeds=msg.embeds,
                        )
                except Exception as e:
                    e.add_note(
                        f"Scheduling retry for message-send to channel {mirror_ch_id} "
                        + "due to exception\n"
                    )
                    logging.exception(e)
                    return KernelWorkDone(
                        source_message_id=msg.id,
                        dest_channel_id=mirror_ch_id,
                        exception=e,
                        retries=current_retries,
                    )

                return KernelWorkDone(
                    source_message_id=msg.id,
                    dest_channel_id=mirror_ch_id,
                    dest_message_id=mirrored_msg.id,
                    retries=current_retries,
                )

            announce_jobs = [
                aio.create_task(kernel(mirror_ch_id)) for mirror_ch_id in mirrors
            ]
            return_in = 10  # seconds
            max_retries = 3
            log_message: h.Message = await log_mirror_progress_to_discord(
                bot,
                0,
                0,
                0,
                len(mirrors),
                msg,
                mirror_start_time,
                title="Mirror progress",
            )

            successes = []
            failures = []
            to_retry = []
            pending = []

            while True:
                done, pending = await aio.wait(
                    # announce_jobs is set then updated to only contain pending jobs
                    announce_jobs,
                    # Use the timeout to return in a fixed time to update logging and the db
                    timeout=return_in,
                    return_when=aio.ALL_COMPLETED,
                )

                # Successes and failures to log to db
                failures_to_log = []
                successes_to_log = []
                # Empty the to_retry list
                to_retry = []

                for task in done:
                    result = task.result()
                    # If the result is an exception
                    if result.exception:
                        if result.retries + 1 < max_retries:
                            # and if we have retries left
                            # then we add it to the to_retry list
                            to_retry.append(result)
                        else:
                            # if we have no retries left
                            # then we add it to the failures list
                            # for logging in the db
                            failures_to_log.append(result)
                    else:
                        # If the result is not an exception
                        # then we add it to the successes list
                        # to be logged in the db
                        successes_to_log.append(result)

                # Log successes, failures and message pairs to the db
                maybe_exceptions = await aio.gather(
                    MirroredChannel.log_legacy_mirror_failure_in_batch(
                        msg.channel_id,
                        [failure.dest_channel_id for failure in failures_to_log],
                        session=session,
                    ),
                    MirroredChannel.log_legacy_mirror_success_in_batch(
                        msg.channel_id,
                        [success.dest_channel_id for success in successes_to_log],
                        session=session,
                    ),
                    MirroredMessage.add_msgs_in_batch(
                        dest_msgs=[
                            success.dest_message_id for success in successes_to_log
                        ],
                        dest_channels=[
                            success.dest_channel_id for success in successes
                        ],
                        source_msg=msg.id,
                        source_channel=msg.channel_id,
                    ),
                )

                # Log exceptions working with the db to the console
                if any(maybe_exceptions):
                    logging.error(
                        "Error logging mirror success/failure in db: "
                        + ", ".join(
                            [
                                str(exception)
                                for exception in maybe_exceptions
                                if exception
                            ]
                        )
                    )

                successes.extend(successes_to_log)
                failures.extend(failures_to_log)

                log_message = await log_mirror_progress_to_discord(
                    bot,
                    len(successes),
                    len(to_retry),
                    len(failures),
                    len(pending),
                    msg,
                    mirror_start_time,
                    existing_message=log_message,
                    is_completed=not bool(pending),
                )

                announce_jobs = pending | set(
                    aio.create_task(
                        kernel(
                            job.dest_channel_id,
                            job.retries + 1,
                            # Wait for between 3 and 5 minutes before retrying
                            # to allow for momentary discord outages of particular
                            # servers
                            delay=randint(180, 300),
                        )
                    )
                    for job in to_retry
                )

                if len(pending) == 0:
                    break

            logging.info(
                "Completed all mirrors in " + str(perf_counter() - mirror_start_time)
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
            if not msgs_to_update:
                # Return if this message was not mirrored for any reason
                return

        except Exception as e:
            await utils.discord_error_logger(bot, e)
            await aio.sleep(backoff_timer)
            backoff_timer += 30 / backoff_timer
        else:
            break

    mirror_start_time = perf_counter()

    async def kernel(
        msg_id: int, channel_id: int, current_retries: Optional[int] = 0, delay: int = 0
    ) -> None | KernelWorkDone:
        await aio.sleep(delay)

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
            e.add_note(
                f"Scheduling retry for message-update to channel {channel_id} "
                + "due to exception\n"
            )
            logging.exception(e)
            return KernelWorkDone(
                msg_id, channel_id, exception=e, retries=current_retries
            )
        else:
            return KernelWorkDone(
                msg_id, channel_id, dest_msg.id, retries=current_retries
            )

    announce_jobs = [
        aio.create_task(kernel(msg_id, channel_id))
        for msg_id, channel_id in msgs_to_update
    ]

    return_in = 15  # seconds
    max_retries = 3
    log_message: h.Message = await log_mirror_progress_to_discord(
        bot,
        0,
        0,
        0,
        len(msgs_to_update),
        msg,
        mirror_start_time,
        title="Mirror update progress",
    )

    successes = []
    to_retry = []
    failures = []
    while True:
        done, pending = await aio.wait(
            announce_jobs,
            timeout=return_in,
            return_when=aio.ALL_COMPLETED,
        )

        # Empty the to_retry list
        to_retry = []

        for task in done:
            result: KernelWorkDone = task.result()
            # If the result is an exception
            if result.exception:
                if result.retries + 1 < max_retries:
                    # and if we have retries left
                    # then we add it to the to_retry list
                    to_retry.append(result)
                else:
                    # if we have no retries left
                    # then we add it to the failures list
                    # for logging only to the console
                    failures.append(result)
            else:
                # If the result is not an exception
                # then we add it to the successes list
                successes.append(result)

        log_message = await log_mirror_progress_to_discord(
            bot,
            len(successes),
            len(to_retry),
            len(failures),
            len(pending),
            msg,
            mirror_start_time,
            existing_message=log_message,
            is_completed=not bool(pending),
        )

        announce_jobs = pending | set(
            aio.create_task(
                kernel(
                    job.source_message_id,
                    job.dest_channel_id,
                    job.retries + 1,
                    # Wait for between 3 and 5 minutes before retrying
                    # to allow for momentary discord outages of particular
                    # servers
                    delay=randint(180, 300),
                )
            )
            for job in to_retry
        )

        if len(pending) == 0:
            break


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
