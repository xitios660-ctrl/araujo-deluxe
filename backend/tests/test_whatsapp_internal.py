import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
for key, value in {
    "MONGO_URL": "mongodb://127.0.0.1:27017", "DB_NAME": "test_only",
    "JWT_SECRET": "test-only-secret", "ADMIN_EMAIL": "test@example.com",
    "ADMIN_PASSWORD": "test-only-password", "PIX_KEY": "test",
    "WHATSAPP_NUMBER": "5511000000000", "OWNER_WHATSAPP": "5511000000000",
    "WHATSAPP_BOT_URL": "http://127.0.0.1:3002",
}.items():
    os.environ[key] = value
import httpx
import server

class InternalAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_internal_endpoints_reject_missing_auth(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
            for method, url, body in [
                ("GET", "/api/internal/whatsapp/session", None),
                ("POST", "/api/internal/whatsapp/session", {"entries": []}),
                ("DELETE", "/api/internal/whatsapp/session", None),
                ("POST", "/api/internal/whatsapp/lease", None),
                ("POST", "/api/whatsapp/incoming", {"phone": "5511111111111", "text": "oi"}),
            ]:
                response = await client.request(method, url, json=body)
                self.assertEqual(response.status_code, 401, url)

    async def test_wrong_instance_cannot_read_saved_session(self):
        fake_db = MagicMock()
        fake_db.wa_runtime.find_one = AsyncMock(return_value={"owner": "other", "until": "2999-01-01"})
        with patch.object(server, "db", fake_db):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
                response = await client.get("/api/internal/whatsapp/session", headers={"X-Bot-Token": server.BOT_TOKEN, "X-Bot-Instance": "wrong"})
                self.assertEqual(response.status_code, 409)
        fake_db.wa_auth.find.assert_not_called()

    async def test_opt_out_blocks_notifications_including_owner(self):
        fake_db = MagicMock()
        fake_db.wa_preferences.find_one = AsyncMock(return_value={"blocked": True})
        with patch.object(server, "db", fake_db):
            self.assertFalse(await server.whatsapp_contact_allowed(server.OWNER_WA))
