# Plan: One Full Run Every Hour, Scheduled with Dagster

**Status:** Written on 2026-11-16, updated the same day, and again on 2026-11-20 and 2026-11-23. Section A (the one-fact model, including A4, the three old views dropped), step B2 and the hand-run test (B3 and B4) are done. Dagster (section C) is next, and C1 is done. Branch: `feat/one-fact-table`, merged into `main` with PR #18. **Update 2026-11-20:** the three marts are built and merged into `main` ([doc 16](16_dbt_marts.md)), so section D is done. **Update 2026-11-26:** Dagster (section C) is the next task again. Docker, Postgres and Airflow are not part of Stage 2, and the dashboard ends up inside Snowflake ([doc 17](17_dagster_plan.md)).

**For an agent reading this:** read sections 1 to 3 first, then work through section 4 one row at a time, in order. The Status column says where we are. Keep changes to the bare minimum (section 3 lists what must **not** change).

**How to work with me (the user is a beginner data engineer and a student):**

- I run **every** terminal command myself, including read-only ones like `ls` and `git status`. Ask me and I paste the output. Do not run them.
- Show code in chat and I paste it into the files. Edit only markdown in `docs/`, and only when I ask. Give whole files for YAML and the dbml.
- Never open `.env`, `.dlt/secrets.toml` or key files. Do not change Snowflake (drop views, grants) without asking me first. Never use DuckDB.
- Do not push or open a PR unless I ask. `scratch/` is in `.gitignore`: do not commit it.
- One small step per message, explained in plain words with an everyday comparison. Say what success looks like. When I say "wait" or "I don't get it", go simpler.
- Be honest about what is verified and what is not. Give one recommendation, not a menu. Do not reopen decisions marked Agreed.
- Commit messages need a body and the trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Remind me, I forget it.

**Next steps, in order (as of 2026-11-26):** the star, the hand-run test and the three marts are done and merged into `main`. Next: Dagster (section C and [doc 17](17_dagster_plan.md)), then the dashboard (section E), first on my PC and then inside Snowflake. The open question about a ranking by players ([doc 16](16_dbt_marts.md), section 11) stays open.

## 1. The goal

My teacher said the dashboard will be more accurate if the pipeline runs every hour instead of once a day.

| Decision | Status | Reason |
|---|---|---|
| Every hour, run the **full** pipeline for **all 81 games**, all five tables | Agreed 2026-11-16 | The dashboard shows one point per hour. It does not split the games across the hours. |
| The scheduler is **Dagster**, not Airflow | Agreed 2026-11-16. Postponed the same day. **Picked up again 2026-11-23**, after the hourly runs were proven by hand. | My choice. Airflow was only ever "future work" in the docs. It is not part of Stage 2, and neither are Postgres and Docker (decided 2026-11-26). Dagster runs on my PC (section C). |
| One fact table, `fact_game_snapshot`, plus `dim_game` and `dim_date` | Agreed 2026-11-16 | See [doc 13](13_conceptual_model.md). The branch was merged into `main` with PR #18 on 2026-11-16. The three-fact version is only in the old commit `71eed57`. |
| No `dim_hour` table, and no hour in `dim_date` | Agreed 2026-11-16 | The dashboard filters by hour with `snapshot_hour_local`, which the mart takes from the fact. `dim_date` stays one row per day. A "part of day" label (morning, afternoon, evening) can be one line of SQL in a mart later, if wanted. |

**Why all 81 games in one run, and not a part per hour:** the fact table joins the four sources on `steam_appid` + `load_id`. That only works when all four tables come from the same complete run. A split run would break that join and the "81 games per run" check.

## 2. Where we are

