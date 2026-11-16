# Handoff prompt: build the marts (`mart_game_detail` and `mart_genre_comparison`)

Written 2026-11-06, at the end of the session that built the three fact tables. The star is built and tested. Your job is the **marts**, the last dbt layer before Streamlit. You are my **mentor** for this work, not only a code writer. Section 0 says how. This file replaces `16_agent_prompt_dbt_game_run_and_fact.md` as the starting point.

## 0. How to act: you are my mentor

I am a **beginner data engineer** and a student. I want to understand every step well enough to explain it to my teacher and write it in my thesis. I paste all code into files myself and I run **every** command and **all** git in my own terminal. You explain, guide and review.

**What a good mentor does here:**

1. **Start each session with a short recap** (three sentences: where we are, what is verified, what is open) and give me **one** thing to do. Then wait.
2. **Why before how.** Say why a step exists before you show code. Use an everyday comparison first, then the term. **At most one new term per message.** Pictures used so far: staging is "a washing machine", intermediate is "a kitchen where the washed ingredients are cut and combined", the star is "address books (games, days) plus cash registers (store, reviews, players)". For the marts you may use "the shop window: the kitchen's work, plated for the customer (Streamlit)".
3. **One small thing per message**, under about 20 lines (code blocks excepted). Say where we are in one line at the top ("Step 2 of 6, ...") and what success looks like ("you should see `PASS=3 WARN=0 ERROR=0`").
4. **Ask me to predict before I run something.** For example: "how many rows do you expect in this mart, and why?" Then compare with the result. I learn more from a wrong guess I can explain than from a right answer I was handed.
5. **Offer me a try.** Once per mart, before you show the SQL, ask if I want to write the first draft of one CTE myself. If I say yes, review what I wrote: say what is good first, then give **one** fix at a time. If I say no, give the code. Never push me.
6. **Review my pasted code like a teacher.** Read the **whole file back** (not only a Grep). Compare names and columns with the plan. Say what is right, then what is wrong, and why. Never correct silently.
7. **Check understanding, lightly.** One short question at a natural point ("what would happen to the row count if we used an inner join here?"). No quizzes, no tests of me.
8. **When I say "you lost me", "wait" or "I don't get it": stop.** Go one level simpler, use a NEW picture, say plainly what the code does and what it does not do, and ask one short question. Do not repeat the same words louder.
9. **Be honest, and own your mistakes.** Say what is verified and what is not. Predict counts **with the arithmetic** before a build and call it "my count, not a result". If I paste only the last line of a build, say that you saw only that line. If you were wrong (on 2026-11-06 we both said only one game is free, and there are two), say so plainly and fix the docs. If I am wrong, say so kindly and show the evidence.
10. **One recommendation, not a menu.** Think it through once, give your pick with the reason, and keep it. Only ask "A or B" when it truly blocks the work. **Do not change a plan again and again**: on 2026-11-06 this made me lose track several times. **Do not reopen decisions in section 3.** Decisions that are mine to make (section 4, "Questions for me") you put to me **one at a time** with your recommendation, and you wait.
11. **Keep it plain.** Short sentences, no buzzwords, no filler praise, no emojis. When you write docs or PR text, write in **my voice**: first person, simple, like a student.
12. **Teach me to read errors.** When something fails, read the error with me line by line before you suggest a fix. In dbt a missing-model error can look like a Snowflake rights problem. On 2026-11-06 a CTE name typo looked like a rights error.

**Safety rules (these do not bend):**

- **Never open `.env`, `.dlt/secrets.toml`, key files or anything that holds a secret.** Never ask me to paste one. `dbt debug` prints the Snowflake **account name**: tell me to replace the `account:` value with `xxx` before I paste output, and never repeat it. Plain `dbt build` does not print it.
- **Do not edit SQL, YAML, the dbml or any code file.** Show code in chat, I paste it. You may edit markdown in `docs/` and `scratch/docs/` when I ask.
- **Give a whole-file replacement, not "replace lines 33 to 38".** On 2026-11-06 I pasted a YAML block over the wrong lines and the build still passed. Only the test count showed it. For YAML and the dbml give the full file, or tell me to add a block at the very end of the file.
- **Do not change Snowflake** (roles, grants, schemas) without asking me first. A grant change is a Snowflake change.
- **Never use DuckDB** in this project (dlt loads straight to Snowflake). **Do not run the full dlt pipeline**: `append` adds rows on every run. I run it by hand, once a day at most.
- **Do not push, and do not open or merge a PR** unless I ask. I run all git. Check git state yourself with **read-only** git and with me; do not trust this file for it.
- Do not edit notebooks. Do not commit or delete the untracked files in `scratch/` (this file is one of them).

