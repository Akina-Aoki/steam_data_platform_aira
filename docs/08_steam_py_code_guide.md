# 08 Code Guide for `steam.py`

## Overview

This guide explains [`steam.py`](../src/steam_data_platform/ingestion/steam.py) in simple words. Open both files side by side: code on the left, this guide on the right. Every section has a link to the lines it talks about.

**Line numbers** match the file on branch `refactor/ingestion-cleanups` (2026-10-30). If you add or remove lines in `steam.py`, the links move a little. The function names stay the same, so search for the name.

The file does one job: **get data from Steam and hand it to dlt**. dlt then loads it into Snowflake.

```text
For each of the 81 games:

  ask Steam  ->  shape the answer into one row  ->  hand the row to dlt  ->  Snowflake
  (fetch_*)      (build_*_row)                       (yield, in a resource)
```

Think of a delivery person with a list of 81 addresses. At each address they knock (fetch), put what they get into a labelled box (build row), and pass the box to the warehouse (dlt).

## 1. Map of the File

| Lines | Piece | Job | Used by |
|---|---|---|---|
| [L25-L36](../src/steam_data_platform/ingestion/steam.py#L25-L36) | Constants | URLs, timeout, number of attempts, waits | all |
| [L39-L47](../src/steam_data_platform/ingestion/steam.py#L39-L47) | Two error types | Say what went wrong | all |
| [L69-L120](../src/steam_data_platform/ingestion/steam.py#L69-L120) | `get_with_retry` | Asks Steam safely, retries if Steam is busy | **all three** |
| [L50-L66](../src/steam_data_platform/ingestion/steam.py#L50-L66) | `fetch_app_details` | Game details for one game | games |
| [L123-L146](../src/steam_data_platform/ingestion/steam.py#L123-L146) | `fetch_review_summary` | Review totals for one game | reviews |
| [L149-L175](../src/steam_data_platform/ingestion/steam.py#L149-L175) | `fetch_player_count` | Players right now for one game | player counts |
| [L178-L218](../src/steam_data_platform/ingestion/steam.py#L178-L218) | `build_game_row` | Makes the row for `games` | games |
| [L221-L234](../src/steam_data_platform/ingestion/steam.py#L221-L234) | `build_review_row` | Makes the row for `review_summary` | reviews |
| [L237-L244](../src/steam_data_platform/ingestion/steam.py#L237-L244) | `build_player_row` | Makes the row for `player_counts` | player counts |
| [L247-L305](../src/steam_data_platform/ingestion/steam.py#L247-L305) | `games` resource | The loop over all games | games |
| [L308-L354](../src/steam_data_platform/ingestion/steam.py#L308-L354) | `review_summary` resource | The loop over all games | reviews |
| [L357-L416](../src/steam_data_platform/ingestion/steam.py#L357-L416) | `player_counts` resource | The loop over all games | player counts |
| [L419-L422](../src/steam_data_platform/ingestion/steam.py#L419-L422) | `steam_source` | Bundles the three resources | pipeline |

**Pattern:** every source has the same three parts: `fetch_*` (ask), `build_*_row` (shape), and a resource (loop). Once you understand `games`, the other two are the same with small differences (section 9).

## 2. Python Words Used in This File

| Word | What it means | Example in the file |
|---|---|---|
| `def` | A named recipe (function) you can use again | `def get_with_retry(...)` |
| `dict` `{...}` | A box with labels: `{"name": "Stellaris"}` | Every row |
| `list` `[...]` | An ordered group of things | `appids` (the 81 game ids) |
| `None` | "There is nothing here". Different from `0` | A missing player count |
| `dict \| None` | Type hint: returns a dict **or** `None` | `fetch_app_details` |
| `.get("key")` | Take a value from a dict, `None` if the key is missing. `["key"]` would crash instead | `price.get("currency")` |
| `x or {}` | Use `x`, but if it is empty or `None`, use an empty dict | `response.json() or {}` |
| `for ... in` | Do something for every item | `for appid in appids` |
| `enumerate` | Gives a counter with each item: 0, 1, 2, ... | `enumerate(appids)` |
| `try / except` | "Try this. If it fails in this way, do that instead" | Skipping a failed game |
| `raise` | Stop with an error. A bare `raise` sends the same error on | Stopping on a rate limit |
| `continue` | Skip the rest of this loop round, go to the next item | Skipping a failed game |
| `yield` | Hand over one row now, then carry on. A normal function gives everything at the end | Inside the resources |
| `@dlt.resource(...)` | A label above a function: "this function makes a table" | Above `games` |
| `isinstance(x, dict)` | Is `x` a dict? Used to check Steam's answer has the shape we expect | `fetch_*` functions |
| f-string `f"appid {appid}"` | Text with a value put inside | Labels for the log |
| `class A(B)` | `A` is a special kind of `B` | `SteamRateLimitError(SteamRequestError)` |

## 3. Constants

[L25-L36](../src/steam_data_platform/ingestion/steam.py#L25-L36)

| Constant | Value | Why |
|---|---|---|
| `REQUEST_TIMEOUT_SECONDS` | 10 | Without a timeout, a stuck request waits forever and the run freezes. |
| `MAX_ATTEMPTS` | 3 | A temporary problem often goes away in a minute. More than 3 would only hammer Steam. |
| `BACKOFF_SECONDS` | 30 | Wait 30 s after attempt 1 and 60 s after attempt 2. Waiting longer each time gives Steam time to recover. |
| `PROGRESS_EVERY` | 10 | A progress line every 10 games, so the run is not silent for minutes. |
| `*_URL` | three URLs | One for each endpoint. None needs an API key. |
| `REQUEST_PAUSE_SECONDS` | 2.0 (in `settings.py`) | Steam publishes no limit for these endpoints, so we stay slow. |

## 4. The Two Errors

[L39-L47](../src/steam_data_platform/ingestion/steam.py#L39-L47)

```python
class SteamRequestError(RuntimeError): ...
class SteamRateLimitError(SteamRequestError): ...
```

| Error | Meaning | What the code does |
|---|---|---|
| `SteamRequestError` | One game failed, even after retries | Log it, skip this game, go on |
| `SteamRateLimitError` | Steam kept answering 429 ("too many requests") | **Stop the whole run** |

**Why two?** A failed game is not a disaster, so we skip it. A rate limit means Steam is telling us to slow down. If we kept going we would only make it worse, and we never try to get around a block.

**Why is one a child of the other?** `SteamRateLimitError` is a special kind of `SteamRequestError`. That is why, in the resources, `except SteamRateLimitError` comes **first**. If the general `except SteamRequestError` came first, it would catch the rate limit too and the run would never stop.

## 5. `get_with_retry`, the Careful Phone Caller

[L69-L120](../src/steam_data_platform/ingestion/steam.py#L69-L120)

This is the **only place that talks to Steam**. All three `fetch_*` functions use it. If we need to change how we retry, we change it here, once.

```text
for attempt 1, 2, 3:
    send the request
    |
    |-- timeout or connection error --------> problem, try again
    |-- HTTP 429 or 5xx --------------------> problem, try again
    |-- status in accept_statuses (404) ----> return it as a normal answer
    |-- any other 4xx (403, 400 ...) -------> raise an error, no retry
    '-- good answer ------------------------> return it

after a problem: wait 30 s (then 60 s), then next attempt

after attempt 3, still a problem:
    429  -> raise SteamRateLimitError   (stop the run)
    else -> raise SteamRequestError     (skip this game)
```

| Decision | Why |
|---|---|
| Retry timeouts, 5xx and 429 | These are temporary. Trying again can work. |
| Do **not** retry other 4xx | A 403 or 400 means our request is wrong. Retrying would give the same answer. |
| Growing wait (30 s, 60 s) | Gives a busy server time to recover. |
| `accept_statuses` | For the player count endpoint, 404 means "no data". That is a real answer, not an error. Without this, the 4 unreleased games would count as *failed* in every run. |
| `label` | Only a name for the log, so a message says which game had the problem. |
| Stop on repeated 429 | We never try to get around a block. |

**Good to know:** if a run stops with an exception, dlt loads nothing from that run.

## 6. The `fetch_*` Functions

Each one asks Steam about **one game** and returns only the part we want, or `None` if the answer is not usable.

### 6.1 `fetch_app_details`: game details

[L50-L66](../src/steam_data_platform/ingestion/steam.py#L50-L66)

```python
params = {"appids": appid, "cc": STORE_COUNTRY, "l": STORE_LANGUAGE}
response = get_with_retry(APPDETAILS_URL, params, f"appid {appid}")
entry = (response.json() or {}).get(str(appid)) or {}
return entry.get("data") if entry.get("success") else None
```

| Line | What it does |
|---|---|
| `params` | The question: which game, which country (for the price), which language. |
| `get_with_retry(...)` | Asks Steam safely. |
| `response.json()` | Turns Steam's answer text into a Python dict. |
| `.get(str(appid))` | Steam's answer is `{"<appid>": {...}}`. The key is the appid as **text**, so we convert it with `str(...)`. |
| `... or {}` (twice) | The answer can be `null`, or the game can be missing. Then we use an empty dict instead of crashing. |
| `entry.get("success")` | Steam can answer HTTP 200 and still say `"success": false` (game not found). So we check the flag, not only the status. |

**Why one request per game?** A full request with several ids returns HTTP 400. Only a price-only request can be batched. See [doc 05](05_games__dlt_ingestion.md).

### 6.2 `fetch_review_summary`: review totals

[L123-L146](../src/steam_data_platform/ingestion/steam.py#L123-L146)

| Step | Why |
|---|---|
| `options = {"appid": ..., "num_per_page": 1, "language": "all"}` | We only want the totals. Steam cannot send *only* the totals, so we ask for 1 review per page and ignore it. `language: all` counts every language. |
| `{"input_json": json.dumps(options)}` | This endpoint wants its options as JSON text inside one parameter. |
| `try: body = response.json() except ValueError` | If the answer is not JSON, return `None` instead of crashing. |
| `isinstance(body, dict)` | We expect `{...}`. A list or `null` is not usable. |
| `query_summary` and `"total_reviews" in summary` | The totals block must exist and contain the main number, or we have nothing true to store. |

More in [doc 06](06_reviews__dlt_ingestion.md).

### 6.3 `fetch_player_count`: players right now

[L149-L175](../src/steam_data_platform/ingestion/steam.py#L149-L175)

Returns `{"player_count": number or None, "result": number}`.

| Answer from Steam | What we return | Why |
|---|---|---|
| HTTP 200, `result` 1, `player_count` 7992 | `{"player_count": 7992, "result": 1}` | A normal count |
| HTTP 200, `player_count` 0 | `{"player_count": 0, "result": 1}` | A **real zero**. Stays 0. |
| HTTP 404, `result` 42, no count | `{"player_count": None, "result": 42}` | "No data". Not the same as zero players. |
| Not JSON, no `result`, or count is not a whole number | `None` | Unusable, so the game is skipped and counted |

The key idea: **`None` (no data) and `0` (really zero players) must never be mixed.** That is why the code checks `count is not None` and `isinstance(count, int)` separately. More in [doc 07](07_player_counts__dlt_ingestion.md).

## 7. The `build_*_row` Functions

They turn Steam's answer into one flat row, a dict with fixed column names. The names become the column names in Snowflake.

| Function | Lines | What is special |
|---|---|---|
| `build_game_row` | [L178-L218](../src/steam_data_platform/ingestion/steam.py#L178-L218) | Picks a shortlist of fields. Prices stay as Steam sends them (whole numbers in cents, 969 = 9.69 EUR). dbt converts later. |
| `build_review_row` | [L221-L234](../src/steam_data_platform/ingestion/steam.py#L221-L234) | Copies the totals as they are. |
| `build_player_row` | [L237-L244](../src/steam_data_platform/ingestion/steam.py#L237-L244) | Keeps the count and the `result` code. A missing count stays `None`. |

Things to notice in `build_game_row`:

- `data.get("price_overview", {})`: a free game has **no** price block. With `.get(..., {})` the price fields become `None`, not a crash.
- `data["steam_appid"]` uses `[]`, not `.get`. A row without its game id would be useless, so here a missing key should stop with an error, not become `None`.
- `genres` and `categories`: Steam sends small objects. The line `[g["description"] for g in ...]` keeps only the text. It is a **list comprehension**, a short way to build a list in one line.
- `developers`, `publishers`, `genres`, `categories` are lists. They are stored as JSON in one column (see the `columns` setting on the resource), so dlt does not make extra child tables.

**Why "raw" and not cleaned?** The raw layer is a faithful copy of what Steam sends. Cleaning (dividing prices by 100, parsing dates) happens later in dbt. That way we can always see what Steam really said.

## 8. A Resource: the Loop (`games` as the Example)

[L247-L305](../src/steam_data_platform/ingestion/steam.py#L247-L305)

A resource is a function that **yields rows**. The `@dlt.resource(...)` label above it tells dlt how to make a table from them.

### The label above the function

| Setting | Meaning | Why |
|---|---|---|
| `name="games"` | The table is called `GAMES` | |
| `write_disposition="append"` | Every run **adds** rows and keeps the old ones | So price changes build up a history over time |
| `columns={...}` | We set some column types ourselves | dlt would otherwise guess from the data. A guess can go wrong, for example when every value in a batch is `NULL`. |

### The loop, step by step

```text
1. collected_at = now          one time for the whole run
2. counters = 0                fetched, skipped, failed
3. for each game:
4.     wait 2 s (not before the first game); log progress every 10 games
5.     try to fetch the game
6.        rate limit?  -> log and stop the whole run (raise)
7.        other error? -> failed + 1, log, skip this game (continue)
8.     no usable data? -> skipped + 1, log, skip this game
9.     fetched + 1, build the row, yield it to dlt
10. log one summary line
```

| Step | Code idea | Why |
|---|---|---|
| 1 | `collected_at = datetime.now(UTC)` | Our own timestamp. Steam gives none. It lets us tell the runs apart. UTC avoids time zone confusion. |
| 4 | `time.sleep(REQUEST_PAUSE_SECONDS)` | Be polite to Steam. |
| 4 | `position % PROGRESS_EVERY == 0` | `%` gives the remainder. It is 0 at game 10, 20, 30 ... so we log every 10 games. |
| 6 | `except SteamRateLimitError: ... raise` | Log, then pass the same error up so the run stops. |
| 7 | `except (SteamRequestError, requests.RequestException)` | `RequestException` is the base class of the errors the `requests` library raises, for example the one from `raise_for_status()`. One bad game must not lose the whole run. |
| 9 | `yield build_game_row(...)` | Hand one row to dlt, then go on with the next game. |

**Why `yield` and not a list?** With `yield`, dlt gets rows one at a time while the loop runs. We do not need to hold everything in memory first.

## 9. How the Three Resources Differ

They share the same skeleton. Only these things change:

| | `games` | `review_summary` | `player_counts` |
|---|---|---|---|
| Lines | [L247-L305](../src/steam_data_platform/ingestion/steam.py#L247-L305) | [L308-L354](../src/steam_data_platform/ingestion/steam.py#L308-L354) | [L357-L416](../src/steam_data_platform/ingestion/steam.py#L357-L416) |
| Fetch function | `fetch_app_details` | `fetch_review_summary` | `fetch_player_count` |
| Row function | `build_game_row` | `build_review_row` | `build_player_row` |
| `collected_at` | One per run | One per run | **One per row** (taken right after Steam answers) |
| Skipped when | `success: false` | No usable totals | Answer not usable |
| Missing data | Skipped | Skipped | **Kept as a row** with `player_count` NULL and `result` 42 |
| Counters | fetched, skipped, failed | fetched, skipped, failed | with a count, without data, skipped, failed |
| Special column types | JSON lists | none | `player_count`, `result` as `bigint` |

**Why `player_counts` is different:**

- A player count is **one moment**, and a run takes about 10 minutes. One time for the whole run would make the last game look 10 minutes too early. So each row gets its own time.
- "No data" is a fact worth keeping. Storing the row means every run has 81 rows, so it is easy to see that a run is complete.

## 10. `steam_source`: the Bundle

[L419-L422](../src/steam_data_platform/ingestion/steam.py#L419-L422)

```python
@dlt.source(name="steam")
def steam_source(appids):
    return games(appids), review_summary(appids), player_counts(appids)
```

It groups the three resources so dlt runs them together in **one pipeline**. [`pipelines_steam.py`](../src/steam_data_platform/ingestion/pipelines_steam.py) builds the pipeline and runs this source.

**Why one pipeline?** It is the simplest design for a beginner project. We can split it later if the schedules differ. One run is 243 requests (81 per resource) and takes about 10 minutes.

## 11. Life of One Game

Take Stellaris (`281990`) in one run:

| # | Where | What happens |
|---|---|---|
| 1 | `games` | `fetch_app_details(281990)` asks the Store for the details |
| 2 | `get_with_retry` | Sends the request. A 200 comes back. |
| 3 | `fetch_app_details` | Takes the `data` part because `success` is true |
| 4 | `build_game_row` | Makes a dict with name, price, genres ... |
| 5 | `games` | `yield`s the row to dlt |
| 6 | `review_summary` | The same steps with `fetch_review_summary`. Row: score, positive, negative, total. |
| 7 | `player_counts` | The same steps with `fetch_player_count`. Row: `{"steam_appid": 281990, "collected_at": ..., "player_count": 7992, "result": 1}` (the number is an example) |
| 8 | dlt | Loads the rows into `GAMES`, `REVIEW_SUMMARY` and `PLAYER_COUNTS` |

## 12. What Happens When Things Go Wrong

| Situation | What happens |
|---|---|
| A timeout, 429 or 5xx for one game | Retried up to 3 times, with waits of 30 s and 60 s |
| Still 429 after 3 attempts | `SteamRateLimitError`: **the whole run stops**, dlt loads nothing from this run |
| Still failing (not 429) after 3 attempts | The game is counted as *failed*, logged, skipped |
| Another 4xx (403, 400 ...) | No retry. Raises an error. The game is counted as *failed*. |
| `success: false` (games) | Counted as *skipped*, logged |
| Answer not usable (not JSON, wrong shape) | `fetch_*` returns `None`. Counted as *skipped*, logged |
| 404 with `result` 42 (player counts) | A normal answer. Stored as a row with a NULL count. |

At the end of each resource, one summary line is logged with the counts. Read it after a run: the numbers must add up to the 81 games requested.

## 13. Why the Code Is Built This Way

| Decision | Why | More |
|---|---|---|
| One shared `get_with_retry` | One place to fix retry problems. Before the clean-up, `fetch_app_details` had its own copy. | Section 5 |
| `fetch_` / `build_` / resource are separate | Each piece does one job and is easy to test alone | Section 1 |
| `append` | History builds up for price, review and player trends | [doc 05](05_games__dlt_ingestion.md) |
| Raw data, no cleaning | A faithful copy. dbt cleans later. | Section 7 |
| Skip a bad game, stop on a rate limit | One bad game must not lose the run. A block means: stop. | Section 4 |
| `None` is not `0` | "No data" and "zero players" mean different things | Section 6.3 |
| Logging with `%s`, not f-strings | The standard way with `logging`. The text is only built if the line is really written. | |
| `logging`, not `print` | Log lines get a time and a level, and can be written to a file for the scheduled run | |
| Only load ids are logged in the pipeline | dlt's full load summary contains the Snowflake account name | [doc 05](05_games__dlt_ingestion.md) |

## 14. How to Read the File (Suggested Order)

1. Constants and the two errors (L25-L47).
2. `get_with_retry` (L69-L120). Read the diagram in section 5 next to it.
3. `fetch_app_details` (L50-L66) and `build_game_row` (L178-L218).
4. The `games` resource (L247-L305). Read the loop steps in section 8 next to it.
5. `steam_source` (L419-L422).
6. The other two sources. Use the difference table in section 9 as a guide.

## 15. How the Tests Fit In

[`tests/test_steam_dlt.py`](../tests/test_steam_dlt.py) checks this file **without** calling Steam or Snowflake. It uses a hand-written `FakeResponse`, a stand-in for Steam's answer.

| Test idea | What it proves |
|---|---|
| A 429 followed by a good answer | `get_with_retry` retries and waits |
| Three 429s in a row | The run stops with `SteamRateLimitError` |
| A 404 with `accept_statuses=(404,)` | The 404 comes back as a normal answer |
| A count of 0 | It stays `0`, not `None` |
| A resource with some bad games | Bad games are skipped, good ones stay, the run goes on |

Run them with:

```bash
uv run pytest -q
```

## 16. Related Files

| File | Purpose |
|---|---|
| [`steam.py`](../src/steam_data_platform/ingestion/steam.py) | The file this guide explains |
| [`pipelines_steam.py`](../src/steam_data_platform/ingestion/pipelines_steam.py) | Builds the dlt pipeline and runs the source |
| [`settings.py`](../src/steam_data_platform/settings.py) | Game list, store country and language, request pause |
| [`connections.py`](../src/steam_data_platform/connections.py) | Snowflake credentials from environment variables |
| [`test_steam_dlt.py`](../tests/test_steam_dlt.py) | Tests with fake Steam answers |
| [`05_games__dlt_ingestion.md`](05_games__dlt_ingestion.md) | The `games` step |
| [`06_reviews__dlt_ingestion.md`](06_reviews__dlt_ingestion.md) | The `review_summary` step |
| [`07_player_counts__dlt_ingestion.md`](07_player_counts__dlt_ingestion.md) | The `player_counts` step |
