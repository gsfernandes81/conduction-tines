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
import attr

# TEST CODE
from inspect import currentframe, getframeinfo

import hikari as h
import yarl

from ..bot import CachedFetchBot
from ..cfg import default_url, embed_default_color


class SimpleEmbed(h.Embed):
    def __init__(
        self,
        *,
        description: str,
        title: t.Optional[str] = None,
        url: t.Optional[str] = None,
        color: t.Optional[h.Colorish] = embed_default_color,
        timestamp: t.Optional[dt.datetime] = None,
        # Dict of fields with a name, value and inline (bool) key:
        fields: t.Optional[t.List[t.Dict[str, str | bool]]] = [],
        author: t.Optional[t.Dict[str, str]] = None,
        image: t.Optional[t.Tuple[str]] = [None],
        thumbnail: t.Optional[str] = None,
        # Dict with text and icon keys:
        footer: t.Optional[t.Dict[str, str]] = None,
    ):
        super().__init__(
            title=title,
            description=description,
            url=url,
            color=color,
            timestamp=timestamp,
        )

        for field in fields:
            self.add_field(*field)

        if author:
            self.set_author(**author)

        if image:
            self.set_image(image)

        if thumbnail:
            self.set_thumbnail(thumbnail)

        if footer:
            self.set_footer(**footer)


class MultiImageEmbedList(list):
    """A list of embeds with the same URL property and different image properties."""

    def __init__(
        self,
        *args,
        url: t.Optional[str] = default_url,
        designator: int = 0,
        images: list[str] = [],
        **kwargs,
    ):
        super().__init__()

        if kwargs.get("image"):
            raise ValueError(
                "Cannot set image property when using MultiImageEmbedList, "
                + "use images instead."
            )

        if not kwargs.get("description"):
            raise ValueError(
                "Must set description property when using MultiImageEmbedList."
            )

        if not kwargs.get("color") or kwargs.get("colour"):
            kwargs["color"] = embed_default_color

        embed = h.Embed(
            *args, url=str(yarl.URL(url) % {"designator": designator}), **kwargs
        )

        try:
            embed.set_image(images.pop(0))
        except IndexError:
            pass

        self.append(embed)

        for image in images:
            self.add_image(image)

    def add_image(self, image: str) -> t.Self:
        """Add an image to the MultiImageEmbedList instance."""
        if self[-1].image:
            embed = h.Embed(
                url=self[0].url,
                description="Masked description",
                color=embed_default_color,
            )
            embed.set_image(image)
            self.append(embed)
        else:
            self[-1].set_image(image)
        return self

    def add_images(self, images: list[str]) -> t.Self:
        """Add multiple images to the MultiImageEmbedList instance."""
        for image in images:
            self.add_image(image)
        return self

    @classmethod
    def from_embed(
        cls, embed: h.Embed, designator=0, images: t.Optional[t.List[str]] = []
    ) -> t.Self:
        # Create a MultiImageEmbed instance
        multi_image_embed: t.List[h.Embed] = cls(
            url=embed.url or default_url,
            designator=designator,
            description=embed.description,
            title=embed.title,
            color=embed.color or embed_default_color,
            timestamp=embed.timestamp,
        )

        if embed.image:
            multi_image_embed[0].set_image(embed.image.url)
        if embed.footer:
            multi_image_embed[0].set_footer(embed.footer.text, icon=embed.footer.icon)
        if embed.thumbnail:
            multi_image_embed[0].set_thumbnail(embed.thumbnail.url)
        if embed.author:
            multi_image_embed[0].set_author(
                name=embed.author.name, url=embed.author.url, icon=embed.author.icon
            )

        for field in embed.fields:
            multi_image_embed[0].add_field(field.name, field.value, inline=field.inline)

        # Loop through the image URLs and create and append new embeds with different image properties
        multi_image_embed.add_images(images)
        # Return the MultiImageEmbed instance
        return multi_image_embed


async def pull_messages_from_channel(
    bot: CachedFetchBot,
    after: dt.datetime,
    channel_id: h.Snowflake,
    before: dt.datetime | None = None,
):
    messages: t.List[h.Message] = []
    channel: h.TextableGuildChannel = await bot.fetch_channel(int(channel_id))

    if not before:
        before = dt.datetime.now(dt.timezone.utc)

    async for message in channel.fetch_history(after=after):
        if message.timestamp > before:
            break
        messages.append(message)

    return messages


