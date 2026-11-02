# dbt Sources and Staging: Steam Data Platform

## Overview

dbt now reads the three raw tables in `STEAM_DB.STEAM_RAW` and cleans them into three staging views in `STEAM_DB.STAGING`. The raw tables are not changed.

**Branch:** `feat/dbt-staging`
**Status:** Models built and tested on 2026-11-02, merged into `main`. This doc is added after the merge.

`Steam Data → dlt → STEAM_RAW → dbt Staging → dbt Intermediate → dbt Marts → Streamlit`

Only the staging step is done. Intermediate and marts do not exist yet.

## 1. Sources

File: [`_steam__sources.yml`](../dbt_project/models/staging/_steam__sources.yml)

A source is a list of the raw tables, so a model can write `{{ source('steam', 'games') }}` instead of a hard-coded table name.

| Source table | Raw table | What is in it |
|---|---|---|
| `games` | `STEAM_RAW.GAMES` | Store appdetails, one row per game per run |
| `review_summary` | `STEAM_RAW.REVIEW_SUMMARY` | Review totals, one row per game per run |
| `player_counts` | `STEAM_RAW.PLAYER_COUNTS` | Players at one moment, one row per game per run |

| Decision | Reason |
|---|---|
| One file, no `steam/` subfolder | There is only one source |
| No tests and no freshness check on the sources | Tests sit next to the models, like the Flight-punctuality reference project, which has no freshness check either. |

## 2. What staging does

The rule for staging: **one row in = one row out.** It cleans the form (units, types, time zones). No joins and no business rules.

| Model | Reads from | What it does |
|---|---|---|
| [`stg_steam__games`](../dbt_project/models/staging/stg_steam__games.sql) | `games` | Prices from cents to euros, times in UTC, `release_date` as a real date, HTML codes fixed in `short_description`, Portal 2 test row removed |
| [`stg_steam__review_summary`](../dbt_project/models/staging/stg_steam__review_summary.sql) | `review_summary` | Times in UTC, adds `pct_positive` and `has_reviews` |
| [`stg_steam__player_counts`](../dbt_project/models/staging/stg_steam__player_counts.sql) | `player_counts` | Times in UTC, adds `has_player_data`. A missing count stays NULL. |

All three are views (set in `dbt_project.yml`), so no data is copied.

### Columns changed in all three models

| Raw column | Staging column | Why |
|---|---|---|
| `_dlt_load_id` | `load_id` | Says which run a row came from |
| `collected_at` (`TIMESTAMP_LTZ`) | `collected_at_utc` | `LTZ` shows in the session's time zone, so the same row can look different. UTC is the same everywhere. |
| `collected_at` | `collected_date` | The Stockholm day. Used later to join the three tables, because their exact times never match. |

`stg_steam__player_counts` also has `collected_hour_local` (Stockholm hour), so runs at the same time of day can be compared.

### `stg_steam__games` only

| Raw column | Staging column | What changes |
|---|---|---|
| `price_initial`, `price_final` | same names | Divided by 100 (Steam sends cents, 969 = 9.69), rounded to 2 decimals. NULL stays NULL, never 0. |
| `release_date_text` | `release_date_text` and `release_date` | `try_to_date(..., 'DD MON, YYYY')`. The text is kept next to the date. |
| `short_description` | same name | Macro [`decode_html_entities`](../dbt_project/macros/decode_html_entities.sql) |
| `developers`, `publishers`, `genres`, `categories` | same names | Stay as lists. They are unpacked later in the intermediate layer. |

## 3. What we found in the data

Before writing the models, two read-only queries were run in Snowsight on the newest run (collected 2026-10-30).

| Finding | Evidence | What staging does |
|---|---|---|
| The date pattern `DD MON, YYYY` works for every released game | 81 rows. Only the 4 unreleased games (two "Coming soon", two "To be announced") have no parsed date. | `try_to_date` gives NULL for these 4, no error |
| Only two HTML codes exist: `&amp;` and `&quot;` | 3 games: 300550, 310060, 794820 | The macro replaces these two. `&quot;` first and `&amp;` last, so `&amp;quot;` cannot turn into a quote by mistake. |
| Prices are right after the division | The view shows `14.99` and `9.99`, not `1499` | none needed |
| A missing player count is not a zero player count | NULL count has `result = 42`. A real zero has `result = 1`. | `player_count` is kept as it is. `has_player_data` is `result = 1`. |
| Zero reviews does not mean "unreleased" | One released free game has no reviews | `has_reviews` is only a flag. "Unreleased" comes from `coming_soon` in games. |

