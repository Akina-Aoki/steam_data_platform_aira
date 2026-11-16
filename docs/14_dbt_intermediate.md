# dbt Intermediate Layer: Steam Data Platform

## Overview

The intermediate layer joins and shapes the five staging views. It holds the prep models and the star schema (`fact_game_snapshot`, `dim_game`, `dim_date`). All of it is built as **views** in `STEAM_DB.INTERMEDIATE` ([doc 13](13_conceptual_model.md), section 9).

**Branch:** `feat/one-fact-table` (the first three models were built on `feat/dbt-intermediate`)
**Status:** The four models are built and tested (`int_steam__games_latest`, `dim_date`, `dim_game`, `fact_game_snapshot`). The whole-project `dbt build` gave `PASS=60 WARN=0 ERROR=0` on 2026-11-16, and again with the same result after the three hourly rounds of that day. History: on 2026-11-06 the single fact was split into three after a tip from my teacher (the commit `71eed57`, still on `main`). On 2026-11-16 I went back to one fact. The marts are not built yet.

`Steam Data → dlt → STEAM_RAW → dbt Staging → dbt Intermediate → dbt Marts → Streamlit`

The design decisions (grain, star schema, columns) are in [doc 13](13_conceptual_model.md). This document records what was built and what was found.

There is no reference model to copy for this layer. The Flight-punctuality repo has no middle layer, and the lecture repo puts its dimensions and facts in a `warehouse` schema. The layer follows doc 13.

## 1. Models

| # | Model | One row is | Status |
|---|---|---|---|
| 1 | `int_steam__games_latest` | one game | Built and tested (2026-11-06) |
| 2 | `dim_date` | one Stockholm day that has a run | Built and tested (2026-11-06) |
| 3 | `dim_game` | one game | Built and tested (2026-11-06) |
| 4 | `fact_game_snapshot` | one game per run | Built and tested (2026-11-16) |

`int_steam__game_run` (a four-way join in front of the fact) was planned and **dropped**. It was never built. The joins are inside `fact_game_snapshot`.

Descriptions and tests are in [`_int_steam__models.yml`](../dbt_project/models/intermediate/_int_steam__models.yml).

## 2. `int_steam__games_latest`

File: [`int_steam__games_latest.sql`](../dbt_project/models/intermediate/int_steam__games_latest.sql)

It keeps the newest row of each game from `stg_steam__games`. It is the base of `dim_game`.

| Step | What it does |
|---|---|
| `row_number() over (partition by steam_appid order by collected_at_utc desc, load_id desc)` | Numbers each game's rows, newest first. `load_id` only breaks a tie. |
| `where row_num = 1` | Keeps the newest row. The helper column is then removed with `exclude`. |

All columns of `stg_steam__games` stay unchanged. Unreleased games are kept (`coming_soon` tells them apart).

**Limit:** if a game is missing from the newest run (for example one request failed), its "latest" row comes from an older run. That is fine for a description (`dim_game`). It is why the fact table has one row per game per run.

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

One row per Stockholm day that has a run. The days come from `select distinct collected_date` on `stg_steam__games`. The fact table will point to it with `snapshot_date`.

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

## 4. `dim_game`

File: [`dim_game.sql`](../dbt_project/models/intermediate/dim_game.sql)

One row per game, with the things that rarely change. It reads `int_steam__games_latest` (the newest row of each game).

| Group | Columns |
|---|---|
| Identity | `steam_appid`, `name`, `type` |
| Release | `release_date`, `release_year`, `release_date_text` |
| Store info | `metacritic_score`, `website`, `short_description` |
| Lists | `developers`, `publishers`, `genres`, `categories` (stay lists) |
| Readable text | `genres_text` |

That is 14 columns. **Dropped on 2026-11-16:** `required_age`, `platform_windows`, `platform_mac` and `platform_linux`. No business area in [doc 13](13_conceptual_model.md) needs them. A column can be added back with one line in `dim_game.sql`.

