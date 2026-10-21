
-- 01: Warehouse and database setup.
-- Execute using SYSADMIN.

USE ROLE SYSADMIN;

-- Create the compute warehouse
CREATE WAREHOUSE IF NOT EXISTS STEAM_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

-- Create the database
CREATE DATABASE IF NOT EXISTS STEAM_DB;


-- Verify the active role
SELECT CURRENT_ROLE() AS ACTIVE_ROLE;

-- Verify warehouse creation and configuration
SHOW WAREHOUSES LIKE 'STEAM_WH';

-- Verify database creation
SHOW DATABASES LIKE 'STEAM_DB';

