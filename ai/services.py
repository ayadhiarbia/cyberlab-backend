"""
AI services for CYBERLAB.

Each service:
  1. Calls the local Ollama server (via ai.llm_client).
  2. Parses and validates the JSON answer.
  3. Optionally persists the result to the Django database.

Keeping the LLM calls and the DB writes inside a service (not in views)
keeps the views thin and makes the AI layer easy to test and reuse.
"""

import logging

from django.conf import settings

from labs.models import Lab

from .llm_client import OllamaClient, OllamaError
from .prompts import (
    LAB_SYSTEM_PROMPT,
    build_lab_prompt,
    SOC_SYSTEM_PROMPT,
    build_soc_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lab generator
# ---------------------------------------------------------------------------

class LabGenerator:
    """
    Generates a cybersecurity lab from a topic using a local LLM.

    Usage:
        gen = LabGenerator()
        lab = gen.generate_and_save(
            topic="SQL Injection for beginners",
            created_by=request.user,
            difficulty="EASY",
        )
    """

    # What we accept as valid from the LLM
    VALID_DIFFICULTIES = {'EASY', 'MEDIUM', 'HARD'}
    VALID_CATEGORIES = {'WEB', 'CRYPTO', 'FORENSICS', 'NETWORKING', 'REVERSE', 'OSINT'}

    # Required JSON keys
    REQUIRED_KEYS = {
        'title', 'description', 'difficulty', 'category',
        'objectives', 'scenario', 'hints', 'flag', 'solution',
    }

    def __init__(self, client=None):
        self.client = client or OllamaClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, topic, difficulty='EASY',
                 audience='étudiants débutants', constraints='aucune'):
        """
        Call the LLM and return a dict of lab fields (not saved).
        Raises OllamaError on any failure.
        """
        user_prompt = build_lab_prompt(
            topic=topic,
            difficulty=difficulty,
            audience=audience,
            constraints=constraints,
        )

        logger.info("Generating lab for topic=%r difficulty=%r", topic, difficulty)

        data = self.client.generate_json(
            prompt=user_prompt,
            system=LAB_SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=1500,
        )

        return self._clean_and_validate(data)

    def generate_and_save(self, topic, created_by,
                          difficulty='EASY',
                          audience='étudiants débutants',
                          constraints='aucune'):
        """
        Same as generate(), but also creates a Lab row (status DRAFT,
        source AI_GENERATED) and returns the Lab instance.
        """
        data = self.generate(
            topic=topic,
            difficulty=difficulty,
            audience=audience,
            constraints=constraints,
        )

        lab = Lab.objects.create(
            title=data['title'][:255],
            description=data['description'],
            difficulty=data['difficulty'],
            category=data['category'],
            objectives=data['objectives'],
            scenario=data['scenario'],
            hints=data['hints'],
            flag=data['flag'][:255],
            solution=data['solution'],
            status=Lab.Status.DRAFT,
            source=Lab.Source.AI_GENERATED,
            ai_prompt=topic,
            created_by=created_by,
        )
        logger.info("AI Lab #%s created: %s", lab.id, lab.title)
        return lab

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _clean_and_validate(self, data):
        """Normalise the LLM answer and enforce the expected schema."""
        if not isinstance(data, dict):
            raise OllamaError("Le modèle n'a pas renvoyé un objet JSON.")

        missing = self.REQUIRED_KEYS - set(data.keys())
        if missing:
            raise OllamaError(
                f"JSON incomplet, champs manquants : {', '.join(sorted(missing))}"
            )

        # Normalise enums
        difficulty = str(data.get('difficulty', 'EASY')).upper()
        if difficulty not in self.VALID_DIFFICULTIES:
            difficulty = 'EASY'

        category = str(data.get('category', 'WEB')).upper()
        if category not in self.VALID_CATEGORIES:
            category = 'WEB'

        # Convert lists to newline-joined strings if the model returned them
        def as_text(value):
            if isinstance(value, list):
                return '\n'.join(str(v) for v in value)
            return str(value or '').strip()

        return {
            'title': as_text(data['title']),
            'description': as_text(data['description']),
            'difficulty': difficulty,
            'category': category,
            'objectives': as_text(data['objectives']),
            'scenario': as_text(data['scenario']),
            'hints': as_text(data['hints']),
            'flag': as_text(data['flag']),
            'solution': as_text(data['solution']),
        }


# ---------------------------------------------------------------------------
# SOC agent (Sprint 3 — ready to be wired later)
# ---------------------------------------------------------------------------

class SOCAgent:
    """
    Analyses a security alert with the local LLM and returns structured
    recommendations. The Alert/Incident models will be added in Sprint 2/3,
    so this service currently returns a dict and does not persist anything.
    """

    def __init__(self, client=None):
        self.client = client or OllamaClient()

    def analyze(self, alert_type, initial_severity, source, target, events):
        """
        events: list[str]
        Returns a dict with summary, attack_type, severity, confidence,
        affected_assets, indicators, recommended_actions, explanation.
        """
        user_prompt = build_soc_prompt(
            alert_type=alert_type,
            initial_severity=initial_severity,
            source=source,
            target=target,
            events=events,
        )

        data = self.client.generate_json(
            prompt=user_prompt,
            system=SOC_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=1000,
        )

        # Light validation — we don't enforce every key yet
        if not isinstance(data, dict):
            raise OllamaError("Le modèle n'a pas renvoyé un objet JSON.")

        return data