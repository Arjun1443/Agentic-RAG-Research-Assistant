"""Request-local data paths, propagated to worker threads by asyncio.to_thread."""
from contextvars import ContextVar
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
scope = ContextVar("research_scope", default=(0, 0))
def data_dir():
    user, workspace = scope.get()
    if (user, workspace) == (0, 0):
        return ROOT / "data"
    return ROOT / "data" / "workspaces" / str(user) / str(workspace)
def documents_dir():
    return data_dir() / "documents"
