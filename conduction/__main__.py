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

import hikari as h
from lightbulb.ext import tasks

from . import cfg, schemas
from .bot import CachedFetchBot, UserCommandBot
from .modules import (
    autoposts,
    eververse,
    lost_sector,
    repeater,
    twab,
    user_commands,
    weekly_reset,
    xur,
)


class Bot(UserCommandBot, CachedFetchBot):
    pass


bot = Bot(**cfg.lightbulb_params, user_command_schema=schemas.UserCommand)

for module in [
    autoposts,
    eververse,
    repeater,
    twab,
    lost_sector,
    weekly_reset,
    xur,
    user_commands,
]:
    module.register(bot)


tasks.load(bot)
bot.run()
