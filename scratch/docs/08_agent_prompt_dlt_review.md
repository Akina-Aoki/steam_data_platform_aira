# Handoff prompt: Steam reviews ingestion (dlt, Snowflake)

Written 2026-10-23 at the end of session 1. It summarises what is done and gives the plan for the next task: the `appreviews` endpoint. Read it fully before doing anything.

## 0. Read this first: how you must work

I am Aira, a beginner data engineering student at Stockholms Tekniska Institut (STI). This is my graduation thesis (Examensarbete) and I have a deadline, so I want to move faster, but I still want to understand every step.

**Hard rules (never break these):**

1. **Never open, read, print, edit or ask for `.env`, `.dlt/secrets.toml`, or any file or value that holds a secret.** Use `.env.example` to see which variables exist. Never ask me to paste a password, key or token in chat. If an error message might contain a secret, tell me to check it before pasting.
2. **Do not create or edit files in my project, and do not run commands, unless I give permission for the specific file or task.** By default, show me the file path and the code in chat. I paste it into VS Code myself. Give terminal commands in their own fenced `bash` block (one command per block), I run them, and I paste the output back. (In session 1 I allowed Claude to write exactly two files: the EDA notebook and the 06 plan. That permission was for those files only.)
3. **Plan first.** Before any code, give me a short written plan for the step and wait for my OK.
4. **Never use DuckDB** anywhere in this project (not as a local destination, not for testing, not for EDA). dlt loads straight to Snowflake `STEAM_DB.STEAM_RAW`. I already removed `duckdb` from `pyproject.toml`.
5. **Ask before** anything that would be hard to undo: committing, pushing, installing packages, changing Snowflake objects, or anything that would send many requests to Steam.
6. **Do not guess about the API.** If something is unverified, say so, and give me a small test I can run.

**Style I want:**
- Plain, simple language ("dumb it down"). Short explanations of why, not only what. Diagrams are welcome.
- A few lines or one small file at a time, but with bigger steps than a tutorial, because of my deadline.
- Ask at most one question at a time, and only when it really blocks the work.
- End each step with a short summary: what we learned, what we decided, what is next.
- Be honest about outcomes: say if something failed, was skipped, or is unverified.

## 1. Project in one paragraph

**Working title:** *Paradox Interactive Game Analysis: A Modern Data Stack for Pricing, Reception and Player Activity on Steam.*

A batch data platform on public Steam data for the 81 games published by **Paradox Interactive**. Paradox is the stakeholder in a proof-of-concept scenario; the project is independent academic work, not affiliated with or endorsed by Paradox or Valve.

**Target flow:** Steam public endpoints -> Python + dlt -> Snowflake `STEAM_RAW` -> dbt Core (`STAGING` -> `INTERMEDIATE` -> `MARTS`) -> Snowsight + Streamlit.

**Business questions:** How are games priced and discounted across the portfolio? How do review sentiment, price and player counts relate? How do new releases compare with older ones and with flagship franchises?

**Known limits (state honestly in the thesis):** batch only; small hand-scoped sample; price and player history exist only from the first collection date; the Store endpoints are undocumented; Steam gives no sales or revenue figures, so reviews and player counts are proxies; findings show correlation, not causation.

## 2. What was done in session 1 (2026-10-23)

- Built and loaded the **`games` resource** from the Store `appdetails` endpoint: 81 Paradox games into `STEAM_DB.STEAM_RAW.GAMES` (81 requested, 81 fetched, 0 skipped, 0 failed, about 3.5 minutes at a 2 s pause, no 429). One extra test row for Portal 2 (appid 620) is in the table; queries exclude it with `steam_appid <> 620`.
- Hardened `steam.py`: a game that fails is logged and skipped; 429 and 5xx are retried with backoff; repeated 429 stops the run; explicit `collected_at` timestamp; `logging` instead of `print`. The pipeline logs only the load ids, because dlt's full load summary contains the Snowflake account name.
- Validated the table in Snowsight, then wrote `notebooks/01_eda_games.ipynb` (queries, what we saw, findings, proposed dbt staging rules). **I have not run that notebook yet.** Its sections 2, 8, 9, 10 are marked "not yet run".
- Rewrote `scratch/docs/06_dlt_ingestion_plan.md` (status, decisions, session notes).
- Made 4 commits on `feat/steam-dlt-ingestion`, pushed, opened a PR and **merged it into `main`** on GitHub.
- Not committed and intentionally left out: `scratch/explore_appdetails.py`, `scratch/probe_appdetails.py`, `scratch/docs/agent_prompt_steam_dlt_ingestion.md`.

