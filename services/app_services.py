"""Singleton service registry — one GemmaService, one TranslationService."""
from flask import current_app, has_app_context

_gemma_service = None
_translation_service = None


def init_services(app):
    """Initialize shared services once at application startup."""
    global _gemma_service, _translation_service
    from .gemma_service import GemmaService
    from .translation_service import TranslationService

    _gemma_service = GemmaService(
        api_key=app.config["NVIDIA_NIM_API_KEY"],
        model_name=app.config["NVIDIA_NIM_MODEL"],
    )
    _translation_service = TranslationService(_gemma_service, db_path=app.config["DATABASE_PATH"])
    app.extensions["gemma"] = _gemma_service
    app.extensions["translation"] = _translation_service


def get_gemma():
    if has_app_context() and "gemma" in current_app.extensions:
        return current_app.extensions["gemma"]
    if _gemma_service is not None:
        return _gemma_service
    from .gemma_service import GemmaService
    return GemmaService()


def get_translation():
    if has_app_context() and "translation" in current_app.extensions:
        return current_app.extensions["translation"]
    if _translation_service is not None:
        return _translation_service
    from .translation_service import TranslationService
    # This fallback is only for command-line maintenance tools.  Flask itself
    # always owns the two registered singleton instances above.
    return TranslationService(get_gemma(), db_path=current_app.config["DATABASE_PATH"])
