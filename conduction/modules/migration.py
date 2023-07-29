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

import logging

import lightbulb as lb

from .. import cfg, schemas

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
@lb.option("dry_run", description="Do not commit changes", default=True)
@lb.command(
    "mirrors",
    description="Migrate mirror data from the old bot",
    hidden=True,
    pass_options=True,
    guilds=[cfg.control_discord_server_id],
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def migrate_mirror(ctx: lb.Context, dry_run: bool = True):
    bot: lb.BotApp = ctx.bot

    if ctx.author.id not in await bot.fetch_owner_ids():
        logger.error("Unauthorised user attempted to migrate mirrors")
        return

    async with schemas.db_session() as session:
        async with session.begin():
            await ctx.respond("Migrating mirrors...")

            for schema, source_channel in [
                (schemas.LostSectorAutopostChannel, cfg.ls_followable),
                (schemas.XurAutopostChannel, cfg.xur_followable),
                (schemas.WeeklyResetAutopostChannel, cfg.reset_followable),
            ]:
                logger.info(f"Migrating {schema.__name__}")

                channels = await schema.get_channels(session=session)
                logger.info(f"Got {len(channels)} channels")
                logger.info(
                    "MirroredChannel initially has "
                    f"{await schemas.MirroredChannel.count_dests(source_channel, session=session)}"
                    " total mirrors and "
                    f"{await schemas.MirroredChannel.count_dests(source_channel, legacy_only=True, session=session)}"
                    f" legacy mirrors of {source_channel}"
                )
                for channel in channels:
                    await schemas.MirroredChannel.add_mirror(
                        source_channel,
                        channel.id,
                        None,
                        legacy=True,
                        session=session,
                    )

                logger.info(
                    "MirroredChannel now has "
                    f"{await schemas.MirroredChannel.count_dests(source_channel, session=session)}"
                    " total mirrors and "
                    f"{await schemas.MirroredChannel.count_dests(source_channel, legacy_only=True, session=session)}"
                    f" legacy mirrors of {source_channel}"
                )

            if dry_run:
                await session.rollback()
                await ctx.edit_last_response("Dry run complete, rolled back")
                logger.info("Dry run complete, rolled back")
            else:
                await ctx.edit_last_response("Committing changes")
                logger.info("Committing changes")

    completion_message = "\n".join(
        [
            "Changes commited" if not dry_run else "Dry run complete, rolled back",
            "MirroredChannel now has "
            + str(await schemas.MirroredChannel.count_total_dests())
            + " total mirrors and "
            + str(await schemas.MirroredChannel.count_total_dests(legacy_only=True))
            + " legacy mirrors.",
        ]
    )

    await ctx.edit_last_response(completion_message)


@migrate_group.child
@lb.option("dry_run", description="Do not commit changes", default=True)
@lb.command(
    "cmds",
    description="Migrate mirror data from the old bot",
    hidden=True,
    pass_options=True,
    guilds=[cfg.control_discord_server_id],
    auto_defer=True,
)
@lb.implements(lb.SlashSubCommand)
async def migrate_cmds(ctx: lb.Context, dry_run: bool = True):
    bot: lb.BotApp = ctx.bot

    if ctx.author.id not in await bot.fetch_owner_ids():
        logger.error("Unauthorised user attempted to migrate mirrors")
        return

    async with schemas.db_session() as session:
        async with session.begin():
            await ctx.respond("Migrating commands...")

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


def register(bot: lb.BotApp):
    bot.command(migrate_group)
