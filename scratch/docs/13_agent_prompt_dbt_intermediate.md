# Handoff prompt: dbt intermediate layer (start at the plan)

> **Old plan, kept for the history. Updated 2026-11-06:** the star is built. The single `fact_game_snapshot` became three facts (`fact_game_store`, `fact_game_reviews`, `fact_game_players`), `int_steam__game_run` was never built, and `dim_game` has 10 columns. The newest handoff is `scratch/docs/16_agent_prompt_dbt_game_run_and_fact.md`. Read `docs/13_conceptual_model.md` and `docs/14_dbt_intermediate.md` for the truth.

Written 2026-11-02, at the end of the staging session. Staging is finished for all five raw tables, PR #14 is merged, and `feat/dbt-intermediate` is up to date with `main`. This file replaces the older version of file 13. Read `scratch/docs/11_agent_prompt_dbt_start.md` first (sections 0 to 1 are the rules and the project) and `scratch/docs/12_agent_prompt_dbt_staging.md` section 0 (how to talk to me). This file says what is done and where to start. **Updated 2026-11-05: read `docs/13_conceptual_model.md` first (sections 1, 5, 6, 9). It holds the decisions of that day. Where it disagrees with this file, doc 13 wins.**

## 0. How to work with me (short version, the long version is in files 11 and 12)

1. **One small thing per message**, under about 20 lines. Say where we are in one line at the top ("Step 2 of 5, ...") and what success looks like ("you should see `PASS=... ERROR=0`").
2. **Teach with an everyday comparison, then the term.** At most one new term per message. Staging was "a washing machine". Use a new picture for intermediate (for example "a kitchen where the washed ingredients are cut and combined"), then use the real word. **When I say "you lost me", go one level simpler, use a picture (in staging it was "counting the people in a room"), say plainly what the code does and what it does not do, and ask one short question.**
3. **One recommendation, not a menu.** Only ask "A or B" when it truly blocks the work. Do not reopen decisions in section 3.
4. **Plan first, then wait for my OK**, then the file. Order that worked in staging: plan table -> SQL file -> YAML tests with comments -> `dbt build` -> I look at the data in Snowsight -> commit. One model at a time.
5. **Put comments in code and YAML** so a beginner can read them. Use `#` and `--` comments that say why, not only what.
6. **Show code in chat, I paste it.** I run all commands and all git. Give each command in its own fenced `bash` block. You may edit markdown in `docs/` and `scratch/docs/`, nothing else without asking. Read-only tools (Read, Grep, Glob) are fine.
7. **Never open `.env`, `.dlt/secrets.toml` or key files.** `dbt debug` prints the Snowflake **account name**. Tell me to replace the `account:` value with `xxx` before pasting, and never repeat it.
8. **Be honest.** Say what is verified and what is not. **Check git state with me; do not trust this file for it.** Check numbers (test counts, row counts) before you put them in a commit message or a doc. **If I give a result from memory ("exactly like you predicted"), say in the doc that you did not see the file.**
9. **After I paste code into a file, check that it is really saved.** In staging the YAML block for `stg_steam__achievements` was never saved, so the build ran the view with no tests (`Found 5 models, 29 data tests` instead of 37). Look for it with Grep, and look at the `Found N models, M data tests` line of the build. Predict the expected count before the build ("my count, not a result").
10. **Staying close to the reference repos** (Flight-punctuality `indiramahadiva/Flight-punctuality_4_DE25` and my lecture repo `Akina-Aoki/AiraTheSnowFairy`): change something only when needed, and ask me first. **For intermediate there is probably no reference to copy.** According to an earlier web summary (not verified), the Flight repo has an empty `intermediate/` folder, and the lecture repo uses `dim/`, `fct/`, `mart/`. Say so, and keep to what my notebooks proposed.
11. PR text: first person, short sentences, no buzzwords, no "This PR ...". Draft it for me each time. End it with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Commit style `feat(dbt): ...`. **End each commit message with a second `-m "Co-Authored-By: ..."` line (the attribution the app gives you); I sometimes drop it, remind me.** Use double quotes only, with no quotes inside.
12. Do not run the full dlt pipeline. `append` adds rows on every run. I run it by hand, once a day at most.

## 1. Where we are

