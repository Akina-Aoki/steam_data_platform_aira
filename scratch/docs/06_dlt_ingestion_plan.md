# 06  Steam Data Ingestion Plan (dlt)

## Overview

This document plans how we take data from Steam and land it in Snowflake `STEAM_DB.STEAM_RAW` using dlt.

**Scope of this phase:** API extraction and loading only. No dbt models, dimensional modeling, Airflow, Docker, or dashboards yet.

**Status on 2026-10-26:**

- Snowflake warehouse, database, schemas, roles, and users are set up and tested.
- dbt Core is set up, but there are no models yet.
- **Games** (Store `appdetails`) are done and merged into `main`. `STEAM_DB.STEAM_RAW.GAMES` has two snapshots of the 81 Paradox Interactive games (2026-10-23 and 2026-10-26), plus one old Portal 2 test row. Notebook: `notebooks/01_eda_games.ipynb`.
- **Review totals** (`review_summary`) are done: built, tested and loaded on 2026-10-26. `STEAM_DB.STEAM_RAW.REVIEW_SUMMARY` has 81 rows (load id `1793014149.3994608`). Notebook: `notebooks/02_eda_reviews.ipynb`. Tests: `tests/test_steam_dlt.py`.
- **Player counts:** not started.
- The reviews work is on branch `feat/steam-reviews-ingestion` and is **not committed yet**.
- This replaces the earlier Aviation Nomad data source (Aviationstack) with Steam.

---

## 1. Data Sources

We use three public endpoints. None of them needs a Steam Web API key (my account is restricted, so we avoid keys).

| # | Endpoint | What it gives us | Status |
|---|---|---|---|
| 1 | Store `appdetails` | Title, genres, price, developer, publisher, release date | Verified and loaded (2026-10-23) |
| 2 | `IUserReviewsService/GetAppReviews` (the Store `appreviews` URL does not work for us) | Total thumbs up and thumbs down per game, plus a score and label. It can also return single reviews, but we do not load them | Verified and loaded (2026-10-26) |
| 3 | `ISteamUserStats/GetNumberOfCurrentPlayers` | Number of players in the game right now | To verify |

URLs to test (Portal 2, `appid=620`):

```text
https://store.steampowered.com/api/appdetails?appids=620&cc=se&l=english
https://store.steampowered.com/appreviews/620?json=1&num_per_page=5&cursor=*
https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=620
```

**Note on reviews (tested 2026-10-26):** the Store URL `store.steampowered.com/appreviews/{appid}` did not work for us. In all three versions we tried, Steam sent us to the Store home page instead of giving data. We do not know why, so we dropped it. The URL `api.steampowered.com/IUserReviewsService/GetAppReviews/v1/` works without a key, so we use that one.

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

### Step 2 — reviews (done, 2026-10-26)

**Goal:** see what the reviews endpoint really returns, then decide what to store.

Checklist:

- [x] Which URL works without a key? Only `IUserReviewsService/GetAppReviews/v1/` (the input goes in as JSON in `input_json`). The Store `appreviews` URL sends us to the Store home page.
- [x] What is in the answer? `query_summary` (the totals), `reviews` (a list), `cursor` (a bookmark for the next page), `day_range_used` and `total_matching`.
- [x] What is in the totals? `review_score` (0 to 9), `review_score_desc` (a label like "Very Positive"), `total_positive`, `total_negative` and `total_reviews`. They stayed the same when we changed the day range and the language, so they are Steam's all-time totals.
- [x] Can we ask for only the summary? No. `num_per_page=0` still gave us 20 reviews. We ask for 1 review per page instead (`num_per_page=1` works).
- [x] Page size limit: 100. We asked for 200 and got 100.
- [x] Cursor: works. Page 2 had no reviews in common with page 1. The totals only come with the first page.
- [x] Review identifier: `recommendationid`.
- [x] Unreleased game: no error, just zeros and the label `No user reviews`. A wrong appid gives us no usable summary (we did not look at exactly what Steam sent), so we skip it.
- [x] Rate limit: Steam publishes none. Our full run of 162 requests (games and reviews) at one request every 2 seconds gave no 429.

**Decision:** we store only the totals, one row per game per run (see section 4). Loading every review would mean thousands of requests: Stellaris alone has about 77,000 reviews, which is about 770 pages of 100.

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
| Reviews | How do we avoid duplicates? | Use `recommendationid` as the key | **Decided:** not needed. We store totals, not single reviews, so there is no review id to check. It is one row per game per run, like `games`. |
| Reviews | Full load or incremental? | Start small, then incremental | **Decided:** a snapshot of the totals on every run (`append`). Single reviews are not loaded. We can add them later if the thesis needs playtime or language. |
| Player counts | How to build history? | Append a row per collection with a timestamp | Open |
| Table names | `games`, `reviews`, `player_counts` | Provisional | `games` and `review_summary` confirmed (we renamed `reviews`, because it holds totals, not reviews); `player_counts` is open |
| Orchestration | Airflow? | Later, in Docker | **Decided:** no Airflow for now. A scheduled batch script comes later; Airflow is future work. |

