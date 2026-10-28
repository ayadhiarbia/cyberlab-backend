from rest_framework import serializers
from .models import Challenge, CTFSubmission


class ChallengeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing challenges (hides the flag)."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)

    class Meta:
        model = Challenge
        fields = [
            'id', 'title', 'category', 'category_display', 
            'difficulty', 'difficulty_display', 'points', 'is_active'
        ]


class ChallengeDetailSerializer(serializers.ModelSerializer):
    """Full serializer for trainers to see everything, and students for hints."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Challenge
        # Note: We include 'flag' here for the Trainers. 
        # We will hide it from students in the View logic.
        fields = [
            'id', 'title', 'description', 'category', 'category_display',
            'difficulty', 'points', 'hints', 'flag', 'is_active', 'created_at'
        ]


class SubmitFlagSerializer(serializers.Serializer):
    """Validate the flag input."""
    flag = serializers.CharField(max_length=255)


class CTFSubmissionSerializer(serializers.ModelSerializer):
    """Shows a user's submission history."""
    challenge_title = serializers.CharField(source='challenge.title', read_only=True)
    
    class Meta:
        model = CTFSubmission
        fields = ['id', 'challenge', 'challenge_title', 'is_correct', 'submitted_at']