# dbt Intermediate Layer: Steam Data Platform

## Overview

The intermediate layer joins and shapes the five staging views. It holds one prep model and the star schema: two dimensions (`dim_date`, `dim_game`) and three facts (`fact_game_store`, `fact_game_reviews`, `fact_game_players`). All of it is built as **views** in `STEAM_DB.INTERMEDIATE` ([doc 13](13_conceptual_model.md), section 9).

**Branch:** `feat/dbt-intermediate`
**Status:** All six models are built and tested (2026-11-06). Whole-project `dbt build`: `PASS=74 WARN=0 ERROR=0` (I saw the last line only). Not committed yet. The two marts come next, on their own branch.

`Steam Data → dlt → STEAM_RAW → dbt Staging → dbt Intermediate → dbt Marts → Streamlit`

The design decisions (grain, star schema, columns) are in [doc 13](13_conceptual_model.md). This document records what was built and what was found.

There is no reference model to copy for this layer. The Flight-punctuality repo has no middle layer, and the lecture repo puts its dimensions and facts in a `warehouse` schema. The layer follows doc 13.

**What changed on 2026-11-06:** the first plan had one fact table, `fact_game_snapshot`, built from a four-way join model, `int_steam__game_run`. After a tip from my teacher the fact was split into three, one for each kind of measurement, and `dim_game` was cut from 18 to 10 columns. `int_steam__game_run` was never built. Section 7 has the reasons.

## 1. Models

| # | Model | One row is | Reads | Status |
|---|---|---|---|---|
| 1 | `int_steam__games_latest` | one game | `stg_steam__games` | Built and tested |
| 2 | `dim_date` | one Stockholm day that has a run | `stg_steam__games` | Built and tested |
| 3 | `dim_game` | one game | `int_steam__games_latest` | Built and tested (10 columns) |
| 4 | `fact_game_store` | one game in one run | `stg_steam__games` | Built and tested |
| 5 | `fact_game_players` | one game in one run | `stg_steam__player_counts` | Built and tested |
| 6 | `fact_game_reviews` | one game in one run | `stg_steam__review_summary`, `stg_steam__review_recent` | Built and tested |

There is also one singular test, `assert_81_games_per_run` (section 6).

Descriptions and tests are in [`_int_steam__models.yml`](../dbt_project/models/intermediate/_int_steam__models.yml). The logical model is in [`logical_model.dbml`](../dbt_project/models/intermediate/logical_model.dbml) and the picture in `assets/logical_model_1.png`.

## 2. `int_steam__games_latest`

File: [`int_steam__games_latest.sql`](../dbt_project/models/intermediate/int_steam__games_latest.sql)

It keeps the newest row of each game from `stg_steam__games`. It is the base of `dim_game`.

| Step | What it does |
|---|---|
| `row_number() over (partition by steam_appid order by collected_at_utc desc, load_id desc)` | Numbers each game's rows, newest first. `load_id` only breaks a tie. |
| `where row_num = 1` | Keeps the newest row. The helper column is then removed with `exclude`. |

All columns of `stg_steam__games` stay unchanged. Unreleased games are kept (`coming_soon` tells them apart).

**Limit:** if a game is missing from the newest run (for example one request failed), its "latest" row comes from an older run. That is fine for a description (`dim_game`). It is why the facts have one row per game per run.

### Tests

| Model | Tests |
|---|---|
| `int_steam__games_latest` | `steam_appid`: `unique` (one row per game) and `not_null` |

### Validation

| Check | Result |
|---|---|
| `dbt build --select int_steam__games_latest` | `Found 6 models, 39 data tests`. 1 view and 2 tests: `PASS=3 WARN=0 ERROR=0` |
| Read-only query in Snowsight on `STEAM_DB.INTERMEDIATE.INT_STEAM__GAMES_LATEST` | 81 rows, 81 games, 1 run used, oldest and newest row both 2026-11-06 |
| Read-only query on `STEAM_DB.STAGING.STG_STEAM__GAMES`, grouped by `collected_date` (CSV export, 2026-11-06) | 8 days: 10-23, 10-26, 10-27, 10-30, 11-02, 11-03, 11-05, 11-06. Each day has 81 rows and 81 games, so 648 rows in all. The model keeps 81 of them. |

