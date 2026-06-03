"""
shared/tools.py — TravelBot mock tools
----------------------------------------
Source of truth for all tool functions used by TravelBot across versions.

v2 — get_flight_status, search_hotels, save_traveler_name, get_trip_summary
v3 — search_destinations, get_visa_info (added in Day 04 module — RAG)
vN — additional tools added here as the project grows

ToolContext usage:
  get_flight_status  — writes last_flight_checked to session state.
  search_hotels      — writes destination to session state.
  save_traveler_name — writes traveler_name to session state.
  get_trip_summary   — reads all state keys and returns a structured summary.
"""

from typing import Any

from google.adk.tools import ToolContext

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
    tool_context.state["traveler_name"] = name
    return {"saved": True, "traveler_name": name}


def get_trip_summary(tool_context: ToolContext) -> dict[str, Any]:
    """
    Return a structured summary of the traveler's session state.
    Reads traveler_name, destination, and last_flight_checked from state.

    Returns:
        A dict with all known trip context from the current session.
    """
    return {
        "traveler_name": tool_context.state.get("traveler_name", "unknown"),
        "destination": tool_context.state.get("destination", "not set"),
        "last_flight_checked": tool_context.state.get("last_flight_checked", "none"),
    }


# ── Tool list passed to LlmAgent ───────────────────────────────────────────
# Add new tools here as TravelBot grows across modules.
TOOLS = [get_flight_status, search_hotels, save_traveler_name, get_trip_summary]
