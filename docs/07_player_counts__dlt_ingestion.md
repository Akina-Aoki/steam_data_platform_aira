# 07 Player Counts Ingestion with dlt (Steam `GetNumberOfCurrentPlayers`)

## Overview

Loaded the **number of players right now** for the same 81 Paradox Interactive games from the public Steam `ISteamUserStats/GetNumberOfCurrentPlayers` endpoint into Snowflake `STEAM_DB.STEAM_RAW.PLAYER_COUNTS`, using Python and dlt.

This is the third ingestion step. With it, the extract and load part (dlt) is done for all three sources.

**Branch:** `feat/steam-player-counts-ingestion`
**Status:** Built, tested and loaded on 2026-10-27. The commits and the pull request are still to do.

```text
Steam GetNumberOfCurrentPlayers (api.steampowered.com)
        |
        v
Python (requests) -> dlt resource `player_counts`
        |
        v
STEAM_DB.STEAM_RAW.PLAYER_COUNTS   (loaded by DLT_USER, role STEAM_LOADER)
        |
        v
dbt staging (next phase)
```

Steam can tell us how many people are playing a game at this moment. That number changes all day, so one count is a snapshot of one moment. We ask once per game per run and store the answer with the exact time we got it.


## 1. The Whole Ingestion at a Glance

One pipeline, one source, three resources. One run loads all three tables, one request at a time.

```text
Steam endpoint                          dlt resource        Snowflake table (STEAM_RAW)
-----------------------------------     ----------------    ---------------------------
Store appdetails                    ->  games            -> GAMES
IUserReviewsService/GetAppReviews   ->  review_summary   -> REVIEW_SUMMARY
ISteamUserStats/                    ->  player_counts    -> PLAYER_COUNTS
  GetNumberOfCurrentPlayers
```

