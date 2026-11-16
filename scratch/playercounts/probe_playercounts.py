"""Probe GetNumberOfCurrentPlayers: print the structure, not the full JSON.

Run: uv run python scratch/playercounts/probe_playercounts.py
No API key and no .env needed. 6 requests, 2 s apart.
"""

import time

import requests

URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
PAUSE_SECONDS = 2.0

CASES = [
    ("Stellaris (normal game)", {"appid": 281990}),
    ("Portal 2 (normal game)", {"appid": 620}),
    ("Prison Architect 2 (unreleased)", {"appid": 1257610}),
    ("fake appid", {"appid": 99999999}),
    ("literal text <appid> (what you pasted)", {"appid": "<appid>"}),
    ("no appid at all", {}),
]


def probe(label: str, params: dict) -> None:
    print(f"\n=== {label} ===")
    try:
        response = requests.get(URL, params=params, timeout=10)
    except requests.RequestException as error:
        print("request failed:", type(error).__name__)
        return

    print("HTTP status:", response.status_code)
    print("content-type:", response.headers.get("Content-Type"))

    try:
        body = response.json()
    except ValueError:
        print("body is not JSON, first 200 chars:", response.text[:200])
        return

    print("body type:", type(body).__name__)
    if not isinstance(body, dict):
        print("body:", body)
        return

    print("top-level keys:", list(body.keys()))
    block = body.get("response")
    print("response block type:", type(block).__name__)
    if isinstance(block, dict):
        for key, value in block.items():
            print(f"  {key} = {value!r}  ({type(value).__name__})")
    print("has player_count:", isinstance(block, dict) and "player_count" in block)


if __name__ == "__main__":
    for position, (label, params) in enumerate(CASES):
        if position > 0:
            time.sleep(PAUSE_SECONDS)
        probe(label, params)