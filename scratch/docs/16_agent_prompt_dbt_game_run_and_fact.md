# Handoff prompt: the star is built (two dimensions, three facts). Next: look at the data, commit, open the PR, then the marts

First written 2026-11-06 for building `int_steam__game_run` and one `fact_game_snapshot`. **Rewritten later on 2026-11-06**, after the plan changed: on my teacher's tip the single fact became **three facts**, `dim_game` was cut to 10 columns, and `int_steam__game_run` was **dropped and never built**. The file name still says `game_run_and_fact`, but the content is the new state. This file replaces `15_agent_prompt_dbt_intermediate_build.md` as the starting point.

## 0. How to work with me (short version)

I am a **beginner data engineer**. I paste all code into files myself and I run **every** command and **all** git in my own terminal. You write and explain. Treat me as your mentee.

1. **One small thing per message**, under about 20 lines (code blocks excepted). Say where we are in one line at the top ("Step 2 of 5, ...") and what success looks like ("you should see `PASS=3 WARN=0 ERROR=0`").
2. **Teach with an everyday comparison, then the term.** At most one new term per message. Used so far: staging is "a washing machine", intermediate is "a kitchen where the washed ingredients are cut and combined", the star is "a contact list of games and a contact list of days, plus a call log that points to both", the three facts are "three cash registers (store, reviews, players) that use the same two address books (the game list and the calendar)". The `load_id` is "the tray number of a run".
3. **When I say "you lost me", "wait" or "I don't get it": stop, go one level simpler, use a NEW picture, say plainly what the code does and what it does not do, and ask one short question.** **Do not change a plan again and again.** Think it through once, give **one recommendation**, say why, and keep it. Only ask "A or B" when it truly blocks the work. **Do not reopen decisions in section 3.**
4. **I prefer the simplest thing that is also correct, close to my old repos.** I dropped `dbt_utils.date_spine` for `dim_date` because it needed an end date and my old repos never used it. Before you suggest a macro, a package, a Jinja trick or a compile-time query, ask yourself if plain SQL does the same. Say when something is **your idea and not copied** from a reference repo.
5. **Plan first, then wait for my OK**, then the file. The order that worked: plan table -> SQL file -> YAML tests with comments -> `dbt build --select <model>` -> I look at the data in Snowsight (read-only query) -> write it into `docs/14_dbt_intermediate.md` -> commit. One model at a time.
6. **Put comments in code and YAML** (`--` and `#`) that say *why*, not only *what*. Copy the style of `dbt_project/models/staging/` and `dbt_project/models/intermediate/` (header comment, `with ... as (...)` blocks, `data_tests:`, `arguments:` nesting, a comment on every test, `severity: warn` where a problem should not stop the build). Do not put a `--` comment inside `{{ ... }}`: it breaks the Jinja.
7. **Show code in chat, I paste it.** Give each command in its own fenced `bash` block (SQL for Snowsight in a `sql` block). You may edit markdown in `docs/` and `scratch/docs/` when I ask. **Do not edit SQL, YAML, the dbml or any code file; ask me first.** Read-only tools (Read, Grep, Glob, read-only git) are fine.
8. **Give a whole-file replacement, not "replace lines 33 to 38".** On 2026-11-06 I pasted a YAML block over the wrong lines. The build still passed, and only the test count (41 instead of 43) showed it. So for YAML and the dbml give the full file, or tell me to add a block at the very end of the file.
9. **After I paste code into a file, read the WHOLE file back** (not only a Grep for a few words) and compare names and columns. On 2026-11-06 `dim_game.sql` still had `categories` after I said I pasted the new version, and the build passed. Look at the `Found N models, M data tests` line of the build. **Predict the expected count before the build, with the arithmetic**, and call it "my count, not a result".
10. **Be honest.** Say what is verified and what is not. **Check git state yourself with read-only git and with me; do not trust this file for it.** Check numbers before they go into a doc or a commit message. If I give a result from memory, say in the doc that you did not see it. I often send **screenshots of Snowsight results and CSV exports** (usually in `C:\Users\adelo\...\Downloads`): read them with the Read tool and say that the numbers come from them. If I paste only the last line of a build, say that you saw only that line.
11. **Never open `.env`, `.dlt/secrets.toml` or key files.** `dbt debug` prints the Snowflake **account name**: tell me to replace the `account:` value with `xxx` before pasting output, and never repeat it.
12. **Stay close to the reference repos** (Flight `indiramahadiva/Flight-punctuality_4_DE25`, my lecture repo `Akina-Aoki/AiraTheSnowFairy`). For this layer there is **no direct model to copy**: the Flight repo has no middle layer, and the lecture repo puts `dim/` and `fct/` as tables in a `warehouse` schema. I have **not verified** how the lecture repo builds a fact table or its joins: ask me if it matters.
13. **Never use DuckDB** in this project (dlt loads straight to Snowflake). Do not run the full dlt pipeline: `append` adds rows on every run. I run it by hand.
14. **Commits and PR text.** Commit style `feat(dbt): ...`, double quotes only, no quotes inside. **Every commit gets a body and a trailer.** The body says why, what is new, which decisions, what was checked (see the example in section 6). End with a second or third `-m "Co-Authored-By: ..."` line (the attribution the app gives you). **I dropped that trailer on the commits `3bd5688` and `745c8b3`, so remind me every time.** Those commits are already pushed: do **not** suggest rewriting pushed history. PR text: first person, short sentences, no buzzwords, no "This PR ...". Draft it for me each time. End it with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
15. Full names in Snowsight queries: `STEAM_DB.STAGING.STG_STEAM__GAMES`, `STEAM_DB.INTERMEDIATE.DIM_GAME` (capitals). Read-only queries only, I run them.

