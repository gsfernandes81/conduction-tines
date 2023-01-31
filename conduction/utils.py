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

import inspect
import logging
import typing as t

import aiohttp


def ensure_session(sessionmaker):
    """Decorator for functions that optionally want an sqlalchemy async session

    Provides an async session via the `session` parameter if one is not already
    provided via the same.

    Caution: Always put below `@classmethod` and `@staticmethod`"""

    def ensured_session(f: t.Coroutine):
        async def wrapper(*args, **kwargs):
            session = kwargs.pop("session", None)
            if session is None:
                async with sessionmaker() as session:
                    async with session.begin():
                        return await f(*args, **kwargs, session=session)
            else:
                return await f(*args, **kwargs, session=session)

        return wrapper

    return ensured_session


async def follow_link_single_step(
    url: str, logger=logging.getLogger("main/" + __name__)
) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, allow_redirects=False) as resp:
            try:
                return resp.headers["Location"]
            except KeyError:
                # If we can't find the location key, warn and return the
                # provided url itself
                logger.info(
                    "Could not find redirect for url "
                    + "{}, returning as is".format(url)
                )
                return url


class FriendlyValueError(ValueError):
    pass


def get_function_name() -> str:
    """Get the name of the function this was called from"""
    return inspect.stack()[1][3]