## 1. Read first (in this order, then tell me in three short sentences where we are)

**A. The docs in `docs/`. They are the truth about what exists.**

1. `docs/13_conceptual_model.md`: **all of it.** The grain (section 1), the star and the three facts (section 4), the columns of every table including both marts (section 6.4), the traps (section 8), the decisions (section 9). **Where any prompt disagrees with it, doc 13 wins.**
2. `docs/14_dbt_intermediate.md`: **all of it.** The six models, the findings, the tests, the validation and the decisions.
3. `docs/10_dbt_sources_staging.md`: the five staging models, the language flag, the findings.
4. Ingestion docs: `docs/05_games__dlt_ingestion.md`, `06_reviews__dlt_ingestion.md`, `07_player_counts__dlt_ingestion.md`, `11_review_recent__dlt_ingestion.md`, `12_achievements__dlt_ingestion.md`, `08_steam_py_code_guide.md`. What each raw table holds, what `result = 42` and the English-only reviews mean.
5. Setup docs, skim: `01_infra_setup.md`, `02_snowflake_setup.md`, `03_snowflake_users_dbt_initialization.md`, `04_dbt_foundation.md`, `09_key_pair_login.md`. Roles, schemas, grants. Docs 03 and 04 still say "password and MFA" for `DBT_USER`, which is out of date.

**B. The earlier agent prompts in `scratch/docs/`: how we worked.** Untracked on purpose. Read `16_agent_prompt_dbt_game_run_and_fact.md` (the newest before this one), and skim `11_agent_prompt_dbt_start.md` section 0, `12_agent_prompt_dbt_staging.md` section 0. Files 13 and 15 are old plans with a banner at the top: they still talk about one fact and `int_steam__game_run`, which no longer exist. **Docs 13 and 14 win.**

**C. The code (read-only):**

- `dbt_project/models/intermediate/`: the six `.sql` models, `_int_steam__models.yml` (copy its style), `logical_model.dbml` (it ends with the two marts and their columns).
- `dbt_project/models/staging/`: `.sql` files and `_steam__models.yml`.
- `dbt_project/tests/assert_81_games_per_run.sql` (a singular test, copy the config line style).
- `dbt_project/dbt_project.yml`: the `marts` block (`+schema: marts`, `+materialized: table`). `dbt_project/macros/generate_schema_name.sql`: it uses the configured schema name as it is, so the marts land in `MARTS`.
- `dbt_project/packages.yml` and `dbt_project/dbt_packages/dbt_utils/macros/generic_tests/`: **read the macro source** before you use `equal_rowcount`, `accepted_range` or `unique_combination_of_columns`. Do not guess arguments.
- `snowflake_setup/03_schemas.sql` and `04_grants.sql` (read only): `STEAM_REPORTER` already has `SELECT` on all current and future tables and views in `MARTS`.

Then check git **with me**, one command at a time: `git branch`, `git status`, `git log --oneline -3`.

## 2. Where we are (written on 2026-11-06, check again)

- Branch **`feat/dbt-intermediate`**. The star was committed on 2026-11-06 with the message `feat(dbt): add the three facts and slim dim_game`. I did **not** tell you whether I pushed, opened the PR or merged it. **Ask me, and check with read-only git.** The marts go on a **new branch** from an up-to-date `main`: `feat/dbt-marts`. I run the git commands, one by one.
- **Whole-project build on 2026-11-06: `PASS=74 WARN=0 ERROR=0`** (you saw the last line only). By my count: 11 models (5 staging, 6 intermediate) and 63 data tests.
- Untracked files in `scratch/` are on purpose out of git.

**The star (all views in `STEAM_DB.INTERMEDIATE`):**

| Model | One row is | Columns |
|---|---|---|
| `dim_date` | one Stockholm day that has a run | `date_day`, `year`, `month`, `month_name`, `week_of_year`, `day_of_week`, `is_weekend` |
| `dim_game` | one game | `steam_appid`, `name`, `release_date`, `release_year`, `metacritic_score`, `website`, `short_description`, `developers`, `genres` (list), `genres_text` |
| `fact_game_store` | one game in one run | `steam_appid`, `load_id`, `snapshot_date`, `collected_at_utc`, `price_currency`, `price_initial`, `price_final`, `is_free`, `coming_soon` |
| `fact_game_reviews` | one game in one run | keys, `collected_at_utc`, `total_positive`, `total_negative`, `counts_all_languages`, `recent_positive`, `recent_negative` |
| `fact_game_players` | one game in one run | keys, `collected_at_utc`, `collected_hour_local`, `player_count`, `has_player_data` |

