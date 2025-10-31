from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Reuse the project data directory used by the legacy JSON cache so SQLite
# databases live alongside the existing files.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

Base = declarative_base()


@dataclass(frozen=True)
class EngineInfo:
    """Represents the configured database engine and connection string."""

    engine: str
    url: str
    echo: bool


@lru_cache()
def get_engine_info() -> EngineInfo:
    engine_name = (os.getenv("DB_ENGINE") or "sqlite").strip().lower()

    if engine_name not in {"sqlite", "postgres"}:
        raise ValueError(f"Unsupported DB_ENGINE '{engine_name}'. Use 'sqlite' or 'postgres'.")

    echo = bool(int(os.getenv("DB_ECHO", "0")))

    if engine_name == "postgres":
        required_vars = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"DB_ENGINE=postgres requires environment variables: {joined}"
            )

        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        user = os.getenv("DB_USER", "")
        password = os.getenv("DB_PASSWORD", "")
        name = os.getenv("DB_NAME", "")
        url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
        return EngineInfo(engine="postgres", url=url, echo=echo)

    # SQLite default path can be overridden via DB_NAME; fallback keeps previous behaviour.
    db_name = os.getenv("DB_NAME")
    if db_name:
        sqlite_path = Path(db_name)
        if not sqlite_path.is_absolute():
            sqlite_path = DATA_DIR / sqlite_path
    else:
        sqlite_path = DATA_DIR / "mission_dashboard.sqlite"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{sqlite_path}"
    return EngineInfo(engine="sqlite", url=url, echo=echo)


def _create_engine() -> Engine:
    info = get_engine_info()
    connect_args = {}
    if info.engine == "sqlite":
        connect_args["check_same_thread"] = False

    return create_engine(
        info.url,
        echo=info.echo,
        future=True,
        connect_args=connect_args,
    )


engine: Engine = _create_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
    expire_on_commit=False,
)


@contextmanager
def get_db_session() -> Generator["SessionLocal", None, None]:
    """
    Provide a transactional scope around a series of operations.

    Yields a SQLAlchemy session that commits on success and rolls back on error.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
