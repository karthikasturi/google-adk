"""
tools.py — Day 04: Production-style tools backed by PostgreSQL
--------------------------------------------------------------
Upgrades Day 03 mock data to real database queries.
Session state usage is identical to Day 03 — same ToolContext.state pattern,
same function signatures, same return shapes.  Drop-in upgrade.

Tool context writes (working memory):
  get_booking_status → current_booking_id, current_passenger
  cancel_booking     → current_booking_id
  search_flights     → last_search_origin, last_search_destination
  save_traveler_name → traveler_name

Day 03 tools retained:
  save_traveler_name, get_trip_summary
"""

import logging
from typing import Any

from google.adk.tools import ToolContext

from db import execute, query_all, query_one

log = logging.getLogger(__name__)


# ── Booking tools ──────────────────────────────────────────────────────────

def get_booking_status(
    booking_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Look up a booking by ID and return its current status.
    Saves current_booking_id and current_passenger to session state so
    follow-up questions don't need to repeat the booking reference.

    Args:
        booking_id: The booking reference, e.g. "TB-1001".

    Returns:
        A dict with booking details, or an error dict if not found.
    """
    if not booking_id or not booking_id.strip():
        return {"found": False, "error": "Booking ID cannot be empty."}

    bid = booking_id.strip().upper()
    try:
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

    # Persist the booking context for this session turn
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
    If booking_id is "current" or empty, the ID saved in session state is used.
    Rejects already-cancelled bookings with a clear message.

    Args:
        booking_id: The booking reference, or "current" to use the session value.

    Returns:
        A dict indicating success or the reason cancellation failed.
    """
    # Resolve "current" shorthand from session state
    if not booking_id or booking_id.strip().lower() in ("", "current"):
        booking_id = tool_context.state.get("current_booking_id", "")

    if not booking_id:
        return {
            "cancelled": False,
            "error": "No booking ID provided or found in this session. Please specify a booking reference.",
        }

    bid = booking_id.strip().upper()
    try:
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


# ── Flight search tools ────────────────────────────────────────────────────

def search_flights(
    origin: str,
    destination: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Search for available flights between two cities or airport codes.
    Accepts full city names (e.g. "Mumbai") or IATA codes (e.g. "BOM").
    Saves the route to session state for follow-up questions.

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

    # Persist route to session for follow-up questions
    tool_context.state["last_search_origin"] = orig
    tool_context.state["last_search_destination"] = dest

    try:
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


# ── Day 03 tools retained (same signatures, improved validation) ───────────

def save_traveler_name(
    name: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """
    Save the traveler's name to session state.
    Call this as soon as the user introduces themselves.

    Args:
        name: The traveler's name.
    """
    if not name or not name.strip():
        return {"saved": False, "error": "Name cannot be empty."}
    clean = name.strip()
    tool_context.state["traveler_name"] = clean
    return {"saved": True, "traveler_name": clean}


def get_trip_summary(tool_context: ToolContext) -> dict[str, Any]:
    """
    Return the traveler's current session working memory.
    Reads all known state keys — booking context, route search, and name.
    """
    return {
        "traveler_name": tool_context.state.get("traveler_name", "unknown"),
        "current_booking_id": tool_context.state.get("current_booking_id", "none"),
        "current_passenger": tool_context.state.get("current_passenger", "unknown"),
        "last_search_origin": tool_context.state.get("last_search_origin", "not set"),
        "last_search_destination": tool_context.state.get("last_search_destination", "not set"),
    }


# ── Tool list passed to LlmAgent ───────────────────────────────────────────
TOOLS = [
    get_booking_status,
    cancel_booking,
    search_flights,
    save_traveler_name,
    get_trip_summary,
]
