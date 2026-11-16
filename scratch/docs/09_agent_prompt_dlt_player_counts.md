# Handoff prompt: Steam player counts ingestion (dlt, Snowflake)

Written 2026-10-26 at the end of session 2. It summarises what is done and gives the plan for the next task: the current players endpoint (`GetNumberOfCurrentPlayers`). Read it fully before doing anything.

## 0. Read this first: how you must work

I am Aira, a beginner data engineering student at Stockholms Tekniska Institut (STI). This is my graduation thesis (Examensarbete) and I have a deadline, so I want to move faster, but I still want to understand every step.

**Hard rules (never break these):**

1. **Never open, read, print, edit or ask for `.env`, `.dlt/secrets.toml`, or any file or value that holds a secret.** Use `.env.example` to see which variables exist. Never ask me to paste a password, key or token in chat. If an error message or a notebook output might contain a secret (for example an account name), tell me to check it before pasting.
2. **Do not create or edit files in my project, and do not run commands, unless I give permission for the specific file or task.** By default, show me the file path and the code in chat. I paste it into VS Code myself. Give terminal commands in their own fenced `bash` block (one command per block), I run them, and I paste the output back. Permission is per file: in session 2 I allowed you to write `notebooks/02_eda_reviews.ipynb`, to edit `scratch/docs/06_dlt_ingestion_plan.md` and to write `scratch/docs/09_...` (this file). That does not carry over to other files. Ask again each time.
3. **Plan first.** Before any code, give me a short written plan for the step and wait for my OK.
4. **Never use DuckDB** anywhere in this project (not as a local destination, not for testing, not for EDA). dlt loads straight to Snowflake `STEAM_DB.STEAM_RAW`. `duckdb` is already removed from `pyproject.toml`.
5. **Ask before** anything that would be hard to undo: committing, pushing, installing packages, changing Snowflake objects, or anything that would send many requests to Steam. A push is something I do myself unless I say otherwise.
6. **Do not guess about the API.** If something is unverified, say so, and give me a small test I can run. Do not write "probably" as if it were a fact in the notebook or the plan.

**Style I want:**
- Plain, simple language ("dumb it down"). Short explanations of why, not only what. Diagrams and small tables are welcome.
- Write notebook text and docs like a student's own notes: short sentences, no report-style labels, no filler. I edit the notebook text myself afterwards (I use `**💡Insights:**` with bullets and small tables), so match that style.
- A few lines or one small file at a time, but with bigger steps than a tutorial, because of my deadline.
- Ask at most one question at a time, and only when it really blocks the work.
- End each step with a short summary: what we learned, what we decided, what is next.
- Be honest about outcomes: say if something failed, was skipped, or is unverified. If a number comes from a hand count or a partial view, say so.

## 1. Project in one paragraph

**Working title:** *Paradox Interactive Game Analysis: A Modern Data Stack for Pricing, Reception and Player Activity on Steam.*

A batch data platform on public Steam data for the 81 games published by **Paradox Interactive**. Paradox is the stakeholder in a proof-of-concept scenario; the project is independent academic work, not affiliated with or endorsed by Paradox or Valve.

**Target flow:** Steam public endpoints -> Python + dlt -> Snowflake `STEAM_RAW` -> dbt Core (`STAGING` -> `INTERMEDIATE` -> `MARTS`) -> Snowsight + Streamlit.

**Business questions:** How are games priced and discounted across the portfolio? How do review sentiment, price and player counts relate? How do new releases compare with older ones and with flagship franchises?

**Known limits (state honestly in the thesis):** batch only; small hand-scoped sample; price, review and player history exist only from the first collection date; the Store endpoints are undocumented; Steam gives no sales or revenue figures, so reviews and player counts are proxies; findings show correlation, not causation.

## 2. What was done so far

**Session 1 (2026-10-23): `games`**
- Built and loaded the `games` resource from the Store `appdetails` endpoint: 81 Paradox games into `STEAM_DB.STEAM_RAW.GAMES` (one request per game, 2 s pause, no 429).
- Hardened `steam.py` (skip and count failures, retry 429 and 5xx, stop on repeated 429, explicit `collected_at`, `logging`).
- Wrote `notebooks/01_eda_games.ipynb` and the first version of `scratch/docs/06_dlt_ingestion_plan.md`.

