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

import lightbulb as lb

SOURCE_CODE_NOTICE = """
```
Copyright © 2019-present gsfernandes81

This bot (conduction-tines) is open source! You can find the source code at \
https://github.com/geolocatingshark/conduction-tines.git

conduction-tines is free software: you can redistribute it and/or modify it under the
terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.

"conduction-tines" is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with
conduction-tines. If not, see <https://www.gnu.org/licenses/>.
```
"""


@lb.command(
    "source_code", description="Get the source code of conduction-tines / this bot"
)
@lb.implements(lb.SlashCommand)
async def source_code(ctx: lb.Context):
    await ctx.respond(SOURCE_CODE_NOTICE)


def register(bot: lb.BotApp):
    bot.command(source_code)
