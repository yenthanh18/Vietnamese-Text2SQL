"""Synthetic model responses exist only in tests, never in the application."""
import sys
import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.model_runtime import ModelRuntime
from backend.services.schema_mapper import SchemaMapper, SchemaMappingError
from backend.services.spider_database import SpiderDatabaseService
from backend.services.text2sql import Text2SQLService


class SchemaMapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.databases = SpiderDatabaseService()
        cls.mapper = SchemaMapper(cls.databases)

    def test_known_databases(self):
        for db, sql, physical in [
            ('cinema', 'SELECT tiêu đề FROM phim', 'SELECT Title FROM film'),
            ('academic', 'SELECT tên FROM tác giả', 'SELECT name FROM author'),
            ('college_2', 'SELECT s.tên FROM sinh viên AS s', 'SELECT name FROM student'),
        ]:
            with self.subTest(db=db):
                mapped = self.mapper.map_sql(db, sql)
                self.assertIn('"' + physical.split()[-1] + '"', mapped)
                self.assertIn('"' + physical.split()[1] + '"', mapped)
                self.assertEqual(self.databases.execute(db, mapped)['rows'], self.databases.execute(db, physical)['rows'])

    def test_literals_join_aggregate(self):
        sql = """SELECT f."tiêu đề", count(*) AS total FROM "phim" f
                 JOIN "lịch chiếu phim" s ON f."id phim" = s."id phim"
                 WHERE f."tiêu đề" <> 'phim và ''tiêu đề'''
                 GROUP BY f."tiêu đề" ORDER BY total DESC"""
        mapped = self.mapper.map_sql('cinema', sql)
        self.assertIn("'phim và ''tiêu đề'''", mapped)
        self.assertIn('"Title"', mapped)
        self.assertIn('"schedule"', mapped)
        self.databases.execute('cinema', mapped)

    def test_nested_queries(self):
        for sql in [
            'SELECT f.tiêu đề FROM phim f WHERE EXISTS (SELECT 1 FROM lịch chiếu phim s WHERE s.id phim = f.id phim)',
            'SELECT tên FROM rạp chiếu phim WHERE sức chứa > (SELECT avg(sức chứa) FROM rạp chiếu phim)',
            'SELECT d.title FROM (SELECT tiêu đề AS title FROM phim) d',
            'SELECT f.tiêu đề FROM phim f WHERE EXISTS (SELECT 1 FROM phim f WHERE f.id phim > 1)',
        ]:
            with self.subTest(sql=sql):
                self.databases.execute('cinema', self.mapper.map_sql('cinema', sql))

    def test_fail_closed(self):
        for sql in [
            'DELETE FROM phim', 'SELECT 1; DELETE FROM phim',
            'SELECT id phim FROM phim f JOIN lịch chiếu phim s ON f.id phim=s.id phim',
            'SELECT unknown FROM phim', 'SELECT * FROM unknown',
            'SELECT "not a known identifier" FROM phim',
            'SELECT * FROM phim NATURAL JOIN lịch chiếu phim',
            'SELECT * FROM phim JOIN lịch chiếu phim USING (id phim)',
            'SELECT d.* FROM (SELECT tiêu đề FROM phim) d',
            'WITH x AS (SELECT * FROM phim) SELECT * FROM x',
            'SELECT * FROM phim AS f(a, b)',
        ]:
            with self.subTest(sql=sql), self.assertRaises(SchemaMappingError):
                self.mapper.map_sql('cinema', sql)
        with self.assertRaises(SchemaMappingError):
            self.mapper.map_sql('academic', 'SELECT số lượng trích dẫn FROM bài báo')
        with self.assertRaises(SchemaMappingError):
            self.mapper.build_mapping('cre_Drama_Workshop_Groups')

    def test_schema_mismatch(self):
        metadata = self.databases.get_schema('cinema')
        metadata['tables'].pop()
        with patch.object(self.databases, 'get_schema', return_value=metadata):
            with self.assertRaises(SchemaMappingError):
                self.mapper.build_mapping('cinema')


class QueryApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_validation(self):
        for body in ({'question': '   ', 'db_id': 'cinema'}, {'question': 'test'},
                     {'question': 'test', 'db_id': '../cinema'}):
            self.assertEqual(self.client.post('/api/query', json=body).status_code, 422)
        self.assertEqual(self.client.post('/api/query', json={'question': 'test', 'db_id': 'unknown'}).status_code, 404)

    def test_unloaded(self):
        with patch('backend.routers.query.get_text2sql_service') as service:
            response = self.client.post('/api/query', json={'question': 'test', 'db_id': 'cinema'})
            self.assertEqual(response.status_code, 503)
            self.assertIn('Model chưa tải', response.json()['detail'])
            service.assert_not_called()
        self.assertFalse(self.client.get('/nlp/status').json()['model_loaded'])
        self.assertNotIn('torch', sys.modules)

    def test_orchestration_mock_only(self):
        metadata = {'tagged_question': '[COL: tiêu đề]', 'e2_sql': 'SELECT tiêu đề FROM phim',
                    'e3_triggered': False, 'schema_violations': 0, 'final_sql': 'SELECT tiêu đề FROM phim'}
        with patch('backend.routers.query.get_model_runtime'), patch('backend.routers.query.get_text2sql_service') as service:
            service.return_value.generate.return_value = metadata
            response = self.client.post('/api/query', json={'question': 'test', 'db_id': 'cinema'})
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data['generated_sql'], metadata['final_sql'])
            self.assertIn('"Title"', data['execution_sql'])
            self.assertEqual(data['row_count'], len(data['rows']))
            self.assertNotIn('answer', data)
            service.return_value.generate.assert_called_once_with('test', 'cinema')
            service.return_value.generate.return_value = {**metadata, 'final_sql': 'DELETE FROM phim'}
            self.assertEqual(self.client.post('/api/query', json={'question': 'test', 'db_id': 'cinema'}).status_code, 422)
            service.return_value.generate.return_value = {**metadata, 'final_sql': "SELECT load_extension('x')"}
            self.assertEqual(self.client.post('/api/query', json={'question': 'test', 'db_id': 'cinema'}).status_code, 400)


class E3RoutingTests(unittest.TestCase):
    def test_e3_only_for_violations(self):
        service = Text2SQLService(Mock(spec=ModelRuntime))
        for violations in (0, 1):
            pipeline = Mock()
            pipeline.apply_dew_tags.return_value = ('tagged test', {})
            pipeline.generate_e2_sql.return_value = 'test E2 SQL'
            pipeline.count_schema_violations.return_value = violations
            pipeline.generate_e3_candidates.return_value = [{'sql': 'test E3 SQL', 'model_score': 0}]
            pipeline.select_e3_candidate.return_value = {'sql': 'test E3 SQL'}
            with patch.object(service, '_bind_pipeline', return_value=pipeline):
                result = service.generate('test', 'cinema')
            sample = {'question': 'tagged test', 'db_id': 'cinema'}
            pipeline.generate_e2_sql.assert_called_once_with(sample)
            self.assertEqual(result['e3_triggered'], bool(violations))
            if violations:
                pipeline.generate_e3_candidates.assert_called_once_with(sample, num_beams=5, num_return_sequences=5)
                pipeline.select_e3_candidate.assert_called_once_with(pipeline.generate_e3_candidates.return_value, 'cinema')
            else:
                pipeline.generate_e3_candidates.assert_not_called()
                pipeline.select_e3_candidate.assert_not_called()
                self.assertEqual(result['final_sql'], 'test E2 SQL')


if __name__ == '__main__':
    unittest.main()
