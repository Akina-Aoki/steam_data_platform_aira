# dbt Marts: Steam Data Platform

## Overview

The marts are the last layer of dbt. They are tables in `STEAM_DB.MARTS`. Streamlit logs in as `STEAM_REPORTER`, and that role can read **only** `MARTS`. So every number the dashboard shows must be in a mart.

Think of the star in `INTERMEDIATE` as a warehouse, with everything in boxes. A mart is a shelf in the shop, set up to answer one kind of question. The dashboard is a customer who may only walk into the shop.

**Branch:** `feat/dbt-marts`
**Status (2026-11-20):** all three marts are built, tested and checked: `mart_game_detail` (2026-11-19), `mart_portfolio_overview` and `mart_genre_comparison` (both 2026-11-20).

`Steam Data → dlt → STEAM_RAW → dbt Staging → dbt Intermediate → dbt Marts → Streamlit`

The design (business areas, grain) is in [doc 13](13_conceptual_model.md). This document records what was built and what was found.

## 1. The three marts

| # | Mart | One row is | Answers (areas in doc 13, section 2) | Status |
|---|---|---|---|---|
| 1 | `mart_game_detail` | one game in one run | 2, 3, 7, and the price of one game (4) | Built 2026-11-19 |
| 2 | `mart_portfolio_overview` | one group in one run, for example "release year 2019" | 1, 4, 5 | Built 2026-11-20 |
| 3 | `mart_genre_comparison` | one genre in one run (D2, decided 2026-11-20) | 6, and the genre split of 1 | Built 2026-11-20 |

Mart 2 is new. Doc 13 only had the game mart and the genre mart. I added it because areas 1, 4 and 5 compare **groups** of games, and a table with one row per game does not give a group percent from sums. Doc 13 now has it (section 6.4 and section 9).

Every mart does the same three things:

1. It reads only the star (`fact_game_snapshot`, `dim_game`), never raw data.
2. It works out what the fact does not store: totals, percentages and changes. A percent always comes from counts, never from an average of percents.
3. It is a table, so it is a saved copy (see section 9).

## 2. What I checked before building (2026-11-18)

| Question | How | Result |
|---|---|---|
| Does `MARTS` exist, and who owns it? | `show schemas in database STEAM_DB` | It exists. The owner is `STEAM_TRANSFORMER`, the role dbt logs in as. So dbt can create tables there. |
| Can `STEAM_REPORTER` read new tables? | `show future grants in schema STEAM_DB.MARTS` | 2 rows: `SELECT` on future tables and on future views, for `STEAM_REPORTER`. |

Both were later proven in practice on 2026-11-19: dbt created the table as `STEAM_TRANSFORMER`, and `select count(*)` as `STEAM_REPORTER` gave 1053 rows. No Snowflake change was needed.

## 3. `mart_game_detail`

File: [`mart_game_detail.sql`](../dbt_project/models/marts/mart_game_detail.sql)

One row per game per run, the same grain as `fact_game_snapshot`, so 1,053 rows today (13 runs x 81 games). It reads `fact_game_snapshot` and `dim_game`.

20 columns, as written in [doc 13](13_conceptual_model.md), section 6.4:

| Group | Columns | How |
|---|---|---|
| Keys and time | `steam_appid`, `load_id`, `snapshot_date`, `snapshot_hour_local` | Copied from the fact |
| Game | `name`, `genres_text`, `coming_soon`, `is_free` | The first two from `dim_game`, the last two from the fact |
| Price | `price_initial`, `price_final`, `discount_percent` | Copied. NULL stays NULL, never 0. |
| Reviews | `total_reviews`, `pct_positive`, `recent_total`, `pct_positive_recent`, `counts_all_languages` | The total is positive + negative. The percent is 100 x positive / total, with one decimal. |
| Players | `player_count`, `collected_hour_local` | Copied. NULL means no data, 0 is a real zero. |
| Change | `pct_positive_change`, `player_count_change` | This run minus the previous run of the same game |

