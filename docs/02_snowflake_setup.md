# Snowflake Infrastructure Setup

## Overview

This folder contains the SQL scripts used to set up Snowflake for the **Steam Games & Reviews Data Platform**.

We use Snowflake to store raw Steam data, transform it using dbt, and provide analytics-ready data to Streamlit.

The setup follows **Role-Based Access Control (RBAC)** so that each service only has access to what it needs.

## 1. Warehouse and Database

**File:** `01_warehouse_database.sql`

Created two Snowflake objects:

- `STEAM_WH` — Virtual warehouse that provides compute power for running queries and transformations.
- `STEAM_DB` — Database that stores our schemas, tables, and views.

Warehouse configuration:
- Size: `XSMALL`
- Auto-suspend: 60 seconds of inactivity
- Auto-resume: Enabled
- Initially suspended: Yes

**Executed using:** `SYSADMIN`

## 2. Roles

**File:** `02_roles.sql`

Created three roles with separate responsibilities.

| Role | Purpose |
|---|---|
| `STEAM_LOADER` | Loads raw data using dlt |
| `STEAM_TRANSFORMER` | Transforms data using dbt |
| `STEAM_REPORTER` | Reads analytics data using Streamlit |

These roles were granted to `SYSADMIN`, which inherits their permissions.

**Executed using:** `USERADMIN`

## 3. Schemas and Ownership

**File:** `03_schemas.sql`

Created four schemas inside `STEAM_DB`.

| Schema | Purpose | Owner |
|---|---|---|
| `STEAM_RAW` | Raw data ingestion | `STEAM_LOADER` |
| `STAGING` | Cleaning and standardization | `STEAM_TRANSFORMER` |
| `INTERMEDIATE` | Joins and business logic | `STEAM_TRANSFORMER` |
| `MARTS` | Fact tables, dimensions, and analytics | `STEAM_TRANSFORMER` |

Ownership allows the assigned role to manage its schema.

**Executed using:** `SYSADMIN`

## 4. Grants and Permissions

**File:** `04_grants.sql`

Configured permissions following the **principle of least privilege**.

- **Loader:** Manages the raw schema.
- **Transformer:** Reads raw data and manages staging, intermediate, and marts.
- **Reporter:** Reads curated tables and views from marts only.

All three roles received `USAGE` privileges on `STEAM_WH` and `STEAM_DB`.

We also configured:

- `SELECT ON ALL` — Access to existing tables and views.
- `SELECT ON FUTURE` — Automatic read access to new tables and views.

This means new data can become accessible to the appropriate service without manually granting permissions each time.

**Executed using:** `SECURITYADMIN`

## 5. Data Flow

```text
Steam Data Source
        |
        v
 Python + dlt
        |
        v
 STEAM_DB.STEAM_RAW
        |
        v
 dbt - STAGING
        |
        v
 dbt - INTERMEDIATE
        |
        v
 dbt - MARTS
        |
        v
 Streamlit Dashboard
```

## 6. Security and Best Practices

- Separate roles for ingestion, transformation, and reporting.
- Grant only the permissions each service needs.
- Use schema ownership to separate responsibilities.
- Keep passwords and credentials out of Git.
- Store local secrets in `.env`, with `.env.example` as a public template.
- Configure service users separately.

## Next Step

**`05_verify_grants.sql`**

Verify that each role can access only its intended Snowflake objects, including testing that unauthorized access is denied.

**Reference:** [Flight Punctuality — PR #2](https://github.com/indiramahadiva/Flight-punctuality_4_DE25/pull/2)
