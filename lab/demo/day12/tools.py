"""
tools.py — Day 12: TravelBot reasoning/eval tools
===================================================
Mock flight search, comparison, booking, and policy data for the five
scenario groups in the Day 12 demo (ReAct loop, reflection, loop
termination, LangSmith trace inspection, cost/latency routing).

No weather tool is defined on purpose — "what's the weather in Tokyo?"
must fall through as a genuine out-of-scope request (Scenario group 4).
"""

# ── Mock flight data ─────────────────────────────────────────────────────────
# Each route lists every fare class TravelBot knows about, direct and
# connecting, so the agent has to reason over the data rather than the
# tool doing the filtering for it.

_FLIGHTS: dict[tuple[str, str], list[dict]] = {
    ("london", "tokyo"): [
        {"flight_number": "TB-881", "direct": True, "stops": 0, "price_gbp": 1180,
         "duration_hours": 11.5, "cabin": "economy"},
        {"flight_number": "TB-882", "direct": True, "stops": 0, "price_gbp": 1340,
         "duration_hours": 11.5, "cabin": "economy"},
        {"flight_number": "TB-410+TB-512", "direct": False, "stops": 1, "price_gbp": 740,
         "duration_hours": 16.0, "cabin": "economy", "via": "Helsinki"},
        {"flight_number": "TB-220+TB-771", "direct": False, "stops": 1, "price_gbp": 860,
         "duration_hours": 15.0, "cabin": "economy", "via": "Dubai"},
    ],
    ("london", "paris"): [
        {"flight_number": "TB-210", "direct": True, "stops": 0, "price_gbp": 180,
         "duration_hours": 1.5, "cabin": "economy"},
        {"flight_number": "TB-212", "direct": True, "stops": 0, "price_gbp": 240,
         "duration_hours": 1.5, "cabin": "economy"},
        {"flight_number": "TB-214", "direct": True, "stops": 0, "price_gbp": 520,
         "duration_hours": 1.5, "cabin": "business"},
    ],
    ("dubai", "new york"): [
        {"flight_number": "TB-101", "direct": True, "stops": 0, "price_gbp": 4200,
         "duration_hours": 13.5, "cabin": "business",
         "comfort": {"seat": "lie-flat", "lounge_access": True, "legroom_in": 78}},
        {"flight_number": "TB-103", "direct": True, "stops": 0, "price_gbp": 3650,
         "duration_hours": 13.5, "cabin": "business",
         "comfort": {"seat": "angled lie-flat", "lounge_access": True, "legroom_in": 60}},
        {"flight_number": "TB-105+TB-220", "direct": False, "stops": 1, "price_gbp": 2950,
         "duration_hours": 18.0, "cabin": "business", "via": "London",
         "comfort": {"seat": "angled lie-flat", "lounge_access": True, "legroom_in": 55}},
    ],
}


def search_flights(
    origin: str,
    destination: str,
    max_budget_gbp: float | None = None,
    direct_only: bool = False,
) -> dict:
    """Search known flights between two cities.

    Args:
        origin: Departure city, e.g. "London".
        destination: Arrival city, e.g. "Tokyo".
        max_budget_gbp: Optional all-in budget ceiling in GBP. Results are
            NOT pre-filtered by this — it is returned alongside the full
            option list so the caller can reason about tradeoffs.
        direct_only: If True, only return non-stop flights.

    Returns:
        Dict with origin, destination, budget, and the matching flight list.
        Each flight includes price_gbp, direct, stops, and duration_hours.
    """
    key = (origin.strip().lower(), destination.strip().lower())
    flights = _FLIGHTS.get(key, [])
    if direct_only:
        flights = [f for f in flights if f["direct"]]

    return {
        "origin": origin,
        "destination": destination,
        "max_budget_gbp": max_budget_gbp,
        "direct_only": direct_only,
        "flights": flights,
        "found": len(flights) > 0,
    }


# ── Mock "anywhere in a region" data — bounded set, used for the loop ────────
# termination scenario. The dataset is intentionally small and finite: once
# the agent has seen every candidate, it has no more ground to cover and
# should stop searching rather than re-querying for a "better" answer.

_REGION_FLIGHTS: dict[str, list[dict]] = {
    "asia": [
        {"destination": "Istanbul", "price_gbp": 410, "direct": True, "days_out": 12},
        {"destination": "Bangkok", "price_gbp": 395, "direct": False, "days_out": 28},
        {"destination": "Hanoi", "price_gbp": 360, "direct": False, "days_out": 35},
        {"destination": "Dubai", "price_gbp": 340, "direct": True, "days_out": 9},
        {"destination": "Mumbai", "price_gbp": 385, "direct": True, "days_out": 21},
        {"destination": "Jakarta", "price_gbp": 470, "direct": False, "days_out": 40},
    ],
}


