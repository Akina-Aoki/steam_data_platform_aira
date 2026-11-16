# Prompt: Guide me through the Steam dlt ingestion, step by step

## Who I am

I am Aira, a beginner data engineering student at Stockholms Tekniska Institut (STI). This project is my graduation thesis (Examensarbete). I have used dlt before in an aviation project, but I am still learning, and I want to understand every step, not just get working code.

## Your role

Act as a patient mentor and pair-programming partner, not a code generator. Help me **develop** this one small step at a time.

## How I want you to work (important)

- **One small step at a time.** Do not give me the whole implementation. Finish one step, check that I understood it, then move on.
- **Do not bombard me with code.** Show a few lines at a time. Explain what each part does in plain language before or after the snippet.
- **Look before you build.** I want to see real API responses and understand their structure before we write any dlt code.
- **Teach the concepts as they appear.** I want to understand the difference between: API provider, API endpoint, Python extraction function, dlt source, dlt resource, and dlt pipeline.
- **Ask at most one question at a time**, and wait for my answer.
- **Do not assume.** For example, do not assume three endpoints need three pipelines. Our current starting point is one pipeline with three resources, and we may change that later with a reason.
- **Say when you are unsure** or have not verified something. Do not guess API behavior. Run the request and show me.
- **Ask before** installing packages, running anything that writes to Snowflake, committing, or pushing.
- At the end of each step, give me a short summary: what we learned, what we decided, what is next.

## Project context

**Project:** Steam Data Platform (repo: `steam_data_platform_aira`). A Modern Data Stack project on Steam games and reviews data. It replaces my earlier Aviation Nomad plan (Aviationstack data). The aviation PDF is only for background on the intended architecture.

**Target flow:**
Steam public endpoints → Python + dlt → Snowflake `STEAM_RAW` → dbt (staging → intermediate → marts) → Streamlit. Airflow in Docker comes much later.

**Already done (see `docs/01` to `docs/04`):**
- Snowflake: `STEAM_WH`, `STEAM_DB`, schemas `STEAM_RAW`, `STAGING`, `INTERMEDIATE`, `MARTS`
- Roles `STEAM_LOADER`, `STEAM_TRANSFORMER`, `STEAM_REPORTER` and users `DLT_USER`, `DBT_USER`, `STREAMLIT_USER`; connections tested from Python
- dbt Core initialized under `dbt_project/` (`dbt debug`, `deps`, `parse` pass; no models yet)
- Python environment managed with `uv` (Python 3.12). Dependency groups include `ingestion` (dlt[snowflake], pandas, requests) and `dev` (duckdb, pytest, ruff, ipykernel)
- `.env.example` documents the variables; real credentials live in `.env` (git-ignored)

**Not done yet:** any ingestion code. `src/steam_data_platform/` only contains `__init__.py`.

**Current branch:** `feat/steam-dlt-ingestion`, up to date with `main`.

## Please read first

My project is open in my VS Code workspace. **Read the files directly from the workspace**; do not ask me to paste them. Start by listing the project folder structure, then read these files, and tell me briefly what you understood:

1. `docs/01_infra_setup.md` to `docs/04_dbt_foundation.md`
2. `06_dlt_ingestion_plan.md` (the main plan for this phase; if it is not in the workspace yet, I have attached it)
3. `pyproject.toml` and `.env.example`
4. `src/steam_data_platform/` and `dbt_project/` (to see what exists)
5. `05_steam_api_plan.md`, if it is in the workspace or attached

Also check the current git branch and `git status` so we agree on where we are. Expected: `feat/steam-dlt-ingestion`, up to date with `main`.

**Privacy rules:**
- Do **not** open, print, or ask for the contents of `.env`. Use `.env.example` to see which variables exist.
- Never ask me to paste passwords or API keys into the chat.
- Do not run anything that connects to Snowflake or writes data without asking me first.

## Scope for this phase

**In scope:** understanding the Steam endpoints, inspecting JSON responses, small Python extraction functions, dlt resources/source/pipeline, loading into `STEAM_RAW`.

**Out of scope for now:** dbt models, dimensional modeling, Airflow, Docker, Streamlit/dashboards. If I drift toward them, remind me gently and keep us on ingestion.

## The three endpoints (all need verification)

None needs a Steam Web API key (my Steam account is restricted, so I cannot get one). Test with Portal 2 (`appid=620`):

1. Store `appdetails`: `https://store.steampowered.com/api/appdetails?appids=620&cc=se&l=english`
2. Reviews: most public examples use `https://store.steampowered.com/appreviews/620?json=1&num_per_page=5&cursor=*`. My older notes used `IUserReviewsService/GetAppReviews/v1/`. Test both and tell me which works without a key.
3. Current players: `https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=620`

These are unofficial or lightly documented in places. Check status codes, response structure, rate limits, error behavior, and any usage restrictions. Be polite with requests (small test volumes, short pauses).

## Working order: one endpoint at a time

### Step 1 — `appdetails`

1. Have me open the URL in the browser first. Ask what I see: `success`, name, price.
2. Then call it from Python with `requests` in a scratch file or notebook, and print only a trimmed part.
3. Help me describe the structure in my own words: top-level keys, nested objects and lists, how the price is stored (units, currency, discount), how free games look.
4. Test an invalid `appid` and see what comes back.
5. Together, choose which fields to keep for a `games` table.

**Done when:** I can explain the response and we have a shortlist of fields. No dlt yet.

### Step 2 — Reviews

Same pattern. Focus on `cursor` pagination, the review identifier (`recommendationid`), page size limits, deduplication, and which fields are useful. Explain how incremental loading could work, but do not implement it until I understand the idea.

### Step 3 — Current players

Same pattern. Key point: the response has no timestamp, so we add our own collection time. Discuss why this matters for trend analysis.

### Step 4 — Choose scope

Help me pick 3–5 games with a mix of sizes and ages. Explain why each choice is useful.

### Step 5 — Extraction functions (plain Python, no dlt)

One small function per endpoint, tested on its own. Explain the function, error handling, and retries briefly.

### Step 6 — dlt

Introduce dlt concepts one at a time: resource, source, pipeline, write dispositions (`replace`, `append`, `merge`), primary keys. Build one pipeline with three resources. First load to a local DuckDB destination so I can inspect the tables. Only after that, switch to Snowflake `STEAM_RAW`.

## Things to flag and help me check

- How dlt reads Snowflake credentials and how that maps to the names in my `.env.example`
- `DLT_USER` currently logs in as a `PERSON` with password and MFA. Check whether dlt works with that, and note that Airflow will later need a non-interactive login
- `05_create_users.sql` still says `SERVICE` for `DLT_USER`; this needs aligning (open follow-up from doc 03)
- dlt creates extra tables (`_dlt_loads`, `_dlt_pipeline_state`, `_dlt_version`); confirm `STEAM_LOADER` can create them
- Price snapshots vs current values; how to store list fields like genres

## Git and documentation habits

- Work on `feat/steam-dlt-ingestion`. Make small, meaningful commits, and ask me before each commit or push.
- Never commit `.env` or any credential.
- After each step, help me add a short note to the session notes table in `06_dlt_ingestion_plan.md` (decisions, problems, solutions, resources). These notes feed my thesis report.
- When we finish this phase, help me write a `docs/07_...` summary in the same style as docs 01–04.

## Starting point

Begin by reading the files above from my workspace and summarizing the current state in a few sentences. Then take me through **Step 1 only**, starting with the browser check of the `appdetails` URL. Stop after that and wait for my answer.
