# 06  Steam Data Ingestion Plan (dlt)

## Overview

This document plans how we take data from Steam and land it in Snowflake `STEAM_DB.STEAM_RAW` using dlt.

**Scope of this phase:** API extraction and loading only. No dbt models, dimensional modeling, Airflow, Docker, or dashboards yet.

**Status on 2026-10-27:**

- Snowflake warehouse, database, schemas, roles, and users are set up and tested.
- dbt Core is set up, but there are no models yet.
- **Games** (Store `appdetails`) are done and merged into `main`. `STEAM_DB.STEAM_RAW.GAMES` has two snapshots of the 81 Paradox Interactive games (2026-10-23 and 2026-10-26), plus one old Portal 2 test row. Notebook: `notebooks/01_eda_games.ipynb`.
- **Review totals** (`review_summary`) are done: built, tested and loaded on 2026-10-26. `STEAM_DB.STEAM_RAW.REVIEW_SUMMARY` has 81 rows (load id `1793014149.3994608`). Notebook: `notebooks/02_eda_reviews.ipynb`. Tests: `tests/test_steam_dlt.py`.
- The reviews work is committed and merged into `main` (pull request #6, 2026-10-26). Doc: `docs/06_reviews__dlt_ingestion.md`.
- **Player counts** (`player_counts`) are done: built, tested and loaded on 2026-10-27, and merged into `main` (pull request #7). `STEAM_DB.STEAM_RAW.PLAYER_COUNTS` has 81 rows (load id `1793094197.9862032`): 77 with a count (13 of them a real 0) and 4 without data (the 4 unreleased games, `result` 42). Notebook: `notebooks/03_eda_player_counts.ipynb`. Doc: `docs/07_player_counts__dlt_ingestion.md`. Tests: 35 in `tests/test_steam_dlt.py`.
- **The dlt extract and load part is done for all three sources.** dbt is the next phase.
- This replaces the earlier Aviation Nomad data source (Aviationstack) with Steam.

---

## 1. Data Sources

We use three public endpoints. None of them needs a Steam Web API key (my account is restricted, so we avoid keys).

| # | Endpoint | What it gives us | Status |
|---|---|---|---|
| 1 | Store `appdetails` | Title, genres, price, developer, publisher, release date | Verified and loaded (2026-10-23) |
| 2 | `IUserReviewsService/GetAppReviews` (the Store `appreviews` URL does not work for us) | Total thumbs up and thumbs down per game, plus a score and label. It can also return single reviews, but we do not load them | Verified and loaded (2026-10-26) |
| 3 | `ISteamUserStats/GetNumberOfCurrentPlayers` | Number of players in the game right now. Unreleased games and wrong ids give HTTP 404 with `result` 42 and no count | Verified and loaded (2026-10-27) |

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

### Step 1  `appdetails` (done, 2026-10-23)

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

### Step 2  reviews (done, 2026-10-26)

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

### Step 3  `GetNumberOfCurrentPlayers` (done, 2026-10-27)

**Goal:** see what the endpoint really returns, then decide what to store.

Checklist (probe of 6 requests, 2 s apart; details in `docs/07_player_counts__dlt_ingestion.md`):

- [x] Does it work without a key? Yes. A normal game gives HTTP 200 and `{"response": {"player_count": N, "result": 1}}`, with `player_count` as an integer.
- [x] Unreleased game (Prison Architect 2): HTTP **404**, `{"response": {"result": 42}}`, no `player_count`.
- [x] Fake appid (99999999): the same as an unreleased game (404, result 42). So the code alone does not tell "unreleased" from "wrong id".
- [x] The text `<appid>` instead of a number: HTTP 200 with a huge count (26,494,868) and `result` 1. Steam does not check that the id is a number. We do not know what that number counts. We only send ids from our own list.
- [x] No appid: HTTP 400 with an HTML page, not JSON.
- [x] Timestamp: none in the answer, so we add our own `collected_at`.
- [x] Rate limit: Steam publishes none. The full run of 243 requests at 2 s gave no 429.
- [ ] What 42 means exactly: unverified (we believe "no match", from memory).
- [ ] Whether a released game can ever get 404 / 42: not seen yet.

**Decision:** one row per game per run (`append`). A 404 / `result` 42 is stored as a row with `player_count` NULL, and a real 0 stays 0. `collected_at` is taken per row. See section 4.

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
| Player counts | How to build history? | Append a row per collection with a timestamp | **Decided:** `append`, one row per game per run, columns `steam_appid`, `collected_at`, `player_count`, `result` |
| Player counts | What about games Steam has no data for (404, result 42)? | Skip them, as with reviews | **Decided:** keep a row with `player_count` NULL and `result` 42. Every run then has 81 rows, and "no data" is kept apart from a real 0. Only unusable answers are skipped. |
| Player counts | Which time goes in `collected_at`? | One time per run, as in the other tables | **Decided:** one time **per row**, right after Steam answers. A count is one moment and a run takes about 10 minutes. |
| Retry helper | How do we treat a 404? | Raise an error for every 4xx | **Decided:** `get_with_retry` takes an optional `accept_statuses` (we pass 404). Other 4xx still raise. |
| Table names | `games`, `reviews`, `player_counts` | Provisional | **Confirmed:** `games`, `review_summary` (renamed from `reviews`, because it holds totals) and `player_counts` |
| Orchestration | Airflow? | Later, in Docker | **Decided:** no Airflow for now. A scheduled batch script comes later; Airflow is future work. |

dlt **write dispositions**: `replace`, `append`, `merge`. We chose `append` for both `games` and `review_summary`. We would only use `merge` on `recommendationid` if we ever load single reviews.

---

## 5. Where the Code Lives

```text
src/steam_data_platform/
├── settings.py              # GAME_APPIDS, store country/language, request pause
├── connections.py           # Snowflake credentials from environment variables
└── ingestion/
    ├── steam.py             # request helpers + dlt source and resources (games, review_summary, player_counts)
    └── pipelines_steam.py   # creates the dlt pipeline and runs it
tests/
└── test_steam_dlt.py        # tests with fake Steam answers (no network, no Snowflake)
```

This follows the pattern of the reference repository (`<source>.py` and `pipelines_<source>.py`).

Build order:

1. Plain `requests` function, tested on its own. (Done)
2. Wrap it in a dlt resource. (Done)
3. ~~Load into a local test destination~~ Skipped on purpose: we do not use DuckDB in this project. We load straight into Snowflake `STEAM_RAW`.
4. Load into Snowflake `STEAM_RAW`. (Done for `games`, `review_summary` and `player_counts`)

Run command ONLY ONCE A DAY MAX! One run now loads `games`, `review_summary` and `player_counts`: 243 requests, about 10 minutes. Start it at about the same clock time every day, because a player count depends on the hour.

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
- [x] `DLT_USER` is a `PERSON` user with a password and no MFA (`DESC USER`, 2026-10-30), which is why a password-only load worked. The loader now logs in with a key pair (doc 09)
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
3. ~~Commit the reviews work in small commits.~~ Done: merged in pull request #6 (2026-10-26).
4. ~~Notebook 01: the outputs for sections 2, 8, 9 and 10 now exist, but the text still says "not yet run". Update the text.~~ Done (2026-10-30).
5. ~~Probe `GetNumberOfCurrentPlayers`, build the `player_counts` resource, tests, first run, notebook 03, docs 06 and 07.~~ Done: merged in pull request #7 (2026-10-27).
6. ~~Small clean-ups: let `fetch_app_details` use `get_with_retry` too, and add a progress line to the `games` resource.~~ Done (2026-10-30), merged from branch `refactor/ingestion-cleanups`.
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
| 2026-10-26 | Reviews work committed in small commits, pushed and merged into `main` (pull request #6). |
| 2026-10-27 | Probed `GetNumberOfCurrentPlayers` with 6 requests. Normal games: HTTP 200, `result` 1, integer `player_count`. Unreleased game and fake appid: HTTP **404**, `result` 42, no `player_count`. The text `<appid>` instead of a number gave HTTP 200 with a huge count (26,494,868) and `result` 1, so Steam does not check the id and `result` 1 alone does not prove the number belongs to the right game (we do not know what that number counts). No appid: HTTP 400 with an HTML page. |
| 2026-10-27 | Design: table `player_counts`, `append`, one row per game per run, columns `steam_appid`, `collected_at`, `player_count`, `result`. A 404 / `result` 42 is kept as a row with a NULL count (so every run has 81 rows and "no data" stays apart from a real 0). `collected_at` is taken per row. `get_with_retry` got an optional `accept_statuses` (we pass 404), because it used to raise an error on every 4xx and would have counted the 4 unreleased games as failed in every run. |
| 2026-10-27 | Built `fetch_player_count`, `build_player_row` and the `player_counts` resource (progress line every 10 games). Tried it on 3 apps without Snowflake: 1 row with a count, 2 rows with a NULL count and `result` 42. Wrote 16 new tests (35 in total, all passing). `ruff` clean. |
| 2026-10-27 | Full run, one time: all three resources, 243 requests, 10:43 to 10:53 Stockholm time, no 429, load id `1793094197.9862032`. `games` 81 fetched, `review_summary` 81 fetched, `player_counts` 77 with a count, 4 without data, 0 skipped, 0 failed. |
| 2026-10-27 | Validated `PLAYER_COUNTS` in Snowsight, recorded in `notebooks/03_eda_player_counts.ipynb`. 81 rows, 81 games, one load id. The 4 rows without data are the 4 unreleased games. 13 released games have a real 0. Result code check: `result` 1 for all 77 rows with a count (64 above zero, 13 zero), `result` 42 for the 4 without a count. Highest: Hearts of Iron IV with 26,021. About 35 of the 77 have 10 players or fewer (hand count). Staging proposals are in section 10 of the notebook. |
| 2026-10-27 | Wrote `docs/06_reviews__dlt_ingestion.md` and `docs/07_player_counts__dlt_ingestion.md` (decisions with reasons, code map with links to lines). Pushed and merged into `main` (pull request #7, `main` at `c1aa1bc`). Typos met on the way: `stream` instead of `steam` in a push command, and a new branch needs `git push --set-upstream`. |
| 2026-10-27 | Open: what `result` 42 means exactly (unverified); whether a released game can ever get 404 / 42; minimum player count for comparisons; why the Free Edition has 0 players and no reviews; repeated-run rule; a scheduled run at about the same clock time with a non-interactive login; notebook 03 sections 2, 4 and 9 and docs 06 and 07 still say the 13 zero rows were not checked, although the check is now done. |
| 2026-10-30 | Clean-up branch `refactor/ingestion-cleanups`, merged into `main`. `fetch_app_details` now uses `get_with_retry` (the retry loop exists once). Added a progress line to the `games` resource (every 10 games). Added 3 tests for `fetch_app_details` (good game, `null` body, 429 retried through the shared helper): 38 tests, all passing. Rewrote the comments and docstrings in `steam.py` in simpler words. Problems met: one extra space before `def` in the test file gave an `IndentationError`, and pytest could not load the file. Wrote `docs/08_steam_py_code_guide.md` (flow, code map with line links, reasons). |
| 2026-10-30 | Docs and notebook text (new branch from `main`). Notebook 01: sections 2, 8, 9 and 10 now say what we saw instead of "not yet run" (section 2: spot-checked rows show `times_collected = 1`, the whole column was not counted; section 8: the 2 games are *Majesty 2 Collection* and *Galaxy of Pen & Paper +1*, reason unknown; section 9: all 81 are `game`; section 10: the SQL works). Notebook 01 sections 1, 11 and the header still describe the single snapshot of 2026-10-23 on purpose. Docs 05, 06 and 07: line links into `steam.py` and into the tests moved to the new line numbers, and the stale "still has its own copy of the retry code", "no progress line", "tests: none yet" and "not run yet" lines were updated. Open: the notebook 03 text about the 13 zero rows was not checked in this session. |
| 2026-10-30 | Key-pair login on branch `feat/schedule-run`. `DESC USER DLT_USER`: `TYPE` PERSON, password set, `HAS_MFA` false, no key. Snowflake's docs say the default `TYPE` is PERSON, and describe an MFA rollout for human users (phase 3 planned Aug to Oct 2026, per account, dates subject to change). Whether it blocks a password-only load from dlt is our reading, not stated by the page. Decision: switch to a key pair now. Made an unencrypted private key with openssl in `~/.snowflake_keys` (outside the repo, never read or pasted), set the public key with `ALTER USER`, `HAS_KEYPAIR` is true. `loader_credentials()` now passes `private_key_path` (dlt supports it, checked in the installed package), new env variable `SNOWFLAKE_LOADER_PRIVATE_KEY_PATH`, 1 new test (39 tests). A login check printed `('DLT_USER', 'STEAM_LOADER', 'STEAM_WH')`. The full pipeline was not run with the key. Decided against Windows Task Scheduler and a wrapper script (not in the reference repo): the run is by hand, once a day at most, Airflow later. Wrote `docs/09_key_pair_login.md`. Fixed the wrong "password and MFA" lines in docs 03, 05, 06 and 07. Open: notebooks 01 to 03 still connect with the password; `DBT_USER` and `STREAMLIT_USER` are PERSON users with passwords. |
