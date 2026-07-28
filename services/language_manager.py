"""Language and speech locale helpers for BizAssist AI."""
import re

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "हिन्दी",
    "te": "తెలుగు",
    "ta": "தமிழ்",
    "kn": "ಕನ್ನಡ",
    "ml": "മലയാളം",
    "mr": "मराठी",
    "bn": "বাংলা",
    "gu": "ગુજરાતી",
}

VOICE_LOCALES = {
    "en": "en-IN",
    "te": "te-IN",
    "hi": "hi-IN",
    "ta": "ta-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
}

DEFAULT_LANGUAGE = "en"

SCRIPT_RANGES = {
    "hi": ("\u0900", "\u097f"),
    "mr": ("\u0900", "\u097f"),
    "te": ("\u0c00", "\u0c7f"),
    "ta": ("\u0b80", "\u0bff"),
    "kn": ("\u0c80", "\u0cff"),
    "ml": ("\u0d00", "\u0d7f"),
    "bn": ("\u0980", "\u09ff"),
    "gu": ("\u0a80", "\u0aff"),
}


def normalize_language_code(language):
    """Return one supported code; never let a browser locale change the UI language."""
    if not language:
        return DEFAULT_LANGUAGE
    code = str(language).strip().lower().replace("_", "-")
    prefix = code.split("-", 1)[0]
    if prefix in SUPPORTED_LANGUAGES:
        return prefix
    for language_code, (first, last) in SCRIPT_RANGES.items():
        if any(first <= character <= last for character in code):
            return language_code
    return DEFAULT_LANGUAGE


def detect_language_from_text(text, fallback=DEFAULT_LANGUAGE):
    """Detect the dominant script/language of user input."""
    if not text or not str(text).strip():
        return normalize_language_code(fallback)
    sample = str(text)
    scores = {code: 0 for code in SUPPORTED_LANGUAGES}
    for character in sample:
        if character.isascii() and character.isalpha():
            scores["en"] += 1
            continue
        for language_code, (first, last) in SCRIPT_RANGES.items():
            if first <= character <= last:
                scores[language_code] += 1
                break
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        if re.search(r"[A-Za-z]", sample):
            return "en"
        return normalize_language_code(fallback)
    if best in ("hi", "mr") and scores["hi"] + scores["mr"] > 0:
        if scores["mr"] > scores["hi"]:
            return "mr"
        return "hi"
    return best


def detect_language(text, fallback=DEFAULT_LANGUAGE):
    return detect_language_from_text(text, fallback)


def resolve_user_language(text, request_obj=None):
    if request_obj is not None:
        selected = request_obj.form.get("language") or request_obj.headers.get("Accept-Language")
        if selected:
            return normalize_language_code(selected)
    return detect_language_from_text(text, DEFAULT_LANGUAGE)


def speech_language(language):
    return VOICE_LOCALES.get(normalize_language_code(language), VOICE_LOCALES[DEFAULT_LANGUAGE])
