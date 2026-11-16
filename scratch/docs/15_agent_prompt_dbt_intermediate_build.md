# Handoff prompt: build the intermediate layer (start at `int_steam__games_latest`)

> **Superseded on 2026-11-06 by `16_agent_prompt_dbt_game_run_and_fact.md`.** This file is the plan of 2026-11-05 and is kept for the history. Two things in it changed: (1) the single `fact_game_snapshot` became **three facts**, `fact_game_store`, `fact_game_reviews` and `fact_game_players`, after a tip from my teacher, and (2) `int_steam__game_run` was **dropped and never built**. `dim_game` also has 10 columns now, not the ones in doc 13 of that day. The star is built (`PASS=74 WARN=0 ERROR=0`). Read `docs/13_conceptual_model.md` and `docs/14_dbt_intermediate.md` for the truth.

Written 2026-11-05, at the end of the planning session. All design decisions for the intermediate layer and the marts are made and written down. **No intermediate SQL exists yet.** Your job tomorrow is to build the models, one at a time, and teach me while you do it. This file replaces `13_agent_prompt_dbt_intermediate.md` as the starting point. Files 11, 12 and 13 still hold useful background (see "Read first").

## 0. How to work with me (short version)

I am a **beginner data engineer**. I paste all code into files myself and I run **every** command and **all** git in my own terminal. You write and explain.

1. **One small thing per message**, under about 20 lines. Say where we are in one line at the top ("Step 2 of 6, ...") and what success looks like ("you should see `PASS=... ERROR=0`").
2. **Teach with an everyday comparison, then the term.** At most one new term per message. Staging was "a washing machine". Intermediate is "a kitchen where the washed ingredients are cut and combined" (this picture is already used, keep it). **When I say "you lost me", go one level simpler, use a new picture, say plainly what the code does and what it does not do, and ask one short question.**
3. **One recommendation, not a menu.** Only ask "A or B" when it truly blocks the work. **Do not reopen decisions in section 2.**
4. **Plan first, then wait for my OK**, then the file. The order that worked in staging: plan table -> SQL file -> YAML tests with comments -> `dbt build` -> I look at the data in Snowsight -> commit. One model at a time.
5. **Put comments in code and YAML** (`--` and `#`) that say *why*, not only *what*. Copy the style of `dbt_project/models/staging/` (header comment, `with ... as (...)` blocks, `data_tests:`, `arguments:` nesting, a comment on every test, `severity: warn` where a problem should not stop the build).
6. **Show code in chat, I paste it.** Give each command in its own fenced `bash` block. You may edit markdown in `docs/` and `scratch/docs/`. **Do not edit SQL, YAML, the dbml or any code file; ask me first.** Read-only tools (Read, Grep, Glob) are fine.
7. **Never open `.env`, `.dlt/secrets.toml` or key files.** `dbt debug` prints the Snowflake **account name**: tell me to replace the `account:` value with `xxx` before pasting output, and never repeat it.
8. **Be honest.** Say what is verified and what is not. **Check git state with me; do not trust this file for it.** Check numbers (test counts, row counts) before they go into a commit message or a doc. If I give a result from memory, say in the doc that you did not see it.
9. **After I paste code into a file, check that it is really saved** with Grep (in staging a YAML block was once never saved and the build ran with no tests). Look at the `Found N models, M data tests` line of the build. **Predict the expected count before the build** and call it "my count, not a result".
10. **Stay close to the reference repos** (Flight `indiramahadiva/Flight-punctuality_4_DE25`, my lecture repo `Akina-Aoki/AiraTheSnowFairy`). For intermediate there is **no direct model to copy**: the Flight repo has no middle layer, and the lecture repo puts `dim/` and `fct/` as tables in a `warehouse` schema. Say so, and follow doc 13.
11. **Never use DuckDB** in this project (dlt loads straight to Snowflake).
12. PR text: first person, short sentences, no buzzwords, no "This PR ...". Draft it for me each time. End it with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Commit style `feat(dbt): ...`, double quotes only, no quotes inside. **End each commit message with a second `-m "Co-Authored-By: ..."` line (the attribution the app gives you); I sometimes drop it, remind me.**
13. Do not run the full dlt pipeline. `append` adds rows on every run. I run it by hand, once a day at most.

## 1. Read first (in this order, then tell me in three short sentences where we are)

1. **`docs/13_conceptual_model.md`**: read **all of it**. Section 9 holds every decision, section 6.4 the columns of each table, section 8 the traps. **Where any other file disagrees with it, doc 13 wins.**
2. `docs/10_dbt_sources_staging.md`: the staging models, their tests and the findings.
3. `scratch/docs/11_agent_prompt_dbt_start.md` sections 0 to 1 (rules and the project) and `scratch/docs/12_agent_prompt_dbt_staging.md` section 0 (how to talk to me).
4. `scratch/docs/13_agent_prompt_dbt_intermediate.md` sections 2 and 4: the **columns** of each staging model, and what my notebooks proposed. Note it was patched on 2026-11-05, but this file (15) is newer.
5. `dbt_project/models/staging/` (the five `.sql` files and `_steam__models.yml`): copy their style. `dbt_project/dbt_project.yml`, `dbt_project/models/intermediate/logical_model.dbml` (the logical model, typed by me on dbdiagram.io).
6. `snowflake_setup/03_schemas.sql` and `04_grants.sql` (read only, do not change).

