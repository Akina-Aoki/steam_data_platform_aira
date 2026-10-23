"""Snowflake connection settings, read from environment variables (.env)."""

import os


def loader_credentials() -> dict[str, str]:
    """Snowflake credentials for the dlt loader (DLT_USER / STEAM_LOADER)."""
    return {
        "host": os.environ["SNOWFLAKE_ACCOUNT"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "username": os.environ["SNOWFLAKE_LOADER_USER"],
        "password": os.environ["SNOWFLAKE_LOADER_PASSWORD"],
        "role": os.environ["SNOWFLAKE_LOADER_ROLE"],
    }
