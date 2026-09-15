from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
from bot_process import BotProcess
import bcrypt
import jwt
import qrcode
import io
import re
import base64
import httpx
import unicodedata
import asyncio
import hmac
import hashlib
from pymongo import UpdateOne, ReturnDocument
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional, List

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

TZ = ZoneInfo("America/Sao_Paulo")
JWT_ALGORITHM = "HS256"
PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "https://araujo-deluxe-studio.onrender.com").rstrip("/")
BOOKING_BUFFER_MINUTES = max(0, int(os.environ.get("BOOKING_BUFFER_MINUTES", "0")))
STUDIO_ADDRESS = os.environ.get("STUDIO_ADDRESS", "").strip()

# ---------- Business configuration ----------
WEEKDAY_SLOTS = {
    0: ["09:00", "11:00", "15:30", "17:00"],
    1: ["09:00", "11:00", "15:30", "17:00"],
    2: ["09:00", "11:00", "15:30", "17:00"],
    3: ["09:00", "11:00", "15:30", "17:00"],
    4: ["09:00", "11:00", "15:30", "17:00"],
    5: ["09:00", "11:00", "14:00", "16:00", "18:00"],
    6: [],
}

WEEKDAY_NAMES = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

SERVICES = [
    {"id": "brasileiro", "name": "Volume Brasileiro", "category": "cilios", "price": 100, "deposit": 50, "duration": "2h", "description": "Fios acetinados em formato Y, volume natural e delicado."},
    {"id": "fox", "name": "Fox Eyes", "category": "cilios", "price": 150, "deposit": 50, "duration": "2h30", "description": "Efeito olhar de raposa, alongado e lifting nas extremidades."},
    {"id": "glamour", "name": "Volume Glamour", "category": "cilios", "price": 140, "deposit": 50, "duration": "2h30", "description": "Máximo glamour com fios volumosos e sofisticados."},
    {"id": "egipcio", "name": "Volume Egípcio", "category": "cilios", "price": 120, "deposit": 50, "duration": "2h", "description": "Técnica marcante com espaçamento estratégico e efeito cílios de boneca."},
    {"id": "hibrido", "name": "Volume Híbrido", "category": "cilios", "price": 140, "deposit": 50, "duration": "2h30", "description": "Mescla de fio a fio com volume russo, textura e densidade."},
    {"id": "manutencao-15", "name": "Manutenção 15 dias", "category": "cilios", "price": 80, "deposit": 50, "duration": "1h30", "description": "Reposição de fios para manter o volume impecável (qualquer técnica)."},
    {"id": "manutencao-25", "name": "Manutenção 25 dias", "category": "cilios", "price": 100, "deposit": 50, "duration": "1h30", "description": "Reposição completa para extensões com mais de 20 dias (qualquer técnica)."},
    {"id": "henna", "name": "Design com Henna", "category": "sobrancelhas", "price": 35, "deposit": 50, "duration": "40min", "description": "Design personalizado com aplicação de henna para preencher falhas."},
    {"id": "brow-lamination", "name": "Brow Lamination", "category": "sobrancelhas", "price": 100, "deposit": 50, "duration": "1h", "description": "Alinhamento dos fios para sobrancelhas volumosas e disciplinadas."},
    {"id": "designer-simples", "name": "Design Simples", "category": "sobrancelhas", "price": 25, "deposit": 15, "duration": "30min", "description": "Design de sobrancelhas com pinça, respeitando seu formato natural."},
    {"id": "fibra-vidro", "name": "Alongamento Fibra de Vidro", "category": "unhas", "price": 140, "deposit": 15, "duration": "2h30", "description": "Alongamento resistente e natural com fibra de vidro."},
    {"id": "molde-f1", "name": "Alongamento Molde F1", "category": "unhas", "price": 115, "deposit": 15, "duration": "2h", "description": "Alongamento em gel com molde F1, formato perfeito."},
    {"id": "esmaltacao-gel", "name": "Esmaltação em Gel", "category": "unhas", "price": 45, "deposit": 15, "duration": "1h", "description": "Esmaltação duradoura com brilho intenso por semanas."},
    {"id": "banho-gel", "name": "Banho em Gel", "category": "unhas", "price": 70, "deposit": 15, "duration": "1h30", "description": "Camada de gel sobre a unha natural para força e durabilidade."},
    {"id": "blindagem", "name": "Blindagem", "category": "unhas", "price": 70, "deposit": 15, "duration": "1h30", "description": "Proteção da unha natural contra quebras, ideal para fortalecer."},
]

for service in SERVICES:
    service["deposit"] = min(service.get("deposit", 0), service.get("price", 0))

def effective_deposit(service: dict) -> int:
    price = max(0, int(service.get("price", 0) or 0))
    configured = max(0, int(service.get("deposit", 0) or 0))
    return min(configured, price)


for _service in SERVICES:
    _service["deposit"] = effective_deposit(_service)

SERVICES_BY_ID = {s["id"]: s for s in SERVICES}
BOOKING_STATUSES = ["pendente", "confirmada", "concluida", "cancelada"]

ALLOWED_PROOF_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
}
MAX_PROOF_BYTES = 8 * 1024 * 1024


# ---------- PIX helpers ----------
def _emv(fid: str, value: str) -> str:
    return f"{fid}{len(value):02d}{value}"


def _crc16(data: str) -> str:
    crc = 0xFFFF
    for ch in data.encode("utf-8"):
        crc ^= ch << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def build_pix(amount: float, txid: str) -> str:
    key = os.environ["PIX_KEY"]
    merchant = _emv("00", "br.gov.bcb.pix") + _emv("01", key)
    payload = (
        _emv("00", "01")
        + _emv("26", merchant)
        + _emv("52", "0000")
        + _emv("53", "986")
        + _emv("54", f"{amount:.2f}")
        + _emv("58", "BR")
        + _emv("59", "ARAUJO DELUXE")
        + _emv("60", "SAO PAULO")
        + _emv("62", _emv("05", txid[:25]))
        + "6304"
    )
    return payload + _crc16(payload)


def pix_qr_base64(payload: str) -> str:
    img = qrcode.make(payload, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _digits(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


def canonical_phone(s: str) -> str:
    digits = _digits(s)
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    return digits


def phones_match(a: str, b: str) -> bool:
    left, right = canonical_phone(a), canonical_phone(b)
    return len(left) >= 10 and left == right


# ---------- Auth helpers ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(days=1), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return {"id": str(user["_id"]), "email": user["email"], "name": user.get("name", ""), "role": user.get("role", "admin")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ---------- Models ----------
class LoginInput(BaseModel):
    password: str


class BookingCreate(BaseModel):
    service_id: str
    date: str
    time: str
    client_name: str = Field(min_length=2, max_length=80)
    client_phone: str = Field(min_length=8, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=300)


class StatusUpdate(BaseModel):
    status: str


class CancelInput(BaseModel):
    phone: str


class BlockCreate(BaseModel):
    date: str
    time: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=120)


# ---------- Slot logic ----------
def parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida. Use o formato AAAA-MM-DD.")


def slots_for_date(date_str: str) -> List[str]:
    d = parse_date(date_str)
    return WEEKDAY_SLOTS.get(d.weekday(), [])


def slot_in_past(date_str: str, time_str: str) -> bool:
    now = datetime.now(TZ)
    d = parse_date(date_str)
    h, m = map(int, time_str.split(":"))
    slot_dt = datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)
    return slot_dt <= now


def time_to_minutes(time_str: str) -> int:
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def minutes_to_time(value: int) -> str:
    value = max(0, value)
    return f"{(value // 60) % 24:02d}:{value % 60:02d}"


def duration_to_minutes(value: str) -> int:
    normalized = unicodedata.normalize("NFKD", (value or "").lower())
    t = "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip()
    hours = re.search(r"(\d+)\s*h", t)
    minutes = re.search(r"(\d+)\s*min", t)
    compact_minutes = re.search(r"\d+\s*h\s*(\d{1,2})\b", t)
    total = (int(hours.group(1)) * 60 if hours else 0)
    if minutes:
        total += int(minutes.group(1))
    elif compact_minutes:
        total += int(compact_minutes.group(1))
    return total or 60


def service_duration_minutes(service_id: str) -> int:
    service = SERVICES_BY_ID.get(service_id)
    return duration_to_minutes(service.get("duration", "1h")) if service else 60


def booking_duration_minutes(booking: dict) -> int:
    if booking.get("duration_minutes"):
        return max(1, int(booking["duration_minutes"]))
    return service_duration_minutes(booking.get("service_id", ""))


def booking_interval_minutes(booking: dict) -> tuple:
    start = time_to_minutes(booking["time"])
    return start, start + booking_duration_minutes(booking) + int(booking.get("buffer_minutes", 0) or 0)


def candidate_interval_minutes(service_id: Optional[str], time_str: str) -> tuple:
    start = time_to_minutes(time_str)
    duration = service_duration_minutes(service_id) if service_id else 1
    return start, start + duration + BOOKING_BUFFER_MINUTES


def intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def candidate_lock_slots(date_str: str, time_str: str, service_id: Optional[str] = None) -> List[str]:
    start, end = candidate_interval_minutes(service_id, time_str)
    result = [slot for slot in slots_for_date(date_str) if start <= time_to_minutes(slot) < end]
    return result or [time_str]


async def get_slot_states(date_str: str, service_id: Optional[str] = None) -> List[dict]:
    slots = slots_for_date(date_str)
    bookings = await db.bookings.find({"date": date_str, "status": {"$ne": "cancelada"}}, {"_id": 0}).to_list(100)
    blocks = await db.blocks.find({"date": date_str}, {"_id": 0}).to_list(100)
    day_block = next((b for b in blocks if b.get("time") is None), None)
    timed_blocks = [b for b in blocks if b.get("time")]
    result = []
    for t in slots:
        state = {"time": t, "available": True, "reason": None, "booking": None, "block_id": None}
        if slot_in_past(date_str, t):
            state.update(available=False, reason="passado")
        elif day_block:
            state.update(available=False, reason="bloqueado", block_id=day_block["id"])
        else:
            c_start, c_end = candidate_interval_minutes(service_id, t)
            blocked = next((b for b in timed_blocks if c_start <= time_to_minutes(b["time"]) < c_end), None)
            if blocked:
                state.update(available=False, reason="bloqueado", block_id=blocked["id"])
            else:
                collision = next(
                    (b for b in bookings if intervals_overlap(c_start, c_end, *booking_interval_minutes(b))),
                    None,
                )
                if collision:
                    if collision.get("time") == t:
                        state.update(available=False, reason="agendado", booking=collision)
                    else:
                        _, occupied_until = booking_interval_minutes(collision)
                        state.update(
                            available=False,
                            reason="ocupado",
                            occupied_by={
                                "booking_id": collision.get("id"),
                                "service_name": collision.get("service_name"),
                                "start": collision.get("time"),
                                "until": minutes_to_time(occupied_until),
                            },
                        )
        result.append(state)
    return result


class BookingSlotError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def booking_slot_lock_id(date_str: str, time_str: str) -> str:
    return f"{date_str}|{time_str}"


async def get_day_availability(date_str: str, service_id: Optional[str] = None) -> dict:
    d = parse_date(date_str)
    scheduled_slots = slots_for_date(date_str)
    states = await get_slot_states(date_str, service_id=service_id)
    day_block = await db.blocks.find_one({"date": date_str, "time": None}, {"_id": 0})
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    scheduled_open = len(scheduled_slots) > 0
    is_past = date_str < today

    if not scheduled_open:
        closed_reason = "Domingo — o estúdio não abre neste dia."
    elif day_block:
        closed_reason = day_block.get("reason") or "Dia fechado pela profissional."
    elif is_past:
        closed_reason = "Esta data já passou."
    else:
        closed_reason = None

    return {
        "date": date_str,
        "weekday_name": WEEKDAY_NAMES[d.weekday()],
        "scheduled_open": scheduled_open,
        "open": scheduled_open and not day_block and not is_past,
        "day_blocked": bool(day_block),
        "day_block_id": day_block.get("id") if day_block else None,
        "closed_reason": closed_reason,
        "service_id": service_id,
        "slots": states,
    }


async def acquire_booking_slot(date_str: str, time_str: str, service_id: Optional[str] = None, booking_id: Optional[str] = None) -> List[str]:
    lock_slots = sorted(candidate_lock_slots(date_str, time_str, service_id), key=time_to_minutes)
    inserted = []
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    try:
        for slot in lock_slots:
            await db.booking_slot_locks.insert_one({
                "_id": booking_slot_lock_id(date_str, slot),
                "date": date_str,
                "time": slot,
                "booking_id": booking_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at,
            })
            inserted.append(slot)
    except DuplicateKeyError:
        for slot in inserted:
            await db.booking_slot_locks.delete_one({"_id": booking_slot_lock_id(date_str, slot)})
        raise BookingSlotError("slot_taken", "Este horário acabou de ser reservado. Escolha outro.")
    return lock_slots


async def release_booking_slot(date_str: str, time_str: str, locked_slots: Optional[List[str]] = None):
    for slot in (locked_slots or [time_str]):
        await db.booking_slot_locks.delete_one({"_id": booking_slot_lock_id(date_str, slot)})


async def create_booking_record(
    service_id: str,
    date_str: str,
    time_str: str,
    client_name: str,
    client_phone: str,
    notes: str = "",
) -> dict:
    service = SERVICES_BY_ID.get(service_id)
    if not service:
        raise BookingSlotError("service_not_found", "Serviço não encontrado.")

    phone_digits = canonical_phone(client_phone)
    if len(phone_digits) < 10:
        raise BookingSlotError("invalid_phone", "Informe um WhatsApp válido com DDD.")

    valid_slots = slots_for_date(date_str)
    if not valid_slots:
        raise BookingSlotError("closed_day", "Não atendemos neste dia. Escolha de segunda a sábado.")
    if time_str not in valid_slots:
        raise BookingSlotError("invalid_time", "Horário inválido para este dia.")
    if slot_in_past(date_str, time_str):
        raise BookingSlotError("past", "Este horário já passou. Escolha outro.")

    day = await get_day_availability(date_str, service_id=service_id)
    if not day["open"]:
        raise BookingSlotError("closed_day", day["closed_reason"] or "O estúdio está fechado neste dia.")

    slot = next((s for s in day["slots"] if s["time"] == time_str), None)
    if not slot or not slot["available"]:
        raise BookingSlotError("slot_taken", "Este horário não está mais disponível para este procedimento. Escolha outro.")

    booking_id = str(uuid.uuid4())
    locked_slots = await acquire_booking_slot(date_str, time_str, service_id=service_id, booking_id=booking_id)
    try:
        refreshed = await get_day_availability(date_str, service_id=service_id)
        refreshed_slot = next((s for s in refreshed["slots"] if s["time"] == time_str), None)
        if not refreshed["open"]:
            raise BookingSlotError("closed_day", refreshed["closed_reason"] or "O estúdio está fechado neste dia.")
        if not refreshed_slot or not refreshed_slot["available"]:
            raise BookingSlotError("slot_taken", "Este horário não está mais disponível para este procedimento. Escolha outro.")

        deposit = min(service["deposit"], service["price"])
        booking = {
            "id": booking_id,
            "code": f"AD-{uuid.uuid4().hex[:6].upper()}",
            "service_id": service["id"],
            "service_name": service["name"],
            "category": service["category"],
            "price": service["price"],
            "deposit": deposit,
            "duration": service["duration"],
            "duration_minutes": service_duration_minutes(service_id),
            "buffer_minutes": BOOKING_BUFFER_MINUTES,
            "date": date_str,
            "time": time_str,
            "client_name": client_name.strip(),
            "client_phone": client_phone.strip(),
            "client_phone_digits": phone_digits,
            "notes": notes.strip(),
            "status": "pendente" if deposit > 0 else "confirmada",
            "payment_status": "aguardando_comprovante" if deposit > 0 else "nao_exigido",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bookings.insert_one({**booking})
        logging.getLogger(__name__).info("BOOKING_CREATED booking_id=%s service=%s date=%s time=%s", booking_id[:8], service_id, date_str, time_str)
        if deposit > 0:
            logging.getLogger(__name__).info("PAYMENT_CREATED booking_id=%s amount=%s", booking_id[:8], deposit)
        return booking
    finally:
        await release_booking_slot(date_str, time_str, locked_slots)


# ---------- Public routes ----------# ---------- Public routes ----------
@api_router.get("/")
async def root():
    return {"message": "Araújo Deluxe API"}


@api_router.get("/health")
async def health():
    database_ok = False
    try:
        await db.command("ping")
        database_ok = True
    except Exception:
        pass

    whatsapp = {"connected": False, "has_qr": False, "offline": True}
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            response = await c.get(f"{BOT_URL}/status", headers=BOT_HEADERS)
            if response.status_code == 200:
                data = response.json()
                whatsapp = {
                    "connected": bool(data.get("connected")),
                    "has_qr": bool(data.get("has_qr")),
                    "offline": bool(data.get("offline", not data.get("connected"))),
                }
    except Exception:
        pass

    payload = {"ok": database_ok, "service": "araujo-deluxe-api", "database": database_ok, "whatsapp": whatsapp}
    return JSONResponse(status_code=200 if database_ok else 503, content=payload)


@api_router.get("/services")
async def get_services():
    return SERVICES


@api_router.get("/business-hours")
async def business_hours():
    return {
        "timezone": "America/Sao_Paulo",
        "days": [
            {"weekday": i, "name": WEEKDAY_NAMES[i], "slots": WEEKDAY_SLOTS[i], "open": len(WEEKDAY_SLOTS[i]) > 0}
            for i in range(7)
        ],
    }


@api_router.get("/availability")
async def availability(date: str, service_id: Optional[str] = None):
    if service_id and service_id not in SERVICES_BY_ID:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    day = await get_day_availability(date, service_id=service_id)
    return {
        "date": day["date"],
        "weekday_name": day["weekday_name"],
        "scheduled_open": day["scheduled_open"],
        "open": day["open"],
        "day_blocked": day["day_blocked"],
        "closed_reason": day["closed_reason"],
        "slots": [{"time": s["time"], "available": s["available"], "reason": s["reason"]} for s in day["slots"]],
    }


@api_router.post("/bookings")
async def create_booking(data: BookingCreate):
    try:
        booking = await create_booking_record(
            data.service_id,
            data.date,
            data.time,
            data.client_name,
            data.client_phone,
            data.notes or "",
        )
    except BookingSlotError as exc:
        status = 404 if exc.code == "service_not_found" else 409 if exc.code == "slot_taken" else 400
        raise HTTPException(status_code=status, detail=exc.detail)

    response = {**booking, "whatsapp": os.environ["WHATSAPP_NUMBER"], "payment": None}
    if booking["deposit"] > 0:
        pix_code = build_pix(float(booking["deposit"]), booking["code"].replace("-", ""))
        response["payment"] = {
            "method": "pix",
            "pix_key": os.environ["PIX_KEY"],
            "pix_code": pix_code,
            "qr_base64": pix_qr_base64(pix_code),
            "amount": booking["deposit"],
        }
    return response


@api_router.get("/bookings/lookup")
async def lookup_bookings(q: str):
    q = q.strip()
    if len(q) < 4:
        raise HTTPException(status_code=400, detail="Informe o código completo ou seu telefone com DDD.")
    results = await db.bookings.find({"code": q.upper()}, {"_id": 0}).to_list(20)
    if results:
        return sorted(results, key=lambda b: (b["date"], b["time"]), reverse=True)[:20]
    digits = canonical_phone(q)
    if len(digits) < 10:
        raise HTTPException(status_code=400, detail="Informe o telefone completo com DDD.")
    return await db.bookings.find({"client_phone_digits": digits}, {"_id": 0}).sort([("date", -1), ("time", -1)]).to_list(20)


@api_router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, data: CancelInput):
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    if not phones_match(data.phone, booking["client_phone"]):
        raise HTTPException(status_code=403, detail="Telefone não confere com o agendamento.")
    if booking["status"] not in ["pendente", "confirmada"]:
        raise HTTPException(status_code=400, detail="Este agendamento não pode mais ser cancelado.")
    if slot_in_past(booking["date"], booking["time"]):
        raise HTTPException(status_code=400, detail="Não é possível cancelar um horário que já passou.")
    await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "cancelada"}})
    await release_booking_slot(booking["date"], booking["time"])
    return {**booking, "status": "cancelada"}


