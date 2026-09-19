"""Manage the local WhatsApp child process and lightweight booking background jobs."""
import asyncio
import hashlib
import hmac
import logging
import os
import re
import shutil
from datetime import datetime, timedelta
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
CLIENT_RESET_MIGRATION = "2026-09-17-clear-agenda-for-retest-v2"
OWNER_COMMAND_RE = re.compile(r"^\s*(aprovar|aprova|aprovado|rejeitar|rejeita|recusar|recusa)\s+(AD[- ]?[A-Za-z0-9]{4,12})\s*$", re.I)


def _bot_token():
    explicit = os.environ.get("WHATSAPP_INTERNAL_TOKEN")
    if explicit:
        return explicit
    secret = os.environ.get("JWT_SECRET", "")
    return hmac.new(secret.encode(), b"whatsapp-internal", hashlib.sha256).hexdigest() if secret else ""


def _digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _canonical_phone(value):
    digits = _digits(value)
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    return digits


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
        self._last_owner_text = None

    async def start(self):
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
        env = {**os.environ, "BOT_PORT": str(self.url.port or 3002), "BOT_HOST": self.url.hostname, "BACKEND_URL": f"http://127.0.0.1:{os.environ.get('PORT', '8001')}"}
        while True:
            try:
                self.process = await asyncio.create_subprocess_exec(node, "-r", "./ai-hook.js", "resilient-runner.js", cwd=directory, env=env)
                code = await self.process.wait()
                logger.error("Bot encerrou com código %s; nova tentativa em 10 segundos", code)
            except OSError:
                logger.exception("Falha ao iniciar processo do bot")
            await asyncio.sleep(10)

    async def _background_jobs(self):
        mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = mongo[os.environ["DB_NAME"]]
        reminder_tick = 0
        try:
            await self._clear_test_conversation_history_once(db)
            await self._clear_test_clients_once(db)
            while True:
                try:
                    await self._process_owner_review_command(db)
                    if reminder_tick <= 0:
                        await self._send_due_reminders(db)
                        reminder_tick = 60
                    reminder_tick -= 1
                except Exception:
                    logger.exception("Falha no ciclo de tarefas do bot; nova tentativa será feita")
                await asyncio.sleep(5)
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
            logger.info("Histórico de teste do WhatsApp limpo: memories=%s sessions=%s", memories.deleted_count, sessions.deleted_count)
        except Exception:
            await db.maintenance.delete_one({"_id": HISTORY_RESET_MIGRATION})
            raise

    async def _clear_test_clients_once(self, db):
        marker = {"_id": CLIENT_RESET_MIGRATION, "created_at": datetime.now(TZ).isoformat()}
        try:
            await db.maintenance.insert_one(marker)
        except DuplicateKeyError:
            return
        try:
            bookings = await db.bookings.delete_many({})
            proofs = await db.proofs.delete_many({})
            locks = await db.booking_slot_locks.delete_many({})
            logger.info("Dados de clientes de teste zerados: bookings=%s proofs=%s locks=%s", bookings.deleted_count, proofs.deleted_count, locks.deleted_count)
        except Exception:
            await db.maintenance.delete_one({"_id": CLIENT_RESET_MIGRATION})
            raise

    async def _process_owner_review_command(self, db):
        owner = _canonical_phone(os.environ.get("OWNER_WHATSAPP", ""))
        if not owner:
            return
        candidates = {owner, "55" + owner}
        memory = await db.wa_memories.find_one({"_id": {"$in": list(candidates)}})
        if not memory:
            return
        text = (memory.get("last_incoming_text") or "").strip()
        seen_key = f"{memory.get('last_seen', '')}|{text}"
        if not text or seen_key == self._last_owner_text:
            return
        self._last_owner_text = seen_key
        match = OWNER_COMMAND_RE.match(text)
        if not match:
            return
        approved = match.group(1).lower().startswith("aprov")
        code = match.group(2).upper().replace(" ", "-")
        booking = await db.bookings.find_one({"code": code})
        if not booking:
            await self._send_whatsapp(os.environ.get("OWNER_WHATSAPP", ""), f"Não encontrei a reserva *{code}*. Confira o código e tente novamente.")
            return
        proof_id = booking.get("proof_id")
        if not proof_id:
            await self._send_whatsapp(os.environ.get("OWNER_WHATSAPP", ""), f"A reserva *{code}* ainda não tem comprovante para analisar.")
            return
        if booking.get("proof_status") != "em_analise":
            status = booking.get("proof_status") or "sem análise"
            await self._send_whatsapp(os.environ.get("OWNER_WHATSAPP", ""), f"O comprovante da reserva *{code}* já está com status *{status}*.")
            return
        now = datetime.now(TZ).isoformat()
        proof_status = "aprovado" if approved else "rejeitado"
        booking_status = "confirmada" if approved else "pendente"
        payment_status = "confirmado" if approved else "rejeitado"
        reviewer = "owner_whatsapp"
        claimed = await db.proofs.update_one({"id": proof_id, "status": "em_analise"}, {"$set": {"status": proof_status, "reviewed_at": now, "reviewed_by": reviewer}})
        if claimed.matched_count == 0:
            await self._send_whatsapp(os.environ.get("OWNER_WHATSAPP", ""), f"O comprovante de *{code}* acabou de ser analisado por outra ação. Atualize o painel.")
            return
        await db.bookings.update_one({"id": booking["id"], "proof_id": proof_id}, {"$set": {"proof_status": proof_status, "proof_reviewed_at": now, "proof_reviewed_by": reviewer, "payment_status": payment_status, "status": booking_status}})
        if approved:
            owner_reply = f"✅ Pagamento da reserva *{code}* aprovado pelo WhatsApp. O site já foi atualizado e a cliente será avisada."
            client_reply = f"✅ *Pagamento aprovado!*\n\nSeu sinal da reserva *{code}* foi confirmado. 💛\n✨ {booking.get('service_name', '')}\n📅 {booking.get('date', '')} às {booking.get('time', '')}\n\nSeu horário está confirmado. Te esperamos!"
        else:
            owner_reply = f"❌ Comprovante da reserva *{code}* rejeitado pelo WhatsApp. O site já foi atualizado."
            client_reply = f"Oi! O comprovante da reserva *{code}* não pôde ser aprovado. 💛\nPode enviar um novo comprovante por aqui ou pelo site para analisarmos novamente."
        await self._send_whatsapp(booking.get("client_phone", ""), client_reply)
        await self._send_whatsapp(os.environ.get("OWNER_WHATSAPP", ""), owner_reply)
        logger.info("OWNER_PROOF_REVIEW booking_id=%s approved=%s", str(booking.get("id", ""))[:8], approved)

    async def _send_due_reminders(self, db):
        now = datetime.now(TZ)
        if now.hour < 7:
            return
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")
        stale_before = (now - timedelta(minutes=5)).isoformat()
        while True:
            # Never send a "your appointment is today" reminder after the
            # appointment time has already passed, for example after a long
            # outage/reconnect. ISO HH:MM strings sort chronologically.
            booking = await db.bookings.find_one_and_update(
                {
                    "date": today,
                    "time": {"$gt": current_time},
                    "status": "confirmada",
                    "$or": [
                        {"reminder_sent_at": {"$exists": False}},
                        {"reminder_status": "sending", "reminder_sent_at": {"$lt": stale_before}},
                    ],
                },
                {"$set": {"reminder_sent_at": now.isoformat(), "reminder_status": "sending"}},
                return_document=ReturnDocument.AFTER,
            )
            if not booking:
                return
            ok = await self._send_whatsapp(booking.get("client_phone", ""), reminder_message(booking))
            if ok:
                await db.bookings.update_one({"id": booking["id"], "reminder_status": "sending"}, {"$set": {"reminder_status": "sent"}})
                logger.info("BOOKING_REMINDER_SENT booking_id=%s", booking.get("id", "")[:8])
            else:
                await db.bookings.update_one({"id": booking["id"], "reminder_status": "sending"}, {"$unset": {"reminder_sent_at": "", "reminder_status": ""}})
                return

    async def _send_whatsapp(self, phone, message):
        digits = _digits(phone)
        token = _bot_token()
        if not digits or not token:
            return False
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(f"http://127.0.0.1:{self.url.port or 3002}/send", headers={"X-Bot-Token": token}, json={"phone": digits, "message": message})
                response.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("Falha ao enviar mensagem automática: %s", exc)
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
