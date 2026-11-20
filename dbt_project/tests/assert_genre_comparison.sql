-- Test: no game is lost or counted twice when the genre list is split.
-- In each run, the genre rows must add up to the number of game-genre pairs:
-- a game counts once for each genre in its list, or once if its list is empty.
-- A dbt test passes when the query returns NO rows. So this query returns the
-- runs that are wrong.

with expected as (

    -- Worked out from the genre lists, not from the mart.
    -- array_size is the number of genres. greatest(..., 1) counts an empty or
    -- missing list as one row, the row called No genre.
    select
        fact.load_id,
        sum(greatest(coalesce(array_size(game.genres::array), 0), 1)) as expected_pairs
    from {{ ref('fact_game_snapshot') }} as fact
    left join {{ ref('dim_game') }} as game
        on fact.steam_appid = game.steam_appid
    group by fact.load_id

),

actual as (

    -- What the mart says: the game_count of all genres of the run, added up.
    select
        load_id,
        sum(game_count) as actual_pairs
    from {{ ref('mart_genre_comparison') }}
    group by load_id

)

select
    expected.load_id,
    expected.expected_pairs,
    actual.actual_pairs
from expected
left join actual
    on expected.load_id = actual.load_id
-- "is distinct from" compares two values and treats NULL as a value, so a run that
-- is missing from the mart also shows up.
where actual.actual_pairs is distinct from expected.expected_pairs