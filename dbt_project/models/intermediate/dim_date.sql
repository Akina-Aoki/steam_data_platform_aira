-- Model: dim_date
-- Layer: INTERMEDIATE (a dimension of the star)
-- One row per day that has a run, taken from the run days in staging.
-- There is no start date and no end date to keep up.
-- Days without a run are not here, because nothing in the fact points to them.

with run_days as (

    select distinct collected_date as date_day
    from {{ ref('stg_steam__games') }}

),

calendar as (

    select
        date_day,
        year(date_day)                 as year,
        month(date_day)                as month,
        to_char(date_day, 'MMMM')      as month_name,
        weekiso(date_day)              as week_of_year,
        -- ISO rule: 1 = Monday ... 7 = Sunday. No Snowflake setting changes it.
        dayofweekiso(date_day)         as day_of_week,
        dayofweekiso(date_day) >= 6    as is_weekend
    from run_days

)

select * from calendar