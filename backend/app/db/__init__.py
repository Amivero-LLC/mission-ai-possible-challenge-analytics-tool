"""
Database initialization package for Mission:AI Possible backend.

This module exposes the SQLAlchemy base metadata and session helpers so the
rest of the application can interact with the configured database without
knowing which engine is active (SQLite by default, PostgreSQL when env vars
are provided).
"""

from .session import Base, SessionLocal, engine, get_db_session, get_engine_info

__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_db_session",
    "get_engine_info",
]
