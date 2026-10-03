"""
Integration tests for Dashboard FastAPI application:
- /health endpoint
- Login page rendering
- /api/v1/auth/login and session cookie issuance
- /api/v1/auth/me session verification
- Single server ID verification
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dashboard.app import create_dashboard_app
from app.dashboard.auth import hash_password
from app.database.engine import get_engine, get_session_direct, init_engine
from app.database.models import Base
from app.database.repositories import AdminUserRepo


@pytest_asyncio.fixture(autouse=True)
async def setup_test_api_database():
    """Ensure database tables exist before API tests run."""
    engine = get_engine()
    if engine is None:
        await init_engine()
        engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
def app():
    """Create test instance of FastAPI dashboard app."""
    return create_dashboard_app()


@pytest.mark.asyncio
async def test_health_endpoint(app):
    """Verify /health endpoint returns JSON status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "discord" in data
        assert "youtube" in data


@pytest.mark.asyncio
async def test_login_and_auth_me(app):
    """Verify admin login with credentials, cookie issuance, and /auth/me."""
    session = await get_session_direct()
    try:
        user = await AdminUserRepo.get_by_username(session, "dashboard_admin")
        if not user:
            await AdminUserRepo.create(session, "dashboard_admin", hash_password("SuperSecret123!"))
            await session.commit()
    finally:
        await session.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Invalid credentials must fail with 401
        res_fail = await client.post("/api/v1/auth/login", json={
            "username": "dashboard_admin",
            "password": "WrongPassword",
        })
        assert res_fail.status_code == 401

        # Valid credentials must succeed with 200
        res_ok = await client.post("/api/v1/auth/login", json={
            "username": "dashboard_admin",
            "password": "SuperSecret123!",
        })
        assert res_ok.status_code == 200
        login_data = res_ok.json()
        assert login_data["success"] is True
        assert login_data["username"] == "dashboard_admin"
        assert "pbhero_session" in res_ok.cookies

        # Verify /api/v1/auth/me using the session cookie
        res_me = await client.get("/api/v1/auth/me", cookies=res_ok.cookies)
        assert res_me.status_code == 200
        me_data = res_me.json()
        assert me_data["authenticated"] is True
        assert me_data["username"] == "dashboard_admin"
        # Verify single server guild ID is returned
        assert me_data["guild_id"] == "123456789012345678"
