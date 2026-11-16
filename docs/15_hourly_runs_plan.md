# Plan: One Full Run Every Hour, Scheduled with Dagster

**Status:** Written on 2026-11-16 and updated the same day. Section A (the one-fact model) and step B2 are done. The hand-run test (B3 and B4) is in progress. Dagster (section C) is postponed. Branch: `feat/one-fact-table`.

**For an agent reading this:** read sections 1 to 3 first, then work through section 4 one row at a time, in order. The Status column says where we are. Keep changes to the bare minimum (section 3 lists what must **not** change).

**How to work with me (the user is a beginner data engineer and a student):**

- I run **every** terminal command myself, including read-only ones like `ls` and `git status`. Ask me and I paste the output. Do not run them.
- Show code in chat and I paste it into the files. Edit only markdown in `docs/`, and only when I ask. Give whole files for YAML and the dbml.
- Never open `.env`, `.dlt/secrets.toml` or key files. Do not change Snowflake (drop views, grants) without asking me first. Never use DuckDB.
- Do not push or open a PR unless I ask. `scratch/` is in `.gitignore`: do not commit it.
- One small step per message, explained in plain words with an everyday comparison. Say what success looks like. When I say "wait" or "I don't get it", go simpler.
- Be honest about what is verified and what is not. Give one recommendation, not a menu. Do not reopen decisions marked Agreed.
- Commit messages need a body and the trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Remind me, I forget it.

**Next steps, in order (as of 2026-11-16):** finish the hand-run test (B3: runs 2 and 3 at 10:41 and 11:41, B4: the full `dbt build`), fix the stale docs and the dbml (section 5), then decide the marts (section 4 D, and section 7). Dagster only after I say go.

## 1. The goal

My teacher said the dashboard will be more accurate if the pipeline runs every hour instead of once a day.

| Decision | Status | Reason |
|---|---|---|
| Every hour, run the **full** pipeline for **all 81 games**, all five tables | Agreed 2026-11-16 | The dashboard shows one point per hour. It does not split the games across the hours. |
| The scheduler is **Dagster**, not Airflow | Agreed 2026-11-16. **Postponed the same day.** | My choice. Airflow was only ever "future work" in the docs. For now we develop locally and I start the run by hand every hour. Dagster comes after the hourly runs are proven to work (section C). |
| One fact table, `fact_game_snapshot`, plus `dim_game` and `dim_date` | Agreed 2026-11-16 | See [doc 13](13_conceptual_model.md). The three-fact version stays in `main` until this branch is merged. |

| No `dim_hour` table, and no hour in `dim_date` | Agreed 2026-11-16 | The dashboard filters by hour with `snapshot_hour_local`, which the mart takes from the fact. `dim_date` stays one row per day. A "part of day" label (morning, afternoon, evening) can be one line of SQL in a mart later, if wanted. |

**Why all 81 games in one run, and not a part per hour:** the fact table joins the four sources on `steam_appid` + `load_id`. That only works when all four tables come from the same complete run. A split run would break that join and the "81 games per run" check.

## 2. Where we are

