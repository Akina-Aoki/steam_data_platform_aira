# 11 Recent Reviews Ingestion with dlt (Steam `GetAppReviews`, last 30 days)

## Overview

Loaded the **positive and negative reviews of the last 30 days** for the same 81 Paradox Interactive games from the public Steam `IUserReviewsService/GetAppReviews` endpoint into Snowflake `STEAM_DB.STEAM_RAW.REVIEW_RECENT`, using Python and dlt.

This is the fourth ingestion step. The all-time totals are in [doc 06](06_reviews__dlt_ingestion.md). This table exists so the dashboard can show who is doing well *right now*, not only over all time. The achievements are in [doc 12](12_achievements__dlt_ingestion.md).

**Branch:** `feat/ingest-recent-reviews-achievements`
**Status:** Built, tested (71 tests) and loaded on 2026-11-02. The pull request was not opened when this doc was written.

```text
Steam GetAppReviews (api.steampowered.com)
        |   2 requests per game: positive (type 1), negative (type 2)
        v
Python (requests) -> dlt resource `review_recent`
        |
        v
STEAM_DB.STEAM_RAW.REVIEW_RECENT   (loaded by DLT_USER, role STEAM_LOADER)
        |
        v
dbt staging (next phase)
```

Steam does not give a count directly. We ask for one review per page and read `total_matching`, the number of reviews that fit the question. We ask it twice per game, once for positive and once for negative reviews.

## 1. Scope and Data Source

