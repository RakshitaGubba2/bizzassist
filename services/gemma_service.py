"""NVIDIA NIM OpenAI-compatible client for BizzAssist."""
import json
import logging
import os
import time

from flask import current_app, has_app_context
from openai import APIConnectionError, APITimeoutError, OpenAI

logger = logging.getLogger(__name__)
from .config import DEFAULT_MODEL, NVIDIA_NIM_BASE_URL

NIM_BASE_URL = NVIDIA_NIM_BASE_URL


class GemmaService:
    def __init__(self, api_key=None, model_name=None):
        # In Flask requests, every Gemma call uses the application's single
        # NVIDIA NIM configuration. Environment values are only a standalone
        # fallback for scripts that instantiate this service outside Flask.
        if has_app_context():
            configured_key = current_app.config["NVIDIA_NIM_API_KEY"]
            configured_model = current_app.config["NVIDIA_NIM_MODEL"]
        else:
            configured_key = os.environ.get("NVIDIA_NIM_API_KEY", "")
            configured_model = os.environ.get("NVIDIA_NIM_MODEL", DEFAULT_MODEL)
        self.api_key = (api_key if api_key is not None else configured_key).strip()
        self.model_name = (model_name if model_name is not None else configured_model).strip()
        self.client = OpenAI(api_key=self.api_key, base_url=NIM_BASE_URL, timeout=20.0, max_retries=2) if self.api_key else None
        logger.info("NVIDIA NIM API key %s; model=%s", "loaded" if self.api_key else "missing", self.model_name)

    @staticmethod
    def _error_message(exc):
        status = getattr(exc, "status_code", None)
        body = getattr(exc, "body", None)
        detail = ""
        if isinstance(body, dict):
            error = body.get("error", body)
            detail = str(error.get("message", "")) if isinstance(error, dict) else str(error)
        detail = detail or str(exc)
        lower = detail.lower()
        if status in (401, 403) or "unauthorized" in lower or "invalid api key" in lower:
            return "Unauthorized: Invalid API Key"
        if status == 429 or "quota" in lower or "rate limit" in lower:
            return "Quota exceeded: " + detail
        if status == 404 or ("model" in lower and ("not found" in lower or "unavailable" in lower)):
            return "Model unavailable: " + detail
        if isinstance(exc, APITimeoutError) or "timeout" in lower:
            return "Network timeout: " + detail
        if isinstance(exc, APIConnectionError):
            return "Network error: " + detail
        return detail

    def is_ready(self):
        return self.client is not None

    def test_connection(self):
        if not self.client:
            return False, 0, self.model_name, "API key is missing"
        start = time.perf_counter()
        try:
            reply = self.client.chat.completions.create(model=self.model_name, messages=[{"role": "user", "content": "Reply with OK"}], temperature=0, max_tokens=10)
            latency = int((time.perf_counter() - start) * 1000)
            content = (reply.choices[0].message.content or "").strip()
            if content.lower().startswith("ok"):
                logger.info("NVIDIA NIM connected; model=%s latency_ms=%s", self.model_name, latency)
                return True, latency, self.model_name, "Connected"
            return False, latency, self.model_name, "Unexpected model response: " + content[:200]
        except Exception as exc:
            logger.exception("NVIDIA NIM connection test failed")
            return False, int((time.perf_counter() - start) * 1000), self.model_name, self._error_message(exc)

    def generate_text(self, prompt, max_output_tokens=512, request_timeout=None):
        if not self.client:
            raise RuntimeError("NVIDIA NIM API key is missing")
        start = time.perf_counter()
        try:
            logger.debug("NVIDIA prompt sent; model=%s prompt=%s", self.model_name, prompt)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_output_tokens,
                timeout=request_timeout,
            )
            text = (response.choices[0].message.content or "").strip()
            logger.debug("NVIDIA response received; latency_ms=%s response=%s", int((time.perf_counter() - start) * 1000), text)
            return text
        except Exception as exc:
            logger.exception("NVIDIA NIM generation failed")
            raise RuntimeError(self._error_message(exc)) from exc

    def generate_json(self, prompt, max_output_tokens=512):
        try:
            return self._extract_json(self.generate_text(prompt, max_output_tokens))
        except ValueError:
            return None

    @staticmethod
    def _extract_json(text):
        first, last = text.find("{"), text.rfind("}")
        if first < 0 or last < first:
            raise ValueError("No JSON object found")
        return json.loads(text[first:last + 1])
