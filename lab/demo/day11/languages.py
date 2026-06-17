"""
languages.py — Language registry for the Day 11 voice pipeline
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Language:
    key: str                 # short selector, e.g. "en"
    name: str                # human name, e.g. "English"
    whisper_code: str        # language hint sent to the STT model
    greeting: str            # spoken on startup
    sample_prompts: list[str] = field(default_factory=list)


LANGUAGES: dict[str, Language] = {
    "en": Language(
        key="en",
        name="English",
        whisper_code="en",
        greeting="Hello! I'm TravelBot. Ask me about a flight, a hotel, or a trip.",
        sample_prompts=[
            "Where is my flight from Mumbai to Dubai tomorrow?",
            "Check the status of booking AB-137 for my hotel in Goa.",
            "Plan a one-day Singapore itinerary near the airport.",
        ],
    ),
    "fr": Language(
        key="fr",
        name="French",
        whisper_code="fr",
        greeting="Bonjour ! Je suis TravelBot. Posez-moi une question sur un vol, un hôtel ou un voyage.",
        sample_prompts=[
            "Où est mon vol de Mumbai à Dubaï demain ?",
            "Vérifiez le statut de la réservation AB-137 pour mon hôtel à Goa.",
            "Proposez un itinéraire d'une journée à Barcelone pour une famille.",
        ],
    ),
    "hi": Language(
        key="hi",
        name="Hindi",
        whisper_code="hi",
        greeting="नमस्ते! मैं TravelBot हूँ। उड़ान, होटल या यात्रा के बारे में पूछें।",
        sample_prompts=[
            "कल मुंबई से दुबई की मेरी फ्लाइट कहाँ है?",
            "गोवा में मेरे होटल की बुकिंग AB-137 की स्थिति जांचें।",
        ],
    ),
}


def get_language(key: str) -> Language:
    key = (key or "en").strip().lower()
    if key not in LANGUAGES:
        valid = ", ".join(LANGUAGES)
        raise ValueError(f"Unknown language '{key}'. Choose one of: {valid}")
    return LANGUAGES[key]
