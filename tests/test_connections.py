"""Tests for the Snowflake connection settings. No real Snowflake."""

from steam_data_platform.connections import loader_credentials


def test_loader_credentials_use_a_key_file_and_no_password(monkeypatch):
    values = {
        "SNOWFLAKE_ACCOUNT": "acct",
        "SNOWFLAKE_DATABASE": "db",
        "SNOWFLAKE_WAREHOUSE": "wh",
        "SNOWFLAKE_LOADER_USER": "user",
        "SNOWFLAKE_LOADER_PRIVATE_KEY_PATH": "/keys/key.p8",
        "SNOWFLAKE_LOADER_ROLE": "role",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    credentials = loader_credentials()

    assert credentials["private_key_path"] == "/keys/key.p8"
    assert "password" not in credentials
