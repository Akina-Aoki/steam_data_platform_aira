"""Throwaway probe of the Steam appdetails endpoint. Few requests, with pauses."""
import json
import time

import requests

URL = "https://store.steampowered.com/api/appdetails"


def get(appids, **extra):
    time.sleep(1.5)  # be polite: pause before every request
    r = requests.get(URL, params={"appids": appids, "cc": "se", "l": "english", **extra}, timeout=10)
    return r


def show(label, r):
    print(f"\n=== {label} ===")
    print("status:", r.status_code, "| content-type:", r.headers.get("Content-Type"))
    try:
        body = r.json()
    except ValueError:
        print("not JSON:", r.text[:200])
        return None
    print("top-level keys:", list(body.keys()) if isinstance(body, dict) else type(body))
    return body


# 1. Invalid appid
body = show("invalid appid 999999999", get(999999999))
print(json.dumps(body, indent=1)[:300])

# 2. Free game (Counter-Strike 2)
body = show("free game 730", get(730))
d = body["730"]["data"]
print("is_free:", d["is_free"], "| has price_overview:", "price_overview" in d)

# 3. Two appids at once, full data
r = get("620,730")
body = show("two appids, full data", r)
if body is None or r.status_code != 200:
    print("-> body start:", r.text[:200])

# 4. Several appids with the price filter (the documented way to batch)
body = show("batch with filters=price_overview", get("620,730,292030,1245620", filters="price_overview"))
if isinstance(body, dict):
    for k, v in body.items():
        print(k, "success:", v.get("success"), "| data:", v.get("data"))

# 5. Small rate-limit probe: 5 requests, 1.5s apart, look at status codes + headers
codes = []
for _ in range(5):
    r = get(620, filters="price_overview")
    codes.append(r.status_code)
print("\n=== 5 sequential requests ===")
print("status codes:", codes)
print("rate-related headers:", {k: v for k, v in r.headers.items() if "rate" in k.lower() or "limit" in k.lower() or "retry" in k.lower()})