The review count (`total_reviews`, `recent_total`) is always next to its percent. A percent alone can lie: 100% of 3 reviews is not better than 90% of 30,000.

### How the SQL works

The file is a chain of small steps (CTEs), each one reading the one before.

| Step | What it does |
|---|---|
| `joined` | Takes the fact and adds `name` and `genres_text` from `dim_game` with a `left join`. `dim_game` has one row per game, so no row is multiplied. The `left join` keeps every fact row. |
| `percents` | Works out the percents from the counts. `nullif(total, 0)` turns a total of 0 into NULL, so there is no division by zero and no fake 0%. |
| `with_previous` | `lag()` looks up the earlier row of the same game, ordered by `collected_at_utc`. It takes the earlier percent, player count and language flag. |
| `final` | Picks the 20 columns. A `case` gives the change only when the language flag is the same in both runs. |

A change is NULL when there is no earlier run, when a value is missing, or when `counts_all_languages` differs between the two runs. Before 2026-11-02 the totals counted English reviews only, so a change across that day would be a fake jump.

### D1: what "change" compares with

| Option | Problem |
|---|---|
| **The previous run** (chosen) | With hourly runs the previous run is one hour back, so review changes will often be 0. Today it can be days back. |
| The same hour yesterday | I counted the rows that have such a partner (SQL in Snowsight, 2026-11-18): **0 of 1,053**. It would give NULL everywhere until there is hourly history. |

I chose the previous run. It works today, and it matches my PDF ("from one run to the next"). "Same hour yesterday" can be added later as two more columns, without changing the rest.

## 4. Tests of `mart_game_detail`

12 tests, in [`_marts__models.yml`](../dbt_project/models/marts/_marts__models.yml).

| Where | Test | What it catches |
|---|---|---|
| Model | `unique_combination_of_columns` on `steam_appid` + `load_id` | A join that made duplicates |
| Model | `equal_rowcount` against `fact_game_snapshot` | A join that lost rows or doubled them |
| `steam_appid`, `load_id`, `snapshot_date`, `snapshot_hour_local` | `not_null` | A broken key or time |
| `name` | `not_null` | The join to `dim_game` found no game |
| `coming_soon`, `is_free` | `not_null` | See below |
| `discount_percent`, `pct_positive`, `pct_positive_recent` | `accepted_range` 0 to 100 | A wrong formula, for example 150% |

A range test ignores NULL, so "no data" passes.

### Why not every column has a `not_null` test

A `not_null` test says "NULL is never allowed here." That is only true for some columns. For the others NULL is a correct answer, and a test would fail on good data. A test that always fails on good data teaches you to ignore failures, and then you miss the real one.

| Column | Why NULL is valid |
|---|---|
| `genres_text` | A game can have no genres |
| `price_initial`, `price_final` | NULL means no price. It is never 0. |
| `total_reviews`, `recent_total`, `counts_all_languages` | Early runs have no review data (the 10-23 run came before `review_summary` existed). `recent_total` has none before 2026-11-02. |
| `pct_positive`, `pct_positive_recent` | A game with no reviews gets NULL, never 0%. These got a range test instead. |
| `player_count`, `collected_hour_local` | Runs before 2026-10-27, and unreleased games, have no player data |
| `pct_positive_change`, `player_count_change` | NULL by our own rules (no earlier run, a missing value, a language switch) |

The columns with `not_null` are the ones where NULL would mean a bug. For `coming_soon` and `is_free` I first thought NULL could happen. I checked the fact (2026-11-19): **0 NULL in 1,053 rows**. They come from the store page of every run, and a NULL would break the "released or coming soon" and "free or paid" splits. So I added the test.

## 5. Validation of `mart_game_detail`

