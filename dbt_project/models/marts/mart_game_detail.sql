-- Model: mart_game_detail
-- Layer: MARTS (a table the dashboard reads)
--
-- WHAT IT GIVES YOU
-- Everything the game page needs to tell the story of ONE game: what it is, what
-- it costs, how well it is reviewed, how many people play it, and whether it is
-- doing better or worse than the last time we checked.
--
-- Each row is one game at one run (a run is one moment when we collected the
-- data from Steam). The rows of the same game, side by side, form its history.
--
-- WHY IT IS BUILT THIS WAY
-- - We keep every run, not only the latest. A trend needs at least two points:
--   "reviews went up 2.5 points" cannot be said from a single row.
-- - The changes are worked out here, once, so the dashboard only reads them and
--   every page shows the same numbers.
-- - A change is left empty (NULL) when the comparison would not be fair, for
--   example for the first run of a game. An empty value says "we cannot say".
--   A 0 would say "nothing changed", and that could be untrue.
--
-- HOW IT IS BUILT
-- Each step below is a CTE: a small named table that the next step reads.
-- Read them from the top down, like a recipe.
--   fact           the measurements: one row per game per run
--   game           the description of each game (name, genres)
--   joined         the measurements and the description side by side
--   percents       the percentages are worked out from the counts
--   with_previous  every row also gets the values of the run before it
--   final          the changes are worked out, and only the columns we show are kept
--
--
-- TWO RULES
-- 1. A percentage comes from counts (positive divided by total), never from an
--    average of percentages.
-- 2. A change is only worked out when the two runs are comparable.
--    Before, the review counts were English only, after that all languages.
--    Comparing the two would show a jump that is not real, so we show NULL.


-- STEP 1: the fact. ref() tells dbt which model to read. dbt also uses it to
-- build the models in the right order.
with fact as (
    select * from {{ ref('fact_game_snapshot') }}
),

-- STEP 2: the description of each game. It has one row per game.
game as (
    select * from {{ ref('dim_game') }}
),

-- STEP 3: put the measurements and the description in one table.
-- We pick the columns we need and add the totals. There is still one row per
-- game per run, nothing is added up across games.
joined as (
    -- left join keeps every fact row, even if a game were missing from the descriptions.
    -- dim_game has one row per game, so this join does not multiply rows.
    --  If it did, every number downstream would be wrong.
    select
        -- These identify the row: which game, which run, when.
        -- (steam_appid + load_id is the unique key we test in the YAML.)
        fact.steam_appid,
        fact.load_id,
        fact.snapshot_date,
        fact.snapshot_hour_local,
        -- The exact time of the run in UTC. We do not show it, we need it in
        -- step 5 to put the runs of a game in time order.
        fact.collected_at_utc,

        -- The description comes from the game table, the status from the fact
        -- (a game can be "coming soon" in one run and released in the next).
        game.name,
        game.genres_text,
        fact.coming_soon,
        fact.is_free,

        -- Price columns are passed on as they are. A free game has no price
        -- (NULL), and that is fine: NULL means "no data", it is not 0.
        fact.price_initial,
        fact.price_final,
        fact.discount_percent,

        -- The total is positive + negative. In SQL, anything + NULL is NULL, so
        -- the total is NULL when there is no review data. We keep total_positive
        -- because step 4 needs it for the percentage.
        fact.total_positive,
        fact.total_positive + fact.total_negative as total_reviews,
        -- true when the review counts include all languages (see rule 2).
        fact.counts_all_languages,
        -- Same idea for the reviews of the recent period.
        fact.recent_positive,
        fact.recent_positive + fact.recent_negative as recent_total,

        -- NULL means no data, 0 is a real zero. A game with 0 players is not
        -- the same as a game we have no player count for.
        fact.player_count,
        fact.collected_hour_local

    from fact
    left join game
        on fact.steam_appid = game.steam_appid
),

