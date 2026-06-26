"""Small local fallback store used when Supabase is temporarily unavailable."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from typing import Any

STORE_PATH = Path(tempfile.gettempdir()) / "pondysevai_fallback_volunteers.json"
_lock = threading.Lock()


def _read() -> dict[str, dict[str, Any]]:
    if not STORE_PATH.exists():
        return {}
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: dict[str, dict[str, Any]]) -> None:
    STORE_PATH.write_text(json.dumps(data), encoding="utf-8")


def add_volunteer(record: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        data = _read()
        data[record["id"]] = record
        _write(data)
    return record


def get_by_id(volunteer_id: str) -> dict[str, Any] | None:
    return _read().get(volunteer_id)


def get_by_phone(phone: str) -> dict[str, Any] | None:
    for volunteer in _read().values():
        if volunteer.get("phone") == phone:
            return volunteer
    return None


def list_volunteers(status: str | None = None, commune: str | None = None) -> list[dict[str, Any]]:
    volunteers = list(_read().values())
    if status:
        volunteers = [
            volunteer for volunteer in volunteers
            if volunteer.get("status") == status
            or (status == "pending_review" and volunteer.get("status") == "registered")
        ]
    if commune:
        volunteers = [volunteer for volunteer in volunteers if volunteer.get("commune") == commune]
    return volunteers


def update_volunteer(volunteer_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        data = _read()
        volunteer = data.get(volunteer_id)
        if not volunteer:
            return None
        volunteer.update(updates)
        data[volunteer_id] = volunteer
        _write(data)
    return volunteer
