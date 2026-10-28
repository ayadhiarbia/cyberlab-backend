from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer used to return user data (read-only)."""
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_display', 'bio', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'role_display']


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for creating a new account."""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'role',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError(
                {"password": "Les mots de passe ne correspondent pas."}
            )
        return attrs

    def create(self, validated_data):
        # Public registration always creates a STUDENT.
        validated_data['role'] = User.Role.STUDENT
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user



class UserAdminSerializer(serializers.ModelSerializer):
    """Read-only representation of a user for admin endpoints."""
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_display',
            'is_active', 'is_staff', 'is_superuser',
            'last_login', 'date_joined', 'created_at',
        ]
        read_only_fields = fields


class RoleUpdateSerializer(serializers.Serializer):
    """Payload used to change a user's role."""
    role = serializers.ChoiceField(choices=User.Role.choices)




# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

class PasswordResetRequestSerializer(serializers.Serializer):
    """Body for POST /password/request-code/"""
    email = serializers.EmailField()


class PasswordResetVerifySerializer(serializers.Serializer):
    """Body for POST /password/verify-code/"""
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Body for POST /password/reset/"""
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {"new_password": "Les mots de passe ne correspondent pas."}
            )
        # Django's built-in password validators (min length, common passwords, etc.)
        validate_password(attrs['new_password'])
        return attrs