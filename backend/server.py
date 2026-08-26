from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import uuid
import logging
import httpx
import bcrypt
import jwt
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

FREE_SHIPPING_THRESHOLD = 250.0

# (prefix_min, prefix_max, region, pac_price, (pac_min, pac_max), sedex_price, (sedex_min, sedex_max))
ZONES = [
    (1, 9, "Grande São Paulo", 18.90, (3, 5), 27.90, (1, 2)),
    (10, 19, "Interior de SP", 21.90, (4, 6), 32.90, (2, 3)),
    (20, 29, "Rio de Janeiro / Espírito Santo", 24.90, (5, 7), 39.90, (2, 4)),
    (30, 39, "Minas Gerais", 24.90, (5, 7), 39.90, (2, 4)),
    (40, 65, "Nordeste", 32.90, (7, 10), 54.90, (4, 6)),
    (66, 69, "Norte", 39.90, (9, 14), 69.90, (5, 8)),
    (70, 79, "Centro-Oeste", 28.90, (6, 9), 46.90, (3, 5)),
    (80, 99, "Sul", 26.90, (5, 8), 42.90, (3, 4)),
]


def eta(dmin, dmax):
    return f"{dmin} a {dmax} dias úteis"


def zone_for(prefix: int):
    for zmin, zmax, region, pac, pac_d, sedex, sedex_d in ZONES:
        if zmin <= prefix <= zmax:
            return region, pac, pac_d, sedex, sedex_d
    return None


JWT_ALGORITHM = "HS256"
ALLOWED_STATUSES = ["aguardando_pagamento", "pago", "em_preparacao", "enviado", "entregue"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "type": "access",
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def get_current_admin(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada. Entre novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Acesso negado.")
    return user


class Customer(BaseModel):
    name: str
    phone: str
    email: str = ""


class Address(BaseModel):
    cep: str
    street: str
    number: str
    complement: str = ""
    neighborhood: str = ""
    city: str
    state: str


class OrderItem(BaseModel):
    id: str
    name: str
    price: float
    qty: int
    image: str = ""


class ShippingChoice(BaseModel):
    id: str
    label: str
    price: float
    eta: str = ""


class OrderCreate(BaseModel):
    customer: Customer
    address: Address
    items: List[OrderItem]
    shipping: ShippingChoice
    payment_method: str
    subtotal: float


class Order(OrderCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_number: str = ""
    total: float = 0
    status: str = "aguardando_pagamento"
    created_at: str = ""


@api_router.get("/")
async def root():
    return {"message": "Dente de Cobra API"}


@api_router.get("/shipping/{cep}")
async def calculate_shipping(cep: str, subtotal: float = 0):
    digits = re.sub(r"\D", "", cep)
    if len(digits) != 8:
        raise HTTPException(status_code=400, detail="CEP inválido. Use 8 dígitos.")

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://viacep.com.br/ws/{digits}/json/")
        data = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Falha ao consultar o CEP. Tente novamente.")

    if data.get("erro"):
        raise HTTPException(status_code=404, detail="CEP não encontrado.")

    zone = zone_for(int(digits[:2]))
    if not zone:
        raise HTTPException(status_code=400, detail="CEP fora da área de entrega.")

    region, pac, pac_d, sedex, sedex_d = zone
    options = []
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        options.append({
            "id": "gratis",
            "label": "Frete Grátis Dente de Cobra",
            "price": 0,
            "eta": eta(pac_d[0] + 2, pac_d[1] + 2),
        })
    options.append({"id": "pac", "label": "PAC — Correios", "price": pac, "eta": eta(*pac_d)})
    options.append({"id": "sedex", "label": "SEDEX — Correios", "price": sedex, "eta": eta(*sedex_d)})

    return {
        "cep": f"{digits[:5]}-{digits[5:]}",
        "region": region,
        "address": {
            "street": data.get("logradouro", ""),
            "neighborhood": data.get("bairro", ""),
            "city": data.get("localidade", ""),
            "state": data.get("uf", ""),
        },
        "options": options,
        "free_shipping_threshold": FREE_SHIPPING_THRESHOLD,
    }


@api_router.post("/orders", response_model=Order)
async def create_order(payload: OrderCreate):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Carrinho vazio.")
    order = Order(
        **payload.model_dump(),
        order_number=f"DDC-{uuid.uuid4().hex[:6].upper()}",
        total=round(payload.subtotal + payload.shipping.price, 2),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    await db.orders.insert_one(order.model_dump())
    return order


@api_router.get("/orders/{order_number}", response_model=Order)
async def get_order(order_number: str):
    doc = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return Order(**doc)


class LoginRequest(BaseModel):
    email: str
    password: str


class StatusUpdate(BaseModel):
    status: str


@api_router.post("/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    email = payload.email.strip().lower()
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    identifier = f"{ip}:{email}"
    now = datetime.now(timezone.utc)
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("locked_until") and datetime.fromisoformat(attempt["locked_until"]) > now:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em 15 minutos.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        count = (attempt.get("count", 0) + 1) if attempt else 1
        update = {"identifier": identifier, "count": count}
        if count >= 5:
            update["locked_until"] = (now + timedelta(minutes=15)).isoformat()
            update["count"] = 0
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    await db.login_attempts.delete_one({"identifier": identifier})
    token = create_access_token(user["id"], email)
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=86400, path="/",
    )
    return {"email": email, "name": user.get("name", "Admin"), "role": user["role"], "access_token": token}


@api_router.get("/auth/me")
async def auth_me(admin: dict = Depends(get_current_admin)):
    return admin


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api_router.get("/admin/orders")
async def admin_list_orders(admin: dict = Depends(get_current_admin)):
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)


@api_router.patch("/admin/orders/{order_number}/status")
async def admin_update_status(order_number: str, payload: StatusUpdate, admin: dict = Depends(get_current_admin)):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido.")
    result = await db.orders.update_one(
        {"order_number": order_number}, {"$set": {"status": payload.status}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return {"order_number": order_number, "status": payload.status}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def seed_admin():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    email = os.environ["ADMIN_EMAIL"].lower()
    password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": hash_password(password),
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
