"""Small local fallback store used when Supabase is temporarily unavailable."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from typing import Any

STORE_PATH = Path(tempfile.gettempdir()) / "pondysevai_fallback_store.json"
_lock = threading.Lock()


def _read_store() -> dict[str, dict[str, dict[str, Any]]]:
    if not STORE_PATH.exists():
        return {"volunteers": {}, "deployments": {}}
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"volunteers": {}, "deployments": {}}
        if "volunteers" not in data:
            return {"volunteers": data, "deployments": {}}
        data.setdefault("volunteers", {})
        data.setdefault("deployments", {})
        return data
    except Exception:
        return {"volunteers": {}, "deployments": {}}


def _write_store(data: dict[str, dict[str, dict[str, Any]]]) -> None:
    STORE_PATH.write_text(json.dumps(data), encoding="utf-8")


def add_volunteer(record: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        data = _read_store()
        data["volunteers"][record["id"]] = record
        _write_store(data)
    return record


def get_by_id(volunteer_id: str) -> dict[str, Any] | None:
    return _read_store()["volunteers"].get(volunteer_id)


def get_by_phone(phone: str) -> dict[str, Any] | None:
    for volunteer in _read_store()["volunteers"].values():
        if volunteer.get("phone") == phone:
            return volunteer
    return None


def list_volunteers(status: str | None = None, commune: str | None = None) -> list[dict[str, Any]]:
    volunteers = list(_read_store()["volunteers"].values())
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
        data = _read_store()
        volunteer = data["volunteers"].get(volunteer_id)
        if not volunteer:
            return None
        volunteer.update(updates)
        data["volunteers"][volunteer_id] = volunteer
        _write_store(data)
    return volunteer


def add_deployment(record: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        data = _read_store()
        data["deployments"][record["id"]] = record
        _write_store(data)
    return record


def list_deployments(volunteer_id: str) -> list[dict[str, Any]]:
    deployments = [
        deployment for deployment in _read_store()["deployments"].values()
        if deployment.get("volunteer_id") == volunteer_id
    ]
    return sorted(deployments, key=lambda item: item.get("scheduled_date") or "", reverse=True)
