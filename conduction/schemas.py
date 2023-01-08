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

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import BigInteger

from . import cfg

Base = declarative_base()
db_engine = create_async_engine(cfg.db_url_async, connect_args=cfg.db_connect_args)
db_session = sessionmaker(db_engine, **cfg.db_session_kwargs)


class MirroredMessage(Base):
    __tablename__ = "mirrored_message"
    __mapper_args__ = {"eager_defaults": True}
    dest_msg = Column("dest_msg", BigInteger, primary_key=True)
    dest_channel = Column("dest_ch", BigInteger)
    source_msg = Column("source_msg", BigInteger)
    source_channel = Column("src_ch", BigInteger)

    def __init__(self, dest_msg, dest_channel, source_msg, source_channel):
        super().__init__()
        self.dest_msg = int(dest_msg)
        self.dest_channel = int(dest_channel)
        self.source_msg = int(source_msg)
        self.source_channel = int(source_channel)

    @classmethod
    async def add_msg(cls, dest_msg, dest_channel, source_msg, source_channel):
        """Create a session, begin it and add a message pair"""
        async with db_session() as session:
            async with session.begin():
                message_pair = await cls.add_msg_with_session(
                    dest_msg, dest_channel, source_msg, source_channel, session
                )

        return message_pair

    @classmethod
    async def add_msg_with_session(
        cls, dest_msg, dest_channel, source_msg, source_channel, session
    ):
        """Add a message pair using a begun session"""
        message_pair = cls(dest_msg, dest_channel, source_msg, source_channel)
        session.add(message_pair)
        return message_pair

    @classmethod
    async def get_dest_msgs_and_channels(cls, source_msg: int):
        """Return destination message ids from source message ids"""
        async with db_session() as session:
            async with session.begin():
                dest_msgs = await cls.get_dest_msgs_and_channels_with_session(
                    source_msg, session
                )

        return dest_msgs

    @classmethod
    async def get_dest_msgs_and_channels_with_session(cls, source_msg: int, session):
        """Return destination message ids from source message ids with session"""
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


async def recreate_all():
    # db_engine = create_engine(cfg.db_url, connect_args=cfg.db_connect_args)
    db_engine = create_async_engine(cfg.db_url_async, connect_args=cfg.db_connect_args)
    # db_session = sessionmaker(db_engine, **cfg.db_session_kwargs)

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(recreate_all())
