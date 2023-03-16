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

import datetime as dt
import json
import ssl
from os import getenv as _getenv

import hikari as h
import regex as re
from sqlalchemy.ext.asyncio import AsyncSession

# Discord bot parameters
discord_token = _getenv("DISCORD_TOKEN")
test_env = _getenv("TEST_ENV") or "false"
test_env = (
    [int(env.strip()) for env in test_env.split(",")] if test_env != "false" else False
)
intents = h.Intents.ALL_UNPRIVILEGED | h.Intents.MESSAGE_CONTENT
lightbulb_params = {
    "token": discord_token,
    "intents": intents,
}
# Only use the test env for testing if it is specified
if test_env:
    lightbulb_params["default_enabled_guilds"] = test_env


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

# Google sheets
gsheets_credentials = {
    "type": "service_account",
    "project_id": _getenv("SHEETS_PROJECT_ID"),
    "private_key_id": _getenv("SHEETS_PRIVATE_KEY_ID"),
    "private_key": _getenv("SHEETS_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": _getenv("SHEETS_CLIENT_EMAIL"),
    "client_id": _getenv("SHEETS_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": _getenv("SHEETS_CLIENT_X509_CERT_URL"),
}
sheets_ls_url = _getenv("SHEETS_LS_URL")

# Discord snowflakes & constants
embed_default_color = h.Color(int(_getenv("EMBED_DEFAULT_COLOR"), 16))
embed_error_color = h.Color(int(_getenv("EMBED_ERROR_COLOR"), 16))
control_discord_server_id = int(_getenv("CONTROL_DISCORD_SERVER_ID"))
control_discord_role_id = int(_getenv("CONTROL_DISCORD_ROLE_ID"))
default_url = str(_getenv("DEFAULT_URL"))
followables = json.loads(_getenv("FOLLOWABLES"), parse_int=int)
log_channel = int(_getenv("LOG_CHANNEL"))
# Minutes of buffer, search messages this many minutes earlier
reset_time_tolerance = dt.timedelta(minutes=60)

# Kyber's links
ls_rotation_webpage = _getenv("LS_ROTATION_WEBPAGE")
ls_infogfx_webpage = _getenv("LS_INFOGFX_WEBPAGE")

# URL Regex
url_regex = re.compile(
    "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)
