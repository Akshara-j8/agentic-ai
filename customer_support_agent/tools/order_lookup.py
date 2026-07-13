import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from logs.audit import write_audit_event


ORDERS_PATH = Path(__file__).resolve().parents[1] / "data" / "orders.json"


class OrderLookupInput(BaseModel):
    order_id: str = Field(..., min_length=1)


class OrderLookupOutput(BaseModel):
    ok: bool
    order_id: str
    status: str | None = None
    carrier: str | None = None
    eta: str | None = None
    error: Literal["order_not_found"] | None = None


def _load_orders() -> dict:
    with ORDERS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _order_eta(order: dict) -> str | None:
    if order.get("status") == "cancelled":
        return None
    return order.get("actual_delivery_date") or order.get("promised_delivery_date")


def order_lookup(order_id: str) -> OrderLookupOutput:
    inputs = OrderLookupInput(order_id=order_id)
    order = _load_orders().get(inputs.order_id)
    if not order:
        output = OrderLookupOutput(ok=False, order_id=inputs.order_id, error="order_not_found")
    else:
        output = OrderLookupOutput(
            ok=True,
            order_id=inputs.order_id,
            status=order.get("status"),
            carrier=order.get("carrier"),
            eta=_order_eta(order),
        )

    write_audit_event(
        {
            "tool": "order_lookup",
            "inputs": inputs.model_dump(),
            "outputs": output.model_dump(),
        }
    )
    return output


def lookup_order(order_id: str) -> dict:
    return order_lookup(order_id).model_dump()