`oldest_row` in the first query is the oldest of the *kept* rows, so it is 2026-11-06. The October rows are still in staging and raw. The model only chooses from them.

`STEAM_TRANSFORMER` can create views in `INTERMEDIATE`. No grant was changed.

The first build failed with a typo (the first CTE was named `game`, but a later step read `from games`). Snowflake then looked for a table `INTERMEDIATE.GAMES`, and the error looked like a rights problem, but it was not one. The second build passed.

## 3. `dim_date`

File: [`dim_date.sql`](../dbt_project/models/intermediate/dim_date.sql)

One row per Stockholm day that has a run. The days come from `select distinct collected_date` on `stg_steam__games`. The three facts point to it with `snapshot_date`.

| Column | How |
|---|---|
| `date_day` | The run day (`collected_date`, a Stockholm day) |
| `year`, `month`, `month_name` | `year()`, `month()`, `to_char(date_day, 'MMMM')` |
| `week_of_year` | `weekiso()` |
| `day_of_week` | `dayofweekiso()`: 1 = Monday, 7 = Sunday. No Snowflake setting changes it. |
| `is_weekend` | `day_of_week >= 6` |

### Tests

| Model | Tests |
|---|---|
| `dim_date` | `date_day`: `unique` and `not_null` |

### Validation

| Check | Result |
|---|---|
| `dbt build --select dim_date` | `Found 7 models, 41 data tests`. 1 view and 2 tests: `PASS=3 WARN=0 ERROR=0` |
| Read-only query on `STEAM_DB.INTERMEDIATE.DIM_DATE` (CSV export, 2026-11-06) | 8 rows, one for each run day from 2026-10-23 to 2026-11-06. Weekdays and ISO weeks checked by hand against a calendar: for example 2026-10-23 is a Friday (5, week 43), 2026-11-02 a Monday (1, week 45). All run days are weekdays, so `is_weekend` is FALSE everywhere. |

**Limit:** `dim_date` is built from the days of `stg_steam__games` only. A fact row whose day is not in `games` would fail the `relationships` test. All three facts passed it on 2026-11-06.

## 4. `dim_game`

File: [`dim_game.sql`](../dbt_project/models/intermediate/dim_game.sql)

One row per game, with the things that rarely change. It reads `int_steam__games_latest` (the newest row of each game). **10 columns**, cut from 18 on 2026-11-06.

| Group | Columns |
|---|---|
| Identity | `steam_appid`, `name` |
| Release | `release_date`, `release_year` |
| Store info | `metacritic_score`, `website`, `short_description` |
| Lists | `developers`, `genres` (stay lists) |
| Readable text | `genres_text` |

Worked out here: `release_year = year(release_date)` (NULL for unreleased games) and `genres_text = nullif(array_to_string(genres::array, ', '), '')`.

**Dropped on 2026-11-06:**

| Column | Why |
|---|---|
| `type`, `release_date_text`, `required_age` | No business area in doc 13 asks a question that needs them |
| `platform_windows`, `platform_mac`, `platform_linux` | Same |
| `publishers`, `categories` | Same |

The price and status columns (`price_initial`, `price_final`, `is_free`, `coming_soon`) are not in `dim_game`. `fact_game_store` owns them. `recommendations_total` and `discount_percent` are not stored anywhere in the star. The mart works the discount out from the two prices.

`metacritic_score`, `short_description`, `website` and `developers` were kept on purpose, although no business area asks for them yet. Adding or removing a column later is one line in `dim_game.sql`.

### Findings