@api_router.get("/studio-info")
async def studio_info():
    return {"whatsapp": os.environ["WHATSAPP_NUMBER"], "pix_key": os.environ["PIX_KEY"]}


# ---------- Auth routes ----------
@api_router.post("/auth/login")
async def login(data: LoginInput, request: Request):
    email = os.environ["ADMIN_EMAIL"].lower()
    identifier = f"{request.client.host}:admin"
    attempt, user = await asyncio.gather(
        db.login_attempts.find_one({"identifier": identifier}),
        db.users.find_one({"email": email}),
    )
    now = datetime.now(timezone.utc)
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = datetime.fromisoformat(attempt["locked_until"]) if attempt.get("locked_until") else None
        if locked_until and locked_until > now:
            raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em 15 minutos.")
        await db.login_attempts.delete_one({"identifier": identifier})
    if not user or not await asyncio.to_thread(verify_password, data.password, user["password_hash"]):
        count = (attempt.get("count", 0) + 1) if attempt else 1
        update = {"identifier": identifier, "count": count}
        if count >= 5:
            update["locked_until"] = (now + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="Senha incorreta")
    await db.login_attempts.delete_one({"identifier": identifier})
    token = create_access_token(str(user["_id"]), email)
    return {"access_token": token, "user": {"id": str(user["_id"]), "email": email, "name": user.get("name", ""), "role": user.get("role", "admin")}}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ---------- Admin routes ----------
@api_router.get("/admin/bookings")
async def admin_bookings(status: Optional[str] = None, date: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    if date:
        query["date"] = date
    bookings = await db.bookings.find(query, {"_id": 0}).sort([("date", -1), ("time", 1)]).to_list(500)
    return bookings


@api_router.get("/admin/customers/{phone}/conversation")
async def admin_customer_conversation(phone: str, user: dict = Depends(get_current_user)):
    raw = _digits(phone)
    canonical = canonical_phone(phone)
    candidates = []
    for value in (raw, canonical, f"55{canonical}" if canonical else ""):
        if value and value not in candidates:
            candidates.append(value)

    memory = await db.wa_memories.find_one({"_id": {"$in": candidates}}, {"_id": 0})
    session = await db.wa_sessions.find_one({"phone": {"$in": candidates}}, {"_id": 0})
    history = []
    for item in (memory or {}).get("history", [])[-30:]:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        text_value = (item.get("text") or "").strip()
        if not text_value:
            continue
        history.append({
            "role": role,
            "text": text_value[:1200],
            "at": item.get("at"),
        })

    last_service_id = (memory or {}).get("last_service_id")
    return {
        "phone": phone,
        "name": (memory or {}).get("name"),
        "last_seen": (memory or {}).get("last_seen"),
        "message_count": (memory or {}).get("message_count", 0),
        "last_service_id": last_service_id,
        "last_service_name": SERVICES_BY_ID.get(last_service_id, {}).get("name") if last_service_id else None,
        "session_state": (session or {}).get("state"),
        "history": history,
    }


@api_router.patch("/admin/bookings/{booking_id}")
async def update_booking(booking_id: str, data: StatusUpdate, user: dict = Depends(get_current_user)):
    if data.status not in BOOKING_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")

    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    old_status = booking.get("status")
    locked_slots = []
    if old_status == "cancelada" and data.status != "cancelada":
        day = await get_day_availability(booking["date"], service_id=booking.get("service_id"))
        slot = next((s for s in day["slots"] if s["time"] == booking["time"]), None)
        if not day["open"] or not slot or not slot["available"]:
            raise HTTPException(status_code=409, detail="Não é possível reativar: o período desse procedimento não está mais disponível.")
        try:
            locked_slots = await acquire_booking_slot(
                booking["date"],
                booking["time"],
                service_id=booking.get("service_id"),
                booking_id=booking_id,
            )
        except BookingSlotError as exc:
            raise HTTPException(status_code=409, detail=exc.detail)

    try:
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {
                "status": data.status,
                "status_updated_at": datetime.now(timezone.utc).isoformat(),
                "status_updated_by": user["id"],
            }},
        )
    finally:
        if locked_slots:
            await release_booking_slot(booking["date"], booking["time"], locked_slots)

    if data.status == "cancelada" and old_status != "cancelada":
        logging.getLogger(__name__).info("BOOKING_CANCELLED booking_id=%s source=admin", booking_id[:8])

    return await db.bookings.find_one({"id": booking_id}, {"_id": 0})


@api_router.get("/admin/agenda")
async def admin_agenda(date: str, user: dict = Depends(get_current_user)):
    day = await get_day_availability(date)
    return day


@api_router.post("/admin/blocks")
async def create_block(data: BlockCreate, user: dict = Depends(get_current_user)):
    parse_date(data.date)
    if data.time and data.time not in slots_for_date(data.date):
        raise HTTPException(status_code=400, detail="Horário inválido para este dia")

    active_bookings = await db.bookings.find(
        {"date": data.date, "status": {"$ne": "cancelada"}},
        {"_id": 0},
    ).to_list(100)
    active_booking = None
    if data.time:
        block_minute = time_to_minutes(data.time)
        active_booking = next(
            (
                booking for booking in active_bookings
                if booking_interval_minutes(booking)[0] <= block_minute < booking_interval_minutes(booking)[1]
            ),
            None,
        )
    elif active_bookings:
        active_booking = active_bookings[0]

    if active_booking:
        detail = (
            f"O horário {data.time} cai dentro de um atendimento já agendado. Cancele ou mova a reserva antes de bloquear."
            if data.time
            else "Este dia possui agendamentos. Cancele ou mova as reservas antes de fechar o dia inteiro."
        )
        raise HTTPException(status_code=409, detail=detail)

    existing = await db.blocks.find_one({"date": data.date, "time": data.time})
    if existing:
        raise HTTPException(status_code=409, detail="Já existe um bloqueio para este horário")
    block = {"id": str(uuid.uuid4()), "date": data.date, "time": data.time, "reason": (data.reason or "").strip(), "created_at": datetime.now(timezone.utc).isoformat()}
    await db.blocks.insert_one({**block})
    logging.getLogger(__name__).info("SCHEDULE_BLOCK_CREATED date=%s time=%s", data.date, data.time or "DAY")
    return block