Branch **`feat/dbt-intermediate`**, fast-forwarded to `main` at `03092c1 Merge pull request #14 from Akina-Aoki/feat/dbt-staging`. There are no commits of its own yet. Check this with me before you trust it. Untracked files in `scratch/` are on purpose out of git: do not commit or delete them (this file is one of them).

**Done and merged (PRs #11, #12 and #14):**

| Item | Result |
|---|---|
| Sources | [`_steam__sources.yml`](../../dbt_project/models/staging/_steam__sources.yml): source `steam`, schema `steam_raw`, tables `games`, `review_summary`, `player_counts`, `review_recent`, `achievements`. No tests, no freshness. |
| Staging models (views in `STAGING`) | `stg_steam__games`, `stg_steam__review_summary`, `stg_steam__player_counts`, `stg_steam__review_recent`, `stg_steam__achievements` in `dbt_project/models/staging/` |
| Tests | 37 tests in `_steam__models.yml`. `dbt build` of the whole project on 2026-11-02: 5 views and 37 tests, `PASS=42 WARN=0 ERROR=0` |
| Macro | `macros/decode_html_entities.sql` (replaces `&quot;` and `&amp;`, used by `stg_steam__games` only) |
| Docs | [`docs/10_dbt_sources_staging.md`](../../docs/10_dbt_sources_staging.md) (read it, it has the decisions and findings). **The next doc is `docs/13_...` for intermediate** (docs 11 and 12 are the ingestion docs for `review_recent` and `achievements`). |
| `DBT_USER` login | Password (`HAS_MFA` false). Key pair later if Snowflake blocks passwords. |

**How I run dbt** (from `dbt_project/`, Git Bash, the virtual environment is active):

```bash
set -a; source ../.env; set +a
dbt build
```

The first line loads my Snowflake settings once per terminal. The long form `uv run --env-file ../.env dbt build` also works. To build one model add `--select <name>`. Packages: `dbt_utils` 1.4.1. The two "unused configuration paths" warnings (`intermediate`, `marts`) go away when the first model exists in that folder.

## 2. What the staging models give you (columns)

| Model | Grain | Columns |
|---|---|---|
| `stg_steam__games` | game + run | `steam_appid`, `load_id`, `collected_at_utc`, `collected_date`, `name`, `type`, `is_free`, `coming_soon`, `required_age`, `short_description` (decoded), `website`, `release_date_text`, `release_date`, `price_currency`, `price_initial` and `price_final` (euros), `discount_percent`, `metacritic_score`, `recommendations_total`, `platform_windows`, `platform_mac`, `platform_linux`, and the lists `developers`, `publishers`, `genres`, `categories` (`VARIANT`) |
| `stg_steam__review_summary` | game + run | `steam_appid`, `load_id`, `collected_at_utc`, `collected_date`, `review_score`, `review_score_desc`, `total_positive`, `total_negative`, `total_reviews`, `pct_positive`, `has_reviews`, **`counts_all_languages`** (false before 2026-11-02, true from that day) |
| `stg_steam__player_counts` | game + run | `steam_appid`, `load_id`, `collected_at_utc`, `collected_date`, `collected_hour_local`, `player_count` (NULL = no data, 0 = real zero), `result` (1 or 42), `has_player_data` |
| `stg_steam__review_recent` | game + run | `steam_appid`, `load_id`, `collected_at_utc`, `collected_date`, `day_range` (30), `recent_positive`, `recent_negative`, `recent_total`, `has_recent_reviews`, `pct_positive_recent` (NULL when no recent reviews) |
| `stg_steam__achievements` | game + achievement + run | `steam_appid`, `load_id`, `collected_at_utc`, `collected_date`, `achievement_name` (Steam's code, not cleaned), `percent` (text), `percent_unlocked` (number, 0 to 100) |

`collected_date` is the **Stockholm** day in all five. A game with no achievements has **no rows** in `stg_steam__achievements`: that means "no data", never 0 %.

**Raw data now** (row counts read from the Snowsight table list on 2026-11-02; the snapshot dates come from the run history): `GAMES` 406 rows (5 snapshots of 81 games: 10-23, 10-26, 10-27, 10-30, 11-02, plus the old Portal 2 test row that staging removes), `REVIEW_SUMMARY` 324 (4 snapshots: 10-26, 10-27, 10-30, 11-02), `PLAYER_COUNTS` 243 (3 snapshots: 10-27, 10-30, 11-02), `REVIEW_RECENT` 81 (11-02 only), `ACHIEVEMENTS` 3,966 rows from 49 games (11-02 only). So far there has been **one run per day**. I have not run dlt since 11-02.

## 3. Decisions already made (do not reopen)

| Topic | Decision |
|---|---|
| Layers | `intermediate` is a **view** in schema `INTERMEDIATE` (set in `dbt_project.yml`), `marts` are tables in `MARTS`. **Since 2026-11-05 the facts and dimensions (`fact_game_snapshot`, `dim_game`, `dim_date`) are also built in `INTERMEDIATE`, as views, no exception. Revisit (table) only if Streamlit feels slow.** Streamlit's role reads `MARTS` only (no grant change, decided 2026-11-05), so marts serve the dashboard: `mart_game_detail` (one row per game per run) for the game page, plus `mart_genre_comparison`. |
| Franchise | **Dropped** from the whole project. No `franchise` column, no seed, no franchise comparison. |
| Minimums | **None.** The dashboard shows one game at a time, with the review count next to the percent, and no ranking by percent positive. |
| Genre mart | `mart_genre_comparison` works out `pct_positive` from sums (all positive ÷ all reviews), not as an average of percentages. |
| Naming | Flight style with double underscore: `int_steam__<name>.sql`, descriptions and tests in `_steam__models.yml` style (`data_tests:`, `arguments:` nesting, `severity: warn`) in `models/intermediate/` (no per-source subfolder). Comments on every test. |
| Staging stays 1:1 | Unpacking lists, joins and "latest row per game" belong in intermediate, not staging |
| Lists | `developers`, `publishers`, `genres`, `categories` are unpacked **here** (`LATERAL FLATTEN`) |
| Unreleased | Use `coming_soon` from `games`. Never use `result = 42` or zero reviews to mean "unreleased". |
| NULL vs 0 | Never `coalesce(player_count, 0)`. A missing price is never 0. No achievement rows is not 0 %. |
| Joins across tables | **Changed 2026-11-05:** on `steam_appid` + `load_id` (one row per game per run, agreed in doc 13). Not on the date and not on exact timestamps. Keep both `price_initial` and `price_final`. |
| English-only reviews | `review_summary` before 2026-11-02 counts English reviews only. Do not treat a jump between 10-30 and 11-02 as a real change, and do not compare `review_recent` (all languages) with `total_reviews` when `counts_all_languages` is false. The flag is the tool for this. |
| Raw stays raw | No change to raw tables. The flag is a label, no rows are removed. |
| Orchestration | None. I run dlt and dbt by hand. Airflow is future work. |

## 4. What my notebooks proposed for intermediate (these are proposals, not decided)

| From | Proposal |
|---|---|
| Notebook 01, finding 5 | Unpack `developers`, `publishers`, `genres`, `categories` into one row per game and value, remove repeated values (2 games repeat a category), decide what to do with the raw key `#category_playable_at_your_own_pace` |
| Notebook 01, findings 1 and 9 | "Current state" questions use the **latest** row per game; trends use all rows |
| Notebook 02, findings 7 and 8 | Daily change of review totals per game with `LAG` over the collection date (do not assume a total can never go down; **not checked**). Join `review_summary` to `games` on `steam_appid` and date. **New:** `LAG` across 10-30 to 11-02 mixes English-only and all-language counts, so use `counts_all_languages` to handle it. |
| Notebook 03, findings 2 and 4 | Join `player_counts` to `games` and `review_summary` on the **date**. Take "unreleased" from the latest `games` row. |
| Notebook 04, finding 5 | The 30-day windows of two runs share 29 days. **Never add `recent_total` over several days** (the same reviews are counted many times). For "now" use the latest row per game, for a trend one value per run. |
| Notebook 04, finding 7 | A test, `severity: warn`, that returns the rows where `recent_total > total_reviews` for the same run. It needs a join of `review_recent` and `review_summary`, so it belongs here. Use only rows with `counts_all_languages = true`. The notebook query returned nothing on 2026-11-02. |
| Notebook 05 and the ingestion notes (doc 12) | A `has_achievements` flag from **our own rows**, not from the store category `Steam Achievements` (7 games disagree with the category: 2 unreleased with the category but no rows, 5 released with rows but no category). I did not re-read notebook 05 for this file, the numbers come from the earlier handoff. |
| Notebooks 02 and 03 | Minimum reviews and minimum players for comparisons: **decided 2026-11-05, none needed** (see doc 13, section 9) |

A possible set of models (the agent must propose its own plan and let me OK it, do not take this as agreed):

| Possible model | Grain | Purpose |
|---|---|---|
| `int_steam__games_latest` | one row per game | Current state of each game (my suggestion for the first one, because the others need it) |
| `int_steam__game_genres` (and `_categories`, `_developers`, `_publishers`) | one row per game and value | Unpacked lists |
| ~~`int_steam__game_run`~~ (was `game_daily`) **dropped and never built, 2026-11-06** | one row per game per run | The staging models joined on `steam_appid` + `load_id`. Feeds `fact_game_snapshot`. A `unique` test on (`steam_appid`, `load_id`). |
| `int_steam__review_changes` | one row per game per run | Change in review totals since the last snapshot, with the language flag respected |
| `int_steam__achievements_by_game` | one row per game | Number of achievements, average share unlocked, `has_achievements` from our own rows |
| `dim_game`, `dim_date`, ~~`fact_game_snapshot`~~ (**now three facts: `fact_game_store`, `fact_game_reviews`, `fact_game_players`**, 2026-11-06) | game / day / game per run | The star, built in `INTERMEDIATE` as views. Columns are in doc 13, section 6.4 and in `dbt_project/models/intermediate/logical_model.dbml`. Build them after `int_steam__games_latest`. |

## 5. Grain and join key (decided 2026-11-05)

**Grain and join key.** Doc 13 (section 1) *proposes* one row per game per **run**, joined on `steam_appid` + `load_id`, not on the date (a query on 2026-11-05 showed the same `load_id` in all four tables, 81 rows each). **Agreed on 2026-11-05.** It replaces the date join in the older notes. Because the join uses `load_id`, a second run on the same day is a second row, not a duplicate, so the old "repeated runs" question is closed. Still not tested: a failed run (a `load_id` that is missing in one table). A completeness test (81 games per run, `severity: warn`) would catch it.

**Schema rights.** `snowflake_setup/03_schemas.sql` (lines 23 to 24) gives `STEAM_TRANSFORMER` ownership of the schema `INTERMEDIATE`, so creating views there should work. This is from reading the SQL file, **not run-verified**: the first `dbt build` of an intermediate model will show it. A grant change is a Snowflake change: ask me first.

## 6. Other open items (do not start unless I ask)

- Ingestion: `result` 42 meaning (unverified), the two released games without a price (`73020`, `349790`), why *Knights of Pen and Paper 2: Free Edition* has no reviews and 0 players, one fixed run hour (my runs were at 10:43, 15:05 and 13:14), compare all 81 names with Steam's publisher page, why *Europa Universalis IV* and *Prison Architect* fell so far in the last 30 days (needs news or patch dates).
- Notebook text for notebooks 01 to 03 is behind the data. Do not edit notebooks without asking.
- `docs/03` and `docs/04` still say "password and MFA" for `DBT_USER`. A small doc fix, only when I say so.
- `DLT_USER` still has a password (remove it or change type later, read Snowflake's docs first). `STREAMLIT_USER` login is decided when Streamlit is built.
- Marts, Streamlit, and the thesis text come after intermediate.

## 7. Please begin by

1. Reading file 11 (sections 0 to 1), file 12 (section 0), `docs/10_dbt_sources_staging.md`, and the staging files in `dbt_project/models/staging/` (copy their style).
2. Checking with me, one command at a time: `git branch`, `git status` and `git log --oneline -3`. Confirm I am on `feat/dbt-intermediate` and that the top of the log is the merge of PR #14 (`03092c1`).
3. Telling me in **three short sentences** where we are.
4. Giving me **one** thing to do: the plan table for the first intermediate model (`int_steam__games_latest`). Then wait. (The grain question is closed, see section 5.)
