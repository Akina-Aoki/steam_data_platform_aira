# Handoff prompt: start of the dbt phase (sources first), Snowflake + dbt Core

Written 2026-10-30 at the end of session 4. It summarises what is done and gives the plan for the next task. Read it fully before doing anything.

## 0. Read this first: how you must work

I am Aira, a beginner data engineering student at Stockholms Tekniska Institut (STI). This is my graduation thesis (Examensarbete) and I have a deadline, so I want to move faster, but I still want to understand every step.

**Hard rules (never break these):**

1. **Never open, read, print, edit or ask for `.env`, `.dlt/secrets.toml`, or any file or value that holds a secret.** That includes private keys (the `.p8` file) and key files for Snowflake. Use `.env.example` to see which variables exist. Never ask me to paste a password, key or token in chat. If an error message or a notebook output might contain a secret (for example the Snowflake account name in a connection error), tell me to check it and replace it with `xxx` before pasting.
   - `dbt_project/profiles.yml` exists in the repo folder. **I have not checked what is in it.** Before you open it, ask me. It should only use `env_var(...)`, but do not assume.
2. **Do not create or edit code files, and do not run commands, unless I give permission for the specific file or task.** By default, show me the file path and the code in chat. I paste it into VS Code myself. Give terminal commands in their own fenced `bash` block (one command per block), I run them, and I paste the output back.
   - **What I have allowed so far** (so you do not need to ask each time): editing markdown files in `docs/` and `scratch/docs/`, and changing text lines in the notebooks. In session 4 I also once asked you to fix a broken test file yourself. That does not carry over. For `src/`, `tests/`, SQL files, dbt models and config, show the code and wait, or ask first.
   - Read-only tools (Read, Grep, Glob) are fine.
3. **Plan first.** Before any code, give me a short written plan for the step and wait for my OK.
4. **Never use DuckDB** anywhere in this project. dlt loads straight to Snowflake `STEAM_DB.STEAM_RAW`.
5. **Ask before** anything that would be hard to undo: committing, pushing, installing packages, changing Snowflake objects (users, keys, grants), or anything that sends many requests to Steam. I run all git commands. **Never commit on `main`**: create a branch first.
6. **Do not guess about the API, about Snowflake or about dbt.** If something is unverified, say so, and give me a small test I can run. Do not write "probably" as if it were a fact in a notebook or doc. When you read the web, you may use the web-fetch agent for public pages. Its report is model output, so say what is verified and what is the agent's summary.
7. **Stay close to the reference repo.** I copy the structure of https://github.com/indiramahadiva/Flight-punctuality_4_DE25 (and my lecture repo https://github.com/Akina-Aoki/AiraTheSnowFairy, folder `09_setup_dbt/`). In session 4 you suggested a wrapper script and Windows Task Scheduler. I said no, because they are not in the reference repo. Do not add infrastructure that is not in the reference repo or that I did not ask for. If you think something extra is needed, say why in two sentences and let me decide.

**Style I want:**
- Plain, simple language ("dumb it down"). Short explanations of why, not only what. Tables are welcome. When I say I do not understand something, go one level simpler, use an everyday comparison, and then ask one short question.
- Keep PR descriptions and replies short and simple. PR text must sound like a student wrote it: first person, short sentences, no buzzwords, no "This PR ...". I tell you if I want more detail. Draft the PR text for me each time.
- Docs and notebook text like a student's own notes: short sentences, no filler. I edit the notebook text myself afterwards, so **read the current text of a cell before you change it, and never rewrite a whole cell from an old copy**. My notebook style: `**💡Insights:**` with bullets and small tables. For dbt findings I use one small table per finding (Findings, Why it matters, What dbt does, Layer).
- A few lines or one small file at a time, but with bigger steps than a tutorial, because of my deadline.
- Ask at most one question at a time, and only when it really blocks the work.
- End each step with a short summary: what we learned, what we decided, what is next.
- Be honest about outcomes: say if something failed, was skipped, or is unverified. If a number comes from a hand count or a partial view, say so. **If you made a mistake, say so plainly** (in session 4 you told me twice that a file was not in Git, and it was).
- Docs in `docs/` (the folder we push to GitHub) use tables, clickable relative links to code lines, and give the reason for every decision. Links in `docs/` must not point to files in `scratch/`.

