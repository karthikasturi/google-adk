"""
tools.py — Day 10: TravelBot tools for the Chainlit generative-UI demo
=======================================================================
Extends Day 09a's tools with:
  - Extra bookings (DEL-SIN-202 for scenario 2A)
  - More attraction cities (Goa, Tokyo, Amsterdam, Berlin for 1A/4A/5A)
  - More weather cities (Goa, Tokyo, Amsterdam, Berlin)
  - search_hotels — used by hotel_specialist and Group 3 (budget action
    buttons) and Group 5B (simulated-error scenario)

Set SIMULATE_HOTEL_ERROR=1 in .env to make search_hotels return an error
response, which exercises Group 5B (graceful error display in Chainlit UI).
"""

import os

# ── Mock flight booking data ────────────────────────────────────────────────
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
        "booking_id": "DEL-SIN-202",
        "origin": "Delhi (DEL)",
        "destination": "Singapore (SIN)",
        "departure": "Tomorrow, 08:15",
        "flight_number": "TB-303",
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

    Args:
        booking_id: Booking reference, e.g. "DEL-SIN-202". Optional.
        origin: Departure city or airport, e.g. "Delhi". Optional.
        destination: Arrival city or airport, e.g. "Singapore". Optional.

    Returns:
        The matching booking record, or {"found": False, ...} if not found.
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
            "the reference (it looks like XXX-XXX-NNN) or the cities."
        ),
    }


# ── Mock attraction data ─────────────────────────────────────────────────────
_ATTRACTIONS: dict[str, list[dict]] = {
    "singapore": [
        {"name": "Sentosa Island", "category": "Theme park / beach", "tags": ["kid-friendly", "family", "outdoor"]},
        {"name": "Gardens by the Bay", "category": "Gardens", "tags": ["kid-friendly", "family", "outdoor", "iconic"]},
        {"name": "Singapore Zoo", "category": "Zoo", "tags": ["kid-friendly", "family", "outdoor"]},
        {"name": "Science Centre Singapore", "category": "Museum", "tags": ["kid-friendly", "family", "indoor"]},
        {"name": "Universal Studios Singapore", "category": "Theme park", "tags": ["kid-friendly", "family", "indoor"]},
    ],
    "goa": [
        {"name": "Baga Beach", "category": "Beach", "tags": ["beach", "outdoor", "family"]},
        {"name": "Anjuna Flea Market", "category": "Market", "tags": ["shopping", "food", "local"]},
        {"name": "Dudhsagar Waterfall", "category": "Nature", "tags": ["outdoor", "nature", "adventure"]},
        {"name": "Old Goa Churches", "category": "Heritage", "tags": ["history", "indoor", "culture"]},
        {"name": "Fisherman's Wharf", "category": "Restaurant / local food", "tags": ["food", "local", "seafood"]},
        {"name": "Colva Beach", "category": "Beach", "tags": ["beach", "outdoor", "peaceful"]},
    ],
    "dubai": [
        {"name": "Burj Khalifa observation deck", "category": "Landmark", "tags": ["iconic", "family"]},
        {"name": "Dubai Mall & Aquarium", "category": "Shopping / aquarium", "tags": ["family", "indoor"]},
        {"name": "Desert safari", "category": "Tour", "tags": ["outdoor", "family", "adventure"]},
        {"name": "Dubai Museum (Al Fahidi Fort)", "category": "Museum", "tags": ["museum", "indoor"]},
        {"name": "Jumeirah Beach", "category": "Beach", "tags": ["outdoor", "family"]},
    ],
    "paris": [
        {"name": "Eiffel Tower", "category": "Landmark", "tags": ["iconic", "outdoor"]},
        {"name": "Louvre Museum", "category": "Museum", "tags": ["museum", "indoor", "art"]},
        {"name": "Musée d'Orsay", "category": "Museum", "tags": ["museum", "indoor", "art"]},
        {"name": "Seine river cruise", "category": "Tour", "tags": ["outdoor", "family", "scenic"]},
        {"name": "Montmartre & Sacré-Cœur", "category": "Neighbourhood", "tags": ["culture", "outdoor", "art"]},
    ],
    "tokyo": [
        {"name": "Senso-ji Temple (Asakusa)", "category": "Heritage", "tags": ["culture", "outdoor", "iconic"]},
        {"name": "Shibuya Crossing & district", "category": "Neighbourhood", "tags": ["iconic", "shopping", "outdoor"]},
        {"name": "Ueno Park & Museums", "category": "Park / museum", "tags": ["family", "outdoor", "culture"]},
        {"name": "Tsukiji Outer Market", "category": "Market / food", "tags": ["food", "local", "morning"]},
        {"name": "teamLab Borderless", "category": "Digital art", "tags": ["art", "indoor", "family", "unique"]},
        {"name": "Akihabara Electric Town", "category": "Shopping", "tags": ["shopping", "tech", "anime"]},
    ],
    "amsterdam": [
        {"name": "Rijksmuseum", "category": "Museum", "tags": ["museum", "indoor", "art", "iconic"]},
        {"name": "Van Gogh Museum", "category": "Museum", "tags": ["museum", "indoor", "art"]},
        {"name": "Anne Frank House", "category": "Heritage / museum", "tags": ["history", "indoor"]},
        {"name": "Canal cruise", "category": "Tour", "tags": ["outdoor", "scenic", "iconic"]},
        {"name": "Vondelpark", "category": "Park", "tags": ["outdoor", "family", "peaceful"]},
    ],
    "berlin": [
        {"name": "Brandenburg Gate", "category": "Landmark", "tags": ["iconic", "outdoor", "history"]},
        {"name": "Museum Island (Museumsinsel)", "category": "Museum cluster", "tags": ["museum", "indoor", "art", "history"]},
        {"name": "East Side Gallery", "category": "Art / history", "tags": ["outdoor", "art", "history"]},
        {"name": "Tiergarten", "category": "Park", "tags": ["outdoor", "family", "peaceful"]},
        {"name": "Checkpoint Charlie", "category": "Heritage", "tags": ["history", "outdoor", "iconic"]},
    ],
}


