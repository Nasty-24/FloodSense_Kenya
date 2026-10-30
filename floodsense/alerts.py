"""Alert drafts, the number check, and the approval queue.

Every alert starts as "pending". Only an officer pressing Approve makes it "approved".
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

QUEUE = Path(__file__).resolve().parent.parent / "alerts.json"
SMS_LIMIT = 160
HELPLINE = "1199"  # Kenya Red Cross toll-free line, allowed in every alert

# A number not glued to a letter, so the "2" in "km2" doesn't count
NUMBER = re.compile(r"(?<![A-Za-z0-9.,])\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    return [float(n.rstrip(".,").replace(",", "")) for n in NUMBER.findall(text)]


def check_alert(text: str, ward: dict) -> list[str]:
    """Return the problems with an alert; an empty list means it may go to the officer."""
    problems = []
    if len(text) > SMS_LIMIT:
        problems.append(f"Too long for one SMS: {len(text)} characters (limit {SMS_LIMIT}).")
    allowed = {float(HELPLINE)}
    for value in ward.values():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            allowed |= {float(value), float(round(value)), round(float(value), 1)}
    for n in numbers_in(text):
        if n not in allowed:
            problems.append(f"The number {n:g} is not in the ward data.")
    return problems


def _load() -> list[dict]:
    return json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []


def _save(alerts: list[dict]) -> None:
    QUEUE.write_text(json.dumps(alerts, indent=2, ensure_ascii=False), encoding="utf-8")


def add_draft(ward: str, language: str, text: str) -> dict:
    alert = {"id": uuid.uuid4().hex[:8], "ward": ward, "language": language, "text": text,
             "status": "pending", "created": datetime.now().strftime("%H:%M")}
    _save(_load() + [alert])
    return alert


def list_alerts(status: str) -> list[dict]:
    return [a for a in _load() if a["status"] == status]


def set_status(alert_id: str, status: str, text: str | None = None) -> None:
    alerts = _load()
    for a in alerts:
        if a["id"] == alert_id:
            a["status"] = status
            a["decided"] = datetime.now().strftime("%H:%M")
            if text is not None:
                a["text"] = text
    _save(alerts)
