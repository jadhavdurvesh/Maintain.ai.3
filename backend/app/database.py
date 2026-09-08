import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Defaults to a local SQLite file so the project runs with zero setup.
# Swap DATABASE_URL to a Postgres URL later without touching any model code.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./maintain_ai.db")

# Some hosts (Render, older Heroku) still hand out "postgres://", which
# SQLAlchemy 2.x's psycopg2 dialect rejects — needs "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