| Item | State |
|---|---|
| `main` | Three fact tables (`fact_game_store`, `fact_game_reviews`, `fact_game_players`). Not touched. |
| Branch `feat/one-fact-table` | Created from `main`. Commit `fccb3f8` reverted the three-fact commit `71eed57`. Later commits on the branch: the one-fact model, a commit that stopped tracking `scratch/` (it is now in `.gitignore`), and the A2/A3 work. Check `git log` for what is pushed. |
| `dim_game.sql` | One row per game, 14 columns: `steam_appid`, `name`, `type`, `release_date`, `release_year`, `release_date_text`, `metacritic_score`, `website`, `short_description`, `developers`, `publishers`, `genres`, `genres_text`, `categories`. The three `platform_*` columns and `required_age` are removed. Built and tested. |
| `fact_game_snapshot.sql` and its block in `_int_steam__models.yml` | Built and tested. One row per game per run, 19 columns, including `snapshot_hour_local`. |
| `dbt_project/tests/assert_81_games_per_run.sql` | Re-created for the one fact. Passes. |
| Data in `fact_game_snapshot` | 10 runs, 81 games each (checked 2026-11-16): 10-23, 10-26, 10-27, 10-30, 11-02, 11-03, 11-05, 11-06, 11-11 and 11-16. The 11-16 run (`load_id` `1794818498.852425`, run hour 9) is the first hourly-test run. |
| Ingestion (dlt) | Works. One run = 5 resources, 486 requests, about 21 minutes (measured 2026-11-02 and again on 2026-11-16, [doc 08](08_steam_py_code_guide.md)). Run by hand. |
| Scheduler | None. |
| Marts | Not built. |

## 3. What does NOT change

This is what keeps things from breaking. Do not touch these.

| Part | Why it stays |
|---|---|
| The dlt pipeline and `steam.py` | One call to `run_steam_pipeline()` already does one complete run of all 81 games and all five resources, with one `load_id`. Running it every hour is just calling it every hour. |
| The 2-second pause between requests (`REQUEST_PAUSE_SECONDS`) | It keeps us at about 0.5 requests per second, far below the ~1 per second people report as safe. Each run is the same speed as today, just repeated. Do not lower it. |
| `write_disposition="append"` | Every run must add new rows. That is what builds the history. |
| The join on `steam_appid` + `load_id` | Already agreed in [doc 13](13_conceptual_model.md). A second run in one day is already allowed. |
| The five staging models | They keep `collected_date` (a Stockholm day) and `load_id`. Their `unique` tests use `load_id`, not the date, so hourly runs do not break them. |
| `dim_date` | Still one row per day. The hour lives in the fact, not in the date dimension. |
| Intermediate layer as **views** | Views are always fresh, so dbt does not need to run after each ingestion yet. This changes only if the marts become tables. |
| Snowflake setup | The warehouse is `XSMALL` with `AUTO_SUSPEND = 60`. It sleeps between loads. No change. |

## 4. The change list

Do these in order. Each row is a small step. Mark the Status column as we go.

### A. Finish the one-fact model first (before any scheduling)

| # | What | Files | Size | Status |
|---|---|---|---|---|
| A1 | Build and test `dim_game` and `fact_game_snapshot`. I run `dbt build --select dim_game fact_game_snapshot` and paste the output. | none | tiny | **Done 2026-11-16.** `dbt build --select dim_game fact_game_snapshot` gave `PASS=11 WARN=0 ERROR=0`. |
| A2 | Add the run hour to the fact: `snapshot_hour_local`, the Stockholm hour of the run, taken from `games.collected_at_utc`. The old `collected_hour_local` column comes from the player count (NULL for early runs), so it cannot be used as the run hour. | `fact_game_snapshot.sql`, its yml block | 2 lines | **Done 2026-11-16**, built with `PASS=9 WARN=0 ERROR=0` |
| A3 | Re-create the completeness test `assert_81_games_per_run.sql` for the one fact (`warn`: every `load_id` must have exactly 81 rows). | `dbt_project/tests/` | 1 file | **Done 2026-11-16**, passed (no run has a number of games other than 81) |
| A4 | Drop the three old views from Snowflake (`FACT_GAME_STORE`, `FACT_GAME_REVIEWS`, `FACT_GAME_PLAYERS`) in `STEAM_DB.INTERMEDIATE`. dbt does not drop models that were removed. Optional, they do no harm. | Snowflake | tiny | Not started |

### B. Ingestion

