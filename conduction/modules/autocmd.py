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

from ..cfg import embed_default_color

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
