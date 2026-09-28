from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.services.model_runtime import ModelNotLoadedError, get_model_runtime
from backend.services.schema_mapper import SchemaMapper, SchemaMappingError
from backend.services.spider_database import SpiderDatabaseError, get_spider_database_service
from backend.services.text2sql import get_text2sql_service

router = APIRouter(prefix="/api", tags=["Query"])


class QueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    db_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_]+$")


class QueryResponse(BaseModel):
    question: str
    db_id: str
    tagged_question: str
    e2_sql: str
    e3_triggered: bool
    schema_violations: int
    generated_sql: str
    execution_sql: str
    columns: list[str] = Field(default_factory=list)
    rows: list[list[object]] = Field(default_factory=list)
    row_count: int
    truncated: bool = False


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    try:
        databases = get_spider_database_service()
        databases.get_schema(request.db_id)  # Validate before checking model state.
        get_model_runtime().require_loaded()  # Never load or download implicitly.
        databases.resolve_path(request.db_id)
        metadata = get_text2sql_service().generate(request.question, request.db_id)
        execution_sql = SchemaMapper(databases).map_sql(request.db_id, metadata["final_sql"])
        result = databases.execute(request.db_id, execution_sql)
        return QueryResponse(
            question=request.question, db_id=request.db_id,
            tagged_question=metadata["tagged_question"], e2_sql=metadata["e2_sql"],
            e3_triggered=metadata["e3_triggered"], schema_violations=metadata["schema_violations"],
            generated_sql=metadata["final_sql"], execution_sql=execution_sql, **result,
        )
    except ModelNotLoadedError:
        raise HTTPException(status_code=503, detail="Model chưa tải. NLP inference hiện không khả dụng.") from None
    except SchemaMappingError as exc:
        raise HTTPException(status_code=422, detail=f"Lỗi ánh xạ schema: {exc}") from None
    except SpiderDatabaseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except Exception:
        # No model/provider tracebacks or generated data in public error responses.
        raise HTTPException(status_code=500, detail="Không thể hoàn tất truy vấn Text-to-SQL.") from None
