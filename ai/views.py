from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from labs.serializers import LabSerializer  # we'll create this next
from .llm_client import OllamaClient, OllamaError
from .services import LabGenerator, SOCAgent


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def ai_status(request):
    """GET /api/ai/status/ — Check that Ollama is reachable."""
    client = OllamaClient()
    available = client.is_available()
    return Response({
        "ollama_available": available,
        "model": client.model,
        "base_url": client.base_url,
    }, status=status.HTTP_200_OK if available else status.HTTP_503_SERVICE_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Lab generation
# ---------------------------------------------------------------------------

def _is_trainer_or_admin(user):
    return user.is_authenticated and user.role in ('TRAINER', 'ADMIN')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_lab(request):
    """
    POST /api/ai/generate-lab/
    Body: {
        "topic": "SQL Injection for beginners",
        "difficulty": "EASY",           # optional
        "audience": "...",              # optional
        "constraints": "...",           # optional
        "save": true                    # optional — save as DRAFT lab
    }

    Only TRAINER or ADMIN can call this.
    """
    if not _is_trainer_or_admin(request.user):
        return Response(
            {"detail": "Action réservée aux formateurs et administrateurs."},
            status=status.HTTP_403_FORBIDDEN,
        )

    topic = (request.data.get('topic') or '').strip()
    if not topic:
        return Response(
            {"detail": "Le champ 'topic' est requis."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    difficulty = (request.data.get('difficulty') or 'EASY').upper()
    audience = request.data.get('audience') or 'étudiants débutants'
    constraints = request.data.get('constraints') or 'aucune'
    save = bool(request.data.get('save', False))

    generator = LabGenerator()

    try:
        if save:
            lab = generator.generate_and_save(
                topic=topic,
                created_by=request.user,
                difficulty=difficulty,
                audience=audience,
                constraints=constraints,
            )
            return Response(LabSerializer(lab).data, status=status.HTTP_201_CREATED)
        else:
            data = generator.generate(
                topic=topic,
                difficulty=difficulty,
                audience=audience,
                constraints=constraints,
            )
            return Response(data, status=status.HTTP_200_OK)

    except OllamaError as e:
        return Response(
            {"detail": str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ---------------------------------------------------------------------------
# SOC agent
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_alert(request):
    """
    POST /api/ai/analyze-alert/
    Body: {
        "alert_type": "Multiple failed logins",
        "initial_severity": "MEDIUM",
        "source": "185.220.101.42",
        "target": "WebServer01",
        "events": ["...", "..."]
    }
    Only TRAINER or ADMIN can call this.
    """
    if not _is_trainer_or_admin(request.user):
        return Response(
            {"detail": "Action réservée aux formateurs et administrateurs."},
            status=status.HTTP_403_FORBIDDEN,
        )

    required = ['alert_type', 'source', 'target']
    missing = [k for k in required if not request.data.get(k)]
    if missing:
        return Response(
            {"detail": f"Champs requis manquants : {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    agent = SOCAgent()
    try:
        result = agent.analyze(
            alert_type=request.data['alert_type'],
            initial_severity=request.data.get('initial_severity', 'MEDIUM'),
            source=request.data['source'],
            target=request.data['target'],
            events=request.data.get('events', []),
        )
        return Response(result, status=status.HTTP_200_OK)
    except OllamaError as e:
        return Response(
            {"detail": str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )