"""
Router – POST /cleanup

Delete all temp files associated with a video ID.
"""

import os
from fastapi import APIRouter

from app.schemas.cleanup import CleanupRequest, CleanupResponse
from app.utils.file_utils import find_tmp_files
from app.utils.logger import get_logger

router = APIRouter(prefix="/cleanup", tags=["4 - Cleanup"])
log    = get_logger("router.cleanup")


@router.post(
    "",
    response_model=CleanupResponse,
    summary="Delete all temp files for a video",
    description="Removes all files in the server temp directory whose name starts with videoId.",
)
def cleanup(body: CleanupRequest) -> CleanupResponse:
    log.info("Cleanup request for videoId: %s", body.videoId)

    files   = find_tmp_files(body.videoId)
    deleted = []
    failed  = []

    for f in files:
        try:
            os.remove(f)
            deleted.append(f)
            log.info("Deleted: %s", f)
        except OSError as exc:
            failed.append({"file": f, "error": str(exc)})
            log.warning("Could not delete %s: %s", f, exc)

    return CleanupResponse(
        status="success",
        videoId=body.videoId,
        deleted=deleted,
        failed=failed,
    )
