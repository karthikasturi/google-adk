"""
shared/tools.py — TravelBot tools (v1 through v3+)
---------------------------------------------------
Source of truth for all tool functions used by TravelBot across versions.

v2 tools (static mock data):
  get_flight_status, search_hotels, save_traveler_name, get_trip_summary

v3 tools (PostgreSQL-backed, requires docker compose postgres):
  get_booking_status, cancel_booking, search_flights (added in Day 04 upgrade)

ToolContext usage:
  get_booking_status  — writes current_booking_id, current_passenger to state.
  cancel_booking      — writes current_booking_id to state.
  search_flights      — writes last_search_origin, last_search_destination to state.
  save_traveler_name  — writes traveler_name to state.
  get_trip_summary    — reads all state keys and returns a structured summary.
"""

import logging
from typing import Any

from google.adk.tools import ToolContext

log = logging.getLogger(__name__)

# ── Static flight database ─────────────────────────────────────────────────
_FLIGHT_DB: dict[str, dict[str, Any]] = {
    "AI-204": {
        "flight_number": "AI-204",
        "route": "Mumbai (BOM) → London (LHR)",
        "status": "On Time",
        "departure": "14:35 IST",
        "arrival": "19:50 BST",
        "gate": "B12",
    },
    "SQ-422": {
        "flight_number": "SQ-422",
        "route": "Singapore (SIN) → Tokyo (NRT)",
        "status": "Delayed",
        "departure": "08:20 SGT (delayed 45 min)",
        "arrival": "16:35 JST",
        "gate": "C7",
    },
    "EK-501": {
        "flight_number": "EK-501",
        "route": "Dubai (DXB) → Paris (CDG)",
        "status": "Boarding",
        "departure": "02:10 GST",
        "arrival": "06:20 CET",
        "gate": "A3",
    },
}

# ── Static hotel database ──────────────────────────────────────────────────
_HOTEL_DB: dict[str, list[dict[str, Any]]] = {
    "tokyo": [
        {
            "name": "The Prince Park Tower Tokyo",
            "stars": 5,
            "area": "Minato",
            "near_station": "Hamamatsucho",
            "price_per_night_usd": 280,
            "available": True,
        },
        {
            "name": "Shinjuku Granbell Hotel",
            "stars": 4,
            "area": "Shinjuku",
            "near_station": "Shinjuku",
            "price_per_night_usd": 140,
            "available": True,
        },
        {
            "name": "Dormy Inn Asakusa",
            "stars": 3,
            "area": "Asakusa",
            "near_station": "Asakusa",
            "price_per_night_usd": 90,
            "available": True,
        },
    ],
    "paris": [
        {
            "name": "Hotel Le Meurice",
            "stars": 5,
            "area": "1st arrondissement",
            "near_station": "Tuileries",
            "price_per_night_usd": 950,
            "available": True,
        },
        {
            "name": "Hotel Fabric",
            "stars": 4,
            "area": "Oberkampf",
            "near_station": "Oberkampf",
            "price_per_night_usd": 220,
            "available": True,
        },
        {
            "name": "Generator Paris",
            "stars": 3,
            "area": "Canal Saint-Martin",
            "near_station": "Colonel Fabien",
            "price_per_night_usd": 75,
            "available": True,
        },
    ],
    "singapore": [
        {
            "name": "Marina Bay Sands",
            "stars": 5,
            "area": "Marina Bay",
            "near_station": "Bayfront",
            "price_per_night_usd": 600,
            "available": True,
        },
        {
            "name": "Hotel Mono",
            "stars": 4,
            "area": "Chinatown",
            "near_station": "Chinatown",
            "price_per_night_usd": 150,
            "available": True,
        },
    ],
}


# ── Tool functions ─────────────────────────────────────────────────────────

