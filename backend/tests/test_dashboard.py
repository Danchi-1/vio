from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from vio_backend import dashboard_store
from vio_backend.database import session_dependency
from vio_backend.main import app


@pytest.mark.asyncio
async def test_get_public_dashboard_metrics_filters_and_suppression():
    mock_session = AsyncMock()

    dept_id = uuid4()
    mock_row = {
        "department_id": dept_id,
        "department": "Computer Science",
        "category": "class_not_held",
        "month": date(2026, 10, 1),
        "findings": 12,
    }

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    metrics = await dashboard_store.get_public_dashboard_metrics(
        mock_session,
        department_id=dept_id,
        category="class_not_held",
        start_month=date(2026, 10, 1),
        end_month=date(2026, 10, 31),
    )

    assert len(metrics) == 1
    assert metrics[0]["department_id"] == str(dept_id)
    assert metrics[0]["department"] == "Computer Science"
    assert metrics[0]["category"] == "class_not_held"
    assert metrics[0]["month"] == "2026-10-01"
    assert metrics[0]["findings"] == 12

    # Privacy verification: no identifying fields
    for field in ("reporter_id", "student_id", "lecturer_name", "finding_id", "description"):
        assert field not in metrics[0]

    executed_query = str(mock_session.execute.call_args[0][0])
    assert "public_dashboard" in executed_query
    assert "d.faculty_id" not in executed_query
    assert "pd.department_id = :department_id" in executed_query
    assert "pd.category = :category" in executed_query
    assert "pd.month >= :start_month" in executed_query
    assert "pd.month <= :end_month" in executed_query


@pytest.mark.asyncio
async def test_get_authority_responsiveness_summary():
    mock_session = AsyncMock()

    mock_rows = [
        {
            "role": "hod",
            "deliveries": 10,
            "acknowledged": 9,
            "avg_hours_to_acknowledge": 14.5,
        },
        {
            "role": "dean",
            "deliveries": 5,
            "acknowledged": 4,
            "avg_hours_to_acknowledge": 28.0,
        },
    ]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows
    mock_session.execute.return_value = mock_result

    stats = await dashboard_store.get_authority_responsiveness_summary(mock_session)

    assert len(stats) == 2
    assert stats[0]["role"] == "hod"
    assert stats[0]["deliveries"] == 10
    assert stats[0]["acknowledged"] == 9
    assert stats[0]["avg_hours_to_acknowledge"] == 14.5

    # Verification: no authority IDs or names
    for s in stats:
        assert "authority_id" not in s
        assert "email" not in s
        assert "name" not in s


@pytest.mark.asyncio
async def test_get_dashboard_filters():
    mock_session = AsyncMock()

    fac_id = uuid4()
    dept_id = uuid4()

    mock_dept_result = MagicMock()
    mock_dept_result.mappings.return_value.all.return_value = [
        {
            "department_id": dept_id,
            "department_name": "Mathematical Sciences",
            "faculty_id": fac_id,
            "faculty_name": "Physical Sciences",
        }
    ]

    mock_cat_result = MagicMock()
    mock_cat_result.mappings.return_value.all.return_value = [
        {"category": "class_not_held"},
        {"category": "materials_sales_unauthorized"},
    ]

    mock_range_result = MagicMock()
    mock_range_result.mappings.return_value.first.return_value = {
        "min_month": date(2026, 9, 1),
        "max_month": date(2026, 11, 1),
    }

    mock_session.execute.side_effect = [
        mock_dept_result,
        mock_cat_result,
        mock_range_result,
    ]

    filters = await dashboard_store.get_dashboard_filters(mock_session)

    assert len(filters["faculties"]) == 1
    assert filters["faculties"][0]["name"] == "Physical Sciences"
    assert filters["faculties"][0]["departments"][0]["name"] == "Mathematical Sciences"
    assert filters["categories"] == ["class_not_held", "materials_sales_unauthorized"]
    assert filters["date_range"]["min_month"] == "2026-09-01"
    assert filters["date_range"]["max_month"] == "2026-11-01"


def test_public_dashboard_api_validation():
    mock_session = AsyncMock()

    async def override_session():
        yield mock_session

    app.dependency_overrides[session_dependency] = override_session
    try:
        with TestClient(app) as client:
            # Invalid category
            res = client.get("/api/v1/public/dashboard?category=fabricated_category")
            assert res.status_code == 400
            assert res.json()["error"]["code"] == "invalid_category"

            # Invalid date range
            res = client.get("/api/v1/public/dashboard?start_month=2026-12-01&end_month=2026-01-01")
            assert res.status_code == 400
            assert res.json()["error"]["code"] == "invalid_date_range"
    finally:
        app.dependency_overrides.pop(session_dependency, None)


def test_public_dashboard_api_success():
    mock_session = AsyncMock()

    mock_metrics_result = MagicMock()
    mock_metrics_result.mappings.return_value.all.return_value = [
        {
            "department_id": uuid4(),
            "department": "Computer Science",
            "category": "class_not_held",
            "month": date(2026, 10, 1),
            "findings": 5,
        }
    ]

    mock_stats_result = MagicMock()
    mock_stats_result.mappings.return_value.all.return_value = [
        {
            "role": "hod",
            "deliveries": 3,
            "acknowledged": 3,
            "avg_hours_to_acknowledge": 6.0,
        }
    ]

    mock_session.execute.side_effect = [
        mock_metrics_result,
        mock_stats_result,
    ]

    async def override_session():
        yield mock_session

    app.dependency_overrides[session_dependency] = override_session
    try:
        with TestClient(app) as client:
            res = client.get("/api/v1/public/dashboard")
            assert res.status_code == 200
            data = res.json()
            assert "data" in data
            assert len(data["data"]) == 1
            assert data["data"][0]["department"] == "Computer Science"
            assert "authority_responsiveness" in data
            assert len(data["authority_responsiveness"]) == 1
    finally:
        app.dependency_overrides.pop(session_dependency, None)