## 1. Project in one paragraph

**Working title:** *Paradox Interactive Game Analysis: A Modern Data Stack for Pricing, Reception and Player Activity on Steam.*

A batch data platform on public Steam data for the 81 games published by **Paradox Interactive**. Paradox is the stakeholder in a proof-of-concept scenario; the project is independent academic work, not affiliated with or endorsed by Paradox or Valve.

**Target flow:** Steam public endpoints -> Python + dlt -> Snowflake `STEAM_RAW` -> dbt Core (`STAGING` -> `INTERMEDIATE` -> `MARTS`) -> Snowsight + Streamlit.

**Business questions:** How are games priced and discounted across the portfolio? How do review sentiment, price and player counts relate? How do new releases compare with older ones and across genres? (Franchise comparison was dropped on 2026-11-05, see `docs/13_conceptual_model.md`.)

**Known limits (state honestly in the thesis):** batch only; small hand-scoped sample; price, review and player history exist only from the first collection date; the Store endpoints are undocumented; Steam gives no sales or revenue figures, so reviews and player counts are proxies; a player count is one moment and depends on the hour; findings show correlation, not causation.

## 2. What was done so far

**The dlt extract and load part is done for all three sources. The login uses a key pair. dbt has not started (no models yet).**

| Session | Date | Work |
|---|---|---|
| 1 | 2026-10-23 | `games` (Store `appdetails`): 81 games. Doc 05, notebook 01. |
| 2 | 2026-10-26 | `review_summary` (`GetAppReviews`, totals only). PR #6. Doc 06, notebook 02. |
| 3 | 2026-10-27 | `player_counts` (`GetNumberOfCurrentPlayers`). PR #7. Doc 07, notebook 03. |
| 4 | 2026-10-30 | Clean-up (`fetch_app_details` uses `get_with_retry`, progress line for `games`, simpler comments, 3 new tests). Guide `docs/08_steam_py_code_guide.md`. Docs and notebook 01 text fixed. **Key-pair login for `DLT_USER`** (`docs/09_key_pair_login.md`). First **full pipeline run with the key**. Notebooks 01 to 03 connect with the key. |

**Run history (clock times are Stockholm time, they differ from day to day):**

| Date | Time | Load id | Tables |
|---|---|---|---|
| 2026-10-23 | about 14:09 | `1792757384.0749068` | `games` |
| 2026-10-26 | 12:29 to 12:36 | `1793014149.3994608` | `games`, `review_summary` |
| 2026-10-27 | 10:43 to 10:53 | `1793094197.9862032` | all three |
| 2026-10-30 | 15:05 to 15:15 | `1793369111.4503539` | all three, with the key login, 81 rows each, status 0 |

## 3. Current state (verify with me before assuming)

- **Git:** my last pushed commit is `03f09a3` on branch `feat/schedule-run` (notebooks use the key). **I had trouble finding the "create pull request" button on GitHub, so that PR may not exist or may not be merged.** Check `git log`, `git branch` and `git status` with me first. Doc 05 and the plan file may or may not be committed. I run all git commands.
- Untracked and intentionally left out of git: `scratch/appdetails/`, `scratch/appreviews/`, `scratch/playercounts/` (probe scripts), `scratch/docs/07_...` to `11_...` (handoff prompts) and `scratch/login_check.py`. Do not commit or delete them. **`scratch/docs/06_dlt_ingestion_plan.md` IS tracked in Git** (session notes). `scratch/docs/05_steam_api_plan.md` too.
- **Snowflake:** warehouse `STEAM_WH`, database `STEAM_DB`, schemas `STEAM_RAW`, `STAGING`, `INTERMEDIATE`, `MARTS`. Roles `STEAM_LOADER`, `STEAM_TRANSFORMER`, `STEAM_REPORTER`. Users `DLT_USER`, `DBT_USER`, `STREAMLIT_USER`. See docs 01 to 03. Check the grants of `STEAM_TRANSFORMER` in `docs/02` and `snowflake_setup/` before the first dbt run. I have not re-checked them in this session.
- **Tables in `STEAM_RAW`** (all loads are `append`, one row per game per run):

