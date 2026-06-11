"""
booking_server.py — Booking MCP tool server
==============================================
A FastMCP server exposing TravelBot's flight-booking tools over stdio.
ADK spawns this as a subprocess via MCPToolset/StdioConnectionParams —
see ../agent.py.

Tools:
  get_booking_status(booking_id)   -> quick status lookup
  get_booking_details(booking_id)  -> full booking record
  list_bookings(email)             -> all bookings for a traveller
  cancel_booking(booking_id, confirm=False)
                                    -> cancel ONE booking; requires an
                                       explicit confirm=True. There is
                                       deliberately no "cancel all
                                       bookings" tool.

Run directly for local testing:
    python booking_server.py
"""

from mcp.server.fastmcp import FastMCP

# WARNING level — keep the demo's console output free of per-request
# "Processing request of type ..." noise from the MCP server loop.
mcp = FastMCP("travelbot-booking", log_level="WARNING")

# ── Mock booking data ───────────────────────────────────────────────────────
_BOOKINGS: dict[str, dict] = {
    "TB-2001": {
        "booking_id": "TB-2001",
        "passenger_name": "Ravi Kumar",
        "email": "ravi.kumar@example.com",
        "origin": "Bengaluru (BLR)",
        "destination": "Delhi (DEL)",
        "departure_date": "2026-06-12",
        "flight_number": "TB-401",
        "cabin_class": "Economy",
        "status": "Confirmed",
    },
    "TB-2002": {
        "booking_id": "TB-2002",
        "passenger_name": "Meera Nair",
        "email": "meera.nair@example.com",
        "origin": "Mumbai (BOM)",
        "destination": "Dubai (DXB)",
        "departure_date": "2026-06-19",
        "flight_number": "TB-512",
        "cabin_class": "Business",
        "status": "Confirmed",
    },
    "TB-2003": {
        "booking_id": "TB-2003",
        "passenger_name": "John Mathews",
        "email": "john@example.com",
        "origin": "Bengaluru (BLR)",
        "destination": "Singapore (SIN)",
        "departure_date": "2026-06-04",
        "flight_number": "TB-330",
        "cabin_class": "Economy",
        "status": "Completed",
    },
    "TB-2004": {
        "booking_id": "TB-2004",
        "passenger_name": "John Mathews",
        "email": "john@example.com",
        "origin": "Delhi (DEL)",
        "destination": "Singapore (SIN)",
        "departure_date": "2026-06-18",
        "flight_number": "TB-345",
        "cabin_class": "Economy",
        "status": "Confirmed",
    },
    "TB-2005": {
        "booking_id": "TB-2005",
        "passenger_name": "John Mathews",
        "email": "john@example.com",
        "origin": "Mumbai (BOM)",
        "destination": "Dubai (DXB)",
        "departure_date": "2026-06-19",
        "flight_number": "TB-512",
        "cabin_class": "Premium Economy",
        "status": "Confirmed",
    },
}


def _not_found(booking_id: str) -> dict:
    return {
        "found": False,
        "booking_id": booking_id,
        "message": (
            f"No booking found with ID '{booking_id}'. Double-check the "
            "reference (it looks like TB-XXXX) or look it up by email instead."
        ),
    }


@mcp.tool()
def get_booking_status(booking_id: str) -> dict:
    """Look up the status of a single flight booking by its reference.

    Args:
        booking_id: Booking reference, e.g. "TB-2001".

    Returns:
        A dict with booking_id, route, departure_date and status if found,
        or {"found": False, ...} with a guidance message if not.
    """
    booking = _BOOKINGS.get(booking_id.strip().upper())
    if booking is None:
        return _not_found(booking_id)

    return {
        "found": True,
        "booking_id": booking["booking_id"],
        "route": f"{booking['origin']} -> {booking['destination']}",
        "departure_date": booking["departure_date"],
        "status": booking["status"],
    }


@mcp.tool()
def get_booking_details(booking_id: str) -> dict:
    """Fetch the full record for a single flight booking.

    Args:
        booking_id: Booking reference, e.g. "TB-2002".

    Returns:
        The full booking record (passenger, route, dates, cabin class,
        status) if found, or {"found": False, ...} if not.
    """
    booking = _BOOKINGS.get(booking_id.strip().upper())
    if booking is None:
        return _not_found(booking_id)

    return {"found": True, **booking}


@mcp.tool()
def list_bookings(email: str) -> dict:
    """List all bookings for a traveller, identified by email address.

    Use this when the user does not know (or did not provide) a booking
    reference, or when a request could affect more than one booking.

    Args:
        email: Traveller's email address, e.g. "john@example.com".

    Returns:
        A dict with the email and a list of bookings (booking_id, route,
        departure_date, cabin_class, status). The list is empty if no
        bookings match.
    """
    email_norm = email.strip().lower()
    matches = [
        {
            "booking_id": b["booking_id"],
            "route": f"{b['origin']} -> {b['destination']}",
            "departure_date": b["departure_date"],
            "cabin_class": b["cabin_class"],
            "status": b["status"],
        }
        for b in _BOOKINGS.values()
        if b["email"].lower() == email_norm
    ]

    result: dict = {"email": email, "bookings": matches}
    if not matches:
        result["message"] = f"No bookings found for {email}."
    return result


@mcp.tool()
def cancel_booking(booking_id: str, confirm: bool = False) -> dict:
    """Cancel a single flight booking. Requires explicit confirmation.

    This tool only ever accepts ONE booking_id - there is intentionally no
    way to cancel multiple bookings in one call. If a user asks to cancel
    "all" bookings, or every booking matching some criteria, use
    list_bookings to find the candidates and ask the user to choose a
    specific booking_id before calling this tool.

    Args:
        booking_id: Booking reference to cancel, e.g. "TB-2004".
        confirm: Must be True to actually cancel. Call this tool first with
            confirm=False (or omitted) to preview what will be cancelled,
            then call again with confirm=True only after the user agrees.

    Returns:
        A dict describing the booking to be cancelled (when confirm=False),
        confirmation that it was cancelled (when confirm=True), or
        {"found": False, ...} if the booking_id does not exist.
    """
    booking = _BOOKINGS.get(booking_id.strip().upper())
    if booking is None:
        return _not_found(booking_id)

    route = f"{booking['origin']} -> {booking['destination']}"

    if not confirm:
        return {
            "found": True,
            "booking_id": booking["booking_id"],
            "status": "cancellation_pending",
            "message": (
                f"This will cancel booking {booking['booking_id']} "
                f"({route} on {booking['departure_date']}). "
                "Call cancel_booking again with confirm=True to proceed."
            ),
        }

    booking["status"] = "Cancelled"
    return {
        "found": True,
        "booking_id": booking["booking_id"],
        "status": "Cancelled",
        "message": f"Booking {booking['booking_id']} ({route}) has been cancelled.",
    }


if __name__ == "__main__":
    mcp.run()
