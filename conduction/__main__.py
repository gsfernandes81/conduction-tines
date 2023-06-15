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

import hikari as h
import lightbulb as lb
import miru
from lightbulb.ext import tasks
import logging

from . import cfg, modules, schemas, utils
from .bot import CachedFetchBot, UserCommandBot


class Bot(UserCommandBot, CachedFetchBot):
    pass


bot = Bot(**cfg.lightbulb_params, user_command_schema=schemas.UserCommand)


@tasks.task(m=5, auto_start=True, wait_before_execution=False)
async def autoupdate_status():
    await utils.wait_till_lightbulb_started(bot)

    await bot.update_presence(
        activity=h.Activity(
            name="{} servers : )".format(len(await bot.rest.fetch_my_guilds())),
            type=h.ActivityType.LISTENING,
        )
    )


_modules = map(modules.__dict__.get, modules.__all__)

for module in _modules:
    logging.info(f"Loading module {module.__name__.split('.')[-1]}")
    module.register(bot)

tasks.load(bot)
miru.install(bot)
bot.run()
