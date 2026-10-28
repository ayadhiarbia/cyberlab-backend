"""
Thin HTTP wrapper around a local Ollama server.

Ollama exposes a simple REST API at http://localhost:11434.
We use /api/generate for one-shot prompts and /api/chat if we ever need
multi-turn conversations. Everything runs on the local machine — no data
ever leaves the laptop.
"""

import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an invalid response."""
    pass


class OllamaClient:
    """Minimal client for a local Ollama instance."""

    def __init__(self, base_url=None, model=None, timeout=None):
        self.base_url = (base_url or getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')).rstrip('/')
        self.model = model or getattr(settings, 'OLLAMA_MODEL', 'mistral')
        self.timeout = timeout or getattr(settings, 'OLLAMA_TIMEOUT', 120)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self):
        """Quick health check — used by the /api/ai/health/ endpoint."""
        try:
            r = requests.get(self.base_url, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt, system=None, temperature=0.4, max_tokens=None):
        """
        Send a single prompt to Ollama and return the model's text answer.

        :param prompt: user message (str)
        :param system: optional system prompt (str)
        :param temperature: 0.0 = deterministic, 1.0 = creative
        :param max_tokens: optional cap on output length
        :return: text (str)
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError:
            raise OllamaError(
                "Impossible de joindre Ollama. Vérifiez qu'Ollama est en cours d'exécution "
                "sur http://localhost:11434."
            )
        except requests.exceptions.Timeout:
            raise OllamaError(
                f"Ollama n'a pas répondu dans les {self.timeout} secondes."
            )

        if response.status_code != 200:
            raise OllamaError(
                f"Ollama a renvoyé une erreur {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError:
            raise OllamaError("Réponse d'Ollama invalide (JSON attendu).")

        text = data.get("response", "").strip()
        if not text:
            raise OllamaError("Ollama a renvoyé une réponse vide.")

        return text

    def generate_json(self, prompt, system=None, temperature=0.2, max_tokens=None):
        """
        Same as generate(), but expects the model to output strict JSON.
        Parses it and returns a Python dict.

        Handles the common case where the model wraps JSON in ```json ... ```
        markdown fences even though we asked it not to.
        """
        raw = self.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        cleaned = raw.strip()

        # Strip markdown fences if present
        if cleaned.startswith("```"):
            # remove first line (``` or ```json)
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1:]
            # remove trailing ```
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Find the outermost JSON object if the model added prose around it
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Ollama returned invalid JSON:\n%s", raw)
            raise OllamaError(f"Le modèle n'a pas renvoyé un JSON valide : {e}")