| Table | Snapshots now | Columns |
|---|---|---|
| `GAMES` | 4 of 81 rows (10-23, 10-26, 10-27, 10-30) plus one old Portal 2 test row (appid 620, load `1792747270.0447536`) | `steam_appid`, `collected_at`, `name`, `type`, `is_free`, `required_age`, `short_description`, `website`, `release_date_text`, `coming_soon`, `price_currency`, `price_initial`, `price_final`, `discount_percent`, `metacritic_score`, `recommendations_total`, `platform_windows/mac/linux`, and four `VARIANT` lists: `developers`, `publishers`, `genres`, `categories` |
| `REVIEW_SUMMARY` | 3 of 81 rows (10-26, 10-27, 10-30) | `steam_appid`, `collected_at`, `review_score`, `review_score_desc`, `total_positive`, `total_negative`, `total_reviews` |
| `PLAYER_COUNTS` | 2 of 81 rows (10-27, 10-30) | `steam_appid`, `collected_at` (**per row**), `player_count` (NULL = no data, 0 = real zero), `result` (1 = count, 42 = no data) |

  All tables also have `_dlt_load_id` and `_dlt_id`. `collected_at` is `TIMESTAMP_LTZ(9)`, counts are `NUMBER(19,0)`, prices are integer minor units in EUR. In `games` and `review_summary`, `collected_at` is one time per run. dlt also made `_DLT_LOADS`, `_DLT_PIPELINE_STATE`, `_DLT_VERSION`.
- **dbt Core is initialised under `dbt_project/`, with no models yet.** What exists: `dbt_project.yml` (models folders `staging` = view in schema `staging`, `intermediate` = view in `intermediate`, `marts` = table in `marts`), `profiles.yml` (not read, see rule 1), `packages.yml` and `package-lock.yml` (**`dbt_utils` 1.4.1, `dbt deps` was run**, so a `unique` test on two columns is possible), `macros/generate_schema_name.sql`, and empty `seeds/`, `snapshots/`, `tests/` with `.gitkeep`. **There is no `models/` folder yet.** Doc: `docs/04_dbt_foundation.md`.
  - **Check before the first run:** `generate_schema_name.sql` makes models land in the schema named in `dbt_project.yml` (`STAGING` and so on), not in my personal dev schema `dbt_aira` (`DBT_SCHEMA` in `.env.example`). Doc 04 says "Schema naming has been parsed but not yet verified through model execution." So **a dev `dbt run` may write into the real `STAGING` schema.** Talk to me about this before the first `dbt run`.
  - I have not written down in this prompt how I run dbt (the exact command and the `--profiles-dir`). Ask me, and look at doc 04.
- **Python:** 3.12 with `uv`. Groups: `ingestion` (dlt[snowflake], pandas, requests), `dev` (ipykernel, pytest, ruff), `transform`, `dashboard`.
- **Code** under `src/steam_data_platform/`: `settings.py` (`GAME_APPIDS` with 81 ids, `STORE_COUNTRY="se"`, `STORE_LANGUAGE="english"`, `REQUEST_PAUSE_SECONDS=2.0`), `connections.py` (`loader_credentials()` reads `SNOWFLAKE_*` variables and passes `private_key_path`), `ingestion/steam.py` (one file, I decided to keep it as one file), `ingestion/pipelines_steam.py`. Tests: `tests/test_steam_dlt.py` and `tests/test_connections.py`, **39 tests, all passing**. Run `uv run ruff format src tests`, then `uv run ruff check src tests`, then `uv run pytest -q`.
- **Run command (by hand, once a day at most, 243 requests, about 10 minutes):**
  `uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam`
  Never run the full pipeline just for testing: `append` adds rows on every run. The next normal run can be 2026-10-31. Start it at about the same clock time, because a player count depends on the hour. **My runs so far were at 10:43 and 15:05, so we need to agree on one hour.**
