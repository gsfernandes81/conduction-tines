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
import typing as t

import hikari as h
import yarl

from ..bot import CachedFetchBot
from ..cfg import default_url, embed_default_color

_no_register = True


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
            multi_image_embed[0].add_field(
                field.name, field.value, inline=field.is_inline
            )

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
