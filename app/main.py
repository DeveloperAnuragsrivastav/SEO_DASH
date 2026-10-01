from __future__ import annotations
"""EZ Rankings SEO Dashboard — FastAPI application."""

from fastapi import FastAPI

from app.routes.connections import router as connections_router
from app.routes.connections import verify_router
from app.routes.connections import read_router as connections_read_router
from app.routes.health import router as health_router
from app.routes.keyword_research import router as keyword_research_router
from app.routes.reports import router as reports_router
from app.routes.clients import router as clients_router
from app.routes.users import router as users_router
from app.routes.admin import router as admin_router
from app.routes.managers import router as managers_router
from app.routes.sheets import router as sheets_router

from app.routes.auth import router as auth_router

from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title="SEO Dashboard",
    description="EZ Rankings agency portal",
    version="0.1.0",
)

class BodySizeLimit:
    """Refuse any request body over MAX_REQUEST_MB — before it is read into
    memory — so nobody can push a 100 MB file at the server. Each image is
    held to MAX_IMAGE_MB where it is saved."""

    def __init__(self, app, limit: int):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers") or []).get(b"content-length")
        if length and length.isdigit() and int(length) > self.limit:
            return await self._too_large(send)

        seen = 0

        async def counted():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body") or b"")
                if seen > self.limit:
                    raise _TooLarge()
            return message

        try:
            await self.app(scope, counted, send)
        except _TooLarge:
            await self._too_large(send)

    async def _too_large(self, send):
        import json
        body = json.dumps({"detail": f"That upload is too large — the limit is {self.limit // (1024 * 1024)} MB."}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class _TooLarge(Exception):
    pass



# Added first so it sits inside CORS: a refusal still carries CORS headers
# and the browser can show why.
app.add_middleware(BodySizeLimit, limit=settings.MAX_REQUEST_MB * 1024 * 1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173", 
        "http://localhost:5174", 
        "http://127.0.0.1:5174",
        settings.FRONTEND_URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fixed assets only (the agency logo); every uploaded image lives in the database.
from fastapi.staticfiles import StaticFiles
import os

app.mount("/static", StaticFiles(directory=os.path.join(os.getcwd(), "app", "static")), name="static")

# Include Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(connections_router)
app.include_router(connections_read_router)
app.include_router(verify_router)
app.include_router(reports_router)
app.include_router(keyword_research_router)
app.include_router(admin_router)
app.include_router(managers_router)
app.include_router(sheets_router)
app.include_router(clients_router)
app.include_router(users_router)

# ── SPA Catch-All Route ────────────────────────────────────────────────
from fastapi.responses import FileResponse

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """
    Serve the built React frontend.
    If the requested file exists in frontend/dist, serve it.
    Otherwise, fall back to index.html for client-side routing.
    """
    dist_dir = os.path.join(os.getcwd(), "frontend", "dist")
    file_path = os.path.join(dist_dir, full_path)
    
    # If the file exists (e.g. /assets/main.js, /favicon.ico), serve it directly
    if os.path.isfile(file_path):
        return FileResponse(file_path)
        
    # Otherwise, return index.html for React Router
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
        
    return {"detail": "Frontend not built or index.html missing."}
