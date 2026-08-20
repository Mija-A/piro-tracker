"""Turn raw PIRO orders + the journal into site/data.json for the front-end."""
import datetime
import re


def is_sub(code):
    return bool(re.match(r"^JO-\d+-\d+", code or ""))


def _iso_date(v):
    return str(v or "")[:10]


def _order_row(o, journey):
    items = o.get("items") or []
    sku = ", ".join(sorted({it.get("itemSKU") or "" for it in items if it.get("itemSKU")}))
    skutype = ", ".join(sorted({it.get("itemTypeSKU") or "" for it in items if it.get("itemTypeSKU")}))
    return {
        "code": o.get("code") or "",
        "cust": o.get("customerName") or "",
        "stage": o.get("currentService") or "",
        "days": o.get("daysInCurrentService"),
        "due": _iso_date(o.get("dueDate")),
        "metal": o.get("metals") or "",
        "assigned": o.get("serviceAssignedUser") or "",
        "img": o.get("imageURL") or "",
        "status": o.get("status") or "",
        "sku": sku,
        "skutype": skutype,
        "price": o.get("totalPrice") or "",
        "orderDate": _iso_date(o.get("orderDate")),
        "address": o.get("customerMainAddress") or "",
        "journey": journey,
    }


def build(orders, hist, generated_at=None):
    """Parents-only payload the page renders from. All grouping, department
    mapping, and formatting is client-side (driven by site/config.json)."""
    generated_at = generated_at or datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tracked = hist.get("orders", {})
    rows = []
    for o in orders:
        code = o.get("code") or ""
        if not code or is_sub(code):
            continue
        journey = tracked.get(code, {}).get("journey", [])
        rows.append(_order_row(o, journey))
    rows.sort(key=lambda r: r["code"])
    return {"generated_at": generated_at, "orders": rows}
