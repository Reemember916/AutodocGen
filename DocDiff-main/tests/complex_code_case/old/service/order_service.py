"""Order service v1"""

from typing import Dict, List


def calc_total(items: List[Dict]) -> float:
    total = 0.0
    for i in items:
        price = float(i.get("price", 0))
        qty = int(i.get("qty", 1))
        total += price * qty
    return round(total, 2)


def create_order(user_id: str, items: List[Dict]) -> Dict:
    if not user_id:
        raise ValueError("user_id required")
    if not items:
        raise ValueError("items required")

    amount = calc_total(items)
    order = {
        "id": "ORD-PLACEHOLDER",
        "user_id": user_id,
        "status": "CREATED",
        "items": items,
        "amount": amount,
    }
    return order


def pay_order(order: Dict, paid_amount: float) -> Dict:
    if order["status"] != "CREATED":
        raise ValueError("invalid status")
    if paid_amount < order["amount"]:
        raise ValueError("insufficient amount")
    order["status"] = "PAID"
    return order
