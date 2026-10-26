# 05 — Games Ingestion with dlt (Steam `appdetails`)

## Overview

Loaded metadata and prices for the **81 games published by Paradox Interactive** from the public Steam Store `appdetails` endpoint into Snowflake `STEAM_DB.STEAM_RAW.GAMES`, using Python and dlt.

This is the first ingestion step. Reviews (`appreviews`) and current players (`GetNumberOfCurrentPlayers`) come next.

**Branch:** `feat/steam-dlt-ingestion`
**Status:** Completed and merged into `main` (2026-10-23)

```text
Steam Store appdetails
        |
        v
Python (requests) -> dlt resource `games`
        |
        v
STEAM_DB.STEAM_RAW.GAMES   (loaded by DLT_USER, role STEAM_LOADER)
        |
        v
dbt staging (next phase)
```

## 1. Scope and Data Source

| Item | Decision |
|---|---|
| Stakeholder | Paradox Interactive (proof-of-concept scenario, independent academic work) |
| Games | 81 apps in `GAME_APPIDS` in `src/steam_data_platform/settings.py` |
| Endpoint | `https://store.steampowered.com/api/appdetails` |
| API key | None needed. My Steam account is restricted, and a key would not unlock this endpoint anyway. |
| Parameters | `appids=<one id>`, `cc=se`, `l=english` |

Steam's publisher search listed 82 entries. One is a bundle (*The Kings' Crusade Collection*), which `appdetails` cannot serve, so it is excluded. Four of the 81 are unreleased. They are kept to test missing data and to follow upcoming releases.

The IDs came from summaries of Steam's search pages. We checked them after the load (section 6).

## 2. What We Verified About the API

Checked with real requests on 2026-10-23:

- The response is keyed by the appid **as a string**: `{"620": {"success": true, "data": {...}}}`.
- An unknown appid returns HTTP 200 with `{"<id>": {"success": false}}`. Check `success`, not only the status code.
- Several appids in one full request return HTTP 400 (body `null`). Batching only works with `filters=price_overview`. So we make **one request per game**.
- Prices are whole numbers in minor units (969 = 9.69). `cc=se` returned **EUR**, not SEK.
- Free games have `is_free: true` and no `price_overview` key.
- `genres[].id` are strings, but `categories[].id` are integers.
- Descriptions contain HTML entities (for example `&quot;`). `release_date.date` is free text. `categories` can repeat a value.

**Rate limits:** the only official limit is for the keyed Steam Web API (100,000 calls per day). Nothing official exists for the Store endpoints. We pace requests (2 s), retry on 429, run the full load once, and stop on repeated 429. Third-party numbers (about 1 request per second) are unverified.

## 3. Design Decisions

| Topic | Decision | Why |
|---|---|---|
| Pipeline | One dlt pipeline, one source, three resources (only `games` exists so far) | Beginner-friendly. We can split later if schedules differ. |
| Write mode | `append` with our own `collected_at` | Every run adds a row per game, so price and discount history builds up. |
| Prices | Keep Steam's integer minor units plus currency in raw | Raw is a faithful copy. dbt converts. |
| Lists | `developers`, `publishers`, `genres`, `categories` stored as JSON (`VARIANT`) in one column | Avoids dlt child tables. dbt unpacks later. |
| Fields | Keep a shortlist, not the whole response | The response is large (screenshots, movies, HTML). |
| Orchestration | No Airflow for now | About 81 requests per run. Later a scheduled script. |
| Destination | Snowflake only, no DuckDB | Project infrastructure is Snowflake. |

## 4. Code

```text
src/steam_data_platform/
├── settings.py              # GAME_APPIDS, STORE_COUNTRY, STORE_LANGUAGE, REQUEST_PAUSE_SECONDS
├── connections.py           # loader_credentials(): reads SNOWFLAKE_* environment variables
└── ingestion/
    ├── steam.py             # fetch_app_details, build_game_row, `games` resource, steam_source
    └── pipelines_steam.py   # builds the dlt pipeline and runs it
```

This follows the structure of the reference project: the source and resources live in `<source>.py`, and `pipelines_<source>.py` builds the pipeline and runs it under `if __name__ == "__main__":`.

| Piece | What it does |
|---|---|
| `fetch_app_details(appid)` | One request per game. Returns the `data` dict, or `None` if `success` is false. |
| `build_game_row(data, collected_at)` | Picks the fields we keep and flattens them into one row. Every optional field uses `.get`, because free and unreleased games lack some keys. |
| `games` resource | Loops over the appids, pauses between requests, yields one row per game. `append`, with explicit column types for `collected_at` and the JSON lists. |
| `steam_source` | Groups the resources into one dlt source. |
| `steam_pipeline()` | `pipeline_name="steam"`, `dataset_name="steam_raw"`, Snowflake destination. |

Credentials come only from environment variables (`.env`, ignored by Git). The variable names are listed in `.env.example`.

