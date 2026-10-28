from django.conf import settings
from django.db import models


class Challenge(models.Model):
    """A CTF Challenge that students can solve for points."""
    
    class Category(models.TextChoices):
        WEB = 'WEB', 'Web Security'
        CRYPTO = 'CRYPTO', 'Cryptographie'
        FORENSICS = 'FORENSICS', 'Forensics'
        NETWORKING = 'NETWORKING', 'Networking'
        REVERSE = 'REVERSE', 'Reverse Engineering'
        OSINT = 'OSINT', 'OSINT'

    class Difficulty(models.TextChoices):
        EASY = 'EASY', 'Facile'
        MEDIUM = 'MEDIUM', 'Moyen'
        HARD = 'HARD', 'Difficile'

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.WEB)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)
    points = models.IntegerField(default=100)
    
    flag = models.CharField(max_length=255, help_text="La réponse exacte (sensible à la casse)")
    hints = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"[{self.points} pts] {self.title}"


class CTFSubmission(models.Model):
    """Tracks a student's successful submission for a challenge."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ctf_submissions')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='submissions')
    submitted_flag = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A user can only submit a challenge once (successfully)
        unique_together = ('user', 'challenge')
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.username} - {self.challenge.title} ({'Correct' if self.is_correct else 'Incorrect'})"