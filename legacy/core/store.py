"""
The one place the app reads and writes its JSON collections.

Every manager used to do `json.load(open(FILE))` and `json.dump(..., open(FILE,'w'))`
directly. Both of those are now routed through here, which means:

  * with DATABASE_URL set, a collection lives in Postgres and survives a
    container restart, and a write is a single atomic UPSERT rather than a
    truncate-then-write that loses everything if the process dies mid-way;
  * with DATABASE_URL unset, it behaves exactly as before — same files, same
    contents — so nothing breaks before Postgres is provisioned.

Writes to disk are atomic even in file mode: write a temp file alongside, then
rename. A half-written users.json is how you lose every customer at once.
"""

import json
import os
import tempfile
import threading
from typing import Any, Optional

from core import db

_locks: dict = {}
_locks_guard = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _locks_guard:
        if name not in _locks:
            _locks[name] = threading.Lock()
        return _locks[name]


def collection_name(path: str) -> str:
    """data/users.json -> users. The document key, stable across environments."""
    return os.path.splitext(os.path.basename(path))[0]


def using_postgres() -> bool:
    # ensure_init() is lazy and idempotent, so the first read from any manager
    # brings Postgres up rather than silently falling through to the disk.
    return db.configured() and db.ensure_init()


def read(path: str, default: Any = None) -> Any:
    """Read a collection. Postgres first when it is live, else the file."""
    name = collection_name(path)
    if using_postgres():
        try:
            body = db.read_document(name)
            if body is not None:
                return body
            # First run against an empty database: fall through to the file so
            # an existing install keeps its data until the migration runs.
        except Exception as exc:
            print(f"[store] Postgres read failed for {name}, falling back to file: {exc}")

    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[store] could not read {path}: {exc}")
        return default


def write(path: str, body: Any) -> None:
    """Write a collection. Postgres when live; always keep the file in step."""
    name = collection_name(path)
    with _lock_for(name):
        if using_postgres():
            try:
                db.write_document(name, body)
            except Exception as exc:
                # Never lose the write. Fall through and put it on disk.
                print(f"[store] Postgres write failed for {name}, writing to file: {exc}")

        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        # Atomic: a crash mid-write leaves the previous file intact.
        fd, tmp = tempfile.mkstemp(dir=folder or ".", prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(body, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise


def exists(path: str) -> bool:
    if using_postgres():
        try:
            if db.read_document(collection_name(path)) is not None:
                return True
            # fall through, the file may still hold pre-migration data
        except Exception:
            pass
    return os.path.exists(path)
