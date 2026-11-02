-- Model: stg_steam__achievements
-- Layer: STAGING
-- One row in = one row out. Cleans the form, plus one number column.

with source as (

    select * from {{ source('steam', 'achievements') }}

),

renamed_staging as (

    select
        steam_appid,
        _dlt_load_id as load_id,

        -- collected_at is TIMESTAMP_LTZ, so we fix it to UTC and a Stockholm day
        convert_timezone('UTC', collected_at)::timestamp_ntz as collected_at_utc,
        convert_timezone('Europe/Stockholm', collected_at)::date as collected_date,

        -- Steam's code, kept exactly as it is (one name has a typo in Steam's data)
        achievement_name,

        -- Raw keeps the percent as text, so we keep it and add a number next to it
        percent,

        -- try_to_double gives NULL, not an error, when the text is not a number
        try_to_double(percent) as percent_unlocked

    from source

)

select * from renamed_staging