| Check | Result |
|---|---|
| `dbt build --select mart_game_detail` (2026-11-19) | `Found 10 models, 63 data tests`. 1 table and 12 tests: `PASS=13 WARN=0 ERROR=0`. The table has 1053 rows and took 3.4 seconds. |
| Whole project `dbt build` (2026-11-19) | `PASS=73 WARN=0 ERROR=0` (10 models and 63 tests, 24 seconds). I saw the whole output. dbt built the mart last, because it reads the fact and `dim_game`. |
| `STEAM_REPORTER`: `select count(*)` on the mart | 1053 |
| NULL counts in the change columns (SQL in Snowsight) | `pct_positive_change`: 293 NULL and 760 filled. `player_count_change`: 360 NULL and 693 filled. Each pair adds up to 1053. |
| One game by hand: Stellaris, 13 rows | The NULLs sit where I predicted. For the player change I did all 9 subtractions by hand, and they match. |

My minimum count of NULLs, worked out before the query, was 243 and 324. Both were met. The extra 50 and 36 fit this reading, which I did **not** check: 4 unreleased games and one released free game with no reviews (50 = 5 games x 10 more runs), and 4 unreleased games with no player count (36 = 4 games x 9 more runs).

## 6. Findings for `mart_game_detail`

| Finding | Evidence |
|---|---|
| Discounts exist | `discount_percent` is above 0 in 43 of 1,053 rows, with a maximum of 80. It is 0 in 906 rows and NULL in 104. My PDF said "not checked yet". I do not know yet if it is one game many times or many games. |
| The language switch shows in the data | Stellaris: the total jumps from 76,828 to 139,723 on 2026-11-02, when `counts_all_languages` turns from false to true. The change is NULL on that row, as intended. |
| `coming_soon` and `is_free` are never NULL | `coming_soon`: 52 true, 1001 false. `is_free`: 26 true, 1027 false. 52 is 4 games x 13 runs, and 26 is 2 games x 13 runs. |
| 104 NULL discounts is 8 games x 13 runs | My reading, **not checked**: 4 unreleased games, 2 free games and the 2 released games with no price ([doc 13](13_conceptual_model.md)). |
| Players depend on the hour and on the gap | Stellaris on 2026-11-16 at 9:00 has −2,984 players. It is compared with 2026-11-11 at 19:00, 4.5 days and a different hour earlier. The change column cannot show that gap. |

## 7. `mart_portfolio_overview`

Files: [`mart_portfolio_overview.sql`](../dbt_project/models/marts/mart_portfolio_overview.sql) and its extra test [`assert_portfolio_groups.sql`](../dbt_project/tests/assert_portfolio_groups.sql)

`mart_game_detail` has one row per game. This mart has one row per **group** of games in a run, for example "games released in 2019" or "Free games". It answers the questions about the whole catalogue (areas 1, 4 and 5 in [doc 13](13_conceptual_model.md)). It has 442 rows today: 34 per run x 13 runs.

### Five ways to split the games

| `group_type` | `group_value` | Answers |
|---|---|---|
| `release_year` | the years 2008 to 2026, and `Coming soon` or `To be announced` for games not released | Areas 1 and 5 |
| `price_level` | `Free`, `No price`, `Under 10`, `10 to 19.99`, `20 to 39.99`, `40 and above` | Areas 1 and 4 |
| `free_or_paid` | `Free`, `Paid` | Area 1 |
| `status` | `Released`, `Coming soon` | Area 1 |
| `has_discount` | `Discount`, `No discount`, `No data` | Area 4 |

One game is in one group of **each** type. So inside one type the games add up to 81. Never add different types together, or the same game is counted five times.

### Columns (20)

| Group | Columns |
|---|---|
| The run | `load_id`, `snapshot_date`, `snapshot_hour_local` |
| The group | `group_type`, `group_value` |
| Size | `game_count` |
| Reviews, all time | `total_positive`, `total_negative`, `total_reviews`, `pct_positive`, `counts_all_languages` |
| Reviews, 30 days | `recent_positive`, `recent_negative`, `recent_total`, `pct_positive_recent` |
| Players | `players_total`, `games_with_player_data` |
| Price | `games_with_price`, `avg_price_final`, `games_with_discount` |

The percent is all positive reviews of the group divided by all its reviews. It is **not** an average of the percents of the games, because that would treat a game with 3 reviews like a game with 30,000.