| # | What | Files | Size | Status |
|---|---|---|---|---|
| B1 | No code change. Check `run_steam_pipeline()` is the one function Dagster will call. It returns `LoadInfo`. After it, Dagster must call `load_info.raise_on_failed_jobs()` like `pipelines_steam.py` does, so a failed load shows as a failed Dagster run. | none | tiny | Not started |
| B2 | Time one full run on this machine and write the number in this doc. A run must finish well before the next hour starts. About 21 minutes so far. | this doc | tiny | **Done 2026-11-16.** The run with `load_id` `1794818498.852425` started at 09:41 and finished at 10:02 (Stockholm time), so about 21 minutes. All four tables have 81 rows for it. |
| B3 | **Hand-run test:** start the pipeline by hand at the same minute of 3 hours in a row. After each run, check in Snowflake that the new `load_id` has 81 rows in `games`, `review_summary`, `player_counts` and `review_recent`, and look in the log for any 429 line. | none, commands only | small | **In progress.** Run 1 of 3 is done (started 09:41, `load_id` `1794818498.852425`, 81 rows in all four tables, no error). Runs 2 and 3 are due at 10:41 and 11:41. |
| B4 | After the 3 runs: `dbt build` for the whole project, and check that every test passes, that `fact_game_snapshot` has 3 new runs of 81 rows, and that no `unique` test fails. | none | tiny | **Partly done 2026-11-16.** The whole-project `dbt build` already passed on the current data (`PASS=60 WARN=0 ERROR=0`: 9 models, 51 tests). It still has to be repeated after the hourly runs (B3). |

### C. Dagster (the scheduler): postponed

Do not start this until B3 and B4 have passed. Until then the run is started by hand every hour.

| # | What | Files | Size | Status |
|---|---|---|---|---|
| C1 | Add a new dependency group `orchestration` with `dagster` and `dagster-webserver` to `pyproject.toml`, then `uv sync`. Check the current Dagster docs for versions when we do this step. | `pyproject.toml`, `uv.lock` | small | Not started |
| C2 | Create the Dagster definitions: one job (or one asset) that calls `run_steam_pipeline()` and `raise_on_failed_jobs()`, and one schedule with the cron `0 * * * *` (every hour on the hour), time zone `Europe/Stockholm`. | new file, for example `src/steam_data_platform/orchestration/definitions.py` | small | Not started |
| C3 | Make sure only **one run at a time** can happen, so a slow run never overlaps the next one. | Dagster config (`dagster.yaml`) | small | Not started |
| C4 | Pass the Snowflake settings to Dagster: start it with the same `.env` as the pipeline (`uv run --env-file .env dagster dev ...`). The private key file path is read from the environment by `connections.py`. | none, command only | tiny | Not started |
| C5 | Test: start Dagster, trigger the job by hand once from the web page, and check the new `load_id` has 81 rows in all tables. Only then turn the schedule on. | none | tiny | Not started |
| C6 | Remove the empty Airflow-style folders `orchestration/dags/.gitkeep` and `docker/.gitkeep` if Dagster does not use them. | those two files | tiny | Not started |

No dbt step is scheduled. The intermediate layer is views, so it is always fresh.

### D. Marts (not built yet, so decide before building)

| # | What | Status |
|---|---|---|
| D1 | `mart_game_detail`: keep one row per game per run, so there is one point per hour. Decide what "change since the previous run" means now. Versus the previous run is only an hour ago and is often 0. Versus the same hour yesterday may be more useful. | Open |
| D2 | `mart_genre_comparison`: it is one row per genre per day. With 24 runs a day, decide: per run, or the latest run of each day. | Open |

### E. Dashboard (later)

| # | What | Status |
|---|---|---|
| E1 | Time axis uses `snapshot_date` and `snapshot_hour_local`, or the timestamp `collected_at_utc` in Stockholm time. | Later |

## 5. Docs that must be updated

Only after the code step they describe is done. These docs say "once a day" or "Airflow".