## 1. Read first (in this order, then tell me in three short sentences where we are)

**A. The docs in `docs/`: what we have built.** Read these, they are the truth about what exists:

1. `docs/13_conceptual_model.md`: read **all of it**. Grain (section 1), the star and the three facts (section 4), entities, the logical model and the columns of each table (section 6.4), the traps (section 8), the decisions (section 9). **Where any prompt file disagrees with it, doc 13 wins.** Note: I have an uncommitted edit in area 8 (see section 5).
2. `docs/14_dbt_intermediate.md`: **all of it, it is the newest.** The six models, the findings, the tests, the validation, the decisions, how to run, and what is not done. This is the file you extend.
3. `docs/10_dbt_sources_staging.md`: the five staging models, their tests, the language flag, the findings.
4. Ingestion docs: `docs/05_games__dlt_ingestion.md`, `06_reviews__dlt_ingestion.md`, `07_player_counts__dlt_ingestion.md`, `11_review_recent__dlt_ingestion.md`, `12_achievements__dlt_ingestion.md`, and `08_steam_py_code_guide.md`. What each raw table holds, what `result = 42` and the English-only reviews mean, how a run works.
5. Setup docs, skim: `01_infra_setup.md`, `02_snowflake_setup.md`, `03_snowflake_users_dbt_initialization.md`, `04_dbt_foundation.md`, `09_key_pair_login.md`. Roles, schemas, grants (`STEAM_TRANSFORMER`, `STEAM_REPORTER`), how dbt connects. Docs 03 and 04 still say "password and MFA" for `DBT_USER`, which is out of date.

**B. The earlier agent prompts in `scratch/docs/`: how we worked and what was decided.** They are **untracked on purpose, out of git**. Do not commit or delete them (this file is one of them). Read them for the working rules, the decisions and the open items, especially the **ingestion**, **staging** and **intermediate** ones:

| Part | Files |
|---|---|
| Ingestion | `05_steam_api_plan.md`, `06_dlt_ingestion_plan.md`, `07_agent_prompt_dlt_games.md`, `08_agent_prompt_dlt_review.md`, `09_agent_prompt_dlt_player_counts.md`, `10_agent_prompt_ingestion_wrapup.md`, `14_agent_prompt_ingestion_recent_reviews_achievements.md` |
| Staging | `11_agent_prompt_dbt_start.md` (sections 0 and 1: rules and the project), `12_agent_prompt_dbt_staging.md` (section 0: how to talk to me, and the staging decisions) |
| Intermediate | `13_agent_prompt_dbt_intermediate.md` and `15_agent_prompt_dbt_intermediate_build.md` (older plans with a banner at the top: they still describe one fact and `int_steam__game_run`, which no longer exist) |

The prompts are older than the docs. **Docs 13 and 14 win** where they differ. Do not re-do work the prompts say is done.

**C. The code (read-only):**