### How the SQL works

The file is a chain of six small steps, and it has a comment above each one.

| Step | What it does |
|---|---|
| `fact` and `game` | Read the fact and `dim_game` |
| `labelled` | Gives every game five labels, one for each way to split. A `case when` picks the price band. |
| `stacked` | Copies the games five times, once for each label (`union all`) |
| `grouped` | Groups the copies and adds up the counts |
| `final` | Works out the percents from the sums |

Why stack first? One `group by` then does all the work. Without it I would write the same grouping five times.

### Price bands

| Band | From (included) | To (not included) | Games, newest run |
|---|---|---|---|
| Under 10 | 0.01 | 10 | 27 |
| 10 to 19.99 | 10 | 20 | 19 |
| 20 to 39.99 | 20 | 40 | 16 |
| 40 and above | 40 | none | 11 |
| Free | | | 2 |
| No price | | | 6 |

- The band uses the regular price (`price_initial`). A game on sale stays in its band.
- The edges are fixed numbers. A new game cannot move an old game, so the history of a chart does not change.
- Every price ends in .99, so no game sits on an edge.
- 59.99 (2 games) is not its own band. Two games are noise, so they are in `40 and above`.

How I decided: I counted my own prices (a CSV from Snowflake, 2026-11-19) and asked a separate research agent. The prompt is in `scratch/` and not in git. The agent guessed my data wrongly at first (it expected `40 and above` to be the biggest band). After it saw my numbers, it gave the same four bands.

### Tests

12 tests, 11 in [`_marts__models.yml`](../dbt_project/models/marts/_marts__models.yml) and 1 in its own file.

| Test | What it catches |
|---|---|
| Unique `load_id` + `group_type` + `group_value` | A duplicate group, or a run that split in two |
| A part is never bigger than the group (`games_with_discount`, `games_with_price`, `games_with_player_data` against `game_count`) | A wrong count |
| `not_null` on the run, `group_type`, `group_value` and `game_count` (6 columns) | A broken run or group |
| `group_type` has only the five known values | A typo in a type |
| `pct_positive` and `pct_positive_recent` between 0 and 100 | A wrong formula |
| `assert_portfolio_groups` (own file) | A game lost or counted twice. In every run, each group type adds up to the number of games of that run. |

As in `mart_game_detail`, the other columns have no `not_null`. NULL is a valid answer there (no reviews, no players, no price).

### What I checked (2026-11-20, newest run)

| Check | Result |
|---|---|
| `dbt build --select mart_portfolio_overview` | `PASS=13 WARN=0 ERROR=0`. The table has 442 rows. |
| Whole project `dbt build` | `PASS=86 WARN=0 ERROR=0` (11 models, 75 tests). I saw the last lines only. |
| `price_level` | 27, 19, 16, 11, No price 6, Free 2. These are the numbers I counted from the CSV, and they add up to 81. |
| `free_or_paid` | Free 2, Paid 79 |
| `status` | Released 77, Coming soon 4 |
| `has_discount` | Discount 4, No discount 69, No data 8 (6 games with no price and 2 free games) |
| `release_year` | 19 years and 2 texts, 21 groups, adding up to 81. `Coming soon` 2 and `To be announced` 2. |

### Good to know when reading it

- **Paid includes 6 games with no price.** Steam does not mark them as free. So `Paid` has 79 games but only 73 have a price.
- **`avg_price_final` is the price after the discount.** The band uses the regular price. That is why `40 and above` has an average of 44.54, below 49.99: 3 of its 11 games were on sale.
- **Small groups are noisy.** Many years hold only 2 or 3 games. The count always sits next to the percent.
- **`group_value` is text**, so it sorts alphabetically. The dashboard has to sort the years itself.

## 8. `mart_genre_comparison`

Files: [`mart_genre_comparison.sql`](../dbt_project/models/marts/mart_genre_comparison.sql) and its extra test [`assert_genre_comparison.sql`](../dbt_project/tests/assert_genre_comparison.sql)

