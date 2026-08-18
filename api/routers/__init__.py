from . import (
    analysis,
    analytics,
    cameras,
    dashboard,
    incidents,
    media,
    nva,
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
    nva.router,
    reports.router,
    settings.router,
    system.router,
    media.router,
]

__all__ = ["ROUTERS"]
