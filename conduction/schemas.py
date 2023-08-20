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
import logging
from collections import defaultdict
from typing import List, Optional, Set, Tuple

import regex as re
from pytz import utc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import (
    declarative_base,
    declarative_mixin,
    declared_attr,
    sessionmaker,
    validates,
)
from sqlalchemy.sql.expression import and_, delete, desc, insert, select, update
from sqlalchemy.sql.functions import coalesce, func
from sqlalchemy.sql.schema import CheckConstraint, Column, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, DateTime, Integer, String, Text

from . import cfg, utils

Base = declarative_base()
OldBase = declarative_base()
db_engine = create_async_engine(
    cfg.db_url_async, connect_args=cfg.db_connect_args, **cfg.db_engine_args
)
db_session = sessionmaker(db_engine, **cfg.db_session_kwargs)


# NOTE: Session configuration for routing to the correct DB is below:
db_session.configure(
    binds={
        Base: create_async_engine(
            cfg.db_url_async,
            connect_args=cfg.db_connect_args,
            **cfg.db_engine_args
        ),
        OldBase: create_async_engine(
            cfg.legacy_db_url_async,
            connect_args={"timeout": 120},
            pool_pre_ping=True,
        ),
    }
)

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
    dest_server_id = Column("dest_server_id", BigInteger)
    legacy = Column("legacy", Boolean)
    enabled = Column("enabled", Boolean, default=True)
    legacy_error_rate = Column("legacy_error_rate", Integer, default=0)
    legacy_disable_for_failure_on_date = Column(
        "legacy_disable_for_failure_on_date", DateTime, default=None
    )
    _dests_cache = defaultdict(list)
    _all_srcs_cache = set()

    def __init__(
        self,
        src_id: int,
        dest_id: int,
        dest_server_id: int,
        legacy: bool,
        enabled: bool,
    ):
        super().__init__()
        self.src_id = int(src_id)
        self.dest_id = int(dest_id)
        self.dest_server_id = dest_server_id and int(dest_server_id)
        self.legacy = bool(legacy)
        self.enabled = bool(enabled)

    @classmethod
    @utils.ensure_session(db_session)
    async def add_mirror(
        cls,
        src_id: int,
        dest_id: int,
        dest_server_id: int,
        legacy: bool,
        enabled: bool = True,
        session: Optional[AsyncSession] = None,
    ):
        src_id = int(src_id)
        dest_id = int(dest_id)
        await session.merge(
            cls(src_id, dest_id, dest_server_id, legacy, enabled=enabled)
        )

        if legacy and enabled and dest_id not in cls._dests_cache[src_id]:
            cls._dests_cache[src_id].append(dest_id)

        if legacy and src_id not in cls._all_srcs_cache:
            cls._all_srcs_cache.add(src_id)

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_dests(
        cls,
        src_id: int,
        legacy: bool | None = True,
        enabled: bool | None = True,
        session: Optional[AsyncSession] = None,
    ) -> List[int]:
        """Fetch all dests for a given src_id

        src_id -> The source channel ID
        legacy -> True: Fetch legacy only, False: Fetch non-legacy only, None: Fetch all
        enabled -> True: Fetch enabled only, False: Fetch disabled only, None: Fetch all
        """
        src_id = int(src_id)
        dests = await session.execute(
            select(cls.dest_id)
            .where(
                and_(
                    cls.src_id == src_id,
                    (cls.legacy == legacy) if legacy is not None else True,
                    (cls.enabled == enabled) if enabled is not None else True,
                )
            )
            .join(
                ServerStatistics,
                cls.dest_server_id == ServerStatistics.id,
                isouter=True,
            )
            .order_by(
                desc(coalesce(ServerStatistics.population, 10**12)),
            )
        )

        dests = dests if dests else []
        dests = [dest[0] for dest in dests]
        return dests

    @classmethod
    @utils.ensure_session(db_session)
    async def get_or_fetch_dests(
        cls, src_id: int, session: Optional[AsyncSession] = None
    ) -> List[int]:
        src_id = int(src_id)
        if src_id in cls._dests_cache:
            # This condition is phrased specifically to allow
            # empty lists to be returned from the cache
            # Also copy the list to guard against mutation
            return list(cls._dests_cache[src_id])
        else:
            dests = await cls.fetch_dests(src_id, session=session)
            cls._dests_cache[src_id] = dests
            return dests

    @classmethod
    def reset_dests_cache(self):
        self._dests_cache = defaultdict(list)

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_srcs(
        cls,
        dest_id: int,
        legacy: bool | None = True,
        enabled: bool | None = True,
        session: Optional[AsyncSession] = None,
    ) -> List[int]:
        dest_id = int(dest_id)
        srcs = (
            await session.execute(
                select(cls.src_id).where(
                    and_(
                        cls.dest_id == dest_id,
                        (cls.legacy == legacy) if legacy is not None else True,
                        (cls.enabled == enabled) if enabled is not None else True,
                    )
                )
            )
        ).fetchall()
        srcs = srcs if srcs else []
        srcs = [src[0] for src in srcs]
        return srcs

    @classmethod
    @utils.ensure_session(db_session)
    async def get_or_fetch_all_srcs(
        cls,
        legacy: bool | None = True,
        session: Optional[AsyncSession] = None,
    ) -> Set[int]:
        """Fetch all srcs

        WARNING: This is function has a failure mode where it will return
        src_ids that may have been deleted with the removal of the last mirror
        with this src. This is intentional to avoid the overhead of clearing
        and refetching the cache on every mirror removal.

        If you need to ensure that the returned src_ids are valid, use
        fetch_all_srcs instead"""
        if legacy and cls._all_srcs_cache:
            return cls._all_srcs_cache
        else:
            srcs = await cls.fetch_all_srcs(legacy=legacy, session=session)
            cls._all_srcs_cache = set(srcs)
            return srcs

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_all_srcs(
        cls,
        legacy: bool | None = True,
        session: Optional[AsyncSession] = None,
    ) -> Set[int]:
        srcs = (
            await session.execute(select(cls.src_id).where(cls.legacy == legacy))
        ).fetchall()
        srcs = srcs if srcs else []
        srcs = [src[0] for src in srcs]
        return set(srcs)

    @classmethod
    @utils.ensure_session(db_session)
    async def count_dests(
        cls,
        src_id: int,
        legacy_only: bool | None = True,
        session: Optional[AsyncSession] = None,
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
        ).scalar_one()

        return dests_count

    @classmethod
    @utils.ensure_session(db_session)
    async def count_total_dests(
        cls,
        legacy_only: bool | None = True,
        session: Optional[AsyncSession] = None,
    ) -> int:
        dests_count = (
            await session.execute(
                select(func.count())
                .select_from(cls)
                .where(
                    (cls.legacy == legacy_only) if legacy_only is not None else True,
                )
            )
        ).scalar_one()

        return dests_count

    @classmethod
    @utils.ensure_session(db_session)
    async def set_legacy(
        cls,
        src_id: int,
        dest_id: int,
        legacy: bool = True,
        session: Optional[AsyncSession] = None,
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
            if src_id not in cls._all_srcs_cache:
                cls._all_srcs_cache.add(src_id)
        else:
            cls._dests_cache[src_id].remove(dest_id)
            if src_id in cls._all_srcs_cache:
                cls._all_srcs_cache.remove(src_id)

    @classmethod
    @utils.ensure_session(db_session)
    async def remove_mirror(
        cls, src_id: int, dest_id: int, session: Optional[AsyncSession] = None
    ) -> None:
        src_id = int(src_id)
        dest_id = int(dest_id)
        await session.execute(
            update(cls)
            .where(
                and_(cls.src_id == src_id, cls.dest_id == dest_id, cls.enabled == True)
            )
            .values(enabled=False)
        )
        try:
            cls._dests_cache[src_id].remove(dest_id)
        except ValueError:
            pass

        # Note: We deliberately don't remove the src_id from the _all_srcs_cache
        # since we don't know if there are other mirrors with the same src_id
        # and clearing and refetching would be needlessly expensive
        # Since mirrors are mostly designed as a one to many repeater of messages
        # it is also unlikely that the last mirror with a given src_id will be
        # removed.

    @classmethod
    @utils.ensure_session(db_session)
    async def remove_all_mirrors(
        cls, dest_id: int, session: Optional[AsyncSession] = None
    ) -> None:
        dest_id = int(dest_id)
        src_ids = await cls.fetch_srcs(dest_id)
        await session.execute(
            update(cls)
            .where(and_(cls.dest_id == dest_id, cls.enabled == True))
            .values(enabled=False)
        )
        for src_id in src_ids:
            try:
                cls._dests_cache[src_id].remove(dest_id)
            except ValueError:
                pass

        # Note: We deliberately don't remove the src_ids from the _all_srcs_cache
        # since we don't know if there are other mirrors with the same src_id
        # and clearing and refetching would be needlessly expensive
        # Since mirrors are mostly designed as a one to many repeater of messages
        # it is also unlikely that the last mirror with a given src_id will be
        # removed.

    @classmethod
    @utils.ensure_session(db_session)
    async def log_legacy_mirror_success(
        cls, src_id: int, dest_id: int, session: Optional[AsyncSession] = None
    ) -> None:
        """Log the successful use of a mirror

        In case of a successful mirror, the error rate is set to 0
        """
        src_id = int(src_id)
        dest_id = int(dest_id)
        await session.execute(
            update(cls)
            .where(
                and_(
                    cls.src_id == src_id,
                    cls.dest_id == dest_id,
                    cls.enabled == True,
                    cls.legacy == True,
                )
            )
            .values(legacy_error_rate=0)
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def log_legacy_mirror_success_in_batch(
        cls, src_id: int, dest_ids: List[int], session: Optional[AsyncSession] = None
    ):
        """Log the successful use of a batch of mirror pairs

        In case of a successful mirror, the error rate is set to 0
        """
        src_id = int(src_id)
        dest_ids = [int(dest_id) for dest_id in dest_ids]
        await session.execute(
            update(cls)
            .where(
                and_(
                    cls.src_id == src_id,
                    cls.dest_id.in_(dest_ids),
                    cls.enabled == True,
                    cls.legacy == True,
                )
            )
            .values(legacy_error_rate=0)
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def log_legacy_mirror_failure(
        cls, src_id: int, dest_id: int, session: Optional[AsyncSession] = None
    ) -> None:
        """Log the failure of a mirror

        In case of a failure, the error rate is increased by 1
        """
        src_id = int(src_id)
        dest_id = int(dest_id)
        await session.execute(
            update(cls)
            .where(
                and_(
                    cls.src_id == src_id,
                    cls.dest_id == dest_id,
                    cls.enabled == True,
                    cls.legacy == True,
                )
            )
            .values(legacy_error_rate=cls.legacy_error_rate + 1)
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def log_legacy_mirror_failure_in_batch(
        cls, src_id: int, dest_ids: List[int], session: Optional[AsyncSession] = None
    ):
        """Log the failure of a batch of mirror pairs

        In case of a failure, the error rate is increased by 1
        """
        src_id = int(src_id)
        dest_ids = [int(dest_id) for dest_id in dest_ids]
        await session.execute(
            update(cls)
            .where(
                and_(
                    cls.src_id == src_id,
                    cls.dest_id.in_(dest_ids),
                    cls.enabled == True,
                    cls.legacy == True,
                )
            )
            .values(legacy_error_rate=cls.legacy_error_rate + 1)
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def get_legacy_failing_mirrors(
        cls,
        threshold: int = 7,
        session: Optional[AsyncSession] = None,
    ) -> List[Tuple[int, int]]:
        """Return mirrors that have failed too many times

        Mirrors that have failed more than `threshold` times are disabled
        """
        disabled_mirrors = await session.execute(
            select(cls.src_id, cls.dest_id).where(
                and_(
                    cls.enabled == True,
                    cls.legacy == True,
                    cls.legacy_error_rate >= threshold,
                )
            )
        )
        disabled_mirrors = disabled_mirrors if disabled_mirrors else []
        disabled_mirrors = disabled_mirrors.fetchall()

        return disabled_mirrors

    @classmethod
    @utils.ensure_session(db_session)
    async def disable_legacy_failing_mirrors(
        cls,
        threshold: int = 7,
        session: Optional[AsyncSession] = None,
    ) -> List[Tuple[int, int]]:
        """Disable mirrors that have failed too many times

        Mirrors that have failed more than `threshold` times are disabled
        Returns the disabled mirrors
        """
        mirrors_to_disable = await cls.get_legacy_failing_mirrors(
            threshold=threshold, session=session
        )
        await session.execute(
            update(cls)
            .where(
                and_(
                    cls.src_id.in_([mirror[0] for mirror in mirrors_to_disable]),
                    cls.dest_id.in_([mirror[1] for mirror in mirrors_to_disable]),
                )
            )
            .values(
                enabled=False,
                legacy_disable_for_failure_on_date=dt.datetime.now(tz=dt.timezone.utc),
            )
        )

        # Remove disabled mirrors from the cache
        for src_id, dest_id in mirrors_to_disable:
            try:
                cls._dests_cache[src_id].remove(dest_id)
            except ValueError:
                pass

        # Note: We deliberately don't remove the src_id from the _all_srcs_cache
        # since we don't know if there are other mirrors with the same src_id
        # and clearing and refetching would be needlessly expensive
        # Since mirrors are mostly designed as a one to many repeater of messages
        # it is also unlikely that the last mirror with a given src_id will be
        # removed.

        return mirrors_to_disable

    @classmethod
    @utils.ensure_session(db_session)
    async def get_legacy_mirrors_disabled_for_failure(
        cls, since: Optional[dt.datetime], session: Optional[AsyncSession] = None
    ) -> List[Tuple[int, int]]:
        """Return mirrors that have been disabled for failure

        Mirrors that have been disabled for failure since `since` are returned
        in the format (src_id, dest_id)
        """
        disabled_mirrors = await session.execute(
            select(cls.src_id, cls.dest_id).where(
                and_(
                    cls.enabled == False,
                    cls.legacy == True,
                    cls.legacy_disable_for_failure_on_date >= since,
                )
            )
        )
        disabled_mirrors = disabled_mirrors if disabled_mirrors else []
        disabled_mirrors = disabled_mirrors.fetchall()

        return disabled_mirrors

    @classmethod
    @utils.ensure_session(db_session)
    async def undo_auto_disable_for_failure(
        cls,
        since: Optional[dt.datetime],
        session: Optional[AsyncSession] = None,
    ) -> List[Tuple[int, int]]:
        """Undo auto disable for failure of mirrors

        Mirrors that have been disabled for failure since `since` are re-enabled
        Mirrors are returned in the format (src_id, dest_id)
        """
        mirrors_to_enable = await cls.get_legacy_mirrors_disabled_for_failure(
            since=since, session=session
        )
        await session.execute(
            update(cls)
            .where(
                and_(
                    cls.src_id.in_([mirror[0] for mirror in mirrors_to_enable]),
                    cls.dest_id.in_([mirror[1] for mirror in mirrors_to_enable]),
                )
            )
            .values(
                enabled=True,
                legacy_error_rate=0,
            )
        )

        # Add reenabled mirrors to the cache
        for src_id, dest_id in mirrors_to_enable:
            cls._dests_cache[src_id].append(dest_id)

            if src_id not in cls._all_srcs_cache:
                cls._all_srcs_cache.add(src_id)

        return mirrors_to_enable


class MirroredMessage(Base):
    __tablename__ = "mirrored_message"
    __mapper_args__ = {"eager_defaults": True}
    dest_msg = Column("dest_msg", BigInteger, primary_key=True)
    dest_channel = Column("dest_ch", BigInteger)
    source_msg = Column("source_msg", BigInteger)
    source_channel = Column("src_ch", BigInteger)
    creation_datetime = Column(
        "creation_datetime", DateTime, default=dt.datetime.utcnow
    )

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
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Create a session, begin it and add a message pair"""
        dest_msg = int(dest_msg)
        dest_channel = int(dest_channel)
        source_msg = int(source_msg)
        source_channel = int(source_channel)

        await session.execute(
            insert(cls).values(
                dest_msg=dest_msg,
                dest_channel=dest_channel,
                source_msg=source_msg,
                source_channel=source_channel,
            )
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def add_msgs_in_batch(
        cls,
        dest_msgs: List[int],
        dest_channels: List[int],
        source_msg: int,
        source_channel: int,
        session: Optional[AsyncSession] = None,
    ):
        """Create a session, begin it and add a message pair"""
        dest_msgs = [int(dest_msg) for dest_msg in dest_msgs]
        dest_channels = [int(dest_channel) for dest_channel in dest_channels]
        source_msg = int(source_msg)
        source_channel = int(source_channel)

        await session.execute(
            insert(cls).values(
                [
                    {
                        "dest_msg": dest_msg,
                        "dest_channel": dest_channel,
                        "source_msg": source_msg,
                        "source_channel": source_channel,
                    }
                    for dest_msg, dest_channel in zip(dest_msgs, dest_channels)
                ]
            )
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def get_dest_msgs_and_channels(
        cls,
        source_msg: int,
        session: Optional[AsyncSession] = None,
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
        cls,
        age: None | dt.timedelta = dt.timedelta(days=21),
        session: Optional[AsyncSession] = None,
    ):
        """Delete entries older than <age>"""
        await session.execute(
            delete(cls).where(dt.datetime.now(tz=utc) - age > cls.creation_datetime)
        )


class ServerStatistics(Base):
    __tablename__ = "server_statistics"
    __mapper_args__ = {"eager_defaults": True}
    # Server id
    id = Column("id", BigInteger, primary_key=True)
    population = Column("population", BigInteger)

    # Population is set high by default since its better to prioritize
    # new servers if we don't yet know their population
    def __init__(self, id: int, population: int = 10**12):
        self.id = int(id)
        self.population = int(population)

    @classmethod
    @utils.ensure_session(db_session)
    async def add_server(
        cls,
        id: int,
        population: int = 10**12,
        session: Optional[AsyncSession] = None,
    ):
        id = int(id)
        await session.merge(cls(id, population))

    @classmethod
    @utils.ensure_session(db_session)
    async def add_servers_in_batch(
        cls,
        ids: List[int],
        populations: List[int],
        session: Optional[AsyncSession] = None,
    ):
        ids = [int(id) for id in ids]
        populations = [int(population) for population in populations]
        if len(ids) != len(populations):
            raise ValueError("ids and populations must be of the same length")

        if not (ids and populations):
            return

        await session.execute(
            insert(cls),
            [
                {"id": id, "population": population}
                for id, population in zip(ids, populations)
            ],
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_server_ids(
        cls,
        session: Optional[AsyncSession] = None,
    ) -> List[int]:
        ids = await session.execute(select(cls.id))
        ids = ids if ids else []
        ids = [id[0] for id in ids]
        return ids

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_server_populations(
        cls, session: Optional[AsyncSession] = None
    ) -> Tuple[int, int]:
        """Returns tuples of server id to population"""
        populations = (await session.execute(select(cls.id, cls.population))).fetchall()
        populations = populations if populations else []
        return populations

    @classmethod
    @utils.ensure_session(db_session)
    async def update_population(
        cls,
        id: int,
        population: int,
        session: Optional[AsyncSession] = None,
    ):
        id = int(id)
        await session.execute(
            update(cls).where(cls.id == id).values(population=population)
        )

    @classmethod
    @utils.ensure_session(db_session)
    async def update_population_in_batch(
        cls,
        ids: List[int],
        populations: List[int],
        session: Optional[AsyncSession] = None,
    ):
        ids = [int(id) for id in ids]
        populations = [int(population) for population in populations]
        await session.execute(
            update(cls),
            [
                {"id": id, "population": population}
                for id, population in zip(ids, populations)
            ],
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
    async def fetch_commands(
        cls, session: Optional[AsyncSession] = None
    ) -> List[UserCommand]:
        commands = (
            await session.execute(select(cls).where(cls.response_type != 0))
        ).fetchall()
        commands = [] if not commands else commands
        commands = [command[0] for command in commands]
        return commands

    @classmethod
    @utils.ensure_session(db_session)
    async def fetch_command_groups(
        cls, session: Optional[AsyncSession] = None
    ) -> List[UserCommand]:
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
    async def fetch_command(
        cls, *ln_names, session: Optional[AsyncSession] = None
    ) -> UserCommand:
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
    async def fetch_command_group(
        cls, *ln_names, session: Optional[AsyncSession] = None
    ) -> UserCommand:
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
        cls, l1_name="", l2_name="", l3_name="", session: Optional[AsyncSession] = None
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
        session: Optional[AsyncSession] = None,
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
    async def add_command_group(
        cls, *ln_names, description, session: Optional[AsyncSession] = None
    ):
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
        session: Optional[AsyncSession] = None,
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
    async def fetch_subcommands(
        cls, l1_name, l2_name: str = "", session: Optional[AsyncSession] = None
    ):
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
        session: Optional[AsyncSession] = None,
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
        session: Optional[AsyncSession] = None,
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


@declarative_mixin
class OldBaseChannelRecord:
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    __mapper_args__ = {"eager_defaults": True}

    id = Column("id", BigInteger, primary_key=True)
    server_id = Column("server_id", BigInteger)
    last_msg_id = Column("last_msg_id", BigInteger)
    enabled = Column("enabled", Boolean)

    @classmethod
    @utils.ensure_session(db_session)
    async def get_channels(
        cls, session: Optional[AsyncSession] = None, enabled_only: bool = True
    ):
        """Get all channels in the table"""
        if enabled_only:
            channels = (
                await session.execute(
                    select(cls.id, cls.enabled).where(cls.enabled == True)
                )
            ).fetchall()
        else:
            channels = (await session.execute(select(cls.id, cls.enabled))).fetchall()
        channels = [] if channels is None else channels
        return channels


class LostSectorAutopostChannel(OldBaseChannelRecord, OldBase):
    pass


class WeeklyResetAutopostChannel(OldBaseChannelRecord, OldBase):
    pass


class XurAutopostChannel(OldBaseChannelRecord, OldBase):
    pass


class OldUserCommand(OldBase):
    __tablename__ = "commands"
    __mapper_args__ = {"eager_defaults": True}
    name = Column("name", String, primary_key=True)
    description = Column("description", String)
    response = Column("response", String)

    @classmethod
    @utils.ensure_session(db_session)
    async def get_all(cls, session: Optional[AsyncSession] = None):
        cmds = await session.execute(select(cls))
        cmds = cmds if cmds else []
        cmds = [cmd[0] for cmd in cmds]
        return cmds


async def recreate_all():
    # db_engine = create_engine(cfg.db_url, connect_args=cfg.db_connect_args)
    db_engine = create_async_engine(cfg.db_url_async, connect_args=cfg.db_connect_args)
    # db_session = sessionmaker(db_engine, **cfg.db_session_kwargs)

    async with db_engine.begin() as conn:
        logging.info(f"Dropping tables: {Base.metadata.tables.keys()}")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        logging.info(f"Created tables: {Base.metadata.tables.keys()}")


if __name__ == "__main__":
    asyncio.run(recreate_all())
