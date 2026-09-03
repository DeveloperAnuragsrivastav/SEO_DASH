from __future__ import annotations
"""EZ Rankings SEO Dashboard — FastAPI application."""

from fastapi import FastAPI

from app.routes.connections import router as connections_router
from app.routes.connections import verify_router
from app.routes.connections import read_router as connections_read_router
from app.routes.health import router as health_router
from app.routes.manual_metrics import router as manual_metrics_router
from app.routes.rankings import router as rankings_router
from app.routes.webhooks import router as webhooks_router
from app.routes.ai_prompts import router as ai_prompts_router
from app.routes.ai_mentions import router as ai_mentions_router
from app.routes.keywords import router as keywords_router
from app.routes.keyword_research import router as keyword_research_router
from app.routes.reports import router as reports_router
from app.routes.search import router as search_router
from app.routes.audience import router as audience_router
from app.routes.ai_visibility import router as ai_visibility_router
from app.routes.links import router as links_router
from app.routes.work import router as work_router
from app.routes.clients import router as clients_router
from app.routes.users import router as users_router
from app.routes.screenshots import router as screenshots_router
from app.routes.admin import router as admin_router
from app.routes.managers import router as managers_router

from app.routes.auth import router as auth_router

from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title="SEO Dashboard",
    description="EZ Rankings agency portal",
    version="0.1.0",
)

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

# Mount static folder for screenshot uploads
from fastapi.staticfiles import StaticFiles
import os

SCREENSHOTS_DIR = os.path.join(os.getcwd(), "app", "static", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(os.getcwd(), "app", "static")), name="static")

# Include Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(connections_router)
app.include_router(connections_read_router)
app.include_router(verify_router)
app.include_router(manual_metrics_router)
app.include_router(reports_router)
app.include_router(keywords_router)
app.include_router(keyword_research_router)
app.include_router(screenshots_router)
app.include_router(admin_router)
app.include_router(managers_router)
app.include_router(rankings_router)
app.include_router(ai_mentions_router)
app.include_router(ai_prompts_router)
app.include_router(search_router)
app.include_router(audience_router)
app.include_router(webhooks_router)
app.include_router(ai_visibility_router)
app.include_router(links_router)
app.include_router(work_router)
app.include_router(clients_router)
app.include_router(users_router)
app.include_router(screenshots_router)

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
