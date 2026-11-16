"""Diagnose: why does the Store appreviews URL return HTML? 4 requests."""

import json
import re
import time

import requests

STELLARIS = 281990
STORE_URL = f"https://store.steampowered.com/appreviews/{STELLARIS}"
SERVICE_URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
PAUSE_SECONDS = 2.0


def short(value) -> str:
    text = repr(value)
    return text if len(text) <= 70 else text[:67] + "..."


def describe(label: str, **kwargs) -> requests.Response | None:
    """Send one request and print what came back (not the whole body)."""
    time.sleep(PAUSE_SECONDS)
    print(f"\n=== {label}")
    try:
        response = requests.get(timeout=10, **kwargs)
    except requests.RequestException as error:
        print("request failed:", type(error).__name__)
        return None
    title = re.search(r"<title>(.*?)</title>", response.text, re.S)
    print("HTTP", response.status_code)
    print("redirects:", [r.status_code for r in response.history])
    print("final url:", response.url.split("?")[0])
    print("content-type:", response.headers.get("Content-Type"))
    print("html title:", title.group(1).strip() if title else None)
    return response


# A. The same call as before, but now we look at the redirects and the title.
describe(
    "A. params dict",
    url=STORE_URL,
    params={"json": 1, "num_per_page": 5, "cursor": "*"},
)

# B. The exact URL text from plan 06.
describe("B. raw url", url=f"{STORE_URL}?json=1&num_per_page=5&cursor=*")

# C. Same as B, with a User-Agent that says who we are.
describe(
    "C. with User-Agent",
    url=f"{STORE_URL}?json=1&num_per_page=5&cursor=*",
    headers={"User-Agent": "steam-thesis-project/0.1 (student project)"},
)

# D. Look INSIDE the IUserReviewsService answer.
response = describe(
    "D. IUserReviewsService",
    url=SERVICE_URL,
    params={
        "input_json": json.dumps({"appid": STELLARIS, "num_per_page": 5}),
    },
)
if response is not None:
    try:
        inner = response.json().get("response", {})
    except ValueError:
        inner = {}
    print("keys inside 'response':")
    for key, value in inner.items():
        if key == "reviews":
            print(f"  {key}: list with {len(value)} items")
        else:
            print(f"  {key}: {short(value)}")
    if inner.get("reviews"):
        print("fields of the first review:")
        for key, value in inner["reviews"][0].items():
            print(f"    {key}: {short(value)}")