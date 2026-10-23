# Graduation Thesis — Steam API & dlt Ingestion Planning

## 1. Project Context

I am a beginner data engineering student working on my graduation thesis at Stockholms Tekniska Institut (STI).

The project will use **Steam Games & Reviews data** to demonstrate API extraction and ingestion using Python and dlt (data load tool).

For now, we are focusing strictly on:

- Understanding available Steam APIs and endpoints.
- Identifying which data can be extracted for free.
- Testing API responses and examining the JSON structure.
- Planning how to organize Python extraction and dlt resources.
- Loading data into Snowflake only after validating the APIs.

**Important:** Do not move ahead to dbt, dimensional modeling, Airflow, Docker, dashboards, or the overall architecture yet. We are working step by step.

## 2. Steam API Decision

Initially, I tried registering for a Steam Web API key through:

https://steamcommunity.com/dev/apikey

However, my Steam account is restricted because I do not meet the account requirements.

We identified three publicly accessible endpoints that we plan to use without purchasing games or registering for a Steam API key.

| Endpoint | Data to collect | API key |
|---|---|---|
| Steam Store `appdetails` | Game titles, genres, prices, developers, publishers, release dates | Not required |
| `IUserReviewsService/GetAppReviews` | Player reviews, positive/negative recommendations, review dates, playtime | Not required for public reviews |
| `ISteamUserStats/GetNumberOfCurrentPlayers` | Number of players currently active in a game | Not required |

These are three endpoints, not three entirely separate API providers.

The Store `appdetails` endpoint is publicly accessible but not as formally documented as the official Steam Web API methods.

**Current status:** These are our intended sources. We have not yet verified all three responses in my own Python environment. We must check endpoint behavior, available fields, pagination, rate limits, and usage restrictions before implementing ingestion.

## 3. API URLs

**Game metadata and pricing:**

```text
https://store.steampowered.com/api/appdetails
```

Example parameters:

```text
appids=620
cc=se
l=english
```

**Player reviews:**

```text
https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/
```

This endpoint accepts query parameters including `input_json`. We need to inspect the official documentation to implement the correct request and pagination.

**Current player count:**

```text
https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=620
```

`620` is the Steam App ID for Portal 2, which we can use as our initial test game.

The common identifier connecting all three datasets is `appid`.

## 4. dlt Pipeline Design

I previously worked on a Swedavia aviation data engineering project.

In that project, I used separate dlt pipelines:

- A pipeline for reference data such as airports and airlines, collected from Wikipedia.
- Another pipeline for operational flight data extracted from the Swedavia API.

For Steam, we discussed whether having three API endpoints means we need three separate dlt pipelines.

**Our initial decision: Start with ONE dlt pipeline containing THREE resources.**

Conceptually:

```text
Steam APIs
    |
    |-- Store appdetails
    |       |
    |       --> games_resource
    |
    |-- GetAppReviews
    |       |
    |       --> reviews_resource
    |
    |-- GetNumberOfCurrentPlayers
            |
            --> player_counts_resource

                  |
                  v
            ONE dlt pipeline
                  |
                  v
               Snowflake
```

The proposed dlt resources would initially load three logical tables:

- `games`
- `reviews`
- `player_counts`

These names are provisional and can be refined after inspecting the API responses.

One dlt pipeline with three resources is a beginner-friendly starting point. We may later separate resources into different pipelines if they need significantly different execution schedules or operational controls.

## 5. Important Data Considerations

The three resources have different data behaviors.

**Games:** Mostly metadata, but prices and discounts can change. We should decide whether to store current values or historical price snapshots.

**Reviews:** New reviews accumulate over time. We should investigate pagination, review identifiers, deduplication, and incremental loading to avoid repeatedly loading the same reviews.

**Player counts:** Each request returns the current player count, not historical player data. To analyze trends, we must save the observation along with a collection timestamp.

The ingestion strategies should be designed after we inspect the actual API data.

## 6. Immediate Next Steps

1. Choose one test game, initially Portal 2 (`appid=620`).
2. Test the three endpoints, starting in the browser and then using Python `requests`.
3. Examine the JSON response structure and available fields.
4. Confirm HTTP responses, authentication requirements, rate limits, and error handling.
5. Decide which fields to retain and how to manage missing or nested data.
6. Design one dlt pipeline with three resources.
7. Only then begin implementing ingestion to Snowflake.

We may eventually select approximately 3–5 games for the initial scope, but the final selection has not been decided.

## 7. Instructions for the Next Agent

Please guide me step by step as a beginner data engineer.

I want to understand the difference between:

- API provider
- API endpoint
- Python extraction function
- dlt source
- dlt resource
- dlt pipeline

Do not automatically assume that three endpoints require three separate pipelines.

I prefer to understand the API response structures and dlt design decisions before writing the entire implementation.

**Where we stopped:** We agreed to investigate the three public Steam endpoints and start with one dlt pipeline containing three resources. No actual Steam API extraction or dlt ingestion has been completed yet.

**Our next task:** Validate the first API endpoint and inspect its JSON response before progressing to the other two endpoints.