"""Metadata and bounded read-only execution for local Spider databases."""

import json
import math
import re
import sqlite3
import time
from contextlib import closing
from functools import lru_cache

from backend.config import PROJECT_ROOT, Settings, get_settings


class SpiderDatabaseError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class SpiderDatabaseService:
    MAX_ROWS = 100
    TIMEOUT_SECONDS = 2
    # Unknown functions are denied, including extension/file-access functions.
    SAFE_FUNCTIONS = frozenset("""
        abs avg coalesce count date datetime dense_rank first_value format glob
        group_concat hex ifnull iif instr julianday lag last_value lead length like
        likelihood likely lower ltrim max min mod nth_value ntile nullif percent_rank
        printf quote rank replace round row_number rtrim sign strftime substr substring
        sum time total trim typeof unicode unixepoch unlikely upper cume_dist
    """.split())

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.root = (PROJECT_ROOT / settings.spider_db_path).resolve()
        try:
            data = json.loads((PROJECT_ROOT / "data/tables.json").read_text(encoding="utf-8"))
            self.schemas = {item["db_id"]: item for item in data}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SpiderDatabaseError("Không thể đọc metadata ViText2SQL.", 503) from exc

    def _schema(self, db_id: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_]+", db_id):
            raise SpiderDatabaseError("db_id không hợp lệ.")
        if db_id not in self.schemas:
            raise SpiderDatabaseError("Không tìm thấy db_id trong ViText2SQL.", 404)
        return self.schemas[db_id]

    def resolve_path(self, db_id: str):
        self._schema(db_id)
        path = (self.root / db_id / f"{db_id}.sqlite").resolve()
        if not path.is_relative_to(self.root):
            raise SpiderDatabaseError("Đường dẫn database nằm ngoài Spider root.")
        if not path.is_file():
            raise SpiderDatabaseError("Không tìm thấy file SQLite của database.", 404)
        return path

    def list_databases(self) -> list[dict]:
        return [
            {"db_id": db_id, "table_count": len(schema["table_names"]),
             "table_names": schema["table_names"]}
            for db_id, schema in sorted(self.schemas.items())
        ]

    def get_schema(self, db_id: str) -> dict:
        schema = self._schema(db_id)
        columns = [
            {"column_id": index, "table_id": table_id, "name": name,
             "data_type": schema["column_types"][index],
             "primary_key": index in schema["primary_keys"]}
            for index, (table_id, name) in enumerate(schema["column_names"])
        ]
        return {
            "db_id": db_id,
            "tables": [
                {"table_id": index, "name": name,
                 "columns": [column for column in columns if column["table_id"] == index]}
                for index, name in enumerate(schema["table_names"])
            ],
            "columns": columns,  # Includes Spider's wildcard column (table_id=-1).
            "primary_keys": schema["primary_keys"],
            "foreign_keys": schema["foreign_keys"],
        }

    @classmethod
    def _authorize(cls, action, arg1, arg2, database, source):
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in cls.SAFE_FUNCTIONS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    def execute(self, db_id: str, sql: str) -> dict:
        path = self.resolve_path(db_id)
        # Deliberately narrow grammar: leading comments and WITH are not enabled.
        # SQLite's authorizer and single-statement execute enforce the real boundary.
        if not isinstance(sql, str) or len(sql) > 20000 or not re.match(r"\s*SELECT\b", sql, re.I):
            raise SpiderDatabaseError("Chỉ cho phép một câu lệnh SELECT (tối đa 20000 ký tự).")
        deadline = time.monotonic() + self.TIMEOUT_SECONDS
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as connection:
                connection.enable_load_extension(False)
                connection.execute("PRAGMA query_only = ON")
                # Bound expression/cell size where Python's sqlite3 exposes limits.
                if hasattr(connection, "setlimit"):
                    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
                connection.set_authorizer(self._authorize)
                connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                with closing(connection.cursor()) as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchmany(self.MAX_ROWS + 1)
                    columns = [item[0] for item in cursor.description]
                    # Represent BLOBs explicitly rather than attempting UTF-8 decoding.
                    values = [[{"hex": cell.hex()} if isinstance(cell, bytes)
                               else str(cell) if isinstance(cell, float) and not math.isfinite(cell)
                               else cell
                               for cell in row] for row in rows[:self.MAX_ROWS]]
                    return {"columns": columns, "rows": values, "row_count": len(values),
                            "truncated": len(rows) > self.MAX_ROWS}
        except (sqlite3.Error, sqlite3.Warning, UnicodeError) as exc:
            if time.monotonic() >= deadline:
                raise SpiderDatabaseError("Truy vấn vượt thời gian cho phép.", 408) from exc
            raise SpiderDatabaseError(
                "Không thể thực thi SELECT: SQL không hợp lệ, không được phép hoặc database không đọc được."
            ) from exc


@lru_cache
def get_spider_database_service() -> SpiderDatabaseService:
    return SpiderDatabaseService()
