"""Single import surface for the dependencies endpoints actually need."""

from backend.core.security import AuthenticatedUser, get_current_user, require_roles
from shared.db.base import get_db

__all__ = ["AuthenticatedUser", "get_current_user", "require_roles", "get_db"]