def get_flight_status(
    flight_number: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Return the current status of a flight.
    Writes the checked flight number to session state under 'last_flight_checked'.

    Args:
        flight_number: The flight identifier, e.g. "AI-204".

    Returns:
        A dict with flight details, or an error dict if not found.
    """
    key = flight_number.strip().upper()
    tool_context.state["last_flight_checked"] = key
    if key in _FLIGHT_DB:
        return {"found": True, **_FLIGHT_DB[key]}
    return {
        "found": False,
        "flight_number": flight_number,
        "error": (
            f"Flight '{flight_number}' was not found in the system. "
            "Please verify the flight number and try again."
        ),
    }


def search_hotels(
    city: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Search for available hotels in a city.
    Writes the searched city to session state under 'destination'.

    Args:
        city: The destination city name, e.g. "Tokyo".

    Returns:
        A dict with a list of hotel options, or an error dict if no results.
    """
    tool_context.state["destination"] = city
    key = city.strip().lower()
    hotels = _HOTEL_DB.get(key)
    if hotels:
        return {"found": True, "city": city, "hotels": hotels}
    return {
        "found": False,
        "city": city,
        "error": (
            f"No hotel listings found for '{city}'. "
            "Try a major city such as Tokyo, Paris, or Singapore."
        ),
    }


def save_traveler_name(
    name: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Save the traveler's name to session state.
    Call this whenever the user introduces themselves by name.

    Args:
        name: The traveler's name, e.g. "Priya".

    Returns:
        A confirmation dict.
    """
    if not name or not name.strip():
        return {"saved": False, "error": "Name cannot be empty."}
    clean = name.strip()
    tool_context.state["traveler_name"] = clean
    return {"saved": True, "traveler_name": clean}


def get_trip_summary(tool_context: ToolContext) -> dict[str, Any]:
    """
    Return a structured summary of the traveler's session state.
    Reads traveler_name, destination, and other context from state.

    Returns:
        A dict with all known trip context from the current session.
    """
    return {
        "traveler_name": tool_context.state.get("traveler_name", "unknown"),
        "destination": tool_context.state.get("destination", "not set"),
        "last_flight_checked": tool_context.state.get("last_flight_checked", "none"),
        "current_booking_id": tool_context.state.get("current_booking_id", "none"),
        "last_search_origin": tool_context.state.get("last_search_origin", "not set"),
        "last_search_destination": tool_context.state.get("last_search_destination", "not set"),
    }


# ── V3 tools (PostgreSQL-backed) ───────────────────────────────────────────

def get_booking_status(
    booking_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Look up a booking by ID and return its current status.
    Queries PostgreSQL bookings table; requires Session backend = database or redis.

    Args:
        booking_id: The booking reference, e.g. "TB-1001".

    Returns:
        A dict with booking details, or an error dict if not found.
    """
    if not booking_id or not booking_id.strip():
        return {"found": False, "error": "Booking ID cannot be empty."}

    bid = booking_id.strip().upper()
    try:
        from db import query_one
        row = query_one("SELECT * FROM bookings WHERE booking_id = %s", (bid,))
    except Exception as exc:
        log.error("DB error in get_booking_status: %s", exc)
        return {"found": False, "error": "Booking lookup is temporarily unavailable. Please try again shortly."}

    if row is None:
        return {
            "found": False,
            "booking_id": bid,
            "error": f"No booking found for '{bid}'. Please check the reference and try again.",
        }

    tool_context.state["current_booking_id"] = bid
    tool_context.state["current_passenger"] = row["passenger_name"]

    return {
        "found": True,
        "booking_id": row["booking_id"],
        "passenger_name": row["passenger_name"],
        "flight_number": row["flight_number"],
        "route": f"{row['origin']} → {row['destination']}",
        "departure_date": str(row["departure_date"]),
        "seat_class": row["seat_class"],
        "status": row["status"],
    }


def cancel_booking(
    booking_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Cancel a confirmed booking.
    If booking_id is "current" or empty, uses the ID saved in session state.

    Args:
        booking_id: The booking reference, or "current" to use the session value.

    Returns:
        A dict indicating success or the reason cancellation failed.
    """
    if not booking_id or booking_id.strip().lower() in ("", "current"):
        booking_id = tool_context.state.get("current_booking_id", "")

    if not booking_id:
        return {
            "cancelled": False,
            "error": "No booking ID provided or found in this session. Please specify a booking reference.",
        }

    bid = booking_id.strip().upper()
    try:
        from db import query_one, execute
        row = query_one(
            "SELECT status, passenger_name FROM bookings WHERE booking_id = %s", (bid,)
        )
    except Exception as exc:
        log.error("DB error in cancel_booking lookup: %s", exc)
        return {"cancelled": False, "error": "Cancellation service is temporarily unavailable. Please try again shortly."}

    if row is None:
        return {"cancelled": False, "booking_id": bid, "error": f"Booking '{bid}' not found."}

    if row["status"].lower() == "cancelled":
        return {
            "cancelled": False,
            "booking_id": bid,
            "error": f"Booking '{bid}' is already cancelled. No changes were made.",
        }

    try:
        execute("UPDATE bookings SET status = 'Cancelled' WHERE booking_id = %s", (bid,))
    except Exception as exc:
        log.error("DB error updating booking: %s", exc)
        return {"cancelled": False, "error": "Cancellation could not be saved. Please try again."}

    tool_context.state["current_booking_id"] = bid
    return {
        "cancelled": True,
        "booking_id": bid,
        "passenger_name": row["passenger_name"],
        "message": f"Booking {bid} for {row['passenger_name']} has been successfully cancelled.",
    }


def search_flights(
    origin: str,
    destination: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Search for available flights between two cities or airport codes.
    Queries PostgreSQL flights table.

    Args:
        origin:      Departure city or airport code, e.g. "Mumbai" or "BOM".
        destination: Arrival city or airport code, e.g. "London" or "LHR".

    Returns:
        A dict with matching flights sorted by price, or an error dict.
    """
    if not origin or not origin.strip():
        return {"found": False, "error": "Origin is required."}
    if not destination or not destination.strip():
        return {"found": False, "error": "Destination is required."}

    orig = origin.strip()
    dest = destination.strip()

    tool_context.state["last_search_origin"] = orig
    tool_context.state["last_search_destination"] = dest

    try:
        from db import query_all
        rows = query_all(
            """
            SELECT flight_number, airline, origin, destination,
                   departure_time::text AS departure_time,
                   arrival_time::text   AS arrival_time,
                   duration_min, seat_class, price_usd, available_seats
            FROM flights
            WHERE (LOWER(origin) = LOWER(%s) OR LOWER(origin_code) = LOWER(%s))
              AND (LOWER(destination) = LOWER(%s) OR LOWER(destination_code) = LOWER(%s))
              AND available_seats > 0
            ORDER BY price_usd ASC
            """,
            (orig, orig, dest, dest),
        )
    except Exception as exc:
        log.error("DB error in search_flights: %s", exc)
        return {"found": False, "error": "Flight search is temporarily unavailable. Please try again shortly."}

    if not rows:
        return {
            "found": False,
            "origin": orig,
            "destination": dest,
            "error": (
                f"No available flights found from '{orig}' to '{dest}'. "
                "Try using the full city name or IATA code."
            ),
        }

    return {
        "found": True,
        "origin": orig,
        "destination": dest,
        "flights": [
            {
                "flight_number": r["flight_number"],
                "airline": r["airline"],
                "departure": r["departure_time"],
                "arrival": r["arrival_time"],
                "duration_min": r["duration_min"],
                "class": r["seat_class"],
                "price_usd": float(r["price_usd"]),
                "seats_left": r["available_seats"],
            }
            for r in rows
        ],
    }


# ── Tool lists (version-specific) ──────────────────────────────────────────

# V1–V2: Static tools only
TOOLS_V2 = [get_flight_status, search_hotels, save_traveler_name, get_trip_summary]

# V3: Static tools + database-backed tools
TOOLS_V3 = [
    get_booking_status,
    cancel_booking,
    search_flights,
    get_flight_status,
    search_hotels,
    save_traveler_name,
    get_trip_summary,
]

# Default: Use v2 tools (backward compatible)
TOOLS = TOOLS_V2
