# Handoff prompt: ingestion of `review_recent` and `achievements` (dlt, Snowflake)

Written 2026-11-02. The dbt intermediate work is **paused** on purpose. This task goes back to ingestion: two new dlt resources, built the same way as `games`, `review_summary` and `player_counts`. Read the whole file before doing anything.

## 0. How to work with me

I am Aira, a beginner data engineering student at Stockholms Tekniska Institut (STI). This is my graduation thesis and I have a deadline. I want to move fast, but I want to understand every step.

**Hard rules (never break these):**

1. **Never open, read, print, edit or ask for `.env`, `.dlt/secrets.toml`, key files or any value that holds a secret.** Use `.env.example` to see which variables exist. If an output might hold the Snowflake account name, tell me to replace it with `xxx` before I paste it. Never repeat it.
2. **Show code in chat. I paste it into VS Code and I run every command and every git command.** Do not create or edit project files and do not run commands, unless I give permission for that specific file or task. Give each terminal command in its own fenced `bash` block. You may edit markdown in `docs/` and `scratch/docs/` when I say so. Nothing else without asking.
3. **Plan first, then wait for my OK**, then the code. One small step per message, under about 20 lines, with the step number at the top ("Step 2 of 9, ...") and what success looks like.
4. **Never use DuckDB.** dlt loads straight to Snowflake `STEAM_DB.STEAM_RAW`.
5. **No Steam API key.** My account is restricted, so both endpoints below must work without one. If one needs a key, say so and stop.
6. **Do not guess about the API.** If something is unverified, say so and give me a small test to run. Do not write "probably" as if it were a fact.
7. **Do not run the full pipeline just to test.** `append` adds rows on every run. One full run per day at most, at about the same clock time.
8. **Ask before** committing, pushing, installing packages, changing Snowflake objects, or sending many requests to Steam. Check git state with me (`git status`, `git branch`); do not trust this file for it.
9. **Be honest.** Say what is verified and what is not. If a number comes from a hand count, say so.

**Style:** plain, simple words. Short reasons, not only what. One everyday comparison, then the real term. At most one new term per message. One recommendation, not a menu. Put comments in code that say why. Ask at most one question at a time, and only when it blocks the work. End each step with a short summary: what we learned, what we decided, what is next.

**Commits and PRs:** conventional style (`feat(ingestion): ...`, `test(ingestion): ...`, `docs: ...`). End each commit with a second `-m "Co-Authored-By: ..."` line (I have forgotten it before, remind me). PR text: first person, short sentences, no buzzwords, no "This PR ...", ending with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. You draft it, I post it.

## 1. The project in one paragraph

**Working title:** *Paradox Interactive Game Analysis: A Modern Data Stack for Pricing, Reception and Player Activity on Steam.* A batch data platform on public Steam data for the 81 games published by Paradox Interactive. Flow: Steam public endpoints -> Python + dlt -> Snowflake `STEAM_RAW` -> dbt Core (`STAGING` -> `INTERMEDIATE` -> `MARTS`) -> Streamlit. Independent academic work, not affiliated with Paradox or Valve.

**Why these two resources.** I want a Streamlit end analysis for Paradox only, in the spirit of SteamDB (most played, trending, popular releases). SteamDB blocked automated reading, so that layout comes from memory and is not verified. From the Steam Web API documentation (`steamapi.xpaw.me`) I chose two extra sources:

- **Recent reviews:** the last 30 days next to the all-time totals, to show who is doing well *right now*.
- **Achievement percentages:** how many players reach each achievement, a rough measure of how many players stick with a game.

I did **not** choose news/patch notes, the DLC list, or Steam's own rankings (the rankings need a key and are undocumented). Do not start those.

## 2. Current state (verify with me before assuming)

