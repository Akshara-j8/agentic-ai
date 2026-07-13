from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from logs.audit import write_audit_event


GOODWILL_CREDIT_CAP = 10.0


class ApplyCreditInput(BaseModel):
    order_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1)


class ApplyCreditOutput(BaseModel):
    ok: bool
    order_id: str
    amount: float
    reason: str
    status: Literal["applied", "requires_human_approval"]
    credit_id: str | None = None
    error: Literal["requires_human_approval"] | None = None
    created_at: str


def apply_credit(order_id: str, amount: float, reason: str) -> ApplyCreditOutput:
    inputs = ApplyCreditInput(order_id=order_id, amount=amount, reason=reason)
    now = datetime.now(timezone.utc)
    created_at = now.isoformat()

    if inputs.amount > GOODWILL_CREDIT_CAP:
        output = ApplyCreditOutput(
            ok=False,
            order_id=inputs.order_id,
            amount=inputs.amount,
            reason=inputs.reason,
            status="requires_human_approval",
            error="requires_human_approval",
            created_at=created_at,
        )
    else:
        output = ApplyCreditOutput(
            ok=True,
            order_id=inputs.order_id,
            amount=inputs.amount,
            reason=inputs.reason,
            status="applied",
            credit_id=f"CR-{inputs.order_id}-{int(now.timestamp())}",
            created_at=created_at,
        )

    write_audit_event(
        {
            "tool": "apply_credit",
            "inputs": inputs.model_dump(),
            "outputs": output.model_dump(),
        }
    )
    return output
