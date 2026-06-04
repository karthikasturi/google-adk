"""
tests/test_tools.py — Unit tests for Day 04 TravelBot tools
------------------------------------------------------------
Tests run against a real PostgreSQL instance.
Use:  SESSION_BACKEND=memory  to skip the ADK DB session service during tests.

Requires:  docker compose up -d postgres
Run with:  python -m pytest tests/ -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the day04 root importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import (
    cancel_booking,
    get_booking_status,
    get_trip_summary,
    save_traveler_name,
    search_flights,
)


# ── ToolContext stub ────────────────────────────────────────────────────────

def _ctx(initial: dict | None = None) -> MagicMock:
    """Return a minimal ToolContext mock with a real state dict."""
    ctx = MagicMock()
    ctx.state = initial or {}
    return ctx


# ── get_booking_status ──────────────────────────────────────────────────────

class TestGetBookingStatus:
    def test_empty_id_returns_error(self):
        result = get_booking_status("", _ctx())
        assert result["found"] is False
        assert "empty" in result["error"].lower()

    def test_whitespace_id_returns_error(self):
        result = get_booking_status("   ", _ctx())
        assert result["found"] is False

    def test_unknown_id_returns_not_found(self):
        with patch("tools.query_one", return_value=None):
            result = get_booking_status("TB-9999", _ctx())
        assert result["found"] is False
        assert "TB-9999" in result["error"]

    def test_valid_booking_returns_details_and_writes_state(self):
        fake_row = {
            "booking_id": "TB-1001",
            "passenger_name": "Priya Sharma",
            "flight_number": "AI-204",
            "origin": "Mumbai",
            "destination": "London",
            "departure_date": "2026-07-15",
            "seat_class": "Economy",
            "status": "Confirmed",
        }
        ctx = _ctx()
        with patch("tools.query_one", return_value=fake_row):
            result = get_booking_status("tb-1001", ctx)

        assert result["found"] is True
        assert result["booking_id"] == "TB-1001"
        assert result["passenger_name"] == "Priya Sharma"
        assert ctx.state["current_booking_id"] == "TB-1001"
        assert ctx.state["current_passenger"] == "Priya Sharma"

    def test_db_error_returns_safe_message(self):
        with patch("tools.query_one", side_effect=Exception("connection refused")):
            result = get_booking_status("TB-1001", _ctx())
        assert result["found"] is False
        assert "connection refused" not in result["error"]   # no stack trace leaked
        assert "unavailable" in result["error"].lower()


# ── cancel_booking ─────────────────────────────────────────────────────────

class TestCancelBooking:
    def test_no_id_and_no_session_state_returns_error(self):
        result = cancel_booking("", _ctx())
        assert result["cancelled"] is False
        assert "No booking ID" in result["error"]

    def test_resolves_current_from_session_state(self):
        ctx = _ctx({"current_booking_id": "TB-1004"})
        fake_row = {"status": "Confirmed", "passenger_name": "James Liu"}
        with (
            patch("tools.query_one", return_value=fake_row),
            patch("tools.execute", return_value=1),
        ):
            result = cancel_booking("current", ctx)
        assert result["cancelled"] is True
        assert result["booking_id"] == "TB-1004"

    def test_already_cancelled_returns_error(self):
        ctx = _ctx()
        fake_row = {"status": "Cancelled", "passenger_name": "Aisha Mehta"}
        with patch("tools.query_one", return_value=fake_row):
            result = cancel_booking("TB-1003", ctx)
        assert result["cancelled"] is False
        assert "already cancelled" in result["error"].lower()

    def test_unknown_booking_returns_not_found(self):
        with patch("tools.query_one", return_value=None):
            result = cancel_booking("TB-9999", _ctx())
        assert result["cancelled"] is False
        assert "TB-9999" in result["error"]

    def test_db_error_on_lookup_returns_safe_message(self):
        with patch("tools.query_one", side_effect=Exception("timeout")):
            result = cancel_booking("TB-1001", _ctx())
        assert result["cancelled"] is False
        assert "timeout" not in result["error"]
        assert "unavailable" in result["error"].lower()

    def test_db_error_on_update_returns_safe_message(self):
        fake_row = {"status": "Confirmed", "passenger_name": "Priya"}
        with (
            patch("tools.query_one", return_value=fake_row),
            patch("tools.execute", side_effect=Exception("disk full")),
        ):
            result = cancel_booking("TB-1001", _ctx())
        assert result["cancelled"] is False
        assert "disk full" not in result["error"]


# ── search_flights ──────────────────────────────────────────────────────────

class TestSearchFlights:
    def test_empty_origin_returns_error(self):
        result = search_flights("", "London", _ctx())
        assert result["found"] is False
        assert "Origin" in result["error"]

    def test_empty_destination_returns_error(self):
        result = search_flights("Mumbai", "", _ctx())
        assert result["found"] is False
        assert "Destination" in result["error"]

    def test_no_results_returns_not_found(self):
        ctx = _ctx()
        with patch("tools.query_all", return_value=[]):
            result = search_flights("Mumbai", "Sydney", ctx)
        assert result["found"] is False
        assert ctx.state["last_search_origin"] == "Mumbai"
        assert ctx.state["last_search_destination"] == "Sydney"

    def test_results_returned_and_state_written(self):
        fake_rows = [
            {
                "flight_number": "AI-204",
                "airline": "Air India",
                "origin": "Mumbai",
                "destination": "London",
                "departure_time": "14:35:00",
                "arrival_time": "19:50:00",
                "duration_min": 545,
                "seat_class": "Economy",
                "price_usd": "420.00",
                "available_seats": 82,
            }
        ]
        ctx = _ctx()
        with patch("tools.query_all", return_value=fake_rows):
            result = search_flights("Mumbai", "London", ctx)
        assert result["found"] is True
        assert len(result["flights"]) == 1
        assert result["flights"][0]["flight_number"] == "AI-204"
        assert ctx.state["last_search_origin"] == "Mumbai"
        assert ctx.state["last_search_destination"] == "London"

    def test_db_error_returns_safe_message(self):
        with patch("tools.query_all", side_effect=Exception("connection lost")):
            result = search_flights("Mumbai", "London", _ctx())
        assert result["found"] is False
        assert "connection lost" not in result["error"]
        assert "unavailable" in result["error"].lower()


# ── save_traveler_name ──────────────────────────────────────────────────────

class TestSaveTravelerName:
    def test_empty_name_returns_error(self):
        result = save_traveler_name("", _ctx())
        assert result["saved"] is False

    def test_saves_trimmed_name_to_state(self):
        ctx = _ctx()
        result = save_traveler_name("  Priya  ", ctx)
        assert result["saved"] is True
        assert result["traveler_name"] == "Priya"
        assert ctx.state["traveler_name"] == "Priya"


# ── get_trip_summary ────────────────────────────────────────────────────────

class TestGetTripSummary:
    def test_returns_defaults_when_state_empty(self):
        result = get_trip_summary(_ctx())
        assert result["traveler_name"] == "unknown"
        assert result["current_booking_id"] == "none"
        assert result["last_search_origin"] == "not set"

    def test_returns_values_from_state(self):
        ctx = _ctx({
            "traveler_name": "Priya",
            "current_booking_id": "TB-1001",
            "current_passenger": "Priya Sharma",
            "last_search_origin": "Mumbai",
            "last_search_destination": "London",
        })
        result = get_trip_summary(ctx)
        assert result["traveler_name"] == "Priya"
        assert result["current_booking_id"] == "TB-1001"
        assert result["last_search_origin"] == "Mumbai"