Worked out here: `release_year = year(release_date)` (NULL for unreleased games) and `genres_text = nullif(array_to_string(genres::array, ', '), '')`. The price and status columns (`price_*`, `discount_percent`, `is_free`, `coming_soon`) and `recommendations_total` are not in `dim_game`. The fact owns them.

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
| `dbt build --select dim_game` | `Found 8 models, 43 data tests`. 1 view and 2 tests: `PASS=3 WARN=0 ERROR=0` |
| Counts on `STEAM_DB.INTERMEDIATE.DIM_GAME` (screenshot, 2026-11-06) | 81 rows, 81 games, 77 with `release_year`, 81 with `genres_text`, 45 with `metacritic_score` |
| First 8 rows by release year | The 4 games without a year have "To be announced" or "Coming soon" as text (Afterworld, Guardians of the Wild Sky, LEGO Skylines, Prison Architect 2). The next four are the oldest games and their years match the text (2008 and 2009). `genres_text` reads like `Simulation, Strategy`. |
| `dbt build --select dim_game fact_game_snapshot` (2026-11-16, after the four columns were dropped) | `PASS=11 WARN=0 ERROR=0` for both models and their tests together. The row counts above are from 2026-11-06, before the cut. |

## 5. `fact_game_snapshot`

File: [`fact_game_snapshot.sql`](../dbt_project/models/intermediate/fact_game_snapshot.sql)

One row per game per run: the store page, the reviews and the players together. It starts from `stg_steam__games` and uses three **left joins** (`stg_steam__review_summary`, `stg_steam__review_recent`, `stg_steam__player_counts`) on `steam_appid` + `load_id`. The base is `games` because it has a row in every run. The other tables started later, so the early runs keep their row and the missing values stay NULL. It stores counts only, never percentages.

19 columns:

| Group | Columns | Comes from |
|---|---|---|
| Keys | `steam_appid`, `load_id`, `snapshot_date` | `stg_steam__games` (`collected_date` is the Stockholm day) |
| Time | `collected_at_utc`, `snapshot_hour_local` | `stg_steam__games`. The hour is `hour(convert_timezone('UTC', 'Europe/Stockholm', collected_at_utc))`. |
| Store page | `price_currency`, `price_initial`, `price_final`, `discount_percent`, `is_free`, `coming_soon` | `stg_steam__games` |
| Reviews, all time | `total_positive`, `total_negative`, `counts_all_languages` | `stg_steam__review_summary` |
| Reviews, last 30 days | `recent_positive`, `recent_negative` | `stg_steam__review_recent`. NULL before 2026-11-02. |
| Players | `player_count`, `has_player_data`, `collected_hour_local` | `stg_steam__player_counts`. NULL for the runs before 2026-10-27. |

### Tests

| Where | Test |
|---|---|
| Model | `dbt_utils.unique_combination_of_columns` on (`steam_appid`, `load_id`). It fails if a join multiplied rows. |
| Model | `dbt_utils.expression_is_true`: recent reviews never above all-time reviews (`warn`, skips rows with no recent data and runs before 2026-11-02) |
| `steam_appid` | `not_null` and `relationships` to `dim_game` |
| `load_id` | `not_null` |
| `snapshot_date` | `not_null` and `relationships` to `dim_date` |
| `dbt_project/tests/assert_81_games_per_run.sql` | A singular test (`warn`): returns every run that does not have exactly 81 rows |

That is 8 tests.

### Validation

| Check | Result |
|---|---|
| `dbt build --select dim_game fact_game_snapshot` (2026-11-16) | `PASS=11 WARN=0 ERROR=0` |
| `dbt build --select fact_game_snapshot` after adding `snapshot_hour_local` and the 81-games test (2026-11-16) | `Found 9 models, 51 data tests`. 1 view and 8 tests: `PASS=9 WARN=0 ERROR=0` |
| Whole project `dbt build` (2026-11-16) | `PASS=60 WARN=0 ERROR=0`: 9 view models and 51 tests |
| Read-only query on `STEAM_DB.INTERMEDIATE.FACT_GAME_SNAPSHOT`, grouped by run (CSV export, 2026-11-16) | 10 runs, each with 81 games. Run hours, oldest first: 14, 12, 10, 15, 13, 14, 15, 9, 19, 9. |
| Same checks after the three hourly rounds (2026-11-16): SQL in `SQL/01_star_checks.ipynb`, and a whole-project `dbt build` | 13 runs, 1,053 rows (13 x 81), no duplicate key, no run without 81 games. The three new runs have the hours 11, 12 and 13. `dbt build` gave `PASS=60 WARN=0 ERROR=0` (I saw the last line only). |

