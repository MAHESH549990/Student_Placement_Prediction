"""Small atomic JSON store used only when MongoDB is not configured."""
import json
import os
import threading
from pathlib import Path

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _lock_for(path: Path):
    key = str(path.resolve())
    with _locks_guard:
        return _locks.setdefault(key, threading.RLock())


def read_list(path: Path):
    lock = _lock_for(path)
    with lock:
        if not path.exists():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Local data file is unreadable: {path.name}") from exc
        if not isinstance(value, list):
            raise RuntimeError(f"Local data file has invalid structure: {path.name}")
        return value


def write_list(path: Path, rows):
    lock = _lock_for(path)
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
