# Handoff prompt: ingestion wrap-up, then the scheduled run (dlt, Snowflake)

Written 2026-10-27 at the end of session 3. It summarises what is done and gives the plan for the next task. Read it fully before doing anything.

## 0. Read this first: how you must work

I am Aira, a beginner data engineering student at Stockholms Tekniska Institut (STI). This is my graduation thesis (Examensarbete) and I have a deadline, so I want to move faster, but I still want to understand every step.

**Hard rules (never break these):**

1. **Never open, read, print, edit or ask for `.env`, `.dlt/secrets.toml`, or any file or value that holds a secret.** That includes private keys and key files for Snowflake. Use `.env.example` to see which variables exist. Never ask me to paste a password, key or token in chat. If an error message or a notebook output might contain a secret (for example an account name), tell me to check it before pasting.
2. **Do not create or edit files in my project, and do not run commands, unless I give permission for the specific file or task.** By default, show me the file path and the code in chat. I paste it into VS Code myself. Give terminal commands in their own fenced `bash` block (one command per block), I run them, and I paste the output back. Permission is per file and does not carry over. Ask again each time.
3. **Plan first.** Before any code, give me a short written plan for the step and wait for my OK.
4. **Never use DuckDB** anywhere in this project. dlt loads straight to Snowflake `STEAM_DB.STEAM_RAW`.
5. **Ask before** anything that would be hard to undo: committing, pushing, installing packages, changing Snowflake objects (users, keys, grants), or anything that sends many requests to Steam. I run all git commands myself. **Never commit on `main`**: create a branch first.
6. **Do not guess about the API or about Snowflake.** If something is unverified, say so, and give me a small test I can run. Do not write "probably" as if it were a fact in a notebook or doc.

**Style I want:**
- Plain, simple language ("dumb it down"). Short explanations of why, not only what. Tables are welcome. Keep PR descriptions and replies short and simple; I will tell you if I want more detail.
- Docs and notebook text like a student's own notes: short sentences, no filler. I edit the notebook text myself afterwards, so **read the current text of a cell before you change it, and never rewrite a whole cell from an old copy**. My notebook style: `**💡Insights:**` with bullets and small tables. For dbt findings I use one small table per finding (Findings, Why it matters, What dbt does, Layer).
- A few lines or one small file at a time, but with bigger steps than a tutorial, because of my deadline.
- Ask at most one question at a time, and only when it really blocks the work.
- End each step with a short summary: what we learned, what we decided, what is next.
- Be honest about outcomes: say if something failed, was skipped, or is unverified. If a number comes from a hand count or a partial view, say so.
- Docs in `docs/` (the folder we push to GitHub) use tables, clickable relative links to code lines, and give the reason for every decision.

## 1. Project in one paragraph

**Working title:** *Paradox Interactive Game Analysis: A Modern Data Stack for Pricing, Reception and Player Activity on Steam.*

A batch data platform on public Steam data for the 81 games published by **Paradox Interactive**. Paradox is the stakeholder in a proof-of-concept scenario; the project is independent academic work, not affiliated with or endorsed by Paradox or Valve.

**Target flow:** Steam public endpoints -> Python + dlt -> Snowflake `STEAM_RAW` -> dbt Core (`STAGING` -> `INTERMEDIATE` -> `MARTS`) -> Snowsight + Streamlit.

**Business questions:** How are games priced and discounted across the portfolio? How do review sentiment, price and player counts relate? How do new releases compare with older ones and with flagship franchises?

**Known limits (state honestly in the thesis):** batch only; small hand-scoped sample; price, review and player history exist only from the first collection date; the Store endpoints are undocumented; Steam gives no sales or revenue figures, so reviews and player counts are proxies; a player count is one moment and depends on the hour; findings show correlation, not causation.

## 2. What was done so far

**The dlt extract and load part is done for all three sources and merged into `main`.**

| Session | Date | Work |
|---|---|---|
| 1 | 2026-10-23 | `games` (Store `appdetails`): 81 games loaded. Doc `docs/05_games__dlt_ingestion.md`, notebook `notebooks/01_eda_games.ipynb`. |
| 2 | 2026-10-26 | `review_summary` (`GetAppReviews`, totals only): 81 rows. Merged in PR #6. Doc `docs/06_reviews__dlt_ingestion.md`, notebook 02. |
| 3 | 2026-10-27 | `player_counts` (`GetNumberOfCurrentPlayers`): probe, build, 16 new tests (35 in total), first full run, notebook 03, docs 06 and 07. Merged in PR #7 (`main` at `c1aa1bc`). |

First full run with all three resources (2026-10-27): 243 requests, 10:43 to 10:53 Stockholm time, no 429. `player_counts`: 77 with a count (13 of them a real 0), 4 without data (the 4 unreleased games, `result` 42).

## 3. Current state (verify with me before assuming)