- **Docs** `docs/01` to `docs/09`. Doc 08 is a guide to read next to `steam.py` (line links). Doc 09 is the key-pair login. Notebooks `notebooks/01_eda_games.ipynb`, `02_eda_reviews.ipynb`, `03_eda_player_counts.ipynb`; each has a section with dbt staging proposals (notebook 01 section 11, notebooks 02 and 03 section 10).

## 4. Decisions already made

| Topic | Decision |
|---|---|
| Scope | 81 Paradox Interactive apps in `GAME_APPIDS`. The scope is the list, **not** the Steam publisher field (*The Kings' Crusade* has an empty publisher list). |
| API key | None. Public endpoints only. |
| Destination | Snowflake only, no DuckDB. |
| Pipeline design | One pipeline, one source, three resources, one `steam.py`. |
| Write mode | `append`, one row per game per run. |
| Raw layer | Faithful copy of what Steam sends. dbt cleans later. |
| Reviews | Totals only. Single reviews are not loaded. |
| Player counts | A 404 / `result` 42 is stored as a row with NULL `player_count`. A real 0 stays 0. |
| Loader login | **Key pair** for `DLT_USER` (private key file outside the repo, path in `SNOWFLAKE_LOADER_PRIVATE_KEY_PATH`). `DLT_USER` stays `PERSON`, the password is still set as a fallback. |
| Why | Snowflake is phasing out password-only sign-in for `PERSON` users (phase 3 planned Aug to Oct 2026 per account, "subject to change"). Whether it blocks dlt is our reading, not stated by Snowflake. Default `TYPE` is `PERSON` (docs). `05_create_users.sql` has no `TYPE` line for `DLT_USER`, like the reference repo. |
| Scheduling | **By hand, once a day. No Task Scheduler, no wrapper script. Airflow is future work.** |
| dbt findings | Proposals are in the notebooks and in docs 05 to 07. They are not built yet. |

**Still open (ask me when relevant):** whether Streamlit runs locally or inside Snowflake; time estimates in the proposal; how dbt logs in (see section 5).

## 5. Open issues

- **How does `DBT_USER` log in?** `DBT_USER` and `STREAMLIT_USER` are `PERSON` users with passwords in `.env`. They have the same risk as `DLT_USER` had (Snowflake's MFA rollout). Decide with me: password for now and key pair later, or a key pair from the start (dbt-snowflake supports key-pair login, but **check its docs for the exact setting names, do not guess**). Changing a Snowflake user or key is hard to undo: ask first, and never read the key file. I did it for `DLT_USER` in `docs/09_key_pair_login.md`: same steps (`openssl` in Git Bash, `ALTER USER ... SET RSA_PUBLIC_KEY`).
- Notebook text is behind the data: notebook 01 section 2 says a rerun "would show 3" per game (it is 4 now, better: "more than 1"); the notebooks' text and saved outputs are from the earlier snapshots. I did not save the outputs of my last "run all". Notebook 03 text about the 13 zero rows was never checked.
- The password is still set on `DLT_USER`. Later: remove it, or change the type to `SERVICE` (read Snowflake's docs first: a `SERVICE` user cannot sign in with a password, and `ALTER USER ... SET TYPE` exists).
- What `result` 42 means exactly (unverified); whether a released game can ever get 404 / 42.
- Whether a review total can go down between two runs (now 3 snapshots, so this can be checked with a `LAG` query).
- Why *Knights of Pen and Paper 2: Free Edition* has zero reviews and zero players.
- Why *Majesty 2 Collection* (73020) and *Galaxy of Pen & Paper +1* (349790) have no price although they are not free and not unreleased.
- Compare all 81 names with Steam's publisher page, not only 12.
- I noticed a line in the pipeline log: botocore "Found credentials in shared credentials file: ~/.aws/credentials". Not investigated. As far as I know it is harmless, but that is unverified.

## 6. Next task: the dbt phase

Suggested order. Ask me which to start with, and do one at a time:

0. **Housekeeping:** check `git log`, `git branch`, `git status` with me. Is the `feat/schedule-run` PR open or merged? Sync `main`. Create a new branch for the next step.
1. **dbt login and how to run dbt.** Ask me how I run dbt (command, `--profiles-dir`), run `dbt debug` (I run it), and decide how `DBT_USER` logs in (section 5). Do not read `.env` or the key.
2. **`feat/dbt-sources`:** define the three sources in `STEAM_RAW` (`games`, `review_summary`, `player_counts`) in a YAML file with tests that make sense on raw data (for example `not_null` on `steam_appid` and `collected_at`). Think about `loaded_at_field` and freshness (the data only changes when I run the pipeline by hand, so a strict freshness check would be noisy: ask me). Look at the reference repo's dbt folder for the structure first. Plan first, show me the files, then I paste.
3. **`feat/dbt-staging`:** one `stg_` model per source, using the proposals in notebook 01 section 11, notebook 02 section 10 and notebook 03 section 10. Main ideas (all proposals, to confirm with me):
   - Filter on the project's game list (a seed or a source list built from `GAME_APPIDS`), not on the publisher field. Exclude the Portal 2 test row (appid 620).
   - `games`: prices divided by 100 (keep NULL, keep `is_free` and `coming_soon` as flags so a missing price is never read as 0); parse the free-text release date and keep the original text; UTC conversion of `collected_at`; unpack the `VARIANT` lists with `LATERAL FLATTEN` (one row per game and value, remove duplicates); decode HTML entities in `short_description` in one place (a macro).
   - `review_summary`: `pct_positive = total_positive / NULLIF(total_reviews, 0)`, a `has_reviews` flag, keep the label raw (free text, and score 0 means both "no reviews" and "1 review").
   - `player_counts`: never turn NULL into 0, add `has_player_data` from `result = 1`, `accepted_values` on `result` (1 and 42) with severity `warn`, and a test that `result = 1` always has a count and `result = 42` never does.
   - Tests: `unique` on (`steam_appid`, `_dlt_load_id`) with `dbt_utils.unique_combination_of_columns`, `not_null`, relationships to the game list.
   - Time: join the three tables on the date, not on the exact time (`collected_at` differs per row in `player_counts`).
4. **`feat/dbt-intermediate`, `feat/dbt-marts`**, then the Streamlit dashboard. Ideas: latest row per game for "now" questions, history models for trends, price versus sentiment, new releases versus older, genre comparison. Franchise was dropped on 2026-11-05 and no minimum number of reviews is needed: see `docs/13_conceptual_model.md`, section 9, for all decisions.
5. **A new doc in `docs/` for each finished step** (next number is `10`), with tables, links to code lines and the reason for every decision, plus session notes in `scratch/docs/06_dlt_ingestion_plan.md` (with my OK).

## 7. Best-practice checklist for everything you show me

- Python 3.12, type hints, short docstrings, small single-purpose functions, clear names; match the style of the existing files. Comments in simple words (see `steam.py`).
- Secrets only from environment variables. Never print credentials, the Snowflake account name or full connection strings.
- dbt: lowercase snake_case, one model per file, `stg_<source>__<table>` style names (check the reference repo), a `_sources.yml` / `_models.yml` next to the models, descriptions and tests for every model, no `select *` in marts, comments in SQL in simple words. `dbt parse` and `dbt build --select <model>` before moving on (I run them).
- Keep raw data untouched. Never fill NULL with 0.
- Idempotency: choose materialisations and keys on purpose and explain the choice.
- Use `logging`, not `print`, in `src/`.
- Format and lint with `ruff`; test with `pytest`; manage dependencies with `uv` and keep `uv.lock` in sync. Run `ruff format` before the final `pytest` run.
- Do not commit data files, `.env`, `.dlt/secrets.toml`, keys or caches. Keep CSV exports from Snowsight out of the repo (they land in my Downloads folder; I share them by attaching the file path).
- Before committing a notebook, check its saved outputs for secrets: `grep -n -i -E "snowflakecomputing|secret|\.aws" notebooks/*.ipynb`. Only harmless text (my own "prints no secrets") should show.
- Commits: small, conventional style (`feat(dbt): ...`, `docs: ...`). End each commit message with the attribution line the app gives you (I sometimes drop it, remind me). Always ask me before committing or pushing. I run the git commands, one command per block. The first push of a new branch needs `git push --set-upstream origin <branch>`; check the branch name for typos (my last branch is named `feat/schedule-run`, not `feat/scheduled-run`).
- If the GitHub "create pull request" banner is missing, open `https://github.com/Akina-Aoki/steam_data_platform_aira/compare/main...<branch>` or use Pull requests, New pull request.

## 8. Tool tips from sessions 2, 3 and 4

- When I paste a whole file over an old one in VS Code, I press Ctrl+A and Delete first. A single extra space before `def` gives an `IndentationError` and pytest cannot load the file (session 4).
- A notebook open in VS Code does not refresh when a file is changed from outside. I close the tab, choose "Don't Save", then reopen it.
- **Notebooks:** the Read tool dumps the **whole** notebook (outputs included) even with `offset` and `limit`: use Grep with `-n` on the raw `.ipynb` to find lines instead. The Edit tool refuses `.ipynb`. NotebookEdit replaces a whole cell, and it saves the cell source as one string instead of a list of lines. Both are valid. Only use it on cells whose text you have just read. A "run all" in the notebook replaces the saved outputs. Do not save that unless I want it.
- dlt wraps any error raised inside a resource in `ResourceExtractionError`. In tests, expect that error and check `error.value.__cause__`.
- Snowsight shows times in my session time zone (Pacific, `-0700`), so they look 9 hours earlier than Stockholm time (UTC+1 since 2026-10-25). Notebooks set the session to UTC. Example: load `1793369111.4503539` is `2026-10-30 07:15:23 -0700` in Snowsight, 15:15 in Sweden.
- Snowsight downloads CSVs to `C:\Users\adelo\I don't know\Downloads\` (yes, that odd folder name). I attach the path and you read the file. `DESC USER <name>` is a good read-only way to see a user's type, password, MFA and key.
- Windows with Git Bash: the repo shows LF/CRLF warnings. They are harmless. In Git Bash `~` is `C:\Users\adelo`. My private key lives in `~/.snowflake_keys/` (outside the repo). **Never `cat`, open or paste the `.p8` file.**
- Reports from web-fetch agents are summaries, not copies. For Snowflake behaviour, read the official page yourself or say it is the agent's summary.

## 9. Please begin by

1. Reading: `scratch/docs/06_dlt_ingestion_plan.md` (session notes at the end), `docs/04_dbt_foundation.md`, `docs/09_key_pair_login.md`, `docs/07_player_counts__dlt_ingestion.md` (section 1 and 9), `dbt_project/dbt_project.yml`, `dbt_project/packages.yml`, `dbt_project/macros/generate_schema_name.sql`, `.env.example` (**not** `.env`), `snowflake_setup/` (roles and grants, to see what `STEAM_TRANSFORMER` may do), and the staging proposals in the notebooks (use Grep, not Read, on `.ipynb` files). Look at the dbt folder of the reference repo for the structure.
2. Checking `git status`, `git branch` and `git log --oneline -5` with me (and whether the `feat/schedule-run` PR is merged).
3. Telling me in a few sentences what you understood and what you are unsure about.
4. Asking me which task in section 6 to start with, then presenting the plan for it and waiting for my OK.