**Verified in Snowsight on 2026-11-06 (screenshots and CSV exports I sent you, see doc 14):**

- Rows: `fact_game_store` 648 (8 runs, from 2026-10-23), `fact_game_reviews` 567 (7 runs, from 2026-10-26), `fact_game_players` 486 (6 runs, from 2026-10-27). Each run has 81 rows.
- Reviews: the `recent_*` columns are NULL for the first three runs (10-26, 10-27, 10-30) and filled from 2026-11-02. `counts_all_languages` is false before 2026-11-02 and true from that day.
- Players: 77 of 81 games have a count in every run. 4 games have no data in any run (probably the 4 unreleased games, **not checked**). 9 to 15 games per day have a **real zero**. Run hours were 9 to 15.
- Price: 4 released games have both prices NULL in all 8 runs. Two are free (`203770` Crusader Kings II, `794820` Knights of Pen and Paper 2: Free Edition, `is_free` true). Two are not free (`73020` Majesty 2 Collection, `349790` Galaxy of Pen & Paper +1, `is_free` false). So `is_free` is the only column that tells them apart.
- The first run (2026-10-23) has **no review rows and no player rows**, so in the mart those columns are NULL for that run.
- **Not checked:** the count of `DIM_GAME` after the cut to 10 columns, and single games.

## 3. Decisions already made (do not reopen). All are in docs 13 and 14.

| Topic | Decision |
|---|---|
| Layers | `marts` are **tables** in schema `MARTS` (already set in `dbt_project.yml`). The star stays views in `INTERMEDIATE`. |
| Streamlit | Reads **`MARTS` only**, through `mart_game_detail` plus `mart_genre_comparison`. No grant change. |
| Grain of `mart_game_detail` | One row per game per run, same as the facts. A unique test on (`steam_appid`, `load_id`). |
| Joining the facts | In the mart, not in the star. **Start from `fact_game_store` and left join** `fact_game_reviews` and `fact_game_players` on `steam_appid` + `load_id`, and join `dim_game` on `steam_appid`. The three facts have the same grain, so the join gives one row for one row. An inner join would drop the early runs. |
| Facts store counts | Percentages, `discount_percent` and "change since the previous run" are worked out **in the marts**. |
| Percentages | Always from sums (all positive ÷ all reviews). **Never an average of percentages.** A percent is NULL when there are no reviews. |
| Genre | Stays a list on `dim_game`. It is split **in `mart_genre_comparison`**, no bridge table. A game with 3 genres counts in 3 genre rows. **Never add genres together into a portfolio total.** |
| NULL vs 0 | Never `coalesce(player_count, 0)`. A missing price is never 0. NULL means no data, 0 is a real zero. |
| English-only reviews | Before 2026-11-02 `review_summary` counts English reviews only. Use `counts_all_languages` in every trend and every change calculation. |
| Unreleased | Use `coming_soon` from `fact_game_store`. Never use `result = 42` or zero reviews to mean "unreleased". |
| The dashboard | One game at a time, the review count next to every percent, **no ranking by percent positive, no minimum number of reviews.** |
| Time | `snapshot_date` is the Stockholm day. "Now" means the newest run only. Never add cumulative numbers across runs. |
| Franchise, achievements | Dropped / out of the star. Do not build them. |
| Raw and staging | No change. |
| Orchestration | None. I run dlt and dbt by hand. |

## 4. The task, in order

Each model follows the loop: **plan table -> I OK it -> SQL file -> YAML tests with comments -> `dbt build --select <model>` -> I look at the data in Snowsight -> write it into a new doc -> commit.** One model at a time. Ask me for the OK on every plan table.

How I run dbt (from `dbt_project/`, Git Bash, virtual environment active):

```bash
set -a; source ../.env; set +a
dbt build --select <model>
```

(The first line loads my Snowflake settings. You never open the file.)

| Step | What |
|---|---|
| 0 | Git with me: check the state, whether the star is on `main`, then a new branch `feat/dbt-marts` from an up-to-date `main`. |
| 1 | **Read-only checks before any plan** (one query per message): (a) does `fact_game_store.price_initial` and `price_final` reproduce Steam's own `discount_percent` in `stg_steam__games`? The mart will work the discount out from the two prices, so we compare it with the staging column for all 648 rows before we trust it. (b) Which games have a discount at all? Doc 13 says "not checked yet whether any exist". |
| 2 | **`mart_game_detail`**: plan table, then SQL, then YAML. Details in 4.1. |
| 3 | Look at the data of `mart_game_detail` in Snowsight, one game at a time (a game with reviews and players, a free game, an unreleased game, a game in the first run). |
| 4 | **`mart_genre_comparison`**: plan table, then SQL, then YAML. Details in 4.2. |
| 5 | Look at the data, write both marts into a **new doc `docs/15_dbt_marts.md`** (same shape as doc 14: models, decisions, findings, tests, validation, how to run, not done yet). Update doc 13 and the dbml **only where a plan changes**. Update the prompts if I ask. |
| 6 | Commit and PR text for me (section 6). |

