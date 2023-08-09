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
from .. import schemas

from ..schemas import MirroredChannel as _MirroredChannel, ServerStatistics


def setup_function():
    asyncio.run(schemas.recreate_all())


@pytest.fixture()
def MirroredChannel():
    # Clear the cache before each test
    _MirroredChannel._dests_cache.clear()
    yield _MirroredChannel


async def assert_all_srcs_equals(
    src_list: list | set, mirrored_channel: _MirroredChannel = None
):
    src_list = set(src_list)
    assert src_list == await mirrored_channel.fetch_all_srcs()
    assert src_list == await mirrored_channel.fetch_all_srcs(legacy=True)
    assert src_list == await mirrored_channel.get_or_fetch_all_srcs()
    assert src_list == await mirrored_channel.get_or_fetch_all_srcs(legacy=True)


@pytest.mark.asyncio
async def test_add_and_fetch_mirror(MirroredChannel):
    src_id = 0
    dest_id = 1
    dest_id_2 = 2
    guild_id = 3

    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)

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
            assert [dest_id] == await MirroredChannel.get_or_fetch_dests(
                src_id, session=session
            )
            assert [] == await MirroredChannel.fetch_dests(
                src_id, legacy=False, session=session
            )

            await MirroredChannel.add_mirror(
                src_id, dest_id_2, guild_id, legacy=False, session=session
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
            assert [dest_id] == await MirroredChannel.get_or_fetch_dests(
                src_id, session=session
            )
            assert [dest_id_2] == await MirroredChannel.fetch_dests(
                src_id, legacy=False, session=session
            )


@pytest.mark.asyncio
async def test_remove_mirror(MirroredChannel):
    src_id = 0
    dest_id = 1
    dest_id_2 = 2
    guild_id = 3

    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)
    await MirroredChannel.add_mirror(src_id, dest_id_2, guild_id, legacy=True)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id_2)
    assert [dest_id, dest_id_2] == await MirroredChannel.fetch_dests(src_id)
    assert [dest_id, dest_id_2] == await MirroredChannel.get_or_fetch_dests(src_id)

    await MirroredChannel.remove_mirror(src_id, dest_id)
    assert dest_id not in await MirroredChannel.fetch_dests(src_id)
    assert dest_id not in await MirroredChannel.get_or_fetch_dests(src_id)


@pytest.mark.asyncio
async def test_remove_all_mirrors(MirroredChannel):
    src_id = 0
    src_id_2 = 1
    dest_id = 2
    guild_id = 3

    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)
    await MirroredChannel.add_mirror(src_id_2, dest_id, guild_id, legacy=True)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id_2)
    assert [dest_id] == await MirroredChannel.get_or_fetch_dests(src_id)
    assert [dest_id] == await MirroredChannel.get_or_fetch_dests(src_id_2)
    assert [src_id, src_id_2] == await MirroredChannel.fetch_srcs(dest_id)

    await MirroredChannel.remove_all_mirrors(dest_id)
    assert [] == await MirroredChannel.fetch_srcs(dest_id)


@pytest.mark.asyncio
async def test_add_duplicate_mirror(MirroredChannel):
    # Note, this should not raise an error since
    # add_mirror uses merge instead of add
    src_id = 0
    dest_id = 1
    guild_id = 2

    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id)
    assert [dest_id] == await MirroredChannel.get_or_fetch_dests(src_id)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id)

    # Errors here indicate that there was an issue merging
    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)

    # Duplicates here should not show up
    assert [dest_id] == await MirroredChannel.fetch_dests(src_id)
    assert [dest_id] == await MirroredChannel.get_or_fetch_dests(src_id)
    assert [src_id] == await MirroredChannel.fetch_srcs(dest_id)


