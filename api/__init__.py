"""FastAPI backend for the SafeVision AI dashboard."""

__all__ = ["create_app"]


def create_app():
    from .main import create_app as _create_app

    return _create_app()
