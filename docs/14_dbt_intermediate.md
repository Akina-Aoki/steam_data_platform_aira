# dbt Intermediate Layer: Steam Data Platform

## Overview

The intermediate layer joins and shapes the five staging views. It holds the prep models and the star schema (`fact_game_snapshot`, `dim_game`, `dim_date`). All of it is built as **views** in `STEAM_DB.INTERMEDIATE` ([doc 13](13_conceptual_model.md), section 9).

**Branch:** `feat/dbt-intermediate`
**Status:** In progress. 2 of 5 models are built (`int_steam__games_latest`, `dim_date`). This document is extended after each model.

`Steam Data → dlt → STEAM_RAW → dbt Staging → dbt Intermediate → dbt Marts → Streamlit`

The design decisions (grain, star schema, columns) are in [doc 13](13_conceptual_model.md). This document records what was built and what was found.

There is no reference model to copy for this layer. The Flight-punctuality repo has no middle layer, and the lecture repo puts its dimensions and facts in a `warehouse` schema. The layer follows doc 13.

## 1. Models

| # | Model | One row is | Status |
|---|---|---|---|
| 1 | `int_steam__games_latest` | one game | Built and tested (2026-11-06) |
| 2 | `dim_date` | one Stockholm day that has a run | Built and tested (2026-11-06) |
| 3 | `dim_game` | one game | Not built |
| 4 | `int_steam__game_run` | one game per run | Not built |
| 5 | `fact_game_snapshot` | one game per run | Not built |

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

## 4. How to Run

From the `dbt_project/` folder, with the virtual environment active:

```bash
set -a; source ../.env; set +a
dbt build --select int_steam__games_latest dim_date
```

## 5. Decisions

| Decision | Reason |
|---|---|
| Newest row per game uses `row_number()` in a CTE, not `qualify` | A CTE reads more easily for a beginner |
| `load_id` is the tie-break after `collected_at_utc` | Two rows with the same time still give exactly one winner |
| Unreleased games are kept | `coming_soon` tells them apart. Zero reviews or `result = 42` never mean "unreleased". |
| `dim_date` holds only days that have a run, no `date_spine` | No start date or end date to keep up. The list stops growing when ingestion stops. A fact row always finds its day, so the `relationships` test cannot fail on a date. The first plan used `dbt_utils.date_spine` (suggested in the handoff, not copied from a reference repo). It needs an end date and builds empty days that nothing uses. |
| `day_of_week` and `week_of_year` use the ISO rules | They do not depend on a Snowflake setting |

**Limit of `dim_date`:** days without a run have no row. This is fine because the dashboard shows markers per run, not a line over gaps ([doc 13](13_conceptual_model.md), section 8). If empty days are needed later, switch to `date_spine`. No column changes.

## 6. Not done yet

| Item | Status |
|---|---|
| `dim_game`, `int_steam__game_run`, `fact_game_snapshot` | Next, in this order |
| `metacritic_score` may change between runs | Not checked. Check before building `dim_game`. If it changes, it moves from `dim_game` to the fact. |
| Completeness test (81 games per run, `severity: warn`) | Planned for `int_steam__game_run` |
| Recent reviews never above all-time reviews (`warn`) | Planned for `int_steam__game_run`, needs a join |
| A failed run (a `load_id` missing in one table) and two runs in one day | Not tested |