## 3. Current state (verify with me before assuming)

- `main` contains the games ingestion. I planned a new branch **`feat/steam-reviews-ingestion`** from updated `main`. **Check `git status` and `git branch` first**: I may not have created it yet.
- Snowflake: warehouse `STEAM_WH`, database `STEAM_DB`, schemas `STEAM_RAW`, `STAGING`, `INTERMEDIATE`, `MARTS`. Roles `STEAM_LOADER`, `STEAM_TRANSFORMER`, `STEAM_REPORTER`; users `DLT_USER`, `DBT_USER`, `STREAMLIT_USER`. See `docs/01` to `docs/04`.
- dbt Core is initialised under `dbt_project/`, no models yet.
- Python 3.12 with `uv`. Groups: `ingestion` (dlt[snowflake], pandas, requests), `dev` (ipykernel, pytest, ruff), `transform`, `dashboard`.
- Code under `src/steam_data_platform/`:
  - `settings.py`: `GAME_APPIDS` (81 ids), `STORE_COUNTRY="se"`, `STORE_LANGUAGE="english"`, `REQUEST_PAUSE_SECONDS=2.0`.
  - `connections.py`: `loader_credentials()` reads `SNOWFLAKE_*` environment variables.
  - `ingestion/steam.py`: `SteamRequestError`, `SteamRateLimitError`, `fetch_app_details`, `build_game_row`, the `games` resource (`append`, JSON columns, explicit `collected_at` timestamp) and `steam_source`.
  - `ingestion/pipelines_steam.py`: builds the pipeline (`pipeline_name="steam"`, `dataset_name="steam_raw"`) and runs it under `if __name__ == "__main__"`.
- Run command: `uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam`
- **Do not run the full pipeline again just for testing.** `append` adds 81 rows per run. One scheduled run per day is the proposed rule.
- Table facts: `collected_at` is `TIMESTAMP_LTZ(9)`; lists are `VARIANT`; prices are integer minor units in EUR.
- Tests: none yet. Folders `tests/`, `sql/` are empty.

## 4. Decisions already made

| Topic | Decision |
|---|---|
| Scope | 81 Paradox Interactive apps in `GAME_APPIDS`. Scope is the list, not Steam's publisher field (The Kings' Crusade, appid 42920, has an empty publisher list). |
| API key | None. Public endpoints only. |
| Destination | Snowflake only, no DuckDB. |
| Pipeline design | One dlt pipeline, one source, three resources (`games`, `reviews`, `player_counts`). `games` is done. |
| Work order | `appdetails` (done), then reviews, then current players. |
| Games write mode | `append` with our own `collected_at`. |
| Raw layer | Faithful copy: prices as Steam sends them; lists as JSON in one column. dbt cleans later. |
| Orchestration | No Airflow for now. Later a simple scheduled batch script. Airflow is future work. |
| Reference repo | https://github.com/indiramahadiva/Flight-punctuality_4_DE25. Copy: `<source>.py` + `pipelines_<source>.py`, `tests/test_<source>_dlt.py` with `monkeypatch` and a hand-written `FakeResponse`, `docs/eda_findings.md` style, one EDA notebook per source. Not copied: Dagster, Docker, Terraform. |

**Still open (ask me when relevant):** reviews and player-count design (below); whether Streamlit runs locally or inside Snowflake; time estimates in the proposal.

## 5. Open issues from session 1

- Notebook sections 2, 8, 9, 10 not yet run; two games have no price and are neither free nor unreleased (unexplained); only 12 of 81 names compared with my key (the rest rely on the publisher check); the full `type = game` check is not done.
- The load log is silent for about 3.5 minutes. Add a progress line (for example every 10 games) in `steam.py`.
- Rule for repeated runs (proposal: one scheduled run per day; use the latest `collected_at` for current-state questions).
- `DLT_USER` is a `PERSON` account (password plus MFA) but loaded with a password only. I do not know why. `snowflake_setup/05_create_users.sql` still says `SERVICE`. Any scheduled run needs a non-interactive login (for example key-pair authentication).
- Tests, `docs/07_...` summary (same style as `docs/01` to `docs/04`) and my proposal rewrite are still to do.

## 6. Next task: the reviews endpoint (step C)

### What is NOT verified yet (do not assume any of this)

I have **not** tested any reviews endpoint. Everything below is a guess to check:

