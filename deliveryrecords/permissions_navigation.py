from rest_framework.exceptions import PermissionDenied


def _get_allowed_nav_keys(request) -> set[str] | None:
    auth_payload = getattr(request, "auth", None)
    if not isinstance(auth_payload, dict):
        return None
    if "allowed_nav_keys" not in auth_payload:
        return None
    return set(auth_payload.get("allowed_nav_keys") or [])


def require_nav_access(request, *required_keys: str) -> None:
    user = getattr(request, "user", None)
    if getattr(user, "role", None) != "admin":
        return

    allowed_nav_keys = _get_allowed_nav_keys(request)
    if allowed_nav_keys is None:
        return

    if any(key in allowed_nav_keys for key in required_keys):
        return

    raise PermissionDenied("This API is not allowed by current navigation policy.")
