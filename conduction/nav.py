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

# Define our custom navigator class
import miru as m
import typing as t
import hikari

from miru.ext.nav import NavigatorView as _NavigatorView, NavItem


class NavigatorView(_NavigatorView):
    def _get_page_payload(
        self, page: t.Union[str, hikari.Embed, t.Sequence[hikari.Embed]]
    ) -> t.MutableMapping[str, t.Any]:
        """Get the page content that is to be sent."""

        content = page if isinstance(page, str) else ""
        if page and isinstance(page, t.Sequence) and isinstance(page[0], hikari.Embed):
            embeds = page
        else:
            embeds = [page] if isinstance(page, hikari.Embed) else []

        if not content and not embeds:
            raise TypeError(
                f"Expected type 'str' or 'hikari.Embed' to send as page, not '{page.__class__.__name__}'."
            )

        if self.ephemeral:
            return dict(
                content=content,
                embeds=embeds,
                components=self,
                flags=hikari.MessageFlag.EPHEMERAL,
            )
        else:
            return dict(content=content, embeds=embeds, components=self)

    async def send_page(
        self, context: m.Context[t.Any], page_index: t.Optional[int] = None
    ) -> None:
        """Send a page, editing the original message.

        Parameters
        ----------
        context : Context
            The context object that should be used to send this page
        page_index : Optional[int], optional
            The index of the page to send, if not specifed, sends the current page, by default None
        """
        if page_index is not None:
            self.current_page = page_index

        page = self.pages[self.current_page]

        for button in self.children:
            if isinstance(button, NavItem):
                await button.before_page_change()

        payload = self.get_page_payload(page)

        self._inter = context.interaction  # Update latest inter

        if not (payload.get("attachment") or payload.get("attachments")):
            # Ensure that payload does not have attachments as a key
            # even if it is a Falsey value
            payload.pop("attachments", None)
            # Set payload attachment to None if no attachments are returned
            # from _get_page_payload to make sure discord clears all atachments
            # in view.
            # Note: attachments=[] does not clear attachments.
            payload = {"attachment": None, **payload}

        await context.edit_response(**payload)
