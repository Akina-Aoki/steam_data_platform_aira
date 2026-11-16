"""One-off check: log in to Snowflake with the key pair and say who we are.

Sends no Steam requests and loads nothing.
"""

import snowflake.connector
from dlt.common.configuration import resolve_configuration
from dlt.destinations.impl.snowflake.configuration import SnowflakeCredentials

from steam_data_platform.connections import loader_credentials

# Build the credentials the same way the pipeline does (dlt reads the key file).
credentials = resolve_configuration(
    SnowflakeCredentials(), explicit_value=loader_credentials()
)
connection = snowflake.connector.connect(**credentials.to_connector_params())
try:
    cursor = connection.cursor()
    cursor.execute("SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
    print(cursor.fetchone())
finally:
    connection.close()