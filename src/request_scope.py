"""Request-local data paths, propagated to worker threads by asyncio.to_thread."""
import os
from contextvars import ContextVar
from pathlib import Path
ROOT = Path("/tmp/research-assistant") if os.getenv("VERCEL") else Path(__file__).resolve().parents[1]
guest_user = ContextVar("guest_user", default=0)
scope = ContextVar("research_scope", default=(0, 0))
def data_dir():
    user, workspace = scope.get()
    if (user, workspace) == (0, 0):
        return ROOT / "data"
    return ROOT / "data" / "workspaces" / str(user) / str(workspace)
def documents_dir():
    return data_dir() / "documents"