| Step | Resource | Rows per run | Document | Code | Notebook |
|---|---|---|---|---|---|
| 1 | `games` | 81 | [05](05_games__dlt_ingestion.md) | [steam.py L240-L290](../src/steam_data_platform/ingestion/steam.py#L240-L290) | [01_eda_games](../notebooks/01_eda_games.ipynb) |
| 2 | `review_summary` | 81 | [06](06_reviews__dlt_ingestion.md) | [steam.py L293-L339](../src/steam_data_platform/ingestion/steam.py#L293-L339) | [02_eda_reviews](../notebooks/02_eda_reviews.ipynb) |
| 3 | `player_counts` | 81 | this document | [steam.py L342-L399](../src/steam_data_platform/ingestion/steam.py#L342-L399) | [03_eda_player_counts](../notebooks/03_eda_player_counts.ipynb) |

| Shared piece | Function | Code |
|---|---|---|
| `steam_source` | Groups the three resources into one dlt source | [steam.py L402-L405](../src/steam_data_platform/ingestion/steam.py#L402-L405) |
| `steam_pipeline()`, `run_steam_pipeline()` | Builds the pipeline (`pipeline_name="steam"`, `dataset_name="steam_raw"`) and runs the source | [pipelines_steam.py L19-L30](../src/steam_data_platform/ingestion/pipelines_steam.py#L19-L30) |
| Entry point | Sets up logging, runs the pipeline, logs only the load ids | [pipelines_steam.py L33-L42](../src/steam_data_platform/ingestion/pipelines_steam.py#L33-L42) |
| `GAME_APPIDS` and the request pause | The 81 games and the 2 s pause | [settings.py](../src/steam_data_platform/settings.py) |
| `get_with_retry` | The one place that does GET, timeout and retry | [steam.py L85-L128](../src/steam_data_platform/ingestion/steam.py#L85-L128) |

## 2. Scope and Data Source

| Item | Decision |
|---|---|
| Games | The same 81 apps in [`GAME_APPIDS`](../src/steam_data_platform/settings.py#L6-L16) |
| Endpoint | `https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/` |
| API key | None needed |
| Parameter | `appid=<one id>` |
| Code | [`PLAYERS_URL`](../src/steam_data_platform/ingestion/steam.py#L26-L28) and [`fetch_player_count`](../src/steam_data_platform/ingestion/steam.py#L153-L176) |

## 3. What We Verified About the API

Probed on 2026-10-27 with a small script (6 requests, 2 s apart). The script lives in `scratch/playercounts/` on my computer and is not in Git, so it has no link.

| Case | HTTP status | `result` | `player_count` |
|---|---:|---:|---|
| Stellaris (normal game) | 200 | 1 | 7859 (integer) |
| Portal 2 (normal game) | 200 | 1 | 868 (integer) |
| Prison Architect 2 (unreleased) | **404** | **42** | missing |
| Fake appid `99999999` | **404** | **42** | missing |
| Text `<appid>` instead of a number | 200 | 1 | 26,494,868 |
| No `appid` at all | 400 (an HTML page, not JSON) | n/a | n/a |

**Findings:**

- **Unreleased games and wrong ids give the same answer:** HTTP 404, `result` 42 and no `player_count`. It is not a `0`. So "no data" and "zero players" are different, and the table has to keep them apart.
- **Steam does not check that the id is a number.** The text `<appid>` returned a huge number with `result` 1. We do not know what that number counts, and we did not guess. It means `result = 1` alone does not prove the number belongs to the right game. We only ever send ids from our own list.
- **We believe 42 means "no match", but that is from memory and not checked.** In the project we only say "Steam has no data".
- **Rate limit:** Steam publishes none for this endpoint. The full run of 243 requests (2 s apart) gave no 429.
- **Not seen yet:** whether a released game can ever get 404 / 42. In the first full run none did.

## 4. Design Decisions

| Topic | Decision | Why |
|---|---|---|
| Table name | `player_counts` | Same naming style as the other two tables. |
| Write mode | `append`, one row per game per run | Every run adds a snapshot, so player activity builds a history for the trend charts. Same as the other two tables. |
| Columns | `steam_appid`, `collected_at`, `player_count`, `result` | `result` is kept because it is the only way to tell "no data" (42) from a real count (1). |
| 404 / `result` 42 | **Store a row** with `player_count` NULL and `result` 42 | Every run then has 81 rows, so it is easy to check that a run is complete. The history shows that we asked and Steam had nothing. When a game is released, its rows change from NULL to a number. Skipping would leave a gap that looks the same as a failure. |
| NULL and zero | Never mixed | A real `0` is stored as `0`. A missing count stays NULL. dbt must not turn NULL into 0. |
| Skipped rows | Only when the answer is unusable (not JSON, no `result`, count is not a number) | We have nothing true to store. The skip is counted and logged. |
| Time | `collected_at` **per row**, taken right after Steam answers | A player count is one moment, and a run takes about 10 minutes. One time for the whole run would make the last game look 10 minutes too early. (`games` and `review_summary` still use one time per run.) |
| Retry code | Use the shared `get_with_retry`, add an optional `accept_statuses` | See section 5. |
| Column types | `player_count` and `result` set to `bigint`, `collected_at` to `timestamp` | A batch where every count is NULL would give dlt nothing to guess the type from. |
| Request pace | 1 request every 2 s, one at a time, no `parallelized=True` | Steam publishes no limit, so we stay slow. dlt alternates between the three resources, so the whole run is about 243 requests and about 10 minutes. |
| Time of day | Start the daily run at about the same clock time | A count depends on the hour. Comparing runs from different hours would mix time-of-day effects with real changes. This goes under limits in the thesis. |
| Orchestration | No Airflow for now | About 243 requests per run. Later a scheduled script. |

## 5. Code

```text
src/steam_data_platform/
├── settings.py              # GAME_APPIDS, REQUEST_PAUSE_SECONDS, ...
├── connections.py           # loader_credentials(): reads SNOWFLAKE_* environment variables
└── ingestion/
    ├── steam.py             # get_with_retry, fetch_player_count, build_player_row,
    │                        # `player_counts` resource, steam_source
    └── pipelines_steam.py   # builds the dlt pipeline and runs it
tests/
└── test_steam_dlt.py        # tests with fake Steam answers (no network, no Snowflake)
```

| Piece | What it does | Code |
|---|---|---|
| `get_with_retry(..., accept_statuses=())` | Same helper as before, plus one new option: status codes in `accept_statuses` (we pass `404`) come back as normal answers instead of raising an error. With the default (empty), nothing changes for the other resources. | [steam.py L85-L128](../src/steam_data_platform/ingestion/steam.py#L85-L128) |
| `fetch_player_count(appid)` | One request per game. Returns `{"player_count": int or None, "result": int}`, or `None` if the answer is not usable at all. | [steam.py L153-L176](../src/steam_data_platform/ingestion/steam.py#L153-L176) |
| `build_player_row(appid, answer, collected_at)` | Builds one row. A missing count stays `None`. | [steam.py L230-L237](../src/steam_data_platform/ingestion/steam.py#L230-L237) |
| `player_counts` resource | Loops over the appids, pauses between requests, logs progress every 10 games, takes `collected_at` per row, yields one row per game. `append`, with typed columns. | [steam.py L342-L399](../src/steam_data_platform/ingestion/steam.py#L342-L399) |
| `steam_source` | Now returns `games`, `review_summary` and `player_counts`. | [steam.py L402-L405](../src/steam_data_platform/ingestion/steam.py#L402-L405) |

**Why the retry helper had to change.** Before, `get_with_retry` treated every 4xx except 429 as a bug on our side and raised an error. For this endpoint a 404 is a normal answer ("no data"). Without the change, the 4 unreleased games would have been counted as *failed* in every run. With `accept_statuses=(404,)` the 404 comes back like any other answer, and `fetch_player_count` reads the body. A 403 or any other 4xx still raises an error ([test](../tests/test_steam_dlt.py#L255-L260)).

**Columns in `PLAYER_COUNTS`:**

| Column | Type in Snowflake | Meaning |
|---|---|---|
| `steam_appid` | `NUMBER(19,0)` | The game |
| `collected_at` | `TIMESTAMP_LTZ(9)` | The moment Steam answered for this row |
| `player_count` | `NUMBER(19,0)` | Players right now. `0` is a real zero. NULL means no data. |
| `result` | `NUMBER(19,0)` | Steam's code. `1` = count given, `42` = no data. |
| `_dlt_load_id`, `_dlt_id` | `VARCHAR` | Added by dlt. The load id is the same for every row of one run. |

## 6. Error Handling

| Situation | What happens |
|---|---|
| HTTP 404 with `result` 42 | A normal answer. Stored as a row with a NULL count. Counted as *without data*. |
| HTTP 200 with a count (including `0`) | Stored as it is. Counted as *with a count*. |
| Timeout, 429 or 5xx | Retried up to 3 times with waits of 30 s, then 60 s. |
| Still 429 after all attempts | The whole run stops (`SteamRateLimitError`). We never try to get around a block. |
| Other 4xx (for example 403 or 400) | Not retried. Raises an error, the game is counted as *failed* and skipped. |
| Still failing after retries (not 429) | Logged, counted as *failed*, skipped. One bad game does not lose the run. |
| Answer not usable (not JSON, no `result`, count is not a number) | Logged, counted as *skipped*, no row. |
| End of the run | One summary line: with a count, without data, skipped, failed, requested. |

Logging uses `logging`, not `print`. The pipeline logs only the load ids, because dlt's own load summary contains the Snowflake account name.

Important to know: if a run stops with an exception, dlt loads nothing from that run.

## 7. Tests

16 new tests were added. The test file now has 35 tests, all passing. They use a hand-written `FakeResponse` and `monkeypatch`. No network and no Snowflake.

| What is tested | Tests | Code |
|---|---:|---|
| `get_with_retry` with `accept_statuses`: an accepted 404 comes back without a retry, a 403 still raises | 2 | [test_steam_dlt.py L240-L260](../tests/test_steam_dlt.py#L240-L260) |
| `fetch_player_count`: a good count, **zero stays zero**, **404 / 42 gives a NULL count and no retry**, 7 kinds of unusable answers return `None`, not JSON | 11 | [test_steam_dlt.py L263-L314](../tests/test_steam_dlt.py#L263-L314) |
| `build_player_row`: a missing count stays `None` | 1 | [test_steam_dlt.py L317-L328](../tests/test_steam_dlt.py#L317-L328) |
| `player_counts` resource: zero and "no data" stay apart, bad games are skipped, each row has its own time in order, repeated 429 stops the run | 2 | [test_steam_dlt.py L331-L376](../tests/test_steam_dlt.py#L331-L376) |

```bash
uv run pytest -q
```

## 8. First Load and Validation

**How to run** (once per day at most, because `append` adds rows on every run):

```bash
uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
```

**Result on 2026-10-27:** 243 requests (81 per resource), 10:43 to 10:53 Stockholm time, about 10 minutes, no 429. Load id `1793094197.9862032`.

| Resource | Result |
|---|---|
| `games` | 81 fetched, 0 skipped, 0 failed |
| `review_summary` | 81 fetched, 0 skipped, 0 failed |
| `player_counts` | 77 with a count, 4 without data, 0 skipped, 0 failed |

**Checked in Snowflake** (queries and notes in [`notebooks/03_eda_player_counts.ipynb`](../notebooks/03_eda_player_counts.ipynb)):

| Check | Result |
|---|---|
| Rows | 81 rows, 81 games, one load id (the same as in the log) |
| Column types | As in section 5 |
| Games without data | 4, all unreleased (`coming_soon = True`): Prison Architect 2, LEGO Skylines, Guardians of the Wild Sky, Afterworld. All have `result` 42 and a NULL count. |
| Zero players | 13 released games have a real `0`. Steam answered them normally. |
| Spread | Highest: Hearts of Iron IV with 26,021. About 35 of the 77 games with a count have 10 players or fewer. This is a hand count from the export. |
| Time | The rows run from 09:43:19 to 09:53:27 UTC, each with its own `collected_at` |
| Snapshots | `GAMES` now has 3 snapshots of 81 rows (plus one old Portal 2 test row). `REVIEW_SUMMARY` has 2. |

Snowsight shows times in the time zone of the session (Pacific, `-0700`), so its times look 9 hours earlier than the Stockholm times in the log. They are the same moment.

## 9. Findings for dbt Staging

These are proposals, to confirm when we build the staging models. The full table with reasons and small SQL sketches is in section 10 of the notebook.

| # | Finding | Proposal |
|---:|---|---|
| 1 | One row per game per load. `collected_at` differs for every row, so it cannot identify a run. | `unique` test on (`steam_appid`, `_dlt_load_id`), `not_null` tests, a relationship test to `games` |
| 2 | `collected_at` is `TIMESTAMP_LTZ` and is taken per row | Convert to UTC. Add the date and the Stockholm hour. Join to `games` and `review_summary` on the date, not the exact time. |
| 3 | NULL means no data, `0` is a real zero | Never fill NULL with 0. Add a flag `has_player_data` from `result = 1`. |
| 3b | A new result code could appear | `accepted_values` test on `result` (1 and 42) with severity `warn`, and a test that `result = 1` always has a count and `result = 42` never has one |
| 4 | `result = 42` does not mean "unreleased" (a fake id gives the same answer) | Use `coming_soon` from `games` |
| 5 | Most games have very few players | Compare only above a minimum, or show only the top games, or use a log scale. The minimum is not decided. |
| 6 | A count is one moment | Run at about the same clock time every day. Show the hour of the snapshot next to the count. |
| 7 | Repeated rows are the history | Not an error. For "players now" use the latest row per game. |

## 10. Known Limits and Open Items

- **One moment, not a daily number.** "Players right now" depends on the hour. A daily snapshot at a random time is a weak measure. More frequent snapshots are possible later but are out of scope.
- **Small games are noise.** For a game with 1 or 2 players, a difference says nothing.
- **Result codes of the 13 zero rows:** we expect all of them to have `result` 1, but we have not checked it yet. The `has_player_data` rule in dbt depends on it.
- **What 42 means:** unverified. We only know that Steam sent it together with a 404 and no count.
- **Released game with no data:** not seen yet.
- **Why *Knights of Pen and Paper 2: Free Edition* has 0 players and no reviews:** unknown.
- **History:** a single snapshot of player counts exists. Each run adds 81 rows.
- **Repeated runs:** proposed rule is one scheduled run per day, and the latest row per game for current-state questions. Not decided.
- **Login:** `DLT_USER` is a `PERSON` account (password and MFA), yet the load worked with a password only, and we do not know why. A scheduled run needs a non-interactive login, for example key-pair authentication.
- **Small clean-ups:** `fetch_app_details` still has its own copy of the retry code, and the `games` resource has no progress line.
- **Undocumented endpoint:** the answer can change without notice.

## 11. Related Files

| File | Purpose |
|---|---|
| [`src/steam_data_platform/ingestion/steam.py`](../src/steam_data_platform/ingestion/steam.py) | Request helpers, the three resources, `steam_source` |
| [`src/steam_data_platform/ingestion/pipelines_steam.py`](../src/steam_data_platform/ingestion/pipelines_steam.py) | Builds the pipeline and runs it |
| [`src/steam_data_platform/settings.py`](../src/steam_data_platform/settings.py) | Game list and request pause |
| [`src/steam_data_platform/connections.py`](../src/steam_data_platform/connections.py) | Snowflake credentials from environment variables |
| [`tests/test_steam_dlt.py`](../tests/test_steam_dlt.py) | Tests with fake Steam answers |
| [`notebooks/03_eda_player_counts.ipynb`](../notebooks/03_eda_player_counts.ipynb) | Validation queries, results and findings |
| [`05_games__dlt_ingestion.md`](05_games__dlt_ingestion.md) | The `games` step |
| [`06_reviews__dlt_ingestion.md`](06_reviews__dlt_ingestion.md) | The `review_summary` step |

## Next Steps

1. Commit the player counts work in small steps and open the pull request.
2. A scheduled run with a non-interactive Snowflake login, at about the same clock time every day.
3. dbt sources and staging on their own branches (`feat/dbt-sources`, `feat/dbt-staging`, ...).
