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

import json
import ssl
from os import getenv as _getenv

from sqlalchemy.ext.asyncio import AsyncSession


# Discord API Token
discord_token = _getenv("DISCORD_TOKEN")


# Mirror dict
mirror_dict = json.loads(_getenv("MIRROR_JSON"))
# Convert all strings to ints in mirror dict
_new_mirror_dict = {}
for key, channel_list in mirror_dict.items():
    _new_mirror_dict[int(key)] = [int(channel_id) for channel_id in channel_list]
mirror_dict = _new_mirror_dict


# DB config
db_url = _getenv("MYSQL_URL")
__repl_till = db_url.find("://")
db_url = db_url[__repl_till:]
db_url_async = "mysql+asyncmy" + db_url
db_url = "mysql" + db_url

db_session_kwargs_sync = {
    "expire_on_commit": False,
}
db_session_kwargs = db_session_kwargs_sync | {
    "class_": AsyncSession,
}

ssl_ctx = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
ssl_ctx.verify_mode = ssl.CERT_REQUIRED
db_connect_args = {"ssl": ssl_ctx}
