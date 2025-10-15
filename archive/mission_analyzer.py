"""Compatibility shim for mission analyzer utilities.

The core implementation now lives in `backend.app.services.mission_analyzer`.
This file re-exports the public API so existing imports continue to work.
"""

from backend.app.services.mission_analyzer import (  # noqa: F401
    DATA_DIR,
    MissionAnalyzer,
    find_latest_export,
)

__all__ = ["MissionAnalyzer", "DATA_DIR", "find_latest_export"]


if __name__ == "__main__":
    import runpy

    runpy.run_module("backend.app.services.mission_analyzer", run_name="__main__")
