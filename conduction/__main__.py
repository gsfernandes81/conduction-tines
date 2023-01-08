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

from . import cfg
from .bot import CachedFetchBot
from .modules import repeater

bot = CachedFetchBot(
    token=cfg.discord_token,
    intents=(h.Intents.ALL_UNPRIVILEGED | h.Intents.MESSAGE_CONTENT),
)

for module in [
    repeater,
]:
    module.register(bot)

bot.run()
