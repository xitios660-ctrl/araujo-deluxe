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


def available_day(date="2026-09-15", time="15:00"):
    return {
        "date": date,
        "weekday_name": "Terça-feira",
        "scheduled_open": True,
        "open": True,
        "day_blocked": False,
        "day_block_id": None,
        "closed_reason": None,
        "slots": [{"time": time, "available": True, "reason": None, "booking": None, "block_id": None}],
    }


class BookingSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_availability_reports_blocked_day_as_closed(self):
        day = available_day()
        day.update(open=False, day_blocked=True, day_block_id="block-1", closed_reason="Folga")
        with patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.availability("2026-09-15")
        self.assertFalse(result["open"])
        self.assertTrue(result["day_blocked"])
        self.assertEqual(result["closed_reason"], "Folga")

    async def test_site_booking_uses_shared_booking_creator(self):
        booking = {
            "id": "b1", "code": "AD-TEST", "service_id": "glamour", "service_name": "Volume Glamour",
            "category": "cilios", "price": 140, "deposit": 50, "date": "2026-09-15", "time": "15:00",
            "client_name": "Cliente Teste", "client_phone": "11999999999", "notes": "", "status": "pendente",
            "created_at": "2026-09-14T00:00:00+00:00",
        }
        creator = AsyncMock(return_value=booking)
        with patch.object(server, "create_booking_record", creator):
            result = await server.create_booking(server.BookingCreate(
                service_id="glamour", date="2026-09-15", time="15:00",
                client_name="Cliente Teste", client_phone="11999999999",
            ))
        creator.assert_awaited_once()
        self.assertEqual(result["id"], "b1")
        self.assertEqual(result["date"], "2026-09-15")
        self.assertEqual(result["time"], "15:00")

    async def test_whatsapp_booking_uses_same_shared_booking_creator(self):
        booking = {
            "id": "b2", "code": "AD-WA", "service_id": "glamour", "service_name": "Volume Glamour",
            "category": "cilios", "price": 140, "deposit": 50, "date": "2026-09-15", "time": "15:00",
            "client_name": "Cliente WhatsApp", "client_phone": "5511999999999", "notes": "Agendado pelo bot do WhatsApp",
            "status": "pendente", "created_at": "2026-09-14T00:00:00+00:00",
        }
        creator = AsyncMock(return_value=booking)
        with patch.object(server, "create_booking_record", creator):
            result = await server.wa_create_booking("glamour", "2026-09-15", "15:00", "Cliente WhatsApp", "5511999999999")
        creator.assert_awaited_once_with(
            "glamour", "2026-09-15", "15:00", "Cliente WhatsApp", "5511999999999",
            "Agendado pelo bot do WhatsApp",
        )
        self.assertEqual(result["id"], "b2")

    async def test_final_recheck_prevents_booking_if_day_closes(self):
        fake_db = MagicMock()
        fake_db.bookings.find_one = AsyncMock(return_value=None)
        fake_db.bookings.insert_one = AsyncMock()
        fake_db.booking_slot_locks.insert_one = AsyncMock()
        fake_db.booking_slot_locks.delete_one = AsyncMock()
        first = available_day()
        closed = available_day()
        closed.update(open=False, day_blocked=True, closed_reason="Dia fechado")
        with patch.object(server, "db", fake_db), patch.object(server, "slot_in_past", return_value=False), patch.object(server, "get_day_availability", AsyncMock(side_effect=[first, closed])):
            with self.assertRaises(server.BookingSlotError) as ctx:
                await server.create_booking_record("glamour", "2026-09-15", "15:00", "Cliente", "11999999999")
        self.assertEqual(ctx.exception.code, "closed_day")
        fake_db.bookings.insert_one.assert_not_awaited()
        self.assertGreaterEqual(fake_db.booking_slot_locks.delete_one.await_count, 1)

    async def test_atomic_lock_rejects_second_simultaneous_booking(self):
        fake_db = MagicMock()
        fake_db.bookings.find_one = AsyncMock(return_value=None)
        fake_db.booking_slot_locks.insert_one = AsyncMock(side_effect=server.DuplicateKeyError("duplicate"))
        with patch.object(server, "db", fake_db):
            with self.assertRaises(server.BookingSlotError) as ctx:
                await server.acquire_booking_slot("2026-09-15", "15:00")
        self.assertEqual(ctx.exception.code, "slot_taken")

    async def test_admin_cannot_close_day_with_active_booking(self):
        fake_db = MagicMock()
        fake_db.bookings.find_one = AsyncMock(return_value={"id": "b1", "time": "15:00"})
        fake_db.bookings.find.return_value.to_list = AsyncMock(return_value=[{"id": "b1", "time": "15:00", "service_id": "glamour", "duration_minutes": 150, "status": "confirmada"}])
        fake_db.blocks.find_one = AsyncMock(return_value=None)
        fake_db.blocks.insert_one = AsyncMock()
        with patch.object(server, "db", fake_db):
            with self.assertRaises(server.HTTPException) as ctx:
                await server.create_block(server.BlockCreate(date="2026-09-15", reason="Folga"), user={})
        self.assertEqual(ctx.exception.status_code, 409)
        fake_db.blocks.insert_one.assert_not_awaited()

    async def test_admin_manual_confirmation_sets_payment_status_and_notifies(self):
        booking = {
            "id": "b-manual", "date": "2026-09-15", "time": "15:00",
            "client_phone": "5511999999999", "status": "pendente", "service_id": "glamour",
            "service_name": "Volume Glamour", "payment_status": "aguardando_comprovante", "proof_status": None,
        }
        updated = {**booking, "status": "confirmada", "payment_status": "confirmado_manual"}
        fake = MagicMock()
        fake.bookings.find_one = AsyncMock(side_effect=[booking, updated])
        fake.bookings.update_one = AsyncMock()
        notify = AsyncMock(return_value=True)
        with patch.object(server, "db", fake), patch.object(server, "bot_send_text", notify):
            result = await server.update_booking("b-manual", server.StatusUpdate(status="confirmada"), user={"id": "admin"})
        update = fake.bookings.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["payment_status"], "confirmado_manual")
        self.assertEqual(result["payment_status"], "confirmado_manual")
        notify.assert_awaited_once()

    async def test_admin_cannot_bypass_proof_in_analysis(self):
        booking = {
            "id": "b-review", "date": "2026-09-15", "time": "15:00", "client_phone": "5511999999999",
            "status": "pendente", "service_id": "glamour", "service_name": "Volume Glamour",
            "payment_status": "em_analise", "proof_status": "em_analise",
        }
        fake = MagicMock()
        fake.bookings.find_one = AsyncMock(return_value=booking)
        fake.bookings.update_one = AsyncMock()
        with patch.object(server, "db", fake):
            with self.assertRaises(server.HTTPException) as ctx:
                await server.update_booking("b-review", server.StatusUpdate(status="confirmada"), user={"id": "admin"})
        self.assertEqual(ctx.exception.status_code, 409)
        fake.bookings.update_one.assert_not_awaited()

    async def test_pending_booking_cannot_jump_to_completed(self):
        booking = {
            "id": "b-pending", "date": "2026-09-15", "time": "15:00", "client_phone": "5511999999999",
            "status": "pendente", "service_id": "glamour", "service_name": "Volume Glamour",
        }
        fake = MagicMock()
        fake.bookings.find_one = AsyncMock(return_value=booking)
        fake.bookings.update_one = AsyncMock()
        with patch.object(server, "db", fake):
            with self.assertRaises(server.HTTPException) as ctx:
                await server.update_booking("b-pending", server.StatusUpdate(status="concluida"), user={"id": "admin"})
        self.assertEqual(ctx.exception.status_code, 409)
        fake.bookings.update_one.assert_not_awaited()

    async def test_cancelling_booking_closes_pending_proof_consistently(self):
        booking = {
            "id": "b-proof-cancel", "date": "2026-09-15", "time": "15:00", "client_phone": "11999999999",
            "status": "pendente", "service_name": "Volume Glamour", "payment_status": "em_analise",
            "proof_status": "em_analise", "proof_id": "proof-1",
        }
        fake = MagicMock()
        claimed = MagicMock(); claimed.matched_count = 1
        fake.bookings.update_one = AsyncMock(return_value=claimed)
        fake.proofs.update_one = AsyncMock()
        release = AsyncMock()
        with patch.object(server, "db", fake), patch.object(server, "release_booking_slot", release):
            ok = await server.mark_booking_cancelled(booking, "test")
        self.assertTrue(ok)
        updates = fake.bookings.update_one.await_args.args[1]["$set"]
        self.assertEqual(updates["status"], "cancelada")
        self.assertEqual(updates["proof_status"], "cancelado")
        self.assertEqual(updates["payment_status"], "cancelado")
        self.assertEqual(fake.proofs.update_one.await_args.args[1]["$set"]["status"], "cancelado")
        release.assert_awaited_once_with("2026-09-15", "15:00")

    async def test_cancel_releases_slot_for_site_and_whatsapp(self):
        booking = {
            "id": "b1", "date": "2026-09-15", "time": "15:00", "client_phone": "11999999999",
            "status": "pendente", "service_name": "Volume Glamour",
        }
        cancelled = {**booking, "status": "cancelada", "payment_status": "cancelado"}
        fake_db = MagicMock()
        # cancel_booking reads the original booking, then reads the persisted result after cancellation.
        fake_db.bookings.find_one = AsyncMock(side_effect=[booking, cancelled])
        claimed = MagicMock(); claimed.matched_count = 1
        fake_db.bookings.update_one = AsyncMock(return_value=claimed)
        release = AsyncMock()
        with patch.object(server, "db", fake_db), patch.object(server, "slot_in_past", return_value=False), patch.object(server, "release_booking_slot", release):
            result = await server.cancel_booking("b1", server.CancelInput(phone="11999999999"))
        release.assert_awaited_once_with("2026-09-15", "15:00")
        self.assertEqual(result["status"], "cancelada")
        self.assertEqual(result["payment_status"], "cancelado")

    def test_duration_parser_and_overlap(self):
        self.assertEqual(server.duration_to_minutes("2h30"), 150)
        self.assertEqual(server.duration_to_minutes("40min"), 40)
        self.assertTrue(server.intervals_overlap(930, 1080, 1020, 1170))
        self.assertFalse(server.intervals_overlap(660, 810, 930, 1080))

    async def test_long_service_blocks_overlapping_start(self):
        fake = MagicMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[{
            "id": "b1", "service_id": "glamour", "date": "2026-09-15", "time": "15:00",
            "status": "confirmada", "duration_minutes": 150, "buffer_minutes": 0,
        }])
        fake.blocks.find.return_value.to_list = AsyncMock(return_value=[])
        with patch.object(server, "db", fake), patch.object(server, "slot_in_past", return_value=False):
            states = await server.get_slot_states("2026-09-15", service_id="brasileiro")
        by_time = {s["time"]: s for s in states}
        self.assertFalse(by_time["17:00"]["available"])
        self.assertEqual(by_time["17:00"]["reason"], "ocupado")
        self.assertIsNone(by_time["17:00"]["booking"])

    def test_public_booking_view_hides_private_fields(self):
        source = {
            "id": "b-public", "code": "AD-PUBLIC1234", "service_id": "glamour", "service_name": "Volume Glamour",
            "category": "cilios", "price": 140, "deposit": 50, "duration": "2h30", "date": "2026-09-19",
            "time": "14:00", "status": "pendente", "payment_status": "em_analise", "proof_status": "em_analise",
            "client_name": "Nome Privado", "client_phone": "5511999999999", "client_phone_digits": "11999999999",
            "notes": "observação privada", "proof_id": "proof-secret", "proof_reviewed_by": "admin-secret",
        }
        result = server.public_booking_view(source)
        self.assertEqual(result["id"], "b-public")
        self.assertEqual(result["proof_status"], "em_analise")
        for key in ("client_name", "client_phone", "client_phone_digits", "notes", "proof_id", "proof_reviewed_by"):
            self.assertNotIn(key, result)

    def test_phone_match_requires_full_number(self):
        self.assertTrue(server.phones_match("+55 11 99999-1234", "11999991234"))
        self.assertFalse(server.phones_match("99991234", "11999991234"))

    async def test_reschedule_detects_concurrent_booking_change(self):
        booking = {
            "id": "b-race", "service_id": "brasileiro", "service_name": "Volume Brasileiro",
            "date": "2026-09-18", "time": "09:00", "status": "confirmada", "duration_minutes": 120, "buffer_minutes": 0,
        }
        fake = MagicMock()
        fake.bookings.find_one = AsyncMock(return_value=booking)
        changed = MagicMock(); changed.matched_count = 0
        fake.bookings.update_one = AsyncMock(return_value=changed)
        available = available_day("2026-09-19", "14:00")
        lock = AsyncMock(return_value=["14:00"])
        release = AsyncMock()
        with patch.object(server, "db", fake), patch.object(server, "get_day_availability", AsyncMock(side_effect=[available, available])), patch.object(server, "acquire_booking_slot", lock), patch.object(server, "release_booking_slot", release):
            with self.assertRaises(server.BookingSlotError) as ctx:
                await server.wa_move_booking("b-race", "2026-09-19", "14:00")
        self.assertEqual(ctx.exception.code, "booking_changed")
        release.assert_awaited_once_with("2026-09-19", "14:00", ["14:00"])

    async def test_admin_status_update_detects_concurrent_change(self):
        booking = {
            "id": "b-status-race", "service_id": "brasileiro", "service_name": "Volume Brasileiro",
            "date": "2026-09-18", "time": "09:00", "client_phone": "5511999999999",
            "status": "confirmada", "payment_status": "confirmado",
        }
        fake = MagicMock()
        fake.bookings.find_one = AsyncMock(return_value=booking)
        changed = MagicMock(); changed.matched_count = 0
        fake.bookings.update_one = AsyncMock(return_value=changed)
        with patch.object(server, "db", fake):
            with self.assertRaises(server.HTTPException) as ctx:
                await server.update_booking("b-status-race", server.StatusUpdate(status="concluida"), user={"id": "admin"})
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_timed_block_rejects_middle_of_long_booking(self):
        fake = MagicMock()
        fake.bookings.find_one = AsyncMock(return_value=None)
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[{
            "id": "b1", "service_id": "glamour", "date": "2026-09-15", "time": "15:00",
            "status": "confirmada", "duration_minutes": 150, "buffer_minutes": 0,
        }])
        fake.blocks.find_one = AsyncMock(return_value=None)
        fake.blocks.insert_one = AsyncMock()
        with patch.object(server, "db", fake):
            with self.assertRaises(server.HTTPException) as ctx:
                await server.create_block(server.BlockCreate(date="2026-09-15", time="17:00", reason="Pausa"), user={})
        self.assertEqual(ctx.exception.status_code, 409)
        fake.blocks.insert_one.assert_not_awaited()

    def test_all_catalog_deposits_are_capped_at_price(self):
        for service in server.SERVICES:
            self.assertLessEqual(service["deposit"], service["price"], service["id"])


if __name__ == "__main__":
    unittest.main()