| Finding | Evidence |
|---|---|
| Six candidate columns do not change between runs | Read-only query on `STG_STEAM__GAMES` (screenshot of the result, 2026-11-06): 0 of 81 games changed `name`, `release_date_text`, `required_age`, `metacritic_score`, `website` or `genres` over the 8 runs. This is only about two weeks of history. |
| Genre items are plain text | `genres` looks like `["Indie", "Simulation", "Strategy"]` and `typeof(genres[0])` is `VARCHAR` (3 rows seen) |
| 45 of 81 games have a Metacritic score | Scores run from 45 to 91. The other 36 are NULL. |

### Tests

| Model | Tests |
|---|---|
| `dim_game` | `steam_appid`: `unique` and `not_null`. `release_year`, `metacritic_score` and `genres_text` have a description only. |

### Validation

| Check | Result |
|---|---|
| `dbt build --select dim_game` (after the cut to 10 columns, two builds on 2026-11-06) | `PASS=3 WARN=0 ERROR=0`. The first build still had `categories` in it. I found this by reading the file back, the build could not catch it, and the second build passed. |
| Counts on `STEAM_DB.INTERMEDIATE.DIM_GAME` (screenshot, 2026-11-06, **before** the cut to 10 columns) | 81 rows, 81 games, 77 with `release_year`, 81 with `genres_text`, 45 with `metacritic_score`. I did not see a new count query after the cut. The row count cannot change, because the `FROM` is the same, and `unique` and `not_null` on `steam_appid` passed again. |
| First 8 rows by release year (before the cut) | The 4 games without a year have "To be announced" or "Coming soon" as text (Afterworld, Guardians of the Wild Sky, LEGO Skylines, Prison Architect 2). The next four are the oldest games and their years match the text (2008 and 2009). `genres_text` reads like `Simulation, Strategy`. |

## 5. The three facts

All three facts have the same grain, **one game in one run**, and the same keys: `steam_appid`, `load_id` and `snapshot_date`. `steam_appid` + `load_id` is unique in each. `snapshot_date` is the Stockholm day of the row and points to `dim_date.date_day`. Each fact connects straight to `dim_game` and `dim_date`.

- A fact has rows only for runs where its source has data. There are no rows padded with NULL for runs before a table existed.
- The facts store counts, not percentages. Percentages and "change since the previous run" are worked out in the marts.
- Each fact reads its staging model directly. Only `fact_game_reviews` has a join.
- A missing price is NULL, never 0. A missing player count is NULL, never 0.

### 5.1 `fact_game_store`

File: [`fact_game_store.sql`](../dbt_project/models/intermediate/fact_game_store.sql). Reads `stg_steam__games`, all rows.

| Group | Columns |
|---|---|
| Keys | `steam_appid`, `load_id`, `snapshot_date` (from `collected_date`) |
| Time | `collected_at_utc` |
| Price | `price_currency`, `price_initial`, `price_final` |
| Status | `is_free`, `coming_soon` |

`discount_percent` is not stored. The mart works it out from the two prices. `is_free` is kept because a free game has no price (NULL), so it is the only way to tell a free game from a missing price. Doc 05 says a free game arrives with `is_free: true` and no price, and a read-only query on `FACT_GAME_STORE` on 2026-11-06 confirmed it (screenshot, section 5, validation). **Two** games are free, *Crusader Kings II* and *Knights of Pen and Paper 2: Free Edition*, and both have a NULL price in all 8 runs. Two other released games, *Majesty 2 Collection* (`73020`) and *Galaxy of Pen & Paper +1* (`349790`), also have a NULL price but `is_free` is false. So `is_free` is the only column that tells the four apart. Earlier notes said only one game was free. That was wrong.

### 5.2 `fact_game_players`

File: [`fact_game_players.sql`](../dbt_project/models/intermediate/fact_game_players.sql). Reads `stg_steam__player_counts`.

| Group | Columns |
|---|---|
| Keys | `steam_appid`, `load_id`, `snapshot_date` |
| Time | `collected_at_utc`, `collected_hour_local` |
| Players | `player_count`, `has_player_data` |

