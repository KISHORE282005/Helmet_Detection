from . import (
    analysis,
    analytics,
    cameras,
    dashboard,
    incidents,
    media,
    reports,
    settings,
    system,
)

ROUTERS = [
    dashboard.router,
    incidents.router,
    cameras.router,
    analysis.router,
    analytics.router,
    reports.router,
    settings.router,
    system.router,
    media.router,
]

__all__ = ["ROUTERS"]
