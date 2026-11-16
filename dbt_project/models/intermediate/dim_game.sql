-- Model: dim_game
-- Layer: INTERMEDIATE (a dimension of the star)
-- One row per game: the things about a game that rarely change.
-- Price and status (coming_soon, is_free) are not here, they live in the fact.

with games_latest as (

    select * from {{ ref('int_steam__games_latest') }}

),

final as (

    select
        steam_appid,
        name,
        type,

        release_date,
        -- NULL for unreleased games, because release_date is NULL for them
        year(release_date) as release_year,
        release_date_text,

        -- NULL means Steam shows no Metacritic score. Never 0.
        metacritic_score,
        website,
        short_description,

        -- These four stay lists. The genre list is split later, in the genre mart.
        developers,
        publishers,
        genres,
        -- ["Indie", "Simulation"] becomes Indie, Simulation. An empty list gives NULL.
        nullif(array_to_string(genres::array, ', '), '') as genres_text,
        categories

    from games_latest

)

select * from final