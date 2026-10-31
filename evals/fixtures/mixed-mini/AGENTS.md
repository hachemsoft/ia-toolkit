# Orders data and API

`models/` is a dbt project (development target `dev`); `api/` is a Python service that reads the `orders` model.

## Verifying your work
| Stack | Changed | Full |
| --- | --- | --- |
| dbt | `dbt build --select orders+ --target dev` | `dbt build --target dev` |
| Python | `python -m pytest api` | `python -m pytest` |
