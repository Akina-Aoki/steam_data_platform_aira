-- Model: fact_game_store
-- Layer: INTERMEDIATE (a fact of the star)
-- One row per game per run: what the Steam store page showed (price and status).
-- Reviews and players are not here, they have their own facts:
-- fact_game_reviews and fact_game_players.

with games as (

    select * from {{ ref('stg_steam__games') }}

),

final as (

    select
        -- Keys. steam_appid + load_id is one row. snapshot_date points to dim_date.
        steam_appid,
        load_id,
        collected_date as snapshot_date,

        collected_at_utc,

        -- Price. NULL means no price, never 0.
        -- The discount is not stored. The mart works it out from the two prices.
        price_currency,
        price_initial,
        price_final,

        -- A free game has no price (NULL), so is_free tells it apart from a missing price.
        is_free,
        -- These two can change over time, so they live in the fact and not in dim_game.
        coming_soon

    from games

)

select * from final