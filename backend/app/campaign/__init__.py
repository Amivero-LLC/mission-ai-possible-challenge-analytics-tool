from __future__ import annotations

from typing import Any

__all__ = ["campaign_router"]


def __getattr__(name: str) -> Any:
    if name == "campaign_router":
        from .router import campaign_router as _campaign_router

        return _campaign_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