| Item | State |
|---|---|
| `main` | The one-fact star and the three marts. |
| Branch `feat/one-fact-table` | Merged into `main` with PR #18 on 2026-11-16. Commit `fccb3f8` reverted the three-fact commit `71eed57`. Later commits on the branch: the one-fact model, a commit that stopped tracking `scratch/` (it is now in `.gitignore`), and the A2/A3 work. |
| `dim_game.sql` | One row per game, 14 columns: `steam_appid`, `name`, `type`, `release_date`, `release_year`, `release_date_text`, `metacritic_score`, `website`, `short_description`, `developers`, `publishers`, `genres`, `genres_text`, `categories`. The three `platform_*` columns and `required_age` are removed. Built and tested. |
| `fact_game_snapshot.sql` and its block in `_int_steam__models.yml` | Built and tested. One row per game per run, 19 columns, including `snapshot_hour_local`. |
| `dbt_project/tests/assert_81_games_per_run.sql` | Re-created for the one fact. Passes. |
| Data in `fact_game_snapshot` | 13 runs, 81 games each, 1,053 rows (checked 2026-11-16): 10-23, 10-26, 10-27, 10-30, 11-02, 11-03, 11-05, 11-06, 11-11 and four on 11-16 (09:41, 11:43, 12:43 and 13:45). The 09:41 run (`load_id` `1794818498.852425`, run hour 9) was the first hourly-test run. |
| Ingestion (dlt) | Works. One run = 5 resources, 486 requests, about 21 to 23 minutes (measured 2026-11-02 and on 2026-11-16, [doc 08](08_steam_py_code_guide.md)). Run by hand. |
| Scheduler | None. |
| Marts | Built on 2026-11-19 and 2026-11-20 and merged into `main`: `mart_game_detail`, `mart_portfolio_overview` and `mart_genre_comparison`. They are tables. See [doc 16](16_dbt_marts.md). |

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
| Intermediate layer as **views** | Views are always fresh, so the star needs no rebuild after an ingestion run. The marts are tables, so they do go old after each run (see the note under section C). |
| Snowflake setup | The warehouse is `XSMALL` with `AUTO_SUSPEND = 60`. It sleeps between loads. No change. |

## 4. The change list

Do these in order. Each row is a small step. Mark the Status column as we go.

### A. Finish the one-fact model first (before any scheduling)

| # | What | Files | Size | Status |
|---|---|---|---|---|
| A1 | Build and test `dim_game` and `fact_game_snapshot`. I run `dbt build --select dim_game fact_game_snapshot` and paste the output. | none | tiny | **Done 2026-11-16.** `dbt build --select dim_game fact_game_snapshot` gave `PASS=11 WARN=0 ERROR=0`. |
| A2 | Add the run hour to the fact: `snapshot_hour_local`, the Stockholm hour of the run, taken from `games.collected_at_utc`. The old `collected_hour_local` column comes from the player count (NULL for early runs), so it cannot be used as the run hour. | `fact_game_snapshot.sql`, its yml block | 2 lines | **Done 2026-11-16**, built with `PASS=9 WARN=0 ERROR=0` |
| A3 | Re-create the completeness test `assert_81_games_per_run.sql` for the one fact (`warn`: every `load_id` must have exactly 81 rows). | `dbt_project/tests/` | 1 file | **Done 2026-11-16**, passed (no run has a number of games other than 81) |
| A4 | Drop the three old views from Snowflake (`FACT_GAME_STORE`, `FACT_GAME_REVIEWS`, `FACT_GAME_PLAYERS`) in `STEAM_DB.INTERMEDIATE`. dbt does not drop models that were removed. Optional, they do no harm. | Snowflake | tiny | **Done 2026-11-16.** I dropped the three views as `STEAM_TRANSFORMER`. A second `show views in schema STEAM_DB.INTERMEDIATE` (CSV export) shows only the 4 current views: `DIM_DATE`, `DIM_GAME`, `FACT_GAME_SNAPSHOT`, `INT_STEAM__GAMES_LATEST`. |

### B. Ingestion

| # | What | Files | Size | Status |
|---|---|---|---|---|
| B1 | No code change. Check `run_steam_pipeline()` is the one function Dagster will call. It returns `LoadInfo`. After it, Dagster must call `load_info.raise_on_failed_jobs()` like `pipelines_steam.py` does, so a failed load shows as a failed Dagster run. | none | tiny | **Done 2026-11-23** (I read `pipelines_steam.py`). `run_steam_pipeline()` returns `LoadInfo`, and `raise_on_failed_jobs()` is called after it only in the `__main__` block, so Dagster has to call it too. |
| B2 | Time one full run on this machine and write the number in this doc. A run must finish well before the next hour starts. About 21 minutes so far. | this doc | tiny | **Done 2026-11-16.** The run with `load_id` `1794818498.852425` started at 09:41 and finished at 10:02 (Stockholm time), so about 21 minutes. All four tables have 81 rows for it. |
| B3 | **Hand-run test:** start the pipeline by hand at the same minute of 3 hours in a row. After each run, check in Snowflake that the new `load_id` has 81 rows in `games`, `review_summary`, `player_counts` and `review_recent`, and look in the log for any 429 line. | none, commands only | small | **Done 2026-11-16.** The first test run was at 09:41 (`load_id` `1794818498.852425`), but the hour 10 was skipped, so I counted a new test of three runs in a row, one hour apart: 11:43 (`1794825794.9216492`), 12:43 (`1794829390.4537466`) and 13:45 (`1794833102.0641682`, two minutes late). Each one has 81 rows in all four raw tables (checked in Snowflake). The three runs took about 21, 23 and 22 minutes, so each ended well before the next hour. **429:** the log of the 13:45 run was saved, and a search for `429` and `waiting` found 0 lines. The 09:41 run had no 429. The 11:43 and 12:43 runs had no saved log, so a retried 429 is **not checked** for them (a 429 that fixes itself leaves nothing in Snowflake). Start times of the last two are worked out from the `load_id`. |
| B4 | After the 3 runs: `dbt build` for the whole project, and check that every test passes, that `fact_game_snapshot` has 3 new runs of 81 rows, and that no `unique` test fails. | none | tiny | **Done 2026-11-16**, after the three runs. The whole-project `dbt build` gave `PASS=60 WARN=0 ERROR=0 SKIP=0` (I saw the last line of the output only). SQL checks in `SQL/01_star_checks.ipynb`: the fact has 13 runs and 1,053 rows (13 x 81), no duplicates and no run with a number of games other than 81. |

