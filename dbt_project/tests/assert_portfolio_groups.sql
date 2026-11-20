-- Test: every group type must hold every game of the run exactly once.
-- A dbt test passes when the query returns NO rows. So this query returns the
-- runs and group types that are wrong.
-- Test created by Claude

with run_sizes as (

    -- How many games each run has in the fact.
    select
        load_id,
        count(*) as games_in_run
    from {{ ref('fact_game_snapshot') }}
    group by load_id

),

group_sizes as (

    -- How many games each group type holds in the mart: its groups added up.
    -- Inside one group type this is fine. Across group types it would not be.
    select
        load_id,
        group_type,
        sum(game_count) as games_in_groups
    from {{ ref('mart_portfolio_overview') }}
    group by load_id, group_type

)

select
    group_sizes.load_id,
    group_sizes.group_type,
    group_sizes.games_in_groups,
    run_sizes.games_in_run
from group_sizes
inner join run_sizes
    on group_sizes.load_id = run_sizes.load_id
where group_sizes.games_in_groups <> run_sizes.games_in_run