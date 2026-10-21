
-- Create the service user for dlt ingestion
USE ROLE USERADMIN;

CREATE USER IF NOT EXISTS DLT_USER
    TYPE = SERVICE
    DEFAULT_ROLE = STEAM_LOADER
    DEFAULT_WAREHOUSE = STEAM_WH
    DEFAULT_NAMESPACE = 'STEAM_DB.STEAM_RAW'
    COMMENT = 'Service user for Steam data ingestion using dlt';

-- Verify user creation
SHOW USERS LIKE 'DLT_USER';



-- Switch to the security administration role
USE ROLE SECURITYADMIN;

-- Assign the loader role to our service user
GRANT ROLE STEAM_LOADER TO USER DLT_USER;

-- Verify the role assignment
SHOW GRANTS TO USER DLT_USER;
