import json
from datetime import datetime, timezone
from pathlib import Path


AUDIT_PATH = Path(__file__).resolve().parent / "audit.jsonl"


def write_audit_event(event: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with AUDIT_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
