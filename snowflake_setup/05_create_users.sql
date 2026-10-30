

-- ***********************************************
--  CREATE DLT_USER
-- ***********************************************

-- Create the user for dlt ingestion
USE ROLE USERADMIN;

CREATE USER IF NOT EXISTS DLT_USER
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






-- ***********************************************
--  CREATE DBT_USER
-- ***********************************************


-- Create the user for dbt transformations
USE ROLE USERADMIN;

CREATE USER IF NOT EXISTS DBT_USER
    TYPE = PERSON
    DEFAULT_ROLE = STEAM_TRANSFORMER
    DEFAULT_WAREHOUSE = STEAM_WH
    DEFAULT_NAMESPACE = 'STEAM_DB.STAGING'
    COMMENT = 'User for Steam data transformations using dbt Core';

-- Verify user creation
SHOW USERS LIKE 'DBT_USER';




-- Switch to security administration
USE ROLE SECURITYADMIN;

-- Assign the dbt transformation role
GRANT ROLE STEAM_TRANSFORMER TO USER DBT_USER;

-- Verify the role assignment
SHOW GRANTS TO USER DBT_USER;




-- ***********************************************
--  CREATE STREAMLIT_USER
-- ***********************************************


USE ROLE USERADMIN;

CREATE USER IF NOT EXISTS STREAMLIT_USER
    TYPE = PERSON
    DEFAULT_ROLE = STEAM_REPORTER
    DEFAULT_WAREHOUSE = STEAM_WH
    DEFAULT_NAMESPACE = 'STEAM_DB.MARTS'
    COMMENT = 'User for Steam analytics dashboard using Streamlit';

-- Verify this user
SHOW USERS LIKE 'STREAMLIT_USER';

-- Grant STEAM_REPORTER to STREAMLIT_USER
USE ROLE SECURITYADMIN;

-- Asign the reporting role
GRANT ROLE STEAM_REPORTER TO USER STREAMLIT_USER;

-- Verify
SHOW GRANTS TO USER STREAMLIT_USER;



