-- Model: fact_game_players
-- Layer: INTERMEDIATE (a fact of the star)
-- One row per game per run: how many players Steam reported at that moment.
-- Price and status are in fact_game_store, reviews are in fact_game_reviews.
-- Rows exist only for runs where player counts were collected.

with player_counts as (

    select * from {{ ref('stg_steam__player_counts') }}

),

final as (

    select
        -- Keys. steam_appid + load_id is one row. snapshot_date points to dim_date.
        steam_appid,
        load_id,
        collected_date as snapshot_date,

        -- Each player count has its own time, because a run takes about 10 minutes.
        collected_at_utc,
        -- The count depends on the hour of the day, so the hour stays next to it.
        collected_hour_local,

        -- NULL = Steam has no data, 0 = a real zero. Never turn NULL into 0.
        player_count,
        has_player_data

    from player_counts

)

select * from final