-- STEP 4: work out the percentages.
-- WHY here and not in step 3: a percentage needs the totals, and the totals only
-- exist after step 3. Every CTE can only use columns that the CTE before it
-- selected. This is rule 1: we divide counts, we do not average percentages.
percents as (
    -- nullif(a, b) gives NULL when a equals b. A total of 0 becomes NULL, and a
    -- division by NULL gives NULL. So a game with no reviews gets NULL, not an
    -- error (division by 0) and not a fake 0 percent.
    -- round(x, 1) keeps one decimal, for example 87.4.
    -- "select *" keeps every column of the step before, and we add two new ones.
    select
        *,
        round(100 * total_positive / nullif(total_reviews, 0), 1) as pct_positive,
        round(100 * recent_positive / nullif(recent_total, 0), 1) as pct_positive_recent
        from joined
),

-- STEP 5: look back. Give every row the values of the run before it.
-- WHY: the game page shows how a game is doing compared to last time (did the
-- reviews get better, did the players go up). To subtract "last time" from "now"
-- both values must be on the SAME row. lag() brings the earlier value onto the
-- current row.
--
-- How to read:  lag(column) over (partition by ... order by ...)
--   partition by steam_appid   look only at rows of the SAME game. Without this,
--                              the "previous row" could be a different game.
--                              This is the window function version of group by,
--                              but it does not collapse the rows.
--   order by collected_at_utc  put the runs of that game in time order, oldest
--                              first, so "previous" means "the run before".
--   load_id                    tie-breaker. If two runs ever had the same time,
--                              the order would be random and could change from
--                              one dbt run to the next. load_id makes it stable.
--   lag(...)                   take the value from the row just before this one.
--                              The very first run of a game has no row before it,
--                              so lag gives NULL.
--
-- Example for one game (the change is worked out in step 6):
--   run | pct_positive | previous_pct_positive
--   1   | 80.0         | NULL   (no run before)
--   2   | 82.5         | 80.0
--   3   | 81.0         | 82.5
-- The same window is written three times, once for each column we look back on.
with_previous as (

    select
        *,
        lag(pct_positive) over (
            partition by steam_appid order by collected_at_utc, load_id
        ) as previous_pct_positive,
        lag(player_count) over (
            partition by steam_appid order by collected_at_utc, load_id
        ) as previous_player_count,
        -- We also look back at the language flag, because step 6 needs it to
        -- decide if the two runs can be compared.
        lag(counts_all_languages) over (
            partition by steam_appid order by collected_at_utc, load_id
        ) as previous_counts_all_languages
    from percents

),

-- STEP 6: work out the changes and choose the columns we show.
-- The change is NULL (not 0) when we cannot give an honest answer:
--   - there is no earlier run (previous value is NULL, and a number minus NULL
--     is NULL)
--   - one of the two values is missing (same reason)
--   - the language flag differs between the two runs (see rule 2)
-- How the case works: when the condition is true we calculate the change. There
-- is no "else" line, so when the condition is false (or NULL, for example when
-- there is no earlier run) the result is NULL. That is exactly what we want.
-- A change of 0 would be a lie: it would say "nothing happened", while the truth
-- is "we cannot say".
--
-- pct_positive_change is in percentage points: 82.5 minus 80.0 gives 2.5 points,
-- not "2.5 percent".
--
-- The select list is also a choice: we leave out collected_at_utc,
-- total_positive, recent_positive and the previous_* columns. They were
-- tools to work out the answer, and the game page does not need them.
final as (

    select
        -- Which game, which run.
        steam_appid,
        load_id,
        snapshot_date,
        snapshot_hour_local,

        -- About the game.
        name,
        genres_text,
        coming_soon,
        is_free,

        -- Price.
        price_initial,
        price_final,
        discount_percent,

        -- Reviews: all time, then the recent period.
        total_reviews,
        pct_positive,
        recent_total,
        pct_positive_recent,
        counts_all_languages,

        -- Players.
        player_count,
        collected_hour_local,

        -- Changes since the run before.
        case
            when counts_all_languages = previous_counts_all_languages
            then round(pct_positive - previous_pct_positive, 1)
        end as pct_positive_change,
        case
            when counts_all_languages = previous_counts_all_languages
            then player_count - previous_player_count
        end as player_count_change

    from with_previous

)

select * from final