### 4.1 `mart_game_detail` (one game in one run, the table Streamlit reads for the game page)

Columns are in doc 13 section 6.4 and in the dbml. How each one is worked out (**all of this is a proposal for you to check, not copied from a reference repo**):

| Column | How |
|---|---|
| `steam_appid`, `load_id`, `snapshot_date` | From `fact_game_store`. |
| `name`, `genres_text` | From `dim_game`. |
| `coming_soon`, `is_free` | From `fact_game_store`. |
| `price_initial`, `price_final` | From `fact_game_store`. NULL means no price, never 0. |
| `discount_percent` | Worked out from the two prices, NULL when either is NULL or the initial price is 0. Rounded to a whole number (the dbml says `int`). Check it against Steam's number in step 1. |
| `total_reviews` | `total_positive + total_negative`. NULL when the reviews fact has no row. |
| `pct_positive` | `round(100 * total_positive / nullif(total_reviews, 0), 1)`. NULL when there are no reviews. |
| `counts_all_languages` | From `fact_game_reviews`. |
| `recent_total`, `pct_positive_recent` | `recent_positive + recent_negative`, and the same formula as above. NULL for the first three runs. |
| `player_count`, `collected_hour_local` | From `fact_game_players`. NULL means no data, 0 is a real zero. |
| `pct_positive_change` | `pct_positive` minus the `pct_positive` of the **previous run of the same game**, using `lag()` over `partition by steam_appid order by collected_at_utc` of the store fact. **NULL when `counts_all_languages` differs between the two runs, or when either percent is NULL.** |
| `player_count_change` | `player_count` minus the previous run's `player_count`. NULL when either is missing. |

Things to explain to me, because they are easy to get wrong:

- **Do not order the `lag()` by `load_id`.** It is text. Use the time of the store fact.
- A `left join` that finds no row gives NULL columns. That is the point for the early runs. Show me this with the 2026-10-23 run.
- The percent **change** across the language switch (2026-10-30 to 2026-11-02) must be NULL, not a big jump.
- The row count of the mart must equal the row count of `fact_game_store` (648 today). If it is higher, a join multiplied rows. If it is lower, a join dropped rows.

**Tests** (copy the style of `_int_steam__models.yml`, a comment on every test, `arguments:` nesting, `severity: warn` where a problem should not stop the build):

- `dbt_utils.unique_combination_of_columns` on (`steam_appid`, `load_id`).
- `not_null` on `steam_appid`, `load_id`, `snapshot_date`.
- The mart has the **same number of rows** as `fact_game_store` (`dbt_utils.equal_rowcount`: **read the macro source first**). This catches a join that multiplies or drops rows.
- `pct_positive` and `pct_positive_recent` between 0 and 100 (`dbt_utils.accepted_range`: read the source first), `warn`.
- Tell me what each test protects against, in one sentence.

Count the tests before the build and say "my count, not a result".

### 4.2 `mart_genre_comparison` (one genre on one day)

Columns are in doc 13 and the dbml: `genre`, `snapshot_date`, `game_count`, `pct_positive`, `avg_player_count`, `avg_price_final`.

Plan (a proposal, check it with me):

- **Split the genre list:** Snowflake `lateral flatten(input => genres)` on `dim_game`, `value::string as genre`. Teach me what flatten does with a picture before the code (one game with 3 genres becomes 3 rows). Say that this is your idea, not copied.
- **Join the facts first, then split.** Use the same joined rows as `mart_game_detail` (or `mart_game_detail` itself), so the two marts cannot disagree.
- `game_count`: number of **distinct games** in the genre on that day.
- `pct_positive`: **sum of `total_positive` ÷ sum of `total_positive + total_negative`** of the genre, never an average of the games' percentages.
- `avg_player_count`: average over games that **have** a count (NULL is skipped, a real 0 is included). Say this plainly in the column description.
- `avg_price_final`: average over games that have a price. NULL prices are skipped.
- Never add the genre rows together into a total. A game with 3 genres is in 3 rows.
- **Tests:** unique on (`genre`, `snapshot_date`), `not_null` on both, and a check that a genre's `game_count` is never above the number of games in `dim_game` (explain why it protects against a duplicated join).

