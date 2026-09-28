from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.config import get_settings
from backend.database import get_engine
from backend.services.schema import extract_schema

router = APIRouter(tags=["Database"])


@router.get("/")
def root():
    return {"status": "ok", "service": "Vietnamese Text-to-SQL", "phase": 1}


@router.get("/health")
def health():
    database = get_settings().db_name
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={
            "status": "error", "backend": "ok", "database": database,
            "postgresql": "disconnected",
            "detail": "Không thể kết nối PostgreSQL. Kiểm tra dịch vụ và cấu hình .env.",
        })
    return {
        "status": "ok", "backend": "ok", "database": database,
        "postgresql": "connected",
    }


@router.get("/schema")
def schema():
    try:
        with get_engine().connect() as connection:
            tables = extract_schema(connection)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Không thể đọc schema PostgreSQL. Kiểm tra kết nối và quyền truy cập.",
        ) from None
    return {"database": get_settings().db_name, "schema": "public", "tables": tables}
