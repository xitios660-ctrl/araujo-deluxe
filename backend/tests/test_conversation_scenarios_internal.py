import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

for key, value in {
    "MONGO_URL": "mongodb://127.0.0.1:27017",
    "DB_NAME": "test_only",
    "JWT_SECRET": "test-only-secret",
    "ADMIN_EMAIL": "test@example.com",
    "ADMIN_PASSWORD": "test-only-password",
    "PIX_KEY": "test-pix",
    "WHATSAPP_NUMBER": "5511000000000",
    "OWNER_WHATSAPP": "5511000000000",
    "WHATSAPP_BOT_URL": "http://127.0.0.1:3002",
}.items():
    os.environ[key] = value

import server


class ConversationHarness:
    def __init__(self):
        self.phone = "5511999999999"
        self.session = {"state": "menu", "data": {}}
        self.memory = {"history": [], "message_count": 0}
        self.booking = None
        self.db = MagicMock()

        self.db.wa_preferences.find_one = AsyncMock(return_value=None)
        self.db.wa_preferences.update_one = AsyncMock()
        self.db.wa_sessions.find_one = AsyncMock(side_effect=self._session_find)
        self.db.wa_sessions.update_one = AsyncMock(side_effect=self._session_update)
        self.db.wa_memories.find_one = AsyncMock(side_effect=self._memory_find)
        self.db.wa_memories.update_one = AsyncMock(side_effect=self._memory_update)

    async def _session_find(self, *args, **kwargs):
        return {"state": self.session["state"], "data": dict(self.session["data"])}

    async def _session_update(self, query, update, **kwargs):
        values = update.get("$set", {})
        if "state" in values:
            self.session["state"] = values["state"]
        if "data" in values:
            self.session["data"] = dict(values["data"])
        return MagicMock(matched_count=1)

    async def _memory_find(self, *args, **kwargs):
        return dict(self.memory)

    async def _memory_update(self, query, update, **kwargs):
        self.memory.update(update.get("$set", {}))
        for key, amount in update.get("$inc", {}).items():
            self.memory[key] = self.memory.get(key, 0) + amount
        push = update.get("$push", {}).get("history")
        if push:
            entries = push.get("$each", [])
            self.memory.setdefault("history", []).extend(entries)
            slice_value = push.get("$slice")
            if isinstance(slice_value, int) and slice_value < 0:
                self.memory["history"] = self.memory["history"][slice_value:]
        return MagicMock(matched_count=1)

    def day(self, date, service_id=None):
        return {
            "date": date,
            "weekday_name": "Dia de teste",
            "scheduled_open": True,
            "open": True,
            "day_blocked": False,
            "closed_reason": None,
            "slots": [
                {"time": "09:00", "available": True, "reason": None, "booking": None, "block_id": None},
                {"time": "11:00", "available": True, "reason": None, "booking": None, "block_id": None},
                {"time": "15:30", "available": True, "reason": None, "booking": None, "block_id": None},
                {"time": "17:00", "available": True, "reason": None, "booking": None, "block_id": None},
            ],
        }

    async def find_bookings(self, phone, only_pending=False):
        if not self.booking:
            return []
        if only_pending and self.booking.get("status") != "pendente":
            return []
        return [self.booking]

    async def create_booking(self, service_id, date_str, time_str, name, phone):
        self.booking = {
            "id": "booking-flow-1",
            "code": "AD-FLOW123456",
            "service_id": service_id,
            "service_name": server.SERVICES_BY_ID[service_id]["name"],
            "category": server.SERVICES_BY_ID[service_id]["category"],
            "price": server.SERVICES_BY_ID[service_id]["price"],
            "deposit": server.SERVICES_BY_ID[service_id]["deposit"],
            "duration": server.SERVICES_BY_ID[service_id]["duration"],
            "date": date_str,
            "time": time_str,
            "client_name": name,
            "client_phone": phone,
            "status": "pendente",
            "payment_status": "aguardando_comprovante",
        }
        return dict(self.booking)

    async def send(self, text):
        with patch.object(server, "db", self.db), \
             patch.object(server, "get_day_availability", AsyncMock(side_effect=self.day)), \
             patch.object(server, "wa_find_bookings", AsyncMock(side_effect=self.find_bookings)), \
             patch.object(server, "wa_create_booking", AsyncMock(side_effect=self.create_booking)):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone=self.phone, text=text, push_name="Ana"),
                auth={"test": True},
            )
            if result.get("reply"):
                await server.wa_remember_message(self.phone, "assistant", result["reply"])
            return result


class FullConversationScenarioTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_natural_booking_payment_and_site_flow(self):
        h = ConversationHarness()

        first = await h.send("tem horário amanhã?")
        self.assertIn("procedimento", first["reply"].lower())
        first_date = h.session["data"]["date"]
        self.assertEqual(h.session["state"], "book_category")

        second = await h.send("e de tarde?")
        self.assertIn("de tarde", second["reply"].lower())
        self.assertEqual(h.session["data"]["date"], first_date)
        self.assertEqual(h.session["data"]["daypart"], "afternoon")

        third = await h.send("brasileiro")
        self.assertIn("15:30", third["reply"])
        self.assertEqual(h.session["state"], "book_time")
        self.assertEqual(h.session["data"]["service_id"], "brasileiro")

        fourth = await h.send("pode ser 15h")
        self.assertIn("nome completo", fourth["reply"].lower())
        self.assertEqual(h.session["state"], "book_name")
        self.assertEqual(h.session["data"]["time"], "15:30")

        fifth = await h.send("Meu nome é Ana Silva")
        self.assertIn("reserva criada", fifth["reply"].lower())
        self.assertEqual(h.booking["client_name"], "Ana Silva")
        self.assertEqual(h.booking["time"], "15:30")
        self.assertEqual(h.session["state"], "menu")

        sixth = await h.send("quanto tenho que pagar?")
        self.assertIn("r$ 100", sixth["reply"].lower())
        self.assertIn("r$ 50", sixth["reply"].lower())

        seventh = await h.send("paguei")
        self.assertIn("aguardando confirmação", seventh["reply"].lower())
        self.assertNotIn("pagamento aprovado", seventh["reply"].lower())

        eighth = await h.send("manda o site também")
        self.assertIn("araujo-deluxe-studio.onrender.com", eighth["reply"])

    async def test_changing_date_mid_booking_replaces_previous_date(self):
        h = ConversationHarness()
        h.session = {
            "state": "book_time",
            "data": {
                "service_id": "brasileiro",
                "date": "2026-09-16",
                "slots": ["15:30", "17:00"],
                "daypart": "afternoon",
            },
        }
        h.memory = {
            "history": [],
            "message_count": 3,
            "last_service_id": "brasileiro",
            "last_service_at": server.datetime.now(server.timezone.utc).isoformat(),
        }

        result = await h.send("na verdade quero sábado")
        self.assertIn("volume brasileiro", result["reply"].lower())
        self.assertEqual(h.session["state"], "book_time")
        self.assertNotEqual(h.session["data"]["date"], "2026-09-16")
        self.assertEqual(h.session["data"]["daypart"], "afternoon")
        self.assertIn("15:30", h.session["data"]["slots"])

    async def test_cannot_tomorrow_reopens_date_choice_without_losing_service(self):
        h = ConversationHarness()
        tomorrow = (server.datetime.now(server.TZ) + server.timedelta(days=1)).strftime("%Y-%m-%d")
        h.session = {
            "state": "book_time",
            "data": {
                "service_id": "glamour",
                "date": tomorrow,
                "slots": ["15:30", "17:00"],
            },
        }
        result = await h.send("não consigo amanhã")
        self.assertIn("qual outro dia", result["reply"].lower())
        self.assertEqual(h.session["state"], "book_date")
        self.assertEqual(h.session["data"]["service_id"], "glamour")


if __name__ == "__main__":
    unittest.main()
