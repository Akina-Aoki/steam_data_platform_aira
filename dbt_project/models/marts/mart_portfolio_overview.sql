-- Model: mart_portfolio_overview
-- Layer: MARTS (a table the dashboard reads)
--
-- WHAT IT GIVES YOU
-- One row per group per run. A group is, for example, "games released in 2019"
-- or "Free games". It answers questions about the whole catalogue:
-- how big is it, and how do the groups compare (areas 1, 4 and 5).
--
-- HOW IT IS BUILT
-- Each step below is a CTE: a small named table that the next step reads.
-- Read them from the top down, like a recipe.
--   fact      the measurements: one row per game per run
--   game      the description of each game (name, release year)
--   labelled  still one row per game per run, but every game gets 5 labels
--   stacked   the games are copied 5 times, once for each label
--   grouped   the games are grouped and the counts are added up
--   final     the percentages are worked out from the added-up counts
--
-- TWO RULES
-- 1. A percentage comes from sums, never from an average of percentages.
-- 2. Never add the five group types together. One game is in one group of EACH
--    type, so adding groups of different types counts the same game many times.


-- STEP 1: the fact. ref() tells dbt which model to read. dbt also uses it to
-- build the models in the right order.
with fact as (

    select * from {{ ref('fact_game_snapshot') }}

),

-- STEP 2: the description of each game. It has one row per game.
game as (

    select * from {{ ref('dim_game') }}

),

-- STEP 3: give every game five labels.
-- We want to split the games five different ways. For each way, a game needs a
-- label that says which group it belongs to. This step makes those labels.
-- There is still one row per game per run, nothing is added up yet.
labelled as (

    select
        -- These identify the run. They travel along so we can group by them later.
        fact.load_id,
        fact.snapshot_date,
        fact.snapshot_hour_local,
        fact.counts_all_languages,

        -- LABEL 1: release year.
        -- coalesce() takes the first value that is not NULL, looking left to right:
        --   the year, and if there is no year (the game is not released yet),
        --   the text from the store (Coming soon, To be announced),
        --   and if there is no text either, the words 'No date'.
        -- to_varchar() turns the year (a number) into text. A column can hold only
        -- one type, and the other values here are words.
        coalesce(to_varchar(game.release_year), game.release_date_text, 'No date')
            as release_year_label,

        -- LABEL 2: price level.
        -- case when is an if / else-if chain. SQL checks the lines from top to
        -- bottom and stops at the FIRST line that is true, so the order matters.
        -- Free must come first. A free game has no price (NULL). If the
        -- "price is null" line came first, a free game would be called 'No price'.
        -- We use the regular price (price_initial), so a sale does not move a game to another band.
        case
            when fact.is_free then 'Free'
            when fact.price_initial is null then 'No price'
            when fact.price_initial < 10 then 'Under 10'
            when fact.price_initial < 20 then '10 to 19.99'
            when fact.price_initial < 40 then '20 to 39.99'
            else '40 and above'
        end as price_level_label,

        -- LABELS 3 and 4: iff(condition, answer if true, answer if false) is a short
        -- if / else for when there are only two answers.
        -- Paid means Steam does not mark the game as free.
        iff(fact.is_free, 'Free', 'Paid') as free_or_paid_label,
        iff(fact.coming_soon, 'Coming soon', 'Released') as status_label,

        -- LABEL 5: discount.
        -- A missing discount (NULL) is not the same as a discount of 0, so it gets
        -- its own label. In a case, NULL is never > 0 and never = 0, so it falls
        -- through to the else line.
        case
            when fact.discount_percent > 0 then 'Discount'
            when fact.discount_percent = 0 then 'No discount'
            else 'No data'
        end as has_discount_label,

        -- The numbers we will add up later. They must travel along, because the
        -- later steps can only use columns that this step selects.
        fact.total_positive,
        fact.total_negative,
        fact.recent_positive,
        fact.recent_negative,
        fact.player_count,
        fact.price_final,
        fact.discount_percent

    from fact
    -- left join keeps every fact row, even if a game were missing from the
    -- description. The game table has one row per game, so no row is multiplied.
    left join game
        on fact.steam_appid = game.steam_appid

),