- `https://store.steampowered.com/appreviews/<appid>?json=1&num_per_page=5&cursor=*` probably works without a key and probably returns `success`, `query_summary` and a `reviews` list plus a `cursor`.
- `https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/` (takes `input_json`) may need a key. My account cannot get a key, so if it does we drop it.
- `query_summary` probably holds total positive and negative counts per game. `num_per_page=0` might return only the summary.
- The page size is probably capped (maybe 100). `cursor` values probably need URL-encoding. The end of the list is probably an empty `reviews` list or a repeated cursor.
- `recommendationid` is probably the review id.
- Unofficial third-party notes mention about 200 requests per minute for reviews, with no source from Valve. Treat as unverified. There is no official rate limit for Store endpoints.

### Plan (present to me and wait for my OK)

1. **Branch and housekeeping.** Confirm I am on a new branch from updated `main`. Optionally, first commit the small cleanup items: progress log line in `steam.py` and running the unrun notebook sections.
2. **One small probe script** (`scratch/probe_appreviews.py`), about 6 requests in total, one game only (Stellaris, `281990`), with pauses. Print structure, not the full JSON:
   - top-level keys and the `query_summary` block
   - the fields of one review (`recommendationid`, playtime, `voted_up`, timestamps, language, purchase type)
   - how the `cursor` works and what the last page looks like
   - the largest accepted page size
   - whether `num_per_page=0` returns only the summary
   - the second URL variant (`IUserReviewsService`), to see whether it needs a key
   - behaviour for an unreleased game (for example Prison Architect 2, `1257610`) and for a game with few reviews
3. **Design decision from what we see.** Our questions are about review sentiment against price and players, so we may not need every review. Options:
   - **A. Summary snapshot per game per run:** 1 request per game, `append` with `collected_at`, same pattern as `games`. Cheap and builds a sentiment history.
   - **B. Individual reviews:** `merge` on `recommendationid`, a few pages per game. Heavier on Steam; adds playtime and language.
   - **C. Both:** summary plus a small recent sample.
   My recommendation is to start with **A** and add **B** only if the thesis needs it. That is a recommendation, not a fact; decide after the probe.
4. **Build the `reviews` resource** in `steam.py` (or a new file if it gets long), following the same pattern as `games`: retry on 429/5xx, stop on repeated 429, skip and count failures, `logging`, small pauses, explicit timestamps.
5. **Volume rule.** The probe is one game. The first full run over 81 games happens only once, after we agree on the design, with a pause of at least 2 s, and with a cap on pages per game if we choose B.
6. **Validate in a notebook** (`notebooks/02_eda_reviews.ipynb`, same style as notebook 01) and record findings and staging rules.
7. **Tests** with `monkeypatch` and a `FakeResponse` (no real network, no Snowflake), then update `scratch/docs/06_dlt_ingestion_plan.md` session notes.

### After reviews

Current players (`GetNumberOfCurrentPlayers`, needs no key to be confirmed; the response has no timestamp so we add `collected_at`; check games that return no count), tests, scheduling with a non-interactive login, docs, then the dbt branches (`feat/dbt-sources`, `feat/dbt-staging`, `feat/dbt-intermediate`, `feat/dbt-marts`) and the Streamlit dashboard. dbt and Streamlit are out of scope until I say so.

## 7. Best-practice checklist for all code you show me

- Python 3.12, type hints, short docstrings, small single-purpose functions, clear names; match the style of the existing files.
- Secrets only from environment variables. Never print credentials, the Snowflake account name or full connection strings.
- Every HTTP call has a timeout, paced requests, retry with backoff on 429/5xx, and `raise_for_status()`.
- Treat `success=false`, missing keys and `None` explicitly; never assume a field exists.
- Idempotency: choose the write disposition and primary key deliberately and explain the choice.
- Use `logging`, not `print`.
- Format and lint with `ruff` (`uv run ruff format src`, `uv run ruff check src`); test with `pytest`; manage dependencies with `uv` and keep `uv.lock` in sync.
- Do not commit data files, `.env`, `.dlt/secrets.toml` or caches. Keep the CSV exports from Snowsight out of the repo.
- Commits: small, conventional style (`feat(ingestion): ...`, `chore: ...`, `docs: ...`). Always ask me before committing or pushing.
- Update the session notes in `scratch/docs/06_dlt_ingestion_plan.md` as we go.

## 8. Please begin by

1. Reading: `scratch/docs/06_dlt_ingestion_plan.md`, `notebooks/01_eda_games.ipynb`, `src/steam_data_platform/ingestion/steam.py`, `src/steam_data_platform/ingestion/pipelines_steam.py`, `settings.py`, `.env.example` (**not** `.env`), and `docs/01` to `docs/04`.
2. Checking `git status` and the current branch with me.
3. Telling me in a few sentences what you understood and what you are unsure about.
4. Presenting the plan for step C and waiting for my OK.
