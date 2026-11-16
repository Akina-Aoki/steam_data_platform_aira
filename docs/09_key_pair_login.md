# 09 Key-Pair Login for the dlt Loader

## Overview

The dlt loader (`DLT_USER`, role `STEAM_LOADER`) now logs in to Snowflake with a **key pair** instead of a password.

**Branch:** `feat/schedule-run`
**Status:** Done. Tested with a login check and with a full pipeline run on 2026-10-30 (load id `1793369111.4503539`, 81 rows in each of the three tables).

```text
Before:  .env password  ->  dlt  ->  Snowflake
Now:     private key file (outside the repo)  ->  dlt  ->  Snowflake
         public key stored on the user DLT_USER in Snowflake
```

## 1. Why We Did It

| Fact | Source |
|---|---|
| `DLT_USER` is a `PERSON` user with a password and **no MFA** (`HAS_MFA = false`) | `DESC USER DLT_USER` on 2026-10-30 |
| That is why a password-only load worked | same |
| Snowflake is phasing out password-only sign-in for human (`PERSON`) users. Phase 3 is planned for Aug to Oct 2026, per account, "subject to change". | Snowflake's page on the MFA rollout (read on 2026-10-30) |
| The page does not name dlt or the Python connector. That a password-only load from dlt would be blocked is **our reading**, not a statement from the page. | |
| We do not know the date for our account. The last password-only load worked on 2026-10-27. | |

**Decision:** switch to a key pair now, so a scheduled run does not fail with a login error later. A key pair is also what Dagster (future work) will need, because it cannot type a code.

**Why it is not in the reference repo:** the reference project logs in with a password from `.env`. We keep its structure (`connections.py` with `loader_credentials()`), and change only how the loader proves who it is.

## 2. What Is Where

| Piece | Where | In Git? |
|---|---|---|
| Private key (`dlt_user_rsa_key.p8`) | `C:\Users\adelo\.snowflake_keys\`, outside the repo | **No, never.** Not read, printed or pasted anywhere. |
| Public key (`dlt_user_rsa_key.pub`) | The same folder, and stored on the Snowflake user | No. It is not secret. |
| Path to the private key | Variable `SNOWFLAKE_LOADER_PRIVATE_KEY_PATH` in `.env` | `.env` is ignored. The name (no value) is in [`.env.example`](../.env.example). |
| Code | [`loader_credentials()`](../src/steam_data_platform/connections.py) passes `private_key_path` to dlt | Yes |
| Test | [`test_connections.py`](../tests/test_connections.py): the credentials contain the key path and no password | Yes |

## 3. How We Did It

| Step | Command or action | Notes |
|---|---|---|
| 1 | `mkdir -p ~/.snowflake_keys` | A folder in the user directory. `.snowflake_keys`, not `.snowflake`, so Snowflake's own tools do not use it. |
| 2 | `openssl genrsa 2048 \| openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake_keys/dlt_user_rsa_key.p8 -nocrypt` | Private key. PKCS8 PEM is a text format, which dlt can read. Not encrypted, see section 5. |
| 3 | `openssl rsa -in ...p8 -pubout -out ...pub` | Public key made from the private key |
| 4 | `ALTER USER DLT_USER SET RSA_PUBLIC_KEY = '...'` as `USERADMIN` | The public key without the `BEGIN` and `END` lines. Undo with `ALTER USER DLT_USER UNSET RSA_PUBLIC_KEY;`. |
| 5 | `DESC USER DLT_USER` | `HAS_KEYPAIR = true` and a `SHA256:` fingerprint |
| 6 | Code and `.env` change | `private_key_path` instead of `password` |
| 7 | A one-off login check (a local script, not in Git) | It printed `('DLT_USER', 'STEAM_LOADER', 'STEAM_WH')` |
| 8 | A normal full run, the same command as always (section 7) | See section 5: it loaded all three tables with the key. |

**How dlt reads the key.** We checked the installed dlt package. `SnowflakeCredentials` accepts `private_key`, `private_key_path` and `private_key_passphrase`. With `private_key_path`, dlt reads the file as text, decodes it and passes it to the Snowflake connector. The password is then `None`. So the successful login check shows that the **key** worked, not the password.

## 4. Why We Did Not Change More

| Not done | Reason |
|---|---|
| The password was not removed from the user | It is a fallback while we test, and it is easy to undo. Nothing in the project needs it any more. |
| `DLT_USER` stays `PERSON`, not changed to `SERVICE` | Smallest change. Snowflake's docs say a `SERVICE` user cannot sign in with a password, and the type can be changed later with `ALTER USER ... SET TYPE`. We did not need it yet. |
| `05_create_users.sql` has no `TYPE` line | The default type is `PERSON` (Snowflake's `CREATE USER` page), so the file now matches the real user and the reference project. |
| No scheduler | The loader is run by hand, **once an hour at most**. Dagster is future work ([doc 15](15_hourly_runs_plan.md)). |

## 5. Known Limits and Risks

| Item | Detail |
|---|---|
| Key file is not encrypted | A scheduled or unattended run then needs no passphrase. The file sits in the user folder. Anyone who can read it can log in as `DLT_USER`. Do not copy it, commit it or send it. |
| Full pipeline run with the key | **Done on 2026-10-30.** 243 requests, no 429, about 10 minutes (15:05 to 15:15 Stockholm time). Load `1793369111.4503539` has status 0 and 81 rows in `GAMES`, `REVIEW_SUMMARY` and `PLAYER_COUNTS`. Older loads were not changed. We ran it as a normal daily run, not as a separate test, because `append` adds rows on every run. |
| Notebooks 01 to 03 | **Done on 2026-10-30.** Their connect cell uses `private_key_file=os.environ["SNOWFLAKE_LOADER_PRIVATE_KEY_PATH"]` instead of the password. All three connected and ran. |
| `DBT_USER` and `STREAMLIT_USER` | They are also `PERSON` users with passwords, so dbt Core and Streamlit may run into the same problem. **`DBT_USER` (decided 2026-11-02):** keeps the password (`HAS_MFA = false`), see [doc 10](10_dbt_sources_staging.md). `STREAMLIT_USER` is decided when Streamlit is built. |
| Dates | The rollout dates come from Snowflake's page and are "subject to change". We do not know the date for our account. |

## 6. Open Items

- ~~Update the connect cell in notebooks 01 to 03 to use the key.~~ Done on 2026-10-30.
- Decide later whether to remove the password from `DLT_USER`, or change it to `SERVICE`. Read Snowflake's docs first.
- `DBT_USER` keeps the password for now. If Snowflake blocks passwords, repeat the steps in this doc for `DBT_USER`. Decide for `STREAMLIT_USER` when Streamlit is built.
- Dagster: the same key and `loader_credentials()` can be used there.

## 7. How to Run

Unchanged, once an hour at most:

```bash
uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
```

The `.env` needs `SNOWFLAKE_LOADER_PRIVATE_KEY_PATH` (with forward slashes, for example `C:/Users/<you>/.snowflake_keys/dlt_user_rsa_key.p8`).

## 8. Related Files

| File | Purpose |
|---|---|
| [`connections.py`](../src/steam_data_platform/connections.py) | `loader_credentials()` |
| [`test_connections.py`](../tests/test_connections.py) | Test for the credentials |
| [`.env.example`](../.env.example) | Variable names, no values |
| [`03_snowflake_users_dbt_initialization.md`](03_snowflake_users_dbt_initialization.md) | How the users were first set up |
| [`08_steam_py_code_guide.md`](08_steam_py_code_guide.md) | A guide to read next to `steam.py` |
