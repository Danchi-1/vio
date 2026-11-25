from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_public_dashboard_metrics(
    session: AsyncSession,
    *,
    faculty_id: UUID | None = None,
    department_id: UUID | None = None,
    category: str | None = None,
    start_month: date | None = None,
    end_month: date | None = None,
) -> list[dict[str, Any]]:
    """Retrieve aggregate findings from public_dashboard view with suppression.
    
    Guarantees k-anonymity: individual findings, student identities, lecturer names,
    and groups smaller than platform_settings.dashboard_min_group are excluded by SQL.
    """
    conditions = ["1=1"]
    params: dict[str, Any] = {}

    if faculty_id is not None:
        conditions.append("d.faculty_id = :faculty_id")
        params["faculty_id"] = faculty_id

    if department_id is not None:
        conditions.append("pd.department_id = :department_id")
        params["department_id"] = department_id

    if category is not None:
        conditions.append("pd.category = :category")
        params["category"] = category

    if start_month is not None:
        conditions.append("pd.month >= :start_month")
        params["start_month"] = start_month

    if end_month is not None:
        conditions.append("pd.month <= :end_month")
        params["end_month"] = end_month

    where_clause = " AND ".join(conditions)

    query = text(
        f"""
        SELECT pd.department_id,
               pd.department,
               pd.category,
               pd.month,
               pd.findings
        FROM public_dashboard pd
        JOIN departments d ON d.id = pd.department_id
        WHERE {where_clause}
        ORDER BY pd.month DESC, pd.department ASC, pd.category ASC
        """
    )

    result = await session.execute(query, params)
    rows = result.mappings().all()

    return [
        {
            "department_id": str(r["department_id"]),
            "department": r["department"],
            "category": r["category"],
            "month": r["month"].isoformat() if hasattr(r["month"], "isoformat") else str(r["month"]),
            "findings": int(r["findings"]),
        }
        for r in rows
    ]


async def get_authority_responsiveness_summary(
    session: AsyncSession,
    *,
    faculty_id: UUID | None = None,
    department_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Retrieve aggregate authority response metrics from authority_response_stats view.
    
    Exposes only roles and aggregate times, never individual identities or authority IDs.
    """
    conditions = ["1=1"]
    params: dict[str, Any] = {}

    if faculty_id is not None:
        conditions.append("(faculty_id = :faculty_id OR faculty_id IS NULL)")
        params["faculty_id"] = faculty_id

    if department_id is not None:
        conditions.append("(department_id = :department_id OR department_id IS NULL)")
        params["department_id"] = department_id

    where_clause = " AND ".join(conditions)

    query = text(
        f"""
        SELECT role,
               SUM(deliveries) AS deliveries,
               SUM(acknowledged) AS acknowledged,
               ROUND(AVG(avg_hours_to_acknowledge)::numeric, 1) AS avg_hours_to_acknowledge
        FROM authority_response_stats
        WHERE {where_clause}
        GROUP BY role
        ORDER BY role ASC
        """
    )

    result = await session.execute(query, params)
    rows = result.mappings().all()

    return [
        {
            "role": r["role"],
            "deliveries": int(r["deliveries"] or 0),
            "acknowledged": int(r["acknowledged"] or 0),
            "avg_hours_to_acknowledge": (
                float(r["avg_hours_to_acknowledge"])
                if r["avg_hours_to_acknowledge"] is not None
                else None
            ),
        }
        for r in rows
    ]


async def get_dashboard_filters(session: AsyncSession) -> dict[str, Any]:
    """Retrieve active filter values available for public dashboard without leaking suppressed groups."""
    dept_query = text(
        """
        SELECT DISTINCT d.id AS department_id, d.name AS department_name, f.id AS faculty_id, f.name AS faculty_name
        FROM public_dashboard pd
        JOIN departments d ON d.id = pd.department_id
        JOIN faculties f ON f.id = d.faculty_id
        ORDER BY f.name ASC, d.name ASC
        """
    )
    dept_res = await session.execute(dept_query)
    dept_rows = dept_res.mappings().all()

    faculties_map: dict[str, dict[str, Any]] = {}
    for r in dept_rows:
        fac_id = str(r["faculty_id"])
        if fac_id not in faculties_map:
            faculties_map[fac_id] = {
                "id": fac_id,
                "name": r["faculty_name"],
                "departments": [],
            }
        faculties_map[fac_id]["departments"].append(
            {"id": str(r["department_id"]), "name": r["department_name"]}
        )

    cat_query = text("SELECT DISTINCT category FROM public_dashboard ORDER BY category ASC")
    cat_res = await session.execute(cat_query)
    categories = [r["category"] for r in cat_res.mappings().all()]

    range_query = text("SELECT MIN(month) AS min_month, MAX(month) AS max_month FROM public_dashboard")
    range_res = await session.execute(range_query)
    range_row = range_res.mappings().first()

    min_m = range_row["min_month"] if range_row and range_row["min_month"] else None
    max_m = range_row["max_month"] if range_row and range_row["max_month"] else None

    return {
        "faculties": list(faculties_map.values()),
        "categories": categories,
        "date_range": {
            "min_month": min_m.isoformat() if hasattr(min_m, "isoformat") else min_m,
            "max_month": max_m.isoformat() if hasattr(max_m, "isoformat") else max_m,
        },
    }
