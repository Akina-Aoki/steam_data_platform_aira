-- Model: stg_steam__review_recent
-- Layer: STAGING
-- One row in = one row out. Cleans the form, plus three simple helper columns.

with source as (

    select * from {{ source('steam', 'review_recent') }}

),

renamed_staging as (

    select
        steam_appid,
        _dlt_load_id as load_id,

        -- collected_at is TIMESTAMP_LTZ, so we fix it to UTC and a Stockholm day
        convert_timezone('UTC', collected_at)::timestamp_ntz as collected_at_utc,
        convert_timezone('Europe/Stockholm', collected_at)::date as collected_date,

        -- The window in days (always 30 so far)
        day_range,

        recent_positive,
        recent_negative,

        -- Raw does not store the total, so we add it here
        recent_positive + recent_negative as recent_total,

        -- Zero recent reviews is a real zero, not missing data
        (recent_positive + recent_negative) > 0 as has_recent_reviews,

        -- Percent positive with one decimal. NULL when there are no recent reviews.
        round(
            100 * recent_positive / nullif(recent_positive + recent_negative, 0),
            1
        ) as pct_positive_recent

    from source

)

select * from renamed_staging