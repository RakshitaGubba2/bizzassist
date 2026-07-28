"""Server-side transcription for MediaRecorder WebM uploads."""
import logging
import os
import shutil
import subprocess
import tempfile

from .language_manager import VOICE_LOCALES, normalize_language_code

logger = logging.getLogger(__name__)


class SpeechTranscriptionError(RuntimeError):
    """Raised when uploaded speech cannot be converted or transcribed."""


def _ffmpeg_executable():
    configured = os.environ.get("SPEECH_FFMPEG_PATH", "").strip()
    if configured:
        return configured
    system_binary = shutil.which("ffmpeg")
    if system_binary:
        return system_binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise SpeechTranscriptionError(
            "Audio decoding is unavailable. Install the project requirements or set SPEECH_FFMPEG_PATH."
        ) from exc


def transcribe_audio_bytes(audio_bytes, language=None, mime_type="audio/webm"):
    """Convert a browser recording to WAV and transcribe it using the selected locale.

    MediaRecorder produces WebM/Opus in Chrome and Edge; SpeechRecognition's
    AudioFile reader only accepts PCM formats, so decoding must happen first.
    """
    if not audio_bytes:
        raise SpeechTranscriptionError("No audio was received.")

    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise SpeechTranscriptionError("SpeechRecognition is not installed. Run pip install -r requirements.txt.") from exc

    suffix = ".webm" if "webm" in (mime_type or "").lower() else ".audio"
    input_path = output_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as source_file:
            source_file.write(audio_bytes)
            input_path = source_file.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output_file:
            output_path = output_file.name

        command = [_ffmpeg_executable(), "-y", "-i", input_path, "-ac", "1", "-ar", "16000", output_path]
        conversion = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if conversion.returncode != 0:
            logger.error("Audio conversion failed: %s", conversion.stderr[-500:])
            raise SpeechTranscriptionError("The recorded audio could not be decoded.")
        logger.info("Audio converted to WAV: source_bytes=%d wav_bytes=%d", len(audio_bytes), os.path.getsize(output_path))

        selected = normalize_language_code(language)
        locales = [VOICE_LOCALES.get(selected, VOICE_LOCALES["en"])]
        locales.extend(locale for locale in VOICE_LOCALES.values() if locale not in locales)
        recognizer = sr.Recognizer()
        with sr.AudioFile(output_path) as source:
            audio_data = recognizer.record(source)
        logger.info("Transcribing audio: bytes=%d selected_locale=%s", len(audio_bytes), locales[0])
        transcription_errors = []
        for locale in locales:
            try:
                result = recognizer.recognize_google(audio_data, language=locale, show_all=True)
                alternatives = result.get("alternative", []) if isinstance(result, dict) else []
                transcript = next((str(item.get("transcript", "")).strip() for item in alternatives if item.get("transcript")), "")
                if transcript:
                    logger.info("Transcription completed: locale=%s transcript=%s", locale, transcript[:200])
                    return transcript
                transcription_errors.append(f"{locale}: no speech result")
            except Exception as exc:
                logger.warning("Transcription attempt failed: locale=%s error=%r", locale, exc)
                transcription_errors.append(f"{locale}: {exc}")
        raise SpeechTranscriptionError(
            "No speech could be transcribed. Tried supported Indian locales. Details: "
            + "; ".join(transcription_errors[:3])
        )
    except SpeechTranscriptionError:
        raise
    except subprocess.TimeoutExpired as exc:
        raise SpeechTranscriptionError("Audio conversion timed out.") from exc
    except Exception as exc:
        logger.exception("Speech transcription failed")
        raise SpeechTranscriptionError("Speech could not be transcribed. Please try again or type your question.") from exc
    finally:
        for path in (input_path, output_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
