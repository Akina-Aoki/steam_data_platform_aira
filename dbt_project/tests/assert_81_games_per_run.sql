{{ config(severity='warn') }}

-- Each run should have exactly 81 games. Another number means a partial load.
-- The test returns the runs that do not have 81 rows. No rows returned means it passes.
-- "warn" reports a problem without failing the test command.

select load_id, count(*) as n_games
from {{ ref('fact_game_snapshot') }}
group by load_id
having count(*) <> 81