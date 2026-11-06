{{ config(severity='warn') }}

-- Each run should have exactly 81 games in each fact. Another number means a partial load.
-- The test returns the runs that do not have 81 rows. No rows returned means it passes.
-- "warn" reports a problem without failing the test command.

with counts as (

    select 'fact_game_store' as fact, load_id, count(*) as n_games
    from {{ ref('fact_game_store') }}
    group by load_id

    union all

    select 'fact_game_reviews' as fact, load_id, count(*) as n_games
    from {{ ref('fact_game_reviews') }}
    group by load_id

    union all

    select 'fact_game_players' as fact, load_id, count(*) as n_games
    from {{ ref('fact_game_players') }}
    group by load_id

)

select *
from counts
where n_games <> 81