- `main` contains everything above. I was about to open a small docs-only PR from a branch **`docs/update-ingestion-plan`** (plan file `scratch/docs/06_dlt_ingestion_plan.md`, doc 07, notebook 03). **Check `git status` and `git branch` first**: it may not be merged yet.
- Untracked and intentionally left out of git: `scratch/appdetails/`, `scratch/appreviews/`, `scratch/playercounts/` (probe scripts), `scratch/docs/07_...`, `08_...`, `09_...` and this file. Do not commit them and do not delete them. Links in `docs/` must not point to files in `scratch/`.
- Snowflake: warehouse `STEAM_WH`, database `STEAM_DB`, schemas `STEAM_RAW`, `STAGING`, `INTERMEDIATE`, `MARTS`. Roles `STEAM_LOADER`, `STEAM_TRANSFORMER`, `STEAM_REPORTER`; users `DLT_USER`, `DBT_USER`, `STREAMLIT_USER`. See `docs/01` to `docs/05`.
- Tables in `STEAM_RAW`: `GAMES` (one Portal 2 test row with appid 620, plus 81 rows from each of 2026-10-23, 10-26 and 10-27), `REVIEW_SUMMARY` (81 rows from 10-26 and from 10-27), `PLAYER_COUNTS` (81 rows from 10-27, each with its own `collected_at`).
- dbt Core is initialised under `dbt_project/`, no models yet.
- Python 3.12 with `uv`. Groups: `ingestion` (dlt[snowflake], pandas, requests), `dev` (ipykernel, pytest, ruff), `transform`, `dashboard`.
- Code under `src/steam_data_platform/`:
  - `settings.py`: `GAME_APPIDS` (81 ids), `STORE_COUNTRY="se"`, `STORE_LANGUAGE="english"`, `REQUEST_PAUSE_SECONDS=2.0`.
  - `connections.py`: `loader_credentials()` reads `SNOWFLAKE_*` environment variables.
  - `ingestion/steam.py`: `get_with_retry(url, params, label, accept_statuses=())`, `fetch_app_details` (**still has its own copy of the retry code**), `fetch_review_summary`, `fetch_player_count`, `build_game_row`, `build_review_row`, `build_player_row`, the resources `games`, `review_summary`, `player_counts` (all `append`), and `steam_source`.
  - `ingestion/pipelines_steam.py`: builds the pipeline (`pipeline_name="steam"`, `dataset_name="steam_raw"`) and runs it under `if __name__ == "__main__"`. It logs only the load ids, because dlt's full load summary contains the Snowflake account name.
- Run command: `uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam`
- **Do not run the full pipeline just for testing.** `append` adds rows on every run. One run per day at most (243 requests, about 10 minutes).
- To test a resource without Snowflake, iterate it directly in a small script (dlt resources are iterable). Resources must not use `parallelized=True`.
- Tests: `tests/test_steam_dlt.py`, 35 tests, all passing. Pattern: a hand-written `FakeResponse`, a `sleeps` fixture, a `patch_get` fixture, plain functions for resource tests. Run `uv run ruff format src tests`, then `uv run ruff check src tests`, then `uv run pytest -q`.
- Table facts: `collected_at` is `TIMESTAMP_LTZ(9)`; counts are `NUMBER(19,0)`; lists are `VARIANT`; prices are integer minor units in EUR. In `player_counts`, `collected_at` is per row; in the other two tables it is one time per run.

## 4. Decisions already made

| Topic | Decision |
|---|---|
| Scope | 81 Paradox Interactive apps in `GAME_APPIDS`. |
| API key | None. Public endpoints only. |
| Destination | Snowflake only, no DuckDB. |
| Pipeline design | One pipeline, one source, three resources. |
| Write mode | `append`, one row per game per run. |
| Raw layer | Faithful copy of what Steam sends. dbt cleans later. |
| Reviews | Totals only. Single reviews are not loaded. |
| Player counts | A 404 / `result` 42 is stored as a row with NULL `player_count`. A real 0 stays 0. `result` is kept. |
| Orchestration | No Airflow for now. Later a simple scheduled batch script. Airflow is future work. |
| dbt findings | Proposals are in section 10 of notebooks 02 and 03 and in the docs. They are not built yet. |
| Reference repo | https://github.com/indiramahadiva/Flight-punctuality_4_DE25 (structure and test style only; not Dagster, Docker, Terraform). |

**Still open (ask me when relevant):** whether Streamlit runs locally or inside Snowflake; time estimates in the proposal; the minimum number of reviews and of players for comparisons; the rule for repeated runs.

## 5. Open issues

- `DLT_USER` is a `PERSON` account (password plus MFA) but loads with a password only. I do not know why. `snowflake_setup/05_create_users.sql` still says `SERVICE`. A scheduled run needs a non-interactive login (for example key-pair authentication).
- `fetch_app_details` should use `get_with_retry`; the `games` resource has no progress line.
- Notebook 01: the outputs for sections 2, 8, 9 and 10 now exist, but the text still says "not yet run".
- Rule for repeated runs (proposal: one scheduled run per day, same clock time, and the latest row per game for current-state questions).
- What `result` 42 means exactly (unverified); whether a released game can ever get 404 / 42.
- Whether a review total can go down between two runs (now there are 2 snapshots, so this can be checked).
- Why *Knights of Pen and Paper 2: Free Edition* has zero reviews and zero players.
- Whether `dbt_utils` is installed (needed for a `unique` test on two columns).