### C. Dagster (the scheduler): next

B3 and B4 have passed, so this is the next task. The detailed plan, in plain words, is in [doc 17](17_dagster_plan.md). Until the schedule is on, I start the run by hand.

| # | What | Files | Size | Status |
|---|---|---|---|---|
| C1 | Add a new dependency group `orchestration` with `dagster` and `dagster-webserver` to `pyproject.toml`, then `uv sync`. Check the current Dagster docs for versions when we do this step. | `pyproject.toml`, `uv.lock` | small | **Group added** (commit `c8d826a`). `pyproject.toml` has `dagster` and `dagster-webserver` in the group `orchestration` (read 2026-11-26). Not checked: `uv sync` and `uv run dagster --version`. |
| C2 | Create the Dagster definitions: one job (or one asset) that calls `run_steam_pipeline()` and `raise_on_failed_jobs()`, and one schedule with the cron `0 * * * *` (every hour on the hour), time zone `Europe/Stockholm`. | new file, for example `src/steam_data_platform/orchestration/definitions.py` | small | Not started |
| C3 | Make sure only **one run at a time** can happen, so a slow run never overlaps the next one. | Dagster config (`dagster.yaml`) | small | Not started |
| C4 | Pass the Snowflake settings to Dagster: start it with the same `.env` as the pipeline (`uv run --env-file .env dagster dev ...`). The private key file path is read from the environment by `connections.py`. | none, command only | tiny | Not started |
| C5 | Test: start Dagster, trigger the job by hand once from the web page, and check the new `load_id` has 81 rows in all tables. Only then turn the schedule on. | none | tiny | Not started |
| C6 | Remove the empty Airflow-style folders `orchestration/dags/.gitkeep` and `docker/.gitkeep` Dagster does not use them, and Docker is not part of Stage 2 (decided 2026-11-26). | those two files | tiny | Not started |

No dbt step is scheduled yet. The intermediate layer is views, so it is always fresh. The marts are tables, so after each ingestion run I run `dbt build` by hand. When Dagster comes, it also has to run `dbt build` after the ingestion ([doc 16](16_dbt_marts.md), section 9).

### D. Marts (done 2026-11-20)

All three marts are built and merged into `main`. The details are in [doc 16](16_dbt_marts.md).

| # | What | Status |
|---|---|---|
| D1 | `mart_game_detail`: what does "change since the previous run" compare with? | **Decided 2026-11-19: the previous run.** The same hour yesterday had no partner in any of the 1,053 rows (checked 2026-11-18). It can be added later as two more columns. |
| D2 | `mart_genre_comparison`: one row per genre per day, or per run? | **Decided 2026-11-20: per run.** It is the same grain as the other marts, no rule is needed to pick the latest run of a day, and the hour stays next to the player numbers. |
| D3 | `mart_portfolio_overview` | New mart, added on 2026-11-19 for the business areas 1, 4 and 5. Built on 2026-11-20. |

### E. Dashboard (later)

| # | What | Status |
|---|---|---|
| E1 | Time axis uses `snapshot_date` and `snapshot_hour_local`, or the timestamp `collected_at_utc` in Stockholm time. | Later |
| E2 | Build the dashboard on my PC first, then deploy it inside Snowflake (Streamlit in Snowflake), owned by `STEAM_REPORTER`. Details in [doc 17](17_dagster_plan.md), section 6.2. | Later, after Dagster |

## 5. Docs that must be updated

Only after the code step they describe is done. These docs say "once a day" or "Airflow".

