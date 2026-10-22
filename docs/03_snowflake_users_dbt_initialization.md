# Snowflake Users and dbt Initialization

## Overview
Configured Snowflake access for the three components of the Steam Data Platform, initialized dbt Core, and merged the setup into `main`.

## 1. Snowflake Users and Roles

| User | Role | Default schema | Purpose |
|---|---|---|---|
| `DLT_USER` | `STEAM_LOADER` | `STEAM_RAW` | Ingest Steam data using dlt |
| `DBT_USER` | `STEAM_TRANSFORMER` | `STAGING` | Transform data using dbt Core |
| `STREAMLIT_USER` | `STEAM_REPORTER` | `MARTS` | Read analytics data for dashboards |

All three users use `STEAM_WH` and `STEAM_DB`. Permissions separate ingestion, transformation, and reporting: dbt can read raw data, while the reporter has read-only access to marts.

Snowflake setup scripts are in `snowflake_setup/`, including `05_create_users.sql` and `06_access_setup.sql`.

## 2. Connection and Security Checks

- Stored local credentials in `.env` (excluded from Git).
- Kept connection settings in `.env.example` without passwords.
- Tested each user with Python and the Snowflake connector.
- Verified the expected user, role, warehouse, database, and schema for all three connections.

> **Follow-up:** Align `05_create_users.sql` with the actual `DLT_USER` account type (`PERSON` was used for the successful local password/MFA connection; the committed script still specifies `SERVICE`).

## 3. dbt Core Setup

Initialized dbt under `dbt_project/`, separate from the Python application in `src/`.

Key files:

- `dbt_project/dbt_project.yml` — dbt project settings.
- `dbt_project/profiles.yml` — Snowflake connection using `env_var()`.
- `dbt_project/models/`, `macros/`, `tests/`, `seeds/` — dbt development folders.

From inside `dbt_project/`, validated the project with:

```bash
uv run --env-file ../.env dbt debug --profiles-dir .
```

**Result:** `profiles.yml` valid, `dbt_project.yml` valid, Snowflake connection OK, and **All checks passed!**

## 4. Git Workflow

- Pushed and merged `feat/snowflake-dlt-connect` into `main`.
- Updated local `main` with `git pull origin main` (fast-forward).
- Created `feat/dbt-foundation` from the updated `main`.
- Confirmed the new branch had a clean working tree.

## Next Steps

Configure dbt model layers (`STAGING`, `INTERMEDIATE`, `MARTS`), define Steam raw sources, and build and test the first staging models.
