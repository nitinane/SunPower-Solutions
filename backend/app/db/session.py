from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import cache_invalidation as _cache_invalidation  # noqa: F401
from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
