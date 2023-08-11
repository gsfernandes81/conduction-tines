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

from ..schemas import ServerStatistics


def setup_function(function):
    asyncio.run(schemas.recreate_all())


@pytest.mark.asyncio
async def test_add_server():
    server_id_1 = 1
    server_1_population = 10
    server_id_2 = 2
    server_2_population = 30

    await ServerStatistics.add_server(server_id_1, server_1_population)
    assert await ServerStatistics.fetch_server_populations() == [
        (server_id_1, server_1_population),
    ]

    await ServerStatistics.add_server(server_id_2, server_2_population)
    assert await ServerStatistics.fetch_server_populations() == [
        (server_id_1, server_1_population),
        (server_id_2, server_2_population),
    ]


@pytest.mark.asyncio
async def test_update_population():
    server_id_1 = 1
    server_1_population = 10
    server_1_population_2 = 20
    server_id_2 = 2
    server_2_population = 30

    await ServerStatistics.add_server(server_id_1, server_1_population)
    await ServerStatistics.add_server(server_id_2, server_2_population)

    await ServerStatistics.update_population(server_id_1, server_1_population_2)
    assert await ServerStatistics.fetch_server_populations() == [
        (server_id_1, server_1_population_2),
        (server_id_2, server_2_population),
    ]


@pytest.mark.asyncio
async def test_add_servers_in_batch():
    server_id_1 = 1
    server_1_population = 10
    server_id_2 = 2
    server_2_population = 30

    await ServerStatistics.add_servers_in_batch(
        (server_id_1, server_id_2), (server_1_population, server_2_population)
    )
    assert await ServerStatistics.fetch_server_populations() == [
        (server_id_1, server_1_population),
        (server_id_2, server_2_population),
    ]


@pytest.mark.asyncio
async def test_update_populations_in_batch():
    server_id_1 = 1
    server_1_population = 10
    server_1_population_2 = 20
    server_id_2 = 2
    server_2_population = 30
    server_2_population_2 = 40
    server_id_3 = 3
    server_3_population = 50

    await ServerStatistics.add_servers_in_batch(
        (server_id_1, server_id_2, server_id_3),
        (server_1_population, server_2_population, server_3_population),
    )
    await ServerStatistics.update_population_in_batch(
        (server_id_1, server_id_2),
        (server_1_population_2, server_2_population_2),
    )
    assert await ServerStatistics.fetch_server_populations() == [
        (server_id_1, server_1_population_2),
        (server_id_2, server_2_population_2),
        (server_id_3, server_3_population),
    ]
