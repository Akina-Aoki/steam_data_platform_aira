"""Snowflake connection settings, read from environment variables (.env)."""

import os


def loader_credentials() -> dict[str, str]:
    """Snowflake credentials for the dlt loader (DLT_USER / STEAM_LOADER).

    The loader logs in with a key pair, not a password. dlt reads the private
    key file from the path in SNOWFLAKE_LOADER_PRIVATE_KEY_PATH.
    """
    return {
        "host": os.environ["SNOWFLAKE_ACCOUNT"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "username": os.environ["SNOWFLAKE_LOADER_USER"],
        "private_key_path": os.environ["SNOWFLAKE_LOADER_PRIVATE_KEY_PATH"],
        "role": os.environ["SNOWFLAKE_LOADER_ROLE"],
    }
