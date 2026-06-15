"""
tools.py — Function tools for the Trips and Support specialist agents
=========================================================================
Plain in-process Python function tools (no MCP here — Day 08 already
covers MCP tool servers; Day 09's focus is orchestration between agents).

  get_booking_status(...)            -> Support specialist
  get_booking_status_unavailable(...) -> Support specialist (Scenario 5A:
                                          simulates a backend outage, used
                                          only by the error-demo agent)
  get_attractions(...)               -> Trips specialist
"""

# ── Mock booking data ───────────────────────────────────────────────────────
_BOOKINGS: list[dict] = [
    {
        "booking_id": "BLR-DEL-123",
        "origin": "Bengaluru (BLR)",
        "destination": "Delhi (DEL)",
        "departure": "Tomorrow, 06:45",
        "flight_number": "TB-410",
        "status": "Confirmed",
    },
    {
        "booking_id": "CHN-PAR-789",
        "origin": "Chennai (MAA)",
        "destination": "Paris (CDG)",
        "departure": "Next week, Tue 23:55",
        "flight_number": "TB-772",
        "status": "Confirmed",
    },
    {
        "booking_id": "BOM-DXB-552",
        "origin": "Mumbai (BOM)",
        "destination": "Dubai (DXB)",
        "departure": "Monday, 21:10",
        "flight_number": "TB-512",
        "status": "Delayed",
        "delay_minutes": 150,
        "new_arrival_time": "Tuesday, 02:10 local time (was Monday, 23:40)",
    },
    {
        "booking_id": "BLR-LHR-456",
        "origin": "Bengaluru (BLR)",
        "destination": "London Heathrow (LHR)",
        "departure": "Next Friday, 02:20",
        "flight_number": "TB-940",
        "status": "Confirmed",
    },
]


def get_booking_status(
    booking_id: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
) -> dict:
    """Look up the status of a flight booking.

    Look up by booking_id if the user gave one. Otherwise, if the user
    described their route instead (e.g. "Mumbai to Dubai"), pass origin
    and/or destination to search by route.

    Args:
        booking_id: Booking reference, e.g. "BLR-DEL-123". Optional.
        origin: Departure city or airport, e.g. "Mumbai". Optional.
        destination: Arrival city or airport, e.g. "Dubai". Optional.

    Returns:
        The matching booking record (route, departure, status, and - for
        delayed flights - delay_minutes / new_arrival_time) if found, or
        {"found": False, ...} with a guidance message if not. If none of
        booking_id, origin or destination are given, returns a message
        asking the user for one of them.
    """
    if not booking_id and not origin and not destination:
        return {
            "found": False,
            "message": (
                "I need a booking reference, or at least the origin and/or "
                "destination of the flight, to look this up."
            ),
        }

    for booking in _BOOKINGS:
        if booking_id and booking["booking_id"].upper() == booking_id.strip().upper():
            return {"found": True, **booking}

    if origin or destination:
        for booking in _BOOKINGS:
            origin_match = origin is None or origin.strip().lower() in booking["origin"].lower()
            dest_match = destination is None or destination.strip().lower() in booking["destination"].lower()
            if origin_match and dest_match:
                return {"found": True, **booking}

    return {
        "found": False,
        "booking_id": booking_id,
        "message": (
            "No booking found matching that reference or route. Double-check "
            "the reference (it looks like XXX-XXX-NNN) or the cities involved."
        ),
    }


def get_booking_status_unavailable(
    booking_id: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
) -> dict:
    """Look up the status of a flight booking.

    Same signature as get_booking_status, but the booking backend is
    simulating an outage: every call returns an error instead of a result.
    Used by the error-recovery demo (Scenario 5A) - do not retry, report
    the issue and suggest trying again later.

    Args:
        booking_id: Booking reference, e.g. "BLR-LHR-456". Optional.
        origin: Departure city or airport. Optional.
        destination: Arrival city or airport. Optional.

    Returns:
        {"error": "..."} describing a temporary backend outage.
    """
    return {
        "error": (
            "Booking lookup service timed out after 10s. The booking "
            "backend is temporarily unavailable."
        ),
    }


# ── Mock itinerary data, grouped by city ────────────────────────────────────
_ATTRACTIONS: dict[str, list[dict]] = {
    "singapore": [
        {"name": "Sentosa Island", "category": "Theme park / beach", "tags": ["kid-friendly", "family", "outdoor"]},
        {"name": "Gardens by the Bay", "category": "Gardens", "tags": ["kid-friendly", "family", "outdoor", "iconic"]},
        {"name": "Singapore Zoo", "category": "Zoo", "tags": ["kid-friendly", "family", "outdoor"]},
        {"name": "Science Centre Singapore", "category": "Museum", "tags": ["kid-friendly", "family", "indoor", "museum"]},
        {"name": "Universal Studios Singapore", "category": "Theme park", "tags": ["kid-friendly", "family", "indoor"]},
    ],
    "dubai": [
        {"name": "Burj Khalifa observation deck", "category": "Landmark", "tags": ["iconic", "family"]},
        {"name": "Dubai Mall & Aquarium", "category": "Shopping / aquarium", "tags": ["family", "indoor"]},
        {"name": "Desert safari", "category": "Tour", "tags": ["outdoor", "family"]},
        {"name": "Dubai Museum (Al Fahidi Fort)", "category": "Museum", "tags": ["museum", "indoor"]},
        {"name": "Jumeirah Beach", "category": "Beach", "tags": ["outdoor", "family"]},
    ],
    "paris": [
        {"name": "Louvre Museum", "category": "Museum", "tags": ["museum", "iconic", "indoor"]},
        {"name": "Musée d'Orsay", "category": "Museum", "tags": ["museum", "indoor"]},
        {"name": "Musée de l'Orangerie", "category": "Museum", "tags": ["museum", "indoor"]},
        {"name": "Eiffel Tower", "category": "Landmark", "tags": ["iconic", "outdoor"]},
        {"name": "Seine river cruise", "category": "Tour", "tags": ["outdoor", "family"]},
    ],
}


def get_attractions(city: str, days: int | None = None, interests: str | None = None) -> dict:
    """List attractions and activities for a city, optionally filtered by interest.

    Args:
        city: City name, e.g. "Singapore" or "Paris".
        days: Optional number of days the itinerary should cover. Returned
            as-is in the response so the caller can plan a day-by-day split.
        interests: Optional interest or tag to prefer, e.g. "museums" or
            "kid-friendly". Matched against each attraction's tags; ignored
            if nothing matches.

    Returns:
        A dict with the city, the filters applied, and a list of matching
        attractions (name, category, tags). The list is empty if no data is
        available for the city.
    """
    attractions = _ATTRACTIONS.get(city.strip().lower())
    if attractions is None:
        return {
            "city": city,
            "filters": {"days": days, "interests": interests},
            "attractions": [],
            "message": f"No itinerary data available for '{city}' yet.",
        }

    results = attractions
    if interests:
        interest_lower = interests.strip().lower()
        matches = [a for a in results if any(interest_lower in tag for tag in a["tags"])]
        if matches:
            results = matches

    return {
        "city": city,
        "filters": {"days": days, "interests": interests},
        "attractions": results,
    }
