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
import sqlalchemy as sql

from .schemas import UserCommand
from .utils import get_function_name


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def setup_function():
    asyncio.run(schemas.recreate_all())


@pytest.fixture(scope="function")
def invalid_command_names():
    # Test the following in command names
    # Capital first letter
    # Names longer than 32 chars
    # Names with *
    # Names with spaces
    # Names with !
    # Names with ,
    # Names with .
    return [
        "P",
        "Pizza",
        "pizzapizzapizzapizzapizzapizzapiz",
        "p*zza",
        "*pizza",
        "pizza*",
        "pizza pizza",
        " pizza",
        "pizza ",
        "pizza!",
        "!pizza",
        "pi,zza",
        ",pizza",
        "pizza,",
        "pi.zza",
        "pizza.",
        ".pizza",
    ]


@pytest.mark.asyncio
async def test_add_and_fetch_command():
    cmd_name = "testl1"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    await UserCommand.add_command(
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )

    cmd = await UserCommand.fetch_command(cmd_name)
    assert cmd.description == desc
    assert cmd.response_type == response_type
    assert cmd.response_data == response_data


@pytest.mark.asyncio
async def test_delete_command():
    cmd_name = "testl1"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    await UserCommand.add_command(
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )

    cmd1 = await UserCommand.delete_command(cmd_name)

    assert cmd1.description == desc
    assert cmd1.response_type == response_type
    assert cmd1.response_data == response_data

    cmd2 = await UserCommand.fetch_command(cmd_name)
    assert not cmd2


@pytest.mark.asyncio
async def test_add_duplicate_command():
    cmd_name = "testl1"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    with pytest.raises(schemas.utils.FriendlyValueError):
        # Adding a command with a duplicate name should raise
        # a custom value error
        for i in range(2):
            await UserCommand.add_command(
                cmd_name,
                description=desc + "_" + str(i + 1),
                response_type=response_type + i,
                response_data=response_data + " " + str(i + 1),
            )
    # Make sure the exception was raised on the second run of
    # the method
    assert i + 1 == 2


@pytest.mark.asyncio
async def test_add_and_fetch_cmd_group():
    cmd_name = "testl1g"
    desc = get_function_name()

    await UserCommand.add_command_group(cmd_name, description=desc)

    cmd = await UserCommand.fetch_command_group(cmd_name)
    assert cmd.description == desc
    assert cmd.response_type == 0


@pytest.mark.asyncio
async def test_fetch_cmd_group_with_fetch_command():
    # Test that fetching a command with the name of the command group
    # returns None to prevent undefined behaviour and enforce the use
    # of fetch_command_group for command groups
    cmd_name = "testl1g"
    desc = get_function_name()

    await UserCommand.add_command_group(cmd_name, description=desc)
    assert (await UserCommand.fetch_command(cmd_name)) is None


@pytest.mark.asyncio
async def test_fetch_cmd_with_fetch_command_group():
    cmd_name = "testl1"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    await UserCommand.add_command(
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )

    assert (await UserCommand.fetch_command_group(cmd_name)) is None


@pytest.mark.asyncio
async def test_invalid_command_name(invalid_command_names):
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Control test to make sure add_command isn't throwing errors on valid
    # command names
    await UserCommand.add_command(
        "pizza",
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )

    for cmd_name in invalid_command_names:
        with pytest.raises(schemas.utils.FriendlyValueError):
            await UserCommand.add_command(
                cmd_name,
                description=desc,
                response_type=response_type,
                response_data=response_data,
            )


@pytest.mark.asyncio
async def test_invalid_command_group_name(invalid_command_names):
    desc = get_function_name()

    # Control test to make sure add_command isn't throwing errors on valid
    # command names
    await UserCommand.add_command_group(
        "pizza",
        description=desc,
    )

    for cmd_name in invalid_command_names:
        with pytest.raises(schemas.utils.FriendlyValueError):
            await UserCommand.add_command_group(
                cmd_name,
                description=desc,
            )


@pytest.mark.asyncio
async def test_add_blank_command_name():
    cmd_name = ""
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Control test to make sure add_command isn't throwing errors on valid
    # command names
    with pytest.raises(schemas.utils.FriendlyValueError):
        await UserCommand.add_command(
            cmd_name,
            description=desc,
            response_type=response_type,
            response_data=response_data,
        )
    with pytest.raises(schemas.utils.FriendlyValueError):
        await UserCommand.add_command_group(
            cmd_name,
            description=desc,
        )