| Doc | What to change |
|---|---|
| [05](05_games__dlt_ingestion.md), [06](06_reviews__dlt_ingestion.md), [07](07_player_counts__dlt_ingestion.md) | **Done 2026-11-16.** "How to run" now says once per hour at most, the one-run-per-day rules say one run every hour, and Airflow is now Dagster later. |
| [09](09_key_pair_login.md) | **Done 2026-11-16.** "Once an hour at most", and Airflow is now Dagster. The 2026-10-30 run is still called a daily run, because it was one. |
| [01](01_infra_setup.md) | **Done 2026-11-16.** Airflow in Docker is now Dagster, one run every hour. |
| `logical_model.dbml` and `assets/logical_model_1.png` | **Done.** The dbml and the png are both the new version (checked 2026-11-16 by looking at the picture): `dim_date` 7 columns, `dim_game` 14, `fact_game_snapshot` 19 with `snapshot_hour_local`, two links, no marts. Checked again on 2026-11-23: they still show the star only, on purpose. The three marts have their own files: `dbt_project/models/marts/marts.dbml` and `assets/marts.png` (three tables with 20 columns each, no links). |
| `_int_steam__models.yml` | **Done 2026-11-18.** I wrote on 2026-11-16 that the `dim_game` description was fixed and committed, but on 2026-11-18 the file still said "store info, platforms, lists". I removed the word "platforms" by hand on 2026-11-18. The whole-project `dbt build` on 2026-11-19 read the file with no error (`PASS=73 WARN=0 ERROR=0`). |
| [13](13_conceptual_model.md) and [14](14_dbt_intermediate.md) | **Done 2026-11-16.** Both now describe the one fact, the 14 columns of `dim_game`, `snapshot_hour_local`, 10 runs and the hourly plan. Doc 14 has a new section for `fact_game_snapshot`, so its later sections moved from 5, 6, 7 to 6, 7, 8. The caption of the picture in doc 13 is updated and the png is the new version. **Updated again 2026-11-16** after the three hourly rounds: both docs now say 13 runs, and that two runs in one day were tested. **Updated again 2026-11-20** for the three marts. |
| [16](16_dbt_marts.md) | **New 2026-11-19**, updated 2026-11-20 for all three marts: columns, tests, what was checked and the decisions. |
| [01](01_infra_setup.md), [13](13_conceptual_model.md), [16](16_dbt_marts.md), [17](17_dagster_plan.md) | **Done 2026-11-26.** Dagster is Stage 2 (not "later" or "the cloud, maybe Azure"). No Docker, Postgres or Airflow. The dashboard ends up inside Snowflake. |

## 6. Things to remember

| Topic | What to remember |
|---|---|
| **Dagster must be running** | A schedule only fires while the Dagster process (`dagster dev`) is running. If this PC is asleep or off, hours are skipped. Dagster runs on this PC (decided 2026-11-23, section 7). |
| **Missed hours are normal** | Gaps will happen. Charts must not draw a straight line over a gap as if it were a trend. Use markers. |
| **A failed run loads nothing** | If Steam answers 429 three times, the run stops before loading. There is no half run. That hour is simply missing. A single game that fails is skipped, so that run has fewer than 81 rows, and the 81-games test warns. |
| **A run takes about 21 to 23 minutes** | The run hour comes from the `games` timestamp, taken at the start of the run, so start the schedule on the hour (cron `0 * * * *`). The player counts come up to about 20 minutes later. |
| **What `snapshot_hour_local` means** | It is the Stockholm hour in which the run **started**. A dlt `load_id` is the Unix time of the start: `1794818498` is 08:41 UTC, which is 09:41 Stockholm, so the hour is 9 even though the run ended at 10:02. This is correct, not a one-hour delay (checked 2026-11-16). Start every run at the same minute. |
| **Clock change** | `snapshot_hour_local` repeats once when the clocks go back in autumn. Use `collected_at_utc` for ordering. |
| **Data grows 24 times faster** | About 2,000 rows per table per day (81 x 24). Fine for Snowflake. `achievements` has more rows per game. |
| **Steam limits are not official** | No official limit exists for the Store endpoints ([doc 05](05_games__dlt_ingestion.md)). Watch the logs for 429 in the first days. If any appear, slow down before anything else. |
| **Snowflake credits** | Each load wakes the warehouse. Check the credit balance after the first days. |

## 7. Open decisions

| # | Question | Options |
|---|---|---|
| 1 | Where does Dagster run? | **Decided 2026-11-23: on this PC with `dagster dev`, which stays on 24/7** (I talked to my teacher). No Azure, Docker or Postgres in Stage 2 (decided 2026-11-26). |
| 2 | Where does the Dagster code live? | Inside the package (`src/steam_data_platform/orchestration/`) or in the top-level `orchestration/` folder |
| 3 | Do we want a "freshness" check that warns when the newest run is more than 2 hours old? | Later, as a dbt source freshness check. Not part of the bare minimum. |