@attr.s
class MessagePrototype:
    """A prototype for a message to be sent to a channel."""

    content: str = attr.ib(default="", converter=str)
    embeds: t.List[h.Embed] = attr.ib(default=attr.Factory(list))
    attachments: t.List[h.Attachment] = attr.ib(default=attr.Factory(list))

    @content.validator
    def _validate_content(self, attribute, value):
        if len(value) > 2000:
            raise ValueError(
                "Cannot send more than 2000 characters in a single message"
            )

    @embeds.validator
    def _validate_embeds(self, attribute, value):
        if len(value) > 10:
            raise ValueError("Cannot send more than 10 embeds in a single message")

    @attachments.validator
    def _validate_attachments(self, attribute, value):
        if len(value) > 10:
            raise ValueError("Cannot send more than 10 attachments in a single message")

    @classmethod
    def from_message(cls, message: h.Message) -> t.Self:
        """Create a MessagePrototype instance from a message."""
        return cls(
            content=message.content or "",
            embeds=message.embeds,
            attachments=message.attachments,
        )

    def to_message_kwargs(self) -> t.Dict[str, t.Any]:
        """Convert the MessagePrototype instance into a dict of kwargs to be passed to
        `hikari.Messageable.send`."""
        return {
            "content": self.content,
            "embeds": self.embeds,
            "attachments": self.attachments,
        }

    def __add__(self, other):
        if not isinstance(other, MessagePrototype):
            raise TypeError(
                f"Cannot add MessagePrototype to {other.__class__.__name__}"
            )

        return MessagePrototype(
            content=self.content + other.content,
            embeds=self.embeds + other.embeds,
            attachments=self.attachments + other.attachments,
        )

    def merge_content_into_embed(
        self, embed_no: int = 0, prepend: bool = True
    ) -> t.Self:
        """Merge the content of a message into the description of an embed.

        Args:
            embed_no (int, optional): The index of the embed to merge the content into.
            prepend (bool, optional): Whether to prepend the content to the embed description.
                If False, the content will be appended to the embed description. Defaults to True.
        """
        content = str(self.content or "")
        self.content = ""

        if not self.embeds:
            self.embeds = [h.Embed(description=content, color=embed_default_color)]
            return self

        embed_no = int(embed_no) % (len(self.embeds) or 1)

        if not isinstance(self.embeds[embed_no].description, str):
            self.embeds[embed_no].description = ""

        if prepend:
            self.embeds[embed_no].description = (
                content + "\n\n" + self.embeds[embed_no].description
            )
        else:
            self.embeds[embed_no].description = (
                self.embeds[embed_no].description + "\n\n" + content
            )

        return self

    def merge_embed_url_as_embed_image_into_embed(
        self, embed_no: int = 0, designator: int = 0
    ) -> t.Self:

        if not self.embeds:
            self.embeds = [h.Embed(color=embed_default_color)]

        embed_no = int(embed_no) % len(self.embeds)

        embed = self.embeds.pop(embed_no)
        embeds = MultiImageEmbedList.from_embed(
            embed,
            designator,
            [embed.url],
        )
        embeds[0].set_thumbnail(None)

        for embed in embeds[::-1]:
            self.embeds.insert(embed_no, embed)

        return self

    def merge_attachements_into_embed(
        self,
        embed_no: int = -1,
        designator: int = 0,
    ) -> t.Self:
        """Merge the attachments of a message into the embed.

        Args:
            embed_no (int, optional): The index of the embed to merge the attachments into.
            designator (int, optional): The designator to use for the embed. Defaults to 0.
        """
        if not self.embeds:
            self.embeds = [h.Embed(color=embed_default_color)]

        embed_no = int(embed_no) % len(self.embeds)

        embeds = MultiImageEmbedList.from_embed(
            self.embeds.pop(embed_no),
            designator,
            [
                attachment.url
                for attachment in self.attachments
                if str(attachment.media_type).startswith("image")
            ],
        )

        for embed in embeds[::-1]:
            self.embeds.insert(embed_no, embed)

        self.attachments = [
            attachment
            for attachment in self.attachments
            if not str(attachment.media_type).startswith("image")
        ]

        return self
