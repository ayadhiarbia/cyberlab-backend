from rest_framework import serializers
from .models import Lab, LabSession, LabReview


class LabListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing labs in a list view."""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)

    class Meta:
        model = Lab
        fields = [
            'id', 'title', 'difficulty', 'difficulty_display',
            'category', 'category_display', 'status', 'source',
            'created_by_username', 'created_at',
        ]


class LabSerializer(serializers.ModelSerializer):
    """Full serializer for detail, create, and update views."""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Lab
        fields = [
            'id', 'title', 'description', 'difficulty', 'category',
            'objectives', 'scenario', 'hints', 'flag', 'solution',
            'status', 'source', 'ai_prompt',
            'created_by', 'created_by_username', 'reviewed_by',
            'created_at', 'updated_at', 'published_at',
        ]
        read_only_fields = [
            'id', 'status', 'source', 'created_by', 'reviewed_by',
            'created_at', 'updated_at', 'published_at',
        ]


class LabSessionSerializer(serializers.ModelSerializer):
    """Serializer for a student's attempt at a lab."""
    lab_title = serializers.CharField(source='lab.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = LabSession
        fields = [
            'id', 'lab', 'lab_title', 'user', 'user_username',
            'status', 'solved', 'score', 'started_at', 'finished_at',
        ]
        read_only_fields = [
            'id', 'user', 'lab_title', 'user_username', 'started_at', 'finished_at', 'score'
        ]


class SubmitFlagSerializer(serializers.Serializer):
    """Just to validate the flag input."""
    flag = serializers.CharField(max_length=255)


class LabReviewSerializer(serializers.ModelSerializer):
    """History of validation decisions."""
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True)

    class Meta:
        model = LabReview
        fields = ['id', 'lab', 'reviewer', 'reviewer_username', 'decision', 'comment', 'created_at']
        read_only_fields = ['id', 'lab', 'reviewer', 'created_at']