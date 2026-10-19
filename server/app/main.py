from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin_dify, ai, auth, internal, situation
from app.core.config import settings
from app.db import Base, engine
from app.services.seed import ensure_registry_columns, ensure_seed_data

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(admin_dify.router, prefix="/api/v1")
app.include_router(situation.router, prefix="/api/v1")
app.include_router(internal.router, prefix="/api/v1")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_registry_columns()
    ensure_seed_data()


@app.get("/health")
def health():
    return {
        "ok": True,
        "mock_ai": settings.use_mock_ai,
        "mock_detection": settings.use_mock_detection,
        "harness_base_url": settings.harness_base_url,
        "dify_base_url": settings.dify_base_url,
    }
