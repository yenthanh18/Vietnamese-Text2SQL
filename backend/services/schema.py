from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def extract_schema(connection: Connection) -> list[dict]:
    inspector = inspect(connection)
    tables = []
    for name in sorted(inspector.get_table_names(schema="public")):
        primary_keys = inspector.get_pk_constraint(name, schema="public").get(
            "constrained_columns", []
        )
        tables.append({
            "name": name,
            "columns": [
                {
                    "name": column["name"],
                    "data_type": str(column["type"]),
                    "nullable": column["nullable"],
                }
                for column in inspector.get_columns(name, schema="public")
            ],
            "primary_keys": primary_keys,
            "foreign_keys": [
                {
                    "name": foreign_key["name"],
                    "columns": foreign_key["constrained_columns"],
                    "referred_schema": foreign_key["referred_schema"] or "public",
                    "referred_table": foreign_key["referred_table"],
                    "referred_columns": foreign_key["referred_columns"],
                }
                for foreign_key in inspector.get_foreign_keys(name, schema="public")
            ],
        })
    return tables
