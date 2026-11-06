-- Model: fact_game_reviews
-- Layer: INTERMEDIATE (a fact of the star)
-- One row per game per run: review counts, all time and the last 30 days.
-- Counts only. Percentages are worked out later, in the mart.
-- Price and status are in fact_game_store, players are in fact_game_players.

with summary as (

    select * from {{ ref('stg_steam__review_summary') }}

),

recent as (

    select * from {{ ref('stg_steam__review_recent') }}

),

joined as (

    -- Left join from summary: review_recent exists only from 2026-11-02,
    -- so earlier runs keep their row and the recent columns stay NULL.
    select
        -- Keys. steam_appid + load_id is one row. snapshot_date points to dim_date.
        summary.steam_appid,
        summary.load_id,
        summary.collected_date as snapshot_date,

        summary.collected_at_utc,

        -- All time. The total is positive + negative, so it is not stored.
        summary.total_positive,
        summary.total_negative,
        -- false before 2026-11-02, when Steam counted English reviews only.
        -- Use it in every trend and every change calculation.
        summary.counts_all_languages,

        -- Last 30 days. NULL before review_recent existed. A real 0 stays 0.
        recent.recent_positive,
        recent.recent_negative

    from summary
    left join recent
        on summary.steam_appid = recent.steam_appid
        and summary.load_id = recent.load_id

)

select * from joined