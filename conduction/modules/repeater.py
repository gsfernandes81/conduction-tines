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

import hikari as h

from .. import cfg
from ..schemas import MirroredMessage, db_session


async def message_create_repeater(event: h.MessageCreateEvent):
    msg = event.message
    bot = event.app

    mirrors = cfg.mirror_dict.get(msg.channel_id)
    if not mirrors:
        # Return if this channel is not to be mirrored
        # ie if no mirror list found for it
        return

    for mirror_ch_id in mirrors:
        channel: h.TextableChannel = await bot.fetch_channel(mirror_ch_id)

        if not isinstance(channel, h.TextableChannel):
            # Ignore non textable channels
            continue

        async with db_session() as session:
            async with session.begin():
                try:
                    # Send the message
                    mirrored_msg = await channel.send(
                        msg.content,
                        attachments=msg.attachments,
                        components=msg.components,
                        embeds=msg.embeds,
                    )
                    # Record the ids in the db
                    await MirroredMessage.add_msg_with_session(
                        dest_msg=mirrored_msg.id,
                        dest_channel=mirrored_msg.channel_id,
                        source_msg=msg.id,
                        source_channel=event.channel_id,
                        session=session,
                    )
                except Exception as e:
                    logging.exception(e)


async def message_update_repeater(event: h.MessageUpdateEvent):
    msg = event.message
    bot = event.app

    if not cfg.mirror_dict.get(msg.channel_id):
        # Return if this channel is not to be mirrored
        # ie if no mirror list found for it
        return

    msgs_to_update = await MirroredMessage.get_dest_msgs_and_channels(msg.id)

    for msg_id, channel_id in msgs_to_update:
        try:
            dest_msg = await bot.fetch_message(channel_id, msg_id)
            await dest_msg.edit(
                msg.content,
                attachments=msg.attachments,
                components=msg.components,
                embeds=msg.embeds,
            )
        except Exception as e:
            logging.exception(e)


def register(bot):
    for event_handler in [
        message_create_repeater,
        message_update_repeater,
    ]:
        bot.listen(event_handler)
