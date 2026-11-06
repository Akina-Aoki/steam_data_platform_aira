-- Model: int_steam__games_latest
-- Layer: INTERMEDIATE
-- One row per game: the newest row of each game from stg_steam__games.
-- It is the base of dim_game.

with games as (
    select * from {{ref('stg_steam__games')}}
),

numbered as (
    -- Number each game's rows, newest first. The newest row gets 1.
    -- load_id only breaks a tie if two rows have the same time. 

    select 
        *,
        row_number() over (
            partition by steam_appid
            order by collected_at_utc desc, load_id desc
        ) as row_num
    from games
),

latest as (

    -- Keep only the newest receipt of each game, then drop the helper column.
    select * exclude (row_num)
    from numbered
    where row_num = 1
)

select * from latest