Each player count has its own time, because a run takes about 10 minutes. The Stockholm hour stays next to the count, because the count depends on the hour of the day. `player_count` NULL means no data, 0 is a real zero.

### 5.3 `fact_game_reviews`

File: [`fact_game_reviews.sql`](../dbt_project/models/intermediate/fact_game_reviews.sql). Reads `stg_steam__review_summary` and left-joins `stg_steam__review_recent` on `steam_appid` + `load_id`.

| Group | Columns |
|---|---|
| Keys | `steam_appid`, `load_id`, `snapshot_date` |
| Time | `collected_at_utc` (of the `review_summary` row) |
| All time | `total_positive`, `total_negative`, `counts_all_languages` |
| Last 30 days | `recent_positive`, `recent_negative` |

The total is positive + negative, so it is not stored. `counts_all_languages` is `false` before 2026-11-02 (English only), so use it in every trend and every change calculation. The last-30-days columns are NULL for the runs before 2026-11-02, when `review_recent` did not exist. A real 0 stays 0.

**Why the left join is safe** (read-only query on the two staging views, CSV export, 2026-11-06):

| Finding | Evidence |
|---|---|
| `review_summary` has 7 runs | 2026-10-26, 10-27, 10-30, 11-02, 11-03, 11-05, 11-06. 81 rows in each. |
| `review_recent` has 4 runs | 2026-11-02, 11-03, 11-05, 11-06. 81 rows in each. |
| Every `review_recent` run also has a `review_summary` run with the same `load_id` | No run has recent rows without summary rows. A left join from `review_summary` loses nothing. |
| No run crosses midnight | First day and last day are the same in every run, for both tables. |

Doc 13 said 5 and 2 runs. That came from the 2026-11-05 query and is now out of date. I changed it.

### Tests

| Model | Tests |
|---|---|
| `fact_game_store` | Table: `dbt_utils.unique_combination_of_columns` on (`steam_appid`, `load_id`). `steam_appid`: `not_null` and `relationships` to `dim_game`. `load_id`: `not_null`. `snapshot_date`: `not_null` and `relationships` to `dim_date.date_day`. **6 tests.** |
| `fact_game_players` | The same 6 tests. **6 tests.** |
| `fact_game_reviews` | The same 6 tests, plus the `warn` test in section 6 (recent never above all-time). **7 tests.** |

The `relationships` test on `snapshot_date` also catches a run that crossed midnight, because each fact takes its own date.

### Validation

The build rows are from the `dbt build` output pasted on 2026-11-06 (the line `Found ...` and the result line). The last row is from a screenshot of a Snowsight result.