@pytest.mark.asyncio
async def test_delete_empty_command_group_no_cascade():
    cmd_name = "testlg1"
    desc = get_function_name()

    # Add and check cmd group added
    await UserCommand.add_command_group(cmd_name, description=desc)
    cmd1 = await UserCommand.fetch_command_group(cmd_name)
    assert cmd1.l1_name == cmd_name
    assert cmd1.description == desc

    # Delete and check right cmd group deleted
    cmd2 = (await UserCommand.delete_command_group(cmd_name, cascade=False))[0]
    assert cmd2.l1_name == cmd_name
    assert cmd2.description == desc

    # Check deleted cmd group not fetchable
    cmd3 = await UserCommand.fetch_command_group(cmd_name)
    assert not cmd3


@pytest.mark.asyncio
async def test_delete_non_empty_command_group_no_cascade():
    cmd_group_name = "testlg1"
    cmd_name = "testl2"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Add and check cmd group added
    await UserCommand.add_command_group(cmd_group_name, description=desc)
    cmd1 = await UserCommand.fetch_command_group(cmd_group_name)
    assert cmd1.l1_name == cmd_group_name
    assert cmd1.description == desc

    # Add and check sub cmd added to group
    await UserCommand.add_command(
        cmd_group_name,
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )
    cmd2 = await UserCommand.fetch_command(cmd_group_name, cmd_name)
    assert (cmd2.l1_name, cmd2.l2_name) == (cmd_group_name, cmd_name)
    assert cmd2.description == desc

    with pytest.raises(schemas.utils.FriendlyValueError):
        # Deleting non empty command without cascade should raise an error
        await UserCommand.delete_command_group(cmd_group_name, cascade=False)


@pytest.mark.asyncio
async def test_delete_empty_command_group_cascade():
    cmd_group_name = "testlg1"
    cmd_name = "testl2"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Add and check cmd group added
    await UserCommand.add_command_group(cmd_group_name, description=desc)
    cmd1 = await UserCommand.fetch_command_group(cmd_group_name)
    assert cmd1.l1_name == cmd_group_name
    assert cmd1.description == desc

    # Add and check sub cmd added to group
    await UserCommand.add_command(
        cmd_group_name,
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )
    cmd2 = await UserCommand.fetch_command(cmd_group_name, cmd_name)
    assert (cmd2.l1_name, cmd2.l2_name) == (cmd_group_name, cmd_name)
    assert cmd2.description == desc

    # Deleting non empty command with cascade should delete subcommands
    await UserCommand.delete_command_group(cmd_group_name, cascade=True)
    cmd3 = await UserCommand.fetch_command(cmd_group_name, cmd_name)
    assert not cmd3
    cmd4 = await UserCommand.fetch_command_group(cmd_group_name)
    assert not cmd4


@pytest.mark.asyncio
async def test_delete_non_empty_command_group_cascade():
    cmd_group_name = "testlg1"
    cmd_name = "testl2"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Add and check cmd group added
    await UserCommand.add_command_group(cmd_group_name, description=desc)
    cmd1 = await UserCommand.fetch_command_group(cmd_group_name)
    assert cmd1.l1_name == cmd_group_name
    assert cmd1.description == desc

    # Add and check sub cmd added to group
    await UserCommand.add_command(
        cmd_group_name,
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )
    cmd2 = await UserCommand.fetch_command(cmd_group_name, cmd_name)
    assert (cmd2.l1_name, cmd2.l2_name) == (cmd_group_name, cmd_name)
    assert cmd2.description == desc

    # Deleting non empty command with cascade should not raise an error
    await UserCommand.delete_command_group(cmd_group_name, cascade=True)

    # Check if all commands deleted
    assert not (await UserCommand.fetch_command_group(cmd_group_name))
    assert not (await UserCommand.fetch_command(cmd_group_name, cmd_name))