One row is **one genre in one run**. It answers how the genres compare (area 6 in [doc 13](13_conceptual_model.md)) and how the catalogue splits by genre (area 1). It has 156 rows today: 12 genres per run x 13 runs.

### The one new idea: splitting the genre list

A game keeps its genres as a list, for example `["Indie", "Strategy"]`. The mart first splits the list, so a game with 3 genres becomes 3 rows (`lateral flatten`). Then it groups by genre, like the portfolio mart.

This has one consequence: **the genre rows of a run add up to more than the number of games.** In the newest run they add up to 165, and the catalogue has 81 games. So never add genres together. Never show a "total" over the genres.

### Columns (20)

| Group | Columns |
|---|---|
| The run | `load_id`, `snapshot_date`, `snapshot_hour_local` |
| The group | `genre` |
| Size | `game_count`, `coming_soon_games` |
| Reviews, all time | `total_positive`, `total_negative`, `total_reviews`, `pct_positive`, `counts_all_languages` |
| Reviews, 30 days | `recent_positive`, `recent_negative`, `recent_total`, `pct_positive_recent` |
| Players | `players_total`, `games_with_player_data`, `avg_player_count` |
| Price | `games_with_price`, `avg_price_final` |

As before, the percents come from sums. `avg_player_count` is `players_total` divided by `games_with_player_data`. It is NULL when no game has a count.

### How the SQL works

| Step | What it does |
|---|---|
| `fact`, `game`, `joined` | Put the fact and the genre list of each game together |
| `split` | Splits the genre list into one row per game per genre. `outer => true` keeps a game with no genre list, and it gets the genre `No genre`. |
| `grouped` | Groups by run and genre and adds up the counts |
| `final` | Works out the percents and the average from the sums |

The file has a comment above each step.

### Decisions

- **One row per genre per run (D2).** Doc 13 first said "one genre on one day". A run is the same grain as the other two marts, no rule is needed to pick the "latest run of the day", and the hour stays next to the player numbers.
- **Unreleased games count in `game_count`.** Area 1 needs the whole catalogue by genre. They have no reviews, players or price (NULL), so they change nothing else. The column `coming_soon_games` shows how many of them are in the genre.

### Tests

10 tests: 9 in [`_marts__models.yml`](../dbt_project/models/marts/_marts__models.yml) and 1 in its own file.

| Test | What it catches |
|---|---|
| Unique `load_id` + `genre` | A duplicate genre, or a run that split in two |
| A part is never bigger than the genre (`coming_soon_games`, `games_with_price`, `games_with_player_data` against `game_count`) | A wrong count |
| `not_null` on the run columns, `genre` and `game_count` (5 columns) | A broken run or genre |
| `pct_positive` and `pct_positive_recent` between 0 and 100 | A wrong formula |
| `assert_genre_comparison` (own file) | A game lost or counted twice in the split. The genre rows of each run must add up to the number of game-genre pairs worked out from the lists. |

### What I checked (2026-11-20)

| Check | Result |
|---|---|
| `dbt build --select mart_genre_comparison` | `PASS=11 WARN=0 ERROR=0`. The table has 156 rows. I guessed 250 to 300, so I was wrong: there are only 12 genres. |
| Whole project `dbt build` | `PASS=97 WARN=0 ERROR=0` (12 models, 85 tests). I saw the last lines only. |
| Newest run | 12 genres. The biggest are Strategy (65 games) and Simulation (30). The `game_count` values add up to 165, which is more than the 81 games. |
| NULL and 0 | `Massively Multiplayer` (1 game, not released) has 0 reviews, so `pct_positive` is NULL and not 0%. `Free To Play` has no price in the average. `Racing` has `avg_player_count` 0.0, a real zero. |
| `No genre` | No such row in the newest run, so every game has a genre |

### Good to know when reading it