@api_router.delete("/admin/blocks/{block_id}")
async def delete_block(block_id: str, user: dict = Depends(get_current_user)):
    result = await db.blocks.delete_one({"id": block_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bloqueio não encontrado")
    logging.getLogger(__name__).info("SCHEDULE_BLOCK_REMOVED block_id=%s", block_id[:8])
    return {"ok": True}


@api_router.get("/admin/stats")
async def admin_stats(user: dict = Depends(get_current_user)):
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    month_prefix = today[:7]
    today_count, upcoming, month_bookings, pending, clients = await asyncio.gather(
        db.bookings.count_documents({"date": today, "status": {"$ne": "cancelada"}}),
        db.bookings.count_documents({"date": {"$gte": today}, "status": "confirmada"}),
        db.bookings.find({"date": {"$regex": f"^{month_prefix}"}, "status": {"$in": ["confirmada", "concluida"]}}, {"_id": 0, "price": 1}).to_list(1000),
        db.bookings.count_documents({"date": {"$gte": today}, "status": "pendente"}),
        db.bookings.distinct("client_phone"),
    )
    month_revenue = sum(b.get("price", 0) for b in month_bookings)
    return {"today": today_count, "upcoming": upcoming, "pending": pending, "month_revenue": month_revenue, "total_clients": len(clients)}


# ---------- Payment proof & WhatsApp bot ----------
BOT_URL = os.environ["WHATSAPP_BOT_URL"]
BOT_TOKEN = os.environ.get("WHATSAPP_INTERNAL_TOKEN") or hmac.new(
    os.environ["JWT_SECRET"].encode(), b"whatsapp-internal", hashlib.sha256
).hexdigest()
BOT_HEADERS = {"X-Bot-Token": BOT_TOKEN}

def require_bot(request: Request):
    if not hmac.compare_digest(request.headers.get("X-Bot-Token", ""), BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Acesso não autorizado")

async def require_bot_lease(request: Request):
    require_bot(request)
    lease = await db.wa_runtime.find_one({"_id": "lease"})
    if not lease or lease.get("owner") != request.headers.get("X-Bot-Instance") or lease.get("until", "") <= datetime.now(timezone.utc).isoformat():
        raise HTTPException(status_code=409, detail="Sessão em uso ou licença de execução expirada")

class SessionEntry(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    value: Optional[str] = Field(default=None, max_length=1000000)

class SessionBatch(BaseModel):
    entries: List[SessionEntry] = Field(max_length=1000)

@api_router.post("/internal/whatsapp/lease")
async def bot_lease(request: Request, auth=Depends(require_bot)):
    owner = request.headers.get("X-Bot-Instance", "")
    if not re.fullmatch(r"[a-f0-9-]{36}", owner):
        raise HTTPException(status_code=400, detail="Instância inválida")
    now = datetime.now(timezone.utc)
    await db.wa_runtime.update_one({"_id": "lease"}, {"$setOnInsert": {"owner": "", "until": ""}}, upsert=True)
    lease = await db.wa_runtime.find_one_and_update(
        {"_id": "lease", "$or": [{"owner": owner}, {"until": {"$lte": now.isoformat()}}]},
        {"$set": {"owner": owner, "until": (now + timedelta(seconds=60)).isoformat()}},
        return_document=ReturnDocument.AFTER,
    )
    return {"acquired": lease is not None}

@api_router.delete("/internal/whatsapp/lease")
async def release_bot_lease(request: Request, auth=Depends(require_bot)):
    await db.wa_runtime.update_one({"_id": "lease", "owner": request.headers.get("X-Bot-Instance", "")}, {"$set": {"until": ""}})
    return {"ok": True}

@api_router.get("/internal/whatsapp/session")
async def read_bot_session(auth=Depends(require_bot_lease)):
    entries = await db.wa_auth.find({}, {"_id": 0, "key": 1, "value": 1}).to_list(100000)
    return {"entries": entries}

@api_router.post("/internal/whatsapp/session")
async def write_bot_session(data: SessionBatch, auth=Depends(require_bot_lease)):
    # Records contain only ciphertext encrypted by the bot.
    operations = []
    for entry in data.entries:
        if entry.value is None:
            await db.wa_auth.delete_one({"_id": entry.key})
        else:
            operations.append(UpdateOne({"_id": entry.key}, {"$set": {"key": entry.key, "value": entry.value}}, upsert=True))
    if operations:
        await db.wa_auth.bulk_write(operations, ordered=True)
    return {"ok": True}

@api_router.delete("/internal/whatsapp/session")
async def clear_bot_session(auth=Depends(require_bot_lease)):
    # Used exclusively by the explicit manager logout action.
    await db.wa_auth.delete_many({})
    return {"ok": True}

bot_process = BotProcess(BOT_URL)
OWNER_WA = os.environ["OWNER_WHATSAPP"]


class ProofUpload(BaseModel):
    data_base64: str
    mime: str = "image/jpeg"


class WAIncoming(BaseModel):
    phone: str
    text: Optional[str] = ""
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None
    push_name: Optional[str] = None


class WAOutgoingMemory(BaseModel):
    phone: str
    text: str


def fmt_date_br(date_str: str) -> str:
    return parse_date(date_str).strftime("%d/%m/%Y")


async def whatsapp_contact_allowed(phone: str, transactional: bool = False):
    phone = _digits(phone)
    pref = await db.wa_preferences.find_one({"_id": phone})
    if pref and pref.get("blocked"):
        return False
    if phone == _digits(OWNER_WA):
        return True
    if transactional:
        return True
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return bool(pref and pref.get("last_incoming", "") >= since)


async def bot_send_text(phone: str, message: str, transactional: bool = False) -> bool:
    if not await whatsapp_contact_allowed(phone, transactional=transactional):
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            response = await c.post(
                f"{BOT_URL}/send",
                headers=BOT_HEADERS,
                json={"phone": _digits(phone), "message": message},
            )
            response.raise_for_status()
            return True
    except Exception as e:
        logging.getLogger(__name__).warning(f"Bot send falhou: {e}")
        return False


async def bot_send_image(phone: str, caption: str, base64_data: str, mimetype: str) -> bool:
    if not await whatsapp_contact_allowed(phone):
        return False
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            response = await c.post(
                f"{BOT_URL}/send-image",
                headers=BOT_HEADERS,
                json={"phone": _digits(phone), "caption": caption, "base64": base64_data, "mimetype": mimetype},
            )
            response.raise_for_status()
            return True
    except Exception as e:
        logging.getLogger(__name__).warning(f"Bot send-image falhou: {e}")
        return False


def validate_proof_payload(data_base64: str, mime: str) -> str:
    normalized_mime = (mime or "").split(";", 1)[0].strip().lower()
    if normalized_mime not in ALLOWED_PROOF_MIMES:
        raise HTTPException(status_code=400, detail="Formato de comprovante não suportado. Envie JPG, PNG, WEBP, HEIC ou PDF.")
    if not data_base64 or len(data_base64) > 12_000_000:
        raise HTTPException(status_code=400, detail="Arquivo inválido ou muito grande. Envie até 8MB.")
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Arquivo inválido. Tente enviar o comprovante novamente.")
    if not raw or len(raw) > MAX_PROOF_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo inválido ou muito grande. Envie até 8MB.")

    signatures_ok = True
    if normalized_mime == "application/pdf":
        signatures_ok = raw.startswith(b"%PDF")
    elif normalized_mime == "image/jpeg":
        signatures_ok = raw.startswith(b"\xff\xd8\xff")
    elif normalized_mime == "image/png":
        signatures_ok = raw.startswith(b"\x89PNG\r\n\x1a\n")
    elif normalized_mime == "image/webp":
        signatures_ok = len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
    elif normalized_mime in {"image/heic", "image/heif"}:
        signatures_ok = len(raw) >= 12 and raw[4:8] == b"ftyp"

    if not signatures_ok:
        raise HTTPException(status_code=400, detail="O conteúdo do arquivo não corresponde ao formato informado.")
    return normalized_mime


async def store_proof_for_review(booking: dict, data_base64: str, mime: str, source: str, notify_client: bool = True) -> str:
    mime = validate_proof_payload(data_base64, mime)
    now = datetime.now(timezone.utc).isoformat()
    proof = {
        "id": str(uuid.uuid4()),
        "booking_id": booking["id"],
        "mime": mime,
        "data": data_base64,
        "source": source,
        "status": "em_analise",
        "created_at": now,
    }
    await db.proofs.insert_one({**proof})
    attached = await db.bookings.update_one(
        {
            "id": booking["id"],
            "status": "pendente",
            "proof_status": {"$ne": "em_analise"},
        },
        {
            "$set": {
                "proof_id": proof["id"],
                "proof_status": "em_analise",
                "payment_status": "em_analise",
                "proof_uploaded_at": now,
            },
            "$unset": {"proof_reviewed_at": "", "proof_reviewed_by": ""},
        },
    )
    if attached.matched_count == 0:
        await db.proofs.delete_one({"id": proof["id"]})
        current = await db.bookings.find_one({"id": booking["id"]}, {"_id": 0})
        if current and current.get("proof_status") == "em_analise" and current.get("proof_id"):
            return current["proof_id"]
        raise HTTPException(status_code=409, detail="Este agendamento não aceita este comprovante agora.")

    logging.getLogger(__name__).info(
        "RECEIPT_RECEIVED booking_id=%s proof_id=%s source=%s",
        booking["id"][:8], proof["id"][:8], source,
    )

    date_br = fmt_date_br(booking["date"])
    if notify_client:
        client_msg = f"""📥 *Comprovante recebido!*

Seu comprovante foi enviado e está *EM ANÁLISE*.
Assim que ele for aprovado ou não aprovado, eu te aviso por aqui. 💛

📋 {booking['service_name']}
📅 {date_br} às {booking['time']}
🔑 Código: {booking['code']}"""
        await bot_send_text(booking["client_phone"], client_msg, transactional=True)

    owner_msg = f"""📥 *Novo comprovante para analisar!*

👤 {booking['client_name']}
📱 {booking['client_phone']}
📋 {booking['service_name']} · R$ {booking['price']}
📅 {date_br} às {booking['time']}
💰 Sinal: R$ {booking['deposit']}
🔑 Código: {booking['code']}

Abra o painel do gestor para aprovar ou não aprovar."""
    if mime.startswith("image/"):
        await bot_send_image(OWNER_WA, owner_msg, data_base64, mime)
    else:
        await bot_send_text(OWNER_WA, owner_msg)
    return proof["id"]


async def notify_proof_review_result(booking: dict, approved: bool) -> bool:
    date_br = fmt_date_br(booking["date"])
    if approved:
        message = f"""✅ *Pagamento aprovado!*

Seu comprovante foi aprovado e seu horário no *Araújo Deluxe* está *CONFIRMADO* ✨

📋 {booking['service_name']}
📅 {date_br} às {booking['time']}
🔑 Código: {booking['code']}

Te esperamos! 💛"""
    else:
        message = f"""❌ *Comprovante não aprovado*

Não conseguimos aprovar o comprovante enviado. Seu horário ainda não está confirmado.
Por favor, confira o pagamento e envie um novo comprovante pelo site ou aqui no WhatsApp. 💛

📋 {booking['service_name']}
📅 {date_br} às {booking['time']}
🔑 Código: {booking['code']}"""
    return await bot_send_text(booking["client_phone"], message, transactional=True)


@api_router.post("/bookings/{booking_id}/proof")
async def upload_proof(booking_id: str, data: ProofUpload):
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    if booking.get("status") == "confirmada":
        return {
            "ok": True,
            "status": "confirmada",
            "proof_status": booking.get("proof_status") or "aprovado",
            "proof_id": booking.get("proof_id"),
        }
    if booking.get("status") != "pendente":
        raise HTTPException(status_code=400, detail="Este agendamento não aceita mais comprovante.")

    if booking.get("proof_status") == "em_analise" and booking.get("proof_id"):
        return {
            "ok": True,
            "status": "pendente",
            "proof_status": "em_analise",
            "proof_id": booking["proof_id"],
        }

    proof_id = await store_proof_for_review(booking, data.data_base64, data.mime, "site")
    return {"ok": True, "status": "pendente", "proof_status": "em_analise", "proof_id": proof_id}


@api_router.get("/admin/proofs/{proof_id}")
async def get_proof(proof_id: str, user: dict = Depends(get_current_user)):
    proof = await db.proofs.find_one({"id": proof_id}, {"_id": 0})
    if not proof:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    booking = await db.bookings.find_one({"id": proof["booking_id"]}, {"_id": 0})
    if not proof.get("status"):
        proof["status"] = (
            (booking or {}).get("proof_status")
            or ("aprovado" if (booking or {}).get("status") == "confirmada" else "em_analise")
        )
    return proof


async def _get_proof_booking(proof_id: str):
    proof = await db.proofs.find_one({"id": proof_id}, {"_id": 0})
    if not proof:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    booking = await db.bookings.find_one({"id": proof["booking_id"]}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    if booking.get("proof_id") != proof_id:
        raise HTTPException(status_code=409, detail="Este não é mais o comprovante atual deste agendamento.")
    return proof, booking


async def _review_proof(proof_id: str, approved: bool, user: dict):
    proof, booking = await _get_proof_booking(proof_id)
    desired_proof = "aprovado" if approved else "rejeitado"
    desired_booking = "confirmada" if approved else "pendente"
    desired_payment = "confirmado" if approved else "rejeitado"

    if booking.get("proof_status") == desired_proof and (
        (approved and booking.get("status") == "confirmada")
        or (not approved and booking.get("status") == "pendente")
    ):
        return {
            "ok": True,
            "status": desired_booking,
            "proof_status": desired_proof,
            "payment_status": desired_payment,
            "notification_sent": None,
        }

    if booking.get("status") != "pendente" or booking.get("proof_status") != "em_analise":
        raise HTTPException(status_code=409, detail="Este comprovante já foi analisado ou não está mais ativo.")

    now = datetime.now(timezone.utc).isoformat()
    claimed = await db.bookings.update_one(
        {
            "id": booking["id"],
            "proof_id": proof_id,
            "status": "pendente",
            "proof_status": "em_analise",
        },
        {"$set": {
            "status": desired_booking,
            "proof_status": desired_proof,
            "payment_status": desired_payment,
            "proof_reviewed_at": now,
            "proof_reviewed_by": user["id"],
        }},
    )
    if claimed.matched_count == 0:
        current = await db.bookings.find_one({"id": booking["id"]}, {"_id": 0})
        if current and current.get("proof_status") == desired_proof:
            return {
                "ok": True,
                "status": current.get("status"),
                "proof_status": current.get("proof_status"),
                "payment_status": current.get("payment_status"),
                "notification_sent": None,
            }
        raise HTTPException(status_code=409, detail="Este comprovante acabou de ser analisado em outra ação.")

    await db.proofs.update_one(
        {"id": proof_id, "status": "em_analise"},
        {"$set": {"status": desired_proof, "reviewed_at": now, "reviewed_by": user["id"]}},
    )
    event = "PAYMENT_CONFIRMED" if approved else "PAYMENT_FAILED"
    logging.getLogger(__name__).info("%s booking_id=%s proof_id=%s", event, booking["id"][:8], proof_id[:8])
    sent = await notify_proof_review_result(booking, approved)
    return {
        "ok": True,
        "status": desired_booking,
        "proof_status": desired_proof,
        "payment_status": desired_payment,
        "notification_sent": sent,
    }


@api_router.post("/admin/proofs/{proof_id}/approve")
async def approve_proof(proof_id: str, user: dict = Depends(get_current_user)):
    return await _review_proof(proof_id, True, user)


@api_router.post("/admin/proofs/{proof_id}/reject")
async def reject_proof(proof_id: str, user: dict = Depends(get_current_user)):
    return await _review_proof(proof_id, False, user)


@api_router.get("/admin/whatsapp/status")
async def whatsapp_status(user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(f"{BOT_URL}/status", headers=BOT_HEADERS)
            return r.json()
    except Exception:
        return {"connected": False, "has_qr": False, "offline": True}


@api_router.get("/admin/whatsapp/qr")
async def whatsapp_qr(user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(f"{BOT_URL}/qr", headers=BOT_HEADERS)
            qr = r.json().get("qr")
            return {"qr_base64": pix_qr_base64(qr) if qr else None}
    except Exception:
        return {"qr_base64": None}


@api_router.post("/admin/whatsapp/logout")
async def whatsapp_logout(user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{BOT_URL}/logout", headers=BOT_HEADERS)
            return r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Serviço do bot indisponível")


# ---------- WhatsApp conversation engine ----------
MENU_TEXT = (
    "✨ *Araújo Deluxe* ✨\n"
    "Olá! Sou a assistente virtual do estúdio. 💛\n\n"
    "*1* — Agendar horário\n"
    "*2* — Ver horários disponíveis\n"
    "*3* — Enviar comprovante do sinal\n"
    "*4* — Minhas reservas\n\n"
    "Pode me dizer o que precisa ou escolher uma opção.\n"
    "Para interromper mensagens: PARAR. Para retomar: REATIVAR."
)

RESET_WORDS = {"menu", "0", "voltar", "inicio", "início"}


CATEGORY_KEYS = ["cilios", "unhas", "sobrancelhas"]
CATEGORY_LABELS_WA = {"cilios": "Cílios", "unhas": "Unhas", "sobrancelhas": "Sobrancelhas"}

CATEGORY_MENU = (
    "💛 O que você quer agendar?\n\n"
    "*1* — Cílios 👁️\n"
    "*2* — Unhas 💅\n"
    "*3* — Sobrancelhas ✨\n\n"
    "Responda com o *número* da opção. (*0* volta ao menu)"
)


def services_menu_text(category: str) -> str:
    cat_services = [s for s in SERVICES if s["category"] == category]
    lines = [f"📋 *{CATEGORY_LABELS_WA[category]}* — escolha o serviço:\n"]
    for i, s in enumerate(cat_services, 1):
        lines.append(f"*{i}* — {s['name']} · R$ {s['price']} (sinal R$ {s['deposit']})")
    lines.append("\nResponda com o *número* do serviço. (*0* volta ao menu)")
    return "\n".join(lines)


def wa_main_menu_ui() -> dict:
    return {
        "type": "list",
        "title": "Araújo Deluxe ✨",
        "text": "O que você quer fazer?",
        "button_text": "Abrir menu",
        "footer": "Ou simplesmente me escreva do seu jeito 💛",
        "sections": [{
            "title": "Atendimento",
            "rows": [
                {"id": "menu:agendar", "title": "📅 Agendar"},
                {"id": "menu:horarios", "title": "🕐 Ver horários"},
                {"id": "menu:comprovante", "title": "📸 Comprovante"},
                {"id": "menu:reservas", "title": "📒 Minhas reservas"},
                {"id": "menu:site", "title": "🌐 Agendar pelo site"},
            ],
        }],
    }


def wa_category_ui() -> dict:
    return {
        "type": "list",
        "title": "O que você quer fazer? 💛",
        "text": "Escolha uma categoria:",
        "button_text": "Escolher",
        "footer": "Ou escreva o que você quer fazer.",
        "sections": [{
            "title": "Categorias",
            "rows": [
                {"id": "cat:cilios", "title": "👁️ Cílios"},
                {"id": "cat:unhas", "title": "💅 Unhas"},
                {"id": "cat:sobrancelhas", "title": "✨ Sobrancelhas"},
            ],
        }],
    }


def wa_services_ui(category: str) -> dict:
    rows = []
    for service in [s for s in SERVICES if s["category"] == category]:
        rows.append({
            "id": f"svc:{service['id']}",
            "title": service["name"][:24],
            "description": f"R$ {service['price']} · {service['duration']} · sinal R$ {service['deposit']}",
        })
    return {
        "type": "list",
        "title": CATEGORY_LABELS_WA.get(category, "Serviços"),
        "text": "Qual serviço você quer?",
        "button_text": "Ver serviços",
        "footer": "Toque em uma opção ou escreva o nome.",
        "sections": [{"title": "Serviços", "rows": rows}],
    }


def wa_slots_ui(date_str: str, slots: List[str]) -> dict:
    return {
        "type": "list",
        "title": f"Horários · {fmt_date_br(date_str)}",
        "text": "Escolha o melhor horário pra você:",
        "button_text": "Ver horários",
        "footer": "Os horários podem mudar se outra pessoa reservar antes.",
        "sections": [{
            "title": "Disponíveis",
            "rows": [{"id": f"slot:{slot}", "title": f"🕐 {slot}"} for slot in slots],
        }],
    }


def wa_reply(text: str, ui: Optional[dict] = None) -> dict:
    response = {"reply": text}
    if ui:
        response["ui"] = ui
    return response


def parse_br_date(text: str) -> Optional[str]:
    t = text.strip().lower()
    now = datetime.now(TZ)
    if t == "hoje":
        return now.strftime("%Y-%m-%d")
    if t in ("amanha", "amanhã"):
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?$", t)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    year = int(m.group(3)) if m.group(3) else now.year
    if year < 100:
        year += 2000
    try:
        dt = datetime(year, month, day)
    except ValueError:
        return None
    ds = dt.strftime("%Y-%m-%d")
    if not m.group(3) and ds < now.strftime("%Y-%m-%d"):
        try:
            ds = datetime(year + 1, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return ds


def wa_normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", (text or "").lower())
    return " ".join("".join(ch for ch in normalized if not unicodedata.combining(ch)).split())


def wa_service_from_text(text: str) -> Optional[dict]:
    t = wa_normalize(text)
    aliases = {
        "brasileiro": "brasileiro",
        "volume brasileiro": "brasileiro",
        "fox": "fox",
        "fox eyes": "fox",
        "glamour": "glamour",
        "volume glamour": "glamour",
        "egipcio": "egipcio",
        "volume egipcio": "egipcio",
        "hibrido": "hibrido",
        "volume hibrido": "hibrido",
        "manutencao 15": "manutencao-15",
        "manutencao de 15": "manutencao-15",
        "manutencao 25": "manutencao-25",
        "manutencao de 25": "manutencao-25",
        "henna": "henna",
        "brow lamination": "brow-lamination",
        "laminacao": "brow-lamination",
        "design simples": "designer-simples",
        "designer simples": "designer-simples",
        "fibra de vidro": "fibra-vidro",
        "fibra": "fibra-vidro",
        "molde f1": "molde-f1",
        "f1": "molde-f1",
        "esmaltacao em gel": "esmaltacao-gel",
        "esmaltacao gel": "esmaltacao-gel",
        "banho em gel": "banho-gel",
        "banho gel": "banho-gel",
        "blindagem": "blindagem",
    }
    ordered_aliases = sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True)
    for alias, service_id in ordered_aliases:
        if alias in t:
            return SERVICES_BY_ID.get(service_id)

    # Tolerate common WhatsApp typos such as "brasilero" / "glamur".
    words = re.findall(r"[a-z0-9]+", t)
    for alias, service_id in ordered_aliases:
        alias_words = alias.split()
        if len(alias_words) == 1:
            if any(SequenceMatcher(None, word, alias).ratio() >= 0.84 for word in words if len(word) >= 4):
                return SERVICES_BY_ID.get(service_id)
    return None


def wa_clean_name(value: Optional[str]) -> Optional[str]:
    value = re.sub(r"\s+", " ", (value or "").strip())[:80]
    if len(value) < 2 or not any(ch.isalpha() for ch in value):
        return None
    return value


def wa_name_from_text(text: str) -> Optional[str]:
    raw = (text or "").strip()
    match = re.search(
        r"\b(?:meu nome (?:e|é)|me chamo)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{1,50})",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    candidate = re.split(r"[,.;!?]|\s+(?:e|mas|porque|pq|quero|queria|gostaria)\s+", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
    words = candidate.strip().split()
    return wa_clean_name(" ".join(words[:4]))


async def wa_get_memory(phone: str) -> Optional[dict]:
    return await db.wa_memories.find_one({"_id": _digits(phone)}, {"_id": 0})


async def wa_update_memory_profile(phone: str, name: Optional[str] = None, service_id: Optional[str] = None):
    updates = {"last_seen": datetime.now(timezone.utc).isoformat()}
    clean_name = wa_clean_name(name)
    if clean_name:
        updates["name"] = clean_name
    if service_id in SERVICES_BY_ID:
        updates["last_service_id"] = service_id
    await db.wa_memories.update_one(
        {"_id": _digits(phone)},
        {"$set": updates, "$setOnInsert": {"first_seen": updates["last_seen"], "message_count": 0}},
        upsert=True,
    )


async def wa_remember_message(
    phone: str,
    role: str,
    text: str,
    push_name: Optional[str] = None,
    service_id: Optional[str] = None,
    booking_name: Optional[str] = None,
):
    phone = _digits(phone)
    now = datetime.now(timezone.utc).isoformat()
    remembered_text = (text or "").strip()[:1200]
    entry = {"role": role, "text": remembered_text, "at": now}
    set_values = {"last_seen": now}
    if role == "user":
        set_values["last_incoming_text"] = remembered_text
    else:
        set_values["last_outgoing_text"] = remembered_text

    remembered_name = wa_clean_name(booking_name) or wa_clean_name(push_name)
    if remembered_name:
        set_values["name"] = remembered_name
    if service_id in SERVICES_BY_ID:
        set_values["last_service_id"] = service_id

    await db.wa_memories.update_one(
        {"_id": phone},
        {
            "$set": set_values,
            "$setOnInsert": {"first_seen": now},
            "$inc": {"message_count": 1},
            "$push": {"history": {"$each": [entry], "$slice": -80}},
        },
        upsert=True,
    )


def wa_recent_user_messages(memory: Optional[dict], limit: int = 3) -> List[str]:
    history = (memory or {}).get("history") or []
    values = []
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        value = (item.get("text") or "").strip()
        if value and not value.startswith("["):
            values.append(value[:140])
        if len(values) >= limit:
            break
    return list(reversed(values))


def wa_memory_name(memory: Optional[dict]) -> Optional[str]:
    return wa_clean_name((memory or {}).get("name"))


def wa_memory_service(memory: Optional[dict]) -> Optional[dict]:
    return SERVICES_BY_ID.get((memory or {}).get("last_service_id"))


def wa_date_from_sentence(text: str, now: Optional[datetime] = None) -> Optional[str]:
    t = wa_normalize(text)
    now = now or datetime.now(TZ)

    if re.search(r"\bdepois\s+de\s+amanha\b", t):
        return (now + timedelta(days=2)).strftime("%Y-%m-%d")
    if re.search(r"\bamanha\b", t):
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    if re.search(r"\bhoje\b", t):
        return now.strftime("%Y-%m-%d")

    match = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b", t)
    if match:
        return parse_br_date(match.group(0))

    day_match = re.search(r"\b(?:dia|pro dia|para o dia|para dia)\s+(\d{1,2})\b", t)
    if day_match:
        day = int(day_match.group(1))
        year, month = now.year, now.month
        for _ in range(13):
            try:
                candidate = datetime(year, month, day, tzinfo=TZ)
            except ValueError:
                candidate = None
            if candidate and candidate.date() >= now.date():
                return candidate.strftime("%Y-%m-%d")
            month += 1
            if month == 13:
                month = 1
                year += 1

    weekdays = {
        "segunda": 0, "segunda feira": 0,
        "terca": 1, "terca feira": 1,
        "quarta": 2, "quarta feira": 2,
        "quinta": 3, "quinta feira": 3,
        "sexta": 4, "sexta feira": 4,
        "sabado": 5,
        "domingo": 6,
    }
    extra_week = any(p in t for p in ("outra semana", "semana seguinte", "da outra semana"))
    for label, target in sorted(weekdays.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(label)}\b", t):
            delta = (target - now.weekday()) % 7
            if delta == 0:
                delta = 7
            if extra_week:
                delta += 7
            return (now + timedelta(days=delta)).strftime("%Y-%m-%d")
    return None


def wa_daypart_from_text(text: str) -> Optional[str]:
    t = wa_normalize(text)
    if any(p in t for p in ("final da tarde", "fim da tarde", "mais pro final da tarde", "mais para o final da tarde")):
        return "late_afternoon"
    if any(p in t for p in ("de manha", "da manha", "pela manha", "cedo")):
        return "morning"
    if any(p in t for p in ("de tarde", "da tarde", "pela tarde", "a tarde")):
        return "afternoon"
    if any(p in t for p in ("de noite", "da noite", "pela noite", "a noite")):
        return "evening"
    return None


def wa_time_from_sentence(text: str, default_daypart: Optional[str] = None, allow_bare: bool = False) -> Optional[str]:
    t = wa_normalize(text)
    if "meio dia" in t:
        return "12:00"
    if "meia noite" in t:
        return "00:00"

    natural = re.search(r"\b(?:umas?\s+)?(\d{1,2})(?:\s+e\s+meia)?\s+(?:da|de)\s+(manha|tarde|noite)\b", t)
    if natural:
        hour = int(natural.group(1))
        minute = 30 if "e meia" in natural.group(0) else 0
        period = natural.group(2)
        if period in {"tarde", "noite"} and 1 <= hour <= 11:
            hour += 12
        if period == "manha" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            return f"{hour:02d}:{minute:02d}"

    match = re.search(r"\b(\d{1,2})(?::(\d{2})|h(?:(\d{2}))?)\b", t)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or match.group(3) or 0)
        part = wa_daypart_from_text(text) or default_daypart
        if part in {"afternoon", "late_afternoon", "evening"} and 1 <= hour <= 11:
            hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    hinted = re.search(r"\b(?:umas?|por volta das?|la pras?|la para as?|as|das)\s+(\d{1,2})(?::(\d{2}))?\b", t)
    if hinted:
        hour = int(hinted.group(1))
        minute = int(hinted.group(2) or 0)
        part = wa_daypart_from_text(text) or default_daypart
        if part in {"afternoon", "late_afternoon", "evening"} and 1 <= hour <= 11:
            hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    if allow_bare and re.fullmatch(r"\d{1,2}", t):
        hour = int(t)
        if default_daypart in {"afternoon", "late_afternoon", "evening"} and 1 <= hour <= 11:
            hour += 12
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    return None


def filter_slots_by_daypart(slots: List[str], daypart: Optional[str]) -> List[str]:
    if not daypart:
        return list(slots)
    result = []
    for slot in slots:
        minute = time_to_minutes(slot)
        if daypart == "morning" and minute < 12 * 60:
            result.append(slot)
        elif daypart == "afternoon" and 12 * 60 <= minute < 18 * 60:
            result.append(slot)
        elif daypart == "late_afternoon" and 16 * 60 <= minute < 19 * 60:
            result.append(slot)
        elif daypart == "evening" and minute >= 18 * 60:
            result.append(slot)
    return result


def resolve_requested_slot(text: str, slots: List[str], daypart: Optional[str] = None) -> Optional[str]:
    requested = wa_time_from_sentence(text, default_daypart=daypart, allow_bare=True)
    if not requested:
        return None
    if requested in slots:
        return requested
    hour = requested.split(":")[0]
    same_hour = [slot for slot in slots if slot.startswith(hour + ":")]
    if len(same_hour) == 1:
        return same_hour[0]
    return None


def wa_recommended_service(text: str) -> Optional[dict]:
    t = wa_normalize(text)
    if any(x in t for x in ("delicado", "delicada", "natural", "discreto", "leve")):
        return SERVICES_BY_ID["brasileiro"]
    if any(x in t for x in ("gatinho", "raposa", "alongado", "puxado", "fox")):
        return SERVICES_BY_ID["fox"]
    if any(x in t for x in ("cheio", "cheiao", "volumoso", "volume alto", "glamour", "chamativo")):
        return SERVICES_BY_ID["glamour"]
    if any(x in t for x in ("boneca", "marcante", "egipcio")):
        return SERVICES_BY_ID["egipcio"]
    if any(x in t for x in ("equilibrado", "meio termo", "hibrido")):
        return SERVICES_BY_ID["hibrido"]
    if any(x in t for x in ("preencher falha", "preencher falhas", "sobrancelha marcada", "henna")):
        return SERVICES_BY_ID["henna"]
    if any(x in t for x in ("sobrancelha natural", "so limpar", "limpar sobrancelha", "design simples")):
        return SERVICES_BY_ID["designer-simples"]
    if any(x in t for x in ("sobrancelha alinhada", "brow", "lamination", "laminacao")):
        return SERVICES_BY_ID["brow-lamination"]
    if any(x in t for x in ("alongamento resistente", "unha longa", "fibra")):
        return SERVICES_BY_ID["fibra-vidro"]
    if any(x in t for x in ("molde", "f1")):
        return SERVICES_BY_ID["molde-f1"]
    return None




def wa_site_cta(prefix: str = "Se preferir") -> str:
    return f"🌐 {prefix}, você também pode fazer a reserva direto pelo site oficial:\n{PUBLIC_SITE_URL}"


def wa_services_from_text(text: str) -> List[dict]:
    t = wa_normalize(text)
    aliases = [
        ("volume brasileiro", "brasileiro"), ("brasileiro", "brasileiro"),
        ("fox eyes", "fox"), ("fox", "fox"),
        ("volume glamour", "glamour"), ("glamour", "glamour"),
        ("volume egipcio", "egipcio"), ("egipcio", "egipcio"),
        ("volume hibrido", "hibrido"), ("hibrido", "hibrido"),
        ("manutencao de 15", "manutencao-15"), ("manutencao 15", "manutencao-15"),
        ("manutencao de 25", "manutencao-25"), ("manutencao 25", "manutencao-25"),
        ("design com henna", "henna"), ("henna", "henna"),
        ("brow lamination", "brow-lamination"), ("laminacao", "brow-lamination"),
        ("design simples", "designer-simples"), ("designer simples", "designer-simples"),
        ("fibra de vidro", "fibra-vidro"), ("fibra", "fibra-vidro"),
        ("molde f1", "molde-f1"), ("f1", "molde-f1"),
        ("esmaltacao em gel", "esmaltacao-gel"), ("esmaltacao gel", "esmaltacao-gel"),
        ("banho em gel", "banho-gel"), ("banho gel", "banho-gel"),
        ("blindagem", "blindagem"),
    ]
    found = []
    seen = set()
    for alias, service_id in aliases:
        if alias in t and service_id not in seen:
            service = SERVICES_BY_ID.get(service_id)
            if service:
                found.append(service)
                seen.add(service_id)
    return found


def wa_category_from_context(text: str = "", memory: Optional[dict] = None, sdata: Optional[dict] = None) -> Optional[str]:
    t = wa_normalize(text)
    if re.search(r"\bcilios?\b", t):
        return "cilios"
    if re.search(r"\bunhas?\b", t):
        return "unhas"
    if re.search(r"\bsobrancelhas?\b", t):
        return "sobrancelhas"

    sdata = sdata or {}
    if sdata.get("category") in CATEGORY_KEYS:
        return sdata["category"]
    service_id = sdata.get("service_id")
    if service_id in SERVICES_BY_ID:
        return SERVICES_BY_ID[service_id]["category"]

    remembered = wa_memory_service(memory)
    if remembered:
        return remembered["category"]

    last_out = wa_normalize((memory or {}).get("last_outgoing_text", ""))
    last_in = wa_normalize((memory or {}).get("last_incoming_text", ""))
    combined = last_out + " " + last_in
    if "cilio" in combined:
        return "cilios"
    if "unha" in combined:
        return "unhas"
    if "sobrancelha" in combined:
        return "sobrancelhas"
    return None


def wa_service_from_context(text: str, memory: Optional[dict], sdata: Optional[dict] = None) -> Optional[dict]:
    explicit = wa_service_from_text(text)
    if explicit:
        return explicit

    t = wa_normalize(text)
    followup_cues = (
        "ele", "ela", "esse", "essa", "isso", "esse ai", "essa ai", "o mesmo", "a mesma",
        "e o valor", "e o preco", "e quanto", "e o sinal", "e quanto tempo", "me explica",
        "como ele e", "como ela e", "desse", "dessa",
    )
    asks_fact = any(x in t for x in (
        "valor", "preco", "quanto custa", "quanto fica", "quanto e",
        "sinal", "entrada", "quanto tempo", "demora", "duracao",
        "como e", "me explica", "explica", "fica natural", "fica cheio",
    ))
    if not (asks_fact or any(cue in t for cue in followup_cues)):
        return None

    sdata = sdata or {}
    if sdata.get("service_id") in SERVICES_BY_ID:
        return SERVICES_BY_ID[sdata["service_id"]]
    return wa_memory_service(memory)


def wa_services_for_category(category: str, include_maintenance: bool = False) -> List[dict]:
    values = [s for s in SERVICES if s["category"] == category]
    if category == "cilios" and not include_maintenance:
        values = [s for s in values if not s["id"].startswith("manutencao-")]
    return values


def wa_category_prices_text(category: str) -> str:
    values = wa_services_for_category(category, include_maintenance=True)
    lines = [f"💛 *{CATEGORY_LABELS_WA[category]} — valores:*"]
    for service in values:
        lines.append(f"• {service['name']}: R$ {service['price']} · sinal R$ {service['deposit']} · {service['duration']}")
    return "\n".join(lines)


def wa_conversation_hint(state: str) -> str:
    hint = wa_step_hint(state)
    return f"\n\nEu não perdi onde a gente estava, tá? {hint}" if hint else ""


async def wa_conversation_action(
    text: str,
    state: str,
    sdata: dict,
    phone: str,
    memory: Optional[dict],
    set_state,
) -> Optional[dict]:
    t = wa_normalize(text)
    if not t:
        return None

    if any(p in t for p in ("onde fica", "qual endereco", "qual o endereco", "endereco do studio", "localizacao", "como chegar")):
        if STUDIO_ADDRESS:
            return wa_reply(f"📍 Ficamos em: *{STUDIO_ADDRESS}*")
        return wa_reply(
            "Ainda não tenho o endereço cadastrado aqui com segurança 😅 Prefiro não inventar. "
            "Posso avisar a responsável para te passar a localização certinha."
        )

    if any(p in t for p in ("qual procedimento dura mais", "qual dura mais", "mais demorado", "maior duracao")):
        max_minutes = max(service_duration_minutes(s["id"]) for s in SERVICES)
        longest = [s for s in SERVICES if service_duration_minutes(s["id"]) == max_minutes]
        names = ", ".join(f"*{s['name']}*" for s in longest)
        return wa_reply(f"Os procedimentos mais longos são {names}, com cerca de *{longest[0]['duration']}*.")

    if any(p in t for p in ("minha primeira vez", "primeira vez", "nunca fiz")):
        category = wa_category_from_context(text, memory, sdata)
        if category == "cilios" or "cilio" in t:
            service = SERVICES_BY_ID["brasileiro"]
            await wa_update_memory_profile(phone, service_id=service["id"])
            return wa_reply(
                f"Pra primeira vez, eu começaria pelo *{service['name']}* 💛 Ele tem um efeito mais natural e delicado. "
                f"Fica R$ {service['price']}, sinal R$ {service['deposit']} e leva em média {service['duration']}. "
                "Se você quiser algo mais marcante, eu também posso te mostrar outras opções."
            )
        return wa_reply("Claro 💛 É sua primeira vez com *cílios, unhas ou sobrancelhas*? Me fala qual e eu te indico uma opção tranquila.")

    date_mentioned = wa_date_from_sentence(text)
    if date_mentioned and any(p in t for p in ("nao consigo", "nao posso", "nao vou conseguir", "nao vou poder")) and state in {"book_date", "book_time", "book_name"}:
        await set_state("book_date", {"service_id": sdata.get("service_id")})
        return wa_reply("Sem problema 💛 Não vou usar essa data. Qual outro dia fica melhor pra você?")

    # Site intent is explicit and always wins over starting another booking flow.
    if any(p in t for p in (
        "manda o site", "mandar o site", "qual o site", "qual e o site", "tem site",
        "link do site", "me passa o site", "passa o site", "reservar pelo site",
        "agendar pelo site", "marcar pelo site", "quero usar o site",
    )):
        return wa_reply(
            "Claro 💛 Esse é o site oficial do Araújo Deluxe para ver os serviços e fazer a reserva:\n"
            f"{PUBLIC_SITE_URL}"
            + wa_conversation_hint(state)
        )

    explicit_services = wa_services_from_text(text)
    asks_difference = any(p in t for p in (
        "qual a diferenca", "qual diferenca", "diferenca entre", "comparar", "compara",
        "qual e a diferenca", "o que muda",
    ))
    if asks_difference and len(explicit_services) >= 2:
        a, b = explicit_services[0], explicit_services[1]
        await wa_update_memory_profile(phone, service_id=b["id"])
        return wa_reply(
            f"*{a['name']}* 💛 {a['description']} Custa R$ {a['price']}, sinal R$ {a['deposit']} e leva {a['duration']}.\n\n"
            f"*{b['name']}* ✨ {b['description']} Custa R$ {b['price']}, sinal R$ {b['deposit']} e leva {b['duration']}.\n\n"
            "Se você me disser se prefere algo mais natural, alongado ou mais cheio, eu te digo qual dos dois faz mais sentido pra você."
            + wa_conversation_hint(state)
        )

    category = wa_category_from_context(text, memory, sdata)

    if any(p in t for p in ("mais barato", "mais em conta", "menor valor", "mais economico")):
        pool = wa_services_for_category(category, include_maintenance=False) if category else SERVICES
        if pool:
            cheapest = min(pool, key=lambda s: s["price"])
            await wa_update_memory_profile(phone, service_id=cheapest["id"])
            return wa_reply(
                f"O mais em conta{' de ' + CATEGORY_LABELS_WA[category] if category else ''} é *{cheapest['name']}*, "
                f"por *R$ {cheapest['price']}* 💛 O sinal é R$ {cheapest['deposit']} e leva em média {cheapest['duration']}."
                + wa_conversation_hint(state)
            )

    if any(p in t for p in ("mais caro", "maior valor")):
        pool = wa_services_for_category(category, include_maintenance=False) if category else SERVICES
        if pool:
            priciest = max(pool, key=lambda s: s["price"])
            await wa_update_memory_profile(phone, service_id=priciest["id"])
            return wa_reply(
                f"O de maior valor{' em ' + CATEGORY_LABELS_WA[category] if category else ''} é *{priciest['name']}*, "
                f"por *R$ {priciest['price']}*. O sinal é R$ {priciest['deposit']} e leva em média {priciest['duration']}."
                + wa_conversation_hint(state)
            )

    remembered_service = wa_service_from_context(text, memory, sdata)
    if any(p in t for p in ("ta caro", "esta caro", "achei caro", "muito caro", "caro kkk", "pesado no bolso")):
        base = remembered_service or wa_memory_service(memory)
        if base:
            pool = [
                s for s in wa_services_for_category(base["category"], include_maintenance=False)
                if s["price"] < base["price"]
            ]
            if pool:
                alternatives = sorted(pool, key=lambda s: s["price"])[:3]
                options = ", ".join(f"*{s['name']}* (R$ {s['price']})" for s in alternatives)
                return wa_reply(
                    f"Kkkkk eu entendo 😅 Se quiser economizar dentro de *{CATEGORY_LABELS_WA[base['category']]}*, "
                    f"tenho {options}. Quer que eu te explique qual deles fica mais parecido com o que você queria?"
                    + wa_conversation_hint(state)
                )
            return wa_reply(
                "Kkkkk eu entendo 😅 Esse já está entre as opções mais em conta dessa categoria. "
                "Se quiser, eu posso te mostrar os outros valores para comparar."
                + wa_conversation_hint(state)
            )

    wants_recommendation = any(p in t for p in (
        "qual voce recomenda", "qual vc recomenda", "qual voce indica", "qual vc indica",
        "qual e melhor", "qual fica melhor", "qual voce faria", "qual vc faria",
        "to indecisa", "estou indecisa", "nao sei qual escolher", "me ajuda a escolher",
        "qual combina comigo",
    ))
    if wants_recommendation and not wa_recommended_service(text):
        if category == "cilios":
            return wa_reply(
                "Te ajudo sim 💛 Pra cílios, me fala o efeito que você quer: *natural/delicado*, *alongado estilo gatinho*, "
                "*mais cheio/glamouroso* ou *meio-termo*. Aí eu te indico um sem chutar."
                + wa_conversation_hint(state)
            )
        if category == "unhas":
            return wa_reply(
                "Claro 💅 Me diz só o que você procura: *alongamento*, *fortalecer a unha natural* ou só uma *esmaltação mais duradoura*. "
                "Aí eu te indico a opção certa."
                + wa_conversation_hint(state)
            )
        if category == "sobrancelhas":
            return wa_reply(
                "Claro ✨ Você quer *preencher falhas*, deixar os fios *alinhados/levantadinhos* ou só fazer um *design natural*? "
                "Com isso eu já consigo te indicar."
                + wa_conversation_hint(state)
            )
        return wa_reply(
            "Te ajudo sim 💛 Primeiro me diz só onde você está em dúvida: *cílios, unhas ou sobrancelhas*. "
            "Depois eu te faço uma recomendação pelo efeito que você quer."
            + wa_conversation_hint(state)
        )

    # Follow-up "sim" should continue the conversation the bot itself just started.
    if t in {"sim", "aham", "uhum", "pode", "pode sim", "quero", "bora", "vamos", "fechado"}:
        last_out = wa_normalize((memory or {}).get("last_outgoing_text", ""))
        remembered = wa_memory_service(memory)
        if remembered and any(p in last_out for p in (
            "ja vejo um horario", "ja marco", "se voce gostar", "quer continuar por ele",
            "quer marcar", "vamos de", "qual dia voce quer", "qual dia voce prefere",
        )):
            await set_state("book_date", {"service_id": remembered["id"]})
            return wa_reply(
                f"Fechado 💛 Vamos de *{remembered['name']}*. Qual dia você quer? "
                "Pode mandar *amanhã*, *sexta* ou *20/09*.\n\n"
                + wa_site_cta("Se achar mais fácil")
            )

        if "te passo os valores" in last_out or "passo os valores" in last_out:
            last_category = wa_category_from_context("", memory, sdata)
            if last_category:
                return wa_reply(wa_category_prices_text(last_category) + wa_conversation_hint(state))

    if t in {"nao", "não", "agora nao", "agora não", "vou pensar", "depois eu vejo", "vou ver"} and state == "menu":
        return wa_reply(
            "Sem problema 💛 Pode pensar tranquila. Quando quiser voltar, eu lembro do que a gente estava falando.\n\n"
            + wa_site_cta("Se quiser olhar com calma")
        )

    # Explain a remembered/current service when the user uses pronouns.
    if remembered_service and any(p in t for p in (
        "me explica", "explica esse", "explica essa", "como ele e", "como ela e",
        "esse e como", "essa e como", "fica como", "e esse", "e essa",
    )):
        service = remembered_service
        await wa_update_memory_profile(phone, service_id=service["id"])
        return wa_reply(
            f"*{service['name']}* 💛 {service['description']} "
            f"Fica R$ {service['price']}, o sinal é R$ {service['deposit']} e leva em média {service['duration']}."
            + wa_conversation_hint(state)
        )

    # Unknown operational facts should not be invented.
    if any(p in t for p in ("tem estacionamento", "estacionamento", "aceita cartao", "aceita cartão", "aceita dinheiro")):
        return wa_reply(
            "Essa informação eu não tenho configurada com segurança aqui e prefiro não inventar 😅 "
            "Se quiser, eu chamo a responsável para te responder certinho."
            + wa_conversation_hint(state)
        )

    return None


async def wa_select_service_for_booking(service: dict, sdata: dict, phone: str, set_state) -> dict:
    await wa_update_memory_profile(phone, service_id=service["id"])
    held_date = sdata.get("date")
    held_time = sdata.get("time")
    daypart = sdata.get("daypart")

    if held_date:
        day = await get_day_availability(held_date, service_id=service["id"])
        if not day["scheduled_open"] or not day["open"]:
            await set_state("book_date", {"service_id": service["id"], "daypart": daypart})
            return wa_reply(
                f"Esse dia não está disponível para *{service['name']}* 😔 Me fala outra data que eu consulto."
            )

        available = [slot["time"] for slot in day["slots"] if slot["available"]]
        available = filter_slots_by_daypart(available, daypart)
        if held_time:
            if held_time in available:
                await set_state("book_name", {
                    "service_id": service["id"],
                    "date": held_date,
                    "time": held_time,
                    "daypart": daypart,
                })
                return wa_reply(
                    f"Fechado 💛 *{service['name']}* em *{fmt_date_br(held_date)} às {held_time}*. "
                    "Agora me manda seu *nome completo* para confirmar a reserva."
                )
            if not available:
                await set_state("book_date", {"service_id": service["id"], "daypart": daypart})
                return wa_reply(
                    f"Para *{service['name']}* não tenho outro horário que encaixe em {fmt_date_br(held_date)} 😔 "
                    "Qual outro dia fica bom?"
                )

        if available:
            await set_state("book_time", {
                "service_id": service["id"],
                "date": held_date,
                "slots": available,
                "daypart": daypart,
            })
            period = " nesse período" if daypart else ""
            return wa_reply(
                f"Perfeito 💛 Para *{service['name']}* em *{fmt_date_br(held_date)}*{period}, tenho: "
                + ", ".join(available)
                + ". Qual você prefere?",
                wa_slots_ui(held_date, available),
            )

        await set_state("book_date", {"service_id": service["id"], "daypart": daypart})
        return wa_reply(f"Não sobrou horário para *{service['name']}* nesse dia 😔 Qual outro dia você quer?")

    await set_state("book_date", {"service_id": service["id"], "daypart": daypart})
    return wa_reply(
        f"Perfeito 💛 Vamos de *{service['name']}*. Qual dia você prefere? "
        "Pode mandar *amanhã*, *sexta* ou *20/09*."
    )


async def wa_smart_action(
    text: str,
    state: str,
    sdata: dict,
    phone: str,
    memory: Optional[dict],
    set_state,
) -> Optional[dict]:
    t = wa_normalize(text)
    if not t:
        return None

    service = wa_service_from_text(text)
    remembered_service = wa_memory_service(memory)
    if not service and state in {"book_date", "book_time", "book_name"} and sdata.get("service_id") in SERVICES_BY_ID:
        service = SERVICES_BY_ID[sdata["service_id"]]

    category = None
    if re.search(r"\bcilios?\b", t):
        category = "cilios"
    elif re.search(r"\bunhas?\b", t):
        category = "unhas"
    elif re.search(r"\bsobrancelhas?\b", t):
        category = "sobrancelhas"

    if state == "menu" and category and not service:
        await set_state("book_service", {"category": category})
        return wa_reply(
            f"Claro 💛 Aqui estão os serviços de *{CATEGORY_LABELS_WA[category]}*. Escolhe o que você quiser:",
            wa_services_ui(category),
        )
    refers_to_previous = any(x in t for x in (
        "esse", "essa", "esse mesmo", "essa mesma", "pode ser", "quero esse", "quero essa",
        "ele", "ela", "isso", "desse", "dessa", "o mesmo", "a mesma",
    ))

    asks_price = any(x in t for x in ("valor", "preco", "quanto custa", "quanto fica", "quanto e"))
    asks_duration = any(x in t for x in ("quanto tempo", "demora", "duracao"))
    asks_deposit = any(x in t for x in ("sinal", "entrada", "quanto pra reservar", "quanto para reservar"))
    asks_explanation = any(x in t for x in ("me explica", "como e", "explica", "fica como"))

    if not service and (refers_to_previous or asks_price or asks_duration or asks_deposit or asks_explanation):
        service = wa_service_from_context(text, memory, sdata)

    if (asks_price or asks_duration or asks_deposit or asks_explanation) and service:
        await wa_update_memory_profile(phone, service_id=service["id"])
        bits = [f"*{service['name']}*"]
        if asks_price:
            bits.append(f"fica *R$ {service['price']}*")
        if asks_deposit or asks_price:
            bits.append(f"o sinal é *R$ {service['deposit']}*")
        if asks_duration:
            bits.append(f"leva em média *{service['duration']}*")
        if asks_explanation or (not asks_duration and not asks_price and not asks_deposit):
            bits.append(service["description"])
        answer = " 💛 ".join(bits) + "."
        if state != "menu":
            answer += wa_conversation_hint(state)
        else:
            answer += "\n\nSe quiser, eu já vejo um horário pra você. " + wa_site_cta("Ou, se preferir")
        return wa_reply(answer)

    wants_recommendation = any(x in t for x in (
        "qual voce recomenda", "qual vc recomenda", "qual indica", "qual voce indica",
        "qual fica melhor", "qual e melhor", "nao sei qual", "me recomenda", "me indica",
        "quero algo", "queria algo",
    ))
    recommended = wa_recommended_service(text) if wants_recommendation or not service else None
    if recommended:
        await wa_update_memory_profile(phone, service_id=recommended["id"])
        return wa_reply(
            f"Pelo que você me falou, eu iria de *{recommended['name']}* 💛 "
            f"{recommended['description']} Fica R$ {recommended['price']}, sinal R$ {recommended['deposit']} e leva em média {recommended['duration']}. "
            "Se você gostar, eu já vejo um horário.\n\n"
            + wa_site_cta("Se quiser reservar sem continuar a conversa")
        )

    if service and state in {"book_category", "book_service"}:
        return await wa_select_service_for_booking(service, sdata, phone, set_state)

    daypart = wa_daypart_from_text(text) or sdata.get("daypart")
    date_str = wa_date_from_sentence(text)
    if not date_str and state in {"book_time", "avail_pick"} and daypart:
        date_str = sdata.get("date")
    time_str = wa_time_from_sentence(text, default_daypart=daypart)
    wants_booking = any(x in t for x in ("agendar", "marcar", "quero fazer", "quero esse", "quero essa", "pode ser"))
    asks_availability = any(x in t for x in (
        "tem horario", "tem vaga", "horario livre", "disponivel",
        "tem amanha", "tem hoje", "tem para", "tem pro dia", "tem no dia",
    ))

    previous_user = (wa_recent_user_messages(memory, 1) or [""])[-1]
    previous_t = wa_normalize(previous_user)
    previous_asked_availability = any(x in previous_t for x in (
        "tem horario", "tem vaga", "horario livre", "disponivel",
        "horarios", "horário", "vaga",
    ))
    availability_followup = bool(
        date_str and (state in {"avail_pick", "book_time"} or previous_asked_availability) and not wants_booking
    )

    if state in {"book_time", "avail_pick"} and daypart and sdata.get("slots"):
        filtered = filter_slots_by_daypart(sdata.get("slots", []), daypart)
        if not filtered:
            return wa_reply("Nesse período não sobrou horário livre 😔 Quer que eu veja outro período?")
        await set_state(state, {**sdata, "slots": filtered, "daypart": daypart})
        return wa_reply(
            "Nesse período tenho: " + ", ".join(filtered) + ". Qual você prefere?",
            wa_slots_ui(sdata.get("date"), filtered) if sdata.get("date") else None,
        )

    # Duration changes the real availability. Without a procedure, preserve the
    # requested date and ask one short question instead of promising a bad slot.
    if date_str and not service and (asks_availability or availability_followup):
        day = await get_day_availability(date_str)
        if not day["scheduled_open"]:
            return wa_reply(f"Em *{fmt_date_br(date_str)}* é {day['weekday_name']} e o estúdio não abre 😔")
        if not day["open"]:
            return wa_reply(f"Em *{fmt_date_br(date_str)}* o estúdio está fechado 😔 {day['closed_reason'] or ''}")
        await set_state("book_category", {"date": date_str, "daypart": daypart})
        period = " nesse período" if daypart else ""
        return wa_reply(
            f"Consigo olhar *{fmt_date_br(date_str)}*{period} 💛 Só me diz qual procedimento você quer, "
            "porque a duração muda os horários que realmente encaixam.",
            wa_category_ui(),
        )

    if False and date_str and not service and (asks_availability or availability_followup):
        day = await get_day_availability(date_str)
        if not day["scheduled_open"]:
            return wa_reply(
                f"Em *{fmt_date_br(date_str)}* é {day['weekday_name']} e o estúdio não abre 😔 Me fala outro dia."
            )
        if not day["open"]:
            return wa_reply(
                f"Em *{fmt_date_br(date_str)}* o estúdio está *fechado* 😔 "
                f"{day['closed_reason'] or 'Me fala outro dia que eu olho.'}"
            )
        available = [s["time"] for s in day["slots"] if s["available"]]
        if not available:
            return wa_reply(
                f"Pra *{fmt_date_br(date_str)}* ({day['weekday_name']}) já está tudo ocupado 😔 Quer que eu veja outro dia?"
            )

        if time_str:
            if time_str not in available:
                await set_state("avail_pick", {"date": date_str, "slots": available})
                return wa_reply(
                    f"Às *{time_str}* não está livre em {fmt_date_br(date_str)} 😔 "
                    "Tenho: " + ", ".join(available) + "."
                )
            await set_state("book_category", {"date": date_str, "time": time_str})
            return wa_reply(
                f"Tenho *{time_str}* livre em *{fmt_date_br(date_str)}* 💛 "
                "Agora me diz o que você quer fazer:",
                wa_category_ui(),
            )

        await set_state("avail_pick", {"date": date_str, "slots": available})
        return wa_reply(
            f"Tenho sim 💛 Em *{fmt_date_br(date_str)}* ({day['weekday_name']}) estão livres: "
            + ", ".join(available)
            + ". Qual você prefere?\n\n"
            + wa_site_cta("Se preferir escolher e reservar pelo site")
        )

    if service and date_str and (wants_booking or asks_availability or state in {"menu", "book_date", "book_time", "book_name"}):
        day = await get_day_availability(date_str, service_id=service["id"])
        if not day["scheduled_open"]:
            return wa_reply(f"Em *{fmt_date_br(date_str)}* é {day['weekday_name']} e o estúdio não abre 😔 Me fala outro dia.")
        if not day["open"]:
            return wa_reply(f"Em *{fmt_date_br(date_str)}* o estúdio está *fechado/bloqueado* 😔 {day['closed_reason'] or ''} Me fala outro dia.")
        available = filter_slots_by_daypart([s["time"] for s in day["slots"] if s["available"]], daypart)
        if not available:
            suffix = " nesse período" if daypart else ""
            return wa_reply(f"Pra *{fmt_date_br(date_str)}* não tenho horário livre{suffix} para *{service['name']}* 😔 Quer outro período ou outro dia?")
        await wa_update_memory_profile(phone, service_id=service["id"])
        if time_str:
            if time_str not in available:
                return wa_reply(
                    f"Às *{time_str}* não está livre em {fmt_date_br(date_str)} 😔 "
                    "Os horários que tenho são: " + ", ".join(available) + ".",
                    wa_slots_ui(date_str, available),
                )
            await set_state("book_name", {"service_id": service["id"], "date": date_str, "time": time_str})
            return wa_reply(
                f"Tenho sim 😊 *{service['name']}* em *{fmt_date_br(date_str)} às {time_str}*. "
                "Me manda seu *nome completo* que eu fecho a reserva."
            )
        await set_state("book_time", {"service_id": service["id"], "date": date_str, "slots": available})
        return wa_reply(
            f"Tenho horário pra *{service['name']}* em *{fmt_date_br(date_str)}* 💛 Escolhe o melhor:",
            wa_slots_ui(date_str, available),
        )

    if service and wants_booking and state == "menu":
        await wa_update_memory_profile(phone, service_id=service["id"])
        await set_state("book_date", {"service_id": service["id"]})
        return wa_reply(f"Perfeito 💛 Vamos marcar *{service['name']}*. Qual dia você prefere? Pode falar tipo *amanhã*, *sexta* ou *20/09*.")

    if state == "menu" and remembered_service and refers_to_previous:
        await set_state("book_date", {"service_id": remembered_service["id"]})
        return wa_reply(f"Fechado 💛 Vamos de *{remembered_service['name']}*. Qual dia você quer?")

    return None


def wa_contextual_chat_reply(text: str, state: str, memory: Optional[dict] = None) -> Optional[str]:
    t = wa_normalize(text)
    if not t:
        return None

    recent = wa_recent_user_messages(memory, 4)
    last_user = recent[-1] if recent else ""
    last_t = wa_normalize(last_user)

    # Self-deprecating / frustrated messages should be treated as conversation,
    # never as an invalid booking choice.
    if any(x in t for x in (
        "sou burro", "sou burra", "muito burro", "muito burra",
        "nao entendo nada", "nao sei mexer", "nao consigo", "to perdido", "to perdida",
        "ta confuso", "esta confuso", "nao entendi",
    )):
        hint = wa_step_hint(state)
        tail = f" Quando quiser continuar, {hint[:1].lower() + hint[1:]}" if hint else ""
        return (
            "Que isso kkk 😅 Você não é burro não. Se eu deixei confuso, a culpa é minha. "
            "Pode falar comigo do seu jeito que eu tento entender." + tail
        )

    # If the user is roasting the bot, take it lightly and keep the flow.
    if any(x in t for x in ("voce e burro", "vc e burro", "robo burro", "bot burro")):
        hint = wa_step_hint(state)
        tail = f" A gente continua daqui: {hint}" if hint else ""
        return "Kkkkk aí eu mereci 😭 Se eu não entendi, fala do seu jeito que eu tento de novo." + tail

    if t.startswith("desculpa") or t in {"foi mal", "mal ai", "mals"}:
        hint = wa_step_hint(state)
        tail = f" E relaxa, eu ainda lembro onde a gente parou: {hint}" if hint else ""
        return "Relaxa kkk, não precisa pedir desculpa 💛" + tail

    if any(x in t for x in ("o que voce acha", "oq voce acha", "o que vc acha", "oq vc acha", "que voce acha", "que vc acha")):
        if any(x in last_t for x in ("burro", "burra", "nao entendo", "confuso", "perdido", "perdida")):
            return (
                "Acho que você não é burro nada kkk 😅 Esse atendimento que estava engessado demais. "
                "Você pode conversar normal comigo e, quando quiser, a gente continua o agendamento."
            )
        if last_user:
            return f"Sobre o que você falou antes, eu entendi sim 💛 Se quiser me dizer exatamente o que quer saber sobre isso, eu respondo sem te jogar de volta pro menu."
        return "Me fala do que você quer minha opinião que eu te respondo 😊"

    if t in {"sim", "aham", "uhum", "isso", "isso mesmo", "exato"} and state != "menu":
        hint = wa_step_hint(state)
        return ("Perfeito 😊 " + hint) if hint else "Perfeito 😊"

    if t in {"nao", "não", "nada", "deixa", "deixa pra la", "deixa pra lá"} and state != "menu":
        return "Tranquilo 💛 Não vou te prender no agendamento. Quando quiser continuar, é só falar *continuar* ou *menu*."

    return None


def wa_step_hint(state: str) -> str:
    hints = {
        "book_category": "Me diz qual você quer: *cílios, unhas ou sobrancelhas* 💛",
        "book_service": "Pode me mandar o *nome ou número do serviço* que você quer.",
        "book_date": "Agora só preciso da *data*. Pode mandar DD/MM, *hoje* ou *amanhã*.",
        "avail_date": "Qual data você quer consultar? Pode mandar DD/MM, *hoje* ou *amanhã*.",
        "avail_pick": "Escolhe um dos *horários livres* que eu te mostrei, ou me pergunta por outro dia.",
        "book_time": "Escolhe um dos *horários* que eu te mostrei e me manda o número ou o horário.",
        "book_name": "Pra finalizar, me manda seu *nome completo* 😊",
        "cancel_pick": "Me diga qual reserva você quer cancelar.",
        "cancel_confirm_one": "Responda *SIM* para cancelar ou *NÃO* para manter.",
        "cancel_confirm_all": "Responda *SIM, CANCELAR TODOS* ou *NÃO*.",
        "reschedule_pick": "Me diga qual reserva você quer remarcar.",
        "reschedule_date": "Qual nova data você quer?",
        "reschedule_time": "Qual novo horário você prefere?",
    }
    return hints.get(state, "")


async def wa_natural_reply(text: str, state: str = "menu", phone: str = "", memory: Optional[dict] = None) -> Optional[str]:
    t = wa_normalize(text)
    if not t:
        return None

    remembered_name = wa_memory_name(memory)
    remembered_service = wa_memory_service(memory)
    name_mentioned = wa_name_from_text(text)

    if name_mentioned:
        return f"Prazer, *{name_mentioned}* 💛 Vou lembrar do seu nome nas próximas conversas por aqui."

    if any(x in t for x in ("lembra de mim", "voce lembra de mim", "vc lembra de mim", "ja falei com voce", "ja conversei com voce", "o que a gente conversou", "o que eu perguntei antes")):
        bookings = (await wa_find_bookings(phone))[:1] if phone else []
        recent = wa_recent_user_messages(memory, 3)
        pieces = []
        if remembered_name:
            pieces.append(f"lembro de você como *{remembered_name}*")
        if remembered_service:
            pieces.append(f"você já perguntou/olhou *{remembered_service['name']}*")
        if bookings:
            last = bookings[0]
            pieces.append(f"seu agendamento mais recente foi *{last['service_name']}* em {fmt_date_br(last['date'])} às {last['time']}")
        if pieces:
            answer = "Lembro sim 😊💛 " + ", e ".join(pieces) + "."
            if recent:
                answer += "\n\nNas últimas mensagens você falou: " + " | ".join(f"“{item}”" for item in recent[-2:])
            return answer
        return "Ainda não tenho uma conversa antiga sua salva o suficiente pra lembrar 😅 Mas a partir de agora eu vou guardando nosso histórico por aqui 💛"

    if any(x in t for x in ("continua de onde paramos", "continuar de onde paramos", "onde paramos", "retoma de onde paramos", "vamos continuar")):
        if state != "menu":
            return "Claro 💛 Eu lembro onde a gente parou. " + wa_step_hint(state)
        if remembered_service:
            return f"Claro 💛 A última coisa que ficou marcada na minha memória foi *{remembered_service['name']}*. Quer continuar por ele?"
        recent = wa_recent_user_messages(memory, 1)
        if recent:
            return f"Claro 💛 A última coisa que você me falou foi: “{recent[-1]}”. Me diz se quer continuar daí."
        return "Claro 💛 Me dá só uma pista do assunto e eu retomo com você daqui."

    greetings = ("oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "eae", "hey", "hello")
    if t in greetings or any(t.startswith(g + " ") for g in greetings):
        if state == "menu":
            if memory and memory.get("message_count", 0) > 0:
                hello_name = f", {remembered_name.split()[0]}" if remembered_name else ""
                tail = f" Da última vez a gente estava falando de *{remembered_service['name']}*." if remembered_service else ""
                return (
                    f"Oii{hello_name} 💛 Bom te ver por aqui de novo!{tail}\n\n"
                    "Quer continuar nisso ou ver outra coisa? Pode falar comigo do seu jeito 😊\n"
                    "Se preferir fazer a reserva pelo site, é só escolher *Agendar pelo site* nas opções abaixo."
                )
            return (
                "Oii 💛 Tudo bem? Me conta o que você está procurando. "
                "Posso te ajudar a escolher o procedimento, ver valores e horários ou já fazer sua reserva 😊\n\n"
                "Se preferir, também dá para agendar pelo site nas opções abaixo."
            )
        return "Oii 💛 Tô por aqui sim! " + wa_step_hint(state)

    if any(x in t for x in ("tudo bem", "como voce ta", "como vc ta", "ta bem")):
        extra = (" " + wa_step_hint(state)) if state != "menu" else " E você? Se quiser, já me fala o que está procurando que eu te ajudo 😊"
        return "Tudo certinho por aqui 💛" + extra

    if t in {"obrigada", "obrigado", "obg", "vlw", "valeu", "brigada", "brigado"} or "muito obrigada" in t or "muito obrigado" in t:
        extra = (" " + wa_step_hint(state)) if state != "menu" else " Quando quiser marcar, é só me chamar por aqui 💛"
        return "Imaginaaa 😊💛" + extra

    if t in {"kkk", "kkkk", "kkkkk", "rs", "rsrs", "haha", "hahaha"}:
        extra = (" " + wa_step_hint(state)) if state != "menu" else " Me fala o que você quer fazer que eu te ajudo por aqui 😄"
        return "Kkkkk 😄" + extra

    if state != "menu":
        return None

    service = wa_service_from_text(text)
    asks_price = any(x in t for x in ("valor", "preco", "quanto custa", "quanto fica", "quanto e"))
    asks_duration = any(x in t for x in ("quanto tempo", "demora", "duracao"))
    if service and (asks_price or asks_duration or service["id"] in t or wa_normalize(service["name"]) in t):
        return (
            f"Faço sim 💛 *{service['name']}* fica *R$ {service['price']}*. "
            f"O sinal é *R$ {service['deposit']}* e leva em média *{service['duration']}*. "
            f"{service['description']}\n\n"
            "Se quiser, eu já vejo um horário pra você 😊"
        )

    if asks_price:
        return (
            "Claro 💛 Os valores dependem do procedimento. "
            "Me fala qual você quer saber, por exemplo *Volume Brasileiro, Glamour, Henna, Fibra de Vidro* ou outro, que eu te passo valor, sinal e duração certinho."
        )

    if any(x in t for x in ("faz cilios", "trabalha com cilios", "tem cilios")):
        return "Faço sim 😊💛 Tenho Volume Brasileiro, Fox Eyes, Glamour, Egípcio, Híbrido e manutenção. Se me disser qual efeito você gosta, eu te passo os valores."
    if any(x in t for x in ("faz unha", "trabalha com unha", "tem unha")):
        return "Faço sim 💅💛 Tem Fibra de Vidro, Molde F1, Esmaltação em Gel, Banho em Gel e Blindagem. Quer que eu te passe os valores?"
    if any(x in t for x in ("faz sobrancelha", "trabalha com sobrancelha", "tem sobrancelha")):
        return "Faço sim ✨💛 Tem Design com Henna, Brow Lamination e Design Simples. Me fala qual te interessa que eu te passo tudo certinho."

    asks_availability = any(x in t for x in ("tem horario", "tem vaga", "horario livre", "disponivel"))
    if asks_availability:
        return "Consigo olhar pra você sim 💛 Qual dia você quer? Pode mandar *16/09*, *dia 16*, *quarta*, *amanhã* ou *depois de amanhã*."

    if any(x in t for x in ("quero agendar", "quero marcar", "quero fazer", "marca pra mim")):
        return (
            "Bora 😊💛 O que você quer fazer: *cílios, unhas ou sobrancelhas*?\n\n"
            + wa_site_cta("Se preferir fazer tudo pelo site")
        )

    if any(x in t for x in ("quem e voce", "voce e robo", "voce e uma pessoa", "e humano")):
        return "Sou a assistente virtual do Araújo Deluxe 💛 Mas pode falar comigo normal, viu? Eu consigo conversar, passar valores, ver horários e fazer seu agendamento por aqui."

    return None


async def wa_find_bookings(phone: str, only_pending: bool = False) -> List[dict]:
    digits = canonical_phone(phone)
    if len(digits) < 10:
        return []
    query = {"client_phone_digits": digits}
    if only_pending:
        query["status"] = "pendente"
    values = await db.bookings.find(query, {"_id": 0}).to_list(50)
    return sorted(values, key=lambda b: b.get("created_at", ""), reverse=True)


def wa_booking_status_label(booking: dict) -> str:
    if booking.get("status") == "cancelada":
        return "cancelado"
    if booking.get("status") == "concluida":
        return "concluído"
    if booking.get("proof_status") == "em_analise":
        return "comprovante em análise"
    if booking.get("proof_status") == "rejeitado":
        return "comprovante não aprovado"
    if booking.get("status") == "confirmada":
        return "confirmado"
    return "sinal pendente"


def wa_booking_line(booking: dict, index: Optional[int] = None) -> str:
    prefix = f"*{index}.* " if index is not None else ""
    return (
        f"{prefix}*{booking['service_name']}* — {fmt_date_br(booking['date'])} às {booking['time']} "
        f"· {wa_booking_status_label(booking)} · {booking['code']}"
    )


async def wa_active_bookings(phone: str) -> List[dict]:
    bookings = await wa_find_bookings(phone)
    active = []
    for booking in bookings:
        if booking.get("status") not in {"pendente", "confirmada"}:
            continue
        try:
            if slot_in_past(booking["date"], booking["time"]):
                continue
        except Exception:
            continue
        active.append(booking)
    return sorted(active, key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("created_at", "")))


def wa_is_cancel_intent(text: str) -> bool:
    t = wa_normalize(text)
    if any(p in t for p in ("nao quero cancelar", "nao cancela", "nao cancele", "sem cancelar")):
        return False
    phrases = (
        "cancelar", "cancela", "cancele", "cancelamento",
        "desmarcar", "desmarca", "desmarque",
        "nao vou conseguir ir", "nao vou poder ir", "nao posso ir",
        "nao consigo ir", "preciso cancelar", "quero cancelar",
        "quero desmarcar", "tirar meu horario", "tirar meus horarios", "tira meu horario", "tira meus horarios",
    )
    return any(p in t for p in phrases)


def wa_is_reschedule_intent(text: str) -> bool:
    t = wa_normalize(text)
    phrases = (
        "remarcar", "remarca", "reagendar", "reagenda",
        "mudar meu horario", "mudar o horario", "trocar meu horario", "trocar o horario",
        "mudar a data", "trocar a data", "mudar meu agendamento", "trocar meu agendamento",
    )
    return any(p in t for p in phrases)


def wa_is_reservations_intent(text: str) -> bool:
    t = wa_normalize(text)
    phrases = (
        "meus agendamentos", "minhas reservas", "meus horarios marcados",
        "meu horario marcado", "qual meu horario", "qual e meu horario",
        "tenho horario marcado", "tenho algum horario", "meu agendamento",
    )
    return any(p in t for p in phrases)


def wa_is_proof_status_intent(text: str) -> bool:
    t = wa_normalize(text)
    if "comprovante" not in t:
        return False
    return any(p in t for p in (
        "status", "aprovado", "aprovou", "aprovaram", "analise",
        "analisado", "resultado", "como esta", "como ficou",
    ))


def wa_yes(text: str) -> bool:
    t = wa_normalize(text)
    t = " ".join(re.sub(r"[^a-z0-9\s]", " ", t).split())
    return t in {
        "sim", "s", "confirmo", "confirmar", "pode", "pode sim", "isso", "isso mesmo",
        "sim pode", "sim cancelar", "sim cancela", "sim cancelar todos", "pode cancelar",
        "cancela", "cancela sim", "cancela tudo", "cancelar todos",
    } or t.startswith("sim ")


def wa_no(text: str) -> bool:
    t = wa_normalize(text)
    t = " ".join(re.sub(r"[^a-z0-9\s]", " ", t).split())
    return t in {
        "nao", "n", "não", "deixa", "deixa quieto", "deixa pra la", "deixa pra lá",
        "voltar", "menu", "esquece", "nao cancela", "não cancela",
    } or t.startswith("nao ")


def wa_all_scope(text: str) -> bool:
    t = wa_normalize(text)
    return any(p in t for p in (
        "todos", "todas", "tudo", "todos os meus", "todas as minhas",
        "todos meus", "todas minhas",
    ))


async def wa_cancel_booking_record(booking: dict, source: str = "whatsapp") -> bool:
    fresh = await db.bookings.find_one({"id": booking["id"]}, {"_id": 0})
    if not fresh or fresh.get("status") not in {"pendente", "confirmada"}:
        return False
    try:
        if slot_in_past(fresh["date"], fresh["time"]):
            return False
    except Exception:
        return False

    now = datetime.now(timezone.utc).isoformat()
    await db.bookings.update_one(
        {"id": fresh["id"]},
        {"$set": {
            "status": "cancelada",
            "cancelled_at": now,
            "cancelled_source": source,
        }},
    )
    if fresh.get("proof_id") and fresh.get("proof_status") == "em_analise":
        await db.proofs.update_one(
            {"id": fresh["proof_id"]},
            {"$set": {"status": "cancelado", "reviewed_at": now, "reviewed_by": source}},
        )
    await release_booking_slot(fresh["date"], fresh["time"])
    return True


async def wa_move_booking(booking_id: str, new_date: str, new_time: str) -> dict:
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking or booking.get("status") not in {"pendente", "confirmada"}:
        raise BookingSlotError("booking_unavailable", "Esse agendamento não pode mais ser remarcado.")

    if booking["date"] == new_date and booking["time"] == new_time:
        return booking

    day = await get_day_availability(new_date, service_id=booking.get("service_id"))
    if not day["open"]:
        raise BookingSlotError("closed_day", day.get("closed_reason") or "O estúdio está fechado nesse dia.")
    slot = next((s for s in day["slots"] if s["time"] == new_time), None)
    if not slot or not slot["available"]:
        raise BookingSlotError("slot_taken", "Esse horário não está mais disponível.")

    locked = await acquire_booking_slot(new_date, new_time, service_id=booking.get("service_id"), booking_id=booking_id)
    try:
        refreshed = await get_day_availability(new_date, service_id=booking.get("service_id"))
        slot = next((s for s in refreshed["slots"] if s["time"] == new_time), None)
        if not refreshed["open"] or not slot or not slot["available"]:
            raise BookingSlotError("slot_taken", "Esse horário não está mais disponível.")
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {
                "date": new_date,
                "time": new_time,
                "duration_minutes": booking_duration_minutes(booking),
                "buffer_minutes": BOOKING_BUFFER_MINUTES,
                "rescheduled_at": datetime.now(timezone.utc).isoformat(),
                "rescheduled_source": "whatsapp",
            }},
        )
        logging.getLogger(__name__).info("BOOKING_RESCHEDULED booking_id=%s date=%s time=%s", booking_id[:8], new_date, new_time)
    finally:
        await release_booking_slot(new_date, new_time, locked)

    return await db.bookings.find_one({"id": booking_id}, {"_id": 0})


def wa_business_hours_text() -> str:
    lines = ["🕐 *Horários de atendimento:*"]
    for weekday in range(7):
        slots = WEEKDAY_SLOTS.get(weekday, [])
        if slots:
            lines.append(f"• {WEEKDAY_NAMES[weekday]}: {', '.join(slots)}")
        else:
            lines.append(f"• {WEEKDAY_NAMES[weekday]}: fechado")
    return "\n".join(lines)


def wa_generic_prices_text() -> str:
    lines = ["💛 *Serviços e valores:*"]
    for category in CATEGORY_KEYS:
        lines.append(f"\n*{CATEGORY_LABELS_WA[category]}*")
        for service in [s for s in SERVICES if s["category"] == category]:
            lines.append(f"• {service['name']}: R$ {service['price']}")
    lines.append("\nSe quiser, me fala o nome de um procedimento que eu te digo também o sinal e a duração.")
    return "\n".join(lines)


async def wa_resolve_booking_selection(text: str, booking_ids: List[str], phone: str) -> Optional[dict]:
    active = await wa_active_bookings(phone)
    candidates = [b for b in active if b["id"] in set(booking_ids)]
    if not candidates:
        return None

    t = wa_normalize(text)
    if t.isdigit() and 1 <= int(t) <= len(candidates):
        return candidates[int(t) - 1]

    code_match = re.search(r"\bad[- ]?([a-z0-9]{4,10})\b", t)
    if code_match:
        compact = "AD-" + code_match.group(1).upper()
        found = [b for b in candidates if b.get("code", "").upper() == compact]
        if len(found) == 1:
            return found[0]

    service = wa_service_from_text(text)
    date_str = wa_date_from_sentence(text)
    filtered = candidates
    if service:
        filtered = [b for b in filtered if b.get("service_id") == service["id"]]
    if date_str:
        filtered = [b for b in filtered if b.get("date") == date_str]
    return filtered[0] if len(filtered) == 1 else None


async def wa_priority_action(
    text: str,
    state: str,
    sdata: dict,
    phone: str,
    set_state,
) -> Optional[dict]:
    t = wa_normalize(text)

    # Stateful destructive flows come first, so casual words cannot accidentally
    # start a fresh booking while a cancellation is waiting for confirmation.
    if state == "cancel_confirm_all":
        if wa_no(text):
            await set_state("menu")
            return wa_reply("Tudo certo 💛 Não cancelei nada.")
        if wa_yes(text):
            ids = sdata.get("booking_ids", [])
            active = await wa_active_bookings(phone)
            targets = [b for b in active if b["id"] in set(ids)]
            cancelled = 0
            for booking in targets:
                if await wa_cancel_booking_record(booking):
                    cancelled += 1
            await set_state("menu")
            if cancelled:
                return wa_reply(
                    f"✅ Pronto. Cancelei *{cancelled}* agendamento{'s' if cancelled != 1 else ''} "
                    "e liberei os horários novamente no site."
                )
            return wa_reply("Não encontrei nenhum agendamento ativo para cancelar agora.")

        return wa_reply("Só para eu não cancelar nada por engano: responda *SIM, CANCELAR TODOS* ou *NÃO*.")

    if state == "cancel_confirm_one":
        if wa_no(text):
            await set_state("menu")
            return wa_reply("Tudo certo 💛 Mantive seu agendamento.")
        if wa_yes(text):
            booking_id = sdata.get("booking_id")
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) if booking_id else None
            ok = bool(booking and await wa_cancel_booking_record(booking))
            await set_state("menu")
            if ok:
                return wa_reply(
                    f"✅ Cancelei *{booking['service_name']}* de {fmt_date_br(booking['date'])} às {booking['time']}. "
                    "O horário já voltou a ficar disponível no site."
                )
            return wa_reply("Esse agendamento já não estava mais disponível para cancelamento.")
        return wa_reply("Confirma o cancelamento? Responda *SIM* ou *NÃO*.")

    if state == "cancel_pick":
        ids = sdata.get("booking_ids", [])
        if wa_no(text):
            await set_state("menu")
            return wa_reply("Tudo certo 💛 Não cancelei nada.")
        if wa_all_scope(text):
            active = await wa_active_bookings(phone)
            targets = [b for b in active if b["id"] in set(ids)]
            if not targets:
                await set_state("menu")
                return wa_reply("Não encontrei mais nenhum agendamento ativo.")
            await set_state("cancel_confirm_all", {"booking_ids": [b["id"] for b in targets]})
            lines = "\n".join(wa_booking_line(b, i) for i, b in enumerate(targets, 1))
            return wa_reply(
                "Você quer cancelar *TODOS* estes agendamentos?\n\n"
                + lines
                + "\n\nNada foi cancelado ainda. Responda *SIM, CANCELAR TODOS* para confirmar."
            )

        selected = await wa_resolve_booking_selection(text, ids, phone)
        if selected:
            await set_state("cancel_confirm_one", {"booking_id": selected["id"]})
            return wa_reply(
                "Só confirmando antes de cancelar:\n\n"
                + wa_booking_line(selected)
                + "\n\nResponda *SIM* para cancelar ou *NÃO* para manter."
            )
        return wa_reply("Me manda o *número* da reserva que quer cancelar, o código dela, ou escreva *todos*.")

    if state == "reschedule_pick":
        ids = sdata.get("booking_ids", [])
        if wa_no(text):
            await set_state("menu")
            return wa_reply("Tudo certo 💛 Não alterei nenhum agendamento.")
        selected = await wa_resolve_booking_selection(text, ids, phone)
        if selected:
            await set_state("reschedule_date", {"booking_id": selected["id"]})
            return wa_reply(
                f"Vamos remarcar *{selected['service_name']}* de {fmt_date_br(selected['date'])} às {selected['time']} 💛\n\n"
                "Qual nova data você quer? Pode mandar *amanhã*, *sexta* ou *20/09*."
            )
        return wa_reply("Me manda o *número* da reserva que quer remarcar ou o código dela.")

    if state == "reschedule_date":
        booking_id = sdata.get("booking_id")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) if booking_id else None
        if not booking:
            await set_state("menu")
            return wa_reply("Não encontrei mais esse agendamento.")
        date_str = wa_date_from_sentence(text)
        if not date_str:
            return wa_reply("Qual nova data você quer? Pode mandar *DD/MM*, *amanhã* ou o dia da semana.")
        day = await get_day_availability(date_str)
        if not day["open"]:
            return wa_reply(
                f"Em *{fmt_date_br(date_str)}* não consigo remarcar: "
                f"{day.get('closed_reason') or 'o estúdio está fechado'}. Me fala outra data."
            )
        available = [s["time"] for s in day["slots"] if s["available"]]
        if booking["date"] == date_str and booking["time"] not in available:
            available = sorted(set(available + [booking["time"]]))
        if not available:
            return wa_reply(f"Não tem horário livre em *{fmt_date_br(date_str)}* 😔 Me fala outro dia.")
        await set_state("reschedule_time", {"booking_id": booking_id, "date": date_str, "slots": available})
        return wa_reply(
            f"Tenho estes horários em *{fmt_date_br(date_str)}*: " + ", ".join(available) + ".\nQual você prefere?"
        )

    if state == "reschedule_time":
        booking_id = sdata.get("booking_id")
        date_str = sdata.get("date")
        slots = sdata.get("slots", [])
        requested = wa_time_from_sentence(text) or t.replace("h", ":").strip()
        if re.fullmatch(r"\d{1,2}:", requested):
            requested += "00"
        if requested in slots:
            chosen = requested
        elif t.isdigit() and 1 <= int(t) <= len(slots):
            chosen = slots[int(t) - 1]
        else:
            return wa_reply("Me manda um dos horários que eu mostrei, por exemplo *15:30*.")

        try:
            moved = await wa_move_booking(booking_id, date_str, chosen)
        except BookingSlotError as exc:
            await set_state("reschedule_date", {"booking_id": booking_id})
            return wa_reply(f"😔 {exc.detail} Me fala outra data que eu consulto novamente.")
        await set_state("menu")
        return wa_reply(
            f"✅ Remarcado! *{moved['service_name']}* ficou para *{fmt_date_br(moved['date'])} às {moved['time']}*.\n"
            f"🔑 Código: {moved['code']}"
        )

    # High-priority intent: cancellation.
    if wa_is_cancel_intent(text):
        active = await wa_active_bookings(phone)
        if not active:
            return wa_reply("Você não tem nenhum agendamento futuro ativo para cancelar por este número. 💛")

        if wa_all_scope(text):
            await set_state("cancel_confirm_all", {"booking_ids": [b["id"] for b in active]})
            lines = "\n".join(wa_booking_line(b, i) for i, b in enumerate(active, 1))
            return wa_reply(
                "Encontrei estes agendamentos:\n\n"
                + lines
                + "\n\n⚠️ *Nada foi cancelado ainda.*\n"
                "Se quer cancelar todos mesmo, responda *SIM, CANCELAR TODOS*."
            )

        if len(active) == 1:
            booking = active[0]
            await set_state("cancel_confirm_one", {"booking_id": booking["id"]})
            return wa_reply(
                "Encontrei este agendamento:\n\n"
                + wa_booking_line(booking)
                + "\n\nQuer cancelar mesmo? Responda *SIM* ou *NÃO*."
            )

        await set_state("cancel_pick", {"booking_ids": [b["id"] for b in active]})
        lines = "\n".join(wa_booking_line(b, i) for i, b in enumerate(active, 1))
        return wa_reply(
            "Qual destes você quer cancelar?\n\n"
            + lines
            + "\n\nResponda com o *número*, o *código*, ou escreva *todos*."
        )

    # High-priority intent: rescheduling. Never interpret "remarcar" as "marcar".
    if wa_is_reschedule_intent(text):
        active = await wa_active_bookings(phone)
        if not active:
            return wa_reply("Você não tem nenhum agendamento futuro ativo para remarcar por este número.")
        if len(active) == 1:
            booking = active[0]
            await set_state("reschedule_date", {"booking_id": booking["id"]})
            return wa_reply(
                f"Claro 💛 Vamos remarcar *{booking['service_name']}* de {fmt_date_br(booking['date'])} às {booking['time']}.\n"
                "Qual nova data você quer?"
            )
        await set_state("reschedule_pick", {"booking_ids": [b["id"] for b in active]})
        lines = "\n".join(wa_booking_line(b, i) for i, b in enumerate(active, 1))
        return wa_reply("Qual destes você quer remarcar?\n\n" + lines + "\n\nResponda com o *número* ou código.")

    payment_claim = any(p in t for p in (
        "ja paguei", "paguei", "fiz o pix", "acabei de pagar", "transferi",
        "mandei o pix", "pagamento feito",
    ))
    if payment_claim:
        bookings = await wa_find_bookings(phone, only_pending=True)
        if not bookings:
            confirmed = [b for b in await wa_find_bookings(phone) if b.get("status") == "confirmada"]
            if confirmed:
                return wa_reply(f"✅ Seu agendamento *{confirmed[0]['code']}* já consta como confirmado.")
            return wa_reply("Não encontrei uma reserva pendente nesse número. Se você acabou de pagar, me manda o código da reserva.")
        booking = bookings[0]
        if booking.get("proof_status") == "em_analise":
            return wa_reply(
                f"⏳ Vi que o comprovante da reserva *{booking['code']}* já está em análise. "
                "O pagamento só fica confirmado depois da validação, e eu te aviso aqui."
            )
        return wa_reply(
            f"Entendi 💛 A reserva *{booking['code']}* ainda está *aguardando confirmação do pagamento*. "
            "Eu não confirmo só pela mensagem “paguei”. Envie a foto do comprovante aqui para entrar em análise."
        )

    if any(p in t for p in ("vou mandar o comprovante", "vou enviar o comprovante", "mandar comprovante", "enviar comprovante")):
        return wa_reply("Pode mandar a foto do comprovante aqui 💛 Eu associo à reserva e deixo como *em análise* até a validação.")

    if any(p in t for p in ("como pago", "como eu pago", "onde pago", "qual pix", "manda o pix")):
        pending = await wa_find_bookings(phone, only_pending=True)
        if len(pending) == 1:
            booking = pending[0]
            return wa_reply(
                f"Para a reserva *{booking['code']}*, o sinal é *R$ {booking['deposit']}* via PIX. "
                f"Chave: *{os.environ['PIX_KEY']}*. Depois envie o comprovante aqui para análise."
            )

    if wa_is_proof_status_intent(text):
        bookings = await wa_find_bookings(phone)
        with_proof = [b for b in bookings if b.get("proof_id") or b.get("proof_status")]
        if not with_proof:
            return wa_reply("Não encontrei nenhum comprovante enviado por este número.")
        booking = with_proof[0]
        status = booking.get("proof_status")
        if status == "em_analise":
            return wa_reply(
                f"⏳ O comprovante do agendamento *{booking['code']}* está *em análise*. "
                "Assim que houver decisão, eu te aviso por aqui."
            )
        if status == "rejeitado":
            return wa_reply(
                f"❌ O comprovante do agendamento *{booking['code']}* não foi aprovado. "
                "Você pode enviar um novo comprovante."
            )
        if status == "aprovado" or booking.get("status") == "confirmada":
            return wa_reply(f"✅ O pagamento do agendamento *{booking['code']}* está aprovado e confirmado.")
        return wa_reply(f"O agendamento *{booking['code']}* ainda está aguardando o comprovante do sinal.")

    if wa_is_reservations_intent(text):
        bookings = await wa_find_bookings(phone)
        if not bookings:
            return wa_reply("Não encontrei nenhuma reserva neste número. Se quiser, eu já posso agendar uma 💛")
        lines = "\n".join(wa_booking_line(b, i) for i, b in enumerate(bookings[:5], 1))
        return wa_reply("📒 *Seus agendamentos:*\n\n" + lines)

    if any(p in t for p in ("falar com atendente", "falar com uma pessoa", "falar com humano", "atendimento humano", "quero falar com alguem")):
        remembered = await wa_get_memory(phone)
        name = wa_memory_name(remembered) or "Cliente"
        await bot_send_text(
            OWNER_WA,
            f"🙋 *Pedido de atendimento humano*\n\n{name} · {phone}\nMensagem: {text}",
        )
        return wa_reply("Claro 💛 Avisei a responsável que você quer falar com uma pessoa. Enquanto isso, pode me adiantar o que precisa.")

    service = wa_service_from_text(text)
    if not service and any(p in t for p in ("tabela de preco", "tabela de precos", "precos", "valores", "quanto sao os procedimentos")):
        return wa_reply(wa_generic_prices_text())

    if any(p in t for p in ("horario de funcionamento", "horarios de funcionamento", "que horas abre", "que horas fecha", "quais dias atende", "quais dias atendem", "quais dias voces atendem", "abre domingo", "atende domingo", "atendem domingo", "voces atendem domingo")):
        return wa_reply(wa_business_hours_text())

    if not service and any(p in t for p in ("aceita pix", "como paga", "como eu pago", "forma de pagamento", "formas de pagamento", "quanto e o sinal", "valor do sinal")):
        return wa_reply(
            "O sinal é pago por *PIX* e o valor depende do procedimento. 💛 "
            "Me fala qual serviço você quer que eu te digo o valor exato do sinal."
        )

    return None


async def wa_available_slots(date_str: str, service_id: Optional[str] = None) -> List[str]:
    day = await get_day_availability(date_str, service_id=service_id)
    if not day["open"]:
        return []
    return [s["time"] for s in day["slots"] if s["available"]]


async def wa_create_booking(service_id: str, date_str: str, time_str: str, name: str, phone: str) -> dict:
    try:
        return await create_booking_record(
            service_id,
            date_str,
            time_str,
            name,
            _digits(phone),
            "Agendado pelo bot do WhatsApp",
        )
    except BookingSlotError as exc:
        raise ValueError(exc.code)


@api_router.post("/whatsapp/incoming")
async def whatsapp_incoming(data: WAIncoming, auth=Depends(require_bot_lease)):
    phone = _digits(data.phone)
    text = (data.text or "").strip()
    lower = text.lower()

    interactive_map = {
        "menu:agendar": "1",
        "menu:horarios": "2",
        "menu:comprovante": "3",
        "menu:reservas": "4",
        "menu:site": "5",
        "cat:cilios": "1",
        "cat:unhas": "2",
        "cat:sobrancelhas": "3",
    }
    if lower in interactive_map:
        text = interactive_map[lower]
        lower = text
    elif lower.startswith("svc:"):
        service_id = lower.split(":", 1)[1]
        service = SERVICES_BY_ID.get(service_id)
        if service:
            text = service["name"]
            lower = text.lower()
    elif lower.startswith("slot:"):
        text = lower.split(":", 1)[1]
        lower = text
    if lower in {"parar", "sair", "stop", "não quero receber mensagens", "nao quero receber mensagens"}:
        await db.wa_preferences.update_one({"_id": phone}, {"$set": {"blocked": True}}, upsert=True)
        return {"reply": None}
    if lower in {"reativar", "voltar"}:
        await db.wa_preferences.update_one({"_id": phone}, {"$set": {"blocked": False}}, upsert=True)
    preference = await db.wa_preferences.find_one({"_id": phone})
    if preference and preference.get("blocked"):
        return {"reply": None}
    await db.wa_preferences.update_one({"_id": phone}, {"$set": {"last_incoming": datetime.now(timezone.utc).isoformat()}}, upsert=True)

    memory = await wa_get_memory(phone)
    detected_service = wa_service_from_text(text)
    explicit_name = wa_name_from_text(text)
    remembered_input = text or ("[imagem/comprovante]" if data.image_base64 else "[mensagem sem texto]")
    await wa_remember_message(
        phone,
        "user",
        remembered_input,
        push_name=data.push_name,
        service_id=detected_service["id"] if detected_service else None,
        booking_name=explicit_name,
    )
    # Use the memory as it existed before this message to distinguish a returning client.
    memory_for_reply = dict(memory or {})
    if explicit_name:
        memory_for_reply["name"] = explicit_name
    elif data.push_name and not memory_for_reply.get("name"):
        memory_for_reply["name"] = wa_clean_name(data.push_name)
    if detected_service:
        memory_for_reply["last_service_id"] = detected_service["id"]

    session = await db.wa_sessions.find_one({"phone": phone}, {"_id": 0})
    state = session.get("state", "menu") if session else "menu"
    sdata = session.get("data", {}) if session else {}

    async def set_state(new_state: str, new_data: Optional[dict] = None):
        await db.wa_sessions.update_one(
            {"phone": phone},
            {"$set": {"state": new_state, "data": new_data or {}, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    if data.image_base64:
        pending = await wa_find_bookings(phone, only_pending=True)
        if not pending:
            return {"reply": "Não encontrei nenhuma reserva aguardando comprovante para este número. 🤔\nDigite *menu* para agendar um horário."}

        booking = None
        code_match = re.search(r"\bAD[- ]?([A-Za-z0-9]{4,10})\b", text, re.IGNORECASE)
        if code_match:
            wanted = "AD-" + code_match.group(1).upper()
            booking = next((b for b in pending if b.get("code", "").upper() == wanted), None)
        if booking is None and len(pending) == 1:
            booking = pending[0]
        if booking is None:
            lines = "\n".join(wa_booking_line(b, i) for i, b in enumerate(pending[:5], 1))
            return {
                "reply": (
                    "Você tem mais de uma reserva aguardando pagamento e eu não quero colocar o comprovante na errada 😅\n\n"
                    + lines
                    + "\n\nMe diga o *código da reserva* e envie o comprovante novamente."
                )
            }
        if booking.get("proof_status") == "em_analise" and booking.get("proof_id"):
            await set_state("menu")
            return {
                "reply": (
                    "⏳ *Seu comprovante já está em análise.*\n\n"
                    "Assim que ele for aprovado ou não aprovado, eu te aviso por aqui. 💛\n\n"
                    f"🔑 Código: {booking['code']}"
                )
            }
        await store_proof_for_review(booking, data.image_base64, data.image_mime or "image/jpeg", "whatsapp", notify_client=False)
        await set_state("menu")
        return {
            "reply": (
                "📥 *Comprovante recebido!*\n\n"
                "Ele está *EM ANÁLISE* agora. Assim que for aprovado ou não aprovado, eu te aviso por aqui. 💛\n\n"
                f"📋 {booking['service_name']}\n"
                f"📅 {fmt_date_br(booking['date'])} às {booking['time']}\n"
                f"🔑 Código: {booking['code']}"
            )
        }

    normalized_input = wa_normalize(text)

    priority_reply = await wa_priority_action(text, state, sdata, phone, set_state)
    if priority_reply:
        return priority_reply

    if lower in RESET_WORDS or re.search(r"\bmenu\b", normalized_input):
        await set_state("menu")
        return wa_reply(
            "Claro 💛 Voltamos pro começo. Escolhe uma opção abaixo, fala comigo normalmente ou reserva direto pelo site:\n"
            + PUBLIC_SITE_URL,
            wa_main_menu_ui(),
        )

    conversation_reply = await wa_conversation_action(text, state, sdata, phone, memory_for_reply, set_state)
    if conversation_reply:
        return conversation_reply

    smart_reply = await wa_smart_action(text, state, sdata, phone, memory_for_reply, set_state)
    if smart_reply:
        return smart_reply

    contextual_reply = wa_contextual_chat_reply(text, state, memory_for_reply)
    if contextual_reply:
        return wa_reply(contextual_reply)

    natural_reply = await wa_natural_reply(text, state, phone, memory_for_reply)
    if natural_reply:
        greeting = wa_normalize(text)
        show_menu = state == "menu" and (
            greeting in {"oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "eae", "hey", "hello"}
            or greeting.startswith(("oi ", "ola ", "bom dia ", "boa tarde ", "boa noite "))
        )
        return wa_reply(natural_reply, wa_main_menu_ui() if show_menu else None)

    if state == "menu":
        if any(word in lower for word in ("agendar", "marcar", "agendamento")):
            lower = "1"
        elif "dispon" in lower or "horário livre" in lower or "horario livre" in lower:
            lower = "2"
        elif "comprovante" in lower:
            lower = "3"
        elif "minha reserva" in lower or "meus agendamentos" in lower:
            lower = "4"
        if lower.startswith("1"):
            await set_state("book_category")
            return wa_reply("Bora marcar 💛 Primeiro escolhe o que você quer fazer:", wa_category_ui())
        if lower.startswith("2"):
            await set_state("avail_date")
            return {"reply": "📅 Qual data você quer consultar?\nDigite no formato *DD/MM* (ex: 25/12), ou *hoje* / *amanhã*."}
        if lower.startswith("3"):
            return {"reply": "📸 É só enviar a *foto do comprovante* aqui nesta conversa. Ele entra *em análise* e eu te aviso assim que for aprovado ou não aprovado."}
        if lower.startswith("4"):
            bookings = (await wa_find_bookings(phone))[:5]
            if not bookings:
                return {"reply": "Você ainda não tem reservas neste número. Digite *1* para agendar! ✨"}
            emojis = {"pendente": "🕐", "confirmada": "✅", "concluida": "💛", "cancelada": "❌"}
            lines = ["📒 *Suas reservas:*\n"]
            for b in bookings:
                lines.append(
                    f"{emojis.get(b['status'], '•')} {b['service_name']} — {fmt_date_br(b['date'])} às {b['time']} "
                    f"({wa_booking_status_label(b)}) · {b['code']}"
                )
            lines.append("\nDigite *menu* para voltar.")
            return {"reply": "\n".join(lines)}
        if lower.startswith("5"):
            return wa_reply(
                "🌐 Esse é o site oficial do Araújo Deluxe. Por lá você consegue fazer sua reserva direto:\n"
                + PUBLIC_SITE_URL
            )
        return wa_reply(
            "Pode falar comigo normalmente 💛 Eu consigo conversar sobre procedimentos, valores, horários, reservas, "
            "cancelamento e comprovantes. Se preferir fazer a reserva pelo site:\n"
            + PUBLIC_SITE_URL,
            wa_main_menu_ui(),
        )

    if state == "avail_pick":
        date_str = sdata.get("date")
        slots = sdata.get("slots", [])
        requested_time = resolve_requested_slot(text, slots, sdata.get("daypart")) or lower.replace("h", ":").strip()
        if re.fullmatch(r"\d{1,2}:", requested_time):
            requested_time += "00"
        if requested_time in slots:
            lower = str(slots.index(requested_time) + 1)
        if lower.isdigit() and 1 <= int(lower) <= len(slots):
            chosen = slots[int(lower) - 1]
            day = await get_day_availability(date_str)
            current_available = [s["time"] for s in day["slots"] if s["available"]] if day["open"] else []
            if chosen not in current_available:
                fresh = ", ".join(current_available) if current_available else "nenhum horário"
                await set_state("avail_pick", {"date": date_str, "slots": current_available})
                return {"reply": f"😔 O horário *{chosen}* não está mais livre. Agora tenho: {fresh}. Me fala outro."}
            await set_state("book_category", {"date": date_str, "time": chosen})
            return wa_reply(
                f"Perfeito 💛 Separei *{fmt_date_br(date_str)} às {chosen}* como sua escolha. "
                "Agora me diz o procedimento:",
                wa_category_ui(),
            )
        return {
            "reply": "Me fala um dos horários que eu mostrei, por exemplo *15:30*. "
                     "Se quiser comparar outro dia, pode mandar *dia 17*, *quarta* ou outra data."
        }

    if state == "book_category":
        direct_service = wa_service_from_text(text)
        if direct_service:
            return await wa_select_service_for_booking(direct_service, sdata, phone, set_state)
        if "cilio" in lower or "cílio" in lower:
            lower = "1"
        elif "unha" in lower:
            lower = "2"
        elif "sobrancelha" in lower:
            lower = "3"
        if lower.isdigit() and 1 <= int(lower) <= 3:
            cat = CATEGORY_KEYS[int(lower) - 1]
            await set_state("book_service", {**sdata, "category": cat})
            return wa_reply(
                f"Perfeito 💛 Agora escolhe o serviço de *{CATEGORY_LABELS_WA[cat]}*:",
                wa_services_ui(cat),
            )
        return wa_reply(
            "Não consegui ligar essa mensagem a uma categoria 😅 Mas não perdi a conversa. "
            "Você pode escrever algo tipo *quero cílios naturais*, *quero alongar as unhas* ou *quero fazer a sobrancelha*. "
            "Se preferir reservar pelo site: " + PUBLIC_SITE_URL,
            wa_category_ui(),
        )

    if state == "book_service":
        cat_services = [s for s in SERVICES if s["category"] == sdata.get("category")]
        direct_service = wa_service_from_text(text)
        if direct_service and direct_service["category"] == sdata.get("category"):
            return await wa_select_service_for_booking(direct_service, sdata, phone, set_state)
        named = [i for i, service in enumerate(cat_services, 1) if lower == service["name"].lower()]
        if len(named) == 1:
            lower = str(named[0])
        if lower.isdigit() and 1 <= int(lower) <= len(cat_services):
            service = cat_services[int(lower) - 1]
            return await wa_select_service_for_booking(service, sdata, phone, set_state)
        return wa_reply(
            "Não peguei qual serviço você quis 😅 Mas pode perguntar sobre qualquer um deles, comparar preços ou me dizer o efeito que você quer. "
            "Eu continuo daqui sem apagar o que você já escolheu.",
            wa_services_ui(sdata.get("category")) if sdata.get("category") in CATEGORY_KEYS else wa_category_ui(),
        )

    if state in ("book_date", "avail_date"):
        ds = wa_date_from_sentence(text) or parse_br_date(text)
        if not ds:
            return {"reply": "Data inválida. 😅 Digite no formato *DD/MM* (ex: 25/12), ou *hoje* / *amanhã*."}
        if ds < datetime.now(TZ).strftime("%Y-%m-%d"):
            return {"reply": "Essa data já passou. 😅 Escolha uma data a partir de hoje."}
        day = await get_day_availability(ds, service_id=sdata.get("service_id") if state == "book_date" else None)
        if not day["scheduled_open"]:
            return {"reply": "Aos domingos o estúdio não abre. 😔 Escolha outra data (segunda a sábado)."}
        if not day["open"]:
            return {"reply": f"🚫 O estúdio está *fechado* em {fmt_date_br(ds)} ({day['weekday_name']}).\n{day['closed_reason'] or 'Escolha outra data.'}"}
        available = [s["time"] for s in day["slots"] if s["available"]]
        weekday = day["weekday_name"]
        if state == "avail_date":
            await set_state("book_category", {"date": ds})
            return wa_reply(
                f"Consigo olhar *{fmt_date_br(ds)}* 💛 Qual procedimento você quer? "
                "A duração muda os horários que realmente encaixam.",
                wa_category_ui(),
            )
        available = filter_slots_by_daypart(available, sdata.get("daypart"))
        if not available:
            return {"reply": f"😔 Não tenho horário livre para esse procedimento em *{fmt_date_br(ds)}* ({weekday}) nesse período. Tente outro período ou outra data!"}
        await set_state("book_time", {**sdata, "date": ds, "slots": available})
        return wa_reply(
            f"🕐 Horários livres em *{fmt_date_br(ds)}* ({weekday}). Escolhe um:",
            wa_slots_ui(ds, available),
        )

    if state == "book_time":
        slots = sdata.get("slots", [])
        requested_time = resolve_requested_slot(text, slots, sdata.get("daypart")) or lower.replace("h", ":").strip()
        if re.fullmatch(r"\d{1,2}:", requested_time):
            requested_time += "00"
        if requested_time in slots:
            lower = str(slots.index(requested_time) + 1)
        if lower.isdigit() and 1 <= int(lower) <= len(slots):
            await set_state("book_name", {**sdata, "time": slots[int(lower) - 1]})
            return {"reply": "Perfeito! 🥰 Agora me diga seu *nome completo* para finalizar a reserva."}
        return wa_reply(
            "Não peguei o horário 😅 Toca em um dos disponíveis abaixo:",
            wa_slots_ui(sdata.get("date"), slots) if sdata.get("date") and slots else None,
        )

    if state == "book_name":
        clean_booking_name = wa_clean_name(text)
        name_words = (clean_booking_name or "").split()
        if (
            not clean_booking_name
            or len(name_words) > 4
            or any(word in wa_normalize(text) for word in ("marcar", "agendar", "horario", "pagar", "comprovante", "site"))
        ):
            return {"reply": "Só falta seu *nome* 😊 Pode me mandar seu nome e sobrenome."}
        try:
            await wa_update_memory_profile(phone, name=clean_booking_name, service_id=sdata.get("service_id"))
            booking = await wa_create_booking(sdata["service_id"], sdata["date"], sdata["time"], clean_booking_name, phone)
        except ValueError as exc:
            await set_state("book_date", {"service_id": sdata.get("service_id")})
            if str(exc) == "closed_day":
                return {"reply": "🚫 Esse dia foi fechado enquanto a gente estava agendando. Não criei a reserva.\n\n📅 Me diga outra data (*DD/MM*, *hoje* ou *amanhã*)."}
            return {"reply": "😔 Esse horário acabou de ser reservado ou bloqueado. Não criei reserva duplicada.\n\n📅 Digite outra data (*DD/MM*, *hoje* ou *amanhã*)."}
        pix_code = build_pix(float(booking["deposit"]), booking["code"].replace("-", ""))
        await set_state("menu")
        return {
            "reply": (
                "🎉 *Reserva criada!*\n\n"
                f"📋 {booking['service_name']}\n"
                f"📅 {fmt_date_br(booking['date'])} às {booking['time']}\n"
                f"💵 Total: R$ {booking['price']} · Sinal: R$ {booking['deposit']}\n"
                f"🔑 Código: {booking['code']}\n\n"
                f"Para confirmar, pague o sinal de *R$ {booking['deposit']}* via PIX:\n\n"
                f"🔑 Chave PIX: {os.environ['PIX_KEY']}\n\n"
                "Ou copie o código abaixo (PIX copia e cola):\n\n"
                f"{pix_code}\n\n"
                "📸 Depois é só enviar a *foto do comprovante aqui*. Ele entra em análise e eu te aviso assim que for aprovado ou não aprovado!"
            )
        }

    await set_state("menu")
    return {"reply": MENU_TEXT}


@api_router.post("/whatsapp/memory/outgoing")
async def whatsapp_memory_outgoing(data: WAOutgoingMemory, auth=Depends(require_bot_lease)):
    phone = _digits(data.phone)
    if phone and data.text.strip():
        await wa_remember_message(phone, "assistant", data.text)
    return {"ok": True}


@api_router.get("/whatsapp/memory/status/{phone}")
async def whatsapp_memory_status(phone: str, auth=Depends(require_bot_lease)):
    memory = await wa_get_memory(phone)
    return {
        "known": bool(memory),
        "returning": bool(memory and memory.get("message_count", 0) > 1),
        "name": wa_memory_name(memory),
        "last_service_id": (memory or {}).get("last_service_id"),
        "message_count": (memory or {}).get("message_count", 0),
    }


app.include_router(api_router)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", PUBLIC_SITE_URL).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("CONVERSATION_ERROR path=%s", request.url.path)
    if request.url.path.endswith("/api/whatsapp/incoming"):
        return JSONResponse(
            status_code=200,
            content={
                "reply": "Tive um probleminha para processar isso agora 😅 Tenta me mandar de novo em alguns segundos."
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Ocorreu um erro interno. Tente novamente em alguns instantes."},
    )


@app.on_event("startup")
async def seed_admin():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.bookings.create_index([("date", 1), ("time", 1)])
    await db.bookings.create_index("client_phone_digits")
    await db.booking_slot_locks.create_index([("date", 1), ("time", 1)])
    await db.booking_slot_locks.create_index("expires_at", expireAfterSeconds=0)
    await db.wa_memories.create_index("last_seen")

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    await db.booking_slot_locks.delete_many({
        "$or": [
            {"expires_at": {"$lt": datetime.now(timezone.utc)}},
            {"expires_at": {"$exists": False}, "created_at": {"$lt": cutoff}},
        ]
    })
    legacy = db.bookings.find(
        {"$or": [{"client_phone_digits": {"$exists": False}}, {"duration_minutes": {"$exists": False}}]},
        {"id": 1, "client_phone": 1, "service_id": 1},
    )
    async for item in legacy:
        await db.bookings.update_one(
            {"id": item["id"]},
            {"$set": {
                "client_phone_digits": canonical_phone(item.get("client_phone", "")),
                "duration_minutes": service_duration_minutes(item.get("service_id", "")),
                "buffer_minutes": 0,
            }},
        )
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({"email": admin_email, "password_hash": hash_password(admin_password), "name": "Araújo Deluxe", "role": "admin", "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info("Admin seeded")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info("Admin password updated")
    # Start after database initialization; callbacks need a ready API.
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            response = await c.get(f"{BOT_URL}/status", headers=BOT_HEADERS)
            response.raise_for_status()
    except (httpx.HTTPError, ValueError):
        await bot_process.start()


@app.on_event("shutdown")
async def shutdown_db_client():
    await bot_process.stop()
    client.close()