The macro only knows these two codes. If Steam sends another one (for example `&#39;`), it stays in the text. A new check for that is not added yet.

## 4. Tests

All tests are in [`_steam__models.yml`](../dbt_project/models/staging/_steam__models.yml), next to the model descriptions. There are 20 tests. Some are set to `warn`: a warning shows up, but the build does not fail.

| Model | Tests | `warn` |
|---|---|---|
| `stg_steam__games` | `steam_appid` + `load_id` unique. `not_null` on `steam_appid`, `load_id`, `collected_at_utc`. `type` is `game`. `price_final <= price_initial` (only when both prices exist). | `type`, price check |
| `stg_steam__review_summary` | `steam_appid` + `load_id` unique. `not_null` on the same 3 columns. positive + negative = total. Every `steam_appid` exists in `stg_steam__games`. | none |
| `stg_steam__player_counts` | `steam_appid` + `load_id` unique. `not_null` on those columns and `result`. Every `steam_appid` exists in `stg_steam__games`. `result` is 1 or 42. A count comes with `result` 1, no count with `result` 42. | `result` values, count vs result |

The `unique` test uses `load_id` and not `collected_at`, because in `player_counts` every row has its own time.

## 5. Validation

| Command (from `dbt_project/`) | Result |
|---|---|
| `dbt debug` | All checks passed |
| `dbt parse` | Parsed. 2 unused-config warnings for `intermediate` and `marts` are expected, there are no models there yet. |
| `dbt build` | 3 views and 20 tests: `PASS=23 WARN=0 ERROR=0` |

Schema naming from [doc 04](04_dbt_foundation.md) is now checked: the models were created as `staging.stg_steam__...` and read back from `STEAM_DB.STAGING`.

## 6. How to Run

From the `dbt_project/` folder:

```bash
uv run --env-file ../.env dbt build
```

`--env-file ../.env` loads the Snowflake settings that `profiles.yml` reads with `env_var(...)`. Without it, dbt stops with a missing-variable error. To build one model: add `--select stg_steam__games`.

Shorter way: load `.env` once per terminal window, then type plain `dbt` commands. The virtual environment must be active (the prompt shows its name).

```bash
set -a; source ../.env; set +a
dbt build
```

This was tested with `dbt debug` on 2026-11-02 in Git Bash (`All checks passed!`). It only works while `.env` is plain `KEY=value` lines. It must be repeated in every new terminal.

## 7. Decisions

| Decision | Reason |
|---|---|
| `DBT_USER` logs in with the password | `DESC USER DBT_USER` shows `HAS_MFA = false`, like `DLT_USER`. A broken dbt login loses no data. A broken ingestion login loses a day of Steam data, which is why `DLT_USER` got a key pair ([doc 09](09_key_pair_login.md)). If Snowflake blocks passwords later, the same steps work for `DBT_USER`. |
| Removed `authenticator: username_password_mfa` from `profiles.yml` | `DBT_USER` has no MFA, and the line is not in the Flight-punctuality reference project |
| Models go straight into the real `STAGING` schema | `generate_schema_name.sql` uses the schema from `dbt_project.yml`, and `DBT_SCHEMA=staging`. There is no personal sandbox schema. This is fine for one person. |
| Portal 2 (appid 620) is filtered with `where steam_appid <> 620` | It is an old test row in `games`. A seed with the 81 ids would be a second copy of `GAME_APPIDS`. |
| The four list columns stay lists in staging | Unpacking them changes the number of rows. That belongs in the intermediate layer. |
| `pct_positive` is a percent with one decimal (91.0), not a fraction | The notebooks show percent |
| `collected_date` is the Stockholm day | All three models use the same day, so the dates match when they are joined |

## 8. Not done yet

| Item | Status |
|---|---|
| Intermediate layer (latest row per game, unpacking lists, joins on the date) | Next PR |
| Marts and Streamlit | Later |
| What `result = 42` means exactly | Unverified. We only say "Steam has no data". |
| Rule for repeated runs on the same day | Open. Joining on date only works with one run per day. |
| Minimum number of reviews and players for comparisons | Not decided |
| Checked on today's data only (4 snapshots of games) | If Steam changes a date format or sends a new `result` code, the tests should warn. Not tested on such a change. |
