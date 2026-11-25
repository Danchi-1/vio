from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import dashboard_store
from vio_backend.database import session_dependency
from vio_backend.errors import ApiError
from vio_backend.report_rules import REPORT_CATEGORIES

router = APIRouter(prefix="/api/v1/public", tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    faculty_id: UUID | None = Query(None, description="Filter by faculty ID"),
    department_id: UUID | None = Query(None, description="Filter by department ID"),
    category: str | None = Query(None, description="Filter by finding category"),
    start_month: date | None = Query(None, description="Filter incidents starting from month (YYYY-MM-DD)"),
    end_month: date | None = Query(None, description="Filter incidents up to month (YYYY-MM-DD)"),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    if category is not None and category not in REPORT_CATEGORIES:
        raise ApiError(400, "invalid_category", f"Unknown category '{category}'")

    if start_month and end_month and start_month > end_month:
        raise ApiError(400, "invalid_date_range", "start_month cannot be after end_month")

    metrics = await dashboard_store.get_public_dashboard_metrics(
        session,
        faculty_id=faculty_id,
        department_id=department_id,
        category=category,
        start_month=start_month,
        end_month=end_month,
    )

    authority_stats = await dashboard_store.get_authority_responsiveness_summary(
        session,
        faculty_id=faculty_id,
        department_id=department_id,
    )

    return {
        "data": metrics,
        "authority_responsiveness": authority_stats,
    }


@router.get("/dashboard/filters")
async def get_dashboard_filters(
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    filters = await dashboard_store.get_dashboard_filters(session)
    return {"data": filters}
