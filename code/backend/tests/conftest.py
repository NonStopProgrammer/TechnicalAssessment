import pytest
from fastapi.testclient import TestClient

from backend.core.security import create_access_token
from backend.main import api
from shared.enums import UserRole


@pytest.fixture(scope="module")
def client():
    # Context-manager form runs FastAPI's lifespan (init_db + demo seed).
    with TestClient(api) as test_client:
        yield test_client


@pytest.fixture
def officer_headers() -> dict:
    token = create_access_token("officer@finserv.test", UserRole.COMPLIANCE_OFFICER)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def head_headers() -> dict:
    token = create_access_token("head@finserv.test", UserRole.COMPLIANCE_HEAD)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auditor_headers() -> dict:
    token = create_access_token("auditor@finserv.test", UserRole.INTERNAL_AUDITOR)
    return {"Authorization": f"Bearer {token}"}