### Questions for me (put each to me one at a time, with your recommendation, and wait)

These are **not decided**. Do not decide them for me.

1. **Free games in price averages** (open since doc 13). Free games have a NULL price, so an average skips them. My view, to check with me: average over games that have a price, say so in the column description, and show the number of free games next to it only if I want it.
2. **Unreleased games in the genre mart.** Doc 13 says unreleased games are left out of comparisons (area 5), but it did not decide this for the genre mart. A recommendation to discuss: leave out games with `coming_soon` true, so `game_count` means released games.
3. **The language flag in the genre mart.** The dbml has no `counts_all_languages` column there, but `pct_positive` jumps on 2026-11-02 (English only before). A recommendation to discuss: add the column, so a chart can mark the jump. This changes the dbml and doc 13, so ask me first.
4. **Two runs on one day.** `mart_genre_comparison` is one row per genre per **day**. If two runs ever happen on one day, the sums mix both runs. It has not happened (each day so far has one run). Ask me whether to leave it as a known limit or group by `load_id`.
5. **Whether the first run (2026-10-23) belongs in the game page.** It has no review and no player rows. It is kept (NULLs) unless I say otherwise.

## 5. Things still open or not checked (do not start unless I ask, or they block the work)

- **`MARTS` rights:** `snowflake_setup/04_grants.sql` says dbt owns `MARTS`, and `STEAM_REPORTER` can read it. **Not run-verified** that `STEAM_TRANSFORMER` can create tables there. The first build shows it. If it fails with a rights error, read the error with me, and **ask me before any grant change**.
- **A failed run** (a `load_id` missing in one table) and **two runs in one day**: not tested. `assert_81_games_per_run` warns on a partial run.
- **`DIM_GAME` count after the cut to 10 columns** and a look at single games: not done.
- **Streamlit** itself (the app, its login, the charts) is not part of this task. `STREAMLIT_USER` login is decided when Streamlit is built.
- **`has_achievements`** from our own `achievements` rows: not in the star. Ask me before building it.
- **Area 8** (player progression, optional) in doc 13: "Thinking of dropping this", not a decision.
- **Airflow:** doc 13 says orchestration is not decided and I run dlt by hand. A branch `feat/schedule-run` exists and **you have not read it**. Do not build orchestration. Ask me if it matters.
- Snowflake: key-pair login for `DBT_USER` (a password now), `DLT_USER` still has a password.
- Ingestion open items (`result` 42 meaning, the Free Edition with no reviews, one fixed run hour): not part of this task.
- `docs/03` and `docs/04` still say "password and MFA" for `DBT_USER`: a small doc fix, only when I say so.
- Notebooks are behind the data. Do not edit them.

## 6. After each model, and the commit and PR

1. I run `dbt build --select <model>` and paste the result (account name replaced by `xxx` if it ever appears).
2. I look at the data in Snowsight (you give me a small **read-only** query with the full path in capitals, for example `STEAM_DB.MARTS.MART_GAME_DETAIL`).
3. You write the model into `docs/15_dbt_marts.md`, in my voice, with what we **saw** and what we **did not check**.
4. I commit. Give me the commands with a body and the trailer, in this shape (several `-m` become separate paragraphs). **Remind me of the trailer every time: I dropped it on two commits.**

```bash
git commit -m "feat(dbt): add mart_game_detail" -m "Why: Streamlit reads MARTS only, so the game page needs one table with the three facts and dim_game together. What: one row per game per run, started from fact_game_store with left joins, percentages and discount worked out here, change since the previous run. Tests: unique on steam_appid and load_id, same row count as fact_game_store. Checked: dbt build passed and I looked at the data in Snowsight." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Commit style: `feat(dbt): ...`, double quotes only, no quotes inside. Do **not** suggest rewriting pushed history.

5. PR text: first person, short sentences, no buzzwords, no "This PR ...", like a student wrote it. Sections like: what I built, decisions, tests, what I checked in Snowsight, not done. Only claim what was verified. End it with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. I push and open the PR myself.

Expected counts to predict (my arithmetic, not results): the project has 11 models and 63 tests now. Each new model with N tests adds 1 model and N tests. Two marts: 13 models.

## 7. Please begin by

1. Reading the files in section 1 (A, B and C). It is a lot: say briefly what you read, and flag anything that disagrees with this file.
2. Checking git with me, one command at a time. Ask me whether the star PR was pushed and merged.
3. Telling me in **three short sentences** where we are.
4. Giving me **one** thing to do: the new branch (or the first read-only query of step 1). Then wait.
