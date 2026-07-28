"""Internationalization helpers for templates and routes."""
from flask import g, has_request_context, session

from .app_services import get_translation
from .language_manager import normalize_language_code
from .local_fallback_translations import get_local_fallback


def current_ui_language():
    if has_request_context():
        return normalize_language_code(session.get("language", "en"))
    return "en"


def current_reply_language():
    if has_request_context():
        return normalize_language_code(
            session.get("reply_language") or session.get("language", "en")
        )
    return "en"


def t(text):
    """Resolve one UI string from the durable cache without network I/O.

    UI rendering must never make an AI request.  Missing entries deliberately
    remain visible to maintenance tooling and are filled by the explicit
    prewarm job, not by an end-user page request.
    """
    text = str(text or "")
    language = current_ui_language()
    if not text or language == "en":
        return text
    cache = getattr(g, "_i18n_cache", None)
    if cache is None:
        cache = {}
        g._i18n_cache = cache
    if text in cache:
        return cache[text]
    translated = get_translation().cached_text(text, language)
    if translated == text:
        translated = get_local_fallback(language, text) or text
    cache[text] = translated
    return translated


def prewarm_language(language):
    return get_translation().prewarm_language(language)
