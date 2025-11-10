from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user, get_db, require_admin
from ..auth.models import AuthUser
from .schemas import CampaignSummaryResponse, SubmissionReloadSummary
from .service import get_campaign_summary, reload_submissions


campaign_router = APIRouter(prefix="/api", tags=["campaign"])


@campaign_router.post(
    "/admin/reload/submissions",
    response_model=SubmissionReloadSummary,
    status_code=status.HTTP_200_OK,
)
async def reload_submissions_endpoint(
    file: UploadFile = File(...),
    _: AuthUser = Depends(require_admin),
    session: Session = Depends(get_db),
) -> SubmissionReloadSummary:
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV uploads are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    summary = reload_submissions(content, session)
    return summary


@campaign_router.get(
    "/campaign/summary",
    response_model=CampaignSummaryResponse,
)
async def campaign_summary_endpoint(
    week: str | None = Query(None, description="Week number between 1-10 or 'all'"),
    user: str | None = Query(None, description="Filter by user email"),
    _: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> CampaignSummaryResponse:
    return get_campaign_summary(session, week=week, user_filter=user)