Then check git **with me, one command at a time**: `git branch`, `git status`, `git log --oneline -3`.

## 2. Decisions already made (do not reopen). All are in doc 13 section 9.

| Topic | Decision |
|---|---|
| Layers | `intermediate` is a **view** in schema `INTERMEDIATE` (already set in `dbt_project.yml`). `marts` are tables in `MARTS`. Staging stays views. |
| Where the star lives | (Changed 2026-11-06: the three facts `fact_game_store`, `fact_game_reviews`, `fact_game_players`, plus) `dim_game` and `dim_date` are built in **`INTERMEDIATE`, as views, no exception** (following the project proposal). Revisit "table" only if Streamlit feels slow. |
| Star schema | Strict star: every dimension connects directly to the fact. |
| Grain | **One row per game per run**, joined on **`steam_appid` + `load_id`** (not on the date). A second run on one day is a second row. A `unique` test on (`steam_appid`, `load_id`) guards it. |
| Fact stores | Counts, not percentages. Percentages and "change since the previous run" (`LAG`) are worked out in the marts. |
| Genre | Stays a list on `dim_game` (plus `genres_text`). It is split in `mart_genre_comparison`, not in a bridge table. The genre share is **all positive ÷ all reviews**, never an average of percentages. A game with 3 genres counts in 3 genre rows, never add genres into a portfolio total. |
| Achievements | Out of the star for now (area 8 is optional). |
| Franchise | **Dropped** from the whole project. No column, no seed. |
| Minimums | **None.** The dashboard shows one game at a time, with the review count next to the percent, and no ranking by percent positive. |
| Streamlit access | Streamlit reads **`MARTS` only**, through `mart_game_detail` (one row per game per run, for the game page) plus `mart_genre_comparison`. **No grant change** (`STEAM_REPORTER` already reads all of `MARTS`). |
| Naming | `int_steam__<name>.sql` for prep models, `fact_...` / `dim_...` for the star, in `models/intermediate/` (no per-source subfolder). Descriptions and tests in a `_int_steam__models.yml` file (same style as `_steam__models.yml`). |
| Staging stays 1:1 | Joins, "latest row per game" and similar belong in intermediate. |
| NULL vs 0 | Never `coalesce(player_count, 0)`. A missing price is never 0. No achievement rows is not 0 %. |
| Unreleased | Use `coming_soon` from `games`. Never use `result = 42` or zero reviews to mean "unreleased". |
| English-only reviews | `review_summary` before 2026-11-02 counts English only. Use `counts_all_languages` in every trend and change calculation. |
| Raw stays raw | No change to raw tables. |
| Orchestration | None. I run dlt and dbt by hand. |

## 3. Where we are (verified at the end of 2026-11-05, check again with me)

