from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from jhai_to_c.config import Settings
from jhai_to_c.main import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        auth_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}",
        langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
        mock_provider_latency_ms=0,
    )


def _register_payload(phone: str, name: str) -> dict[str, str]:
    return {
        "phone": phone,
        "display_name": name,
        "password": "secure-pass-123",
        "password_confirm": "secure-pass-123",
    }


def _project_payload(title: str) -> dict[str, object]:
    return {
        "title": title,
        "request_text": f"请为{title}制作短视频",
        "target_platform": "douyin",
        "duration_seconds": 10,
        "aspect_ratio": "9:16",
        "references": [],
    }


@pytest.mark.asyncio
async def test_registration_login_permissions_and_project_ownership(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            unauthenticated = await client.post(
                "/api/content-projects", json=_project_payload("未登录项目")
            )
            assert unauthenticated.status_code == 401

            admin_response = await client.post(
                "/api/auth/register", json=_register_payload("13800138000", "管理员")
            )
            assert admin_response.status_code == 201
            admin_data = admin_response.json()
            assert admin_data["user"]["role"]["code"] == "admin"
            admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

            duplicate = await client.post(
                "/api/auth/register", json=_register_payload("13800138000", "重复账号")
            )
            assert duplicate.status_code == 409

            member_response = await client.post(
                "/api/auth/register", json=_register_payload("13900139000", "创作成员")
            )
            assert member_response.status_code == 201
            member_data = member_response.json()
            assert member_data["user"]["role"]["code"] == "member"
            member_headers = {"Authorization": f"Bearer {member_data['access_token']}"}

            member_access = await client.get("/api/access", headers=member_headers)
            assert member_access.status_code == 403

            member_project = await client.post(
                "/api/content-projects",
                json=_project_payload("成员项目"),
                headers=member_headers,
            )
            assert member_project.status_code == 201
            project_id = member_project.json()["id"]
            assert (
                await client.get(f"/api/content-projects/{project_id}", headers=admin_headers)
            ).status_code == 200

            other_response = await client.post(
                "/api/auth/register", json=_register_payload("13700137000", "其他成员")
            )
            other_data = other_response.json()
            other_headers = {"Authorization": f"Bearer {other_data['access_token']}"}
            hidden = await client.get(f"/api/content-projects/{project_id}", headers=other_headers)
            assert hidden.status_code == 404

            access = (await client.get("/api/access", headers=admin_headers)).json()
            member_role = next(role for role in access["roles"] if role["code"] == "member")
            restricted_permissions = [
                permission
                for permission in member_role["permissions"]
                if permission != "content_projects:create"
            ]
            updated = await client.patch(
                f"/api/access/roles/{member_role['id']}",
                json={"permissions": restricted_permissions},
                headers=admin_headers,
            )
            assert updated.status_code == 200

            forbidden_create = await client.post(
                "/api/content-projects",
                json=_project_payload("越权项目"),
                headers=member_headers,
            )
            assert forbidden_create.status_code == 403

            logged_in = await client.post(
                "/api/auth/login",
                json={"phone": "13800138000", "password": "secure-pass-123"},
            )
            assert logged_in.status_code == 200
            assert (await client.get("/api/auth/me")).status_code == 200
            assert (await client.post("/api/auth/logout")).status_code == 204
            signed_out = await client.get("/api/auth/me")
            assert signed_out.status_code == 200
            assert signed_out.json() is None