**Session 2 (2026-10-26): `review_summary`**
- Probed the reviews endpoint with real requests (details in plan 06, section 3, step 2). The Store `appreviews` URL redirects to the Store home page, so it was dropped. `api.steampowered.com/IUserReviewsService/GetAppReviews/v1/` works without a key.
- Decided to store only the review totals (one row per game per run), not single reviews. Reason: Stellaris alone has about 77,000 reviews, which is about 770 requests at 100 per page.
- Built the `review_summary` resource, 19 tests, and `notebooks/02_eda_reviews.ipynb` (with 9 proposals for dbt staging in section 10).
- First full run: `games` and `review_summary` together, 162 requests, about 7 minutes (12:29 to 12:36 Stockholm), no 429, load id `1793014149.3994608`. Result: 81 rows in `STEAM_RAW.REVIEW_SUMMARY`, one `collected_at`, no duplicates, no NULLs.
- Committed in 5 small commits, pushed, and **merged into `main`** through a pull request.

## 3. Current state (verify with me before assuming)

- `main` contains `games` and `review_summary`. I planned a new branch **`feat/steam-player-counts-ingestion`** from updated `main`. **Check `git status` and `git branch` first**: I may not have created it yet.
- Untracked and intentionally left out of git: `scratch/appdetails/`, `scratch/appreviews/` (probe scripts), `scratch/docs/07_...`, `08_...` and this file. Do not commit them and do not delete them.
- Snowflake: warehouse `STEAM_WH`, database `STEAM_DB`, schemas `STEAM_RAW`, `STAGING`, `INTERMEDIATE`, `MARTS`. Roles `STEAM_LOADER`, `STEAM_TRANSFORMER`, `STEAM_REPORTER`; users `DLT_USER`, `DBT_USER`, `STREAMLIT_USER`. See `docs/01` to `docs/05`.
- Tables in `STEAM_RAW`: `GAMES` (a Portal 2 test row with appid 620, plus 81 rows from 2026-10-23 and 81 rows from 2026-10-26) and `REVIEW_SUMMARY` (81 rows from 2026-10-26).
- dbt Core is initialised under `dbt_project/`, no models yet.
- Python 3.12 with `uv`. Groups: `ingestion` (dlt[snowflake], pandas, requests), `dev` (ipykernel, pytest, ruff), `transform`, `dashboard`.
- Code under `src/steam_data_platform/`:
  - `settings.py`: `GAME_APPIDS` (81 ids), `STORE_COUNTRY="se"`, `STORE_LANGUAGE="english"`, `REQUEST_PAUSE_SECONDS=2.0`.
  - `connections.py`: `loader_credentials()` reads `SNOWFLAKE_*` environment variables.
  - `ingestion/steam.py`: `SteamRequestError`, `SteamRateLimitError`, `get_with_retry(url, params, label)` (timeout, retry with backoff on 429, 5xx, timeouts and connection errors; stops after `MAX_ATTEMPTS`), `fetch_app_details`, `build_game_row`, `fetch_review_summary`, `build_review_row`, the resources `games` and `review_summary` (both `append`, explicit `collected_at`), and `steam_source`, which returns both resources. Constants: `REQUEST_TIMEOUT_SECONDS=10`, `MAX_ATTEMPTS=3`, `BACKOFF_SECONDS=30`, `PROGRESS_EVERY=10`.
  - `ingestion/pipelines_steam.py`: builds the pipeline (`pipeline_name="steam"`, `dataset_name="steam_raw"`) and runs it under `if __name__ == "__main__"`. It logs only the load ids, because dlt's full load summary contains the Snowflake account name.
- Run command: `uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam`
- **Do not run the full pipeline just for testing.** `append` adds rows on every run. One run per day at most. A run now means 162 requests; with player counts it will be about 243 and take about 10 minutes.
- To test a resource without Snowflake, iterate it directly in a small script (for example `list(review_summary([281990, 1257610, 99999999]))`). dlt resources are iterable. See `scratch/appreviews/` for examples.
- dlt by default alternates between the resources of one source, one row at a time, in a single thread (it showed as about 2.5 s per request in the log). Requests therefore stay one at a time. New resources must not use `parallelized=True`.
- Tests: `tests/test_steam_dlt.py`, 19 tests, all passing. Pattern: a hand-written `FakeResponse`, a `sleeps` fixture that replaces `time.sleep`, a `patch_get` fixture that makes `requests.get` answer from a list, and plain functions for the resource tests. Run with `uv run pytest -q`.
- Table facts: `collected_at` is `TIMESTAMP_LTZ(9)`; counts are `NUMBER(19,0)`; lists are `VARIANT`; prices are integer minor units in EUR.

## 4. Decisions already made

