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

import asyncio as aio
import logging
import typing as t

import lightbulb as lb

from .. import cfg, schemas
from ..bot import CachedFetchBot, UserCommandBot

# Get logger for module
# & Set logging level to INFO
logger = logging.getLogger(__name__.split(".")[-1])
logger.setLevel(logging.INFO)


@lb.command(
    "migrate",
    description="Migrate data from the old bot",
    hidden=True,
    guilds=[cfg.control_discord_server_id],
)
@lb.implements(lb.SlashCommandGroup)
async def migrate_group(ctx: lb.Context):
    pass


@migrate_group.child
@lb.command(
    "mirrors",
    description="Migrate mirror data from the old bot",
    hidden=True,
    guilds=[cfg.control_discord_server_id],
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def migrate_mirror(ctx: lb.Context):
    bot: lb.BotApp = ctx.bot

    if ctx.author.id not in await bot.fetch_owner_ids():
        logger.error("Unauthorised user attempted to migrate mirrors")
        return

    await ctx.respond(f"Migrating mirrors...")

    for schema, source_channel in [
        (schemas.LostSectorAutopostChannel, cfg.ls_followable),
        (schemas.XurAutopostChannel, cfg.xur_followable),
        (schemas.WeeklyResetAutopostChannel, cfg.reset_followable),
    ]:
        logger.info(f"Migrating {schema.__name__}")

        channels = await schema.get_channels()
        logger.info(f"Got {len(channels)} channels")
        logger.info(
            "MirroredChannel initially has "
            f"{await schemas.MirroredChannel.count_dests(source_channel)}"
            " total mirrors and "
            f"{await schemas.MirroredChannel.count_dests(source_channel, legacy_only=True)}"
            f" legacy mirrors of {source_channel}"
        )
        for channel in channels:
            await schemas.MirroredChannel.add_mirror(
                source_channel,
                channel.id,
                None,
                legacy=True,
            )

        logger.info(
            "MirroredChannel now has "
            f"{await schemas.MirroredChannel.count_dests(source_channel)}"
            " total mirrors and "
            f"{await schemas.MirroredChannel.count_dests(source_channel, legacy_only=True)}"
            f" legacy mirrors of {source_channel}"
        )

        await ctx.edit_last_response("Committed changes")
        logger.info("Committed changes")

    completion_message = "\n".join(
        [
            "Changes commited",
            "MirroredChannel now has "
            + str(await schemas.MirroredChannel.count_total_dests())
            + " total mirrors and "
            + str(await schemas.MirroredChannel.count_total_dests(legacy_only=True))
            + " legacy mirrors.",
        ]
    )

    await ctx.edit_last_response(completion_message)


@migrate_group.child
@lb.option("dry_run", description="Do not commit changes", default="True")
@lb.command(
    "cmds",
    description="Migrate mirror data from the old bot",
    hidden=True,
    pass_options=True,
    guilds=[cfg.control_discord_server_id],
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def migrate_cmds(ctx: lb.Context, dry_run: str):
    bot: UserCommandBot = ctx.bot

    if ctx.author.id not in await bot.fetch_owner_ids():
        logger.error("Unauthorised user attempted to migrate mirrors")
        return

    dry_run = dry_run.lower() != "false"

    async with schemas.db_session() as session:
        async with session.begin():
            await ctx.respond(f"Migrating commands... Dry run: {dry_run}")

            for old_command in await schemas.OldUserCommand.get_all(session=session):
                try:
                    await schemas.UserCommand.add_command(
                        str(old_command.name),
                        description=str(old_command.description),
                        response_type=1,  # Plaintext
                        response_data=str(old_command.response),
                        session=session,
                    )
                except Exception as e:
                    logging.exception(e)
                else:
                    logging.info(f"Migrated {old_command.name}")
                    logging.info(f"Description: {old_command.description}")
                    logging.info(f"Response: {old_command.response}")

            if dry_run:
                await session.rollback()
                await ctx.edit_last_response("Dry run complete, rolled back")
                logger.info("Dry run complete, rolled back")
            else:
                await ctx.edit_last_response("Committing changes")
                logger.info("Committing changes")
                await bot.sync_application_commands(session=session)

    completion_message = "\n".join(
        [
            "Changes commited" if not dry_run else "Dry run complete, rolled back",
            "UserCommand now has "
            + str(len(await schemas.UserCommand.fetch_commands()))
            + " commands. OldUserCommand had "
            + str(len(await schemas.OldUserCommand.get_all()))
            + "  commands.",
        ]
    )

    await ctx.edit_last_response(completion_message)


@migrate_group.child
@lb.command(
    "pull_server_data",
    description="Pull server data from the api",
    hidden=True,
    guilds=[cfg.control_discord_server_id],
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def pull_server_data(ctx: lb.Context):
    bot: t.Union[UserCommandBot, CachedFetchBot] = ctx.bot

    if ctx.author.id not in await bot.fetch_owner_ids():
        logger.error("Unauthorised user attempted to migrate mirrors")
        return

    async with schemas.db_session() as session:
        session: schemas.AsyncSession

        async def get_dests_with_no_server_id(session_):
            dests = await session_.execute(
                schemas.select(schemas.MirroredChannel.dest_id).where(
                    schemas.and_(
                        (schemas.MirroredChannel.legacy == True),
                        (schemas.MirroredChannel.enabled == True),
                        (schemas.MirroredChannel.dest_server_id == None),
                    )
                )
            )

            dests = dests if dests else []
            dests = [dest[0] for dest in dests]
            return dests

        dests = await get_dests_with_no_server_id(session)

    await ctx.respond("Pulling server data for " + str(len(dests)) + " channels...")

    completed_servers = []
    completed_dests = []
    for dest_id in dests:
        try:
            channel = await bot.fetch_channel(dest_id)
            guild_id = channel.guild_id
            guild = channel.get_guild() or await channel.fetch_guild()
            if not guild.member_count:
                raise ValueError(f"No member count for guild {guild_id}")
        except Exception as e:
            e.add_note(f"Failed to fetch data for channel {dest_id}")
            logger.exception(e)
            await aio.sleep(3)

        else:
            async with schemas.db_session() as session:
                session: schemas.AsyncSession
                async with session.begin():
                    src_ids = await schemas.MirroredChannel.fetch_srcs(
                        dest_id, session=session
                    )

                    for src_id in src_ids:
                        mirror = await session.get(
                            schemas.MirroredChannel, (src_id, dest_id)
                        )
                        await mirror.add_mirror(
                            src_id=mirror.src_id,
                            dest_id=mirror.dest_id,
                            dest_server_id=guild_id,
                            legacy=mirror.legacy,
                            enabled=mirror.enabled,
                            session=session,
                        )
                    await schemas.ServerStatistics.add_server(
                        guild_id, guild.member_count, session=session
                    )
                    completed_servers.append(guild_id)
            await aio.sleep(1)
        finally:
            completed_dests.append(dest_id)

    async with schemas.db_session() as session:
        await ctx.respond(
            "Server data pulled. Remaining incomplete no of dests: "
            + str(len(await get_dests_with_no_server_id(session)))
        )


def register(bot: lb.BotApp):
    bot.command(migrate_group)
