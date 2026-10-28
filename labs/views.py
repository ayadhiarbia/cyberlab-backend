from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Lab, LabSession, LabReview
from .serializers import (
    LabSerializer, LabListSerializer, LabSessionSerializer,
    SubmitFlagSerializer, LabReviewSerializer
)
from .permissions import IsTrainerOrAdmin, IsOwnerOrAdmin, CanViewLab


class LabViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for Labs, plus custom actions for the workflow.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return LabListSerializer
        return LabSerializer

    def get_queryset(self):
        user = self.request.user
        # Students only see PUBLISHED labs. Trainers/Admins see all.
        if user.role == 'STUDENT':
            return Lab.objects.filter(status=Lab.Status.PUBLISHED).order_by('-created_at')
        return Lab.objects.all().order_by('-created_at')

    def get_permissions(self):
        # Creation is for trainers/admins only
        if self.action == 'create':
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        # Updates/deletes require ownership
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsTrainerOrAdmin(), IsOwnerOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        # Automatically assign the creator
        serializer.save(created_by=self.request.user, source=Lab.Source.MANUAL)

    # ---------------------------------------------------------
    # Custom Actions
    # ---------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='submit-for-review')
    def submit_for_review(self, request, pk=None):
        lab = self.get_object()
        if lab.created_by != request.user and request.user.role != 'ADMIN':
            raise ValidationError({"detail": "Seul le créateur peut soumettre ce lab."})
        if lab.status != Lab.Status.DRAFT:
            raise ValidationError({"detail": "Seul un brouillon peut être soumis."})
        
        lab.status = Lab.Status.REVIEW
        lab.save()
        return Response({"detail": "Lab soumis pour validation.", "status": lab.status})

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        if request.user.role not in ['TRAINER', 'ADMIN']:
            raise ValidationError({"detail": "Accès refusé."})
        
        lab = self.get_object()
        if lab.status != Lab.Status.REVIEW:
            raise ValidationError({"detail": "Ce lab n'est pas en attente de validation."})

        lab.status = Lab.Status.PUBLISHED
        lab.published_at = timezone.now()
        lab.reviewed_by = request.user
        lab.save()
        
        LabReview.objects.create(
            lab=lab, reviewer=request.user,
            decision=LabReview.Decision.APPROVED,
            comment=request.data.get('comment', '')
        )
        return Response({"detail": "Lab publié avec succès.", "status": lab.status})

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        if request.user.role not in ['TRAINER', 'ADMIN']:
            raise ValidationError({"detail": "Accès refusé."})
        
        lab = self.get_object()
        if lab.status != Lab.Status.REVIEW:
            raise ValidationError({"detail": "Ce lab n'est pas en attente de validation."})

        lab.status = Lab.Status.DRAFT
        lab.reviewed_by = request.user
        lab.save()

        LabReview.objects.create(
            lab=lab, reviewer=request.user,
            decision=LabReview.Decision.REJECTED,
            comment=request.data.get('comment', '')
        )
        return Response({"detail": "Lab rejeté et remis en brouillon.", "status": lab.status})

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """Start a new session for the current user."""
        lab = self.get_object()
        if lab.status != Lab.Status.PUBLISHED:
            raise ValidationError({"detail": "Ce lab n'est pas publié."})
        
        existing = LabSession.objects.filter(
            lab=lab, user=request.user, status=LabSession.Status.RUNNING
        ).first()
        if existing:
            return Response(LabSessionSerializer(existing).data)

        session = LabSession.objects.create(lab=lab, user=request.user)
        return Response(LabSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='submit-flag')
    def submit_flag(self, request, pk=None):
        """Submit the flag for a lab."""
        lab = self.get_object()
        serializer = SubmitFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted = serializer.validated_data['flag'].strip()

        session = LabSession.objects.filter(
            lab=lab, user=request.user, status=LabSession.Status.RUNNING
        ).first()
        
        if not session:
            raise ValidationError({"detail": "Aucune session en cours. Démarrez le lab d'abord."})

        session.submitted_flag = submitted
        
        if submitted == lab.flag.strip():
            session.solved = True
            session.status = LabSession.Status.COMPLETED
            session.score = 100
            session.finished_at = timezone.now()
            session.save()
            return Response({"detail": "Flag correct ! Lab terminé.", "solved": True})
        else:
            session.save()
            return Response({"detail": "Flag incorrect.", "solved": False}, status=status.HTTP_400_BAD_REQUEST)


class LabSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet to list the current user's sessions."""
    serializer_class = LabSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LabSession.objects.filter(user=self.request.user).order_by('-started_at')