| Topic | Decision |
|---|---|
| Scope | 81 Paradox Interactive apps in `GAME_APPIDS`. Scope is the list, not Steam's publisher field. |
| API key | None. Public endpoints only. |
| Destination | Snowflake only, no DuckDB. |
| Pipeline design | One dlt pipeline, one source, three resources: `games` (done), `review_summary` (done), `player_counts` (this task). |
| Work order | `appdetails` (done), reviews (done), current players (next). |
| Write mode | `append` with our own `collected_at`, one row per game per run. |
| Raw layer | Faithful copy of what Steam sends. dbt cleans later (percent, types, flags). |
| Reviews | Totals only (`review_summary`). Single reviews are not loaded. |
| Orchestration | No Airflow for now. Later a simple scheduled batch script. Airflow is future work. |
| Reference repo | https://github.com/indiramahadiva/Flight-punctuality_4_DE25. Copy: `<source>.py` + `pipelines_<source>.py`, `tests/test_<source>_dlt.py` with `monkeypatch` and a hand-written `FakeResponse`, `docs/eda_findings.md` style, one EDA notebook per source. Not copied: Dagster, Docker, Terraform. |

**Still open (ask me when relevant):** whether Streamlit runs locally or inside Snowflake; time estimates in the proposal; the minimum number of reviews for comparisons (100 is only a proposal); the rule for repeated runs.

## 5. Open issues

- `DLT_USER` is a `PERSON` account (password plus MFA) but loads with a password only. I do not know why. `snowflake_setup/05_create_users.sql` still says `SERVICE`. Any scheduled run needs a non-interactive login (for example key-pair authentication).
- Why *Knights of Pen and Paper 2: Free Edition* (appid 794820, released and free) has zero reviews.
- Whether a review total can go down between two runs (needs more than one run).
- Notebook 01: the outputs for sections 2, 8, 9 and 10 now exist, but the text still says "not yet run". Update the text (ask me first).
- Small clean-ups: let `fetch_app_details` use `get_with_retry` (it still has its own copy of the retry code), and add a progress line to the `games` resource.
- Rule for repeated runs (proposal: one scheduled run per day, and use the latest `collected_at` for current-state questions).

## 6. Next task: current players (step D)

### What is NOT verified yet (do not assume any of this)

I have **not** tested this endpoint. Everything below is a guess to check:

- `https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=<appid>` probably works without an API key.
- The answer is probably `{"response": {"player_count": N, "result": 1}}`.
- For an unreleased game, a wrong appid or a game with no data, `result` may be something other than 1, or `player_count` may be missing. We do not know yet.
- `player_count` may be `0` for a real game with nobody playing, and that is different from "no data". The raw table must not turn a missing count into 0.
- The answer has no timestamp, so we add our own `collected_at`.
- There is no official rate limit for these endpoints. Unofficial notes are not a source.

### Things to think about before building

- **A player count is one moment, not a daily number.** "Players right now" depends on the time of day. A single daily snapshot at a random time is a weak measure. For the thesis, the run time should be about the same every day, and this must be stated under limits. More frequent snapshots are possible later but are out of scope now. Tell me what you think after the probe.
- **Request volume.** One more request per game means about 243 requests per run (81 each for `games`, `review_summary`, `player_counts`), at the same 2 s pause, one at a time. A run takes about 10 minutes. Check that the log still shows a steady pace.
- **Do not copy the retry code again.** Use `get_with_retry`.

### Plan (present to me and wait for my OK)

1. **Branch and housekeeping.** Confirm I am on a new branch from updated `main`. Optionally, first do the small clean-ups from section 5 (ask me which ones).
2. **One small probe script** (for example `scratch/probe_playercounts.py`; ask me before you suggest a folder), about 5 requests in total, with pauses. Print structure, not full JSON:
   - top-level keys and the `response` block
   - the fields and types of `player_count` and `result`
   - Stellaris (`281990`) and Portal 2 (`620`) for a normal game
   - an unreleased game (for example Prison Architect 2, `1257610`)
   - a fake appid (for example `99999999`)
   - whether it works without a key (it should, since we send none)
   - the HTTP status and what a failure looks like