| Doc | What to change |
|---|---|
| [05](05_games__dlt_ingestion.md), [06](06_reviews__dlt_ingestion.md), [07](07_player_counts__dlt_ingestion.md) | "How to run (once per day at most)" and the "one scheduled run per day" rules. Hourly now. |
| [09](09_key_pair_login.md) | "Unchanged, once a day at most", and "Airflow (future work)". Now Dagster, hourly. |
| [01](01_infra_setup.md) | "Apache Airflow running inside Docker". Now Dagster. |
| [13](13_conceptual_model.md) | Section 6.4 and 9 for the one fact and the removed platform columns. Section 7 (history). Section 8 "Gaps in the date axis" and "Player counts depend on the hour". Section 10 "Airflow as Stage 2". |
| [14](14_dbt_intermediate.md) | The model list: `int_steam__game_run` is dropped, the fact is `fact_game_snapshot`. |
| `logical_model.dbml` and `assets/logical_model_1.png` | The new dbml (the two dimensions and the one fact, no marts) was written on 2026-11-16 and has to be pasted into the file. Then the png is redrawn on dbdiagram.io. The repo files were still the old version when this was checked. |
| `_int_steam__models.yml` | The `dim_game` description still says "store info, platforms, lists". Change it to "store info, lists". Text only. |
| [13](13_conceptual_model.md) and [14](14_dbt_intermediate.md) | **Done 2026-11-16.** Both now describe the one fact, the 14 columns of `dim_game`, `snapshot_hour_local`, 10 runs and the hourly plan. Doc 14 has a new section for `fact_game_snapshot`, so its later sections moved from 5, 6, 7 to 6, 7, 8. The caption of the picture in doc 13 is updated, but the png itself still has to be redrawn. |

## 6. Things to remember

| Topic | What to remember |
|---|---|
| **Dagster must be running** | A schedule only fires while the Dagster process (`dagster dev`) is running. If this PC is asleep or off, hours are skipped. Where Dagster runs is an open decision (section 7). |
| **Missed hours are normal** | Gaps will happen. Charts must not draw a straight line over a gap as if it were a trend. Use markers. |
| **A failed run loads nothing** | If Steam answers 429 three times, the run stops before loading. There is no half run. That hour is simply missing. A single game that fails is skipped, so that run has fewer than 81 rows, and the 81-games test warns. |
| **A run takes about 21 minutes** | The run hour comes from the `games` timestamp, taken at the start of the run, so start the schedule on the hour (cron `0 * * * *`). The player counts come up to about 20 minutes later. |
| **What `snapshot_hour_local` means** | It is the Stockholm hour in which the run **started**. A dlt `load_id` is the Unix time of the start: `1794818498` is 08:41 UTC, which is 09:41 Stockholm, so the hour is 9 even though the run ended at 10:02. This is correct, not a one-hour delay (checked 2026-11-16). Start every run at the same minute. |
| **Clock change** | `snapshot_hour_local` repeats once when the clocks go back in autumn. Use `collected_at_utc` for ordering. |
| **Data grows 24 times faster** | About 2,000 rows per table per day (81 x 24). Fine for Snowflake. `achievements` has more rows per game. |
| **Steam limits are not official** | No official limit exists for the Store endpoints ([doc 05](05_games__dlt_ingestion.md)). Watch the logs for 429 in the first days. If any appear, slow down before anything else. |
| **Snowflake credits** | Each load wakes the warehouse. Check the credit balance after the first days. |

## 7. Open decisions

| # | Question | Options |
|---|---|---|
| 1 | Where does Dagster run? | (a) On this PC with `dagster dev`, fine for testing, but the PC must stay on. (b) In Docker on this PC, same problem. (c) On an always-on machine or a Dagster cloud service, which may cost money. |
| 2 | Where does the Dagster code live? | Inside the package (`src/steam_data_platform/orchestration/`) or in the top-level `orchestration/` folder |
| 3 | Do we want a "freshness" check that warns when the newest run is more than 2 hours old? | Later, as a dbt source freshness check. Not part of the bare minimum. |