def get_attractions(city: str, days: int | None = None, interests: str | None = None) -> dict:
    """List attractions and activities for a city, optionally filtered by interest.

    Args:
        city: City name, e.g. "Goa" or "Tokyo".
        days: Optional number of days the itinerary should cover.
        interests: Optional interest keyword, e.g. "beaches" or "museums".

    Returns:
        Dict with city, filters applied, and a list of matching attractions.
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
        kw = interests.strip().lower()
        matches = [a for a in results if any(kw in tag for tag in a["tags"]) or kw in a["category"].lower()]
        if matches:
            results = matches

    return {
        "city": city,
        "filters": {"days": days, "interests": interests},
        "attractions": results,
    }


# ── Mock weather data ────────────────────────────────────────────────────────
_WEATHER: dict[str, list[dict]] = {
    "singapore": [
        {"day": 1, "condition": "Thunderstorms", "high_c": 30, "notes": "Heavy afternoon downpours - better for indoor plans"},
        {"day": 2, "condition": "Sunny", "high_c": 32, "notes": "Clear and hot - good for outdoor activities"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 31, "notes": "Warm with light humidity"},
    ],
    "goa": [
        {"day": 1, "condition": "Sunny", "high_c": 33, "notes": "Perfect beach weather"},
        {"day": 2, "condition": "Sunny", "high_c": 34, "notes": "Ideal for water sports and markets"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 32, "notes": "Good for sightseeing"},
    ],
    "dubai": [
        {"day": 1, "condition": "Sunny", "high_c": 39, "notes": "Very hot - best for early-morning or indoor activities"},
        {"day": 2, "condition": "Sandstorm", "high_c": 36, "notes": "Low visibility - avoid outdoor desert activities"},
        {"day": 3, "condition": "Sunny", "high_c": 37, "notes": "Clear skies, still very hot"},
    ],
    "paris": [
        {"day": 1, "condition": "Rainy", "high_c": 14, "notes": "Steady rain - indoor activities recommended"},
        {"day": 2, "condition": "Cloudy", "high_c": 16, "notes": "Dry but overcast - ok for walking"},
        {"day": 3, "condition": "Sunny", "high_c": 18, "notes": "Clear skies - best day for Eiffel Tower"},
    ],
    "tokyo": [
        {"day": 1, "condition": "Sunny", "high_c": 22, "notes": "Crisp and clear - ideal for outdoor temples"},
        {"day": 2, "condition": "Rainy", "high_c": 18, "notes": "Rain in the afternoon - plan indoor activities"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 20, "notes": "Mild - good for Shibuya or Ueno"},
    ],
    "amsterdam": [
        {"day": 1, "condition": "Rainy", "high_c": 13, "notes": "Dutch drizzle - visit the museums"},
        {"day": 2, "condition": "Partly cloudy", "high_c": 15, "notes": "Dry intervals - good for a canal cruise"},
        {"day": 3, "condition": "Sunny", "high_c": 17, "notes": "Clear - best day for Vondelpark and outdoors"},
    ],
    "berlin": [
        {"day": 1, "condition": "Cloudy", "high_c": 16, "notes": "Overcast but dry - fine for walking"},
        {"day": 2, "condition": "Sunny", "high_c": 20, "notes": "Warm and clear - great for East Side Gallery"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 18, "notes": "Light clouds - good for Tiergarten"},
    ],
}


def get_weather_forecast(city: str, days: int | None = None) -> dict:
    """Get a short-range daily weather forecast for a city.

    Args:
        city: City name, e.g. "Goa" or "Tokyo".
        days: Optional number of days to return (up to 3).

    Returns:
        Dict with the city and per-day forecasts (condition, high_c, notes).
    """
    forecast = _WEATHER.get(city.strip().lower())
    if forecast is None:
        return {
            "city": city,
            "forecast": [],
            "message": f"No forecast data available for '{city}' yet.",
        }
    if days:
        forecast = forecast[:days]
    return {"city": city, "forecast": forecast}


# ── Mock hotel data ─────────────────────────────────────────────────────────
# budget_category: "budget" | "midrange" | "premium"
_HOTELS: dict[str, list[dict]] = {
    "bangalore": [
        {"name": "The Stay Inn Indiranagar", "category": "Guest house", "budget_category": "budget",
         "price_inr": 1800, "neighbourhood": "Indiranagar", "rating": 3.9},
        {"name": "Zostel Bengaluru", "category": "Hostel / boutique", "budget_category": "budget",
         "price_inr": 2200, "neighbourhood": "Indiranagar", "rating": 4.1},
        {"name": "Treebo Trend Central", "category": "Business hotel", "budget_category": "midrange",
         "price_inr": 3800, "neighbourhood": "Indiranagar", "rating": 4.0},
        {"name": "Lemon Tree Hotel Whitefield", "category": "Business hotel", "budget_category": "midrange",
         "price_inr": 5500, "neighbourhood": "Near Indiranagar", "rating": 4.2},
        {"name": "The Paul Bangalore", "category": "Boutique hotel", "budget_category": "premium",
         "price_inr": 9500, "neighbourhood": "Near Indiranagar (UB City)", "rating": 4.6},
        {"name": "Marriott Hotel Whitefield", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 14000, "neighbourhood": "Near Indiranagar", "rating": 4.5},
    ],
    "tokyo": [
        {"name": "Khaosan Tokyo Kabuki (Capsule)", "category": "Capsule hotel", "budget_category": "budget",
         "price_inr": 2500, "neighbourhood": "Asakusa (near Shibuya by metro)", "rating": 4.0},
        {"name": "Shibuya Stream Excel Hotel Tokyu", "category": "Business hotel", "budget_category": "midrange",
         "price_inr": 8500, "neighbourhood": "Shibuya", "rating": 4.3},
        {"name": "Cerulean Tower Tokyu Hotel", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 22000, "neighbourhood": "Shibuya", "rating": 4.6},
    ],
    "goa": [
        {"name": "Zostel Goa", "category": "Hostel", "budget_category": "budget",
         "price_inr": 800, "neighbourhood": "Baga Beach area", "rating": 4.2},
        {"name": "Hotel Golden Eye", "category": "Beach guesthouse", "budget_category": "budget",
         "price_inr": 1500, "neighbourhood": "Baga Beach", "rating": 3.8},
        {"name": "Acron Waterfront Resort", "category": "Resort", "budget_category": "midrange",
         "price_inr": 5000, "neighbourhood": "Baga", "rating": 4.3},
        {"name": "Taj Exotica Resort & Spa", "category": "Luxury resort", "budget_category": "premium",
         "price_inr": 25000, "neighbourhood": "South Goa", "rating": 4.8},
    ],
    "rome": [
        {"name": "The RomeHello Hostel", "category": "Hostel", "budget_category": "budget",
         "price_inr": 1800, "neighbourhood": "Near Colosseum", "rating": 4.1},
        {"name": "Hotel Capo d'Africa", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 9000, "neighbourhood": "Colosseum area", "rating": 4.4},
        {"name": "Palazzo Manfredi", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 35000, "neighbourhood": "Directly facing Colosseum", "rating": 4.9},
    ],
    "paris": [
        {"name": "Generator Paris", "category": "Design hostel", "budget_category": "budget",
         "price_inr": 3500, "neighbourhood": "10th arrondissement", "rating": 4.0},
        {"name": "Hotel du Champ de Mars", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 10000, "neighbourhood": "Near Eiffel Tower", "rating": 4.5},
        {"name": "Le Meurice", "category": "Palace hotel", "budget_category": "premium",
         "price_inr": 65000, "neighbourhood": "1st arrondissement", "rating": 4.9},
    ],
    "amsterdam": [
        {"name": "ClinkNOORD Hostel", "category": "Hostel", "budget_category": "budget",
         "price_inr": 2800, "neighbourhood": "Noord (5 min by ferry)", "rating": 4.1},
        {"name": "Hotel V Nesplein", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 11000, "neighbourhood": "City centre", "rating": 4.4},
        {"name": "Conservatorium Hotel", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 40000, "neighbourhood": "Museum Quarter", "rating": 4.8},
    ],
    "berlin": [
        {"name": "Pfefferbett Hostel", "category": "Hostel", "budget_category": "budget",
         "price_inr": 2000, "neighbourhood": "Prenzlauer Berg", "rating": 4.2},
        {"name": "Michelberger Hotel", "category": "Design hotel", "budget_category": "midrange",
         "price_inr": 9500, "neighbourhood": "Friedrichshain (East Side Gallery area)", "rating": 4.5},
        {"name": "Hotel Adlon Kempinski", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 55000, "neighbourhood": "Brandenburg Gate", "rating": 4.7},
    ],
}


def search_hotels(
    city: str,
    budget_category: str = "",
    nights: int = 2,
) -> dict:
    """Search for hotels in a city, optionally filtered by budget tier.

    Args:
        city: City name, e.g. "Bangalore" or "Tokyo".
        budget_category: Optional filter - "budget", "midrange", or "premium".
            If empty, all tiers are returned so the traveller can compare.
        nights: Length of stay in nights (used for cost estimates). Default 2.

    Returns:
        Dict with city, nights, applied filter, and a list of hotels
        (name, category, budget_category, price per night in INR, neighbourhood,
        rating). Returns an error dict if the hotel search service is
        unavailable (set SIMULATE_HOTEL_ERROR=1 to trigger this).
    """
    if os.environ.get("SIMULATE_HOTEL_ERROR") == "1":
        return {
            "error": (
                "Hotel search service is temporarily unavailable. "
                "Please try again in a few minutes or adjust your dates."
            ),
            "city": city,
        }

    hotels = _HOTELS.get(city.strip().lower(), [])
    if budget_category:
        hotels = [h for h in hotels if h["budget_category"] == budget_category.strip().lower()]

    return {
        "city": city,
        "nights": nights,
        "filter": budget_category or "all tiers",
        "hotels": hotels,
        "found": len(hotels) > 0,
    }
