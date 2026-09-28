"""Index-based ViText2SQL bridge, outside the frozen research pipeline.

SQL is parsed and resolved by SELECT scope. Never replace substrings in literals.
Unsupported or ambiguous constructs fail closed rather than guessing identifiers.
"""

import re
import sqlite3
from contextlib import closing

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import Scope, traverse_scope

from backend.services.spider_database import SpiderDatabaseService


class SchemaMappingError(ValueError):
    pass


def quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class SchemaMapper:
    def __init__(self, databases: SpiderDatabaseService):
        self.databases = databases

    def build_mapping(self, db_id: str) -> dict:
        metadata = self.databases.get_schema(db_id)
        path = self.databases.resolve_path(db_id)
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
                # Same ordering as build_sqlite_schema() in the evaluation notebook.
                names = [row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"
                )]
                if len(names) != len(metadata["tables"]):
                    raise SchemaMappingError("Số bảng SQLite không khớp metadata ViText2SQL.")
                mapping = {}
                for table, physical in zip(metadata["tables"], names):
                    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({quoted(physical)})")]
                    if len(columns) != len(table["columns"]):
                        raise SchemaMappingError("Số cột SQLite không khớp metadata ViText2SQL.")
                    key = table["name"].casefold()
                    column_map = {}
                    for col, name in zip(table["columns"], columns):
                        column_key = col["name"].casefold()
                        column_map[column_key] = None if column_key in column_map else name
                    if key in mapping:
                        raise SchemaMappingError("Tên bảng trùng lặp; không thể ánh xạ duy nhất.")
                    mapping[key] = {"table": physical, "columns": column_map}
                return mapping
        except sqlite3.Error as exc:
            raise SchemaMappingError("Không thể đọc schema vật lý SQLite.") from exc

    @staticmethod
    def _quote_phrases(sql: str, mapping: dict) -> str:
        # Evaluation SQL can contain unquoted Vietnamese identifiers with spaces.
        # Quote exact, longest schema phrases only in unquoted text, then parse.
        names = set(mapping)
        for table in mapping.values():
            names.update(table["columns"])
        phrases = sorted((name for name in names if len(name.split()) > 1), key=len, reverse=True)
        if not phrases:
            return sql
        pattern = re.compile(r"(?<![\w])(?:" + "|".join(
            r"\s+".join(re.escape(word) for word in phrase.split()) for phrase in phrases
        ) + r")(?![\w])", re.I)
        protected = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]|--[^\n]*|/\*[\s\S]*?\*/)")
        parts = protected.split(sql)
        for index in range(0, len(parts), 2):
            parts[index] = pattern.sub(lambda match: quoted(' '.join(match[0].split())), parts[index])
        return ''.join(parts)

    @staticmethod
    def _normalize_double_quoted_literals(sql: str, mapping: dict) -> str:
        schema_names = set(mapping)
        for table in mapping.values():
            schema_names.update(table["columns"])

        def replace(match):
            value = match.group(1).replace('""', '"')
            if value.casefold() in schema_names:
                return match.group(0)
            return "'" + value.replace("'", "''") + "'"

        return re.sub(r'"((?:""|[^"])*)"', replace, sql)

    def map_sql(self, db_id: str, sql: str) -> str:
        if not isinstance(sql, str) or not sql.strip() or len(sql) > 20000:
            raise SchemaMappingError("SQL trống hoặc vượt giới hạn độ dài.")
        mapping = self.build_mapping(db_id)
        sql = self._normalize_double_quoted_literals(sql, mapping)
        try:
            statements = sqlglot.parse(self._quote_phrases(sql, mapping), read="sqlite")
            if len(statements) != 1 or not isinstance(statements[0], exp.Select):
                raise SchemaMappingError("Mapping chỉ hỗ trợ một câu SELECT.")
            tree = statements[0]
            # Keep the accepted subset explicit. Existing execution safety remains
            # authoritative after mapping, including function authorization.
            if any(tree.find_all(exp.With, exp.SetOperation, exp.Into, exp.Placeholder)):
                raise SchemaMappingError("WITH, UNION/INTERSECT/EXCEPT, INTO hoặc tham số chưa được hỗ trợ.")
            if any(alias.args.get("columns") for alias in tree.find_all(exp.TableAlias)):
                raise SchemaMappingError("Danh sách đổi tên cột trên alias bảng chưa được hỗ trợ.")
            for join in tree.find_all(exp.Join):
                if join.args.get("using") or join.args.get("method") == "NATURAL":
                    raise SchemaMappingError("JOIN USING/NATURAL chưa thể ánh xạ an toàn; cần JOIN ON.")
            scopes = traverse_scope(tree)
            by_select = {id(scope.expression): scope for scope in scopes}
            environments = {}
            table_updates = []
            for scope in scopes:
                env = {}
                for alias, (_, source) in scope.selected_sources.items():
                    key = alias.casefold()
                    if key in env:
                        raise SchemaMappingError("Alias bảng bị trùng.")
                    if isinstance(source, exp.Table):
                        if source.db or source.catalog or not isinstance(source.this, exp.Identifier):
                            raise SchemaMappingError("Không hỗ trợ database qualifier hoặc table function.")
                        info = mapping.get(source.name.casefold())
                        if info is None:
                            raise SchemaMappingError("Tên bảng không tồn tại trong schema ViText2SQL.")
                        env[key] = (alias, info["columns"])
                        table_updates.append((source, info["table"], alias))
                    elif isinstance(source, Scope):
                        # Derived tables are deterministic only with explicit,
                        # unique output aliases; wildcard/inferred labels rejected.
                        outputs = source.expression.selects
                        if not outputs or any(not isinstance(item, exp.Alias) for item in outputs):
                            raise SchemaMappingError("Bảng con cần AS rõ ràng cho từng cột đầu ra.")
                        columns = {item.alias.casefold(): item.alias for item in outputs}
                        if len(columns) != len(outputs):
                            raise SchemaMappingError("Alias cột bảng con bị trùng.")
                        env[key] = (alias, columns)
                    else:
                        raise SchemaMappingError("Nguồn dữ liệu không được hỗ trợ.")
                environments[id(scope)] = env

            def resolve(scope, column):
                qualifier, name = column.table.casefold(), column.name.casefold()
                current = scope
                while current:
                    env = environments[id(current)]
                    if qualifier:
                        if qualifier in env:
                            alias, columns = env[qualifier]
                            if name == '*' or name in columns:
                                return alias, columns.get(name, '*')
                            raise SchemaMappingError("Cột không thuộc alias/bảng đã chỉ định.")
                    else:
                        matches = [(alias, columns[name]) for alias, columns in env.values() if name in columns]
                        if len(matches) > 1:
                            raise SchemaMappingError("Cột không có qualifier và khớp nhiều bảng.")
                        if matches:
                            return matches[0]
                    current = current.parent if current.can_be_correlated else None
                raise SchemaMappingError("Không xác định được cột hoặc alias trong phạm vi truy vấn.")

            for column in list(tree.find_all(exp.Column)):
                if column.db or column.catalog:
                    raise SchemaMappingError("Column qualifier nhiều cấp chưa được hỗ trợ.")
                scope = by_select.get(id(column.find_ancestor(exp.Select)))
                if scope is None:
                    raise SchemaMappingError("Không xác định được phạm vi cột.")
                aliases = [item.alias.casefold() for item in scope.expression.selects if isinstance(item, exp.Alias)]
                if not column.table and column.name.casefold() in aliases:
                    context = column.find_ancestor(exp.Order, exp.Group, exp.Having, exp.Select)
                    if isinstance(context, (exp.Order, exp.Group, exp.Having)):
                        if aliases.count(column.name.casefold()) > 1 or any(
                            column.name.casefold() in cols for _, cols in environments[id(scope)].values()
                        ):
                            raise SchemaMappingError("Alias đầu ra mơ hồ với tên cột.")
                        continue
                alias, physical = resolve(scope, column)
                if physical is None:
                    raise SchemaMappingError("Tên cột tiếng Việt tương ứng nhiều cột vật lý.")
                if not column.is_star:
                    column.set("this", exp.to_identifier(physical, quoted=True))
                column.set("table", exp.to_identifier(alias, quoted=True))
            for table, physical, alias in table_updates:
                table.set("this", exp.to_identifier(physical, quoted=True))
                # Preserve source names even for an originally unaliased table.
                table.set("alias", exp.TableAlias(this=exp.to_identifier(alias, quoted=True)))
            # Never use transpilation as a way to admit non-SELECT statements.
            return tree.sql(dialect="sqlite", comments=False)
        except (SqlglotError, RecursionError) as exc:
            raise SchemaMappingError("Không thể phân tích hoặc ánh xạ SQL một cách xác định.") from exc