3. **Design decision from what we see.** My starting idea is the same as the other two tables: table `player_counts`, one row per game per run, `append`, columns `steam_appid`, `collected_at`, `player_count`, and possibly the raw `result` code if it carries information. Decide after the probe, and explain the choice in plain words.
4. **Build the `player_counts` resource** in `steam.py` (or a new file if it gets long), following the same pattern as `review_summary`: `get_with_retry`, skip and count failures, stop on repeated 429, `logging`, a progress line every `PROGRESS_EVERY` games, an explicit timestamp, `columns` hint for `collected_at`. Add it to `steam_source`.
5. **Try it without Snowflake** on 3 apps (a normal game, an unreleased game, a fake id) by iterating the resource directly.
6. **Volume rule.** The probe is one game or a handful. The first full run happens only once, after we agree on the design, and it loads all three tables (about 243 requests, about 10 minutes). Check that today's run has not already happened (one run per day).
7. **Validate in Snowsight, then a notebook** (`notebooks/03_eda_player_counts.ipynb`, same style as notebooks 01 and 02, with the connection cell copied) and record findings and proposed dbt staging rules.
8. **Tests** with `monkeypatch` and `FakeResponse` in `tests/test_steam_dlt.py` (no real network, no Snowflake): good answer, missing `player_count`, `result` not 1, 429 stops the run, skipped games are counted, `0` players is kept as 0 and a missing count stays missing.
9. **Update `scratch/docs/06_dlt_ingestion_plan.md`** (status, endpoint table, step 3, decisions, next steps, session notes) with my permission for that file.
10. **Commits and pull request.** Small commits in conventional style. I run the git commands. Write me a detailed, beginner-friendly pull request description (what, why, what changed, how it was checked, limits, not included), as in the last PR.

### After player counts

A simple scheduled batch script with a non-interactive Snowflake login, the clean-ups from section 5, docs, then the dbt branches (`feat/dbt-sources`, `feat/dbt-staging`, `feat/dbt-intermediate`, `feat/dbt-marts`) and the Streamlit dashboard. dbt and Streamlit are out of scope until I say so.

## 7. Best-practice checklist for all code you show me

- Python 3.12, type hints, short docstrings, small single-purpose functions, clear names; match the style of the existing files.
- Secrets only from environment variables. Never print credentials, the Snowflake account name or full connection strings.
- Every HTTP call has a timeout, paced requests, retry with backoff on 429/5xx, and `raise_for_status()` (all of this is in `get_with_retry`, so use it).
- Treat `success=false`, missing keys and `None` explicitly; never assume a field exists. Keep zero and missing apart.
- Idempotency: choose the write disposition and primary key deliberately and explain the choice.
- Use `logging`, not `print`, in `src/`.
- Format and lint with `ruff` (`uv run ruff format src tests`, `uv run ruff check src tests`); test with `pytest`; manage dependencies with `uv` and keep `uv.lock` in sync.
- Run `ruff format` before the final `pytest` run, not after, so the last test result is for the final code.
- Do not commit data files, `.env`, `.dlt/secrets.toml` or caches. Keep the CSV exports from Snowsight out of the repo.
- Before committing a notebook, check its saved outputs for secrets, for example with `grep -n -i -E "snowflakecomputing|secret|\.aws" notebooks/*.ipynb`. The output should only show harmless text.
- Commits: small, conventional style (`feat(ingestion): ...`, `test(ingestion): ...`, `docs: ...`). Always ask me before committing or pushing.
- Update the session notes in `scratch/docs/06_dlt_ingestion_plan.md` as we go.

## 8. Tool tips from session 2 (they will save you time)

- When you paste a whole file over an old one in VS Code, press Ctrl+A and Delete first. In session 2, a pasted test was added below the old one, and the old copy kept failing.
- A notebook open in VS Code does not refresh when a file is changed from outside. Close the tab and choose "Don't Save", then reopen it. Saving the old view would overwrite the new text.
- If you edit a notebook file, use the notebook edit tool, not the normal edit tool. The normal read tool shows an old cached view after edits, so check the file on disk with a search if you are unsure. An empty `.ipynb` file cannot be read, and the write tool will not overwrite a file it has not read, so write a new file and move it over the empty one.
- dlt wraps any error raised inside a resource in `ResourceExtractionError`. In tests, expect that error and check `error.value.__cause__`.
- Windows with Git Bash: the repo shows LF/CRLF warnings. They are harmless.

## 9. Please begin by

1. Reading: `scratch/docs/06_dlt_ingestion_plan.md`, `notebooks/02_eda_reviews.ipynb`, `src/steam_data_platform/ingestion/steam.py`, `src/steam_data_platform/ingestion/pipelines_steam.py`, `settings.py`, `tests/test_steam_dlt.py`, `.env.example` (**not** `.env`), and `docs/01` to `docs/05`.
2. Checking `git status` and the current branch with me.
3. Telling me in a few sentences what you understood and what you are unsure about.
4. Presenting the plan for step D and waiting for my OK.
