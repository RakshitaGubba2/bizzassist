"""Server-side translation with SQLite cache — translate once, serve forever."""
import json
import logging
import re
import sqlite3
import threading

from .language_manager import SUPPORTED_LANGUAGES, normalize_language_code
from .local_fallback_translations import get_local_fallback
from .ui_catalog import all_ui_strings

logger = logging.getLogger(__name__)

SKIP_TAG_PATTERN = re.compile(
    r"<(script|style|noscript|code|pre)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
SKIP_CONTAINER_PATTERN = re.compile(
    r'<([a-zA-Z0-9]+)([^>]*\bdata-skip-translate="1"[^>]*)>.*?</\1>',
    re.IGNORECASE | re.DOTALL,
)
TEXT_NODE_PATTERN = re.compile(r">([^<>]+)<")
ATTR_PATTERN = re.compile(
    r'\b(placeholder|title|aria-label|alt|value)\s*=\s*"([^"]+)"',
    re.IGNORECASE,
)
JS_STRING_PATTERN = re.compile(r"(['\"])((?:\\.|(?!\1).)*)\1", re.DOTALL)
CONFIRM_PATTERN = re.compile(
    r"confirm\s*\(\s*'((?:\\'|[^'])*)'\s*\)",
    re.IGNORECASE,
)

_cache_lock = threading.Lock()


class TranslationService:
    def __init__(self, gemma_service, db_path="database.db"):
        self.gemma = gemma_service
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL").close()
        conn.execute("PRAGMA busy_timeout = 30000").close()
        return conn

    def _ensure_schema(self):
        with _cache_lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ui_translations (
                        language TEXT NOT NULL,
                        source_text TEXT NOT NULL,
                        translated_text TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        PRIMARY KEY (language, source_text)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ui_translations_lang ON ui_translations(language)"
                )
                conn.commit()
            finally:
                conn.close()

    def _load_cached(self, language, texts):
        if not texts:
            return {}
        language = normalize_language_code(language)
        placeholders = ",".join("?" for _ in texts)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT source_text, translated_text
                FROM ui_translations
                WHERE language = ? AND source_text IN ({placeholders})
                """,
                [language, *texts],
            ).fetchall()
            return {
                row["source_text"]: row["translated_text"]
                for row in rows
                if row["translated_text"] and row["translated_text"] != row["source_text"]
            }
        finally:
            conn.close()

    def _save_cache(self, language, mapping):
        if not mapping:
            return
        language = normalize_language_code(language)
        with _cache_lock:
            conn = self._connect()
            try:
                conn.executemany(
                    """
                    INSERT INTO ui_translations (language, source_text, translated_text)
                    VALUES (?, ?, ?)
                    ON CONFLICT(language, source_text) DO UPDATE SET
                        translated_text = excluded.translated_text,
                        updated_at = datetime('now')
                    """,
                    [(language, src, dst) for src, dst in mapping.items()],
                )
                conn.commit()
            finally:
                conn.close()

    def translate_texts(self, texts, target_language, batch_size=25):
        """Maintenance-only translation population API.

        It is intentionally never called from a request render path.  The
        database primary key makes repeated prewarm runs idempotent.
        """
        target_language = normalize_language_code(target_language)
        texts = list(dict.fromkeys(str(t).strip() for t in texts if isinstance(t, str) and str(t).strip()))
        if target_language == "en" or not texts:
            return {text: text for text in texts}

        cached = self._load_cached(target_language, texts)
        result = dict(cached)
        pending = [text for text in texts if text not in result]

        if pending and self.gemma.is_ready():
            for index in range(0, len(pending), batch_size):
                chunk = pending[index : index + batch_size]
                translated = self._translate_chunk_adaptive(chunk, target_language)
                valid = {
                    src: dst for src, dst in translated.items()
                    if dst and dst.strip() and dst != src
                }
                if valid:
                    self._save_cache(target_language, valid)
                    result.update(valid)
        elif pending:
            logger.warning("Gemma not ready; %d strings remain in English", len(pending))

        for text in texts:
            result.setdefault(text, text)
        return result

    def _translate_batch_with_gemma(self, texts, target_language):
        language_name = SUPPORTED_LANGUAGES.get(target_language, "English")
        payload = json.dumps(texts, ensure_ascii=False)
        prompt = (
            f"Translate each English UI phrase below into {language_name}. "
            "Return ONLY a valid JSON object mapping every original phrase to its translation. "
            "Keep numbers, currency symbols, punctuation, and placeholders unchanged. "
            "Use native script for the target language.\n\n"
            f"Phrases: {payload}"
        )
        try:
            # Translation population is an explicit maintenance operation,
            # not an interactive request.  It may use a longer network timeout
            # without affecting assistant-response latency.
            content = self.gemma.generate_text(
                prompt, max_output_tokens=4096, request_timeout=90.0
            )
            if not content:
                return {}
            parsed = self.gemma._extract_json(content)
            if not isinstance(parsed, dict):
                return {}
            return {
                text: str(parsed[text]).strip()
                for text in texts
                if isinstance(parsed.get(text), str) and parsed[text].strip()
            }
        except Exception:
            logger.exception("Gemma translation batch failed for %s", target_language)
            return {}

    def _translate_chunk_adaptive(self, texts, target_language):
        texts = list(texts)
        if not texts:
            return {}
        translated = self._translate_batch_with_gemma(texts, target_language)
        if translated or len(texts) == 1:
            return translated
        mid = max(1, len(texts) // 2)
        left = self._translate_chunk_adaptive(texts[:mid], target_language)
        right = self._translate_chunk_adaptive(texts[mid:], target_language)
        combined = dict(left)
        combined.update(right)
        return combined

    def prewarm_language(self, language):
        language = normalize_language_code(language)
        if language == "en":
            return {"language": language, "cached": len(all_ui_strings()), "translated": 0}
        strings = all_ui_strings()
        before = self._load_cached(language, strings)
        missing = [s for s in strings if s not in before]
        if missing and self.gemma.is_ready():
            # Larger maintenance batches keep the one-time catalogue build
            # efficient; user-facing requests never use this path.
            self.translate_texts(missing, language, batch_size=8)
        after = self._load_cached(language, strings)
        return {
            "language": language,
            "cached": len(after),
            "translated": len(after) - len(before),
            "total": len(strings),
        }

    def cached_texts(self, texts, language):
        """Return cache values only; this method never contacts NVIDIA."""
        language = normalize_language_code(language)
        texts = list(dict.fromkeys(str(text).strip() for text in texts if str(text).strip()))
        if language == "en":
            return {text: text for text in texts}
        result = {}
        unresolved = []
        for text in texts:
            fallback = get_local_fallback(language, text)
            if fallback:
                result[text] = fallback
            else:
                unresolved.append(text)
        if unresolved:
            cached = self._load_cached(language, unresolved)
            for text in unresolved:
                result[text] = cached.get(text, text)
        return result

    def cached_text(self, text, language):
        return self.cached_texts([text], language).get(str(text).strip(), str(text))

    def translate_html(self, html, language):
        """Backward-compatible name for the cache-only HTML localizer."""
        return self.translate_html_cached(html, language)

    def translate_html_cached(self, html, language):
        """Localize rendered markup using SQLite values already on disk.

        Scripts and styles are intentionally left untouched: translated
        JavaScript strings are supplied as server-rendered data where needed,
        and rewriting executable code is unsafe.  This parser is limited to
        text nodes and user-facing attributes and performs no network I/O.
        """
        language = normalize_language_code(language)
        if language == "en" or not html:
            return html
        protected = []

        def protect(match):
            protected.append(match.group(0))
            return f"__PROTECTED_{len(protected) - 1}__"

        working = SKIP_CONTAINER_PATTERN.sub(protect, html)
        working = SKIP_TAG_PATTERN.sub(protect, working)
        phrases = set()
        for match in TEXT_NODE_PATTERN.finditer(working):
            phrase = match.group(1).strip()
            if phrase and not phrase.startswith("__PROTECTED_"):
                phrases.add(phrase)
        for match in ATTR_PATTERN.finditer(working):
            phrase = match.group(2).strip()
            if phrase:
                phrases.add(phrase)
        for match in CONFIRM_PATTERN.finditer(html):
            phrases.add(match.group(1).replace("\\'", "'"))
        translations = self.cached_texts(phrases, language)

        def replace_text(match):
            inner = match.group(1)
            source = inner.strip()
            translated = translations.get(source, source)
            if not source or source.startswith("__PROTECTED_") or translated == source:
                return match.group(0)
            return ">" + inner.replace(source, translated, 1) + "<"

        working = TEXT_NODE_PATTERN.sub(replace_text, working)

        def replace_attr(match):
            attr, value = match.group(1), match.group(2)
            return f'{attr}="{translations.get(value.strip(), value)}"'

        working = ATTR_PATTERN.sub(replace_attr, working)
        for index, block in enumerate(protected):
            if block.lstrip().lower().startswith("<script"):
                def replace_js_string(match):
                    source = match.group(2)
                    translated = translations.get(source, source)
                    # json.dumps always returns a valid JavaScript string
                    # literal, including when a translation contains quotes.
                    return json.dumps(translated, ensure_ascii=False) if translated != source else match.group(0)

                block = JS_STRING_PATTERN.sub(replace_js_string, block)
            working = working.replace(f"__PROTECTED_{index}__", block)
        return working

    def translate_one(self, text, language):
        text = str(text or "").strip()
        if not text:
            return text
        return self.cached_text(text, language)