- Branch **`feat/dbt-intermediate`**, one commit of its own on top of `main`: `87a692d` ("refactor/planning intermediate layer and conceptual + logical models"). Staging is merged (PRs #11, #12, #14): 5 views, 37 tests, `PASS=42 WARN=0 ERROR=0` on 2026-11-02.
- **Not committed:** edits to `docs/02`, `04`, `06`, `07`, `10`, `11`, `13`, `assets/logical_model_1.png` and `logical_model.dbml` (all from the planning session). A good first small task is to **review and commit these together** as a docs commit. Do not commit it for me, give me the commands.
- **Untracked files in `scratch/` are on purpose out of git.** Do not commit or delete them (this file is one of them).
- `dbt_project/models/intermediate/` holds only `logical_model.dbml`. **No intermediate SQL exists.**
- Not run-verified: that `STEAM_TRANSFORMER` can create views in `INTERMEDIATE` (it owns the schema according to `03_schemas.sql`). The first build will show it. A grant change is a Snowflake change: ask me first.

**How I run dbt** (from `dbt_project/`, Git Bash, virtual environment active):

```bash
set -a; source ../.env; set +a
dbt build
```

The first line loads my Snowflake settings once per terminal. To build one model add `--select <name>`. Packages: `dbt_utils` 1.4.1. Two "unused configuration paths" warnings (`intermediate`, `marts`) should disappear once the first model exists in `intermediate/`.

## 4. The task: build the star, one model at a time

Do them in this order. Each one follows the loop in section 0, rule 4. Ask me for the OK on each plan table.

| # | Model | One row is | Purpose |
|---|---|---|---|
| 1 | `int_steam__games_latest` | one game (81 rows) | Newest row per game. The base of `dim_game`. |
| 2 | `dim_date` | one Stockholm day | Built by dbt, not read from Steam. Columns in doc 13 section 6.4. Probably `dbt_utils.date_spine` (check its docs, do not guess the arguments). The start date is 2026-10-23 (first run). |
| 3 | `dim_game` | one game | From `int_steam__games_latest`. Columns in doc 13 section 6.4 and in the dbml. `release_year` and `genres_text` are worked out here. Lists stay lists. |
| 4 | ~~`int_steam__game_run`~~ **dropped, never built** (2026-11-06) | one game per run | The four staging models (`games`, `review_summary`, `review_recent`, `player_counts`) joined on `steam_appid` + `load_id`, **left join from `games`** so early runs stay and missing values stay NULL. |
| 5 | ~~`fact_game_snapshot`~~ **split into `fact_game_store`, `fact_game_reviews` and `fact_game_players`** (2026-11-06) | one game per run | Columns in doc 13 section 6.4. A `relationships` test to `dim_game` and `dim_date`, and a `unique` test on (`steam_appid`, `load_id`). |
| 6 | Extra checks | | See section 5. |

Marts (`mart_game_detail`, `mart_genre_comparison`) come **after** the star, on a separate branch (`feat/dbt-marts`). Do not start them unless I ask.

### The plan for model 1 (already drafted with me, I had not answered yet)

| | Plan |
|---|---|
| File | `dbt_project/models/intermediate/int_steam__games_latest.sql` (a view, no config needed) |
| Reads | `ref('stg_steam__games')` |
| One row is | One game (81 rows) |
| Logic | Number each game's rows newest first (`row_number()` over `partition by steam_appid order by collected_at_utc desc, load_id desc`) and keep number 1. Snowflake has `qualify`, or use a CTE (the CTE is easier to read for a beginner). |
| Columns | All columns of `stg_steam__games`, unchanged |
| Unreleased games | Kept (`coming_soon` tells them apart) |
| Tests | `steam_appid` unique and not null, in `_int_steam__models.yml`, with a comment on each |

The picture I like: "a pile of receipts for each game, one per run; keep only the newest receipt of each game". The new term: "latest row per game".

Honest limit to tell me: if a game is missing from the newest run (for example one request failed), its "latest" row comes from an older run. That is fine for a description (`dim_game`) and is why the fact uses the per-run grain.

**Expected test count for model 1:** 2 tests (unique, not_null) on the new model. After the build of the whole project the line should say about `Found 6 models, 39 data tests` (5 staging models and 37 tests, plus the new model and its 2 tests). That is my count, not a result.

## 5. Things still open or not checked (do not start unless I ask, or they block the model)

- **Completeness test**: a run should have exactly 81 games, `severity: warn`. Catches a partial load. (Built on 2026-11-06 as `dbt_project/tests/assert_81_games_per_run.sql`, it counts the rows of each run in the three facts.)
- **Recent never above all-time**: a `warn` test that returns rows where `recent_total > total_reviews` for the same run, only with `counts_all_languages = true` (notebook 04 returned none on 2026-11-02). Needs the join of `review_recent` and `review_summary`, so it belongs here.
- **`has_achievements`** from our own `achievements` rows (7 games disagree with the store category). It is not in the star. Ask me before building it.
- **Unpacked lists** (`int_steam__game_genres`, `_categories`, `_developers`, `_publishers`) from my older notes are **probably not needed**: doc 13 keeps the lists on `dim_game` and splits genres in the mart. Do not build them without asking me.
- `metacritic_score` may change between runs: not checked. If it does, it moves from `dim_game` to the fact.
- Whether to include free games in price averages: decide in the marts.
- A failed run (a `load_id` missing in one table) and two runs in one day: **not tested**.
- Snowflake: key-pair login for `DBT_USER` (it uses a password now), `DLT_USER` still has a password, `STREAMLIT_USER` login is decided when Streamlit is built.
- Ingestion open items (`result` 42 meaning, two games without a price `73020` and `349790`, the Free Edition with no reviews, one fixed run hour): not part of this task.
- The notebooks are behind the data. **Do not edit notebooks without asking.**
- `docs/03` and `docs/04` still say "password and MFA" for `DBT_USER`: a small doc fix, only when I say so.

## 6. After each model

1. I run `dbt build --select <model>` and paste the result (account name replaced by `xxx`).
2. I check the data in Snowsight (give me a small read-only query with the **full path** `STEAM_DB.INTERMEDIATE.<MODEL>`, in capitals).
3. We write the model into a **new doc** `docs/14_dbt_intermediate.md` (decisions, findings, test table, how to run), as we did in `docs/10_dbt_sources_staging.md`. One doc for the whole intermediate layer, extended after each model. Update `docs/13_conceptual_model.md` only where a plan changes.
4. I commit and open the PR when the layer is done (or earlier, if I say so). Draft the commit text and PR text for me.

## 7. Please begin by

1. Reading the files in section 1.
2. Checking git with me, one command at a time (`git branch`, `git status`, `git log --oneline -3`). Confirm I am on `feat/dbt-intermediate`.
3. Telling me in **three short sentences** where we are.
4. Giving me **one** thing to do. My suggestion: first the small docs commit (section 3), then the plan table for `int_steam__games_latest` and wait for my OK.