- `dbt_project/models/staging/`: the five `.sql` files and `_steam__models.yml` (copy the style).
- `dbt_project/models/intermediate/`: `int_steam__games_latest.sql`, `dim_date.sql`, `dim_game.sql`, `fact_game_store.sql`, `fact_game_reviews.sql`, `fact_game_players.sql`, `_int_steam__models.yml`, `logical_model.dbml` (the logical model, typed by me on dbdiagram.io, with the marts at the end).
- `dbt_project/tests/assert_81_games_per_run.sql` (the singular completeness test).
- `dbt_project/dbt_project.yml`, `dbt_project/macros/`, `dbt_project/packages.yml` (`dbt_utils` 1.4.1 is installed in `dbt_packages/`: read the macro source there, do not guess arguments).
- `snowflake_setup/03_schemas.sql` and `04_grants.sql` (read only, do not change).

Then check git **with me**: `git branch`, `git status`, `git log --oneline -3`.

## 2. Where we are (written on 2026-11-06, check again)

- I decided to **stay on `feat/dbt-intermediate`** for the whole star, and not make a new branch. The branch has three commits of its own on top of the merge of PR #15, all pushed: `2e4a023`, `3bd5688`, `745c8b3`. Local `main` did not yet have them when I last checked (I said I merged on GitHub, but had not run `git switch main` and `git pull`). **Check.**
- **Everything from the split is uncommitted:** `dim_game.sql` (10 columns), three new models (`fact_game_store.sql`, `fact_game_players.sql`, `fact_game_reviews.sql`), the new test file in `dbt_project/tests/`, `_int_steam__models.yml`, `logical_model.dbml`, the re-exported `assets/logical_model_1.png`, and docs 13 and 14. Docs 13 and 14 hold the whole story.
- **Whole project build on 2026-11-06, 13:32, pasted by me: `Done. PASS=74 WARN=0 ERROR=0`.** You saw only that last line. By my count that is 11 models (5 staging views, 6 intermediate views) and 63 data tests (37 staging, 26 intermediate). Only the `marts` "unused configuration paths" warning should be left.
- **Untracked files in `scratch/` are on purpose out of git.**
- I did **not** yet look at the rows of the three facts in Snowsight, and I did not run a new count query on `DIM_GAME` after the cut to 10 columns.

**What is built** (all views in `STEAM_DB.INTERMEDIATE`, all in `dbt_project/models/intermediate/`):

| Model | One row is | Reads | Tests |
|---|---|---|---|
| `int_steam__games_latest` | one game | `stg_steam__games` | 2 |
| `dim_date` | one Stockholm day that has a run | `stg_steam__games` | 2 |
| `dim_game` (10 columns) | one game | `int_steam__games_latest` | 2 |
| `fact_game_store` | one game in one run | `stg_steam__games` | 6 |
| `fact_game_players` | one game in one run | `stg_steam__player_counts` | 6 |
| `fact_game_reviews` | one game in one run | `stg_steam__review_summary` left join `stg_steam__review_recent` | 7 |
| `assert_81_games_per_run` (singular test, `warn`) | | the three facts | 1 |

Columns:
- `dim_game`: `steam_appid`, `name`, `release_date`, `release_year`, `metacritic_score`, `website`, `short_description`, `developers`, `genres`, `genres_text`.
- `fact_game_store`: keys, `collected_at_utc`, `price_currency`, `price_initial`, `price_final`, `is_free`, `coming_soon`.
- `fact_game_reviews`: keys, `collected_at_utc`, `total_positive`, `total_negative`, `counts_all_languages`, `recent_positive`, `recent_negative`.
- `fact_game_players`: keys, `collected_at_utc`, `collected_hour_local`, `player_count`, `has_player_data`.
- Keys in every fact: `steam_appid`, `load_id`, `snapshot_date` (the Stockholm day, points to `dim_date.date_day`).

**Findings that matter for the marts** (details in docs 13 and 14):

- Runs per table (CSV exports of 2026-11-06): `games` 8 (from 2026-10-23), `review_summary` 7 (from 2026-10-26), `review_recent` 4 (from 2026-11-02), `player_counts` 6 (from 2026-10-27, from the row count of `fact_game_players`, screenshot 2026-11-06: 486 rows). Doc 13 once said 4, which was out of date. Each run has 81 rows in each fact (the completeness test passed, and 648, 567 and 486 rows are 8, 7 and 6 times 81).
- Every `review_recent` run also has a `review_summary` run with the same `load_id`. No run crosses midnight.
- 0 of 81 games changed `name`, `release_date_text`, `required_age`, `metacritic_score`, `website` or `genres` over the 8 runs. Only about two weeks of history.
- 45 of 81 games have a Metacritic score. 4 unreleased games have no release date: Afterworld, Guardians of the Wild Sky, LEGO Skylines, Prison Architect 2.
- A free game has no price (NULL). **Two** games are free: *Crusader Kings II* (`203770`) and *Knights of Pen and Paper 2: Free Edition* (`794820`). Two other released games have no price and are not free: *Majesty 2 Collection* (`73020`) and *Galaxy of Pen & Paper +1* (`349790`). All four have both prices NULL in all 8 runs (query on `FACT_GAME_STORE`, screenshot 2026-11-06). I had said only one game is free, which was wrong. So `is_free` is the only column that tells the four apart.
- Run times vary (10:43, 15:05, 13:14 earlier), so the hour of a player count matters.

