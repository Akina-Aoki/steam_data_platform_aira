-- Model: fact_game_snapshot
-- Layer: INTERMEDIATE (the one fact of the star)
-- One row per game per run: store page, reviews and players together.
-- Counts only. Percentages are worked out later, in the mart.

with games as (

    select * from {{ ref('stg_steam__games') }}

),

review_summary as (

    select * from {{ ref('stg_steam__review_summary') }}

),

review_recent as (

    select * from {{ ref('stg_steam__review_recent') }}

),

player_counts as (

    select * from {{ ref('stg_steam__player_counts') }}

),

joined as (

    -- games is the base, because it has a row in every run.
    -- The other three tables started later, so we use left joins:
    -- early runs keep their row and the missing values stay NULL.
    select
        -- Keys. steam_appid + load_id is one row. snapshot_date points to dim_date.
        games.steam_appid,
        games.load_id,
        games.collected_date as snapshot_date,

        games.collected_at_utc,
        -- The Stockholm hour (0 to 23) of the run. It comes from games, which has a row in every run.
        hour(convert_timezone('UTC', 'Europe/Stockholm',
        games.collected_at_utc)) as snapshot_hour_local,

        -- Store page. NULL price means no price, never 0.
        games.price_currency,
        games.price_initial,
        games.price_final,
        games.discount_percent,
        games.is_free,
        games.coming_soon,

        -- Reviews, all time. The total is positive + negative, so it is not stored.
        -- counts_all_languages is false before 2026-11-02 (English only).
        review_summary.total_positive,
        review_summary.total_negative,
        review_summary.counts_all_languages,

        -- Reviews, last 30 days. NULL before 2026-11-02. A real 0 stays 0.
        review_recent.recent_positive,
        review_recent.recent_negative,

        -- Players. NULL means no data, 0 is a real zero.
        player_counts.player_count,
        player_counts.has_player_data,
        player_counts.collected_hour_local

    from games
    left join review_summary
        on games.steam_appid = review_summary.steam_appid
        and games.load_id = review_summary.load_id
    left join review_recent
        on games.steam_appid = review_recent.steam_appid
        and games.load_id = review_recent.load_id
    left join player_counts
        on games.steam_appid = player_counts.steam_appid
        and games.load_id = player_counts.load_id

)

select * from joined