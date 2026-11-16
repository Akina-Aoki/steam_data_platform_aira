"""Probe IUserReviewsService/GetAppReviews: totals, filters, page size, cursor."""

import json
import time

import requests

STELLARIS = 281990
UNRELEASED = 1257610  # Prison Architect 2
URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
PAUSE_SECONDS = 2.0


def call(label: str, **options) -> dict:
    """One request with a pause; returns the 'response' block."""
    time.sleep(PAUSE_SECONDS)
    print(f"\n=== {label}")
    try:
        r = requests.get(URL, params={"input_json": json.dumps(options)}, timeout=10)
        print("HTTP", r.status_code)
        return r.json().get("response", {})
    except (requests.RequestException, ValueError) as error:
        print("failed:", type(error).__name__)
        return {}


def show(block: dict) -> None:
    print("  keys:", list(block.keys()))
    print("  query_summary:", json.dumps(block.get("query_summary")))
    print("  day_range_used:", block.get("day_range_used"))
    print("  total_matching:", block.get("total_matching"))
    print("  reviews returned:", len(block.get("reviews", [])))


# 1. Summary only, default filters.
show(call("1. num_per_page=0, defaults", appid=STELLARIS, num_per_page=0))

# 2. Summary only, all time and all languages. Do the totals change?
show(
    call(
        "2. num_per_page=0, filter=all, day_range=365, language=all",
        appid=STELLARIS,
        num_per_page=0,
        filter="all",
        day_range=365,
        language="all",
    )
)

# 3. Biggest page size?
big = call(
    "3. num_per_page=200",
    appid=STELLARIS,
    num_per_page=200,
    filter="recent",
    language="all",
)
show(big)
ids_page1 = {r.get("recommendationid") for r in big.get("reviews", [])}

# 4. Next page with the cursor: any overlap with page 1?
page2 = call(
    "4. page 2 with cursor",
    appid=STELLARIS,
    num_per_page=5,
    filter="recent",
    language="all",
    cursor=big.get("cursor"),
)
show(page2)
ids_page2 = {r.get("recommendationid") for r in page2.get("reviews", [])}
print("  ids in both pages:", len(ids_page1 & ids_page2))

# 5. Unreleased game.
show(call("5. unreleased game", appid=UNRELEASED, num_per_page=0, language="all"))