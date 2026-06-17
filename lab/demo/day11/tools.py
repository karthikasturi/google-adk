"""
tools.py — Day 11: Voice TravelBot tools
=========================================
Extends Day 10 tools with destinations and bookings needed for the seven
voice-demo scenario groups.

Additions over Day 10:
  _BOOKINGS    — AB-137 (Goa hotel, Scenario 2A)
                 BCN-HOT-001 (Barcelona hotel, Scenario 7A)
  _HOTELS      — Barcelona (family options, Scenario 7B)
                 Zurich (Scenario 6A)
  _ATTRACTIONS — Barcelona (Scenario 7B), Zurich (Scenario 6A)
"""

import os

# ── Mock booking data ────────────────────────────────────────────────────────

_BOOKINGS: list[dict] = [
    # Flights ── carried over from Day 10
    {
        "booking_id": "BLR-DEL-123",
        "booking_type": "flight",
        "origin": "Bengaluru (BLR)",
        "destination": "Delhi (DEL)",
        "departure": "Tomorrow, 06:45",
        "flight_number": "TB-410",
        "status": "Confirmed",
    },
    {
        "booking_id": "DEL-SIN-202",
        "booking_type": "flight",
        "origin": "Delhi (DEL)",
        "destination": "Singapore (SIN)",
        "departure": "Tomorrow, 08:15",
        "arrival": "Tomorrow, 14:30 Singapore local time",
        "flight_number": "TB-303",
        "status": "Confirmed",
    },
    {
        "booking_id": "CHN-PAR-789",
        "booking_type": "flight",
        "origin": "Chennai (MAA)",
        "destination": "Paris (CDG)",
        "departure": "Next week, Tuesday 23:55",
        "flight_number": "TB-772",
        "status": "Confirmed",
    },
    {
        "booking_id": "BOM-DXB-552",
        "booking_type": "flight",
        "origin": "Mumbai (BOM)",
        "destination": "Dubai (DXB)",
        "departure": "Tomorrow, 21:10",
        "flight_number": "TB-512",
        "status": "Delayed",
        "delay_minutes": 150,
        "new_arrival_time": "Tuesday, 02:10 local time (was Monday, 23:40)",
    },
    {
        "booking_id": "BLR-LHR-456",
        "booking_type": "flight",
        "origin": "Bengaluru (BLR)",
        "destination": "London Heathrow (LHR)",
        "departure": "Next Friday, 02:20",
        "flight_number": "TB-940",
        "status": "Confirmed",
    },
    # Hotel bookings ── new in Day 11
    {
        "booking_id": "AB-137",
        "booking_type": "hotel",
        "property": "Acron Waterfront Resort",
        "destination": "Goa",
        "check_in": "This Friday, 14:00",
        "check_out": "Next Monday, 11:00",
        "nights": 3,
        "room_type": "Sea-view Deluxe",
        "status": "Confirmed",
    },
    {
        "booking_id": "BCN-HOT-001",
        "booking_type": "hotel",
        "property": "Hotel Arts Barcelona",
        "destination": "Barcelona",
        "check_in": "This Saturday, 15:00",
        "check_out": "Next Monday, 12:00",
        "nights": 2,
        "room_type": "Superior Sea View",
        "status": "Confirmed",
    },
]


