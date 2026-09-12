"""FastAPI Application Factory for Loan Easier."""

from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import UPLOADS_DIR, BASE_DIR
from src.api.routes_ocr import router as ocr_router
from src.api.routes_loans import router as loans_router
from src.api.routes_export import export_router, loans_pdf_router
from src.db.schema import init_db

STATIC_DIR = BASE_DIR / "src" / "static"

def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Loan Easier OCR & Verification API",
        description="Production web API for loan document ingestion, dual OCR fallback, HITL verification, and PDF/CSV export.",
        version="1.0.0",
    )

    # Initialize SQLite database
    init_db()

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(ocr_router)
    app.include_router(loans_router)
    app.include_router(loans_pdf_router)
    app.include_router(export_router)

    # Mount static assets and document uploads
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Root route for Web UI or health check
    @app.get("/", include_in_schema=False)
    async def root_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "system": "Loan Easier OCR & Verification API",
                "status": "online",
                "endpoints": {
                    "upload": "/api/documents/upload",
                    "loans": "/api/loans",
                    "pdf_export": "/api/loans/{id}/pdf",
                    "csv_export": "/api/export/csv?month=YYYY-MM",
                    "docs": "/docs",
                },
            },
        )

    # Global exception handler for uniform JSON responses
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    return app

# Singleton app instance for uvicorn runner and TestClient
app = create_app()