dlt **write dispositions**: `replace`, `append`, `merge`. We chose `append` for both `games` and `review_summary`. We would only use `merge` on `recommendationid` if we ever load single reviews.

---

## 5. Where the Code Lives

```text
src/steam_data_platform/
├── settings.py              # GAME_APPIDS, store country/language, request pause
├── connections.py           # Snowflake credentials from environment variables
└── ingestion/
    ├── steam.py             # request helpers + dlt source and resources (games, review_summary)
    └── pipelines_steam.py   # creates the dlt pipeline and runs it
tests/
└── test_steam_dlt.py        # tests with fake Steam answers (no network, no Snowflake)
```

This follows the pattern of the reference repository (`<source>.py` and `pipelines_<source>.py`).

Build order:

1. Plain `requests` function, tested on its own. (Done)
2. Wrap it in a dlt resource. (Done)
3. ~~Load into a local test destination~~ Skipped on purpose: we do not use DuckDB in this project. We load straight into Snowflake `STEAM_RAW`.
4. Load into Snowflake `STEAM_RAW`. (Done for `games`)

Run command ONLY ONCE A DAY MAX! One run now loads both `games` and `review_summary`: 162 requests, about 7 minutes.

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
2. ~~Probe the reviews endpoint, build the `review_summary` resource, write tests and the notebook.~~ Done on 2026-10-26.
3. Run `uv run pytest -q` once more (the 19 tests passed, but `ruff format` changed the test file afterwards), then commit the reviews work in small commits on `feat/steam-reviews-ingestion`. Ask before committing.
4. Notebook 01: the outputs for sections 2, 8, 9 and 10 now exist, but the text still says "not yet run". Update the text.
5. Probe `GetNumberOfCurrentPlayers`, then build the `player_counts` resource.
6. Small clean-ups: let `fetch_app_details` use `get_with_retry` too (it still has its own copy of the retry code), and add a progress line to the `games` resource (only `review_summary` has one).
7. Decide the rule for repeated runs (proposal: one run per day) and set up a scheduled run with a non-interactive Snowflake login.
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
| 2026-10-26 | Tested the reviews endpoint with real requests (about 6 per probe, one game). The Store URL `store.steampowered.com/appreviews/...` redirects to the Store home page in all 3 versions we tried, so we dropped it (cause unknown). `IUserReviewsService/GetAppReviews` works without a key. `query_summary` holds the all-time totals. `num_per_page=0` does not give a summary only (it returned 20 reviews), the page size stops at 100, and the cursor works. An unreleased game gives zeros, and a wrong appid gives no usable summary. |
| 2026-10-26 | Decided to store only the review totals (one row per game per run, `append`), not single reviews. Stellaris alone has about 77,000 reviews, which is about 770 requests for one game. Columns: `steam_appid`, `collected_at`, `review_score`, `review_score_desc`, `total_positive`, `total_negative`, `total_reviews`. This gives a sentiment history over time and needs only 81 requests per run. |
| 2026-10-26 | Wrote `get_with_retry`, `fetch_review_summary`, `build_review_row` and the `review_summary` resource in `steam.py`, with a progress line every 10 games. Tested the fetch on 3 apps (Stellaris, an unreleased game, a fake id) before loading anything: the 3 behaved as expected. Wrote 19 tests with fake Steam answers. One failed at first because dlt wraps errors raised inside a resource in its own `ResourceExtractionError`. The code was right and the test was wrong, so we fixed the test. A second failure came from pasting the new test below the old one in the file, so the old copy was still there. Emptying the file before pasting fixed it. |
| 2026-10-26 | Full run, one time: `games` and `review_summary` together, 162 requests, about 7 minutes (12:29 to 12:36 Stockholm time), no 429, load id `1793014149.3994608`. dlt alternates between the two resources one row at a time, so it stays one request at a time (about 2.5 seconds each). In Snowsight: 81 rows in `REVIEW_SUMMARY` with a single `collected_at`, no game without a summary, and `GAMES` now has two snapshots (81 rows each). |
| 2026-10-26 | Notebook 02 results: no duplicates, counts always add up (positive + negative = total), no NULLs. 5 games have no reviews: 4 unreleased games and *Knights of Pen and Paper 2: Free Edition* (released, free, reason unknown). 43 of 81 games have fewer than 1,000 reviews, so their percent positive is noisy. Steam's labels follow clear percent bands (below 40 %, 40 to 70 %, 70 to 80 %, 80 % and up), but `review_score = 0` is used for both "no reviews" and "1 user review", and the label is free text (for example `1 user reviews`). 9 proposals for dbt staging are in section 10 of the notebook. |
| 2026-10-26 | Open: why the Free Edition has no reviews; minimum number of reviews for comparisons (100 is only a proposal); whether a total can go down between runs (needs more than one run); price against sentiment (no correlation calculated yet); repeated-run rule; `DLT_USER` account type and non-interactive login. `duckdb` is no longer in `pyproject.toml` (checked). Nothing committed yet. |
