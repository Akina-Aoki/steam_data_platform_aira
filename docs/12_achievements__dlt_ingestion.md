# 12 Achievements Ingestion with dlt (Steam `GetGlobalAchievementPercentagesForApp`)

## Overview

Loaded the **achievement percentages** (the share of players who unlocked each achievement) for the same 81 Paradox Interactive games from the public Steam `ISteamUserStats/GetGlobalAchievementPercentagesForApp` endpoint into Snowflake `STEAM_DB.STEAM_RAW.ACHIEVEMENTS`, using Python and dlt.

This is the fifth ingestion step. It gives a rough idea of how far players get in a game. The recent reviews are in [doc 11](11_review_recent__dlt_ingestion.md).

**Branch:** `feat/ingest-recent-reviews-achievements`
**Status:** Built, tested (71 tests) and loaded on 2026-11-02. The pull request was not opened when this doc was written.

```text
Steam GetGlobalAchievementPercentagesForApp (api.steampowered.com)
        |   1 request per game, many achievements back
        v
Python (requests) -> dlt resource `achievements`
        |
        v
STEAM_DB.STEAM_RAW.ACHIEVEMENTS   (loaded by DLT_USER, role STEAM_LOADER)
        |
        v
dbt staging (next phase)
```

## 1. Scope and Data Source

