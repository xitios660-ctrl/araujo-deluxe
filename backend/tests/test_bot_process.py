import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from bot_process import BotProcess


class BotProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_bot_does_not_spawn_local_process(self):
        bot = BotProcess("https://bot.example.com")
        with patch("bot_process.shutil.which") as which:
            await bot.start()
        which.assert_not_called()
        self.assertIsNone(bot.task)

    async def test_missing_dependencies_leave_api_running(self):
        bot = BotProcess("http://localhost:3002")
        with patch("bot_process.shutil.which", return_value=None):
            await bot.start()
        self.assertIsNone(bot.task)

    async def test_child_uses_render_port_and_stops_cleanly(self):
        bot = BotProcess("http://127.0.0.1:3002")
        child = AsyncMock(); child.returncode = None
        running = asyncio.Event()
        async def wait():
            running.set(); await asyncio.Event().wait()
        child.wait.side_effect = wait
        from unittest.mock import Mock
        child.terminate = Mock()
        with patch("bot_process.shutil.which", return_value="/usr/bin/node"), patch("bot_process.Path.exists", return_value=True), patch.dict("os.environ", {"PORT": "10000"}), patch("bot_process.asyncio.create_subprocess_exec", return_value=child) as spawn:
            await bot.start(); await asyncio.wait_for(running.wait(), timeout=1)
            self.assertEqual(spawn.call_args.kwargs["env"]["BACKEND_URL"], "http://127.0.0.1:10000")
            self.assertEqual(spawn.call_args.kwargs["env"]["BOT_PORT"], "3002")
            child.wait.side_effect = None; child.wait.return_value = 0
            await bot.stop(); child.terminate.assert_called_once()

    async def test_clear_test_clients_removes_booking_data(self):
        bot = BotProcess("http://127.0.0.1:3002")
        db = MagicMock(); db.maintenance.insert_one = AsyncMock(); db.maintenance.delete_one = AsyncMock()
        for collection in (db.bookings, db.proofs, db.booking_slot_locks):
            result = MagicMock(); result.deleted_count = 3; collection.delete_many = AsyncMock(return_value=result)
        await bot._clear_test_clients_once(db)
        db.bookings.delete_many.assert_awaited_once_with({}); db.proofs.delete_many.assert_awaited_once_with({}); db.booking_slot_locks.delete_many.assert_awaited_once_with({})

    async def test_owner_approval_updates_site_booking_and_notifies(self):
        bot = BotProcess("http://127.0.0.1:3002")
        db = MagicMock()
        db.wa_memories.find_one = AsyncMock(return_value={"last_incoming_text": "Aprovar AD-TEST1234", "last_seen": "2026-09-15T10:00:00Z"})
        booking = {"id":"booking-1","code":"AD-TEST1234","proof_id":"proof-1","proof_status":"em_analise","status":"pendente","client_phone":"5511999999999","service_name":"Volume Brasileiro","date":"2026-09-20","time":"15:30"}
        db.bookings.find_one = AsyncMock(return_value=booking)
        claimed = MagicMock(); claimed.matched_count = 1
        db.proofs.update_one = AsyncMock(return_value=claimed); db.bookings.update_one = AsyncMock(); bot._send_whatsapp = AsyncMock(return_value=True)
        with patch.dict(os.environ, {"OWNER_WHATSAPP":"5511888888888"}): await bot._process_owner_review_command(db)
        proof = db.proofs.update_one.await_args.args[1]["$set"]; update = db.bookings.update_one.await_args.args[1]["$set"]
        self.assertEqual(proof["status"], "aprovado"); self.assertEqual(update["payment_status"], "confirmado"); self.assertEqual(update["status"], "confirmada"); self.assertEqual(bot._send_whatsapp.await_count, 2)

    async def test_owner_rejection_keeps_booking_pending(self):
        bot = BotProcess("http://127.0.0.1:3002")
        db = MagicMock(); db.wa_memories.find_one = AsyncMock(return_value={"last_incoming_text":"Rejeitar AD-TEST1234","last_seen":"2026-09-15T10:01:00Z"})
        booking={"id":"booking-1","code":"AD-TEST1234","proof_id":"proof-1","proof_status":"em_analise","client_phone":"5511999999999","service_name":"Volume Brasileiro","date":"2026-09-20","time":"15:30"}
        db.bookings.find_one=AsyncMock(return_value=booking); claimed=MagicMock(); claimed.matched_count=1; db.proofs.update_one=AsyncMock(return_value=claimed); db.bookings.update_one=AsyncMock(); bot._send_whatsapp=AsyncMock(return_value=True)
        with patch.dict(os.environ,{"OWNER_WHATSAPP":"5511888888888"}): await bot._process_owner_review_command(db)
        update=db.bookings.update_one.await_args.args[1]["$set"]; self.assertEqual(update["proof_status"],"rejeitado"); self.assertEqual(update["payment_status"],"rejeitado"); self.assertEqual(update["status"],"pendente")


if __name__ == "__main__": unittest.main()
