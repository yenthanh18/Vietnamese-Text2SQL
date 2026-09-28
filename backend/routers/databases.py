from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.config import get_settings
from backend.services.spider_database import SpiderDatabaseError, get_spider_database_service

router = APIRouter(prefix="/api/databases", tags=["Spider databases"])


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sql: str = Field(min_length=1, max_length=20000)


def call_service(method: str, *args):
    try:
        return getattr(get_spider_database_service(), method)(*args)
    except SpiderDatabaseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("")
def databases():
    return call_service("list_databases")


@router.get("/{db_id}/schema")
def database_schema(db_id: str):
    return call_service("get_schema", db_id)


@router.post("/{db_id}/execute", summary="Development only: bounded read-only SELECT")
def execute(db_id: str, request: ExecuteRequest):
    if not get_settings().spider_execute_enabled:
        raise HTTPException(status_code=403, detail="Spider execution đã bị tắt trong cấu hình.")
    return call_service("execute", db_id, request.sql)
