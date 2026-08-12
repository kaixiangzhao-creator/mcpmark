"""External-state support for the WebArena Playwright service."""

from .external_backend import ExternalStateBackend
from .models import MountSpec, PreparedState

__all__ = ["ExternalStateBackend", "MountSpec", "PreparedState"]
