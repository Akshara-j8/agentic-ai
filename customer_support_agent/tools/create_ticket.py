import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from logs.audit import write_audit_event


TICKETS_PATH = Path(__file__).resolve().parents[1] / "data" / "tickets.json"
TicketCategory = Literal["billing", "delivery", "returns", "security", "general", "escalation"]
TicketPriority = Literal["low", "normal", "high", "urgent"]


class CreateTicketInput(BaseModel):
    summary: str = Field(..., min_length=1)
    category: TicketCategory
    priority: TicketPriority


class CreateTicketOutput(BaseModel):
    ok: bool
    ticket_id: str
    summary: str
    category: TicketCategory
    priority: TicketPriority
    status: Literal["queued"]
    created_at: str


def _load_ticket_queue() -> list[dict]:
    if not TICKETS_PATH.exists():
        return []
    with TICKETS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_ticket_queue(tickets: list[dict]) -> None:
    TICKETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TICKETS_PATH.open("w", encoding="utf-8") as file:
        json.dump(tickets, file, indent=2)
        file.write("\n")


def create_ticket(summary: str, category: TicketCategory, priority: TicketPriority) -> CreateTicketOutput:
    inputs = CreateTicketInput(summary=summary, category=category, priority=priority)
    output = CreateTicketOutput(
        ok=True,
        ticket_id=f"TCK-{uuid4().hex[:8].upper()}",
        summary=inputs.summary,
        category=inputs.category,
        priority=inputs.priority,
        status="queued",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    tickets = _load_ticket_queue()
    tickets.append(output.model_dump())
    _save_ticket_queue(tickets)

    write_audit_event(
        {
            "tool": "create_ticket",
            "inputs": inputs.model_dump(),
            "outputs": output.model_dump(),
        }
    )
    return output

