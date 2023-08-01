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


def _test_env(var_name: str) -> list[int] | bool:
    test_env = _getenv(var_name) or "false"
    test_env = (
        [int(env.strip()) for env in test_env.split(",")]
        if test_env != "false"
        else False
    )
    return test_env


def _lightbulb_params() -> dict:
    intents = h.Intents.ALL_UNPRIVILEGED | h.Intents.MESSAGE_CONTENT
    lightbulb_params = {
        "token": discord_token,
        "intents": intents,
    }
    # Only use the test env for testing if it is specified
    if test_env:
        lightbulb_params["default_enabled_guilds"] = test_env
    return lightbulb_params


def _db_urls(var_name: str) -> tuple[str, str]:
    db_url = _getenv(var_name)
    __repl_till = db_url.find("://")
    db_url = db_url[__repl_till:]
    db_url_async = "mysql+asyncmy" + db_url
    db_url = "mysql" + db_url
    return db_url, db_url_async


def _legacy_db_url(var_name: str) -> tuple[str, str]:
    legacy_db_url = _getenv("DATABASE_URL")
    if legacy_db_url.startswith("postgres"):
        repl_till = legacy_db_url.find("://")
        legacy_db_url = legacy_db_url[repl_till:]
        legacy_db_url_async = "postgresql+asyncpg" + legacy_db_url
    return legacy_db_url, legacy_db_url_async


def _db_config():
    db_session_kwargs_sync = {
        "expire_on_commit": False,
    }
    db_session_kwargs = db_session_kwargs_sync | {
        "class_": AsyncSession,
    }

    ssl_ctx = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    db_connect_args = {"ssl": ssl_ctx}
    return db_session_kwargs, db_session_kwargs_sync, db_connect_args


def _sheets_credentials(
    proj_id: str,
    priv_key_id: str,
    priv_key: str,
    client_email: str,
    client_id: str,
    client_x509_cert_url: str,
) -> dict[str, str]:
    gsheets_credentials = {
        "type": "service_account",
        "project_id": _getenv(proj_id),
        "private_key_id": _getenv(priv_key_id),
        "private_key": _getenv(priv_key).replace("\\n", "\n"),
        "client_email": _getenv(client_email),
        "client_id": _getenv(client_id),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": _getenv(client_x509_cert_url),
    }
    return gsheets_credentials


###### Environment variables ######

# Discord control server config
control_discord_server_id = int(_getenv("CONTROL_DISCORD_SERVER_ID"))
control_discord_role_id = int(_getenv("CONTROL_DISCORD_ROLE_ID"))
kyber_discord_server_id = int(_getenv("KYBER_DISCORD_SERVER_ID"))
log_channel = int(_getenv("LOG_CHANNEL_ID"))
alerts_channel = int(_getenv("ALERTS_CHANNEL_ID"))

# Discord environment config
discord_token = _getenv("DISCORD_TOKEN")
test_env = _test_env("TEST_ENV")
disable_bad_channels = str(_getenv("DISABLE_BAD_CHANNELS")).lower() == "true"

# Discord constants
embed_default_color = h.Color(int(_getenv("EMBED_DEFAULT_COLOR"), 16))
embed_error_color = h.Color(int(_getenv("EMBED_ERROR_COLOR"), 16))
emoji = json.loads(_getenv("EMOJI"))
followables = json.loads(_getenv("FOLLOWABLES"), parse_int=int)
default_url = _getenv("DEFAULT_URL")

# Database URLs
db_url, db_url_async = _db_urls("MYSQL_URL")

# Sheets credentials & URLs
gsheets_credentials = _sheets_credentials(
    "SHEETS_PROJECT_ID",
    "SHEETS_PRIVATE_KEY_ID",
    "SHEETS_PRIVATE_KEY",
    "SHEETS_CLIENT_EMAIL",
    "SHEETS_CLIENT_ID",
    "SHEETS_CLIENT_X509_CERT_URL",
)
sheets_ls_url = _getenv("SHEETS_LS_URL")

# Legacy database config
legacy_db_url, legacy_db_url_async = _legacy_db_url("DATABASE_URL")
ls_followable = int(_getenv("LS_FOLLOW_CHANNEL_ID"))
xur_followable = int(_getenv("LS_FOLLOW_CHANNEL_ID"))
reset_followable = int(_getenv("RESET_FOLLOW_CHANNEL_ID"))

#### Environment variables end ####

###################################

####### Configs & constants #######

db_session_kwargs, db_session_kwargs_sync, db_connect_args = _db_config()
lightbulb_params = _lightbulb_params()
reset_time_tolerance = dt.timedelta(minutes=60)
url_regex = re.compile(
    "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)
IMAGE_EXTENSIONS_LIST = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".tiff",
    ".tif",
    ".heif",
    ".heifs",
    ".heic",
    ".heics",
    ".webp",
]

##### Configs & constants end #####
