# 06 — Steam Data Ingestion Plan (Python + dlt)

## Overview

This document plans how we take data from Steam and land it in Snowflake `STEAM_DB.STEAM_RAW` using Python and dlt.

**Scope of this phase:** API extraction and loading only. No dbt models, dimensional modeling, Airflow, Docker, or dashboards yet.

**Status on 2026-10-23:**

- Snowflake warehouse, database, schemas, roles, and users are set up and tested.
- dbt Core is initialized, but no models exist.
- Code for the `appdetails` endpoint exists in `src/steam_data_platform/` (`settings.py`, `connections.py`, `ingestion/steam.py`, `ingestion/pipelines_steam.py`).
- First full load done: 81 Paradox Interactive games in `STEAM_DB.STEAM_RAW.GAMES` (load id `1792757384.0749068`). An earlier test row for Portal 2 (appid 620) is also in the table.
- Validation and first EDA of that table: `notebooks/01_eda_games.ipynb`.
- Reviews and player counts: not started.
- Everything is uncommitted on branch `feat/steam-dlt-ingestion`.
- This replaces the earlier Aviation Nomad data source (Aviationstack) with Steam.

---

## 1. Data Sources

We use three public endpoints. None of them needs a Steam Web API key (my account is restricted, so we avoid keys).

| # | Endpoint | What it gives us | Status |
|---|---|---|---|
| 1 | Store `appdetails` | Title, genres, price, developer, publisher, release date | Verified and loaded (2026-10-23) |
| 2 | Store `appreviews` (or `IUserReviewsService/GetAppReviews`) | Player reviews, thumbs up/down, timestamps, playtime | To verify |
| 3 | `ISteamUserStats/GetNumberOfCurrentPlayers` | Number of players in the game right now | To verify |

URLs to test (Portal 2, `appid=620`):

```text
https://store.steampowered.com/api/appdetails?appids=620&cc=se&l=english
https://store.steampowered.com/appreviews/620?json=1&num_per_page=5&cursor=*
https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=620
```

**Note on reviews:** the earlier plan used `IUserReviewsService/GetAppReviews`. Most public examples use `store.steampowered.com/appreviews/{appid}` instead. We test both and keep whichever works without a key.

The common identifier across all three is `appid`.

**Scope change:** the plan started with 3–5 hand-picked games. The scope is now the 81 apps published by Paradox Interactive on Steam (see `GAME_APPIDS` in `settings.py`).

---

## 2. Vocabulary

| Term | In this project |
|---|---|
| API provider | Steam (Valve) |
| API endpoint | One URL that returns one kind of data |
| Python extraction function | Code that calls one endpoint and returns the JSON |
| dlt resource | One logical table we load (e.g. `games`) |
| dlt source | A group of related resources (e.g. `steam_source`) |
| dlt pipeline | The object that loads resources into Snowflake |

Starting design: **one pipeline, one source, three resources.** We will not assume three endpoints need three pipelines. We can split later if the schedules differ.

---

## 3. Working One Endpoint at a Time

We finish one endpoint completely before starting the next.

**Order:** `appdetails` → `appreviews` → `GetNumberOfCurrentPlayers`

### Step 1 — `appdetails` (done, 2026-10-23)

**Goal:** Understand the response before writing any dlt code.

Checklist:

- [X] Open the URL in the browser and look at the JSON
- [x] Call it with Python `requests` and check the status code
- [x] Confirm the response is keyed by `appid` (as a string) and has a `success` flag
- [x] List the fields we might keep
- [x] Note which fields are nested (lists or objects)
- [x] Check what happens with an invalid `appid` (HTTP 200 with `success: false`)
- [x] Check what `cc=se` changes (it returned EUR, not SEK)
- [x] Find out whether several `appids` can be requested at once (no: a full request with several ids returns HTTP 400; only `filters=price_overview` allows batching, so we make one request per game)
- [x] Test rate limits and error behavior (a full run of 81 requests with a 2 s pause gave no 429; the official limits for the Store endpoints are not documented)

Fields to inspect:

