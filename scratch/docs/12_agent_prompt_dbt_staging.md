# Handoff prompt: dbt staging for the two new tables, `review_recent` and `achievements`

Written 2026-11-02, at the end of the ingestion session for the two new resources. This file replaces the older version of file 12 (it was about `stg_steam__games`, which is done and merged). Read this whole file before you do anything. For the long rules, read `scratch/docs/11_agent_prompt_dbt_start.md` (sections 0 to 1) too.

## 0. How to work with me (I got lost before, so go slowly)

1. **One small thing per message,** under about 20 lines. Say where we are in one line at the top ("Step 3 of 8, ...") and what success looks like ("you should see `PASS=... ERROR=0`").
2. **Teach with an everyday comparison, then the real term.** Staging was "a washing machine" (changes the form, not the meaning). At most one new term per message.
3. **One recommendation, not a menu.** Only ask "A or B" when it truly blocks the work. Ask one question at a time.
4. **Do not reopen decisions in section 4.** If I say "OK" or "Next", move on. If I answer with a fragment, assume "continue from where we were".
5. **Plan first, then wait for my OK,** then the file. Order that worked: plan table -> SQL file -> YAML tests with comments -> `dbt build` -> I look at the data in Snowsight -> commit. **One model at a time.**
6. **Put comments in code and YAML** so a beginner can read them. Use `--` and `#` comments that say why, not only what.
7. **Show code in chat, I paste it.** I run all commands and all git. Give each command in its own fenced `bash` block (one command per block). You may edit markdown in `docs/` and `scratch/docs/` when I say so. **Nothing else without asking.** In the ingestion session I allowed code edits for that task only. That does not carry over.
8. **Never open `.env`, `.dlt/secrets.toml` or key files.** `dbt debug` prints the Snowflake **account name**. Tell me to replace the `account:` value with `xxx` before pasting, and never repeat it.
9. **Be honest.** Say what is verified and what is not. **Check git state with me; do not trust this file for it.** Check numbers (file counts, test counts) before you put them in a commit message.
10. **No DuckDB. No API key.** I do not run the full dlt pipeline (it adds rows on every run, and it takes about 21 minutes). I run it by hand, once a day at most.
11. **Stay close to the two reference repos** (Flight-punctuality `indiramahadiva/Flight-punctuality_4_DE25` and my lecture repo `Akina-Aoki/AiraTheSnowFairy`). Change something only when needed, and ask me first.
12. **Commits and PR text.** Commit style `feat(dbt): ...`. I run git. End each commit with a second `-m` for the attribution line the app gives you (I sometimes drop it, remind me). Use double quotes only, with no quotes inside, because a quote inside a quote made my last commit hang. PR text: first person, short sentences, no buzzwords, no "This PR ...", ending with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. You draft it, I post it.

## 1. Where we are