## 3. Decisions already made (do not reopen). All are in docs 13 and 14.

| Topic | Decision |
|---|---|
| Layers | `intermediate` is a **view** in schema `INTERMEDIATE`, `marts` are tables in `MARTS`. Staging stays views. The five star models live in `INTERMEDIATE` as views, no exception. Revisit "table" only if Streamlit feels slow. `STEAM_TRANSFORMER` can create views there (run-verified), no grant change. |
| Star schema | Strict star: every dimension connects directly to every fact, no dimension links to another. **Three facts share two dimensions** (a fact constellation). |
| Three facts | `fact_game_store`, `fact_game_reviews`, `fact_game_players`, one for each kind of measurement (my teacher's tip, 2026-11-06). Each reads its staging model directly. `int_steam__game_run` was dropped. |
| Grain | **One row per game per run** in every fact, joined on **`steam_appid` + `load_id`**, not on the date. A `unique` test on (`steam_appid`, `load_id`) guards each fact. |
| Rows | A fact has rows only for runs where its source has data. No rows padded with NULL. |
| Joining the facts | In the **mart**, not in the star. Start from `fact_game_store` and **left join** the other two. The grain is the same, so the join gives one row for one row. Never join facts to each other anywhere else. Never add numbers across facts. |
| Facts store | Counts, not percentages. Percentages, `discount_percent` and "change since the previous run" (`LAG`) are worked out in the marts. |
| `dim_game` | 10 columns. `type`, `release_date_text`, `required_age`, the three platform columns, `publishers` and `categories` are dropped. `metacritic_score`, `short_description`, `website` and `developers` kept on purpose. |
| `fact_game_store` | Keeps `is_free` (a free game has no price, so `is_free` is the only way to tell it from a missing price). Does not store `discount_percent`. |
| Genre | Stays a list on `dim_game` plus `genres_text`. It is split in `mart_genre_comparison`. The genre share is all positive ÷ all reviews, never an average of percentages. A game with 3 genres counts in 3 genre rows. |
| Achievements | Out of the star for now. |
| Franchise | Dropped from the whole project. |
| Minimums | None. One game at a time, the review count next to the percent, no ranking. |
| Streamlit | Reads **`MARTS` only**, through `mart_game_detail` plus `mart_genre_comparison`. No grant change. |
| Naming | `int_steam__<name>.sql` for prep models, `fact_...` / `dim_...` for the star, in `models/intermediate/`. Tests in `_int_steam__models.yml`. |
| Staging stays 1:1 | Joins and "latest row per game" belong in intermediate. |
| NULL vs 0 | Never `coalesce(player_count, 0)`. A missing price is never 0. No achievement rows is not 0 %. A missing Metacritic score is NULL. |
| Unreleased | Use `coming_soon` from `fact_game_store`. Never use `result = 42` or zero reviews to mean "unreleased". |
| English-only reviews | `review_summary` before 2026-11-02 counts English only. Use `counts_all_languages` in every trend and change calculation. |
| `dim_date` | Run days only, no `date_spine`, no end date. |
| Extra checks | Recent never above all-time: a `warn` test on `fact_game_reviews`. Completeness: a `warn` singular test, 81 games per run in each fact. Both passed. |
| Raw stays raw | No change to raw tables. |

## 4. The task, in order

How I run dbt (from `dbt_project/`, Git Bash, virtual environment active):

```bash
set -a; source ../.env; set +a
dbt build
```

| Step | What |
|---|---|
| 0 | Git: check state with me (`git branch`, `git status`, `git log --oneline -3`). Confirm I am on `feat/dbt-intermediate`. Check whether `745c8b3` is on `main`. |
| 1 | **Look at the data of the three facts in Snowsight** (read-only queries, full names in capitals, one per message). **Done on 2026-11-06 (see doc 14):** row counts and runs per fact, the prices of the free and no-price games, the NULL `recent_*` columns in the first three runs of `fact_game_reviews`, and the player counts per day (77 of 81 games have a count every day, 9 to 15 real zeros, run hours 9 to 15). **Still open:** a count query on `STEAM_DB.INTERMEDIATE.DIM_GAME` after the cut to 10 columns (before the cut: 81 rows, 77 with `release_year`, 45 with `metacritic_score`), and a look at single games if I want. Write what we see into doc 14. |
| 2 | **Commit.** One commit or a few small ones, as I choose. Give me the commands with a body and the trailer (section 6). The changes are in `docs/13`, `docs/14`, `assets/logical_model_1.png`, `dbt_project/models/intermediate/`, `dbt_project/tests/`. **Leave the uncommitted area 8 edit in doc 13 alone** (section 5): ask me what I want first. Then a PR draft for me. |
| 3 | **Marts**, only when I ask, on a separate branch (`feat/dbt-marts`): `mart_game_detail` (one game per run, starts from `fact_game_store`, left joins the other two facts and `dim_game`, works out `total_reviews`, `pct_positive`, `pct_positive_recent`, `discount_percent` and the changes since the previous run) and `mart_genre_comparison` (splits `dim_game.genres`, groups by genre and day, shares are sums divided by sums). Columns are in doc 13 section 6.4 and in the dbml. Plan table first, as always. |

Expected count to predict (my arithmetic, not a result): the project has 11 models and 63 tests. Each new model with N tests adds 1 model and N tests.

## 5. Things still open or not checked (do not start unless I ask, or they block the work)

- **Failed run and two runs in one day:** not tested. `assert_81_games_per_run` warns on a partial run.
- **Area 8 (player progression, optional) in doc 13:** I have an **uncommitted** edit that says "Thinking of droppng this" (typo) in the area name. It is not a decision yet. Ask me before you commit or change it, and ask what I want the text to say.
- **`has_achievements`** from our own `achievements` rows (7 games disagree with the store category). Not in the star. Ask me before building it.
- **Unpacked lists** (`int_steam__game_genres` and similar): probably never needed. Do not build.
- **Free games in price averages:** decide in the marts (NULL prices are skipped by an average).
- **Airflow:** I said on 2026-11-06 that I can "just stop the pipeline with Airflow". Doc 13 says orchestration is not decided and I run dlt by hand. A branch `feat/schedule-run` exists and **you have not read it**. Do not build anything for orchestration. Ask me if it matters.
- **`README.md`:** it changed in commit `3bd5688`. I did that, you did not look at the change. It may still describe the star with one fact: check it before the PR.
- **Commit messages:** `2e4a023` is `feat/int schema models`, `745c8b3` is `refactor(dbt models) add dim_game and refactor dim_date`. They are pushed, with no body and no trailer.
- **The picture:** `assets/logical_model_1.png` is re-exported. The bottom of the `fact_game_reviews` box is cut off a little.
- Snowflake: key-pair login for `DBT_USER` (a password now), `DLT_USER` still has a password, `STREAMLIT_USER` login is decided when Streamlit is built.
- Ingestion open items (`result` 42 meaning, two games without a price `73020` and `349790`, the Free Edition with no reviews, one fixed run hour): not part of this task.
- The notebooks are behind the data. **Do not edit notebooks without asking.**
- `docs/03` and `docs/04` still say "password and MFA" for `DBT_USER`: a small doc fix, only when I say so.

## 6. After each model or step

1. I run `dbt build --select <model>` and paste the result (account name replaced by `xxx`).
2. I check the data in Snowsight (you give me a small read-only query with the full path in capitals).
3. You write it into `docs/14_dbt_intermediate.md` (new section, status line, models table, validation, decisions, "Not done yet").
4. I commit. Give me the commands with a body and the trailer, in this shape (several `-m` become separate paragraphs):

```bash
git commit -m "feat(dbt): add the three facts and slim dim_game" -m "Why: one fact mixed four sources with different histories, so it is now one fact for each kind of measurement. What: fact_game_store, fact_game_reviews, fact_game_players, dim_game cut to 10 columns, a completeness test, docs 13 and 14 and the logical model updated. Decisions: strict star kept, int_steam__game_run dropped, is_free kept and discount_percent not stored. Checked: dbt build gave PASS=74 WARN=0 ERROR=0." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

## 7. Please begin by

1. Reading the files in section 1 (A, B and C). It is a lot: say briefly what you read, and flag anything that disagrees with this file.
2. Checking git with me, one command at a time.
3. Telling me in **three short sentences** where we are.
4. Giving me **one** thing to do: the first Snowsight query of step 1. Then wait.
