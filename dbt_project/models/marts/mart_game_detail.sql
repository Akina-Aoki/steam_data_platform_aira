-- Model: mart_game_detail
-- Layer: Marts (a table the dashboard reads).
-- One row per game per run, for the game page.
-- Counts come from the fact. 
-- Percentages and changes are worked out there.


with fact as (
    select * from {{ ref('fact_game_snapshot') }}
),

game as (
    select * from {{ ref('dim_game') }}
),

joined as (
    -- dim_game has one row per game, so this join does not multiply rows.
    select
        fact.steam_appid,
        fact.load_id,
        fact.snapshot_date,
        fact.snapshot_hour_local,
        fact.collected_at_utc,

        game.name,
        game.genres_text,
        fact.coming_soon,
        fact.is_free,

        fact.price_initial,
        fact.price_final,
        fact.discount_percent,

    -- The total is positive + negative. NULL when there is no review data.
        fact.total_positive,
        fact.total_positive + fact.total_negative as total_reviews,
        fact.counts_all_languages,
        fact.recent_positive,
        fact.recent_positive + fact.recent_negative as recent_total,
        
    -- NULL means no data, 0 is a real zero
        fact.player_count,
        fact.collected_hour_local
    
    from fact
    left join game
        on fact.steam_appid = game.steam_appid
),

percents as (
    -- Worked out from counts. NULLIF turns a total of 0 into NULL, so there's no division by 0 and no fake 0%.
    select
        *,
        round(100 * total_positive / nullif(total_reviews, 0), 1) as pct_positive,
        round(100 * recent_positive / nullif(recent_total, 0), 1) as pct_positive_recent
        from joined
),

with_previous as (

    -- lag() looks up the earlier row of the same game, ordered by time.
    select
        *,
        lag(pct_positive) over (
            partition by steam_appid order by collected_at_utc, load_id
        ) as previous_pct_positive,
        lag(player_count) over (
            partition by steam_appid order by collected_at_utc, load_id
        ) as previous_player_count,
        lag(counts_all_languages) over (
            partition by steam_appid order by collected_at_utc, load_id
        ) as previous_counts_all_languages
    from percents

),

final as (

    -- A change is NULL when there is no earlier run, when a value is missing,
    -- or when the language flag differs between the two runs.
    select
        steam_appid,
        load_id,
        snapshot_date,
        snapshot_hour_local,

        name,
        genres_text,
        coming_soon,
        is_free,

        price_initial,
        price_final,
        discount_percent,

        total_reviews,
        pct_positive,
        recent_total,
        pct_positive_recent,
        counts_all_languages,

        player_count,
        collected_hour_local,

        case
            when counts_all_languages = previous_counts_all_languages
            then round(pct_positive - previous_pct_positive, 1)
        end as pct_positive_change,
        case
            when counts_all_languages = previous_counts_all_languages
            then player_count - previous_player_count
        end as player_count_change

    from with_previous

)

select * from final