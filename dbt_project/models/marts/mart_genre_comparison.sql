-- Model: mart_genre_comparison
-- Layer: MARTS (a table the dashboard reads)
--
-- WHAT IT GIVES YOU
-- One row per genre per run. It answers: how do the genres compare (area 6),
-- and how is the catalogue split by genre (area 1)?
--
-- HOW IT IS BUILT (the same shape as mart_portfolio_overview)
--   fact      the measurements: one row per game per run
--   game      the description of each game, including its list of genres
--   joined    the fact and the game together, still one row per game per run
--   split     the genre list is split: one row per game per genre
--   grouped   the rows are grouped by genre and the counts are added up
--   final     the percentages and the average are worked out from the sums
--
-- RULES
-- 1. A percentage comes from sums, never from an average of percentages.
-- 2. A game can have several genres, so it appears in several genre rows.
--    That means the genre rows of one run add up to MORE than the number of games.
--    Never add the genres together into one total.


-- STEP 1: the fact.
with fact as (

    select * from {{ ref('fact_game_snapshot') }}

),

-- STEP 2: the description of each game. It has one row per game.
game as (

    select * from {{ ref('dim_game') }}

),

-- STEP 3: put the fact and the genre list of each game together.
-- left join keeps every fact row. dim_game has one row per game, so no row is
-- multiplied here.
joined as (

    select
        fact.load_id,
        fact.snapshot_date,
        fact.snapshot_hour_local,
        fact.counts_all_languages,
        fact.coming_soon,

        -- The list of genres of the game, for example ["Indie", "Strategy"].
        game.genres,

        -- The numbers we add up later.
        fact.total_positive,
        fact.total_negative,
        fact.recent_positive,
        fact.recent_negative,
        fact.player_count,
        fact.price_final

    from fact
    left join game
        on fact.steam_appid = game.steam_appid

),

-- STEP 4: split the genre list. This is the new idea.
-- A game has ONE row now, but its genres are a list inside one cell.
-- lateral flatten unpacks the list: a game with two genres becomes two rows,
-- one for each genre. Think of unpacking a suitcase: one suitcase (game) with
-- three items (genres) becomes three items on the table, each still labelled with
-- the suitcase it came from. All the other columns are copied to every new row.
--
-- "lateral" means flatten looks at the genres of the row it sits next to.
-- "outer => true" keeps a game whose list is empty or missing. It gets one row with
-- a NULL genre, and we call that genre 'No genre'. Without outer, such a game would
-- disappear without any message.
-- genre_item.value is one item of the list. ::varchar turns it into plain text.
split as (

    select
        joined.load_id,
        joined.snapshot_date,
        joined.snapshot_hour_local,
        joined.counts_all_languages,
        joined.coming_soon,
        coalesce(genre_item.value::varchar, 'No genre') as genre,
        joined.total_positive,
        joined.total_negative,
        joined.recent_positive,
        joined.recent_negative,
        joined.player_count,
        joined.price_final

    from joined,
        lateral flatten(input => joined.genres::array, outer => true) as genre_item

),

-- STEP 5: group by genre and add up, inside one run.
-- group by means one row for every different combination of the columns listed.
-- Here that is one row per run and per genre. Everything else is inside an
-- aggregate: count, sum, avg.
-- The run columns and counts_all_languages are the same for all games of a run. They
-- are in group by only so they appear in the result. If a run ever had two values,
-- it would split into two rows and the unique-key test would fail. That is the alarm.
--
-- count(*) counts rows. count(column) counts the rows where the column is not NULL.
-- sum() and avg() ignore NULL. An unreleased game has no reviews, no players and
-- no price, so it only changes game_count, and coming_soon_games shows how many
-- of those are in the genre.
grouped as (

    select
        load_id,
        snapshot_date,
        snapshot_hour_local,
        genre,
        counts_all_languages,

        count(*) as game_count,
        count_if(coming_soon) as coming_soon_games,

        sum(total_positive) as total_positive,
        sum(total_negative) as total_negative,
        sum(recent_positive) as recent_positive,
        sum(recent_negative) as recent_negative,

        sum(player_count) as players_total,
        count(player_count) as games_with_player_data,

        -- Free games and games with no price have no price, so they are not in the average.
        count(price_final) as games_with_price,
        round(avg(price_final), 2) as avg_price_final

    from split
    group by
        load_id,
        snapshot_date,
        snapshot_hour_local,
        genre,
        counts_all_languages

),

-- STEP 6: the percentages and the average, from the sums of the genre.
-- nullif(a, b) gives NULL when a equals b. A total of 0 becomes NULL, so a genre
-- with no reviews gets NULL, not an error and not a fake 0 percent.
-- avg_player_count is the players of the genre divided by the number of games that
-- have a player count. It is NULL when no game has one.
final as (

    select
        load_id,
        snapshot_date,
        snapshot_hour_local,

        genre,

        game_count,
        coming_soon_games,

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
        round(players_total / nullif(games_with_player_data, 0), 1) as avg_player_count,

        games_with_price,
        avg_price_final

    from grouped

)

select * from final