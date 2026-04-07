from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission, SAFE_METHODS


class AuthenticatedReadAdminWrite(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and getattr(user, "is_authenticated", False)):
            raise NotAuthenticated("Authentication credentials were not provided.")
        if request.method in SAFE_METHODS:
            return True
        if user.role != "admin":
            raise PermissionDenied("Admin role required.")
        return True