## 5. Error Handling

- **Timeout, 429 or 5xx:** retried up to 3 times with growing waits (30 s, then 60 s).
- **Repeated 429:** the whole run stops (`SteamRateLimitError`). We never try to get around a block.
- **Any other failure for one game** (bad body, other 4xx, still failing after retries): logged, counted as *failed*, and skipped. One bad game does not lose the run.
- **`success = false`:** logged, counted as *skipped*.
- **Run summary** at the end: fetched, skipped, failed, and requested.
- **Logging:** `logging`, not `print`. The pipeline logs only the load ids. dlt's own load summary includes the Snowflake account name, so we do not print it.

Important to know: if a run stops with an exception, dlt loads nothing from that run.

## 6. First Load and Validation

**How to run** (once per day at most, because `append` adds rows on every run):

```bash
uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
```

**Result on 2026-10-23:** 81 requested, 81 fetched, 0 skipped, 0 failed. About 3.5 minutes at a 2 s pause. No 429.

**Checked in Snowflake** (queries and notes in `notebooks/01_eda_games.ipynb`):

| Check | Result |
|---|---|
| Rows | 81 Paradox rows, plus one Portal 2 test row (appid 620) from the first test load. Queries exclude it with `steam_appid <> 620`. |
| Names | All 12 compared against our key match. |
| Publisher check | Every game lists Paradox in `publishers`, except *The Kings' Crusade* (42920), whose publisher list is empty on Steam. |
| Column types | `collected_at` is `TIMESTAMP_LTZ(9)`. List columns are `VARIANT`. Prices, scores and counts are `NUMBER(19,0)`. Booleans are `BOOLEAN`. |
| Free and unreleased | 2 free games, 4 unreleased games (Steam answered `success = true` for all four, with data but no price). |
| Missing values | 8 games without a price (2 free, 4 unreleased, 2 not yet explained). 36 of 81 without a Metacritic score. 1 currency (EUR). |

dlt also created `_DLT_LOADS`, `_DLT_PIPELINE_STATE` and `_DLT_VERSION`. All tables are owned by `STEAM_LOADER`.

## 7. Findings for dbt Staging

These are proposals, to confirm when we build the staging models.

1. **Grain:** one row per `steam_appid` per `collected_at`. Filter on the project's game list, not on the publisher field.
2. **Prices:** divide by 100 and keep NULL when there is no price. Keep `is_free` and `coming_soon` as separate flags so a missing price is never read as 0.
3. **Release date:** free text. Parse it to a date where possible and get NULL for values like `To be announced` or `Coming soon`. Keep the original text.
4. **Time:** convert `collected_at` explicitly (UTC, and a Stockholm date if needed), because `TIMESTAMP_LTZ` follows the session time zone.
5. **Lists:** unpack the JSON lists into one row per game and value (`LATERAL FLATTEN`), and remove duplicates such as repeated categories. One raw untranslated category key was seen.
6. **Text:** decode HTML entities in `short_description` in one place.
7. **Metacritic:** 44 % missing, so it cannot be a main metric. Review sentiment and player counts have to carry the reception analysis.

## 8. Known Limits and Open Items

- **Not run yet:** sections 2, 8, 9 and 10 of the notebook (one line per game, the 2 games without a price, the `type` check, counts of messy-data cases).
- **Names:** only 12 of 81 were compared with my key. The rest rely on the publisher check.
- **History:** a single snapshot exists, so there is no price or discount history yet.
- **Repeated runs:** each run adds 81 rows. Proposed rule: one scheduled run per day, and use the latest `collected_at` for current-state questions.
- **Silent run:** the load log shows nothing for about 3.5 minutes. A progress line is still to be added.
- **Login:** `DLT_USER` is a `PERSON` account (password and MFA), yet the load worked with a password only, and we do not know why. `snowflake_setup/05_create_users.sql` still says `SERVICE`. A scheduled run needs a non-interactive login, for example key-pair authentication.
- **Tests:** none yet. Planned with mocked HTTP (`monkeypatch`, no network, no Snowflake).
- **Data quality:** the Store endpoints are undocumented, so the response can change without notice.

## 9. Related Files

| File | Purpose |
|---|---|
| `notebooks/01_eda_games.ipynb` | Validation queries, results and findings |
| `scratch/docs/05_steam_api_plan.md` | Original API research |
| `scratch/docs/06_dlt_ingestion_plan.md` | Ingestion plan and session notes |
| `scratch/docs/08_agent_prompt_dlt_review.md` | Handoff for the reviews task |

## Next Steps

1. Run the open notebook sections and record the results.
2. Add a progress line to the load log.
3. Probe the `appreviews` endpoint on one game, then design and build the `reviews` resource.
4. Probe `GetNumberOfCurrentPlayers`, then build `player_counts`.
5. Tests, a scheduled run with a non-interactive Snowflake login, then dbt sources and staging on their own branches.
