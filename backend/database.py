from functools import lru_cache

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine

from backend.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = URL.create(
        "postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 5,
            "options": "-c default_transaction_read_only=on -c statement_timeout=5000",
        },
    )