- `main` contains `games`, `review_summary`, `player_counts`, the key-pair login, and the dbt sources and staging models (PRs up to #12, `main` at `d5a98da` when I last looked).
- I am currently on branch `feat/dbt-intermediate`, with **no commits on it**. Untracked files in `scratch/` are on purpose out of git: do not commit or delete them.
- Code under `src/steam_data_platform/`:
  - `settings.py`: `GAME_APPIDS` (81 ids), `STORE_COUNTRY`, `STORE_LANGUAGE`, `REQUEST_PAUSE_SECONDS=2.0`.
  - `connections.py`: `loader_credentials()` (key-pair login for `DLT_USER`).
  - `ingestion/steam.py`: `SteamRequestError`, `SteamRateLimitError`, `get_with_retry(url, params, label, accept_statuses=())`, `fetch_*`, `build_*_row`, three `@dlt.resource` functions (all `append`), and `steam_source(appids)` which returns the three resources. Constants: `REQUEST_TIMEOUT_SECONDS=10`, `MAX_ATTEMPTS=3`, `BACKOFF_SECONDS=30`, `PROGRESS_EVERY=10`.
  - `ingestion/pipelines_steam.py`: builds the pipeline (`pipeline_name="steam"`, `dataset_name="steam_raw"`), logs only the load ids (dlt's full summary contains the Snowflake account name).
- Run command (one full run: 243 requests, about 10 minutes):

```bash
uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
```

- Tests: `tests/test_steam_dlt.py`, 39 tests when last counted. Pattern: a hand-written `FakeResponse`, a `sleeps` fixture that makes `time.sleep` instant, a `patch_get` fixture that makes `requests.get` answer from a list, plain functions for resource tests with `monkeypatch`. dlt wraps errors raised inside a resource in `ResourceExtractionError`, so tests check `error.value.__cause__`. Run with `uv run pytest -q`.
- dlt alternates between the resources of one source, one row at a time, in a single thread. Requests stay one at a time. **New resources must not use `parallelized=True`.**
- Table facts: `collected_at` is `TIMESTAMP_LTZ(9)`, counts `NUMBER(19,0)`, lists `VARIANT`.
- Last full run: 2026-10-30, 15:05 to 15:15 Stockholm time. I have not run dlt since.
- Reference repo: `indiramahadiva/Flight-punctuality_4_DE25` (pattern `<source>.py` + `pipelines_<source>.py`, `tests/test_<source>_dlt.py`, one EDA notebook per source). Stay close to it. Change something only when needed, and ask me first.

## 3. What is verified and what is not

**Verified (from my notes of 2026-10-26, on the reviews endpoint we already use):**

- The working URL is `https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/`. The input goes in as JSON in one parameter, `input_json`. The Store URL `store.steampowered.com/appreviews/...` redirects to the Store home page for us, so do not use it.
- The answer has `query_summary`, `reviews`, `cursor`, `day_range_used` and `total_matching`.
- `query_summary` holds **all-time** totals. They **stayed the same when I changed `day_range` and the language.** So `query_summary` can **not** give a 30-day count.
- `num_per_page=0` still returns 20 reviews. `num_per_page=1` works. The page limit is 100.
- Reading single reviews is too expensive (Stellaris alone has about 77,000 reviews).

**Unverified (a probe must settle each of these, do not assume):**

| # | Question | Why it matters |
|---|---|---|
| 1 | Does `total_matching` count only the reviews that match `day_range` and `review_type`? | If yes, we get recent counts in 1 to 3 requests per game. If no, `review_recent` is not worth building and we say so. |
| 2 | Does `review_type` (`positive` / `negative`) work in `input_json`? Does `day_range` need `filter: all`? | Decides the number of requests per game. |
| 3 | `GetGlobalAchievementPercentagesForApp/v2`: the exact answer. The xpaw docs list the request only (`gameid`), not the fields. I expect a list of achievements with a name and a percent, and I do not know if the percent is a number or text. | Decides the columns and the types. |
| 4 | What Steam sends for a game **with no achievements**, an **unreleased** game, and a **fake id**. A status code (404? 403? 200 with an empty list?) | Decides `accept_statuses` and whether "no data" gets a row. |
| 5 | Does the achievements answer show an achievement name only, or also a readable title? | The name may be a code, not display text. The readable title may need `ISteamUserStats/GetSchemaForGame`, which needs a key. If so, we keep the code only. |

## 4. Decisions already made / starting ideas

| Topic | Decision or starting idea |
|---|---|
| Pipeline | Same pipeline and source. Add two resources to `steam_source`. |
| Table names | `review_recent`, `achievements` (my names). |
| Write mode | `append` with our own `collected_at` for both. I first thought `replace` for achievements, then rejected it: if a run stops halfway on a 429, `replace` would wipe the games never reached. Percentages move slowly, but about 4,000 rows per run is nothing for Snowflake. |
| Raw layer | A faithful copy of what Steam sends. dbt cleans later (types, percentages, flags). |
| `review_recent` row | One row per game per run: `steam_appid`, `collected_at`, the window in days (30), recent positive, recent negative, recent total. **Final columns only after probe 1 and 2.** |
| `achievements` row | One row per game and achievement per run: `steam_appid`, `collected_at`, the achievement name, the percentage as Steam sends it. **Final columns only after probe 3.** |
| NULL vs 0 | Never turn a missing value into 0. A game with no achievements gets **no rows** (not 0%). A recent count of 0 is only stored if Steam really said 0. |
| Unreleased games | Decided after probe 4. Reviews gave zeros for them before. |
| Retry code | Reuse `get_with_retry`. Pass `accept_statuses` only if Steam uses a 4xx for "no data". Do not copy the retry loop. |
| Request volume | 243 requests now. Adding about 81 for achievements and 81 to 243 for recent reviews gives about 400 to 570 requests, about 17 to 25 minutes at the 2 s pause. State the real number once the design is fixed, and ask me before the first full run. |
| Orchestration | None. I run dlt by hand. Airflow is future work. |
| Out of scope | dbt models for these two (separate branch afterwards), Streamlit, news, DLC, rankings. |

## 5. Plan (present your version to me and wait for my OK)

| Step | What | Who |
|---|---|---|
| 1 | Check `git status` and `git branch` with me. New branch from updated `main`: `feat/ingest-recent-reviews-achievements`. One git command per message. | me |
| 2 | **Probe** both endpoints on one game (Stellaris, `281990`). See section 6. About 8 requests in total, 2 s apart, printing structure, not full JSON. | I run, you read |
| 3 | Decide the columns and the rules for "no data" from what we saw. Explain in plain words and wait for my OK. | both |
| 4 | Write `fetch_review_recent`, `build_review_recent_row` and the `review_recent` resource in `steam.py`, then tests. Follow `review_summary` exactly: skip and count failures, stop on repeated 429, `logging`, a progress line every `PROGRESS_EVERY` games, a `columns` hint for `collected_at`. | you show, I paste |
| 5 | Same for `fetch_achievements`, `build_achievement_row` and `achievements`. | you show, I paste |
| 6 | Add both resources to `steam_source`. Run `uv run ruff format src tests`, then `uv run ruff check src tests`, then `uv run pytest -q`. | I run |
| 7 | Try each resource on 3 apps **without Snowflake** (a normal game, an unreleased game, a fake id) by iterating the resource directly, for example `list(review_recent([281990, 1257610, 99999999]))`. | I run |
| 8 | One full run, only after we agree on the design and the request count. Check that today's run has not happened yet. Then check the load in Snowsight (`_DLT_LOADS` status 0, 81 games in `REVIEW_RECENT`, expected rows in `ACHIEVEMENTS`). | I run |
| 9 | With my OK for each file: notebooks `04_eda_review_recent.ipynb` and `05_eda_achievements.ipynb` (same style as notebooks 01 to 03), `scratch/docs/06_dlt_ingestion_plan.md` (status, endpoint table, decisions, session notes), and a new doc in `docs/` (`11_...`, decisions with reasons and a code map with line links). | later |
| 10 | Small commits, push, PR text. I run git. | me |

## 6. Step 2: the probes (give me these, I run them and paste the output)

**Reviews.** 4 requests on Stellaris. Compare `total_matching` across the lines:

```bash
uv run python - <<'EOF'
import json, time, requests

URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
tests = {
    "all time": {},
    "30d all": {"day_range": 30, "filter": "all"},
    "30d positive": {"day_range": 30, "filter": "all", "review_type": "positive"},
    "30d negative": {"day_range": 30, "filter": "all", "review_type": "negative"},
}
for label, extra in tests.items():
    options = {"appid": 281990, "num_per_page": 1, "language": "all", **extra}
    r = requests.get(URL, params={"input_json": json.dumps(options)}, timeout=10)
    block = r.json()["response"]
    summary = block.get("query_summary", {})
    print(label, "| total_reviews:", summary.get("total_reviews"),
          "| total_matching:", block.get("total_matching"),
          "| day_range_used:", block.get("day_range_used"))
    time.sleep(2)
EOF
```

How to read it: `total_matching` much smaller than all-time, and "30d positive" plus "30d negative" about equal to "30d all", means recent counts work. If `total_matching` is empty or the same on every line, the shortcut does not work. Then stop and tell me, and do not build `review_recent`.

**Achievements.** One game with achievements first:

```bash
uv run python - <<'EOF'
import requests

URL = "https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/"
r = requests.get(URL, params={"gameid": 281990}, timeout=10)
print(r.status_code)
body = r.json()
items = body.get("achievementpercentages", {}).get("achievements", [])
print(len(items), "achievements")
print(items[:3])
print([type(item.get("percent")).__name__ for item in items[:3]])
EOF
```

Then, 2 s apart, an unreleased game (Prison Architect 2, `1257610`) and a fake id (`99999999`). Print the status code, the content type and the first 200 characters of the body, because the answer may not be JSON. Also pick one released Paradox game that I suspect has no achievements, if the first results suggest one. Do not run all 81 games.

## 7. Best-practice checklist for all code you show me

- Python 3.12, type hints, short docstrings, small single-purpose functions, names and comments that match the style of `steam.py` (simple words, comments that say why).
- Secrets only from environment variables. Never print credentials, the account name or connection strings.
- Every HTTP call goes through `get_with_retry` (timeout, pause, backoff on 429 and 5xx).
- Treat missing keys, `None`, empty lists and wrong types explicitly. Keep zero and missing apart. Check that a percentage is a number before keeping it.
- Use `logging`, not `print`, in `src/`.
- Tests: no real network, no Snowflake. Cover a good answer, an empty answer, a wrong type, zero kept as zero, a 4xx that means "no data", a 429 that stops the run, and skipped games being counted.
- Run `ruff format` before the final `pytest`, so the last test result is for the final code.
- When I paste a whole file over an old one in VS Code, I press Ctrl+A and Delete first (a pasted test once stayed below the old copy).
- Before committing a notebook, check its saved outputs for secrets with `grep -n -i -E "snowflakecomputing|secret|\.aws" notebooks/*.ipynb`.
- Do not commit data files, `.env`, `.dlt/secrets.toml` or caches.
- Windows with Git Bash: LF/CRLF warnings are harmless.

## 8. Please begin by

1. Reading: `scratch/docs/06_dlt_ingestion_plan.md`, `docs/08_steam_py_code_guide.md`, `src/steam_data_platform/ingestion/steam.py`, `src/steam_data_platform/ingestion/pipelines_steam.py`, `src/steam_data_platform/settings.py`, `tests/test_steam_dlt.py`, `.env.example` (**not** `.env`).
2. Checking `git status` and `git branch` with me, one command at a time.
3. Telling me in three short sentences what you understood and what you are unsure about.
4. Giving me **one** thing to do: the branch commands (step 1), then the probes (step 2). Then wait.
