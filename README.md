```uv run pytest -q

uv run --env-file .env python -m steam_data_platform.ingestion.pipelines_steam
```

From dbt_project
```
set -a; source ../.env; set +a

dbt build --select # name of model
```
