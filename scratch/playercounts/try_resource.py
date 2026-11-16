"""Run the player_counts resource on 3 apps, without Snowflake."""

import logging

from steam_data_platform.ingestion.steam import player_counts

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Stellaris (normal), Prison Architect 2 (unreleased), fake id
for row in list(player_counts([281990, 1257610, 99999999])):
    print(row)