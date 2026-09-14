import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

for key, value in {
    "MONGO_URL": "mongodb://127.0.0.1:27017",
    "DB_NAME": "test_only",
    "JWT_SECRET": "test-only-secret",
    "ADMIN_EMAIL": "test@example.com",
    "ADMIN_PASSWORD": "test-only-password",
    "PIX_KEY": "test",
    "WHATSAPP_NUMBER": "5511000000000",
    "OWNER_WHATSAPP": "5511000000000",
    "WHATSAPP_BOT_URL": "http://127.0.0.1:3002",
}.items():
    os.environ[key] = value

import server


class DialogueRegressionTests(unittest.IsolatedAsyncioTestCase):
    def fake_db(self, state="book_category", history=None):
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock(return_value=None)
        fake.wa_memories.find_one = AsyncMock(return_value={
            "history": history or [],
            "message_count": len(history or []),
        })
        fake.wa_memories.update_one = AsyncMock(return_value=None)
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": state, "data": {}})
        fake.wa_sessions.update_one = AsyncMock(return_value=None)
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[])
        return fake

    async def call(self, text, state="book_category", history=None):
        fake = self.fake_db(state, history)
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text=text, push_name="Cliente"),
                auth={"test": True},
            )
        return result, fake

    async def test_self_deprecation_does_not_loop_category_prompt(self):
        result, fake = await self.call("Sou burro")
        reply = result["reply"].lower()
        self.assertIn("não é burro", reply)
        self.assertNotIn("você quer fazer cílios, unhas ou sobrancelhas", reply)
        fake.wa_sessions.update_one.assert_not_awaited()

    async def test_apology_self_deprecation_is_conversation(self):
        result, fake = await self.call("Desculpa sou muito burro para isso")
        reply = result["reply"].lower()
        self.assertIn("não é burro", reply)
        self.assertNotIn("escolha uma categoria", reply)
        fake.wa_sessions.update_one.assert_not_awaited()

    async def test_what_do_you_think_uses_previous_context(self):
        history = [{"role": "user", "text": "Desculpa sou muito burro para isso"}]
        result, fake = await self.call("O que você acha", history=history)
        reply = result["reply"].lower()
        self.assertIn("não é burro", reply)
        self.assertIn("conversar normal", reply)
        fake.wa_sessions.update_one.assert_not_awaited()

    async def test_unhas_still_continues_booking_after_chat(self):
        result, fake = await self.call("Unhas")
        self.assertIn("serviço de", result["reply"].lower())
        self.assertEqual(result["ui"]["type"], "list")
        self.assertTrue(any("fibra" in row["title"].lower() for row in result["ui"]["sections"][0]["rows"]))
        fake.wa_sessions.update_one.assert_awaited()

    async def test_menu_always_resets_and_returns_options(self):
        result, fake = await self.call("Manda o menu porfavor", state="book_category")
        self.assertIn("voltamos pro começo", result["reply"].lower())
        self.assertEqual(result["ui"]["button_text"], "Abrir menu")
        fake.wa_sessions.update_one.assert_awaited()


if __name__ == "__main__":
    unittest.main()
