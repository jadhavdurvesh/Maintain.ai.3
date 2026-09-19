import os
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite keeps local development zero-config. Set DATABASE_URL to a PostgreSQL
# connection string for the hosted backend; model code does not change.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./maintain_ai.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")
is_serverless = os.getenv("VERCEL", "").lower() == "1" or bool(os.getenv("VERCEL"))

connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_kwargs = {"connect_args": connect_args}

if is_serverless and not is_sqlite:
    # Vercel functions are short-lived and may be frozen between invocations.
    # Reusing a process-local SQLAlchemy pool can leave stale Postgres
    # connections after a freeze. Open/close a connection per request instead.
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
