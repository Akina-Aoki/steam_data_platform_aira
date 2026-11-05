# 06 Reviews Ingestion with dlt (Steam `GetAppReviews`)

## Overview

Loaded the **review totals** for the same 81 Paradox Interactive games from the public Steam `IUserReviewsService/GetAppReviews` endpoint into Snowflake `STEAM_DB.STEAM_RAW.REVIEW_SUMMARY`, using Python and dlt.

- This is the second ingestion step. 
- Games are in [05_games__dlt_ingestion.md](05_games__dlt_ingestion.md). 
- Current players are in [07_player_counts__dlt_ingestion.md](07_player_counts__dlt_ingestion.md).

**Branch:** `feat/steam-reviews-ingestion`
**Status:** Completed and merged into `main` (2026-10-26, pull request #6)
**Update 2026-11-02:** a mistake was found and fixed. The code sent `language: "all"`, which Steam ignores, so the totals counted **English reviews only**. It now sends `languages: ["all"]`. Rows loaded before 2026-11-02 stay English only. See section 2 and section 9. Recent reviews (the last 30 days) are in [doc 11](11_review_recent__dlt_ingestion.md).

```text
Steam GetAppReviews (api.steampowered.com)
        |
        v
Python (requests) -> dlt resource `review_summary`
        |
        v
STEAM_DB.STEAM_RAW.REVIEW_SUMMARY   (loaded by DLT_USER, role STEAM_LOADER)
        |
        v
dbt staging (next phase)
```

For each game, Steam keeps a counter of thumbs up and thumbs down. We ask Steam for those counters once per run and store them with the time we asked. We do **not** store the single reviews due to call rate limits and risks of being blocked.


## 1. Scope and Data Source

| Item | Decision |
|---|---|
| Games | The same 81 apps in [`GAME_APPIDS`](../src/steam_data_platform/settings.py#L6-L16) |
| Endpoint | `https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/` |
| API key | None needed |
| Parameters | One JSON string in `input_json`: `{"appid": <id>, "num_per_page": 1, "languages": ["all"]}`. Until 2026-11-02 it said `"language": "all"`, which Steam ignores (section 2). |
| Keep | Only the `query_summary` block (the totals). The list of single reviews is ignored. |
| Code | [`REVIEWS_URL`](../src/steam_data_platform/ingestion/steam.py#L34) and [`fetch_review_summary`](../src/steam_data_platform/ingestion/steam.py#L131-L156) |

## 2. Verified About the API

Checked with real requests on 2026-10-26 (about 6 requests per probe, one game at a time):

| Question | Tried | Answer |
|---|---|---|
| Which URL works without a key? | The Store URL `store.steampowered.com/appreviews/{appid}` in 3 versions | It sent us to the Store home page every time. We do not know why, so we dropped it. |
| | `api.steampowered.com/IUserReviewsService/GetAppReviews/v1/` | Works. The input goes in as JSON in `input_json`. |
| What is in the answer? | Looked at the keys | `query_summary` (the totals), `reviews` (a list), `cursor` (a bookmark for the next page), `day_range_used` and `total_matching`. |
| What is in the totals? | Looked at `query_summary` | `review_score` (0 to 9), `review_score_desc` (a label like "Very Positive"), `total_positive`, `total_negative`, `total_reviews`. |
| Do the totals depend on language or day range? | Changed `language` and `day_range` | They stayed the same, so we wrote that they are Steam's all-time totals. **Half of this was wrong.** The totals do not follow `day_range`, which is true. But `language` is not an option Steam knows. The real option is `languages`, a list (found on 2026-11-02). With `languages: ["all"]` the all-time total of Stellaris is 139,722. Without it, Steam counts English only (76,854). |
| Can we ask for the totals only? | `num_per_page=0` | No. It still returned 20 reviews. `num_per_page=1` works, so we ask for 1. |
| Page size limit | Asked for 200 | We got 100. |
| Does the cursor work? | Asked for page 2 | Yes. Page 2 had no reviews in common with page 1. The totals only come with the first page. |
| Review identifier | Looked at one review | `recommendationid` |
| Unreleased game | Prison Architect 2 | No error. Zeros and the label `No user reviews`. |
| Wrong appid | Fake id | No usable summary. We did not look at exactly what Steam sent, so we skip it. |
| Rate limit | Full run of 162 requests (games + reviews), 2 s apart | No 429. Steam publishes no limit for this endpoint. |

## 3. Design Decisions

| Topic | Decision | Why |
|---|---|---|
| Totals or every review | **Totals only** | Stellaris alone has about 77,000 reviews. At 100 per page that is about 770 requests for one game. The totals need 81 requests per run and still show how sentiment changes over time. We can add single reviews later if the thesis needs playtime or language. |
| Endpoint | `IUserReviewsService/GetAppReviews` | The Store `appreviews` URL does not work for us (section 2). |
| Request size | 1 review per page, all languages (`languages: ["all"]`, since 2026-11-02) | The smallest answer we can ask for. The totals come with the first page anyway. |
| Table name | `review_summary` | The first idea was `reviews`, but the table holds totals, not reviews. |
| Write mode | `append` with our own `collected_at` | Every run adds one row per game, so sentiment builds a history. Same as `games`. |
| Key | None needed | There is no review id, because we store totals. It is one row per game per run. |
| Raw layer | Keep Steam's values as they are | Score 0–9 and the text label stay raw. dbt calculates the percent positive later. |
| Pipeline | The same pipeline and source as `games` | `steam_source` returns both resources, so one run loads both tables. |
| Retry code | New shared helper [`get_with_retry`](../src/steam_data_platform/ingestion/steam.py#L77-L128) | The retry logic should exist once. `fetch_app_details` used its own copy at first. Since the clean-up of 2026-10-30 it uses `get_with_retry` too. |
| Pace | One request at a time, 2 s pause | Steam publishes no limit, so we stay slow. |
| Orchestration | No Airflow for now | About 81 requests per resource per run. Later a scheduled script. |

## 4. Code

```text
src/steam_data_platform/
├── settings.py              # GAME_APPIDS, REQUEST_PAUSE_SECONDS, ...
├── connections.py           # loader_credentials(): reads SNOWFLAKE_* environment variables
└── ingestion/
    ├── steam.py             # get_with_retry, fetch_review_summary, build_review_row,
    │                        # `review_summary` resource, steam_source
    └── pipelines_steam.py   # builds the dlt pipeline and runs it
tests/
└── test_steam_dlt.py        # tests with fake Steam answers (no network, no Snowflake)
```

| Piece | Function | Code |
|---|---|---|
| `get_with_retry(url, params, label)` | One GET with a timeout. Retries timeouts, 5xx and 429 with growing waits. Raises `SteamRateLimitError` on repeated 429 and `SteamRequestError` on other lasting problems. | [steam.py L77-L128](../src/steam_data_platform/ingestion/steam.py#L77-L128) |
| `SteamRequestError`, `SteamRateLimitError` | Our two error types. The first means "skip this game", the second means "stop the run". | [steam.py L47-L55](../src/steam_data_platform/ingestion/steam.py#L47-L55) |
| `fetch_review_summary(appid)` | One request per game. Returns the `query_summary` dict, or `None` if the answer has no usable summary (not JSON, no summary, no `total_reviews`). | [steam.py L131-L156](../src/steam_data_platform/ingestion/steam.py#L131-L156) |
| `build_review_row(appid, summary, collected_at)` | Picks the totals and builds one row. | [steam.py L300-L313](../src/steam_data_platform/ingestion/steam.py#L300-L313) |
| `review_summary` resource | Loops over the appids, pauses between requests, logs progress every 10 games, yields one row per game. `append`, with `collected_at` typed as a timestamp. | [steam.py L428-L474](../src/steam_data_platform/ingestion/steam.py#L428-L474) |
| `steam_source` | Groups the resources into one dlt source. | [steam.py L662-L671](../src/steam_data_platform/ingestion/steam.py#L662-L671) |
| `steam_pipeline()` and `run_steam_pipeline()` | `pipeline_name="steam"`, `dataset_name="steam_raw"`, Snowflake destination. | [pipelines_steam.py L19-L30](../src/steam_data_platform/ingestion/pipelines_steam.py#L19-L30) |

**Columns in `REVIEW_SUMMARY`:**

| Column | Meaning |
|---|---|
| `steam_appid` | The game |
| `collected_at` | When we collected it. One time for the whole run (taken when the resource starts). |
| `review_score` | Steam's score from 0 to 9 |
| `review_score_desc` | Steam's label, free text (for example `Very Positive`, `No user reviews`, `1 user reviews`) |
| `total_positive`, `total_negative`, `total_reviews` | All-time totals. **English reviews only** in the loads before 2026-11-02, all languages from then on. |

Credentials come only from environment variables (`.env`, ignored by Git). The names are in `.env.example`.

## 5. Error Handling

| Situation | What happens |
|---|---|
| Timeout, 429 or 5xx | Retried up to 3 times with waits of 30 s, then 60 s. |
| Still 429 after all attempts | The whole run stops (`SteamRateLimitError`). We never try to get around a block. |
| Other 4xx | Not retried. It raises an error, because it points to a bug on our side. The game is counted as *failed* and skipped. |
| Still failing after retries (not 429) | Logged, counted as *failed*, skipped. One bad game does not lose the run. |
| Answer without a usable summary | Logged, counted as *skipped*. |
| End of the run | One summary line: fetched, skipped, failed, requested. |

Logging uses `logging`, not `print`. The pipeline logs only the load ids, because dlt's own load summary contains the Snowflake account name.

Important to know: if a run stops with an exception, dlt loads nothing from that run.

## 6. First Load and Validation

**How to run** (once per day at most, because `append` adds rows on every run):

```bash
uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
```

**Result on 2026-10-26:** `games` and `review_summary` together, 162 requests, about 7 minutes (12:29 to 12:36 Stockholm), no 429. Load id `1793014149.3994608`. dlt alternates between the resources one row at a time, so requests still go out one at a time (about 2.5 s each).

**Checked in Snowflake** (queries and notes in [`notebooks/02_eda_reviews.ipynb`](../notebooks/02_eda_reviews.ipynb)):

| Check | Result |
|---|---|
| Rows | 81 rows, 81 games, one `collected_at` |
| Duplicates | None |
| Column types | `collected_at` is `TIMESTAMP_LTZ(9)`. Counts and score are `NUMBER(19,0)`. The label is `VARCHAR`. |
| Consistency | Positive + negative = total in all 81 rows. No NULLs. |
| Games without reviews | 5: the 4 unreleased games and *Knights of Pen and Paper 2: Free Edition* (released and free, reason unknown). |
| Review volume | 43 of 81 games have fewer than 1,000 reviews. Only 13 have 10,000 or more. |
| Labels | Very Positive, Mostly Positive, Mixed, Mostly Negative, `No user reviews`, `1 user reviews`. No Overwhelmingly labels in this data. |
| Label and percent | In this data the label follows clear percent bands: below 40 %, 40 to 70 %, 70 to 80 %, 80 % and up. This is what we see in 81 games, not a rule published by Steam. |

A second snapshot of 81 rows was added on 2026-10-27, together with the player counts run ([doc 07](07_player_counts__dlt_ingestion.md)).

**Language fix (2026-11-02):** while we probed the recent reviews ([doc 11](11_review_recent__dlt_ingestion.md)), the all-time total of Stellaris came out as 139,722 with `languages: ["all"]`, but we had stored 76,854. The old option `language` is ignored by Steam, so the totals were English only. We changed the option name and added a test that checks it. The older rows were **not** changed. In the full run of 2026-11-02 the sum of `total_reviews` over the 81 games went from 674,829 (load of 2026-10-30) to 1,269,461. Notebook 02 and the earlier docs still show the English-only numbers, because they describe the earlier loads.

## 7. Tests

19 tests were written for the reviews work and the shared retry helper (the file now has more, see [doc 07](07_player_counts__dlt_ingestion.md)). They use a hand-written `FakeResponse` and `monkeypatch`. No network and no Snowflake.

| Tested| Tests total | Code |
|---|---|---|
| `get_with_retry`: good answer, 429 then success, timeout then success, 429 on every attempt, 500 is not a rate limit, other 4xx is not retried | 6 | [test_steam_dlt.py L71-L122](../tests/test_steam_dlt.py#L71-L122) |
| `fetch_review_summary`: good answer, zero counts are kept, unusable answers return `None` (5 cases), not JSON, and (added 2026-11-02) the question asks for all languages | 9 | [test_steam_dlt.py L125-L179](../tests/test_steam_dlt.py#L125-L179) |
| `build_review_row` | 1 | [test_steam_dlt.py L182-L196](../tests/test_steam_dlt.py#L182-L196) |
| `review_summary` resource: bad games are skipped, repeated 429 stops the run | 2 | [test_steam_dlt.py L199-L234](../tests/test_steam_dlt.py#L199-L234) |
| `games`: `fetch_app_details` (a good game, `success=false`, a `null` answer, a 429 that is retried) and `build_game_row` (a free game has no price). The last 3 `fetch_app_details` tests were added on 2026-10-30. | 5 | [test_steam_dlt.py L237-L282](../tests/test_steam_dlt.py#L237-L282) |

dlt wraps any error raised inside a resource in `ResourceExtractionError`. That is why the rate-limit test checks `error.value.__cause__`.

```bash
uv run pytest -q
```

## 8. Findings for dbt Staging

These are proposals, to confirm when we build the staging models. The full list with reasons is in section 10 of the notebook.

| # | Finding | Proposal |
|---:|---|---|
| 1 | One row per game per run, no duplicates | `unique` test on (`steam_appid`, `collected_at`), `not_null` on both |
| 2 | `collected_at` follows the session time zone | Convert to UTC explicitly, add a calendar date for joining with `games` |
| 3 | Counts add up | Keep the three counts. Calculate `pct_positive = total_positive / NULLIF(total_reviews, 0)`. |
| 4 | 5 games have no reviews | Keep the rows, add a flag such as `has_reviews`. Use `coming_soon` from `games` for "unreleased". |
| 5 | The label is free text, and score 0 means both "no reviews" and "1 review" | Keep both raw. Do not test the label against a fixed list. Base the analysis on `pct_positive` and `total_reviews`. |
| 6 | Small samples | Show the number of reviews next to every percent. No minimum is needed because the dashboard shows one game at a time (decided 2026-11-05, [doc 13](13_conceptual_model.md)). |
| 7 | Totals, not new reviews | Daily change = difference between two snapshots (`LAG`). Do not assume a total can never go down. |
| 8 | Prices are discounted at the time of the snapshot | Join to `games` and keep both `price_initial` and `price_final` |
| 9 | Repeated rows are the history | Not an error |
| 10 | Loads before 2026-11-02 count English reviews only, later loads count all languages | Add a flag such as `counts_all_languages` in the staging model. Compare with `review_recent` ([doc 11](11_review_recent__dlt_ingestion.md)) only on flagged rows. |

## 9. Known Limits and Open Items

- **History:** at the time of the first load there was one snapshot. Each run adds 81 rows.
- **Totals can change in ways we have not seen:** we do not know if a total can go down between two runs. It needs more than one run.
- **Free Edition:** we do not know why *Knights of Pen and Paper 2: Free Edition* has no reviews.
- **Minimum number of reviews** for comparisons: not needed, decided on 2026-11-05 ([doc 13](13_conceptual_model.md), section 9).
- **Retry code:** done on 2026-10-30. `fetch_app_details` now uses `get_with_retry`, so the retry logic exists once.
- **Reviews are a stand-in:** Steam gives no sales numbers. We can show correlation, not causation.
- **Login:** `DLT_USER` is a `PERSON` user with a password and **no MFA** (checked with `DESC USER` on 2026-10-30), which is why a password-only load worked. Snowflake is phasing out password-only sign-in for `PERSON` users, so the loader now logs in with a key pair (see [doc 09](09_key_pair_login.md)).
- **Undocumented endpoint:** the answer can change without notice.
- **Language break:** the first three loads (2026-10-26, 10-27, 10-30) are English only. The load of 2026-11-02 is the first with all languages. A chart of the all-time total over time would show a jump that is not new reviews. The older rows were left as they are.

## 10. Related Files

| File | Purpose |
|---|---|
| [`src/steam_data_platform/ingestion/steam.py`](../src/steam_data_platform/ingestion/steam.py) | Request helpers, `review_summary` resource, `steam_source` |
| [`src/steam_data_platform/ingestion/pipelines_steam.py`](../src/steam_data_platform/ingestion/pipelines_steam.py) | Builds the pipeline and runs it |
| [`src/steam_data_platform/settings.py`](../src/steam_data_platform/settings.py) | Game list and request pause |
| [`tests/test_steam_dlt.py`](../tests/test_steam_dlt.py) | Tests with fake Steam answers |
| [`notebooks/02_eda_reviews.ipynb`](../notebooks/02_eda_reviews.ipynb) | Validation queries, results and findings |
| [`05_games__dlt_ingestion.md`](05_games__dlt_ingestion.md) | The `games` step |
| [`07_player_counts__dlt_ingestion.md`](07_player_counts__dlt_ingestion.md) | The `player_counts` step |
| [`11_review_recent__dlt_ingestion.md`](11_review_recent__dlt_ingestion.md) | The `review_recent` step (last 30 days) |
| [`12_achievements__dlt_ingestion.md`](12_achievements__dlt_ingestion.md) | The `achievements` step |
| [`08_steam_py_code_guide.md`](08_steam_py_code_guide.md) | A guide to read next to `steam.py` |

## Next Steps

1. ~~Player counts~~ Done, see [07_player_counts__dlt_ingestion.md](07_player_counts__dlt_ingestion.md).
2. ~~Recent reviews and achievements~~ Done on 2026-11-02, see [doc 11](11_review_recent__dlt_ingestion.md) and [doc 12](12_achievements__dlt_ingestion.md).
3. dbt staging for the two new tables, and the language flag in `stg_steam__review_summary`.
4. A scheduled run with a non-interactive Snowflake login.
