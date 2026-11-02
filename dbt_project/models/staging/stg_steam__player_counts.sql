-- Model: stg_steam__player_counts
-- Layer: STAGING
-- One row in = one row out. Cleans the form, plus one helper flag.

with source as (

    select * from {{ source('steam', 'player_counts') }}

),

renamed_staging as (

    select
        steam_appid,
        _dlt_load_id as load_id,

        -- collected_at is TIMESTAMP_LTZ and differs for every row (a run takes about 10 minutes)
        convert_timezone('UTC', collected_at)::timestamp_ntz as collected_at_utc,
        convert_timezone('Europe/Stockholm', collected_at)::date as collected_date,
        hour(convert_timezone('Europe/Stockholm', collected_at)) as collected_hour_local,

        -- NULL = Steam has no data, 0 = a real zero. Never turn NULL into 0.
        player_count,
        result,

        -- result 1 = Steam sent a count, result 42 = no data
        (result = 1) as has_player_data

    from source

)

select * from renamed_staging