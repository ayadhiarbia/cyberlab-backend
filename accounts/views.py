from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, PasswordResetCode
from .permissions import IsAdminRole
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    UserAdminSerializer,
    RoleUpdateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer,
)


# ---------------------------------------------------------------------------
# Public / basic auth endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def api_status(request):
    """Public health-check endpoint."""
    return Response({
        "status": "ok",
        "project": "CYBERLAB",
        "message": "Backend opérationnel",
    })


class RegisterView(generics.CreateAPIView):
    """POST /api/accounts/register/ — create a new STUDENT account."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class MeView(generics.RetrieveAPIView):
    """GET /api/accounts/me/ — return the authenticated user."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    POST /api/accounts/logout/
    Body: { "refresh": "<refresh_token>" }
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {"detail": "Le champ 'refresh' est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(
            {"detail": "Déconnexion réussie."},
            status=status.HTTP_205_RESET_CONTENT,
        )
    except Exception:
        return Response(
            {"detail": "Token invalide ou déjà blacklisté."},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ---------------------------------------------------------------------------
# Admin-only user management
# ---------------------------------------------------------------------------

class UserAdminViewSet(viewsets.ModelViewSet):
    """
    Admin-only user management.
      GET    /api/accounts/users/                        → list
      GET    /api/accounts/users/<id>/                   → detail
      PATCH  /api/accounts/users/<id>/role/              → change role
      PATCH  /api/accounts/users/<id>/toggle-active/     → activate / deactivate
      DELETE /api/accounts/users/<id>/                   → hard delete (confirm=true)
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()

        # ?role=STUDENT
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)

        # ?active=true / false
        active = self.request.query_params.get('active')
        if active is not None:
            qs = qs.filter(is_active=active.lower() == 'true')

        # ?search=<text>
        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        return qs

    @action(detail=True, methods=['patch'], url_path='role')
    def change_role(self, request, pk=None):
        """PATCH /api/accounts/users/<id>/role/  Body: {"role": "..."}"""
        user = self.get_object()
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data['role']

        # Guard 1: cannot change your own role
        if user == request.user:
            raise ValidationError(
                {"detail": "Vous ne pouvez pas modifier votre propre rôle."}
            )

        # Guard 2: cannot demote the last remaining ADMIN
        if (
            user.role == User.Role.ADMIN
            and new_role != User.Role.ADMIN
            and User.objects.filter(role=User.Role.ADMIN).count() <= 1
        ):
            raise ValidationError(
                {"detail": "Impossible de rétrograder le dernier administrateur."}
            )

        user.role = new_role
        user.save(update_fields=['role'])
        return Response(UserAdminSerializer(user).data)

    @action(detail=True, methods=['patch'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """PATCH /api/accounts/users/<id>/toggle-active/"""
        user = self.get_object()

        if user == request.user:
            raise ValidationError(
                {"detail": "Vous ne pouvez pas désactiver votre propre compte."}
            )

        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return Response(UserAdminSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/accounts/users/<id>/
        Body (JSON): { "confirm": true }

        Hard-deletes a user. Requires explicit confirmation.
        Guards: cannot delete self; cannot delete the last ADMIN.
        """
        user = self.get_object()

        # Guard 1: cannot delete yourself
        if user == request.user:
            raise ValidationError(
                {"detail": "Vous ne pouvez pas supprimer votre propre compte."}
            )

        # Guard 2: cannot delete the last ADMIN
        if (
            user.role == User.Role.ADMIN
            and User.objects.filter(role=User.Role.ADMIN).count() <= 1
        ):
            raise ValidationError(
                {"detail": "Impossible de supprimer le dernier administrateur."}
            )

        # Guard 3: require explicit confirmation flag
        if not request.data.get('confirm'):
            raise ValidationError(
                {"detail": "Ajoutez \"confirm\": true au corps de la requête pour confirmer la suppression."}
            )

        username = user.username
        user.delete()
        return Response(
            {"detail": f"Utilisateur '{username}' supprimé."},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Password reset (email code flow)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    POST /api/accounts/password/request-code/
    Body: { "email": "user@example.com" }

    Generates a 6-digit code, stores it, and "sends" it by email.
    In dev, the email prints in the runserver terminal.
    For privacy, we always return 200 — even if the email doesn't exist.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']

    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        # Don't reveal whether the email exists.
        return Response(
            {"detail": "Si un compte existe pour cet email, un code a été envoyé."},
            status=status.HTTP_200_OK,
        )

    # Throttle: cooldown between two code requests for the same user
    cooldown = getattr(settings, 'PASSWORD_RESET_RESEND_COOLDOWN_SECONDS', 60)
    last = PasswordResetCode.objects.filter(user=user).order_by('-created_at').first()
    if last and (timezone.now() - last.created_at).total_seconds() < cooldown:
        return Response(
            {"detail": f"Veuillez patienter avant de demander un nouveau code."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    reset_code = PasswordResetCode.generate_for(user)

    send_mail(
        subject="CYBERLAB — Code de réinitialisation du mot de passe",
        message=(
            f"Bonjour {user.username},\n\n"
            f"Votre code de réinitialisation est : {reset_code.code}\n\n"
            f"Ce code expire dans {getattr(settings, 'PASSWORD_RESET_CODE_TTL_MINUTES', 15)} minutes.\n"
            f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
            f"— L'équipe CYBERLAB"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return Response(
        {"detail": "Si un compte existe pour cet email, un code a été envoyé."},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_verify(request):
    """
    POST /api/accounts/password/verify-code/
    Body: { "email": "...", "code": "123456" }

    Verifies the code WITHOUT consuming it (so the user can then call /reset/).
    """
    serializer = PasswordResetVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']

    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        return Response(
            {"detail": "Code invalide ou expiré."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reset_code = PasswordResetCode.objects.filter(user=user, code=code).order_by('-created_at').first()
    if not reset_code or not reset_code.is_valid():
        # Count a failed attempt to eventually lock the code.
        if reset_code:
            reset_code.attempts += 1
            reset_code.save(update_fields=['attempts'])
        return Response(
            {"detail": "Code invalide ou expiré."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"detail": "Code valide."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """
    POST /api/accounts/password/reset/
    Body: { "email": "...", "code": "123456",
            "new_password": "...", "new_password_confirm": "..." }

    Verifies the code, sets the new password, marks the code as used.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    new_password = serializer.validated_data['new_password']

    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        return Response(
            {"detail": "Code invalide ou expiré."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reset_code = PasswordResetCode.objects.filter(user=user, code=code).order_by('-created_at').first()
    if not reset_code or not reset_code.is_valid():
        if reset_code:
            reset_code.attempts += 1
            reset_code.save(update_fields=['attempts'])
        return Response(
            {"detail": "Code invalide ou expiré."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # All good — set the new password and consume the code
    user.set_password(new_password)
    user.save(update_fields=['password'])
    reset_code.mark_used()

    return Response(
        {"detail": "Mot de passe réinitialisé avec succès."},
        status=status.HTTP_200_OK,
    )