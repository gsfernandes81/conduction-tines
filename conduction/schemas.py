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

from __future__ import annotations

import asyncio
import datetime as dt
from collections import defaultdict
from typing import List

import regex as re
from pytz import utc
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, validates
from sqlalchemy.sql.expression import and_, delete, select, update
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import CheckConstraint, Column, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, DateTime, Integer, String, Text

from . import cfg, utils

Base = declarative_base()
db_engine = create_async_engine(cfg.db_url_async, connect_args=cfg.db_connect_args)
db_session = sessionmaker(db_engine, **cfg.db_session_kwargs)


rgx_cmd_name_is_valid = re.compile("^[a-z][a-z0-9_-]{1,31}$")
rgx_sub_cmd_name_is_valid = re.compile("^[a-z]{0,1}[a-z0-9_-]{0,31}$")
# The difference between command and sub command name validator regexes is
# that the sub command regex needs to allow blank strings to indicate and
# match blanks for commands that aren't 3 layers deep (where the last and)
# potentially the second last layer will be blank


class MirroredChannel(Base):
    """Cache enabled mirror channels model

    Cache only implemented for fetches with src_id for legacy mirrors
    with the get_dests method and invalidated on additions and deletions"""

    __tablename__ = "mirrored_channel"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (UniqueConstraint("src_id", "dest_id", name="_mir_ids_uc"),)
    src_id = Column("src_id", BigInteger, primary_key=True)
    dest_id = Column("dest_id", BigInteger, primary_key=True)
    legacy = Column("legacy", Boolean)
    _dests_cache = defaultdict(list)

    def __init__(self, src_id: int, dest_id: int, legacy: bool):
        super().__init__()
        self.src_id = int(src_id)
        self.dest_id = int(dest_id)
        self.legacy = bool(legacy)

    @classmethod
    @utils.ensure_session(db_session)
    async def add_mirror(cls, src_id: int, dest_id: int, legacy: bool, session=None):
        src_id = int(src_id)
        dest_id = int(dest_id)
        await session.merge(cls(src_id, dest_id, legacy))
        if legacy and dest_id not in cls._dests_cache[src_id]:
            cls._dests_cache[src_id].append(dest_id)

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_dests(
        cls, src_id: int, legacy: bool | None = True, session=None
    ) -> List[MirroredChannel]:
        src_id = int(src_id)
        dests = (
            await session.execute(
                select(cls).where(
                    and_(
                        cls.src_id == src_id,
                        (cls.legacy == legacy) if legacy is not None else True,
                    )
                )
            )
        ).fetchall()
        dests = dests if dests else []
        dests = [dest[0].dest_id for dest in dests]
        return dests

    @classmethod
    @utils.ensure_session(db_session)
    async def get_or_fetch_dests(cls, src_id: int, session=None) -> List[int]:
        src_id = int(src_id)
        if cls._dests_cache[src_id]:
            return cls._dests_cache[src_id]
        else:
            dests = await cls.fetch_dests(src_id, session=session)
            cls._dests_cache[src_id] = dests
            return dests

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_srcs(
        cls, dest_id: int, legacy: bool | None = True, session=None
    ) -> List[MirroredChannel]:
        dest_id = int(dest_id)
        srcs = (
            await session.execute(
                select(cls).where(
                    and_(
                        cls.dest_id == dest_id,
                        (cls.legacy == legacy) if legacy is not None else True,
                    )
                )
            )
        ).fetchall()
        srcs = srcs if srcs else []
        srcs = [src[0].src_id for src in srcs]
        return srcs

    @classmethod
    @utils.ensure_session(db_session)
    async def count_dests(
        cls, src_id: int, legacy_only: bool | None = True, session=None
    ) -> int:
        src_id = int(src_id)
        dests_count = (
            await session.execute(
                select(func.count())
                .select_from(cls)
                .where(
                    and_(
                        cls.src_id == src_id,
                        (cls.legacy == legacy_only)
                        if legacy_only is not None
                        else True,
                    )
                )
            )
        ).scalars()
        return dests_count

    @classmethod
    @utils.ensure_session(db_session)
    async def set_legacy(
        cls, src_id: int, dest_id: int, legacy: bool = True, session=None
    ) -> None:
        src_id = int(src_id)
        dest_id = int(dest_id)
        await session.execute(
            update(cls)
            .where(and_(cls.src_id == src_id, cls.dest_id == dest_id))
            .values(legacy=legacy)
        )
        if legacy:
            cls._dests_cache[src_id].append(dest_id)
        else:
            cls._dests_cache[src_id].remove(dest_id)

    @classmethod
    @utils.ensure_session(db_session)
    async def remove_mirror(cls, src_id: int, dest_id: int, session=None) -> None:
        src_id = int(src_id)
        dest_id = int(dest_id)
        await session.execute(
            delete(cls).where(and_(cls.src_id == src_id, cls.dest_id == dest_id))
        )
        try:
            cls._dests_cache[src_id].remove(dest_id)
        except ValueError:
            pass

    @classmethod
    @utils.ensure_session(db_session)
    async def remove_all_mirrors(cls, dest_id: int, session=None) -> None:
        dest_id = int(dest_id)
        src_ids = await cls.fetch_srcs(dest_id)
        await session.execute(delete(cls).where(and_(cls.dest_id == dest_id)))
        for src_id in src_ids:
            try:
                cls._dests_cache[src_id].remove(dest_id)
            except ValueError:
                pass