| Check | Result |
|---|---|
| `dbt build --select fact_game_store` | `Found 9 models, 49 data tests`. 1 view and 6 tests: `PASS=7 WARN=0 ERROR=0` |
| `dbt build --select fact_game_players` | `Found 10 models, 55 data tests`. 1 view and 6 tests: `PASS=7 WARN=0 ERROR=0` |
| `dbt build --select fact_game_reviews` | `Found 11 models, 62 data tests`. 1 view and 7 tests: `PASS=8 WARN=0 ERROR=0` |
| `dbt test --select assert_81_games_per_run` | `Found 11 models, 63 data tests`. `PASS=1 WARN=0 ERROR=0` |
| `dbt build` (whole project) | `PASS=74 WARN=0 ERROR=0`. I saw the last line only, not the `Found` line. 74 is 11 models and 63 tests, which matches my count. |
| Row counts of the three facts, read-only query on `STEAM_DB.INTERMEDIATE` (screenshot, 2026-11-06) | `FACT_GAME_STORE` 648 rows, 8 runs, 2026-10-23 to 2026-11-06. `FACT_GAME_REVIEWS` 567 rows, 7 runs, 2026-10-26 to 2026-11-06. `FACT_GAME_PLAYERS` 486 rows, 6 runs, 2026-10-27 to 2026-11-06. Each is runs × 81, which matches the completeness test. My earlier prediction for the first two was right. For the players I had said 4 runs (doc 13, from the 2026-11-05 query), which was out of date: there are 6. |
| Games with `is_free` true or with no price, read-only query on `FACT_GAME_STORE` joined to `DIM_GAME` (screenshot, 2026-11-06) | 4 games, each in all 8 runs, with `price_initial` and `price_final` NULL and `coming_soon` false: *Crusader Kings II* (`203770`) and *Knights of Pen and Paper 2: Free Edition* (`794820`) with `is_free` true, and *Majesty 2 Collection* (`73020`) and *Galaxy of Pen & Paper +1* (`349790`) with `is_free` false. I had predicted one free game, and that was wrong. Both prices are NULL together in every case. |
| `FACT_GAME_REVIEWS` per day: games, games with recent data, games with `counts_all_languages` true (screenshot, 2026-11-06) | 7 days, 81 games each. 2026-10-26, 10-27 and 10-30: 0 with recent data, 0 with the flag. 2026-11-02, 11-03, 11-05 and 11-06: 81 with recent data, 81 with the flag. Both change on 2026-11-02, as predicted. |
| `FACT_GAME_PLAYERS` per day: games, rows with a count, rows with `has_player_data`, real zeros, first and last hour (screenshot, 2026-11-06) | 6 days (2026-10-27, 10-30, 11-02, 11-03, 11-05, 11-06), 81 games each. 77 rows with a count and 77 with `has_player_data` on every day, so 4 games have no data in every run (probably the 4 unreleased games, not checked). 9 to 15 real zeros per day, kept as 0. Run hours: 10, 15, 13, 14, 15, and 9 to 10 on 2026-11-06, so the hour of a count matters. |

Checked so far: the row counts, the free and no-price games, the recent and language columns of the reviews fact, and the player counts per day. I did not look at single games or at the `dim_game` counts after the cut to 10 columns (section 9).

## 6. Extra checks

| Check | Where | Severity | Result |
|---|---|---|---|
| **Recent never above all-time:** `recent_positive + recent_negative <= total_positive + total_negative` | `data_tests` of `fact_game_reviews` (`dbt_utils.expression_is_true`) | `warn` | Passed. It only looks at rows with recent data and `counts_all_languages` true, because before 2026-11-02 the all-time total counted English reviews only and could be smaller than the recent one. |
| **Completeness:** every run has exactly 81 rows in each of the three facts | [`dbt_project/tests/assert_81_games_per_run.sql`](../dbt_project/tests/assert_81_games_per_run.sql) (a singular test: it returns the runs that do not have 81, no rows means it passes) | `warn` | Passed. The 81 is written into the test. If a game is added to `GAME_APPIDS`, change it. |

Before the split both checks were planned for `int_steam__game_run`, because they needed a join. With three facts the first check sits in one fact and the second counts rows, so neither needs a join.

## 7. Decisions