| Field | Question to answer | Answer |
|---|---|---|
| `steam_appid` | Is this our key? | Yes, with `collected_at` (one row per game per run) |
| `name`, `type` | Do we only want `type = game`? | All 12 games checked are `game`; the full check is still open |
| `release_date` | Format? Missing values? | Free text, e.g. `18 Apr, 2011`, also `To be announced` / `Coming soon` |
| `developers`, `publishers` | Lists, so how do we store them? | JSON in one `VARIANT` column |
| `genres`, `categories` | List of objects, so child tables or JSON? | We keep only the description text, as JSON in one column |
| `price_overview` | Units (minor units?), currency, discount fields | Whole numbers in minor units (969 = 9.69), `EUR`, with `initial`, `final` and `discount_percent` |
| `is_free` | What does `price_overview` look like for free games? | The key is missing, so all price columns are NULL |

**Done when:** we can describe the response structure in our own words and have chosen which fields to keep. (Done.)

### Step 2 — `appreviews`

Questions: pagination with `cursor`, page size limit (max 100), review identifier (`recommendationid`), how to avoid reloading the same reviews, which `filter`, `language`, and `purchase_type` to use, which fields are worth keeping (e.g. `voted_up`, playtime, timestamps).

### Step 3 — `GetNumberOfCurrentPlayers`

Questions: the response has no timestamp, so we must add our own collection time. How often would we collect it? How do we handle games that return no count?

---

## 4. Design Decisions

| Topic | Question | Starting idea | Decision |
|---|---|---|---|
| Games list | Which games do we load? | 3–5 hand-picked `appid`s | **Decided:** the 81 Paradox Interactive apps in `GAME_APPIDS`. The list is not the Steam publisher field (see notebook 01, section 3). |
| Games table | Current values or price history? | Decide after step 1 | **Decided:** `append` with our own `collected_at`, so price and discount history builds up |
| Prices | Convert in raw? | Keep Steam's values | **Decided:** keep integer minor units plus currency in raw; convert in dbt staging |
| Nested data | Flatten or keep as JSON? | Let dlt unnest, then review | **Decided:** lists stored as JSON (`VARIANT`) in one column; dbt unpacks later |
| Reviews | How do we avoid duplicates? | Use `recommendationid` as the key | Open |
| Reviews | Full load or incremental? | Start small, then incremental | Open |
| Player counts | How to build history? | Append a row per collection with a timestamp | Open |
| Table names | `games`, `reviews`, `player_counts` | Provisional | `games` confirmed; the others are open |
| Orchestration | Airflow? | Later, in Docker | **Decided:** no Airflow for now. A scheduled batch script comes later; Airflow is future work. |

dlt **write dispositions**: `replace`, `append`, `merge`. We chose `append` for `games`. We expect `merge` on `recommendationid` for `reviews`.

---

## 5. Where the Code Lives

```text
src/steam_data_platform/
├── settings.py              # GAME_APPIDS, store country/language, request pause
├── connections.py           # Snowflake credentials from environment variables
└── ingestion/
    ├── steam.py             # extraction function + dlt source and resources
    └── pipelines_steam.py   # creates the dlt pipeline and runs it
```

This follows the pattern of the reference repository (`<source>.py` and `pipelines_<source>.py`).

Build order:

1. Plain `requests` function, tested on its own. (Done)
2. Wrap it in a dlt resource. (Done)
3. ~~Load into a local test destination~~ Skipped on purpose: we do not use DuckDB in this project. We load straight into Snowflake `STEAM_RAW`.
4. Load into Snowflake `STEAM_RAW`. (Done for `games`)

Run command ONLY ONCE A DAY MAX!

```bash
uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
```

---

## 6. Landing in Snowflake

| Setting | Value |
|---|---|
| Database | `STEAM_DB` |
| Target schema (dlt dataset) | `STEAM_RAW` |
| Role | `STEAM_LOADER` |
| User | `DLT_USER` |
| Warehouse | `STEAM_WH` |

To check later:

- [x] How dlt reads Snowflake credentials, and how that maps to the variable names in `.env.example` (`connections.py` reads the `SNOWFLAKE_*` variables and passes them to the dlt Snowflake destination)
- [ ] `DLT_USER` is a `PERSON` account (password and MFA), yet the load worked with a password only, and we do not know why. Plan a non-interactive login (for example key-pair authentication) before any scheduled run
- [ ] Align `05_create_users.sql` with the real `DLT_USER` account type (open follow-up from doc 03)
- [x] Confirm dlt's extra tables (`_dlt_loads`, `_dlt_pipeline_state`, `_dlt_version`) are allowed by the loader role (they were created, owned by `STEAM_LOADER`)

---

## 7. Business Case and Dashboard (to refine)

Draft questions to guide which fields we keep:

- How are games priced and discounted across the portfolio?
- How do review sentiment, price and player counts relate to each other?
- How do new releases compare with older ones and with flagship franchises?

Possible dashboard views:

- Current players per game and the trend over time
- Percent positive reviews per month
- Price against review score, and discount history
- Playtime at review time
- Genre comparison

Player counts and prices only exist from the day we start collecting them, so an early collection of snapshots matters for the trend charts. Steam gives no sales or revenue figures, so reviews and player counts are proxies.

---

## 8. Next Steps

1. ~~Inspect `appdetails`, pick the games, build the extraction, load into `STEAM_RAW`.~~ Done on 2026-10-23.
2. Run the open queries in `notebooks/01_eda_games.ipynb` (sections 2, 8, 9, 10) and record the results.
3. Add a progress line to the load log; decide the rule for repeated runs.
4. Commit this work (small commits on `feat/steam-dlt-ingestion`).
5. Probe `appreviews`, then build the `reviews` resource.
6. Probe `GetNumberOfCurrentPlayers`, then build the `player_counts` resource.
7. Tests with mocked HTTP, then a scheduled run with a non-interactive Snowflake login.
8. dbt work on separate branches (`feat/dbt-sources`, `feat/dbt-staging`, ...), after ingestion.

---

## 9. Session Notes

Short notes after each session (decisions, problems, solutions, resources). These feed the thesis report.

| Date | Notes |
|---|---|
| 2026-10-23 | Switched data source from Aviationstack to Steam. Wrote this plan. Starting with `appdetails`. |
| 2026-10-23 | Checked `appdetails` with real requests: response keyed by appid as a string, `success: false` for unknown ids with HTTP 200, HTTP 400 for several ids in a full request (so one request per game), prices in minor units, `cc=se` gives EUR, free games have no `price_overview`. Chose `append` with `collected_at` and JSON columns for lists. First dlt load (Portal 2, 1 row) worked; the loader role can create tables. |
| 2026-10-23 | Scope changed to the 81 Paradox Interactive apps on Steam. Hardened `steam.py`: a game that fails is logged and skipped, 429 and 5xx are retried with backoff, repeated 429 stops the run, explicit `collected_at` timestamp, `logging` instead of `print`. The pipeline now logs load ids instead of the full load summary, because that text includes the Snowflake account name. Problems met: `ruff` UP017 (`datetime.UTC`), and an edit that was not saved before the check. |
| 2026-10-23 | Full load: 81 fetched, 0 skipped, 0 failed, about 3.5 minutes at a 2 s pause, no 429. The run is silent while it fetches, so a progress line is still to be added. |
| 2026-10-23 | Validated the table in Snowsight, now recorded in `notebooks/01_eda_games.ipynb`. All 12 compared names match. Only *The Kings' Crusade* has an empty publisher list. `collected_at` is `TIMESTAMP_LTZ`, lists are `VARIANT`. 36 of 81 have no Metacritic score; 4 unreleased games; 2 free games; 2 games without a price not yet explained. Staging rules proposed in the notebook (prices / 100, date parsing, UTC, flatten lists, decode HTML entities). |
| 2026-10-23 | Open: 2 games without a price, full `type` check, 81-name comparison, repeated-run rule, `DLT_USER` account type and non-interactive login, `duckdb` still listed in the `dev` dependency group (we do not use it), notebook queries for sections 2, 8, 9, 10 not yet run. Nothing committed yet. |
