from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsTrainerOrAdmin(BasePermission):
    """Allows access only to TRAINER or ADMIN roles."""
    message = "Action réservée aux formateurs et administrateurs."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('TRAINER', 'ADMIN')
        )


class IsOwnerOrAdmin(BasePermission):
    """Object-level: only the creator of the object or an ADMIN."""
    message = "Vous ne pouvez modifier que vos propres laboratoires."

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True
        return obj.created_by_id == request.user.id


class CanViewLab(BasePermission):
    """PUBLISHED labs can be viewed by all; others only by owner/admin."""
    message = "Ce laboratoire n'est pas encore publié."

    def has_object_permission(self, request, view, obj):
        if request.method not in SAFE_METHODS:
            return True
        if obj.status == 'PUBLISHED':
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == 'ADMIN':
            return True
        return obj.created_by_id == request.user.id