| Decision | Reason |
|---|---|
| Newest row per game uses `row_number()` in a CTE, not `qualify` | A CTE reads more easily for a beginner |
| `load_id` is the tie-break after `collected_at_utc` | Two rows with the same time still give exactly one winner |
| Unreleased games are kept | `coming_soon` tells them apart. Zero reviews or `result = 42` never mean "unreleased". |
| `dim_date` holds only days that have a run, no `date_spine` | No start date or end date to keep up. The list stops growing when ingestion stops. A fact row always finds its day, so the `relationships` test cannot fail on a date. The first plan used `dbt_utils.date_spine` (suggested in the handoff, not copied from a reference repo). It needs an end date and builds empty days that nothing uses. |
| `day_of_week` and `week_of_year` use the ISO rules | They do not depend on a Snowflake setting |
| A missing `metacritic_score` stays NULL in `dim_game` | A number column cannot hold text, and NULL means "no data", never 0. The words "no Metacritic data available" are a display choice for the mart or Streamlit. |
| `genres_text` gives NULL for an empty list | `nullif(..., '')`, so "no genres" is not an empty text |
| **Three facts instead of one** (2026-11-06) | A tip from my teacher. The four sources have different histories (8, 7, 4 and 6 runs) and different times of collection, so one fact would pad the early runs with NULL and mix four sources. Each kind of measurement gets its own fact: store, reviews, players. All three have the same grain and connect straight to both dimensions. The star stays strict, and the three stars share their dimensions (a fact constellation). |
| `int_steam__game_run` is dropped | It was a four-way join that only fed the single fact. With three facts each one reads its staging model directly, and only `fact_game_reviews` has a join. |
| The joins move to the marts | `mart_game_detail` starts from `fact_game_store` and left-joins the other two facts on `steam_appid` + `load_id`. The three facts have the same grain, so the join gives one row for one row, and the `unique` tests guard it. |
| `dim_game` has 10 columns | Only columns that a business area in doc 13 can use. `metacritic_score`, `short_description`, `website` and `developers` were kept on purpose. |
| `fact_game_store` keeps `is_free` and drops `discount_percent` | The discount can be worked out from the two prices. `is_free` cannot be worked out from anything else, and without it a free game looks like a missing price. |
| `snapshot_date` comes from each fact's own staging model | Simplest, and each fact needs no join to `games`. The `relationships` test to `dim_date` would catch a run that crosses midnight. |

**Limit of `dim_date`:** days without a run have no row. This is fine because the dashboard shows markers per run, not a line over gaps ([doc 13](13_conceptual_model.md), section 8). If empty days are needed later, switch to `date_spine`. No column changes.

## 8. How to Run

From the `dbt_project/` folder, with the virtual environment active:

```bash
set -a; source ../.env; set +a
dbt build
```

To build only the intermediate layer:

```bash
dbt build --select int_steam__games_latest dim_date dim_game fact_game_store fact_game_reviews fact_game_players
```

The singular test `assert_81_games_per_run` runs with a full `dbt build`. It has to be selected by name to run alone: `dbt test --select assert_81_games_per_run`.

## 9. Not done yet

| Item | Status |
|---|---|
| Commit and pull request for the intermediate layer | Not done. The changes are not committed. |
| Marts `mart_game_detail` and `mart_genre_comparison` | Next, on their own branch (`feat/dbt-marts`). They read the three facts and `dim_game`. |
| Look at the values of the three facts in Snowsight | Row counts are done (section 5). The values are not. |
| New count query on `DIM_GAME` after the cut to 10 columns | Not done. The counts in section 4 are from before the cut. |
| `metacritic_score` may change between runs | **Checked on 2026-11-06** (read-only query on `STG_STEAM__GAMES`, 8 runs, screenshot of the result). 0 of 81 games changed `name`, `release_date_text`, `required_age`, `metacritic_score`, `website` or `genres`. So `metacritic_score` stays in `dim_game`. Only 8 runs over about two weeks, so this is not proof for later. |
| `type` is always "game" | Not checked for the dimension. The staging test accepts `game` only and warns on other values, and it gave no warning. `type` is dropped from `dim_game` anyway. |
| Free games in price averages | Decide in the marts. A free game has a NULL price, and NULL prices are skipped by an average. |
| A failed run (a `load_id` missing in one table) and two runs in one day | Not tested. `assert_81_games_per_run` would warn on a partial run. |
| The rows of the three facts in Snowsight | The row counts, the prices of the free and no-price games, and the recent and language columns of `fact_game_reviews` and the player counts per day are checked (section 5, validation). Not looked at yet: single games. |
| Picture `assets/logical_model_1.png` | Re-exported on 2026-11-06. The bottom of the `fact_game_reviews` box is cut off a little. |
| `docs/03` and `docs/04` still say "password and MFA" for `DBT_USER` | A small doc fix, only when I say so |
