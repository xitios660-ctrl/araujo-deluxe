"""Manage the local WhatsApp child process and lightweight booking background jobs."""
import asyncio
import hashlib
import hmac
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)
TZ = ZoneInfo("America/Sao_Paulo")
HISTORY_RESET_MIGRATION = "2026-09-15-clean-test-conversation-history-v1"


def _bot_token():
    explicit = os.environ.get("WHATSAPP_INTERNAL_TOKEN")
    if explicit:
        return explicit
    secret = os.environ.get("JWT_SECRET", "")
    return hmac.new(secret.encode(), b"whatsapp-internal", hashlib.sha256).hexdigest() if secret else ""


def reminder_message(booking):
    name = (booking.get("client_name") or "").strip().split(" ")[0]
    greeting = f"Oi, {name}!" if name else "Oi!"
    return (
        f"{greeting} 💛 Passando para lembrar que seu horário no *Araújo Deluxe* é hoje.\n\n"
        f"✨ {booking.get('service_name', 'Seu procedimento')}\n"
        f"🕐 {booking.get('time', '')}\n"
        f"🔑 Reserva: {booking.get('code', '')}\n\n"
        "Se precisar consultar ou remarcar, pode falar comigo por aqui. Te esperamos! ✨"
    )


class BotProcess:
    def __init__(self, bot_url):
        self.url = urlparse(bot_url)
        self.process = None
        self.task = None
        self.background_task = None

    async def start(self):
        # A separately hosted bot must never spawn a competing local session.
        if self.url.hostname not in ("localhost", "127.0.0.1", "::1"):
            return
        node = shutil.which("node")
        directory = Path(__file__).resolve().parent.parent / "whatsapp-bot"
        if not node or not (directory / "node_modules" / "baileys").exists():
            logger.error("Bot indisponível: execute backend/build.sh com Node.js e a pasta whatsapp-bot presentes")
            return
        if not self.background_task and all(os.environ.get(k) for k in ("MONGO_URL", "DB_NAME", "JWT_SECRET")):
            self.background_task = asyncio.create_task(self._background_jobs())
        self.task = asyncio.create_task(self._supervise(node, directory))

    async def _supervise(self, node, directory):
        env = {
            **os.environ,
            "BOT_PORT": str(self.url.port or 3002),
            "BOT_HOST": self.url.hostname,
            "BACKEND_URL": f"http://127.0.0.1:{os.environ.get('PORT', '8001')}",
        }
        while True:
            try:
                self.process = await asyncio.create_subprocess_exec(node, "index.js", cwd=directory, env=env)
                code = await self.process.wait()
                logger.error("Bot encerrou com código %s; nova tentativa em 10 segundos", code)
            except OSError:
                logger.exception("Falha ao iniciar processo do bot")
            await asyncio.sleep(10)

    async def _background_jobs(self):
        mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = mongo[os.environ["DB_NAME"]]
        try:
            await self._clear_test_conversation_history_once(db)
            while True:
                try:
                    await self._send_due_reminders(db)
                except Exception:
                    logger.exception("Falha no ciclo de lembretes; nova tentativa será feita")
                await asyncio.sleep(300)
        finally:
            mongo.close()

    async def _clear_test_conversation_history_once(self, db):
        marker = {"_id": HISTORY_RESET_MIGRATION, "created_at": datetime.now(TZ).isoformat()}
        try:
            await db.maintenance.insert_one(marker)
        except DuplicateKeyError:
            return
        try:
            memories = await db.wa_memories.delete_many({})
            sessions = await db.wa_sessions.delete_many({})
            logger.info(
                "Histórico de teste do WhatsApp limpo: memories=%s sessions=%s",
                memories.deleted_count,
                sessions.deleted_count,
            )
        except Exception:
            await db.maintenance.delete_one({"_id": HISTORY_RESET_MIGRATION})
            raise

    async def _send_due_reminders(self, db):
        now = datetime.now(TZ)
        # Send once on the appointment day, starting at 07:00 local time.
        if now.hour < 7:
            return
        today = now.strftime("%Y-%m-%d")
        while True:
            booking = await db.bookings.find_one_and_update(
                {
                    "date": today,
                    "status": "confirmada",
                    "reminder_sent_at": {"$exists": False},
                },
                {"$set": {"reminder_sent_at": now.isoformat(), "reminder_status": "sending"}},
                return_document=ReturnDocument.AFTER,
            )
            if not booking:
                return
            ok = await self._send_whatsapp(booking.get("client_phone", ""), reminder_message(booking))
            if ok:
                await db.bookings.update_one(
                    {"id": booking["id"], "reminder_status": "sending"},
                    {"$set": {"reminder_status": "sent"}},
                )
                logger.info("BOOKING_REMINDER_SENT booking_id=%s", booking.get("id", "")[:8])
            else:
                await db.bookings.update_one(
                    {"id": booking["id"], "reminder_status": "sending"},
                    {"$unset": {"reminder_sent_at": "", "reminder_status": ""}},
                )
                return

    async def _send_whatsapp(self, phone, message):
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        token = _bot_token()
        if not digits or not token:
            return False
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"http://127.0.0.1:{self.url.port or 3002}/send",
                    headers={"X-Bot-Token": token},
                    json={"phone": digits, "message": message},
                )
                response.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("Falha ao enviar lembrete de agendamento: %s", exc)
            return False

    async def stop(self):
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
            self.background_task = None
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except ProcessLookupError:
                pass
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
