import os
import base64
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


def booking():
    return {
        "id": "booking-12345678",
        "code": "AD-TEST12",
        "service_id": "brasileiro",
        "service_name": "Volume Brasileiro",
        "category": "cilios",
        "price": 100,
        "deposit": 50,
        "date": "2026-09-20",
        "time": "15:30",
        "client_name": "Cliente",
        "client_phone": "5511999999999",
        "client_phone_digits": "11999999999",
        "status": "pendente",
        "payment_status": "aguardando_comprovante",
    }


class PaymentFlowTests(unittest.IsolatedAsyncioTestCase):
    def proof_b64(self):
        return base64.b64encode(b"\xff\xd8\xff\xe0receipt-test").decode()

    async def test_proof_payload_rejects_unsupported_or_forged_files(self):
        with self.assertRaises(server.HTTPException) as unsupported:
            server.validate_proof_payload(self.proof_b64(), "text/html")
        self.assertEqual(unsupported.exception.status_code, 400)

        forged = base64.b64encode(b"not-a-jpeg").decode()
        with self.assertRaises(server.HTTPException) as mismatch:
            server.validate_proof_payload(forged, "image/jpeg")
        self.assertEqual(mismatch.exception.status_code, 400)

    def test_proof_payload_accepts_supported_image(self):
        self.assertEqual(server.validate_proof_payload(self.proof_b64(), "image/jpeg"), "image/jpeg")

    async def test_duplicate_proof_upload_keeps_single_current_proof(self):
        b = booking()
        fake = MagicMock()
        first = MagicMock()
        first.matched_count = 0
        fake.proofs.insert_one = AsyncMock()
        fake.proofs.delete_one = AsyncMock()
        fake.bookings.update_one = AsyncMock(return_value=first)
        fake.bookings.find_one = AsyncMock(return_value={**b, "proof_status": "em_analise", "proof_id": "existing-proof"})
        with patch.object(server, "db", fake), \
             patch.object(server, "bot_send_text", AsyncMock()), \
             patch.object(server, "bot_send_image", AsyncMock()):
            proof_id = await server.store_proof_for_review(b, self.proof_b64(), "image/jpeg", "site")
        self.assertEqual(proof_id, "existing-proof")
        fake.proofs.delete_one.assert_awaited_once()

    async def test_approve_claim_is_idempotent_and_notifies_once(self):
        b = {**booking(), "proof_status": "em_analise", "proof_id": "proof-1", "payment_status": "em_analise"}
        proof = {"id": "proof-1", "booking_id": b["id"], "status": "em_analise"}
        fake = MagicMock()
        fake.proofs.find_one = AsyncMock(return_value=proof)
        fake.bookings.find_one = AsyncMock(return_value=b)
        claimed = MagicMock()
        claimed.matched_count = 1
        fake.bookings.update_one = AsyncMock(return_value=claimed)
        fake.proofs.update_one = AsyncMock()
        notify = AsyncMock(return_value=True)
        with patch.object(server, "db", fake), patch.object(server, "notify_proof_review_result", notify):
            result = await server._review_proof("proof-1", True, {"id": "admin"})
        self.assertEqual(result["payment_status"], "confirmado")
        notify.assert_awaited_once()
        query = fake.bookings.update_one.await_args.args[0]
        self.assertEqual(query["proof_status"], "em_analise")

    async def test_payment_amount_uses_pending_booking_not_guess(self):
        b = booking()
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": "menu", "data": {}})
        fake.wa_sessions.update_one = AsyncMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[b])
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="quanto tenho que pagar?", push_name="Cliente"),
                auth={"test": True},
            )
        reply = result["reply"].lower()
        self.assertIn("r$ 100", reply)
        self.assertIn("r$ 50", reply)
        self.assertIn("ad-test12", reply)

    async def test_paid_message_never_self_confirms(self):
        b = {**booking(), "proof_status": None}
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": "menu", "data": {}})
        fake.wa_sessions.update_one = AsyncMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[b])
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="já paguei", push_name="Cliente"),
                auth={"test": True},
            )
        reply = result["reply"].lower()
        self.assertIn("aguardando confirmação", reply)
        self.assertIn("comprovante", reply)
        self.assertNotIn("pagamento aprovado", reply)

    async def test_paid_message_with_multiple_pending_bookings_asks_which_one(self):
        b1 = booking()
        b2 = {**booking(), "id": "booking-87654321", "code": "AD-OTHER1234", "time": "17:00"}
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": "menu", "data": {}})
        fake.wa_sessions.update_one = AsyncMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[b1, b2])
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="paguei", push_name="Cliente"),
                auth={"test": True},
            )
        self.assertIn("qual delas", result["reply"].lower())
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "payment_pick")
        self.assertEqual(update["data"]["action"], "claim")

    async def test_payment_pick_accepts_reservation_code(self):
        b1 = booking()
        b2 = {**booking(), "id": "booking-87654321", "code": "AD-OTHER1234", "time": "17:00"}
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={
            "state": "payment_pick",
            "data": {"action": "claim", "booking_ids": [b1["id"], b2["id"]]},
        })
        fake.wa_sessions.update_one = AsyncMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[b1, b2])
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="AD-OTHER1234", push_name="Cliente"),
                auth={"test": True},
            )
        self.assertIn("ad-other1234", result["reply"].lower())
        self.assertIn("aguardando confirmação", result["reply"].lower())

    async def test_multiple_pending_bookings_do_not_guess_proof_target(self):
        b1 = booking()
        b2 = {**booking(), "id": "booking-87654321", "code": "AD-OTHER1", "time": "17:00"}
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": "menu", "data": {}})
        fake.wa_sessions.update_one = AsyncMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[b1, b2])
        with patch.object(server, "db", fake), patch.object(server, "store_proof_for_review", AsyncMock()) as store:
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="", image_base64="abc", image_mime="image/jpeg"),
                auth={"test": True},
            )
        self.assertIn("mais de uma reserva", result["reply"].lower())
        store.assert_not_awaited()
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "proof_pick")
        self.assertEqual(set(update["data"]["booking_ids"]), {b1["id"], b2["id"]})


    async def test_proof_selection_is_remembered_until_image_arrives(self):
        b1 = booking()
        b2 = {**booking(), "id": "booking-87654321", "code": "AD-OTHER1234", "time": "17:00"}
        session = {"state": "proof_pick", "data": {"booking_ids": [b1["id"], b2["id"]]}}
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()

        async def session_find(*args, **kwargs):
            return {"state": session["state"], "data": dict(session["data"])}

        async def session_update(query, update, **kwargs):
            values = update["$set"]
            session["state"] = values["state"]
            session["data"] = dict(values["data"])

        fake.wa_sessions.find_one = AsyncMock(side_effect=session_find)
        fake.wa_sessions.update_one = AsyncMock(side_effect=session_update)
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[b1, b2])
        store = AsyncMock(return_value="proof-new")

        with patch.object(server, "db", fake), patch.object(server, "store_proof_for_review", store):
            picked = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="AD-OTHER1234", push_name="Cliente"),
                auth={"test": True},
            )
            self.assertIn("agora envie", picked["reply"].lower())
            self.assertEqual(session["state"], "proof_wait_image")
            self.assertEqual(session["data"]["booking_id"], b2["id"])

            uploaded = await server.whatsapp_incoming(
                server.WAIncoming(
                    phone="5511999999999",
                    text="",
                    image_base64=self.proof_b64(),
                    image_mime="image/jpeg",
                    push_name="Cliente",
                ),
                auth={"test": True},
            )

        self.assertIn("em análise", uploaded["reply"].lower())
        self.assertEqual(store.await_args.args[0]["id"], b2["id"])
        self.assertEqual(session["state"], "menu")


if __name__ == "__main__":
    unittest.main()
