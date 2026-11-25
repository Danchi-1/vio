from fastapi.testclient import TestClient

from vio_backend.link_auth import create_lecturer_session_token
from vio_backend.main import app


def test_liveness_is_available_without_database():
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_cors_preflight_allows_local_frontend_with_credentials():
    origin = "http://127.0.0.1:5500"
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/auth/student/email-challenges",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_readiness_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["message"] == "Database is not configured"
    assert "request_id" in body["error"]


def test_catalogue_endpoint_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/universities")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_academic_sessions_endpoint_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/academic-sessions")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_email_challenge_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/student/email-challenges",
            json={"university_id": "00000000-0000-0000-0000-000000000000", "email": "surnametl.26@student.funaab.edu.ng"},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_session_summary_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/session")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_student_profile_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/student/profile")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_unknown_route_is_not_found():
    with TestClient(app) as client:
        response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_report_options_fail_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/student/report-options")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_submit_report_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/student/reports",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "incident_date": "2026-10-12",
                "category": "class_not_held",
                "description": "The lecturer did not hold the class on the scheduled date.",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_list_reports_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/student/reports")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_confirmable_findings_fail_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/student/findings/confirmable")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_get_finding_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/student/findings/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_confirm_finding_fails_closed_without_database_configuration():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/student/findings/00000000-0000-0000-0000-000000000000/confirmations",
            json={"comment": "I was present and this class definitely did not hold."},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_post_class_notice_requires_lecturer_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_post_class_notice_fails_closed_without_database_when_authenticated():
    token = create_lecturer_session_token(
        "insecure-dev-lecturer-secret",
        lecturer_id="00000000-0000-0000-0000-000000000000",
        email="prof@funaab.edu.ng",
        department_id="00000000-0000-0000-0000-000000000000",
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/lecturer/class-notices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "course_id": "00000000-0000-0000-0000-000000000000",
                "kind": "cancelled",
                "for_date": "2026-10-12",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_authority_endpoints_require_authority_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/deliveries/00000000-0000-0000-0000-000000000000/acknowledgement"
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authority_access_fails_closed_without_database():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/authority/access",
            json={"token": "a" * 32},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


