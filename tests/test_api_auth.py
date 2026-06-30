import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_auth_flow(client: AsyncClient):
    # 1. Register a new user
    reg_data = {
        "email": "user@example.com",
        "password": "supersecretpassword",
        "full_name": "Jane Doe"
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_data)
    assert reg_res.status_code == 201
    assert reg_res.json()["email"] == reg_data["email"]
    assert "id" in reg_res.json()

    # 2. Prevent duplicate registration
    dupe_res = await client.post("/api/v1/auth/register", json=reg_data)
    assert dupe_res.status_code == 409

    # 3. Login with correct credentials
    login_res = await client.post("/api/v1/auth/login", json={
        "email": reg_data["email"],
        "password": reg_data["password"]
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert "refresh_token" in login_res.json()
    
    tokens = login_res.json()

    # 4. Access protected profile route with token
    auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    profile_res = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert profile_res.status_code == 200
    assert profile_res.json()["full_name"] == reg_data["full_name"]

    # 5. Access profile route with invalid token
    bad_headers = {"Authorization": "Bearer invalid_token"}
    bad_res = await client.get("/api/v1/auth/me", headers=bad_headers)
    assert bad_res.status_code == 401

    # 6. Refresh tokens using refresh token
    refresh_res = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()