@pytest.mark.asyncio
async def test_count_dests(MirroredChannel):
    src_id = 0
    src_id_2 = 1
    dest_id = 2
    dest_id_2 = 3
    guild_id = 4

    assert 0 == await MirroredChannel.count_dests(src_id)
    assert 0 == await MirroredChannel.count_dests(src_id_2)
    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)
    await MirroredChannel.add_mirror(src_id_2, dest_id, guild_id, legacy=True)
    assert 1 == await MirroredChannel.count_dests(src_id)
    assert 1 == await MirroredChannel.count_dests(src_id_2)
    assert 0 == await MirroredChannel.count_dests(dest_id)
    await MirroredChannel.add_mirror(src_id, dest_id_2, guild_id, legacy=True)
    assert 2 == await MirroredChannel.count_dests(src_id)
    assert 1 == await MirroredChannel.count_dests(src_id_2)
    assert 0 == await MirroredChannel.count_dests(dest_id)
    assert 0 == await MirroredChannel.count_dests(dest_id_2)


@pytest.mark.asyncio
async def test_order_fetch_by_server_size(MirroredChannel: _MirroredChannel):
    src_id = 0

    dest_id_1 = 1
    guild_id_1 = 1
    low_pop = 1 * 10**6

    dest_id_2 = 2
    guild_id_2 = 2
    medium_pop = 2 * 10**6

    dest_id_3 = 3
    guild_id_3 = 3
    high_pop = 3 * 10**6

    async def add_mirror(src_id, dest_id, guild_id, pop=None):
        await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)
        if pop:
            await ServerStatistics.add_server(guild_id, pop)
        else:
            await ServerStatistics.add_server(guild_id)

    await add_mirror(src_id, dest_id_1, guild_id_1, low_pop)
    await add_mirror(src_id, dest_id_2, guild_id_2, medium_pop)
    # Ensure the default value for guild_id_3 is the largest
    await add_mirror(src_id, dest_id_3, guild_id_3)

    dests_in_order = await MirroredChannel.fetch_dests(src_id)
    assert dests_in_order == [
        dest_id_3,
        dest_id_2,
        dest_id_1,
    ]

    # Stop using the default value for guild_id_3
    await ServerStatistics.update_population(guild_id_3, high_pop)

    await ServerStatistics.update_population(guild_id_1, high_pop + 1)
    dests_in_order = await MirroredChannel.fetch_dests(src_id)
    assert dests_in_order == [
        dest_id_1,
        dest_id_3,
        dest_id_2,
    ]

    await ServerStatistics.update_population_in_batch(
        [
            guild_id_3,
            guild_id_2,
            guild_id_1,
        ],
        [
            low_pop,
            medium_pop,
            high_pop,
        ],
    )
    dests_in_order = await MirroredChannel.fetch_dests(src_id)
    assert dests_in_order == [
        dest_id_1,
        dest_id_2,
        dest_id_3,
    ]


@pytest.mark.asyncio
async def test_add_and_fetch_mirror_srcs_cache(MirroredChannel: _MirroredChannel):
    src_id = 0
    src_id_2 = 4
    dest_id = 1
    dest_id_2 = 2
    guild_id = 3

    await assert_all_srcs_equals([], mirrored_channel=MirroredChannel)

    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)

    await MirroredChannel.add_mirror(src_id, dest_id_2, guild_id, legacy=True)
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)

    await MirroredChannel.add_mirror(src_id_2, dest_id_2, guild_id, legacy=False)
    # Added non legacy mirror, so should not be in cache
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)

    await MirroredChannel.add_mirror(src_id_2, dest_id, guild_id, legacy=True)
    # Added legacy mirror, so should be in cache
    await assert_all_srcs_equals([src_id, src_id_2], mirrored_channel=MirroredChannel)


@pytest.mark.asyncio
async def test_set_legacy_with_mirror_dests_cache(MirroredChannel: _MirroredChannel):
    src_id = 0
    dest_id = 1
    dest_id_2 = 5
    guild_id = 2

    await assert_all_srcs_equals([], mirrored_channel=MirroredChannel)

    await MirroredChannel.add_mirror(src_id, dest_id, guild_id, legacy=True)
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)

    await MirroredChannel.set_legacy(src_id, dest_id, True)
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)

    await MirroredChannel.add_mirror(src_id, dest_id_2, guild_id, legacy=True)
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)

    await MirroredChannel.set_legacy(src_id, dest_id, False)
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)

    await MirroredChannel.set_legacy(src_id, dest_id, True)
    await assert_all_srcs_equals([src_id], mirrored_channel=MirroredChannel)
