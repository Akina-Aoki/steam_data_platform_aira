-- Model: stg_steam__games
-- Layer: STAGING
-- One row in = one row out. Cleans the form, no business rules.

with source as (

    select * from {{ source ('steam', 'games') }}
    --appid 620 (Portal 2) is an old test row not from Paradox
    where steam_appid <> 620

),

renamed_staging as (

    select
        steam_appid,
        _dlt_load_id as load_id,

        -- collected_at is TIMESTAMP_LTZ, so we fix it to UTC and a Stockholm day
        convert_timezone('UTC', collected_at)::timestamp_ntz as collected_at_utc,
        convert_timezone('Europe/Stockholm', collected_at)::date as collected_date,

        name,
        type,
        is_free,
        coming_soon,
        required_age,
        {{ decode_html_entities('short_description') }} as short_description,
        website,

        release_date_text,
        try_to_date(release_date_text, 'DD MON, YYYY') as release_date,

         -- Steam sends cents (969 = 9.69). NULL stays NULL, never 0.
         price_currency,
         round(price_initial / 100, 2) as price_initial,
         round(price_final / 100, 2) as price_final,
         discount_percent,

         metacritic_score,
         recommendations_total,
         platform_windows,
         platform_mac,
         platform_linux,

         developers,
         publishers,
         genres,
         categories
        
    from source

)

select * from renamed_staging