## 6. Next task: ingestion wrap-up, then the scheduled run

Suggested order. Ask me which to start with, and do one at a time:

1. **Clean-ups (small, safe, own branch, for example `refactor/ingestion-cleanups`).**
   - Let `fetch_app_details` use `get_with_retry`. Keep the behaviour: a 200 with `success: false` returns `None`. Keep or adapt the tests.
   - Add a progress line to the `games` resource.
   - Update the text in notebook 01 where it says "not yet run" (read the current text first; I edit it myself).
   - Plan first. Then show the code in chat.
2. **Scheduled run with a non-interactive login (own branch, for example `feat/scheduled-run`).** First a written plan with options (I use Windows, with `uv`), and wait for my OK:
   - What runs the script (for example Windows Task Scheduler) and at which clock time every day (my first run started at 10:43 Stockholm time).
   - Key-pair authentication for `DLT_USER`: what changes in Snowflake and in `connections.py`. **Changes to Snowflake users and keys are hard to undo: ask first, and never read or print a key file.**
   - A simple wrapper script, logging to a file, a rule for a failed run, and the one-run-per-day rule.
   - Do not run the full pipeline to test it. Test with fake data or one small run that I agree to.
3. **After that, dbt (not before I say so):** `feat/dbt-sources`, `feat/dbt-staging`, `feat/dbt-intermediate`, `feat/dbt-marts`, then the Streamlit dashboard. The proposals are in notebooks 02 and 03 (section 10).

## 7. Best-practice checklist for all code you show me

- Python 3.12, type hints, short docstrings, small single-purpose functions, clear names; match the style of the existing files.
- Secrets only from environment variables. Never print credentials, the Snowflake account name or full connection strings.
- Every HTTP call has a timeout, paced requests, retry with backoff on 429/5xx (this is in `get_with_retry`, so use it).
- Treat missing keys and `None` explicitly; keep zero and missing apart.
- Idempotency: choose the write disposition and key deliberately and explain the choice.
- Use `logging`, not `print`, in `src/`.
- Format and lint with `ruff`; test with `pytest`; manage dependencies with `uv` and keep `uv.lock` in sync. Run `ruff format` before the final `pytest` run.
- Do not commit data files, `.env`, `.dlt/secrets.toml`, keys or caches. Keep CSV exports from Snowsight out of the repo.
- Before committing a notebook, check its saved outputs for secrets: `grep -n -i -E "snowflakecomputing|secret|\.aws" notebooks/*.ipynb`. The output should only show harmless text.
- Commits: small, conventional style (`feat(ingestion): ...`, `test(ingestion): ...`, `docs: ...`). End each commit message with the attribution line the app gives you. Always ask me before committing or pushing. I run the git commands, one command per block.
- Update `scratch/docs/06_dlt_ingestion_plan.md` (session notes) as we go, with my permission for that file, and add a new doc in `docs/` for each finished step (next number is `08`).

## 8. Tool tips from sessions 2 and 3

- When you paste a whole file over an old one in VS Code, press Ctrl+A and Delete first.
- A notebook open in VS Code does not refresh when a file is changed from outside. Close the tab and choose "Don't Save", then reopen it.
- Notebooks: use the notebook edit tool for whole cells, but only after reading the current text. For one or two changed lines in a notebook that has saved outputs and my own edits, a small script that replaces exact strings (and checks the file is still valid JSON) is safer than rewriting cells.
- dlt wraps any error raised inside a resource in `ResourceExtractionError`. In tests, expect that error and check `error.value.__cause__`.
- The first push of a new branch needs `git push --set-upstream origin <branch>`. Check the branch name for typos.
- Snowsight shows times in my session time zone (Pacific, `-0700`), so they look 9 hours earlier than Stockholm time (UTC+1 now). Notebooks set the session to UTC.
- Windows with Git Bash: the repo shows LF/CRLF warnings. They are harmless.

## 9. Please begin by

1. Reading: `scratch/docs/06_dlt_ingestion_plan.md`, `docs/05`, `docs/06`, `docs/07`, `src/steam_data_platform/ingestion/steam.py`, `pipelines_steam.py`, `connections.py`, `settings.py`, `tests/test_steam_dlt.py`, `.env.example` (**not** `.env`), and `snowflake_setup/05_create_users.sql`.
2. Checking `git status` and the current branch with me.
3. Telling me in a few sentences what you understood and what you are unsure about.
4. Asking me which of the three tasks in section 6 to start with, then presenting the plan for it and waiting for my OK.