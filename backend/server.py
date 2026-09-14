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
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
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
    d = parse_date(date)
    slots = await get_slot_states(date)
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    if date < today:
        slots = [{**s, "available": False, "reason": "passado"} for s in slots]
    return {
        "date": date,
        "weekday_name": WEEKDAY_NAMES[d.weekday()],
        "open": len(slots) > 0,
        "slots": [{"time": s["time"], "available": s["available"], "reason": s["reason"]} for s in slots],
    }


@api_router.post("/bookings")
async def create_booking(data: BookingCreate):
    service = SERVICES_BY_ID.get(data.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    valid_slots = slots_for_date(data.date)
    if not valid_slots:
        raise HTTPException(status_code=400, detail="Não atendemos neste dia. Escolha de segunda a sábado.")
    if data.time not in valid_slots:
        raise HTTPException(status_code=400, detail="Horário inválido para este dia.")
    if slot_in_past(data.date, data.time):
        raise HTTPException(status_code=400, detail="Este horário já passou. Escolha outro.")
    states = await get_slot_states(data.date)
    slot = next(s for s in states if s["time"] == data.time)
    if not slot["available"]:
        raise HTTPException(status_code=409, detail="Este horário acabou de ser reservado. Escolha outro.")
    booking = {
        "id": str(uuid.uuid4()),
        "code": f"AD-{uuid.uuid4().hex[:6].upper()}",
        "service_id": service["id"],
        "service_name": service["name"],
        "category": service["category"],
        "price": service["price"],
        "deposit": service["deposit"],
        "date": data.date,
        "time": data.time,
        "client_name": data.client_name.strip(),
        "client_phone": data.client_phone.strip(),
        "notes": (data.notes or "").strip(),
        "status": "pendente" if service["deposit"] > 0 else "confirmada",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bookings.insert_one({**booking})
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
    return {**booking, "status": "cancelada"}


@api_router.get("/studio-info")
async def studio_info():
    return {"whatsapp": os.environ["WHATSAPP_NUMBER"], "pix_key": os.environ["PIX_KEY"]}


# ---------- Auth routes ----------
@api_router.post("/auth/login")
async def login(data: LoginInput, request: Request):
    email = os.environ["ADMIN_EMAIL"].lower()
    identifier = f"{request.client.host}:admin"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    now = datetime.now(timezone.utc)
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = datetime.fromisoformat(attempt["locked_until"]) if attempt.get("locked_until") else None
        if locked_until and locked_until > now:
            raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em 15 minutos.")
        await db.login_attempts.delete_one({"identifier": identifier})
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
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
    result = await db.bookings.update_one({"id": booking_id}, {"$set": {"status": data.status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    return booking


@api_router.get("/admin/agenda")
async def admin_agenda(date: str, user: dict = Depends(get_current_user)):
    d = parse_date(date)
    states = await get_slot_states(date)
    return {"date": date, "weekday_name": WEEKDAY_NAMES[d.weekday()], "open": len(states) > 0, "slots": states}


@api_router.post("/admin/blocks")
async def create_block(data: BlockCreate, user: dict = Depends(get_current_user)):
    parse_date(data.date)
    if data.time and data.time not in slots_for_date(data.date):
        raise HTTPException(status_code=400, detail="Horário inválido para este dia")
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
    today_count = await db.bookings.count_documents({"date": today, "status": {"$ne": "cancelada"}})
    upcoming = await db.bookings.count_documents({"date": {"$gte": today}, "status": "confirmada"})
    month_bookings = await db.bookings.find({"date": {"$regex": f"^{month_prefix}"}, "status": {"$in": ["confirmada", "concluida"]}}, {"_id": 0, "price": 1}).to_list(1000)
    month_revenue = sum(b.get("price", 0) for b in month_bookings)
    pending = await db.bookings.count_documents({"date": {"$gte": today}, "status": "pendente"})
    clients = await db.bookings.distinct("client_phone")
    return {"today": today_count, "upcoming": upcoming, "pending": pending, "month_revenue": month_revenue, "total_clients": len(clients)}


# ---------- Payment proof & WhatsApp bot ----------
BOT_URL = os.environ["WHATSAPP_BOT_URL"]
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


def fmt_date_br(date_str: str) -> str:
    return parse_date(date_str).strftime("%d/%m/%Y")


async def bot_send_text(phone: str, message: str):
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await c.post(f"{BOT_URL}/send", json={"phone": _digits(phone), "message": message})
    except Exception as e:
        logging.getLogger(__name__).warning(f"Bot send falhou: {e}")


async def bot_send_image(phone: str, caption: str, base64_data: str, mimetype: str):
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            await c.post(f"{BOT_URL}/send-image", json={"phone": _digits(phone), "caption": caption, "base64": base64_data, "mimetype": mimetype})
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
            r = await c.get(f"{BOT_URL}/status")
            return r.json()
    except Exception:
        return {"connected": False, "has_qr": False, "offline": True}


@api_router.get("/admin/whatsapp/qr")
async def whatsapp_qr(user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(f"{BOT_URL}/qr")
            qr = r.json().get("qr")
            return {"qr_base64": pix_qr_base64(qr) if qr else None}
    except Exception:
        return {"qr_base64": None}


@api_router.post("/admin/whatsapp/logout")
async def whatsapp_logout(user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{BOT_URL}/logout")
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
    "Responda com o *número* da opção desejada."
)

RESET_WORDS = {"menu", "0", "voltar", "inicio", "início", "oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "cancelar", "sair"}


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


async def wa_find_bookings(phone: str, only_pending: bool = False) -> List[dict]:
    digits = _digits(phone)[-8:]
    query = {"status": "pendente"} if only_pending else {}
    all_b = await db.bookings.find(query, {"_id": 0}).to_list(2000)
    matches = [b for b in all_b if _digits(b["client_phone"])[-8:] == digits]
    return sorted(matches, key=lambda b: b.get("created_at", ""), reverse=True)


async def wa_available_slots(date_str: str) -> List[str]:
    states = await get_slot_states(date_str)
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    if date_str < today:
        return []
    return [s["time"] for s in states if s["available"]]


async def wa_create_booking(service_id: str, date_str: str, time_str: str, name: str, phone: str) -> dict:
    service = SERVICES_BY_ID[service_id]
    states = await get_slot_states(date_str)
    slot = next((s for s in states if s["time"] == time_str), None)
    if not slot or not slot["available"]:
        raise ValueError("slot_taken")
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
        "client_name": name.strip(),
        "client_phone": _digits(phone),
        "notes": "Agendado pelo bot do WhatsApp",
        "status": "pendente",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bookings.insert_one({**booking})
    return booking


@api_router.post("/whatsapp/incoming")
async def whatsapp_incoming(data: WAIncoming):
    phone = _digits(data.phone)
    text = (data.text or "").strip()
    lower = text.lower()

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

    if lower in RESET_WORDS:
        await set_state("menu")
        return {"reply": MENU_TEXT}

    if state == "menu":
        if lower.startswith("1"):
            await set_state("book_category")
            return {"reply": CATEGORY_MENU}
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
        return {"reply": MENU_TEXT}

    if state == "book_category":
        if lower.isdigit() and 1 <= int(lower) <= 3:
            cat = CATEGORY_KEYS[int(lower) - 1]
            await set_state("book_service", {"category": cat})
            return {"reply": services_menu_text(cat)}
        return {"reply": "Não entendi. 😅 Responda *1* para Cílios, *2* para Unhas ou *3* para Sobrancelhas. (*0* volta ao menu)"}

    if state == "book_service":
        cat_services = [s for s in SERVICES if s["category"] == sdata.get("category")]
        if lower.isdigit() and 1 <= int(lower) <= len(cat_services):
            service = cat_services[int(lower) - 1]
            await set_state("book_date", {"service_id": service["id"]})
            return {"reply": f"Ótima escolha! *{service['name']}* ✨\n\n📅 Para qual data?\nDigite *DD/MM* (ex: 25/12), ou *hoje* / *amanhã*.\n\n_Atendemos de segunda a sábado._"}
        return {"reply": "Não entendi. 😅 Responda com o *número* do serviço da lista, ou *0* para voltar ao menu."}

    if state in ("book_date", "avail_date"):
        ds = parse_br_date(text)
        if not ds:
            return {"reply": "Data inválida. 😅 Digite no formato *DD/MM* (ex: 25/12), ou *hoje* / *amanhã*."}
        if ds < datetime.now(TZ).strftime("%Y-%m-%d"):
            return {"reply": "Essa data já passou. 😅 Escolha uma data a partir de hoje."}
        if not slots_for_date(ds):
            return {"reply": f"Aos domingos o estúdio não abre. 😔 Escolha outra data (segunda a sábado)."}
        available = await wa_available_slots(ds)
        weekday = WEEKDAY_NAMES[parse_date(ds).weekday()]
        if not available:
            return {"reply": f"😔 Todos os horários de *{fmt_date_br(ds)}* ({weekday}) já estão ocupados.\nTente outra data!"}
        lines = [f"🕐 Horários livres em *{fmt_date_br(ds)}* ({weekday}):\n"]
        for i, t in enumerate(available, 1):
            lines.append(f"*{i}* — {t}")
        if state == "avail_date":
            lines.append("\nDigite *1* no menu para agendar, ou *menu* para voltar.")
            await set_state("menu")
            return {"reply": "\n".join(lines)}
        lines.append("\nResponda com o *número* do horário desejado.")
        await set_state("book_time", {**sdata, "date": ds, "slots": available})
        return {"reply": "\n".join(lines)}

    if state == "book_time":
        slots = sdata.get("slots", [])
        if lower.isdigit() and 1 <= int(lower) <= len(slots):
            await set_state("book_name", {**sdata, "time": slots[int(lower) - 1]})
            return {"reply": "Perfeito! 🥰 Agora me diga seu *nome completo* para finalizar a reserva."}
        return {"reply": "Não entendi. 😅 Responda com o *número* do horário da lista, ou *0* para voltar ao menu."}

    if state == "book_name":
        if len(text) < 2:
            return {"reply": "Digite seu *nome completo*, por favor. 😊"}
        try:
            booking = await wa_create_booking(sdata["service_id"], sdata["date"], sdata["time"], text, phone)
        except ValueError:
            await set_state("book_date", {"service_id": sdata.get("service_id")})
            return {"reply": "😔 Esse horário acabou de ser reservado. Vamos tentar de novo!\n\n📅 Digite outra data (*DD/MM*, *hoje* ou *amanhã*)."}
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
            response = await c.get(f"{BOT_URL}/status")
            response.raise_for_status()
    except (httpx.HTTPError, ValueError):
        await bot_process.start()


@app.on_event("shutdown")
async def shutdown_db_client():
    await bot_process.stop()
    client.close()