class MirroredMessage(Base):
    __tablename__ = "mirrored_message"
    __mapper_args__ = {"eager_defaults": True}
    dest_msg = Column("dest_msg", BigInteger, primary_key=True)
    dest_channel = Column("dest_ch", BigInteger)
    source_msg = Column("source_msg", BigInteger)
    source_channel = Column("src_ch", BigInteger)
    creation_datetime = Column("creation_datetime", DateTime)

    def __init__(
        self,
        dest_msg: int,
        dest_channel: int,
        source_msg: int,
        source_channel: int,
        creation_datetime: dt.datetime | None = None,
    ):
        super().__init__()
        self.dest_msg = int(dest_msg)
        self.dest_channel = int(dest_channel)
        self.source_msg = int(source_msg)
        self.source_channel = int(source_channel)
        self.creation_datetime = creation_datetime or dt.datetime.now(tz=utc)

    @classmethod
    @utils.ensure_session(db_session)
    async def add_msg(
        cls,
        dest_msg: int,
        dest_channel: int,
        source_msg: int,
        source_channel: int,
        session=None,
    ):
        """Create a session, begin it and add a message pair"""
        dest_msg = int(dest_msg)
        dest_channel = int(dest_channel)
        source_msg = int(source_msg)
        source_channel = int(source_channel)
        message_pair = cls(dest_msg, dest_channel, source_msg, source_channel)
        session.add(message_pair)
        return message_pair

    @classmethod
    @utils.ensure_session(db_session)
    async def get_dest_msgs_and_channels(
        cls,
        source_msg: int,
        session=None,
    ):
        """Return dest message and channel ids from source message id"""
        source_msg = int(source_msg)
        dest_msgs = (
            await session.execute(
                select(cls.dest_msg, cls.dest_channel).where(
                    cls.source_msg == source_msg
                )
            )
        ).fetchall()
        # Handle source_id not found
        dest_msgs = [] if dest_msgs is None else dest_msgs
        return dest_msgs

    @classmethod
    @utils.ensure_session(db_session)
    async def prune(
        cls, age: None | dt.timedelta = dt.timedelta(days=21), session=None
    ):
        """Delete entries older than <age>"""
        await session.execute(
            delete(cls).where(dt.datetime.now(tz=utc) - age > cls.creation_datetime)
        )


