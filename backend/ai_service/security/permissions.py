ROLE_PERMISSIONS = {
    "viewer": {"chat:ask", "chat:read_own", "document:list", "document:read"},
    "maintainer": {
        "chat:ask", "chat:read_own", "document:list", "document:read",
    },
    "admin": {"*"},
}


def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())
    return "*" in permissions or permission in permissions
