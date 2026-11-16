"""Probe the Steam appreviews endpoint: 6 requests, prints structure only."""

import json
import time

import requests

STELLARIS = 281990
UNRELEASED = 1257610  # Prison Architect 2
URL = "https://store.steampowered.com/appreviews/{appid}"
SERVICE_URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
PAUSE_SECONDS = 2.0


def short(value) -> str:
    """Cut long values so the output stays readable."""
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def get(label: str, url: str, params: dict) -> dict:
    """One request with a pause; returns the JSON (or {} if it is not JSON)."""
    time.sleep(PAUSE_SECONDS)
    print(f"\n=== {label}")
    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.RequestException as error:
        print("request failed:", type(error).__name__)
        return {}
    print("HTTP", response.status_code)
    try:
        return response.json()
    except ValueError:
        print("not JSON, first 200 chars:", response.text[:200])
        return {}


def show_keys(data: dict) -> None:
    for key, value in data.items():
        if key == "reviews":
            print(f"  {key}: list with {len(value)} items")
        else:
            print(f"  {key}: {short(value)}")


base = {"json": 1, "filter": "recent", "language": "all", "purchase_type": "all"}

# 1. Summary only?
data = get("1. num_per_page=0", URL.format(appid=STELLARIS),
           {**base, "num_per_page": 0, "cursor": "*"})
show_keys(data)

# 2. Five reviews: what does one review look like?
data = get("2. num_per_page=5", URL.format(appid=STELLARIS),
           {**base, "num_per_page": 5, "cursor": "*"})
show_keys(data)
first_ids = [r.get("recommendationid") for r in data.get("reviews", [])]
if data.get("reviews"):
    print("  --- fields of the first review:")
    for key, value in data["reviews"][0].items():
        print(f"    {key}: {short(value)}")
cursor = data.get("cursor")

# 3. Use the cursor: do we get different reviews?
data = get("3. next page with the cursor", URL.format(appid=STELLARIS),
           {**base, "num_per_page": 5, "cursor": cursor})
show_keys(data)
next_ids = [r.get("recommendationid") for r in data.get("reviews", [])]
print("  same ids as page 1?", set(first_ids) & set(next_ids) != set())

# 4. Biggest page size?
data = get("4. num_per_page=200", URL.format(appid=STELLARIS),
           {**base, "num_per_page": 200, "cursor": "*"})
print("  reviews returned:", len(data.get("reviews", [])))

# 5. Unreleased game
data = get("5. unreleased game", URL.format(appid=UNRELEASED),
           {**base, "num_per_page": 5, "cursor": "*"})
show_keys(data)

# 6. The second URL: does it work without a key?
data = get("6. IUserReviewsService", SERVICE_URL,
           {"input_json": json.dumps({"appid": STELLARIS, "num_per_page": 5})})
print("  top-level keys:", list(data.keys()))