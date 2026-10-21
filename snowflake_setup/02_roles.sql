
-- 02: Create separate roles for each service.
-- Execute using USERADMIN.

USE ROLE USERADMIN;

-- Data ingestion using dlt
CREATE ROLE IF NOT EXISTS STEAM_LOADER;

-- Data transformation using dbt Core
CREATE ROLE IF NOT EXISTS STEAM_TRANSFORMER;

-- Read-only analytics using Streamlit
CREATE ROLE IF NOT EXISTS STEAM_REPORTER;

-- Connect application roles to SYSADMIN.
-- SYSADMIN inherits the privileges of these roles.
GRANT ROLE STEAM_LOADER TO ROLE SYSADMIN;
GRANT ROLE STEAM_TRANSFORMER TO ROLE SYSADMIN;
GRANT ROLE STEAM_REPORTER TO ROLE SYSADMIN;




-- Confirm active role
SELECT CURRENT_ROLE();

-- Confirm the application roles exist
SHOW ROLES LIKE 'STEAM_%';

-- Verify inheritance
SHOW GRANTS OF ROLE STEAM_LOADER;
SHOW GRANTS OF ROLE STEAM_TRANSFORMER;
SHOW GRANTS OF ROLE STEAM_REPORTER;
