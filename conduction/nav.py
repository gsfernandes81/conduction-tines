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
import abc
import datetime as dt
import typing as t
from asyncio import sleep
from random import randint

import hikari as h
import lightbulb as lb
import miru as m
from hmessage import HMessage as MessagePrototype
from lightbulb.ext import tasks
from miru.ext import nav

from . import utils
from .bot import CachedFetchBot
from .cfg import embed_default_color, reset_time_tolerance

NO_DATA_HERE_EMBED = h.Embed(title="No data here!", color=embed_default_color)


class DateRangeDict(t.Dict[dt.datetime, MessagePrototype]):
    """Dict with keys that are contiguous date ranges up to limits

    The keys of the backing dict are the start of the date ranges.
    The keys received by __getitem__ are rounded down to the nearest date
    provided it is within DateRangeDict.period: dt.timedelta
    If the key provided is an int, then it is interpreted as n periods
    since the current datetime rounded down.

    period: dt.timedelta
        The period between each key

    limits: t.Tuple[dt.datetime, dt.datetime]
        The upper and lower bounds of the dict"""

    def __init__(
        self,
        period: dt.timedelta,
        limits: t.Optional[t.Tuple[dt.datetime, dt.datetime]] = None,
    ):
        if not isinstance(period, dt.timedelta):
            raise TypeError("period must be of type datetime.timedelta")

        self.period = period

        if limits:
            if len(limits) != 2:
                raise ValueError("limits must be a tuple of length 2")

            if not all(isinstance(l, dt.datetime) for l in limits):
                raise TypeError("limits must be a tuple of datetime.datetime")

            if limits[0] > limits[1]:
                raise ValueError("limits[0] must be less than limits[1]")

            if limits[1] - limits[0] < period:
                raise ValueError("limits must be at least one period apart")

            if (limits[1] - limits[0]) % period != dt.timedelta(0):
                raise ValueError("limits must be an integer multiple of period apart")

            self.limits = limits

    def round_down(self, key: dt.datetime) -> dt.datetime:
        """Round down key to nearest period"""
        return ((key - self.limits[0]) // self.period) * self.period + self.limits[0]

    def index_to_date(self, index: int) -> dt.datetime:
        """Return the datetime of the period at <index>"""
        return (
            self.round_down(dt.datetime.now(tz=dt.timezone.utc)) + index * self.period
        )

    def __getitem__(self, key: dt.datetime | int) -> MessagePrototype:
        if isinstance(key, int):
            key = self.index_to_date(key)
        if not isinstance(key, dt.datetime):
            raise TypeError("Key must be of type datetime.datetime")

        if not (self.limits[0] <= key <= self.limits[1]):
            raise KeyError(f"Key {key} is not in range {self.limits}")

        self._truncate_outside_limits()
        key = self.round_down(key)
        return super().__getitem__(key)

    def __setitem__(self, key: dt.datetime, value: MessagePrototype) -> None:
        if not isinstance(key, dt.datetime):
            raise TypeError("Key must be of type datetime.datetime")

        if not (self.limits[0] <= key <= self.limits[1]):
            raise KeyError(f"Key {key} is not in range {self.limits}")

        self._truncate_outside_limits()
        key = self.round_down(key)
        super().__setitem__(key, value)

    def _truncate_outside_limits(self) -> None:
        """Remove all keys outside our limits"""
        for key in list(self.keys()):
            if not (self.limits[0] <= key <= self.limits[1]):
                self.pop(key)

    @staticmethod
    def nearest_limit_from_period_and_ref(period: dt.timedelta, ref: dt.datetime):
        """Return the nearest lower limit to ref that is an integer multiple of period"""
        if not isinstance(period, dt.timedelta):
            raise TypeError("period must be of type datetime.timedelta")

        if not isinstance(ref, dt.datetime):
            raise TypeError("ref must be of type datetime.datetime")

        now = dt.datetime.now(tz=dt.timezone.utc)
        return ((now - ref) // period) * period + ref


class NavigatorView(nav.NavigatorView):
    def __init__(
        self,
        *,
        pages: "NavPages",
        timeout: t.Optional[t.Union[float, int, dt.timedelta]] = 120,
        autodefer: bool = True,
    ) -> None:
        super().__init__(pages=pages, timeout=timeout, autodefer=autodefer)
        self._pages = pages
        # Set current page to the first non blank page
        while True:
            try:
                current_page = pages[self.current_page]
                if current_page.embeds and current_page.embeds[0] == NO_DATA_HERE_EMBED:
                    self.current_page = self.current_page - 1
                else:
                    break
            except KeyError:
                self.current_page = 0
                break

    async def send(
        self,
        to: t.Union[
            h.SnowflakeishOr[h.TextableChannel],
            h.MessageResponseMixin[t.Any],
        ],
        *,
        start_at: t.Optional[int] = None,
        ephemeral: bool = False,
        responded: bool = False,
    ):
        # Override the default page number of 0 with the current page as set by init
        return await super().send(
            to,
            start_at=start_at if start_at is not None else self.current_page,
            ephemeral=ephemeral,
            responded=responded,
        )

    def _get_page_payload(
        self, page: t.Union[str, h.Embed, t.Sequence[h.Embed], MessagePrototype]
    ) -> t.MutableMapping[str, t.Any]:
        """Get the page content that is to be sent."""

        if not isinstance(page, MessagePrototype):
            raise TypeError(
                f"Expected type 'MessagePrototype' to send as page, not '{page.__class__.__name__}'."
            )

        return_dict = page.to_message_kwargs()
        return_dict["components"] = self

        if self.ephemeral:
            return_dict["flags"] = h.MessageFlag.EPHEMERAL

        return return_dict

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
            if isinstance(button, nav.NavItem):
                await button.before_page_change()

        payload = self._get_page_payload(page)

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

    def get_default_buttons(self) -> t.Sequence[nav.NavButton]:
        return [PrevButton(), IndicatorButton(), NextButton()]

    @property
    def pages(self) -> "NavPages":
        """
        The pages that the navigator is navigating.
        """
        return self._pages

    @property
    def current_page(self) -> int:
        """
        The current page of the navigator, zero-indexed integer.
        """
        return self._current_page

    @current_page.setter
    def current_page(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("Expected type int for property current_page.")

        # Ensure this value is always correct
        self._current_page = max(
            -(self.pages.history_len - 1), min(value, self.pages.lookahead_len)
        )


class NavPages(DateRangeDict, abc.ABC):
    """Class to maintain a dict of slash command responses over time.

    The key for the dict is the datetime after which the response was posted
    and the value is the MessagePrototype instance for the response.
    Additionally the key also accepts an int and interprets it as n periods
    since the currrent datetime rounded down.

    __init__ registers tasks to update the dict regularly based on history_update_interval
    and lookahead_update_interval."""

    def __init__(
        self,
        channel: h.GuildNewsChannel,
        period: dt.timedelta,
        reference_date: dt.datetime,
        history_len: int = 7,
        lookahead_len: int = 0,
        lookahead_update_interval: int = 1800,
    ):
        super().__init__(period)
        self.history_len = history_len
        self.lookahead_len = lookahead_len
        self.channel = channel
        self.bot: CachedFetchBot = channel.app
        self.lookahead_update_interval = lookahead_update_interval

        self._reference_date = reference_date

    @property
    def limits(self) -> t.Tuple[dt.datetime, dt.datetime]:
        midpoint = self.nearest_limit_from_period_and_ref(
            period=self.period, ref=self._reference_date
        )
        limit_low = midpoint - self.period * (self.history_len - 1)
        limit_high = midpoint + self.period * self.lookahead_len
        return (limit_low, limit_high)

    @classmethod
    @abc.abstractmethod
    def preprocess_messages(
        cls, messages: t.List[MessagePrototype | h.Message]
    ) -> MessagePrototype:
        pass

    @classmethod
    async def from_channel(cls, bot: CachedFetchBot, channel, **kwargs) -> t.Self:
        if isinstance(channel, (int, h.Snowflake)):
            channel = await bot.fetch_channel(int(channel))

        if not isinstance(channel, h.GuildNewsChannel):
            raise TypeError(
                f"Cannot create {cls.__name__} from {channel.__class__.__name__} "
                + "since it is not an Announce channel"
            )

        self: t.Self = cls(channel, **kwargs)

        await self._populate_history()
        await self._update_lookahead()
        self._setup_autoupdate()

        return self

    async def _populate_history(self):
        # Find start time
        after = self.limits[0]

        # Bin messages into periods
        async for msg in self.channel.fetch_history(after=after - reset_time_tolerance):
            msg_time = msg.timestamp

            start_of_period = self.round_down(msg_time)

            if not self.get(start_of_period):
                self[start_of_period] = []

            self[start_of_period].append(msg)

        # Preprocess messages
        key = self.limits[0]
        while key <= self.limits[1]:
            if self.get(key):
                self[key] = self.preprocess_messages(self[key])
            else:
                self[key] = MessagePrototype(embeds=[NO_DATA_HERE_EMBED])
            key += self.period

    async def _update_history(self, event: h.MessageCreateEvent | h.MessageUpdateEvent):
        """Updates the history with any changes or new messages in self.channel"""
        try:
            if not event.channel_id == self.channel.id:
                return

            msg = event.message

            if not isinstance(msg, h.Message):
                msg = await self.bot.fetch_message(event.channel_id, msg)

            if not (self.limits[0] <= msg.timestamp <= self.limits[1]):
                return

            # Get all messages in this event's message's period
            from_ = self.round_down(msg.timestamp)
            until_ = from_ + self.period
            msgs_from_api = []
            async for msg_from_api in self.channel.fetch_history(after=from_):
                if msg_from_api.timestamp > until_:
                    break
                msgs_from_api.append(msg_from_api)

            self[from_] = self.preprocess_messages(msgs_from_api)

        except Exception as e:
            await utils.discord_error_logger(self.bot, e)

    async def _update_lookahead(self):
        if self.lookahead_len <= 0:
            return

        self.update(await self.lookahead(self.index_to_date(1)))

    def _setup_autoupdate(self):
        if self.history_len > 0:

            @self.bot.listen()
            async def history_updater(
                event: h.MessageCreateEvent | h.MessageUpdateEvent,
            ):
                await self._update_history(event)

        if self.lookahead_len > 0:

            @tasks.task(
                s=self.lookahead_update_interval,
                auto_start=True,
                wait_before_execution=False,
                pass_app=True,
            )
            async def lookahead_update_task(bot: lb.BotApp):
                try:
                    # Introduce a 5% jitter to the update interval
                    # to avoid ratelimit issues
                    await sleep(randint(0, int(self.lookahead_update_interval / 20)))
                    await self._update_lookahead()
                except Exception as e:
                    await utils.discord_error_logger(bot, e)

    async def lookahead(
        self, after: dt.datetime
    ) -> t.Dict[dt.datetime, MessagePrototype]:
        """Return the predicted messages for the periods after <after>

        The dict must have <self.lookahead_len> entries, indexed by the start of the
        period and must contain the MessagePrototype for that period."""
        return {}


class IndicatorButton(nav.IndicatorButton):
    """
    A built-in NavButton to indicate the current page.
    """

    def __init__(
        self,
        *,
        custom_id: t.Optional[str] = None,
        emoji: t.Union[h.Emoji, str, None] = None,
        row: t.Optional[int] = None,
    ):
        super().__init__(
            style=h.ButtonStyle.SECONDARY, custom_id=custom_id, emoji=emoji, row=row
        )

    async def callback(self, context: m.ViewContext) -> None:
        pass

    async def before_page_change(self) -> None:
        date = self.view.pages.index_to_date(self.view.current_page)
        suffix = utils.get_ordinal_suffix(date.day)
        self.label = f"{date.strftime('%B %-d')}{suffix}"


class NextButton(nav.NavButton):
    """
    A built-in NavButton to jump to the next page.
    """

    def __init__(
        self,
        *,
        style: t.Union[h.ButtonStyle, int] = h.ButtonStyle.PRIMARY,
        label: t.Optional[str] = None,
        custom_id: t.Optional[str] = None,
        emoji: t.Union[h.Emoji, str, None] = chr(9654),
        row: t.Optional[int] = None,
    ):
        super().__init__(
            style=style, label=label, custom_id=custom_id, emoji=emoji, row=row
        )

    async def callback(self, context: m.ViewContext) -> None:
        self.view.current_page += 1
        await self.view.send_page(context)

    async def before_page_change(self) -> None:
        if self.view.current_page >= self.view.pages.lookahead_len:
            self.disabled = True
        else:
            self.disabled = False


class PrevButton(nav.NavButton):
    """
    A built-in NavButton to jump to previous page.
    """

    def __init__(
        self,
        *,
        style: t.Union[h.ButtonStyle, int] = h.ButtonStyle.PRIMARY,
        label: t.Optional[str] = None,
        custom_id: t.Optional[str] = None,
        emoji: t.Union[h.Emoji, str, None] = chr(9664),
        row: t.Optional[int] = None,
    ):
        super().__init__(
            style=style, label=label, custom_id=custom_id, emoji=emoji, row=row
        )

    async def callback(self, context: m.ViewContext) -> None:
        self.view.current_page -= 1
        await self.view.send_page(context)

    async def before_page_change(self) -> None:
        if self.view.current_page <= 1 - self.view.pages.history_len:
            self.disabled = True
        else:
            self.disabled = False
