#!/usr/bin/env python
"""Pre-warm translation cache for all supported languages.

Run this script after setting up NVIDIA_NIM_API_KEY to translate all UI strings
for all supported languages. This ensures sub-second page load times.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.app_services import init_services, get_translation
from services.config import load_flask_config
from services.language_manager import SUPPORTED_LANGUAGES
from services.ui_catalog import all_ui_strings


def prewarm_all_languages():
    """Pre-warm translations for all supported languages."""
    print("Starting translation prewarming...")
    print(f"Supported languages: {list(SUPPORTED_LANGUAGES.keys())}")
    
    # Create a minimal Flask app for context
    from flask import Flask
    app = Flask(__name__)
    app.config.update(load_flask_config())
    
    # Initialize services
    init_services(app)
    
    # Get all UI strings
    ui_strings = all_ui_strings()
    print(f"Total UI strings to translate: {len(ui_strings)}")
    
    translation_service = get_translation()
    
    # Check if API key is available
    if not translation_service.gemma.is_ready():
        print("WARNING: NVIDIA_NIM_API_KEY is not configured.")
        print("Translations will remain in English until API key is set.")
        print("Please set NVIDIA_NIM_API_KEY in .env file and run this script again.")
        return
    
    # Pre-warm each language
    for code, name in SUPPORTED_LANGUAGES.items():
        if code == "en":
            print(f"Skipping {name} (en) - source language")
            continue
            
        print(f"\nPre-warming {name} ({code})...")
        result = translation_service.prewarm_language(code)
        print(f"  Cached: {result['cached']}/{result['total']}")
        print(f"  Translated: {result['translated']}")
    
    print("\n✓ Translation prewarming complete!")
    print("All pages will now load in under 1 second for all languages.")


if __name__ == "__main__":
    prewarm_all_languages()
