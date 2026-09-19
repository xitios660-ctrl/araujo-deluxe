import os
import unittest
from unittest.mock import AsyncMock, patch

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


class StableAvailabilityDateTests(unittest.IsolatedAsyncioTestCase):
    def test_past_day_month_rolls_to_next_year(self):
        now = server.datetime(2026, 9, 17, 8, 0, tzinfo=server.TZ)
        self.assertEqual(server.wa_date_from_sentence("dia 16/09", now), "2027-09-16")
        self.assertEqual(server.wa_date_from_sentence("dia 18/09", now), "2027-09-18")

    async def test_specific_future_date_availability_without_service(self):
        day = {
            "date": "2099-09-16", "weekday_name": "Quarta-feira",
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
                "Para dia 16/09/2099 tem horário", "menu", {}, "5511999999999", {}, setter
            )
        self.assertIn("16/09/2099", result["reply"])
        self.assertIn("qual procedimento", result["reply"].lower())
        self.assertNotIn("qual dia", result["reply"].lower())

    async def test_future_followup_day_keeps_availability_context(self):
        day = {
            "date": "2099-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [{"time": "17:00", "available": True}],
        }
        memory = {"history": [{"role": "user", "text": "Para depois de amanhã tem horário?"}]}
        setter = AsyncMock()
        with patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.wa_smart_action(
                "E dia 16/09/2099?", "menu", {}, "5511999999999", memory, setter
            )
        self.assertIn("16/09/2099", result["reply"])
        self.assertIn("qual procedimento", result["reply"].lower())
        self.assertNotIn("menu", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
