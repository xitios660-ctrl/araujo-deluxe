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

SERVICES_BY_ID = {s["id"]: s for s in SERVICES}
BOOKING_STATUSES = ["pendente", "confirmada", "concluida", "cancelada"]


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
    return "".join(c for c in s if c.isdigit())


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


async def get_slot_states(date_str: str) -> List[dict]:
    slots = slots_for_date(date_str)
    bookings = await db.bookings.find({"date": date_str, "status": {"$ne": "cancelada"}}, {"_id": 0}).to_list(100)
    blocks = await db.blocks.find({"date": date_str}, {"_id": 0}).to_list(100)
    day_block = next((b for b in blocks if b.get("time") is None), None)
    booked_times = {b["time"]: b for b in bookings}
    blocked_times = {b["time"]: b for b in blocks if b.get("time")}
    result = []
    for t in slots:
        state = {"time": t, "available": True, "reason": None, "booking": None, "block_id": None}
        if slot_in_past(date_str, t):
            state.update(available=False, reason="passado")
        elif day_block:
            state.update(available=False, reason="bloqueado", block_id=day_block["id"])
        elif t in blocked_times:
            state.update(available=False, reason="bloqueado", block_id=blocked_times[t]["id"])
        elif t in booked_times:
            state.update(available=False, reason="agendado", booking=booked_times[t])
        result.append(state)
    return result


class BookingSlotError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def booking_slot_lock_id(date_str: str, time_str: str) -> str:
    return f"{date_str}|{time_str}"


async def get_day_availability(date_str: str) -> dict:
    d = parse_date(date_str)
    scheduled_slots = slots_for_date(date_str)
    states = await get_slot_states(date_str)
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
        "slots": states,
    }