- **Small genres are noisy.** Five of the 12 genres hold 1 to 3 games. The percent of a 1-game genre is that one game. The count always sits next to the percent.
- **The player average can be misleading.** In a genre with many games, a few popular games can pull the average up. I have not checked this with the data.
- **Do not add genres together**, and do not compare a genre with the whole catalogue by adding up the rows.

## 9. How to run, and the freshness limit

From the `dbt_project/` folder:

```bash
uv run --env-file ../.env dbt build --select mart_game_detail
```

Or the whole project: `uv run --env-file ../.env dbt build`.

**A mart is a table, not a view.** It is a copy taken when `dbt build` runs. After each ingestion the dashboard still shows the old numbers until I run `dbt build` again. The staging and intermediate layers are views, so they are always fresh.

For now I run `dbt build` by hand after an ingestion run. Dagster does it later, and the cloud (maybe Azure) after that. **Limit for the thesis:** the dashboard is only as new as the last `dbt build`.

## 10. Decisions

| Decision | Reason |
|---|---|
| `mart_game_detail` has exactly the 20 columns of doc 13, section 6.4 | I stick to the documented plan. A column can be added with one line later. |
| Change = the previous run (D1) | It works today and matches the PDF. "Same hour yesterday" has 0 partners today. |
| The language flag blanks both change columns | Doc 13 says so. It also blanks the player change on 2026-11-02, where the flag does not matter for players. I followed the doc. It can be relaxed later. |
| `not_null` only where NULL would be a bug | See section 4. |
| `coming_soon` and `is_free` get `not_null` | 0 NULL in 1,053 rows, and a NULL would break the splits. |
| I run `dbt build` by hand for now | Local development. Dagster and the cloud come later. |
| The model name is `mart_game_detail` and the YAML is `_marts__models.yml` | Same naming as `_int_steam__models.yml` |
| `mart_portfolio_overview` stacks five copies of the games and groups them once | One `group by` does all the work. Each game is in one group of each type. |
| Price bands: Under 10, 10 to 19.99, 20 to 39.99, 40 and above | Regular price, fixed edges, at least 11 games per band. 59.99 (2 games) is merged into `40 and above`. |
| The price band uses `price_initial` | A sale does not move a game to another band. |
| Free games are a band called `Free` and are not in the price average. A missing price is a band called `No price`. | A missing price is never 0. |
| Games not released show their store text in `release_year` (`Coming soon`, `To be announced`) | They stay visible and are not mixed into a year. |
| `mart_genre_comparison` has one row per genre per run (D2) | Same grain as the other marts. No rule for picking a run, and the hour stays next to the player numbers. |
| Unreleased games count in the genre `game_count`, with a column `coming_soon_games` | Area 1 needs the whole catalogue by genre. They add only NULL to reviews, players and price. |
| A game with no genre list shows as `No genre` | `outer => true` keeps it, so it does not disappear. There is none in the newest run. |

## 11. Not done yet

| Item | Status |
|---|---|
| Years in `mart_portfolio_overview` | Many years hold only 2 or 3 games, so a percent per year is noisy. If the dashboard looks jumpy, years could be grouped into periods. That would be a display choice. Not decided. |
| Price band and discount together | Not planned. The mart groups by one thing at a time. |
| The player average per genre | I have not checked how much a few big games pull it up. A median could be shown instead. Not decided. |
| `mart_genre_comparison` | Not built, last. D2 is open: per run, or the latest run of each day. |
| "Which games have the most players now?" (area 2) | A ranking. It clashes with the "no ranking" decision in doc 13. Not decided. |
| The gap between two runs is not shown | The `hours_since_previous_run` column is not in doc 13, so I left it out. |
| Most `pct_positive_change` values are 0.0 | With about 139,000 reviews, 10 new ones do not move a percent rounded to one decimal. A `total_reviews_change` column could show it. Not added. |
| Docs 14 and 15 and the dbml | Not updated for the marts yet. Doc 13 was updated on 2026-11-19 and 2026-11-20. Doc 15 still shows D1 and D2 as open. |
| Many hourly runs | Not tested. The mart was checked on 13 runs, of which only 2026-11-16 has several in one day. |
