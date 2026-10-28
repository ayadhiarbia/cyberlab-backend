from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom user model for CYBERLAB.
    Adds a 'role' field to distinguish Admins, Students and Trainers.
    """

    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrateur'
        STUDENT = 'STUDENT', 'Étudiant'
        TRAINER = 'TRAINER', 'Formateur / Analyste'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"






class PasswordResetCode(models.Model):
    """
    One-time code sent by email to reset a user's password.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_codes',
    )
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'code']),
        ]

    def __str__(self):
        return f"Code for {self.user.username} (used={self.used})"

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    @classmethod
    def generate_for(cls, user):
        """Create a fresh code for the given user, invalidating previous ones."""
        # Invalidate all previous unused codes
        cls.objects.filter(user=user, used=False).update(used=True)

        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        ttl = getattr(settings, 'PASSWORD_RESET_CODE_TTL_MINUTES', 15)
        expires_at = timezone.now() + timedelta(minutes=ttl)

        return cls.objects.create(
            user=user,
            code=code,
            expires_at=expires_at,
        )

    def is_valid(self):
        """A code is valid if not used, not expired, and under max attempts."""
        if self.used:
            return False
        if timezone.now() > self.expires_at:
            return False
        max_attempts = getattr(settings, 'PASSWORD_RESET_MAX_ATTEMPTS', 5)
        if self.attempts >= max_attempts:
            return False
        return True

    def mark_used(self):
        self.used = True
        self.save(update_fields=['used'])





