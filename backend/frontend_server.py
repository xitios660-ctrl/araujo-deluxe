import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BACKEND_ORIGIN = os.environ.get(
    "BACKEND_ORIGIN",
    "https://dente-de-cobra-api.onrender.com",
).rstrip("/")

ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT_DIR / "frontend" / "build"
INDEX_FILE = BUILD_DIR / "index.html"

logger = logging.getLogger("araujo-smoketest")

app = FastAPI(
    title="Araújo Deluxe Frontend",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
HOP_BY_HOP = {
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
}


@app.get("/health")
async def health():
    return {"ok": True, "frontend": True}


@app.api_route("/api", methods=METHODS)
@app.api_route("/api/{path:path}", methods=METHODS)
async def proxy_api(request: Request, path: str = ""):
    target = f"{BACKEND_ORIGIN}/api"
    if path:
        target += f"/{path}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP
    }

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            upstream = await client.request(
                request.method,
                target,
                params=request.query_params,
                content=body,
                headers=headers,
            )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=502,
            content={"detail": "O servidor principal está temporariamente indisponível."},
        )

    response_headers = {}
    for key in ("content-type", "cache-control", "etag", "last-modified"):
        value = upstream.headers.get(key)
        if value:
            response_headers[key] = value

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


async def _smoke_test():
    await asyncio.sleep(4)
    port = os.environ.get("PORT", "10000")
    base = f"http://127.0.0.1:{port}"
    booking = None
    test_phone = "11900000000"

    def ok(name, detail=""):
        logger.info("[SMOKETEST] PASS %-28s %s", name, detail)

    def fail(name, detail=""):
        logger.error("[SMOKETEST] FAIL %-28s %s", name, detail)

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.get(f"{base}/")
            if r.status_code == 200 and "root" in r.text:
                ok("frontend raiz", "200")
            else:
                fail("frontend raiz", f"status={r.status_code}")

            r = await client.get(f"{base}/health")
            if r.status_code == 200 and r.json().get("ok"):
                ok("frontend health", "200")
            else:
                fail("frontend health", f"status={r.status_code}")

            r = await client.get(f"{base}/api/")
            if r.status_code == 200 and r.json().get("message") == "Araújo Deluxe API":
                ok("proxy API", "200")
            else:
                fail("proxy API", f"status={r.status_code} body={r.text[:120]}")

            r = await client.get(f"{base}/api/services")
            services = r.json() if r.status_code == 200 else []
            if r.status_code == 200 and services:
                ok("serviços", f"{len(services)} carregados")
            else:
                fail("serviços", f"status={r.status_code}")

            r = await client.get(f"{base}/api/business-hours")
            if r.status_code == 200 and len(r.json().get("days", [])) == 7:
                ok("horários do estúdio", "7 dias")
            else:
                fail("horários do estúdio", f"status={r.status_code}")

            r = await client.get(f"{base}/api/studio-info")
            info = r.json() if r.status_code == 200 else {}
            if r.status_code == 200 and info.get("whatsapp") and info.get("pix_key"):
                ok("dados estúdio/PIX", "presentes")
            else:
                fail("dados estúdio/PIX", f"status={r.status_code}")

            chosen = None
            today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
            for offset in range(1, 46):
                ds = (today + timedelta(days=offset)).isoformat()
                r = await client.get(f"{base}/api/availability", params={"date": ds})
                if r.status_code != 200:
                    continue
                data = r.json()
                slot = next((s for s in data.get("slots", []) if s.get("available")), None)
                if data.get("open") and slot:
                    chosen = (ds, slot["time"])
                    break

            if chosen:
                ok("disponibilidade", f"{chosen[0]} {chosen[1]}")
            else:
                fail("disponibilidade", "nenhum horário em 45 dias")
                return

            service_id = services[0]["id"]
            payload = {
                "service_id": service_id,
                "date": chosen[0],
                "time": chosen[1],
                "client_name": "Teste Automatizado",
                "client_phone": test_phone,
                "notes": "[AUTOTEST] Pode ignorar",
            }
            r = await client.post(f"{base}/api/bookings", json=payload)
            if r.status_code == 200:
                booking = r.json()
                pay = booking.get("payment")
                if booking.get("id") and booking.get("code") and pay and pay.get("pix_code") and pay.get("qr_base64"):
                    ok("criar agendamento + PIX", booking["code"])
                else:
                    fail("criar agendamento + PIX", "resposta incompleta")
            else:
                fail("criar agendamento + PIX", f"status={r.status_code} body={r.text[:180]}")
                return

            r = await client.get(f"{base}/api/bookings/lookup", params={"q": booking["code"]})
            found = r.json() if r.status_code == 200 else []
            if r.status_code == 200 and any(b.get("id") == booking["id"] for b in found):
                ok("buscar agendamento", "encontrado")
            else:
                fail("buscar agendamento", f"status={r.status_code}")

            r = await client.post(
                f"{base}/api/bookings/{booking['id']}/cancel",
                json={"phone": test_phone},
            )
            if r.status_code == 200 and r.json().get("status") == "cancelada":
                ok("cancelar agendamento", "cancelado")
            else:
                fail("cancelar agendamento", f"status={r.status_code} body={r.text[:120]}")

            r = await client.get(f"{base}/api/availability", params={"date": chosen[0]})
            data = r.json() if r.status_code == 200 else {}
            slot = next((s for s in data.get("slots", []) if s.get("time") == chosen[1]), None)
            if r.status_code == 200 and slot and slot.get("available"):
                ok("liberar horário após cancelar", chosen[1])
            else:
                fail("liberar horário após cancelar", f"status={r.status_code}")

            for name, path in (
                ("proteção auth/me", "/api/auth/me"),
                ("proteção gestor", "/api/admin/bookings"),
                ("proteção WhatsApp gestor", "/api/admin/whatsapp/status"),
            ):
                r = await client.get(f"{base}{path}")
                if r.status_code in (401, 403):
                    ok(name, str(r.status_code))
                else:
                    fail(name, f"status={r.status_code}")

            logger.info("[SMOKETEST] COMPLETE")
    except Exception as exc:
        logger.exception("[SMOKETEST] ERROR %s", exc)
        if booking:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(
                        f"{base}/api/bookings/{booking['id']}/cancel",
                        json={"phone": test_phone},
                    )
            except Exception:
                pass


@app.on_event("startup")
async def run_smoke_test_once():
    asyncio.create_task(_smoke_test())


if (BUILD_DIR / "static").exists():
    app.mount(
        "/static",
        StaticFiles(directory=BUILD_DIR / "static"),
        name="static",
    )


@app.get("/{path:path}")
async def frontend(path: str):
    if not INDEX_FILE.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "Frontend ainda não foi compilado."},
        )

    requested = (BUILD_DIR / path).resolve()
    try:
        requested.relative_to(BUILD_DIR.resolve())
        inside_build = True
    except ValueError:
        inside_build = False

    if path and inside_build and requested.is_file():
        return FileResponse(requested)

    return FileResponse(INDEX_FILE)