def search_cheapest_in_region(
    region: str,
    max_budget_gbp: float | None = None,
    max_days_out: int | None = None,
) -> dict:
    """Search the cheapest known fares to any destination in a region.

    This returns TravelBot's complete, finite knowledge of fares for the
    region in one call — there is nothing further to fetch after this.

    Args:
        region: Region name, e.g. "Asia".
        max_budget_gbp: Optional all-in budget ceiling in GBP.
        max_days_out: Optional latest departure, in days from today.

    Returns:
        Dict with the region, filters applied, matching candidates sorted
        by price, and `exhausted: True` — there are no more candidates to
        search for this region.
    """
    candidates = _REGION_FLIGHTS.get(region.strip().lower(), [])

    if max_budget_gbp is not None:
        candidates = [c for c in candidates if c["price_gbp"] <= max_budget_gbp]
    if max_days_out is not None:
        candidates = [c for c in candidates if c["days_out"] <= max_days_out]

    candidates = sorted(candidates, key=lambda c: c["price_gbp"])

    return {
        "region": region,
        "max_budget_gbp": max_budget_gbp,
        "max_days_out": max_days_out,
        "candidates": candidates,
        "candidates_considered": len(_REGION_FLIGHTS.get(region.strip().lower(), [])),
        "exhausted": True,
    }


def compare_business_class(origin: str, destination: str) -> dict:
    """Compare business-class options between two cities on comfort and value.

    Args:
        origin: Departure city, e.g. "Dubai".
        destination: Arrival city, e.g. "New York".

    Returns:
        Dict with the route and business-class options, each annotated with
        comfort details (seat type, lounge access, legroom) alongside price.
    """
    key = (origin.strip().lower(), destination.strip().lower())
    flights = [f for f in _FLIGHTS.get(key, []) if f.get("cabin") == "business"]
    return {
        "origin": origin,
        "destination": destination,
        "options": flights,
        "found": len(flights) > 0,
    }


# ── Cancellation policy — cheap, single-lookup, no reasoning loop needed ─────

_CANCELLATION_POLICY = {
    "flight": (
        "Flights are refundable up to 24 hours before departure for a 10% "
        "service fee. Within 24 hours, fares are non-refundable but can be "
        "changed to a different date for a $75 change fee plus any fare "
        "difference."
    ),
    "hotel": (
        "Hotel bookings can be cancelled free of charge up to 48 hours before "
        "check-in. Cancelling within 48 hours forfeits the first night's rate."
    ),
}


def get_cancellation_policy(booking_type: str = "flight") -> dict:
    """Look up TravelBot's cancellation policy.

    Args:
        booking_type: "flight" or "hotel". Defaults to "flight".

    Returns:
        Dict with the booking type and the applicable policy text.
    """
    key = booking_type.strip().lower()
    policy = _CANCELLATION_POLICY.get(key, _CANCELLATION_POLICY["flight"])
    return {"booking_type": key, "policy": policy}


# ── Booking status lookup — reused pattern from earlier days ────────────────

_BOOKINGS: list[dict] = [
    {
        "booking_id": "LON-TOK-901",
        "origin": "London",
        "destination": "Tokyo",
        "status": "Confirmed",
        "departure": "Next month, 09:40",
    },
    {
        "booking_id": "DXB-NYC-204",
        "origin": "Dubai",
        "destination": "New York",
        "status": "Confirmed",
        "departure": "Next Friday, 02:15",
        "cabin": "business",
    },
]


def get_booking_status(booking_id: str | None = None) -> dict:
    """Look up a booking by its reference.

    Args:
        booking_id: Booking reference, e.g. "LON-TOK-901". Optional — if
            omitted, the caller should ask the traveller for it.

    Returns:
        The matching booking record, or {"found": False, ...} if no
        reference was given or nothing matched.
    """
    if not booking_id:
        return {
            "found": False,
            "message": "I need a booking reference to look that up — what is it?",
        }

    for booking in _BOOKINGS:
        if booking["booking_id"].upper() == booking_id.strip().upper():
            return {"found": True, **booking}

    return {
        "found": False,
        "booking_id": booking_id,
        "message": "No booking found matching that reference. Double-check the format (e.g. LON-TOK-901).",
    }
