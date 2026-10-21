# 01 — Infrastructure Setup

## Overview

The **Steam Data Platform** uses Snowflake to store Steam games and reviews data. The infrastructure separates data ingestion, transformation, and reporting so that each component has its own responsibilities and permissions.

This setup follows the architecture from the [Flight Punctuality project — PR #2](https://github.com/indiramahadiva/Flight-punctuality_4_DE25/pull/2), adapted for Steam.

**Progress:** The repository and Python environment are ready. The Snowflake setup below describes our planned configuration; SQL execution and verification have not yet been confirmed in this documentation.

## 1. Snowflake Architecture

| Object | Name | Purpose |
|---|---|---|
| Warehouse | `STEAM_WH` | Provides compute resources for SQL queries. |
| Database | `STEAM_DB` | Stores our Steam data. |
| Raw schema | `STEAM_RAW` | Stores data loaded by dlt. |
| Staging schema | `STAGING` | Stores cleaned data transformed by dbt. |
| Marts schema | `MARTS` | Stores analytics-ready data for reporting. |

The dbt project will also contain an **intermediate layer** for business logic and transformations. We'll decide whether this needs a separate Snowflake schema during dbt setup.

The warehouse will use the XSMALL size with auto-suspend after 60 seconds and auto-resume enabled to help reduce unnecessary compute costs.

## 2. Snowflake Roles

We separate permissions based on what each tool needs to do.

- **`STEAM_LOADER`** — Used by dlt to load raw data into Snowflake.
- **`STEAM_TRANSFORMER`** — Used by dbt to read raw data and create transformed models.
- **`STEAM_REPORTER`** — Used by Streamlit to read data from the marts schema without modifying it.

Each role will have its own service user: `DLT_USER`, `DBT_USER`, and `STREAMLIT_USER`.

This approach follows the **principle of least privilege**, meaning each tool receives only the access it needs.

## 3. Snowflake Setup Scripts

All infrastructure SQL scripts belong in the `snowflake_setup/` folder.

| File | What it does |
|---|---|
| `01_warehouse_database.sql` | Creates the Snowflake warehouse and database. |
| `02_roles.sql` | Creates roles for dlt, dbt, and Streamlit. |
| `03_schemas.sql` | Creates the raw, staging, and marts schemas. |
| `04_grants.sql` | Assigns the necessary permissions to each role. |
| `05_verify_grants.sql` | Verifies that each role has the correct permissions. |

The scripts are numbered because they need to be executed in a logical order. For example, the database must exist before we can create schemas inside it.

## 4. Environment Variables and Security

We use two environment configuration files:

- **`.env.example`** — A template listing the configuration variables required by the project.
- **`.env`** — Stores the actual local credentials and is excluded from Git using `.gitignore`.

Passwords, API keys, and other sensitive credentials must never be committed to GitHub.

## 5. Verification

After executing the infrastructure scripts, we'll check that:

1. The warehouse and database exist.
2. All three Snowflake roles and schemas exist.
3. dlt has permission to load raw data.
4. dbt can read raw data and create models.
5. Streamlit has read-only access to the marts.

These checks help us confirm that each component has the correct permissions before building our data pipelines.

## 6. Next Steps

Once the Snowflake infrastructure is verified, we'll begin developing our Steam data ingestion pipeline using Python and dlt.

The overall workflow will be:

**Steam Data Source → Python + dlt → Snowflake Raw → dbt → Analytics Marts → Streamlit**

Later, we'll use Apache Airflow running inside Docker to orchestrate the ingestion, transformation, and testing processes.