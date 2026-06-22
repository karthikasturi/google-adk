"""
tools.py — Day 13: mock tools for the guardrail scenarios
============================================================
Adjacent-domain tools (travel / banking / food delivery / retail) kept
deliberately small. The point of Day 13 is the guardrail *pattern* around
the tools, not the tools themselves.

Note: get_support_notes returns notes that DELIBERATELY contain PII (email,
phone, account id) so the OUTPUT guardrail has something real to redact.
cancel_order validates its own argument too (defense in depth) — but the
TOOL-INPUT guardrail is what stops an unsafe call before it ever runs.
"""

import re

# ── Travel: flight change ───────────────────────────────────────────────────

_FLIGHTS = {
    ("mumbai", "singapore"): [
        {"flight": "TB-303", "depart": "Tue 08:15", "fare_diff_usd": 0},
        {"flight": "TB-411", "depart": "Wed 21:40", "fare_diff_usd": 45},
    ],
}


def change_flight(origin: str, destination: str) -> dict:
    """Look up rebooking options for a flight change.

    Args:
        origin: Current departure city, e.g. "Mumbai".
        destination: Destination city, e.g. "Singapore".

    Returns:
        Dict with available rebooking options for the route.
    """
    options = _FLIGHTS.get((origin.strip().lower(), destination.strip().lower()), [])
    return {"origin": origin, "destination": destination, "options": options,
            "found": bool(options)}


# ── Banking: support notes (contain PII on purpose) ─────────────────────────

_SUPPORT_NOTES = {
    "C-7782": (
        "Customer called about a declined transaction. Verified identity. "
        "Contact email jane.doe@example.com, phone +1 415 555 0137. "
        "Account ID ACC-558213. Issued a provisional credit; case to be "
        "reviewed by the fraud team within 48 hours."
    ),
}


def get_support_notes(customer_id: str = "C-7782") -> dict:
    """Fetch the latest support conversation notes for a customer.

    Args:
        customer_id: Internal customer reference. Defaults to the demo customer.

    Returns:
        Dict with the raw notes (which may contain personal data).
    """
    notes = _SUPPORT_NOTES.get(customer_id.strip().upper() if customer_id else "C-7782")
    if not notes:
        return {"found": False, "customer_id": customer_id}
    return {"found": True, "customer_id": customer_id, "notes": notes}


# ── Food delivery: cancel order ─────────────────────────────────────────────

_ORDERS = {"48291": "active", "48015": "delivered"}
_VALID_ORDER_ID = re.compile(r"^#?\d{4,6}$")


def cancel_order(order_id: str, confirmed: bool = False) -> dict:
    """Cancel a single food-delivery order. Destructive — confirm first.

    Args:
        order_id: A single numeric order id, e.g. "48291" or "#48291".
            Wildcards or bulk values are not accepted.
        confirmed: Must be True to actually cancel. If False, returns a
            confirmation request instead of cancelling.

    Returns:
        Dict describing the result or a confirmation request.
    """
    if not _VALID_ORDER_ID.match(order_id.strip()):
        return {"status": "rejected",
                "reason": f"'{order_id}' is not a valid single order id."}

    oid = order_id.strip().lstrip("#")
    if oid not in _ORDERS:
        return {"status": "not_found", "order_id": oid}
    if _ORDERS[oid] != "active":
        return {"status": "not_cancellable", "order_id": oid, "state": _ORDERS[oid]}
    if not confirmed:
        return {"status": "confirmation_required", "order_id": oid,
                "message": f"Cancel order {oid}? This cannot be undone."}
    return {"status": "cancelled", "order_id": oid}


# ── Retail: laptop search ───────────────────────────────────────────────────

_LAPTOPS = [
    {"name": "ProBook Studio 16", "cpu": "8-core", "gpu": "discrete", "ram_gb": 32,
     "price_usd": 1899, "good_for": "video editing"},
    {"name": "CreatorEdge 15", "cpu": "10-core", "gpu": "discrete", "ram_gb": 32,
     "price_usd": 2099, "good_for": "video editing"},
    {"name": "UltraSlim 14", "cpu": "6-core", "gpu": "integrated", "ram_gb": 16,
     "price_usd": 1199, "good_for": "everyday use"},
]


def search_laptops(use_case: str = "video editing") -> dict:
    """Search the product catalog for laptops matching a use case.

    Args:
        use_case: What the laptop is for, e.g. "video editing".

    Returns:
        Dict with matching laptops from the catalog.
    """
    kw = use_case.strip().lower()
    matches = [l for l in _LAPTOPS if kw in l["good_for"]] or _LAPTOPS
    return {"use_case": use_case, "laptops": matches}
