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

import asyncio

import pytest
from . import schemas
import sqlalchemy.exc

from .schemas import MirroredChannel
from .utils import get_function_name


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def setup_function():
    asyncio.run(schemas.recreate_all())


@pytest.mark.asyncio
async def test_add_and_fetch_mirror():
    src_id = 0
    dest_id = 1
    dest_id_2 = 2

    await MirroredChannel.add_mirror(src_id, dest_id, legacy=True)

    async with schemas.db_session() as session:
        async with session.begin():
            assert [src_id] == await MirroredChannel.fetch_srcs(
                dest_id, legacy=None, session=session
            )
            assert [src_id] == await MirroredChannel.fetch_srcs(
                dest_id, session=session
            )
            assert [] == await MirroredChannel.fetch_srcs(
                dest_id, legacy=False, session=session
            )
            assert [dest_id] == await MirroredChannel.fetch_dests(
                src_id, legacy=None, session=session
            )
            assert [dest_id] == await MirroredChannel.fetch_dests(
                src_id, session=session
            )
            assert [] == await MirroredChannel.fetch_dests(
                src_id, legacy=False, session=session
            )

            await MirroredChannel.add_mirror(
                src_id, dest_id_2, legacy=False, session=session
            )

            assert [src_id] == await MirroredChannel.fetch_srcs(
                dest_id_2, legacy=False, session=session
            )
            assert [] == await MirroredChannel.fetch_srcs(dest_id_2, session=session)
            assert [src_id] == await MirroredChannel.fetch_srcs(
                dest_id_2, legacy=None, session=session
            )
            assert [dest_id, dest_id_2] == await MirroredChannel.fetch_dests(
                src_id, legacy=None, session=session
            )
            assert [dest_id] == await MirroredChannel.fetch_dests(
                src_id, session=session
            )
            assert [dest_id_2] == await MirroredChannel.fetch_dests(
                src_id, legacy=False, session=session
            )


@pytest.mark.asyncio
async def test_remove_mirror():
    src_id = 0
    dest_id = 1
    dest_id_2 = 2

    await MirroredChannel.add_mirror(src_id, dest_id, legacy=True)
    await MirroredChannel.add_mirror(src_id, dest_id_2, legacy=True)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id_2)
    assert [dest_id, dest_id_2] == await MirroredChannel.fetch_dests(src_id)

    await MirroredChannel.remove_mirror(src_id, dest_id)
    assert dest_id not in await MirroredChannel.fetch_dests(src_id)


@pytest.mark.asyncio
async def test_remove_all_mirrors():
    src_id = 0
    src_id_2 = 1
    dest_id = 2

    await MirroredChannel.add_mirror(src_id, dest_id, legacy=True)
    await MirroredChannel.add_mirror(src_id_2, dest_id, legacy=True)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id_2)
    assert [src_id, src_id_2] == await MirroredChannel.fetch_srcs(dest_id)

    await MirroredChannel.remove_all_mirrors(dest_id)
    assert [] == await MirroredChannel.fetch_srcs(dest_id)


@pytest.mark.asyncio
async def test_add_duplicate_mirror():
    src_id = 0
    dest_id = 1

    await MirroredChannel.add_mirror(src_id, dest_id, legacy=True)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id)

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await MirroredChannel.add_mirror(src_id, dest_id, legacy=True)

    assert [dest_id] == await MirroredChannel.fetch_dests(src_id)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id)


@pytest.mark.asyncio
async def test_count_dests():
    src_id = 0
    src_id_2 = 1
    dest_id = 2

    await MirroredChannel.add_mirror(src_id, dest_id, legacy=True)
    await MirroredChannel.add_mirror(src_id_2, dest_id, legacy=True)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id_2)
    assert [src_id, src_id_2] == await MirroredChannel.fetch_srcs(dest_id)

    await MirroredChannel.remove_all_mirrors(dest_id)
    assert [] == await MirroredChannel.fetch_srcs(dest_id)