| Item | Decision |
|---|---|
| Games | The same 81 apps in [`GAME_APPIDS`](../src/steam_data_platform/settings.py#L6-L16) |
| Endpoint | `https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/` (the same as the review totals) |
| API key | None needed |
| Parameters | One JSON string in `input_json`: `appid`, `num_per_page` 1, `day_range` 30, `languages` `["all"]`, `review_type` 1 or 2 |
| Keep | Only `total_matching` from each answer |
| Code | Constants [L39-L44](../src/steam_data_platform/ingestion/steam.py#L39-L44), [`fetch_recent_review_count`](../src/steam_data_platform/ingestion/steam.py#L188-L220), [`build_review_recent_row`](../src/steam_data_platform/ingestion/steam.py#L326-L339), [`review_recent` resource](../src/steam_data_platform/ingestion/steam.py#L539-L590) |

## 2. What We Verified About the API

Probed on 2026-11-02, one game (Stellaris, `281990`), 2 s apart. The probes were small scripts run in the terminal and are not in Git.

| # | What we tried | What we saw |
|---|---|---|
| 1 | `day_range` 30 with `review_type` as the **word** `positive` or `negative` | All four lines gave the same `total_matching` (297) and `day_range_used` 30. So 30 days is Steam's default, and the word was ignored. |
| 2 | `day_range` 7, 90 and 365 | `total_matching` 58, 664 and 4,695 (30 days: 297). So it follows `day_range`. |
| 3 | The xpaw API reference page for this method | `review_type` is a **number**, `languages` is a **list**, empty means English, `day_range` default 30 (max 365, 0 = no limit). The page says Valve does not document the method. |
| 4 | `languages: ["all"]`, 30 days, then `review_type` 1 and 2 | 558 for all, 363 and 195 for the two types. 363 + 195 = 558. |
| 5 | `languages: ["all"]`, `day_range` 0 | `total_matching` 139,722. The summary totals with all languages are the same number. |
| 6 | `day_range` 0, `review_type` 1 and 2 | 119,757 and 19,965, the same as the all-time positive and negative totals. So **1 is positive and 2 is negative** (checked on Stellaris). |
| 7 | Look at `query_summary` when `review_type` is set | It has no totals. So the numbers must come from `total_matching`. |
| 8 | The resource on 3 apps without Snowflake | Stellaris 364 + 195, Prison Architect 2 (unreleased) 0 + 0, a fake id was skipped with a warning. |

**What probe 5 also showed:** with `languages: ["all"]` the all-time total of Stellaris is 139,722. We had stored 76,854. The old code sent `language` (not `languages`), which Steam ignores, so `review_summary` counted English reviews only. This was fixed on the same day, see [doc 06](06_reviews__dlt_ingestion.md).

**Rate limit:** Steam publishes none for this endpoint. The full run of 486 requests (all five resources, 2 s apart) gave no 429.

## 3. Design Decisions

| Topic | Decision | Why |
|---|---|---|
| Table name | `review_recent` | Short and clear next to `review_summary`. |
| Rows | One per game per run: `steam_appid`, `collected_at`, `day_range`, `recent_positive`, `recent_negative` | Same grain as the other tables. |
| Total | **Not stored** | It is positive + negative. dbt adds it, in one place. |
| Window | 30 days, written to the column `day_range` | The window is explicit in the data. If we add 7 or 90 days later, the rows tell them apart. |
| Languages | All | The all-time totals count all languages now. Both must count the same thing. |
| Requests | 2 per game, with a pause between them | Steam gives one count per filter. |
| Half pairs | The game is **skipped** if either count is not usable | We never store a positive count with a missing negative count. If the first answer is not usable, the second question is not sent. |
| Zero | A real 0 stays 0 | Unreleased games answer 0 and 0. For reviews, "no reviews" and "no data" look the same. dbt uses `coming_soon` from `games`. |
| Write mode | `append` with our own `collected_at` | Every run adds a row per game, so the recent sentiment builds a history. |
| `collected_at` | One time per run | Same as `review_summary`. |
| Filter | We leave `filter` at its default | Steam's default sort is "helpful", and `day_range` works with it (probe 2). |
| Review bombs | Steam says it leaves them out by default. We did not change that. | Not tested. It may make the counts a little lower than the real number of reviews. |
| Pace | One request at a time, 2 s pause | Steam publishes no limit, so we stay slow. |

## 4. Code

```text
src/steam_data_platform/ingestion/steam.py
    fetch_recent_review_count(appid, review_type)   # one question, one whole number or None
    build_review_recent_row(appid, positive, negative, collected_at)
    review_recent(appids)                           # the resource (the loop)
    steam_source(appids)                            # now returns five resources
```

| Piece | What it does | Code |
|---|---|---|
| `fetch_recent_review_count` | One request. Returns `total_matching` as a whole number, or `None` if the answer is not JSON, has the wrong shape, or has no whole number (text and `True` are refused). | [steam.py L188-L220](../src/steam_data_platform/ingestion/steam.py#L188-L220) |
| `build_review_recent_row` | Builds one row with the two counts and `day_range`. | [steam.py L326-L339](../src/steam_data_platform/ingestion/steam.py#L326-L339) |
| `review_recent` resource | Loops over the appids. Per game: positive, pause, negative. Skips the game if either is `None`. Logs progress every 10 games. `append`, `collected_at` typed as a timestamp. | [steam.py L539-L590](../src/steam_data_platform/ingestion/steam.py#L539-L590) |
| `steam_source` | Returns all five resources. | [steam.py L662-L671](../src/steam_data_platform/ingestion/steam.py#L662-L671) |

**Columns in `REVIEW_RECENT`:**

| Column | Type in Snowflake | Meaning |
|---|---|---|
| `steam_appid` | `NUMBER(19,0)` | The game |
| `collected_at` | `TIMESTAMP_LTZ(9)` | When we collected it. One time for the whole run. |
| `day_range` | `NUMBER(19,0)` | The window in days (30) |
| `recent_positive` | `NUMBER(19,0)` | Positive reviews in that window |
| `recent_negative` | `NUMBER(19,0)` | Negative reviews in that window |
| `_dlt_load_id`, `_dlt_id` | `VARCHAR` | Added by dlt. The load id is the same for every row of one run. |

## 5. Error Handling

| Situation | What happens |
|---|---|
| Timeout, 429 or 5xx | Retried up to 3 times with waits of 30 s, then 60 s. |
| Still 429 after all attempts | The whole run stops (`SteamRateLimitError`). |
| Other 4xx | Not retried. Raises an error. The game is counted as *failed* and skipped. |
| Still failing after retries (not 429) | Logged, counted as *failed*, skipped. |
| Either count is not usable | Logged, counted as *skipped*. No row. |
| End of the run | One summary line: fetched, skipped, failed, requested. |

If a run stops with an exception, dlt loads nothing from that run.

## 6. Tests

14 tests were added for this resource (the file then had 71). No network and no Snowflake.

| What is tested | Tests | Code |
|---|---:|---|
| `fetch_recent_review_count`: a good count, **the question that is sent** (30 days, all languages, the review type), zero stays zero, 7 kinds of unusable answers return `None`, not JSON | 11 | [test_steam_dlt.py L424-L490](../tests/test_steam_dlt.py#L424-L490) |
| `build_review_recent_row` | 1 | [test_steam_dlt.py L492-L505](../tests/test_steam_dlt.py#L492-L505) |
| `review_recent` resource: bad games are skipped, a real zero is kept, the second question is not sent when the first fails, repeated 429 stops the run | 2 | [test_steam_dlt.py L507-L554](../tests/test_steam_dlt.py#L507-L554) |

```bash
uv run pytest -q
```

## 7. First Load and Validation

**Result on 2026-11-02:** one full run of all five resources, 486 requests, 13:14 to 13:35 Stockholm time (about 21 minutes), no 429. Load id `1793621677.9089065`. The log line for this resource: `review_recent: 81 fetched, 0 skipped (no usable count), 0 failed, of 81 requested`.

**Checked in Snowflake** (queries and notes in [`notebooks/04_eda_review_recent.ipynb`](../notebooks/04_eda_review_recent.ipynb)):

| Check | Result |
|---|---|
| Rows | 81 rows, 81 games, one `collected_at`, `day_range` 30 everywhere |
| Duplicates | None |
| Column types | As in section 4 |
| Games with no recent reviews | 5: the 4 unreleased games and *Knights of Pen and Paper 2: Free Edition*. All five also have 0 reviews of all time. |
| Volume | 5 games with 0 recent reviews, 36 with 1 to 9, 29 with 10 to 99, and only 11 with 100 or more |
| Recent never above all-time | No game has more recent than all-time reviews |
| Biggest drops (100+ recent reviews) | Europa Universalis IV from 86.5 % to 33.8 % positive, Prison Architect from 89.0 % to 38.0 %. Six of the 11 games are more than 10 points below their all-time percent. We do not know why. |
| Language break | The sum of `total_reviews` over the 81 games was about 674,000 in the three English-only loads and 1,269,461 in this load. Stellaris went from 76,828 to 139,723. |

## 8. Findings for dbt Staging

These are proposals. The full list is in section 10 of the notebook.

| # | Finding | Proposal |
|---:|---|---|
| 1 | One row per game per load | `unique` on (`steam_appid`, `load_id`), `not_null`, a relationship test to `games`. Include `day_range` if we add other windows. |
| 2 | Total and percent are not stored | Add `recent_total`, `has_recent_reviews` and `pct_positive_recent` (NULL when the total is 0) |
| 3 | 0 is a real number | Never turn a NULL percent into 0. Use `coming_soon` for "unreleased". |
| 4 | Small numbers are noise | Show the number of recent reviews next to the recent percent. No minimum is needed because the dashboard shows one game at a time (decided 2026-11-05, [doc 13](13_conceptual_model.md)). |
| 5 | The 30 days overlap between runs | Never add the counts over days. Use the latest row for "now". |
| 6 | `review_summary` is English only before 2026-11-02 | A flag such as `counts_all_languages` in `stg_steam__review_summary`. Compare with `review_recent` only on flagged rows. |
| 7 | Recent can never be more than all-time | A `warn` test in the intermediate layer |

## 9. Known Limits and Open Items

- **One snapshot:** no trend yet. Each run adds 81 rows.
- **Rolling window:** two runs on consecutive days share 29 of 30 days.
- **Small games are noise:** no minimum is needed, the count is shown next to the percent (decided 2026-11-05, [doc 13](13_conceptual_model.md)).
- **Review-bomb filter:** Steam says it is on by default. We did not test how much it changes the counts.
- **The count moves a little between requests:** Stellaris gave 558 and 559 within hours. We do not know why.
- **Why Europa Universalis IV and Prison Architect dropped:** unknown. News or patch dates could help later.
- **Undocumented endpoint:** Valve does not document it, and the answer can change without notice.
- **Positive/negative numbers:** checked on one game (Stellaris) for all time, not on every game.

## 10. Related Files

| File | Purpose |
|---|---|
| [`src/steam_data_platform/ingestion/steam.py`](../src/steam_data_platform/ingestion/steam.py) | Request helpers, the `review_recent` resource, `steam_source` |
| [`tests/test_steam_dlt.py`](../tests/test_steam_dlt.py) | Tests with fake Steam answers |
| [`notebooks/04_eda_review_recent.ipynb`](../notebooks/04_eda_review_recent.ipynb) | Validation queries, results and findings |
| [`06_reviews__dlt_ingestion.md`](06_reviews__dlt_ingestion.md) | The all-time totals and the language fix |
| [`12_achievements__dlt_ingestion.md`](12_achievements__dlt_ingestion.md) | The `achievements` step |
| [`08_steam_py_code_guide.md`](08_steam_py_code_guide.md) | A guide to read next to `steam.py` |

## Next Steps

1. dbt staging for `review_recent` and `achievements` (and the language flag in `stg_steam__review_summary`).
2. More runs, so the recent reviews show a trend.
3. A scheduled run with a non-interactive Snowflake login.