class UserCommand(Base):
    __tablename__ = "user_command"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("l1_name", "l2_name", "l3_name", name="_ln_name_uc"),
        # Make sure if l3_name is empty then response_type is 0
        # ie either l3_name can be empty or response_type can be non 0
        CheckConstraint("l3_name = '' OR response_type <> 0"),
        # Make sure if l2_name is empty, the so is l3
        CheckConstraint("(l2_name = '' AND l3_name = '') OR (l2_name <> '')"),
    )
    id = Column("id", Integer, primary_key=True)
    l1_name = Column("l1_name", String(length=32))
    l2_name = Column("l2_name", String(length=32))
    l3_name = Column("l3_name", String(length=32))
    # command_name can include spaces, must match rgx_command_name_is_valid
    description = Column("description", String(length=256))
    response_type = Column("response_type", Integer)
    # response_types are as follows:
    # 0: No response, ie this is a command group
    # 1: Plain text, respondes directly with response_data column text
    # 2: Message id, copies the content of message id if possible and
    #    responds with the same. Note: please check that message id is
    #    accessible before adding to db
    #    response_data must be in the form channel_id:message_id
    # 3: Embed, responds by parsing response data, parsing the same as
    #    json, and passing it to hikari.Embed(...). This embed is sent
    #    as a response
    response_data = Column(Text)

    def __init__(
        self,
        l1_name: str,
        l2_name: str = "",
        l3_name: str = "",
        *,
        description: str,
        response_type: int,
        response_data: str = "",
    ):
        self.l1_name = str(l1_name)
        self.l2_name = str(l2_name)
        self.l3_name = str(l3_name)
        self.description = str(description)
        self.response_type = int(response_type)
        self.response_data = str(response_data)

    def __repr__(self) -> str:
        return " -> ".join(
            ln_name for ln_name in [self.l1_name, self.l2_name, self.l3_name] if ln_name
        )

    @validates("l1_name", "l2_name", "l3_name")
    def command_name_validator(self, key, value: str):
        """Restrict to valid discord command names"""
        value = str(value)
        if key == "l1_name" and rgx_cmd_name_is_valid.match(value):
            return value
        elif key in ["l2_name", "l3_name"] and rgx_sub_cmd_name_is_valid.match(value):
            return value
        else:
            raise utils.FriendlyValueError(
                "Command names must start with a letter, be all lowercase, and only "
                + "contain letter, numbers, dashes (-) and underscores (_) and must "
                + "not be longer than 32 characters. Spaces cannot be used."
            )

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_commands(cls, session=None) -> List[UserCommand]:
        commands = (
            await session.execute(select(cls).where(cls.response_type != 0))
        ).fetchall()
        commands = [] if not commands else commands
        commands = [command[0] for command in commands]
        return commands

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_command_groups(cls, session=None) -> List[UserCommand]:
        commands = (
            await session.execute(
                select(cls)
                .where(cls.response_type == 0)
                .order_by(cls.l1_name, cls.l2_name, cls.l3_name)
            )
        ).fetchall()
        commands = [] if not commands else commands
        commands = [command[0] for command in commands]
        return commands

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_command(cls, *ln_names, session=None) -> UserCommand:
        utils.check_number_of_layers(ln_names)

        # Pad ln_names with "" up to len 3
        ln_names = list(ln_names)
        ln_names.extend([""] * (3 - len(ln_names)))

        return (
            await session.execute(
                select(cls).where(
                    and_(
                        cls.l1_name == ln_names[0],
                        cls.l2_name == ln_names[1],
                        cls.l3_name == ln_names[2],
                        cls.response_type != 0,
                    )
                )
            )
        ).scalar()

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_command_group(cls, *ln_names, session=None) -> UserCommand:
        if len(ln_names) >= 3:
            raise utils.FriendlyValueError(
                "Discord does not support slash command groups more than "
                + "2 layers deep"
            )
        elif len(ln_names) == 0:
            raise ValueError("Too few ln_names provided, need at least 1")

        # Pad ln_names with "" up to len 3
        ln_names = list(ln_names)
        ln_names.extend([""] * (2 - len(ln_names)))

        return (
            await session.execute(
                select(cls).where(
                    and_(
                        cls.l1_name == ln_names[0],
                        cls.l2_name == ln_names[1],
                        cls.response_type == 0,
                    )
                )
            )
        ).scalar()

    @classmethod
    @utils.ensure_session(db_session)
    async def _autocomplete(
        cls, l1_name="", l2_name="", l3_name="", session=None
    ) -> List[List[str]]:
        completions = (
            await session.execute(
                select(cls).where(
                    (cls.l1_name + cls.l2_name + cls.l3_name).startswith(
                        l1_name + l2_name + l3_name
                    )
                )
            )
        ).fetchall()
        completions = [] if not completions else completions
        completions = [completion[0] for completion in completions]
        return completions

    @classmethod
    @utils.ensure_session(db_session)
    async def add_command(
        cls,
        *ln_names,  # Layer n names
        description: str,
        response_type: int,
        response_data: str,
        session=None,
    ):
        utils.check_number_of_layers(ln_names)
        await cls.check_parent_command_groups_exist(*ln_names, session=session)

        # Check if there is an existing command with the same name
        existing_command = await cls.fetch_command(*ln_names, session=session)
        if existing_command:
            raise utils.FriendlyValueError(
                f"Command {' -> '.join(filter(lambda n: n != '', ln_names))} already exists"
            )

        self = cls(
            *ln_names,
            description=description,
            response_type=response_type,
            response_data=response_data,
        )
        session.add(self)
        return self

    @classmethod
    @utils.ensure_session(db_session)
    async def add_command_group(cls, *ln_names, description, session=None):
        return await cls.add_command(
            *ln_names,
            description=description,
            response_type=0,  # Response type 0 for command groups
            session=session,
            response_data=None,
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def check_parent_command_groups_exist(
        cls,
        l1_name: str,
        l2_name: str = "",
        l3_name: str = "",
        session=None,
    ):
        """Check if the parent command groups exist

        Note, this is different from the command existing (response_type must be 0)

        raises utils.FriendlyValueError if command groups specified do not exist"""

        if l2_name:
            # Only check l1_name if l3_name command is provided
            l1_exists = (
                await session.execute(
                    select(cls.id).where(
                        # Check whether l1_name exists with a 0 response type
                        # since 0 response types signify a command group
                        and_(cls.l1_name == l1_name, cls.response_type == 0)
                    )
                )
            ).scalar()
            # scalar only returns false (None) when no rows are found

            if not l1_exists:
                raise utils.FriendlyValueError(
                    f"{l1_name} is not an existing command group",
                )

        if l3_name:
            # Only check if l2_name exists if l3_name command is provided
            l2_exists = (
                await session.execute(
                    select(cls.id).where(
                        and_(
                            # Check whether l1_name -> l2_name exists with a 0 response
                            # type since 0 response types signify a command group
                            cls.l1_name == l1_name,
                            cls.l2_name == l2_name,
                            cls.response_type == 0,
                        )
                    )
                )
            ).scalar()
            # scalar only returns false (None) when no rows are found

            if not l2_exists:
                raise utils.FriendlyValueError(
                    f"{l1_name} -> {l2_name} is not an existing command group",
                )

        # Return true if command groups exist
        return True

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_subcommands(cls, l1_name, l2_name: str = "", session=None):
        return (
            await session.execute(
                select(cls).where(
                    and_(
                        cls.l1_name == l1_name,
                        # The below is to handle subcommands of command groups
                        # at the top layer where l2_name will not be specified
                        # when trying to fetch subcommands
                        (cls.l2_name == l2_name) if l2_name else True,
                        cls.response_type != 0,
                    )
                )
            )
        ).fetchall()

    @classmethod
    @utils.ensure_session(db_session)
    async def delete_command(
        cls,
        l1_name: str,
        l2_name: str = "",
        l3_name: str = "",
        fetch_deleted: bool = True,
        session=None,
    ) -> UserCommand:
        commands_to_delete = (
            (
                await session.execute(
                    select(cls).where(
                        and_(
                            cls.l1_name == l1_name,
                            cls.l2_name == l2_name,
                            cls.l3_name == l3_name,
                            cls.response_type != 0,
                        )
                    )
                )
            ).scalar()
            if fetch_deleted  # Do not fetch if fetch_deleted is False
            else []
        )

        await session.execute(
            delete(cls).where(
                and_(
                    cls.l1_name == l1_name,
                    cls.l2_name == l2_name,
                    cls.l3_name == l3_name,
                    cls.response_type != 0,
                )
            )
        )
        return commands_to_delete

    @classmethod
    @utils.ensure_session(db_session)
    async def delete_command_group(
        cls,
        l1_name: str,
        l2_name: str = "",
        cascade: bool = False,
        fetch_deleted: bool = True,
        session=None,
    ) -> List[UserCommand]:
        subcommands = await cls.fetch_subcommands(l1_name, l2_name, session=session)
        if subcommands and not cascade:
            # Handle the case where subcommands are found and we aren't supposed
            # to cascade delete
            raise utils.FriendlyValueError(
                f"Command group {l1_name}{(' -> ' + l2_name) if l2_name else ''} "
                + "still has subcommands"
            )
        else:
            # If cascade delete is not specified then the below will only delete the
            # command group since we already know that there are no subcommands as per
            # the above branch
            # If cascade delete is True, delete all with matching l1 & if specified l2
            # names

            deleted = (
                (
                    await session.execute(
                        select(cls).where(
                            and_(
                                cls.l1_name == l1_name,
                                (cls.l2_name == l2_name) if l2_name else True,
                            )
                        )
                    )
                ).fetchall()
                if fetch_deleted  # Do not fetch if fetch_delted is False
                else []
            )
            await session.execute(
                delete(cls).where(
                    and_(
                        cls.l1_name == l1_name,
                        (cls.l2_name == l2_name) if l2_name else True,
                    )
                )
            )
            deleted = [] if not deleted else deleted
            deleted = [item[0] for item in deleted]
            return deleted

    @property
    def is_command_group(self):
        return self.response_type == 0

    @property
    def is_subcommand_or_subgroup(self):
        return self.depth > 1

    @property
    def depth(self):
        return len(self.ln_names)

    @property
    def ln_names(self):
        return [
            ln_name for ln_name in [self.l1_name, self.l2_name, self.l3_name] if ln_name
        ]


async def recreate_all():
    # db_engine = create_engine(cfg.db_url, connect_args=cfg.db_connect_args)
    db_engine = create_async_engine(cfg.db_url_async, connect_args=cfg.db_connect_args)
    # db_session = sessionmaker(db_engine, **cfg.db_session_kwargs)

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(recreate_all())
