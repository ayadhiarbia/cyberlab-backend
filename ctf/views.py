from django.db.models import Sum, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from accounts.models import User
from .models import Challenge, CTFSubmission
from .serializers import (
    ChallengeListSerializer, ChallengeDetailSerializer,
    SubmitFlagSerializer, CTFSubmissionSerializer
)
from labs.permissions import IsTrainerOrAdmin

class ChallengeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Challenge.objects.filter(is_active=True).order_by('-points')

    def get_serializer_class(self):
        if self.action == 'list':
            return ChallengeListSerializer
        return ChallengeDetailSerializer

    def get_permissions(self):
        # Only trainers/admins can create, update, or delete challenges
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        return super().get_permissions()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to hide the flag from Students."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # If the user is a student, remove the flag from the response!
        if request.user.role == 'STUDENT':
            data.pop('flag', None)
            
        return Response(data)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit_flag(self, request, pk=None):
        """Submit a flag for a challenge."""
        challenge = self.get_object()
        serializer = SubmitFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted = serializer.validated_data['flag'].strip()

        # 1. Check if the user already solved it
        already_solved = CTFSubmission.objects.filter(
            user=request.user, challenge=challenge, is_correct=True
        ).exists()
        
        if already_solved:
            return Response({"detail": "Vous avez déjà résolu ce challenge."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Check if the flag is correct
        is_correct = (submitted == challenge.flag.strip())

        # 3. Record the submission
        submission = CTFSubmission.objects.create(
            user=request.user,
            challenge=challenge,
            submitted_flag=submitted,
            is_correct=is_correct
        )

        if is_correct:
            return Response({
                "detail": "Flag correct ! Bien joué.",
                "is_correct": True,
                "points_awarded": challenge.points
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "detail": "Flag incorrect. Essayez encore.",
                "is_correct": False
            }, status=status.HTTP_400_BAD_REQUEST)


class LeaderboardViewSet(viewsets.ViewSet):
    """A read-only view to see the CTF ranking."""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Get all students, sum their correct submission points
        # We only count correct submissions
        users = User.objects.filter(role='STUDENT').annotate(
            total_score=Sum('ctf_submissions__challenge__points', filter=Q(ctf_submissions__is_correct=True))
        ).order_by('-total_score')

        # Format the output
        leaderboard = []
        for index, user in enumerate(users):
            score = user.total_score if user.total_score else 0
            leaderboard.append({
                "rank": index + 1,
                "username": user.username,
                "score": score
            })

        return Response(leaderboard)