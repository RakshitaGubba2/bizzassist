import os
import tempfile

from .language_manager import VOICE_LOCALES


def transcribe_audio_bytes(audio_bytes, language=None):
    if not audio_bytes:
        return ""

    try:
        import speech_recognition as sr
    except ImportError:
        return ""

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio_data = recognizer.record(source)
        # Google Web Speech needs a locale hint.  For uploaded audio there is
        # no trustworthy browser locale, so probe all supported locales and
        # keep the highest-confidence transcript.  A selected input locale,
        # when supplied, is tried first.
        locales = [language] if language else []
        locales.extend(locale for locale in VOICE_LOCALES.values() if locale not in locales)
        candidates = []
        for locale in locales:
            try:
                result = recognizer.recognize_google(audio_data, language=locale, show_all=True)
                for alternative in (result.get("alternative", []) if isinstance(result, dict) else []):
                    transcript = str(alternative.get("transcript", "")).strip()
                    if transcript:
                        candidates.append((float(alternative.get("confidence", 0)), transcript))
            except Exception:
                continue
        return max(candidates, default=(0, ""), key=lambda item: item[0])[1]
    except Exception:
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
