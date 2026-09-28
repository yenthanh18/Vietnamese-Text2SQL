from fastapi import APIRouter, HTTPException

from backend.services.text2sql import get_text2sql_service

router = APIRouter(prefix="/nlp", tags=["NLP"])


@router.get("/status")
def nlp_status():
    try:
        return get_text2sql_service().get_status()
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=503,
            detail="Không thể đọc NLP artifacts. Kiểm tra tables.json và dew_dictionary.json.",
        ) from None
