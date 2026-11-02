-- Model: stg_steam__review_summary
-- Layer: STAGING
-- One row in = one row out. Cleans the form, plus two simple helper columns.

with source as (

    select * from {{ source('steam', 'review_summary') }}

),

renamed_staging as (

    select
        steam_appid,
        _dlt_load_id as load_id,

        -- collected_at is TIMESTAMP_LTZ, so we fix it to UTC and a Stockholm day
        convert_timezone('UTC', collected_at)::timestamp_ntz as collected_at_utc,
        convert_timezone('Europe/Stockholm', collected_at)::date as collected_date,

        -- The label is free text (for example "1 user reviews"), so we keep it as it is
        review_score,
        review_score_desc,

        total_positive,
        total_negative,
        total_reviews,

        -- Percent positive with one decimal. NULL when a game has no reviews.
        round(100 * total_positive / nullif(total_reviews, 0), 1) as pct_positive,

        -- Zero reviews does not mean the game is unreleased
        total_reviews > 0 as has_reviews

    from source

)

select * from renamed_staging