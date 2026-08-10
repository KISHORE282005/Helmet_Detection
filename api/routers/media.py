"""Evidence, poster and report file delivery.

Every path goes through `resolve_media`, which confines reads to a fixed set
of output directories.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..state import resolve_media

router = APIRouter(prefix="/api/media", tags=["media"])

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/{kind}/{name}")
def get_media(kind: str, name: str, download: bool = False):
    path = resolve_media(kind, name)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type=CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        filename=path.name if download else None,
    )
