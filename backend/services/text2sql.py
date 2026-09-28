"""Wire research artifacts to the existing pipeline; never execute generated SQL."""

import json
from functools import lru_cache
from threading import RLock

from backend.config import PROJECT_ROOT
from backend.services.model_runtime import ModelRuntime, get_model_runtime

# Exact prompt used in notebook/training.ipynb.
SYSTEM_PROMPT = (
    "You are a Vietnamese Text-to-SQL system. "
    "Convert the user's question into a SQL query."
)
# nlp.pipeline stores globals; serialize binding and generation across services.
_PIPELINE_LOCK = RLock()


class Text2SQLService:
    def __init__(self, runtime: ModelRuntime):
        self.runtime = runtime
        self.tables_data = json.loads(
            (PROJECT_ROOT / "data/tables.json").read_text(encoding="utf-8")
        )
        self.dew_dict = json.loads(
            (PROJECT_ROOT / "nlp/dew_dictionary.json").read_text(encoding="utf-8")
        )
        self.vt_map = {schema["db_id"]: schema for schema in self.tables_data}

    def get_status(self) -> dict:
        return {
            **self.runtime.get_status(),
            "number_of_schemas": len(self.vt_map),
            "dew_available": bool(self.dew_dict),
            "dew_schema_count": len(self.dew_dict),
            "demo_schema_available": "student_management_demo" in self.vt_map,
        }

    def _bind_pipeline(self):
        # pipeline imports torch at module scope. Defer importing it so status and
        # the Web app work even without the optional inference stack installed.
        from nlp import pipeline

        pipeline.tables_data = self.tables_data
        pipeline.vt_map = self.vt_map
        pipeline.SYSTEM_PROMPT = SYSTEM_PROMPT
        pipeline.tokenizer, pipeline.model_e2 = self.runtime.require_loaded()
        return pipeline

    def generate(self, question: str, db_id: str) -> dict:
        self.runtime.require_loaded()
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Câu hỏi không được để trống.")
        if db_id not in self.vt_map:
            raise ValueError(f"db_id không có trong data/tables.json: {db_id}")
        if db_id not in self.dew_dict:
            raise ValueError(f"Không có DEW dictionary cho db_id: {db_id}")
        with _PIPELINE_LOCK:
            pipeline = self._bind_pipeline()
            tagged_question, _ = pipeline.apply_dew_tags(question, db_id, self.dew_dict)
            sample = {"question": tagged_question, "db_id": db_id}
            e2_sql = pipeline.generate_e2_sql(sample)
            violations = pipeline.count_schema_violations(e2_sql, db_id)
            final_sql = e2_sql
            if violations > 0:
                candidates = pipeline.generate_e3_candidates(
                    sample, num_beams=5, num_return_sequences=5,
                )
                final_sql = pipeline.select_e3_candidate(candidates, db_id)["sql"]
            return {
                "raw_question": question,
                "tagged_question": tagged_question,
                "db_id": db_id,
                "e2_sql": e2_sql,
                "schema_violations": violations,
                "e3_triggered": violations > 0,
                "final_sql": final_sql,
            }


@lru_cache
def get_text2sql_service() -> Text2SQLService:
    return Text2SQLService(get_model_runtime())
