"""Operational commands for BizAssist AI.

Run ``python manage.py prewarm-translations`` during deployment (or after
changing the UI catalogue).  It is deliberately separate from Flask startup:
web requests only read the durable SQLite cache.
"""
import argparse

from app import app
from services.language_manager import SUPPORTED_LANGUAGES, normalize_language_code


def prewarm(language=None):
    service = app.extensions["translation"]
    languages = [normalize_language_code(language)] if language else SUPPORTED_LANGUAGES
    for code in languages:
        if code == "en":
            continue
        result = service.prewarm_language(code)
        print(f"{code}: {result['cached']}/{result['total']} cached")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prewarm-translations"])
    parser.add_argument("--language", choices=SUPPORTED_LANGUAGES)
    args = parser.parse_args()
    prewarm(args.language)
