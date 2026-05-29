"""BAT3 Pipeline API package."""

from .main import app

__all__ = ["app"]


def create_app():
    """Factory function to create the FastAPI app."""
    from .main import app as application
    return application
