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


class AvailabilityLanguageTests(unittest.IsolatedAsyncioTestCase):
    def test_after_tomorrow_is_two_days_ahead(self):
        now = server.datetime(2026, 9, 14, 21, 38, tzinfo=server.TZ)
        self.assertEqual(server.wa_date_from_sentence("Para depois de amanhã tem horário?", now), "2026-09-16")

    def test_day_number_uses_current_month_when_future(self):
        now = server.datetime(2026, 9, 14, 21, 38, tzinfo=server.TZ)
        self.assertEqual(server.wa_date_from_sentence("E dia 16?", now), "2026-09-16")

    def test_day_number_rolls_to_next_month_if_needed(self):
        now = server.datetime(2026, 9, 30, 21, 38, tzinfo=server.TZ)
        self.assertEqual(server.wa_date_from_sentence("dia 2", now), "2026-10-02")

    async def test_specific_date_availability_without_service(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [
                {"time": "09:00", "available": True},
                {"time": "11:00", "available": False},
                {"time": "15:30", "available": True},
            ],
        }
        setter = AsyncMock()
        with patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.wa_smart_action(
                "Para dia 16/09 tem horário", "menu", {}, "5511999999999", {}, setter
            )
        self.assertIn("16/09/2026", result["reply"])
        self.assertIn("09:00", result["reply"])
        self.assertIn("15:30", result["reply"])
        self.assertNotIn("11:00", result["reply"])
        self.assertNotIn("qual dia", result["reply"].lower())

    async def test_time_pick_after_availability_keeps_date(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [
                {"time": "09:00", "available": True},
                {"time": "15:30", "available": True},
            ],
        }
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={
            "state": "avail_pick",
            "data": {"date": "2026-09-16", "slots": ["09:00", "15:30"]},
        })
        fake.wa_sessions.update_one = AsyncMock()
        with patch.object(server, "db", fake), \
             patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="15:30", push_name="Cliente"),
                auth={"test": True},
            )
        self.assertIn("procedimento", result["reply"].lower())
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_category")
        self.assertEqual(update["data"]["date"], "2026-09-16")
        self.assertEqual(update["data"]["time"], "15:30")

    async def test_category_preserves_preselected_date_and_time(self):
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={
            "state": "book_category",
            "data": {"date": "2026-09-16", "time": "15:30"},
        })
        fake.wa_sessions.update_one = AsyncMock()
        with patch.object(server, "db", fake):
            await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Cílios", push_name="Cliente"),
                auth={"test": True},
            )
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_service")
        self.assertEqual(update["data"]["date"], "2026-09-16")
        self.assertEqual(update["data"]["time"], "15:30")
        self.assertEqual(update["data"]["category"], "cilios")

    async def test_service_uses_preselected_slot_without_asking_date_again(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [{"time": "15:30", "available": True}],
        }
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={
            "state": "book_service",
            "data": {"category": "cilios", "date": "2026-09-16", "time": "15:30"},
        })
        fake.wa_sessions.update_one = AsyncMock()
        with patch.object(server, "db", fake), \
             patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Volume Glamour", push_name="Cliente"),
                auth={"test": True},
            )
        self.assertIn("nome completo", result["reply"].lower())
        self.assertNotIn("para qual data", result["reply"].lower())
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_name")
        self.assertEqual(update["data"]["service_id"], "glamour")
        self.assertEqual(update["data"]["date"], "2026-09-16")
        self.assertEqual(update["data"]["time"], "15:30")

    async def test_followup_day_keeps_availability_context(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [{"time": "17:00", "available": True}],
        }
        memory = {"history": [{"role": "user", "text": "Para depois de amanhã tem horário?"}]}
        setter = AsyncMock()
        # The parser itself is covered with a fixed clock above. For the smart
        # follow-up, use an explicit date so the test is stable on any CI date.
        with patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.wa_smart_action(
                "E dia 16/09?", "menu", {}, "5511999999999", memory, setter
            )
        self.assertIn("16/09/2026", result["reply"])
        self.assertIn("17:00", result["reply"])
        self.assertNotIn("menu", result["reply"].lower())


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
