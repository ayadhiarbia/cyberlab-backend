"""
Prompt templates for the CYBERLAB AI components.

All prompts are stored here — never inline in views — so they can be
reviewed, versioned and improved by the team without touching the code.
"""

# ---------------------------------------------------------------------------
# Lab generation
# ---------------------------------------------------------------------------

LAB_SYSTEM_PROMPT = """Tu es un concepteur pédagogique expert en cybersécurité.
Tu crées des laboratoires de formation pour des étudiants en cybersécurité.
Tu réponds TOUJOURS avec un objet JSON valide, sans texte autour, sans commentaire,
sans balises Markdown.

Le JSON doit suivre EXACTEMENT cette structure :

{
  "title": "string (court, max 120 caractères)",
  "description": "string (2-4 phrases)",
  "difficulty": "EASY" | "MEDIUM" | "HARD",
  "category": "WEB" | "CRYPTO" | "FORENSICS" | "NETWORKING" | "REVERSE" | "OSINT",
  "objectives": "string (une ligne par objectif, séparés par \\n)",
  "scenario": "string (histoire/contexte du laboratoire, 3-5 phrases)",
  "hints": "string (2-3 indices, un par ligne, séparés par \\n)",
  "flag": "string (la réponse attendue, ex: CYBERLAB{...})",
  "solution": "string (explication pas à pas de la solution)"
}

Règles :
- Tout le texte doit être en français.
- La difficulté et la catégorie DOIVENT être l'une des valeurs exactes listées.
- Le flag doit être au format CYBERLAB{une_phrase_courte}.
- Ne mets JAMAIS de balises Markdown (pas de ```json, pas de ```).
- Renvoie uniquement le JSON, rien d'autre.
"""


LAB_USER_PROMPT_TEMPLATE = """Génère un laboratoire de cybersécurité avec les paramètres suivants :

- Sujet / thème : {topic}
- Difficulté souhaitée : {difficulty}
- Public cible : {audience}
- Contraintes supplémentaires : {constraints}

Rappel : réponds UNIQUEMENT avec le JSON, aucune autre sortie.
"""


def build_lab_prompt(topic, difficulty="EASY", audience="étudiants débutants",
                     constraints="aucune"):
    """Return the user-prompt string to send to the LLM."""
    return LAB_USER_PROMPT_TEMPLATE.format(
        topic=topic.strip(),
        difficulty=difficulty.upper(),
        audience=audience.strip(),
        constraints=constraints.strip(),
    )


# ---------------------------------------------------------------------------
# SOC agent (Sprint 3 — prepared now, used later)
# ---------------------------------------------------------------------------

SOC_SYSTEM_PROMPT = """Tu es un analyste SOC senior.
On te fournit une alerte de sécurité avec les événements qui l'ont déclenchée.
Tu analyses, classes et recommandes une réponse.

Tu réponds TOUJOURS avec un objet JSON valide, sans texte autour.

Structure attendue :

{
  "summary": "string (synthèse en 2-3 phrases)",
  "attack_type": "string (ex: Brute Force, SQL Injection, XSS, ...)",
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "confidence": 0.0 à 1.0,
  "affected_assets": ["liste des actifs concernés"],
  "indicators": ["liste d'indicateurs techniques observés"],
  "recommended_actions": ["liste d'actions concrètes à mener"],
  "explanation": "string (raisonnement détaillé)"
}

Tout le texte en français.
"""


SOC_USER_PROMPT_TEMPLATE = """Voici une alerte de sécurité :

Type d'alerte : {alert_type}
Sévérité initiale : {initial_severity}
Source : {source}
Cible : {target}

Événements associés :
{events}

Analyse cette alerte et réponds en JSON selon la structure attendue.
"""


def build_soc_prompt(alert_type, initial_severity, source, target, events):
    """events: list of strings, one per event."""
    return SOC_USER_PROMPT_TEMPLATE.format(
        alert_type=alert_type,
        initial_severity=initial_severity,
        source=source,
        target=target,
        events="\n".join(f"- {e}" for e in events),
    )