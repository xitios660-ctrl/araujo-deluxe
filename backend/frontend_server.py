import os
from pathlib import Path

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


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/admin") or request.url.path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health():
    backend = {"ok": False, "database": False, "whatsapp": {"connected": False}}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{BACKEND_ORIGIN}/api/health")
            if response.headers.get("content-type", "").startswith("application/json"):
                backend = response.json()
            backend_ok = response.status_code == 200 and bool(backend.get("ok"))
    except Exception:
        backend_ok = False
    payload = {"ok": backend_ok, "frontend": True, "backend": backend}
    return JSONResponse(status_code=200 if backend_ok else 503, content=payload)


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