**Done and merged earlier:** sources and three staging views (`stg_steam__games`, `stg_steam__review_summary`, `stg_steam__player_counts`), 20 tests, `dbt build`: `PASS=23 WARN=0 ERROR=0` on 2026-11-02 (PRs #11 and #12, `main` at `d5a98da` when I last looked). Doc: `docs/10_dbt_sources_staging.md`.

**Done in the ingestion session of 2026-11-02, on branch `feat/ingest-recent-reviews-achievements`:**

| Item | Result |
|---|---|
| Two new dlt resources | `review_recent` and `achievements`, in `src/steam_data_platform/ingestion/steam.py`. 71 tests pass. |
| One full run on 2026-11-02 | 486 requests, 13:14 to 13:35 Stockholm, no 429. Load id `1793621677.9089065`. |
| New raw tables in `STEAM_DB.STEAM_RAW` | `REVIEW_RECENT` (81 rows) and `ACHIEVEMENTS` (3,966 rows from 49 games). The other three tables got 81 new rows each. |
| A bug fixed | `review_summary` counted **English reviews only** before 2026-11-02 (the option was `language`, Steam wants `languages`). Rows before that day stay English only. |
| Docs and notebooks | `docs/11_review_recent__dlt_ingestion.md`, `docs/12_achievements__dlt_ingestion.md`, `notebooks/04_eda_review_recent.ipynb`, `notebooks/05_eda_achievements.ipynb`. Docs 05, 06, 07, 08 and 10 were updated. |

**The ingestion PR is merged** (PR #13, `main` at `51f76eb`). I switched to **`feat/dbt-staging`** and merged `main` into it, so the branch is at `51f76eb` and has `docs/11`, `docs/12`, notebooks 04 and 05 and the new `steam.py`. `feat/dbt-staging` was used before (PRs #11 and #12), so it has no commits of its own now. Still check git with me first (section 7, step 1), because I do not want you to trust this file for it.

## 2. What the staging layer looks like now (copy this style)

Read these first: `dbt_project/models/staging/stg_steam__review_summary.sql`, `stg_steam__player_counts.sql`, `_steam__models.yml`, `_steam__sources.yml`, `docs/10_dbt_sources_staging.md`.

| Topic | How it is done |
|---|---|
| Files | All in `models/staging/`, no per-source subfolder. `stg_steam__<table>.sql`, tests and descriptions in `_steam__models.yml`, sources in `_steam__sources.yml` (source `steam`, schema `steam_raw`, tables `games`, `review_summary`, `player_counts`, no tests, no freshness). |
| SQL shape | Header comments `-- Model: ...` and `-- Layer: STAGING`. A CTE `source` (`select * from {{ source('steam', '<table>') }}`), then `renamed_staging`, then `select * from renamed_staging`. |
| Columns every model has | `steam_appid`, `_dlt_load_id as load_id`, `convert_timezone('UTC', collected_at)::timestamp_ntz as collected_at_utc`, `convert_timezone('Europe/Stockholm', collected_at)::date as collected_date` |
| Rule | One row in = one row out. Clean the form (units, types, time zones). **No joins, no business rules.** |
| Tests | `data_tests:` with `arguments:` nesting, `dbt_utils.unique_combination_of_columns` on (`steam_appid`, `load_id`), `not_null`, `relationships` to `stg_steam__games`, `severity: warn` for checks that should warn and not fail. Comments on every test. |
| Materialization | Views in schema `STAGING` (from `dbt_project.yml`). Models land in the real `STAGING` schema (`DBT_SCHEMA=staging`, our `generate_schema_name`). |
| Macro | `macros/decode_html_entities.sql` (used by `stg_steam__games` only) |
| Packages | `dbt_utils` 1.4.1 |
| Login | `DBT_USER` with a password (`HAS_MFA` false). Role `STEAM_TRANSFORMER`. |
| How I run dbt | From `dbt_project/` in Git Bash with the virtual environment active: `set -a; source ../.env; set +a`, then `dbt build`. The long form `uv run --env-file ../.env dbt build` also works. To build one model: `--select <name>`. |

## 3. The two new raw tables (facts, from the ingestion session)

Read `docs/11_review_recent__dlt_ingestion.md`, `docs/12_achievements__dlt_ingestion.md` and section 10 of notebooks 04 and 05 (they have proposals). Short version:

**`STEAM_RAW.REVIEW_RECENT`** (one row per game per run, `append`):

| Column | Type | Meaning |
|---|---|---|
| `steam_appid` | `NUMBER(19,0)` | The game |
| `collected_at` | `TIMESTAMP_LTZ(9)` | One time for the whole run |
| `day_range` | `NUMBER(19,0)` | The window in days, always 30 so far |
| `recent_positive`, `recent_negative` | `NUMBER(19,0)` | Reviews in the last 30 days. A real 0 stays 0. All languages. |
| `_dlt_load_id`, `_dlt_id` | `VARCHAR` | Added by dlt |

Facts: 81 rows, 81 games, no duplicates. 5 games have 0 and 0 (the 4 unreleased games and *Knights of Pen and Paper 2: Free Edition*). Only 11 games have 100 or more recent reviews, 36 have 1 to 9. The total is **not stored** (it is positive + negative).

**`STEAM_RAW.ACHIEVEMENTS`** (one row per game and achievement per run, `append`):

| Column | Type | Meaning |
|---|---|---|
| `steam_appid` | `NUMBER(19,0)` | The game |
| `collected_at` | `TIMESTAMP_LTZ(9)` | One time for the whole run |
| `achievement_name` | `VARCHAR` | Steam's code, for example `achievement_economy_1`. Not a readable title. |
| `percent` | `VARCHAR` | Share of players who unlocked it, **as text** (for example `40.9`) |
| `_dlt_load_id`, `_dlt_id` | `VARCHAR` | Added by dlt |

Facts: 3,966 rows from 49 games. No duplicates for (game, achievement, load). All 3,966 percents parse as numbers (`try_to_double`), between 0.0 and 100.0. Only 3,925 different names: **41 names are used by more than one game**, so the name alone is not unique. 32 of 81 games have **no rows** (4 unreleased and 28 released games from 2008 to 2013). That means "no data", never 0 %. Steam has a typo in one name (`achieviement_conquer_homeworld`), so do not clean names in staging.

## 4. Decisions already made (do not reopen)

| Topic | Decision |
|---|---|
| Staging rule | One row in = one row out. No joins, no business rules. |
| Names and files | Flight style, as in section 2. Descriptions and tests in `_steam__models.yml`. |
| NULL and zero | Never `coalesce(..., 0)`. A missing value is not 0. No achievement rows is not 0 %. |
| Raw stays raw | The raw tables are not changed. |
| Recent total | Not stored in raw. dbt adds it. |
| Achievement percent | Kept as text in raw. dbt adds a number next to it and keeps the text. |
| Orchestration | None. I run dlt and dbt by hand. |
| Intermediate layer | Paused on purpose. It comes after this branch. Do not start it. |

## 5. Proposals (NOT decided: present your own plan and wait for my OK)

These come from section 10 of notebooks 04 and 05. Names are suggestions.

**Sources file:** add `review_recent` and `achievements` with short descriptions (no tests, no freshness, like the others).

**`stg_steam__review_recent`:**

| Column | What staging does |
|---|---|
| `steam_appid`, `load_id`, `collected_at_utc`, `collected_date` | As in the other models |
| `day_range`, `recent_positive`, `recent_negative` | Keep |
| `recent_total` | `recent_positive + recent_negative` |
| `has_recent_reviews` | `recent_total > 0` |
| `pct_positive_recent` | `round(100 * recent_positive / nullif(recent_total, 0), 1)`, NULL when the total is 0 |

Tests to consider: `unique_combination_of_columns` on (`steam_appid`, `load_id`); `not_null` on `steam_appid`, `load_id`, `collected_at_utc`, `day_range`, `recent_positive`, `recent_negative`; `relationships` to `stg_steam__games`; `accepted_values` on `day_range` = 30 with `severity: warn`. The check "recent is never above all-time" needs a join, so it belongs in the **intermediate** layer, not here.

**`stg_steam__achievements`:**

| Column | What staging does |
|---|---|
| `steam_appid`, `load_id`, `collected_at_utc`, `collected_date` | As in the other models |
| `achievement_name` | Keep exactly as it is |
| `percent` | Keep the text |
| `percent_unlocked` | `try_to_double(percent)`, a number |

Tests to consider: `unique_combination_of_columns` on (`steam_appid`, `achievement_name`, `load_id`); `not_null` on those plus `percent_unlocked` (it catches a value that is not a number); `dbt_utils.accepted_range` on `percent_unlocked` from 0 to 100; `relationships` to `stg_steam__games`.

**A change to an existing model (ask me first, it touches a merged model):** `stg_steam__review_summary` should get a flag such as `counts_all_languages`, true from the load of 2026-11-02, because earlier rows are English only. The open question is how to set the date: hard-coded in the SQL with a comment, or a `var` in `dbt_project.yml`. Give me one recommendation. The `relationships` and other tests of that model must still pass.

## 6. Open items you should know about (do not start them unless I ask)

- **Seven achievement games disagree with the store category** `Steam Achievements`. Checked: the 2 with the category but no rows (*Afterworld*, *Prison Architect 2*) are unreleased, so no data was lost. The 5 with rows but no category are released (*A Game of Dwarves*, *Crusader Kings II*, *FOUNDRY*, *Star Trek: Infinite*, *Sword of the Stars II: Enhanced Edition*), and we do not know why the category is missing. So the intermediate flag `has_achievements` later should come from our own rows, not from the category. This does not block staging.
- **Minimum number of recent reviews** for a percent, and the minimum for players: decided on 2026-11-05, none needed (the dashboard shows one game at a time). See `docs/13_conceptual_model.md`, section 9.
- **Rule for repeated runs on the same day:** decided on 2026-11-05. The grain is one row per game per run, joined on `steam_appid` + `load_id` (see `docs/13_conceptual_model.md`, section 1).
- **Why Europa Universalis IV and Prison Architect fell so far in the last 30 days:** unknown. Needs news or patch dates. Not part of this task.
- **What `result` 42 means** (player counts): still unverified.
- **Notebook text for notebooks 01 to 03 is behind the data.** Do not edit notebooks without asking.
- `docs/03` and `docs/04` still say "password and MFA" for `DBT_USER`. I allowed editing docs, but only when you write the dbt doc.

## 7. Plan (present your version to me and wait for my OK)

| Step | What | Who |
|---|---|---|
| 1 | Check `git branch`, `git status`, `git log --oneline -5`. The top of the log should be the merge of PR #13 (`51f76eb`). | me |
| 2 | Check that `STEAM_TRANSFORMER` can read the new tables, and look at the data. In Snowsight, role `STEAM_TRANSFORMER`: `SELECT COUNT(*) FROM STEAM_DB.STEAM_RAW.REVIEW_RECENT;` (expect 81) and `... .ACHIEVEMENTS;` (expect 3966). `snowflake_setup/04_grants.sql` has `FUTURE TABLES` grants, so it should work, but it is not verified. If it fails with "insufficient privileges", stop. A grant change is a Snowflake change, so ask me first. | I run, you read |
| 3 | Update `_steam__sources.yml` with the two tables. Check with `dbt parse`. | you show, I paste |
| 4 | `stg_steam__review_recent.sql`, then its part of `_steam__models.yml`, then `dbt build --select stg_steam__review_recent`, then I look at the data in Snowsight. | |
| 5 | The same for `stg_steam__achievements`. | |
| 6 | The language flag in `stg_steam__review_summary` (only if I agree in section 5). Run the whole `dbt build`. | |
| 7 | Update `docs/10_dbt_sources_staging.md` (sources, models, tests, findings, what is done). I allow editing that file. Check the test count before you write it. | |
| 8 | Commit messages, PR text, I run git. | me |

## 8. Please begin by

1. Reading this file, `scratch/docs/11_agent_prompt_dbt_start.md` (sections 0 and 1), `docs/10_dbt_sources_staging.md`, and the files listed at the top of section 2.
2. Checking `git branch` with me, then `git status` and `git log --oneline -5`, one command at a time.
3. Telling me in **three short sentences** where we are.
4. Giving me **one** thing to do. Then wait.