-- STEP 4: stack five copies of the games.
-- WHY: we want to do the same counting five times, once for each way of splitting.
-- We could write the whole counting step five times. Instead we make five copies of
-- the games first. Each copy gets a name for the split (group_type) and its own
-- label (group_value). Then ONE group-by in the next step does all the work.
-- Think of five photocopies of a class list, each one with a different column
-- to sort by.
--
-- union all glues tables on top of each other. "all" keeps every row. Plain
-- "union" would remove rows that look the same, and that would delete games.
-- The columns must be in the same order in every part. The star at the end of each
-- part gives the same columns in the same order every time.
--
-- Example: a game released in 2019 that costs 14.99 and is not on sale becomes
-- 5 rows in this step:
--   release_year | 2019        price_level | 10 to 19.99      free_or_paid | Paid
--   status | Released          has_discount | No discount
stacked as (

    select 'release_year' as group_type, release_year_label as group_value, * from labelled
    union all
    select 'price_level', price_level_label, * from labelled
    union all
    select 'free_or_paid', free_or_paid_label, * from labelled
    union all
    select 'status', status_label, * from labelled
    union all
    select 'has_discount', has_discount_label, * from labelled

),

-- STEP 5: group and add up.
-- group by means: make ONE row for every different combination of the columns
-- listed. Here that is one row per run, per group type, per group value.
-- Every other column must be inside an aggregate (count, sum, avg): a function
-- that turns many rows into one number.
--
-- Why these columns are in group by:
--   load_id                 so groups of different runs never mix
--   group_type, group_value so each group gets its own row
--   snapshot_date, snapshot_hour_local, counts_all_languages
--       They are the same for every game of a run, so they do not split a run.
--       They are in group by only because we want them in the result.
--       If a run ever had two values, it would split into two rows, and the
--       unique-key test we add in the YAML would fail. That is the alarm.
grouped as (

    select
        load_id,
        snapshot_date,
        snapshot_hour_local,
        group_type,
        group_value,
        counts_all_languages,

        -- count(*) counts rows. count(column) counts only rows where the column
        -- is not NULL. That is how we count "games that have player data".
        count(*) as game_count,

        -- sum() ignores NULL. If EVERY game is NULL, the result is NULL, not 0,
        -- so "no data" stays "no data".
        sum(total_positive) as total_positive,
        sum(total_negative) as total_negative,
        sum(recent_positive) as recent_positive,
        sum(recent_negative) as recent_negative,
        sum(player_count) as players_total,
        count(player_count) as games_with_player_data,

        -- avg() ignores NULL too, so free games and games with no price are not in
        -- the average. games_with_price says how many games the average is about.
        count(price_final) as games_with_price,
        round(avg(price_final), 2) as avg_price_final,

        -- count_if() counts the rows where the condition is true.
        count_if(discount_percent > 0) as games_with_discount

    from stacked
    group by
        load_id,
        snapshot_date,
        snapshot_hour_local,
        group_type,
        group_value,
        counts_all_languages

),

-- STEP 6: work out the percentages and the totals.
-- WHY here and not in step 5: a percentage needs the SUM of the whole group,
-- and the sums only exist after step 5. A separate step also keeps each step
-- small. This is rule 1: all positive reviews of the group divided by all its
-- reviews. An average of the percentages of the games would treat a game with
-- 3 reviews like a game with 30,000.
-- nullif(a, b) gives NULL when a equals b. A total of 0 becomes NULL, and a
-- division by NULL gives NULL. So a group with no reviews gets NULL, not an
-- error and not a fake 0 percent.
final as (

    select
        load_id,
        snapshot_date,
        snapshot_hour_local,

        group_type,
        group_value,

        game_count,

        total_positive,
        total_negative,
        total_positive + total_negative as total_reviews,
        round(100 * total_positive / nullif(total_positive + total_negative, 0), 1)
            as pct_positive,
        counts_all_languages,

        recent_positive,
        recent_negative,
        recent_positive + recent_negative as recent_total,
        round(100 * recent_positive / nullif(recent_positive + recent_negative, 0), 1)
            as pct_positive_recent,

        players_total,
        games_with_player_data,

        games_with_price,
        avg_price_final,
        games_with_discount

    from grouped

)

select * from final