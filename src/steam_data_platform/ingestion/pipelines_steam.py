"""Pipeline entry point: loads Steam data into Snowflake STEAM_RAW.

Run with:
    uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
"""

import logging

import dlt
from dlt.pipeline import LoadInfo

from steam_data_platform.connections import loader_credentials
from steam_data_platform.ingestion.steam import steam_source
from steam_data_platform.settings import GAME_APPIDS

logger = logging.getLogger(__name__)


def steam_pipeline() -> dlt.Pipeline:
    """Create the dlt pipeline that targets Snowflake."""
    return dlt.pipeline(
        pipeline_name="steam",
        destination=dlt.destinations.snowflake(credentials=loader_credentials()),
        dataset_name="steam_raw",  # dlt creates/uses this schema in STEAM_DB
    )


def run_steam_pipeline() -> LoadInfo:
    """Extract the configured games and load them."""
    return steam_pipeline().run(steam_source(GAME_APPIDS))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_info = run_steam_pipeline()
    # We log the load ids, not the whole `load_info`: its text includes the
    # Snowflake account and user name.
    logger.info("Load finished, load ids: %s", load_info.loads_ids)
    load_info.raise_on_failed_jobs()
