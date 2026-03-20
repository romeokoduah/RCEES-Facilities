"""RCEES Facilities - FastAPI Application"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .config import UPLOAD_DIR, FRONTEND_DIR
from .routes.auth import router as auth_router
from .routes.facilities import router as facilities_router
from .routes.bookings import router as bookings_router
from .routes.maintenance import router as maintenance_router
from .routes.discounts import router as discounts_router
from .routes.invoices import router as invoices_router
from .routes.misc import equipment_router, users_router, reviews_router, analytics_router
from .routes.availability import router as availability_router
from .routes.activity import router as activity_router

def create_app() -> FastAPI:
    from .database import init_db
    init_db()

    app = FastAPI(title="RCEES Facilities Management System", version="3.5.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    if UPLOAD_DIR.exists():
        app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
    app.include_router(auth_router)
    app.include_router(facilities_router)
    app.include_router(bookings_router)
    app.include_router(maintenance_router)
    app.include_router(discounts_router)
    app.include_router(invoices_router)
    app.include_router(equipment_router)
    app.include_router(users_router)
    app.include_router(reviews_router)
    app.include_router(analytics_router)
    app.include_router(availability_router)
    app.include_router(activity_router)

    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        index = FRONTEND_DIR / "index.html"
        if index.exists():
            return index.read_text(encoding="utf-8")
        return "<h1>RCEES Facilities API</h1><p>Frontend not found.</p>"

    return app

app = create_app()