### Findings

| Finding | Evidence |
|---|---|
| `snapshot_hour_local` is the hour the run **started**, not a delay | The newest run showed hour 9 while it was already 10 o'clock. A dlt `load_id` is the Unix time of the start. `1794818498` is 08:41 UTC, which is 09:41 Stockholm. The run ended at 10:02. This is my calculation from the `load_id` and the terminal log, not a Snowflake query. |
| Each run has 81 games in the fact | The CSV above, and `assert_81_games_per_run` passed |

## 6. How to Run

From the `dbt_project/` folder, with the virtual environment active:

```bash
set -a; source ../.env; set +a
dbt build --select int_steam__games_latest dim_date dim_game fact_game_snapshot
```

Or the whole project, which also runs the staging models:

```bash
dbt build
```

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
| One fact table, `fact_game_snapshot`. The three-fact version of 2026-11-06 is not used. | One table is simpler to read, and the mart needs no join between facts. The fact keeps the early runs by starting from `games` with left joins. See [doc 13](13_conceptual_model.md), section 9. |
| No `int_steam__game_run` | The joins are inside the fact. A second model with the same columns would only have to be kept in sync. |
| The run hour (`snapshot_hour_local`) is worked out in the fact from the `games` time | `games` has a row in every run. The hour in `collected_hour_local` comes from the player counts, so it is NULL for early runs and it is the hour of the count, not of the run. |
| `discount_percent` stays in the fact | It is Steam's own number, taken from `stg_steam__games`. The marts can check it against the two prices. |
| No `dim_hour` table | The dashboard filters by hour on `snapshot_hour_local`. `dim_date` stays one row per day. |

**Limit of `dim_date`:** days without a run have no row. This is fine because the dashboard shows markers per run, not a line over gaps ([doc 13](13_conceptual_model.md), section 8). If empty days are needed later, switch to `date_spine`. No column changes.

## 8. Not done yet

| Item | Status |
|---|---|
| The marts (`mart_game_detail`, `mart_genre_comparison`) | Not built. Two things are decided first: what the "change" columns compare with, and whether the genre mart is per day or per run ([doc 15](15_hourly_runs_plan.md), D1 and D2). |
| Hourly runs | The hand-run test is done: three runs in a row on 2026-11-16 ([doc 15](15_hourly_runs_plan.md)). Dagster comes later. |
| The three old views `FACT_GAME_STORE`, `FACT_GAME_REVIEWS` and `FACT_GAME_PLAYERS` | Still in `STEAM_DB.INTERMEDIATE` from the build on 2026-11-06. dbt does not drop models that were removed. Optional to drop. |
| `metacritic_score` may change between runs | **Checked on 2026-11-06** (read-only query on `STG_STEAM__GAMES`, 8 runs, screenshot of the result). 0 of 81 games changed `name`, `release_date_text`, `required_age`, `metacritic_score`, `website` or `genres`. So they stay in `dim_game`. Only 8 runs over about two weeks, so this is not proof for later. |
| Completeness test (81 games per run, `severity: warn`) | **Done on 2026-11-16**, `assert_81_games_per_run` passes |
| Recent reviews never above all-time reviews (`warn`) | **Done on 2026-11-16**, a test on `fact_game_snapshot`, passes |
| A failed run (a `load_id` missing in one table) | Not tested. |
| Two runs in one day | **Tested on 2026-11-16.** Four runs that day (09:41, 11:43, 12:43 and 13:45). The fact has 13 runs and 1,053 rows in all, and no duplicate key. |