async def acquire_booking_slot(date_str: str, time_str: str):
    lock_id = booking_slot_lock_id(date_str, time_str)
    active = await db.bookings.find_one(
        {"date": date_str, "time": time_str, "status": {"$ne": "cancelada"}},
        {"_id": 0, "id": 1},
    )
    if active:
        raise BookingSlotError("slot_taken", "Este horário acabou de ser reservado. Escolha outro.")

    try:
        await db.booking_slot_locks.insert_one({
            "_id": lock_id,
            "date": date_str,
            "time": time_str,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except DuplicateKeyError:
        raise BookingSlotError("slot_taken", "Este horário acabou de ser reservado. Escolha outro.")


async def release_booking_slot(date_str: str, time_str: str):
    await db.booking_slot_locks.delete_one({"_id": booking_slot_lock_id(date_str, time_str)})


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

    valid_slots = slots_for_date(date_str)
    if not valid_slots:
        raise BookingSlotError("closed_day", "Não atendemos neste dia. Escolha de segunda a sábado.")
    if time_str not in valid_slots:
        raise BookingSlotError("invalid_time", "Horário inválido para este dia.")
    if slot_in_past(date_str, time_str):
        raise BookingSlotError("past", "Este horário já passou. Escolha outro.")

    day = await get_day_availability(date_str)
    if not day["open"]:
        raise BookingSlotError("closed_day", day["closed_reason"] or "O estúdio está fechado neste dia.")

    slot = next((s for s in day["slots"] if s["time"] == time_str), None)
    if not slot or not slot["available"]:
        raise BookingSlotError("slot_taken", "Este horário não está mais disponível. Escolha outro.")

    await acquire_booking_slot(date_str, time_str)
    try:
        # Recheck after acquiring the slot. This catches a day/time block created
        # between the first availability check and the final booking write.
        refreshed = await get_day_availability(date_str)
        refreshed_slot = next((s for s in refreshed["slots"] if s["time"] == time_str), None)
        if not refreshed["open"]:
            raise BookingSlotError("closed_day", refreshed["closed_reason"] or "O estúdio está fechado neste dia.")
        if not refreshed_slot or not refreshed_slot["available"]:
            raise BookingSlotError("slot_taken", "Este horário não está mais disponível. Escolha outro.")

        booking = {
            "id": str(uuid.uuid4()),
            "code": f"AD-{uuid.uuid4().hex[:6].upper()}",
            "service_id": service["id"],
            "service_name": service["name"],
            "category": service["category"],
            "price": service["price"],
            "deposit": service["deposit"],
            "date": date_str,
            "time": time_str,
            "client_name": client_name.strip(),
            "client_phone": client_phone.strip(),
            "notes": notes.strip(),
            "status": "pendente" if service["deposit"] > 0 else "confirmada",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bookings.insert_one({**booking})
        return booking
    except Exception:
        await release_booking_slot(date_str, time_str)
        raise


# ---------- Public routes ----------
@api_router.get("/")
async def root():
    return {"message": "Araújo Deluxe API"}


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
async def availability(date: str):
    day = await get_day_availability(date)
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

    service = SERVICES_BY_ID[booking["service_id"]]
    response = {**booking, "whatsapp": os.environ["WHATSAPP_NUMBER"], "payment": None}
    if service["deposit"] > 0:
        pix_code = build_pix(float(service["deposit"]), booking["code"].replace("-", ""))
        response["payment"] = {
            "method": "pix",
            "pix_key": os.environ["PIX_KEY"],
            "pix_code": pix_code,
            "qr_base64": pix_qr_base64(pix_code),
            "amount": service["deposit"],
        }
    return response


@api_router.get("/bookings/lookup")
async def lookup_bookings(q: str):
    q = q.strip()
    if len(q) < 4:
        raise HTTPException(status_code=400, detail="Informe o código completo ou seu telefone com DDD.")
    results = await db.bookings.find({"code": q.upper()}, {"_id": 0}).to_list(20)
    if not results:
        digits = _digits(q)
        if len(digits) >= 8:
            all_b = await db.bookings.find({}, {"_id": 0}).to_list(2000)
            results = [b for b in all_b if _digits(b["client_phone"]).endswith(digits) or digits.endswith(_digits(b["client_phone"]))]
    return sorted(results, key=lambda b: (b["date"], b["time"]), reverse=True)[:20]


@api_router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, data: CancelInput):
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    d1, d2 = _digits(data.phone), _digits(booking["client_phone"])
    if not d1 or not (d1.endswith(d2) or d2.endswith(d1)):
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


@api_router.patch("/admin/bookings/{booking_id}")
async def update_booking(booking_id: str, data: StatusUpdate, user: dict = Depends(get_current_user)):
    if data.status not in BOOKING_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")

    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    old_status = booking.get("status")
    acquired = False
    if old_status == "cancelada" and data.status != "cancelada":
        day = await get_day_availability(booking["date"])
        slot = next((s for s in day["slots"] if s["time"] == booking["time"]), None)
        if not day["open"] or not slot or not slot["available"]:
            raise HTTPException(status_code=409, detail="Não é possível reativar: o dia/horário não está mais disponível.")
        try:
            await acquire_booking_slot(booking["date"], booking["time"])
            acquired = True
        except BookingSlotError as exc:
            raise HTTPException(status_code=409, detail=exc.detail)

    try:
        await db.bookings.update_one({"id": booking_id}, {"$set": {"status": data.status}})
    except Exception:
        if acquired:
            await release_booking_slot(booking["date"], booking["time"])
        raise

    if data.status == "cancelada" and old_status != "cancelada":
        await release_booking_slot(booking["date"], booking["time"])

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

    active_query = {"date": data.date, "status": {"$ne": "cancelada"}}
    if data.time:
        active_query["time"] = data.time
    active_booking = await db.bookings.find_one(active_query, {"_id": 0, "id": 1, "time": 1})
    if active_booking:
        detail = (
            f"O horário {data.time} já tem agendamento. Cancele ou mova a reserva antes de bloquear."
            if data.time
            else "Este dia possui agendamentos. Cancele ou mova as reservas antes de fechar o dia inteiro."
        )
        raise HTTPException(status_code=409, detail=detail)

    existing = await db.blocks.find_one({"date": data.date, "time": data.time})
    if existing:
        raise HTTPException(status_code=409, detail="Já existe um bloqueio para este horário")
    block = {"id": str(uuid.uuid4()), "date": data.date, "time": data.time, "reason": (data.reason or "").strip(), "created_at": datetime.now(timezone.utc).isoformat()}
    await db.blocks.insert_one({**block})
    return block


@api_router.delete("/admin/blocks/{block_id}")
async def delete_block(block_id: str, user: dict = Depends(get_current_user)):
    result = await db.blocks.delete_one({"id": block_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bloqueio não encontrado")
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


async def whatsapp_contact_allowed(phone: str):
    phone = _digits(phone)
    pref = await db.wa_preferences.find_one({"_id": phone})
    if pref and pref.get("blocked"):
        return False
    if phone == _digits(OWNER_WA):
        return True
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return bool(pref and pref.get("last_incoming", "") >= since)


async def bot_send_text(phone: str, message: str):
    if not await whatsapp_contact_allowed(phone):
        return
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await c.post(f"{BOT_URL}/send", headers=BOT_HEADERS, json={"phone": _digits(phone), "message": message})
    except Exception as e:
        logging.getLogger(__name__).warning(f"Bot send falhou: {e}")


async def bot_send_image(phone: str, caption: str, base64_data: str, mimetype: str):
    if not await whatsapp_contact_allowed(phone):
        return
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            await c.post(f"{BOT_URL}/send-image", headers=BOT_HEADERS, json={"phone": _digits(phone), "caption": caption, "base64": base64_data, "mimetype": mimetype})
    except Exception as e:
        logging.getLogger(__name__).warning(f"Bot send-image falhou: {e}")


async def confirm_with_proof(booking: dict, data_base64: str, mime: str, source: str, notify_client: bool = True) -> str:
    proof = {
        "id": str(uuid.uuid4()),
        "booking_id": booking["id"],
        "mime": mime,
        "data": data_base64,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.proofs.insert_one({**proof})
    await db.bookings.update_one({"id": booking["id"]}, {"$set": {"status": "confirmada", "proof_id": proof["id"]}})
    date_br = fmt_date_br(booking["date"])
    if notify_client:
        client_msg = (
            "✅ *Comprovante recebido!*\n\n"
            "Seu horário no *Araújo Deluxe* está *CONFIRMADO* ✨\n\n"
            f"📋 {booking['service_name']}\n"
            f"📅 {date_br} às {booking['time']}\n"
            f"🔑 Código: {booking['code']}\n\n"
            "Até lá! 💛"
        )
        await bot_send_text(booking["client_phone"], client_msg)
    owner_msg = (
        "📥 *Novo agendamento confirmado!*\n\n"
        f"👤 {booking['client_name']}\n"
        f"📱 {booking['client_phone']}\n"
        f"📋 {booking['service_name']} · R$ {booking['price']}\n"
        f"📅 {date_br} às {booking['time']}\n"
        f"💰 Sinal: R$ {booking['deposit']} (comprovante anexado)\n"
        f"🔑 Código: {booking['code']}"
    )
    await bot_send_image(OWNER_WA, owner_msg, data_base64, mime)
    return proof["id"]


@api_router.post("/bookings/{booking_id}/proof")
async def upload_proof(booking_id: str, data: ProofUpload):
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    if booking.get("proof_id"):
        return {"ok": True, "status": "confirmada", "proof_id": booking["proof_id"]}
    if booking["status"] not in ("pendente", "confirmada"):
        raise HTTPException(status_code=400, detail="Este agendamento não aceita mais comprovante.")
    if len(data.data_base64) > 11_000_000:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Envie até 8MB.")
    proof_id = await confirm_with_proof(booking, data.data_base64, data.mime, "site")
    return {"ok": True, "status": "confirmada", "proof_id": proof_id}


@api_router.get("/admin/proofs/{proof_id}")
async def get_proof(proof_id: str, user: dict = Depends(get_current_user)):
    proof = await db.proofs.find_one({"id": proof_id}, {"_id": 0})
    if not proof:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    return proof


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

RESET_WORDS = {"menu", "0", "voltar", "inicio", "início", "cancelar", "sair"}


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
        "text": "Como posso te ajudar?",
        "button_text": "Abrir menu",
        "footer": "Você também pode escrever normalmente 💛",
        "sections": [{
            "title": "Atendimento",
            "rows": [
                {"id": "menu:agendar", "title": "📅 Agendar horário", "description": "Escolher procedimento, data e horário"},
                {"id": "menu:horarios", "title": "🕐 Ver horários", "description": "Consultar horários disponíveis"},
                {"id": "menu:comprovante", "title": "📸 Enviar comprovante", "description": "Confirmar o sinal do agendamento"},
                {"id": "menu:reservas", "title": "📒 Minhas reservas", "description": "Consultar meus agendamentos"},
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

    # Order matters: "depois de amanhã" also contains the word "amanhã".
    if re.search(r"\bdepois\s+de\s+amanha\b", t):
        return (now + timedelta(days=2)).strftime("%Y-%m-%d")
    if re.search(r"\bamanha\b", t):
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    if re.search(r"\bhoje\b", t):
        return now.strftime("%Y-%m-%d")

    match = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b", t)
    if match:
        return parse_br_date(match.group(0))

    # Natural follow-ups: "e dia 16?", "pro dia 3", "dia 28 tem horário?"
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
    for label, target in sorted(weekdays.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(label)}\b", t):
            delta = (target - now.weekday()) % 7
            if delta == 0:
                delta = 7
            return (now + timedelta(days=delta)).strftime("%Y-%m-%d")
    return None


def wa_time_from_sentence(text: str) -> Optional[str]:
    t = wa_normalize(text)
    match = re.search(r"\b(\d{1,2})(?::(\d{2})|h(?:(\d{2}))?)\b", t)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or match.group(3) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
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
    refers_to_previous = any(x in t for x in ("esse", "essa", "esse mesmo", "pode ser", "quero esse", "quero essa"))
    if not service and refers_to_previous:
        service = remembered_service

    asks_price = any(x in t for x in ("valor", "preco", "quanto custa", "quanto fica", "quanto e"))
    asks_duration = any(x in t for x in ("quanto tempo", "demora", "duracao"))
    if (asks_price or asks_duration) and service:
        await wa_update_memory_profile(phone, service_id=service["id"])
        bits = [f"*{service['name']}*"]
        if asks_price:
            bits.append(f"fica *R$ {service['price']}* e o sinal é *R$ {service['deposit']}*")
        if asks_duration:
            bits.append(f"leva em média *{service['duration']}*")
        answer = " 💛 ".join(bits) + f". {service['description']}"
        if state != "menu":
            answer += "\n\nE eu não perdi seu agendamento, tá? " + wa_step_hint(state)
        else:
            answer += "\n\nSe quiser, eu já marco pra você."
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
            f"{recommended['description']} Fica R$ {recommended['price']} e leva em média {recommended['duration']}. "
            "Se você gostar, eu já vejo um horário."
        )

    date_str = wa_date_from_sentence(text)
    time_str = wa_time_from_sentence(text)
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
    availability_followup = bool(date_str and previous_asked_availability and not wants_booking)

    # Availability does not require choosing a procedure first. The website and
    # WhatsApp consult the same day/slot source of truth.
    if date_str and not service and (asks_availability or availability_followup):
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
        return wa_reply(
            f"Tenho sim 💛 Em *{fmt_date_br(date_str)}* ({day['weekday_name']}) estão livres: "
            + ", ".join(available)
            + ". Quer marcar algum desses?"
        )

    if service and date_str and (wants_booking or asks_availability or state == "menu"):
        day = await get_day_availability(date_str)
        if not day["scheduled_open"]:
            return wa_reply(f"Em *{fmt_date_br(date_str)}* é {day['weekday_name']} e o estúdio não abre 😔 Me fala outro dia.")
        if not day["open"]:
            return wa_reply(f"Em *{fmt_date_br(date_str)}* o estúdio está *fechado/bloqueado* 😔 {day['closed_reason'] or ''} Me fala outro dia.")
        available = [s["time"] for s in day["slots"] if s["available"]]
        if not available:
            return wa_reply(f"Pra *{fmt_date_br(date_str)}* todos os horários já estão ocupados 😔 Me fala outro dia que eu olho.")
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
        "book_time": "Escolhe um dos *horários* que eu te mostrei e me manda o número ou o horário.",
        "book_name": "Pra finalizar, me manda seu *nome completo* 😊",
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
                return f"Oii{hello_name} 💛 Que bom falar com você de novo!{tail} O que você precisa hoje?"
            return "Oii 💛 Tudo bem? Me conta o que você está querendo fazer. Trabalho com cílios, unhas e sobrancelhas. Se quiser, já vejo valores ou horários pra você."
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
        return "Bora 😊💛 O que você quer fazer: *cílios, unhas ou sobrancelhas*?"

    if any(x in t for x in ("quem e voce", "voce e robo", "voce e uma pessoa", "e humano")):
        return "Sou a assistente virtual do Araújo Deluxe 💛 Mas pode falar comigo normal, viu? Eu consigo conversar, passar valores, ver horários e fazer seu agendamento por aqui."

    return None


async def wa_find_bookings(phone: str, only_pending: bool = False) -> List[dict]:
    digits = _digits(phone)[-8:]
    query = {"status": "pendente"} if only_pending else {}
    all_b = await db.bookings.find(query, {"_id": 0}).to_list(2000)
    matches = [b for b in all_b if _digits(b["client_phone"])[-8:] == digits]
    return sorted(matches, key=lambda b: b.get("created_at", ""), reverse=True)


async def wa_available_slots(date_str: str) -> List[str]:
    day = await get_day_availability(date_str)
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
        booking = pending[0]
        await confirm_with_proof(booking, data.image_base64, data.image_mime or "image/jpeg", "whatsapp", notify_client=False)
        await set_state("menu")
        return {
            "reply": (
                "✅ *Comprovante recebido!*\n\n"
                "Seu horário está *CONFIRMADO* ✨\n\n"
                f"📋 {booking['service_name']}\n"
                f"📅 {fmt_date_br(booking['date'])} às {booking['time']}\n"
                f"🔑 Código: {booking['code']}\n\n"
                "Até lá! 💛 Araújo Deluxe"
            )
        }

    normalized_input = wa_normalize(text)
    if lower in RESET_WORDS or re.search(r"\bmenu\b", normalized_input):
        await set_state("menu")
        return wa_reply(
            "Claro 💛 Voltamos pro começo. Escolhe uma opção abaixo ou me fala normalmente o que você precisa.",
            wa_main_menu_ui(),
        )

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
            return {"reply": "📸 É só enviar a *foto do comprovante* (ou PDF) aqui nesta conversa que eu confirmo seu horário na hora!"}
        if lower.startswith("4"):
            bookings = (await wa_find_bookings(phone))[:5]
            if not bookings:
                return {"reply": "Você ainda não tem reservas neste número. Digite *1* para agendar! ✨"}
            emojis = {"pendente": "🕐", "confirmada": "✅", "concluida": "💛", "cancelada": "❌"}
            lines = ["📒 *Suas reservas:*\n"]
            for b in bookings:
                lines.append(f"{emojis.get(b['status'], '•')} {b['service_name']} — {fmt_date_br(b['date'])} às {b['time']} ({b['status']}) · {b['code']}")
            lines.append("\nDigite *menu* para voltar.")
            return {"reply": "\n".join(lines)}
        return wa_reply(
            "Posso te ajudar com agendamento, valores, horários e escolher o procedimento ideal 💛 "
            "Você pode escrever do seu jeito ou usar o menu abaixo.",
            wa_main_menu_ui(),
        )

    if state == "book_category":
        if "cilio" in lower or "cílio" in lower:
            lower = "1"
        elif "unha" in lower:
            lower = "2"
        elif "sobrancelha" in lower:
            lower = "3"
        if lower.isdigit() and 1 <= int(lower) <= 3:
            cat = CATEGORY_KEYS[int(lower) - 1]
            await set_state("book_service", {"category": cat})
            return wa_reply(
                f"Perfeito 💛 Agora escolhe o serviço de *{CATEGORY_LABELS_WA[cat]}*:",
                wa_services_ui(cat),
            )
        return wa_reply(
            "Não consegui ligar essa mensagem a uma categoria 😅 Mas pode conversar comigo normal. "
            "Quando quiser continuar o agendamento, escolha *1 Cílios, 2 Unhas ou 3 Sobrancelhas*.",
            wa_category_ui(),
        )

    if state == "book_service":
        cat_services = [s for s in SERVICES if s["category"] == sdata.get("category")]
        named = [i for i, service in enumerate(cat_services, 1) if lower == service["name"].lower()]
        if len(named) == 1:
            lower = str(named[0])
        if lower.isdigit() and 1 <= int(lower) <= len(cat_services):
            service = cat_services[int(lower) - 1]
            await wa_update_memory_profile(phone, service_id=service["id"])
            await set_state("book_date", {"service_id": service["id"]})
            return {"reply": f"Ótima escolha! *{service['name']}* ✨\n\n📅 Para qual data?\nDigite *DD/MM* (ex: 25/12), ou *hoje* / *amanhã*.\n\n_Atendemos de segunda a sábado._"}
        return wa_reply(
            "Não peguei qual serviço você quis 😅 Se era só conversa, pode falar normal comigo. "
            "Se quiser continuar, manda o nome ou o número do procedimento.",
            wa_services_ui(sdata.get("category")) if sdata.get("category") in CATEGORY_KEYS else wa_category_ui(),
        )

    if state in ("book_date", "avail_date"):
        ds = wa_date_from_sentence(text) or parse_br_date(text)
        if not ds:
            return {"reply": "Data inválida. 😅 Digite no formato *DD/MM* (ex: 25/12), ou *hoje* / *amanhã*."}
        if ds < datetime.now(TZ).strftime("%Y-%m-%d"):
            return {"reply": "Essa data já passou. 😅 Escolha uma data a partir de hoje."}
        day = await get_day_availability(ds)
        if not day["scheduled_open"]:
            return {"reply": "Aos domingos o estúdio não abre. 😔 Escolha outra data (segunda a sábado)."}
        if not day["open"]:
            return {"reply": f"🚫 O estúdio está *fechado* em {fmt_date_br(ds)} ({day['weekday_name']}).\n{day['closed_reason'] or 'Escolha outra data.'}"}
        available = [s["time"] for s in day["slots"] if s["available"]]
        weekday = day["weekday_name"]
        if not available:
            return {"reply": f"😔 Todos os horários de *{fmt_date_br(ds)}* ({weekday}) já estão ocupados.\nTente outra data!"}
        if state == "avail_date":
            await set_state("menu")
            return wa_reply(
                f"🕐 Em *{fmt_date_br(ds)}* ({weekday}) estão livres: "
                + ", ".join(available)
                + ". Quer marcar algum desses?"
            )
        await set_state("book_time", {**sdata, "date": ds, "slots": available})
        return wa_reply(
            f"🕐 Horários livres em *{fmt_date_br(ds)}* ({weekday}). Escolhe um:",
            wa_slots_ui(ds, available),
        )

    if state == "book_time":
        slots = sdata.get("slots", [])
        requested_time = wa_time_from_sentence(text) or lower.replace("h", ":").strip()
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
        if len(text) < 2:
            return {"reply": "Digite seu *nome completo*, por favor. 😊"}
        try:
            await wa_update_memory_profile(phone, name=text, service_id=sdata.get("service_id"))
            booking = await wa_create_booking(sdata["service_id"], sdata["date"], sdata["time"], text, phone)
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
                "📸 Depois é só enviar a *foto do comprovante aqui* nesta conversa que eu confirmo na hora!"
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

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def seed_admin():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.bookings.create_index([("date", 1), ("time", 1)])
    await db.booking_slot_locks.create_index([("date", 1), ("time", 1)])
    await db.wa_memories.create_index("last_seen")
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