def get_booking_status(
    booking_id: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
) -> dict:
    """Look up a flight or hotel booking by reference or route.

    Args:
        booking_id: Booking or confirmation reference, e.g. "AB-137". Optional.
        origin: Departure city or airport code for flight lookups. Optional.
        destination: Arrival city or destination. Optional.

    Returns:
        The matching booking record, or {"found": False, ...} if not found.
    """
    if not booking_id and not origin and not destination:
        return {
            "found": False,
            "message": (
                "I need a booking reference, or at least the origin or "
                "destination, to look this up."
            ),
        }

    for booking in _BOOKINGS:
        if booking_id and booking["booking_id"].upper() == booking_id.strip().upper():
            return {"found": True, **booking}

    if origin or destination:
        for booking in _BOOKINGS:
            btype = booking.get("booking_type", "flight")
            if btype == "hotel":
                dest_match = (
                    destination is None
                    or destination.strip().lower() in booking.get("destination", "").lower()
                )
                if dest_match:
                    return {"found": True, **booking}
            else:
                origin_match = (
                    origin is None
                    or origin.strip().lower() in booking.get("origin", "").lower()
                )
                dest_match = (
                    destination is None
                    or destination.strip().lower() in booking.get("destination", "").lower()
                )
                if origin_match and dest_match:
                    return {"found": True, **booking}

    return {
        "found": False,
        "booking_id": booking_id,
        "message": (
            "No booking found matching that reference or route. "
            "Double-check the reference (format: XXX-NNN) or the city names."
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
        {"name": "Jewel Changi Airport", "category": "Mall / attraction", "tags": ["family", "indoor", "near-airport"]},
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
    "barcelona": [
        {"name": "Sagrada Família", "category": "Landmark / church", "tags": ["iconic", "indoor", "family", "culture"]},
        {"name": "Park Güell", "category": "Park / art", "tags": ["outdoor", "family", "iconic", "art"]},
        {"name": "La Barceloneta Beach", "category": "Beach", "tags": ["beach", "outdoor", "family"]},
        {"name": "Gothic Quarter (Barri Gòtic)", "category": "Neighbourhood", "tags": ["history", "outdoor", "culture", "food"]},
        {"name": "Camp Nou stadium tour", "category": "Sports / museum", "tags": ["family", "indoor", "sports"]},
        {"name": "Montjuïc Castle & cable car", "category": "Landmark / view", "tags": ["outdoor", "family", "iconic"]},
    ],
    "zurich": [
        {"name": "Old Town (Altstadt)", "category": "Neighbourhood", "tags": ["history", "outdoor", "culture", "food"]},
        {"name": "Swiss National Museum", "category": "Museum", "tags": ["museum", "indoor", "history"]},
        {"name": "Lake Zurich promenade", "category": "Park / lakeside", "tags": ["outdoor", "family", "peaceful"]},
        {"name": "Uetliberg hill viewpoint", "category": "Nature / view", "tags": ["outdoor", "nature", "hiking"]},
        {"name": "Bahnhofstrasse shopping", "category": "Shopping", "tags": ["shopping", "indoor", "luxury"]},
    ],
}


def get_attractions(city: str, days: int | None = None, interests: str | None = None) -> dict:
    """List attractions and activities for a city, optionally filtered by interest.

    Args:
        city: City name, e.g. "Goa" or "Barcelona".
        days: Optional number of days the itinerary should cover.
        interests: Optional interest keyword, e.g. "family" or "museums".

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
        {"day": 1, "condition": "Thunderstorms", "high_c": 30, "notes": "Heavy afternoon downpours — better for indoor plans"},
        {"day": 2, "condition": "Sunny", "high_c": 32, "notes": "Clear and hot — good for outdoor activities"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 31, "notes": "Warm with light humidity"},
    ],
    "goa": [
        {"day": 1, "condition": "Sunny", "high_c": 33, "notes": "Perfect beach weather"},
        {"day": 2, "condition": "Sunny", "high_c": 34, "notes": "Ideal for water sports and markets"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 32, "notes": "Good for sightseeing"},
    ],
    "dubai": [
        {"day": 1, "condition": "Sunny", "high_c": 39, "notes": "Very hot — best for early-morning or indoor activities"},
        {"day": 2, "condition": "Sandstorm", "high_c": 36, "notes": "Low visibility — avoid outdoor desert activities"},
        {"day": 3, "condition": "Sunny", "high_c": 37, "notes": "Clear skies, still very hot"},
    ],
    "paris": [
        {"day": 1, "condition": "Rainy", "high_c": 14, "notes": "Steady rain — indoor activities recommended"},
        {"day": 2, "condition": "Cloudy", "high_c": 16, "notes": "Dry but overcast — ok for walking"},
        {"day": 3, "condition": "Sunny", "high_c": 18, "notes": "Clear skies — best day for Eiffel Tower"},
    ],
    "tokyo": [
        {"day": 1, "condition": "Sunny", "high_c": 22, "notes": "Crisp and clear — ideal for outdoor temples"},
        {"day": 2, "condition": "Rainy", "high_c": 18, "notes": "Rain in the afternoon — plan indoor activities"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 20, "notes": "Mild — good for Shibuya or Ueno"},
    ],
    "amsterdam": [
        {"day": 1, "condition": "Rainy", "high_c": 13, "notes": "Dutch drizzle — visit the museums"},
        {"day": 2, "condition": "Partly cloudy", "high_c": 15, "notes": "Dry intervals — good for a canal cruise"},
        {"day": 3, "condition": "Sunny", "high_c": 17, "notes": "Clear — best day for Vondelpark and outdoors"},
    ],
    "berlin": [
        {"day": 1, "condition": "Cloudy", "high_c": 16, "notes": "Overcast but dry — fine for walking"},
        {"day": 2, "condition": "Sunny", "high_c": 20, "notes": "Warm and clear — great for East Side Gallery"},
        {"day": 3, "condition": "Partly cloudy", "high_c": 18, "notes": "Light clouds — good for Tiergarten"},
    ],
    "barcelona": [
        {"day": 1, "condition": "Sunny", "high_c": 25, "notes": "Beautiful Mediterranean weather — ideal for Park Güell"},
        {"day": 2, "condition": "Partly cloudy", "high_c": 23, "notes": "Mild — good for the Gothic Quarter or beach"},
        {"day": 3, "condition": "Sunny", "high_c": 26, "notes": "Clear and warm — perfect for La Barceloneta"},
    ],
    "zurich": [
        {"day": 1, "condition": "Partly cloudy", "high_c": 17, "notes": "Pleasant — good for Old Town walk"},
        {"day": 2, "condition": "Sunny", "high_c": 19, "notes": "Clear — best for Lake Zurich promenade"},
        {"day": 3, "condition": "Rainy", "high_c": 14, "notes": "Rainy afternoon — visit the Swiss National Museum"},
    ],
}


def get_weather_forecast(city: str, days: int | None = None) -> dict:
    """Get a short-range daily weather forecast for a city.

    Args:
        city: City name, e.g. "Goa" or "Zurich".
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


# ── Mock hotel data ──────────────────────────────────────────────────────────

_HOTELS: dict[str, list[dict]] = {
    "bangalore": [
        {"name": "The Stay Inn Indiranagar", "category": "Guest house", "budget_category": "budget",
         "price_inr": 1800, "neighbourhood": "Indiranagar", "rating": 3.9, "family_friendly": False},
        {"name": "Zostel Bengaluru", "category": "Hostel / boutique", "budget_category": "budget",
         "price_inr": 2200, "neighbourhood": "Indiranagar", "rating": 4.1, "family_friendly": False},
        {"name": "Treebo Trend Central", "category": "Business hotel", "budget_category": "midrange",
         "price_inr": 3800, "neighbourhood": "Indiranagar", "rating": 4.0, "family_friendly": True},
        {"name": "Lemon Tree Hotel Whitefield", "category": "Business hotel", "budget_category": "midrange",
         "price_inr": 5500, "neighbourhood": "Near Indiranagar", "rating": 4.2, "family_friendly": True},
        {"name": "The Paul Bangalore", "category": "Boutique hotel", "budget_category": "premium",
         "price_inr": 9500, "neighbourhood": "Near Indiranagar (UB City)", "rating": 4.6, "family_friendly": True},
        {"name": "Marriott Hotel Whitefield", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 14000, "neighbourhood": "Near Indiranagar", "rating": 4.5, "family_friendly": True},
    ],
    "tokyo": [
        {"name": "Khaosan Tokyo Kabuki (Capsule)", "category": "Capsule hotel", "budget_category": "budget",
         "price_inr": 2500, "neighbourhood": "Asakusa", "rating": 4.0, "family_friendly": False},
        {"name": "Shibuya Stream Excel Hotel Tokyu", "category": "Business hotel", "budget_category": "midrange",
         "price_inr": 8500, "neighbourhood": "Shibuya", "rating": 4.3, "family_friendly": True},
        {"name": "Cerulean Tower Tokyu Hotel", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 22000, "neighbourhood": "Shibuya", "rating": 4.6, "family_friendly": True},
    ],
    "goa": [
        {"name": "Zostel Goa", "category": "Hostel", "budget_category": "budget",
         "price_inr": 800, "neighbourhood": "Baga Beach area", "rating": 4.2, "family_friendly": False},
        {"name": "Hotel Golden Eye", "category": "Beach guesthouse", "budget_category": "budget",
         "price_inr": 1500, "neighbourhood": "Baga Beach", "rating": 3.8, "family_friendly": True},
        {"name": "Acron Waterfront Resort", "category": "Resort", "budget_category": "midrange",
         "price_inr": 5000, "neighbourhood": "Baga", "rating": 4.3, "family_friendly": True},
        {"name": "Taj Exotica Resort & Spa", "category": "Luxury resort", "budget_category": "premium",
         "price_inr": 25000, "neighbourhood": "South Goa", "rating": 4.8, "family_friendly": True},
    ],
    "rome": [
        {"name": "The RomeHello Hostel", "category": "Hostel", "budget_category": "budget",
         "price_inr": 1800, "neighbourhood": "Near Colosseum", "rating": 4.1, "family_friendly": False},
        {"name": "Hotel Capo d'Africa", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 9000, "neighbourhood": "Colosseum area", "rating": 4.4, "family_friendly": True},
        {"name": "Palazzo Manfredi", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 35000, "neighbourhood": "Directly facing Colosseum", "rating": 4.9, "family_friendly": True},
    ],
    "paris": [
        {"name": "Generator Paris", "category": "Design hostel", "budget_category": "budget",
         "price_inr": 3500, "neighbourhood": "10th arrondissement", "rating": 4.0, "family_friendly": False},
        {"name": "Hotel du Champ de Mars", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 10000, "neighbourhood": "Near Eiffel Tower", "rating": 4.5, "family_friendly": True},
        {"name": "Le Meurice", "category": "Palace hotel", "budget_category": "premium",
         "price_inr": 65000, "neighbourhood": "1st arrondissement", "rating": 4.9, "family_friendly": True},
    ],
    "amsterdam": [
        {"name": "ClinkNOORD Hostel", "category": "Hostel", "budget_category": "budget",
         "price_inr": 2800, "neighbourhood": "Noord (5 min by ferry)", "rating": 4.1, "family_friendly": False},
        {"name": "Hotel V Nesplein", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 11000, "neighbourhood": "City centre", "rating": 4.4, "family_friendly": True},
        {"name": "Conservatorium Hotel", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 40000, "neighbourhood": "Museum Quarter", "rating": 4.8, "family_friendly": True},
    ],
    "berlin": [
        {"name": "Pfefferbett Hostel", "category": "Hostel", "budget_category": "budget",
         "price_inr": 2000, "neighbourhood": "Prenzlauer Berg", "rating": 4.2, "family_friendly": False},
        {"name": "Michelberger Hotel", "category": "Design hotel", "budget_category": "midrange",
         "price_inr": 9500, "neighbourhood": "Friedrichshain (East Side Gallery area)", "rating": 4.5, "family_friendly": True},
        {"name": "Hotel Adlon Kempinski", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 55000, "neighbourhood": "Brandenburg Gate", "rating": 4.7, "family_friendly": True},
    ],
    "barcelona": [
        {"name": "Urban Youth Hostel Barcelona", "category": "Hostel", "budget_category": "budget",
         "price_inr": 2200, "neighbourhood": "Gothic Quarter", "rating": 4.0, "family_friendly": False},
        {"name": "Hotel Gaudí", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 8500, "neighbourhood": "Near Sagrada Família", "rating": 4.3, "family_friendly": True},
        {"name": "Hotel Casa Fuster", "category": "Modernista luxury hotel", "budget_category": "midrange",
         "price_inr": 12000, "neighbourhood": "Gràcia", "rating": 4.5, "family_friendly": True},
        {"name": "W Barcelona", "category": "Design hotel", "budget_category": "premium",
         "price_inr": 28000, "neighbourhood": "La Barceloneta beach", "rating": 4.6, "family_friendly": True},
        {"name": "Hotel Arts Barcelona", "category": "Luxury hotel", "budget_category": "premium",
         "price_inr": 35000, "neighbourhood": "Olympic Port / beach", "rating": 4.8, "family_friendly": True},
    ],
    "zurich": [
        {"name": "Youth Hostel Zurich", "category": "Hostel", "budget_category": "budget",
         "price_inr": 3200, "neighbourhood": "Wollishofen", "rating": 4.0, "family_friendly": True},
        {"name": "Hotel Kindli", "category": "Boutique hotel", "budget_category": "midrange",
         "price_inr": 16000, "neighbourhood": "Old Town (Altstadt)", "rating": 4.4, "family_friendly": True},
        {"name": "The Dolder Grand", "category": "Luxury resort hotel", "budget_category": "premium",
         "price_inr": 75000, "neighbourhood": "Zürichberg hill", "rating": 4.9, "family_friendly": True},
    ],
}


def search_hotels(
    city: str,
    budget_category: str = "",
    nights: int = 2,
    family_friendly: bool | None = None,
) -> dict:
    """Search for hotels in a city, optionally filtered by budget tier or family suitability.

    Args:
        city: City name, e.g. "Barcelona" or "Zurich".
        budget_category: Optional filter — "budget", "midrange", or "premium".
            Leave empty to return all tiers.
        nights: Length of stay in nights. Default 2.
        family_friendly: If True, return only family-suitable properties. Optional.

    Returns:
        Dict with city, nights, applied filters, and a list of hotels.
    """
    if os.environ.get("SIMULATE_HOTEL_ERROR") == "1":
        return {
            "error": (
                "Hotel search service is temporarily unavailable. "
                "Please try again in a few minutes."
            ),
            "city": city,
        }

    hotels = _HOTELS.get(city.strip().lower(), [])

    if budget_category:
        hotels = [h for h in hotels if h["budget_category"] == budget_category.strip().lower()]

    if family_friendly is True:
        hotels = [h for h in hotels if h.get("family_friendly")]

    return {
        "city": city,
        "nights": nights,
        "filter": budget_category or "all tiers",
        "family_friendly_filter": family_friendly,
        "hotels": hotels,
        "found": len(hotels) > 0,
    }
