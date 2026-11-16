"""Test 1: Try fetch_review_summary on 3 apps. No Snowflake, 3 requests.

Test it without loading anything into Snowflake. 
This is 3 requests: Stellaris, the unreleased game, 
and a fake appid (to see what Steam answers for a wrong id).

Checks:
- whether num_per_page=1 works
- what the fake id returns
- that nothing crashes.
-----------------------------------------------------------------

import time

from steam_data_platform.ingestion.steam import fetch_review_summary

for appid in (281990, 1257610, 99999999):  # Stellaris, unreleased, fake id
    print(appid, fetch_review_summary(appid))
    time.sleep(2)
"""


""" Test 2: Run the review_summary resource on 3 apps and print the rows. No Snowflake."""

import logging

from steam_data_platform.ingestion.steam import review_summary

logging.basicConfig(level=logging.INFO)

for row in review_summary([281990, 1257610, 99999999]):
    print(row)