| Item | Decision |
|---|---|
| Games | The same 81 apps in [`GAME_APPIDS`](../src/steam_data_platform/settings.py#L6-L16) |
| Endpoint | `https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/` |
| API key | None needed |
| Parameter | `gameid=<one id>` |
| Keep | The list `achievementpercentages` -> `achievements`. Each item has a `name` and a `percent`. |
| Code | [`ACHIEVEMENTS_URL`](../src/steam_data_platform/ingestion/steam.py#L38), [`fetch_achievements`](../src/steam_data_platform/ingestion/steam.py#L223-L254), [`build_achievement_rows`](../src/steam_data_platform/ingestion/steam.py#L342-L364), [`achievements` resource](../src/steam_data_platform/ingestion/steam.py#L593-L659) |

## 2. What We Verified About the API

Probed on 2026-11-02 with 3 requests, 2 s apart.

| Case | HTTP status | Body |
|---|---:|---|
| Stellaris (normal game) | 200 | 219 achievements. Each has a `name` (a code like `achievement_economy_1`) and a `percent` as **text** (`"40.9"`). |
| Prison Architect 2 (unreleased) | **403** | `{}` |
| Fake appid `99999999` | **403** | `{}` |

**Findings:**

- **The percent is text,** not a number. We keep it as text. dbt turns it into a number.
- **The name is a code,** not a readable title. Readable titles would need `GetSchemaForGame`, which needs a Steam key. We do not use a key.
- **Unreleased games and wrong ids give the same answer:** HTTP 403 with an empty `{}`. Our retry helper treats every 4xx as our own mistake, so this needed a special rule (section 3).
- **Steam sends the achievements already sorted** from the most to the least unlocked (seen on Stellaris).
- **Steam has a typo in one name:** `achieviement_conquer_homeworld` (Stellaris).
- **Not seen yet:** what a released game *without* achievements sends. The log cannot tell a 403 from an empty list, and the result is the same (no rows).
- **Rate limit:** Steam publishes none for this endpoint. The full run of 486 requests (all five resources, 2 s apart) gave no 429.

## 3. Design Decisions

| Topic | Decision | Why |
|---|---|---|
| Table name | `achievements` | |
| Rows | One per game and achievement per run: `steam_appid`, `collected_at`, `achievement_name`, `percent` | |
| Percent | Kept as **text**, with the column type set to `text` | Steam sends text. A number that shows up one day would otherwise split the column in two. dbt casts it. |
| Names | Kept as Steam sends them | The raw layer is a faithful copy. |
| No data | **No rows** (not a row with 0 %) | An unreleased game or a game without achievements has nothing to list. 0 % would claim that nobody unlocks anything. |
| 403 rule | A 403 with an empty `{}` means "no data". Any other 403 raises an error. | The empty body is how Steam says "no data". A 403 with something else (or not JSON) may be a real block, which must never look like "no data". |
| Bad entries | An entry without a name or a percent is left out, and the log says how many | One bad entry must not lose the game. |
| Write mode | `append` with our own `collected_at` | Same as the other tables. `replace` was rejected: if a run stopped halfway on a 429, it would wipe the games that were not reached. About 4,000 rows per run is small for Snowflake. |
| Repeated rows | Accepted | Percentages move slowly, so most rows repeat. dbt uses the latest load for "now". |
| `collected_at` | One time per run | Same as `review_summary`. |
| Pace | One request at a time, 2 s pause | Steam publishes no limit, so we stay slow. |

## 4. Code

```text
src/steam_data_platform/ingestion/steam.py
    fetch_achievements(appid)                         # list, [] for no data, or None
    build_achievement_rows(appid, items, collected_at) # a list of rows
    achievements(appids)                              # the resource (the loop)
    steam_source(appids)                              # now returns five resources
```

| Piece | What it does | Code |
|---|---|---|
| `fetch_achievements` | One request with `accept_statuses=(403,)`. A 403 with `{}` returns `[]`. Another 403 raises an error. A 200 returns the list, or `None` if the shape is wrong. | [steam.py L223-L254](../src/steam_data_platform/ingestion/steam.py#L223-L254) |
| `build_achievement_rows` | One row per achievement. Leaves out entries without a name or a percent. Turns the percent into text. | [steam.py L342-L364](../src/steam_data_platform/ingestion/steam.py#L342-L364) |
| `achievements` resource | Loops over the appids, logs progress every 10 games, `yield from` the rows of each game. A game with no rows is counted as *without data*. `append`, with `collected_at` as a timestamp and `percent` as text. | [steam.py L593-L659](../src/steam_data_platform/ingestion/steam.py#L593-L659) |
| `steam_source` | Returns all five resources. | [steam.py L662-L671](../src/steam_data_platform/ingestion/steam.py#L662-L671) |

**Columns in `ACHIEVEMENTS`:**

| Column | Type in Snowflake | Meaning |
|---|---|---|
| `steam_appid` | `NUMBER(19,0)` | The game |
| `collected_at` | `TIMESTAMP_LTZ(9)` | When we collected it. One time for the whole run. |
| `achievement_name` | `VARCHAR` | Steam's code for the achievement |
| `percent` | `VARCHAR` | Share of players who unlocked it, as text (for example `40.9`) |
| `_dlt_load_id`, `_dlt_id` | `VARCHAR` | Added by dlt. The load id is the same for every row of one run. |

## 5. Error Handling

| Situation | What happens |
|---|---|
| HTTP 403 with an empty `{}` | A normal "no data" answer. No rows for this game. Counted as *without data*. |
| HTTP 403 with anything else, or not JSON | Raises an error. The game is counted as *failed* and skipped. |
| Timeout, 429 or 5xx | Retried up to 3 times with waits of 30 s, then 60 s. |
| Still 429 after all attempts | The whole run stops (`SteamRateLimitError`). |
| Answer not usable (not JSON, wrong shape) | Logged, counted as *skipped*. |
| End of the run | One summary line: games with rows (and the number of rows), without data, skipped, failed, requested. |

If a run stops with an exception, dlt loads nothing from that run.

## 6. Tests

16 tests were added for this resource, and one for `steam_source`. No network and no Snowflake.

| What is tested | Tests | Code |
|---|---:|---|
| `fetch_achievements`: a good list, **403 with `{}` is no data and not retried**, **another 403 raises**, 6 kinds of unusable answers return `None`, not JSON | 11 | [test_steam_dlt.py L556-L614](../tests/test_steam_dlt.py#L556-L614) |
| `build_achievement_rows`: the percent stays text, a number becomes text, bad entries are left out | 3 | [test_steam_dlt.py L616-L652](../tests/test_steam_dlt.py#L616-L652) |
| `achievements` resource: rows for a good game, no rows for "no data", bad games are skipped, repeated 429 stops the run | 2 | [test_steam_dlt.py L654-L691](../tests/test_steam_dlt.py#L654-L691) |
| `steam_source` has the five resources | 1 | [test_steam_dlt.py L693-L705](../tests/test_steam_dlt.py#L693-L705) |

```bash
uv run pytest -q
```

## 7. First Load and Validation

**Result on 2026-11-02:** one full run of all five resources, 486 requests, 13:14 to 13:35 Stockholm time, no 429. Load id `1793621677.9089065`. The log line for this resource: `achievements: 49 games with rows (3966 rows), 32 without data, 0 skipped, 0 failed, of 81 requested`.

**Checked in Snowflake** (queries and notes in [`notebooks/05_eda_achievements.ipynb`](../notebooks/05_eda_achievements.ipynb)):

| Check | Result |
|---|---|
| Rows | 3,966 rows from 49 games, one `collected_at` |
| Duplicates | None for (game, achievement, load) |
| Names | Only 3,925 different names, so 41 names are used by more than one game (each by exactly 2). The name alone is not a key. |
| Column types | `percent` is `VARCHAR`, as intended |
| Percent | All 3,966 values can be read as numbers (`try_to_double`), from 0.0 to 100.0 |
| Games without rows | 32: the 4 unreleased games and 28 released games that came out between 2008 and 2013 |
| Cross-check with the store category `Steam Achievements` | 74 of 81 games agree (30 without rows and without the category, 44 with both). 7 do not. The 2 with the category but no rows are *Afterworld* and *Prison Architect 2*, both unreleased, so no data was lost. The 5 with rows but no category are released: *A Game of Dwarves*, *Crusader Kings II*, *FOUNDRY*, *Star Trek: Infinite* and *Sword of the Stars II: Enhanced Edition*. We do not know why the category is missing for them. |
| Most achievements | Europa Universalis IV 373, Hearts of Iron IV 293, Stellaris 219, Crusader Kings III 198, Crusader Kings II 161 |
| Fewest | NECROPOLIS: BRUTAL EDITION 13, Sword of the Stars II 14, Prison Architect 18 |
| Hardest on average | Imperator: Rome 1.7 %, Hearts of Iron IV 1.9 %, Crusader Kings II 2.5 % |

## 8. Findings for dbt Staging

These are proposals. The full list is in section 10 of the notebook.

| # | Finding | Proposal |
|---:|---|---|
| 1 | One row per game, achievement and load. Names repeat between games. | `unique` on (`steam_appid`, `achievement_name`, `load_id`), `not_null`, a relationship test to `games` |
| 2 | The percent is text | Add `percent_unlocked` with `try_to_double`, keep the text. Tests: `not_null` and `accepted_range` 0 to 100. |
| 3 | No rows means no data | Never fill with 0 %. In intermediate, left join from `games` and add `has_achievements`. Make the flag from our own rows, not from the store category (it is missing for 5 games that have rows). |
| 4 | Names are codes, and Steam has a typo in one | Keep the real name. Make a display name only in the marts and check it by eye. |
| 5 | Repeated runs give mostly the same rows | Use the latest load per game and achievement for "now" |
| 6 | The number of achievements ranges from 13 to 373 | One row per game in the marts: count, average, median, easiest, hardest. Do not rank by one number. |

## 9. Known Limits and Open Items

- **The store category is not a perfect check:** 5 released games have achievement rows but no `Steam Achievements` category. We do not know why. The 2 games with the category but no rows are unreleased.
- **403 or an empty list:** the log does not say which one the 32 games got. The result is the same.
- **What the percent is measured against** (all owners or all players): unknown.
- **DLC achievements:** we do not know if they are in the lists.
- **One snapshot:** no change over time yet. Percentages move slowly.
- **Readable titles:** need a Steam key, which we do not use.
- **Undocumented endpoint:** the xpaw reference lists the request, not the answer. The answer can change without notice.

## 10. Related Files

| File | Purpose |
|---|---|
| [`src/steam_data_platform/ingestion/steam.py`](../src/steam_data_platform/ingestion/steam.py) | Request helpers, the `achievements` resource, `steam_source` |
| [`tests/test_steam_dlt.py`](../tests/test_steam_dlt.py) | Tests with fake Steam answers |
| [`notebooks/05_eda_achievements.ipynb`](../notebooks/05_eda_achievements.ipynb) | Validation queries, results and findings |
| [`11_review_recent__dlt_ingestion.md`](11_review_recent__dlt_ingestion.md) | The `review_recent` step |
| [`08_steam_py_code_guide.md`](08_steam_py_code_guide.md) | A guide to read next to `steam.py` |

## Next Steps

1. dbt staging for `review_recent` and `achievements`.
2. More runs, to see if the percentages change.
3. A scheduled run with a non-interactive Snowflake login.
