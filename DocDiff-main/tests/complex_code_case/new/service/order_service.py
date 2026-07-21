"""Order service v2 with discounts, tax, and lifecycle hooks"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional


TAX_RATE = Decimal("0.06")
VIP_DISCOUNT = Decimal("0.1")


@dataclass
class OrderSummary:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal


def _d(value) -> Decimal:
    return Decimal(str(value))


def calc_subtotal(items: List[Dict]) -> Decimal:
    subtotal = Decimal("0")
    for row in items:
        unit = _d(row.get("price", 0))
        qty = _d(row.get("qty", 1))
        subtotal += unit * qty
    return subtotal


def calc_discount(subtotal: Decimal, user_tier: str) -> Decimal:
    if user_tier == "vip":
        return (subtotal * VIP_DISCOUNT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0")


def calc_tax(base_amount: Decimal) -> Decimal:
    return (base_amount * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def summarize_order(items: List[Dict], user_tier: str = "normal") -> OrderSummary:
    subtotal = calc_subtotal(items)
    discount = calc_discount(subtotal, user_tier)
    taxable = subtotal - discount
    tax = calc_tax(taxable)
    total = (taxable + tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return OrderSummary(subtotal=subtotal, discount=discount, tax=tax, total=total)


def create_order(user_id: str, items: List[Dict], *, user_tier: str = "normal", note: Optional[str] = None) -> Dict:
    if not user_id:
        raise ValueError("user_id required")
    if not items:
        raise ValueError("items required")

    summary = summarize_order(items, user_tier=user_tier)
    order = {
        "id": "ORD-PLACEHOLDER",
        "user_id": user_id,
        "status": "CREATED",
        "items": items,
        "subtotal": str(summary.subtotal),
        "discount": str(summary.discount),
        "tax": str(summary.tax),
        "amount": str(summary.total),
        "note": note or "",
    }
    return order


def transition_order(order: Dict, to_status: str) -> Dict:
    allowed = {
        "CREATED": {"PAID", "CANCELLED"},
        "PAID": {"SHIPPED", "REFUNDED"},
        "SHIPPED": {"COMPLETED"},
    }
    current = order.get("status")
    if to_status not in allowed.get(current, set()):
        raise ValueError(f"invalid transition: {current} -> {to_status}")
    order["status"] = to_status
    return order


def pay_order(order: Dict, paid_amount) -> Dict:
    expected = _d(order["amount"])
    got = _d(paid_amount)
    if got < expected:
        raise ValueError("insufficient amount")
    return transition_order(order, "PAID")
