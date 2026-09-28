"""Read-only checks against the existing local Spider files; no model imports."""

import unittest

from backend.services.spider_database import SpiderDatabaseError, SpiderDatabaseService


class SpiderDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = SpiderDatabaseService()

    def test_catalog_and_files(self):
        self.assertEqual(len(self.service.list_databases()), 166)
        for db_id in self.service.schemas:
            self.assertTrue(self.service.resolve_path(db_id).is_file())

    def test_requested_schemas(self):
        for db_id in ("academic", "cinema", "college_2"):
            schema = self.service.get_schema(db_id)
            self.assertEqual(schema["db_id"], db_id)
            self.assertTrue(schema["tables"])
            self.assertTrue(schema["columns"])

    def test_select_limit_and_aggregate(self):
        result = self.service.execute("academic", 'SELECT * FROM "author"')
        self.assertTrue(result["columns"])
        self.assertEqual(result["row_count"], len(result["rows"]))
        self.assertLessEqual(result["row_count"], 100)
        total = self.service.execute("academic", 'SELECT count(*) FROM "author"')
        self.assertEqual(result["truncated"], total["rows"][0][0] > 100)
        # Academic may contain empty tables; catalog cross join verifies truncation
        # independently of dataset row contents, without creating fixture data.
        catalog = self.service.execute(
            "academic", "SELECT a.name FROM sqlite_master a CROSS JOIN sqlite_master b"
        )
        self.assertEqual(catalog["row_count"], 100)
        self.assertTrue(catalog["truncated"])

    def test_unsafe_sql(self):
        for sql in (
            'DELETE FROM author', 'UPDATE author SET aid=1', 'INSERT INTO author VALUES (1)',
            'DROP TABLE author', 'ALTER TABLE author ADD COLUMN x', 'CREATE TABLE x (a)',
            'REPLACE INTO author VALUES (1)', "ATTACH ':memory:' AS other", 'DETACH main',
            'PRAGMA table_info(author)', 'VACUUM', 'BEGIN', 'EXPLAIN SELECT 1',
            'SELECT 1; DELETE FROM author', "SELECT load_extension('missing')",
            "SELECT * FROM pragma_table_info('author')", "SELECT writefile('x', 'x')",
            "SELECT * FROM missing_table",
        ):
            with self.subTest(sql=sql), self.assertRaises(SpiderDatabaseError):
                self.service.execute("academic", sql)

    def test_unknown_and_traversal(self):
        for db_id in ('unknown_database', '../academic', '..', 'C:\\academic', 'academic/x', 'academic%2f..'):
            with self.subTest(db_id=db_id), self.assertRaises(SpiderDatabaseError):
                self.service.resolve_path(db_id)

    def test_missing_file_and_symlink_escape(self):
        from pathlib import Path
        from unittest.mock import patch
        with patch.object(Path, 'is_file', return_value=False):
            with self.assertRaises(SpiderDatabaseError) as error:
                self.service.resolve_path('academic')
            self.assertEqual(error.exception.status_code, 404)
        with patch.object(Path, 'resolve', return_value=self.service.root.parent / 'outside.sqlite'):
            with self.assertRaises(SpiderDatabaseError):
                self.service.resolve_path('academic')


if __name__ == '__main__':
    unittest.main()