@pytest.mark.asyncio
async def test_add_command_to_nonexistant_group():
    cmd_group_name = "testlg1"
    cmd_name = "testl2"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Check that cmd_group_name is not an existing command group
    assert not await UserCommand.fetch_command_group(cmd_group_name)

    # Add and check sub cmd added to group
    with pytest.raises(schemas.utils.FriendlyValueError):
        await UserCommand.add_command(
            cmd_group_name,
            cmd_name,
            description=desc,
            response_type=response_type,
            response_data=response_data,
        )

    # Check to make sure command isn't added
    assert not await UserCommand.fetch_command(cmd_group_name, cmd_name)


@pytest.mark.asyncio
async def test_add_command_group_to_nonexistant_group():
    cmd_group_name = "testlg1"
    cmd_name = "testl2"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Check that cmd_group_name is not an existing command group
    assert not await UserCommand.fetch_command_group(cmd_group_name)

    # Add and check sub cmd added to group
    with pytest.raises(schemas.utils.FriendlyValueError):
        await UserCommand.add_command(
            cmd_group_name,
            cmd_name,
            description=desc,
            response_type=response_type,
            response_data=response_data,
        )

    # Check to make sure command isn't added
    assert not await UserCommand.fetch_command(cmd_group_name, cmd_name)


@pytest.mark.asyncio
async def test_fetch_all_command_groups():
    cmd_group_name = "testlg1"
    cmd_name = "testl2"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Add and check cmd group added
    await UserCommand.add_command_group(cmd_group_name, description=desc)
    await UserCommand.add_command_group(
        cmd_group_name, cmd_group_name, description=desc
    )
    cmd1 = await UserCommand.fetch_command_group(cmd_group_name)
    assert cmd1.l1_name == cmd_group_name
    assert cmd1.description == desc
    cmd2 = await UserCommand.fetch_command_group(cmd_group_name, cmd_group_name)
    assert cmd2.l1_name == cmd_group_name
    assert cmd2.description == desc

    # Add and check sub cmd added to group
    await UserCommand.add_command(
        cmd_group_name,
        cmd_group_name,
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )
    cmd2 = await UserCommand.fetch_command(cmd_group_name, cmd_group_name, cmd_name)
    assert (cmd2.l1_name, cmd2.l2_name, cmd2.l3_name) == (
        cmd_group_name,
        cmd_group_name,
        cmd_name,
    )
    assert cmd2.description == desc

    cmd_groups = await UserCommand.fetch_command_groups()
    for cmd_group in cmd_groups:
        # Check that only command groups are returned
        assert cmd_group.response_type == 0
        assert cmd_group.l3_name == ""

    # Check that the lower level groups are returned first
    assert cmd_groups[0].l1_name == cmd_group_name
    assert cmd_groups[0].l2_name == ""
    assert cmd_groups[1].l1_name == cmd_group_name
    assert cmd_groups[1].l2_name == cmd_group_name
    # Check that we only have 2 returns
    assert len(cmd_groups) == 2


@pytest.mark.asyncio
async def test_fetch_all_commands():
    cmd_group_name = "testlg1"
    cmd_name = "testl2"
    desc = get_function_name()
    response_type = 1
    response_data = "Hello"

    # Add and check cmd group added
    await UserCommand.add_command_group(cmd_group_name, description=desc)
    await UserCommand.add_command_group(
        cmd_group_name, cmd_group_name, description=desc
    )
    cmd1 = await UserCommand.fetch_command_group(cmd_group_name)
    assert cmd1.l1_name == cmd_group_name
    assert cmd1.description == desc
    cmd2 = await UserCommand.fetch_command_group(cmd_group_name, cmd_group_name)
    assert cmd2.l1_name == cmd_group_name
    assert cmd2.description == desc

    # Add and check sub cmd added to group
    await UserCommand.add_command(
        cmd_group_name,
        cmd_group_name,
        cmd_name,
        description=desc,
        response_type=response_type,
        response_data=response_data,
    )
    cmd2 = await UserCommand.fetch_command(cmd_group_name, cmd_group_name, cmd_name)
    assert (cmd2.l1_name, cmd2.l2_name, cmd2.l3_name) == (
        cmd_group_name,
        cmd_group_name,
        cmd_name,
    )
    assert cmd2.description == desc

    cmds = await UserCommand.fetch_commands()
    assert len(cmds) == 1
    assert cmds[0].l1_name == cmd2.l1_name
    assert cmds[0].l2_name == cmd2.l2_name
    assert cmds[0].l3_name == cmd2.l3_name
    assert cmds[0].response_type != 0
