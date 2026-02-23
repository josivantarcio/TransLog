from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.redis import close_redis, get_redis_client
from app.routers import auth, deliveries, tenants, tracking, users, vehicles, webhooks
from app.websockets.tracking_ws import tracking_websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pre-aquece conexão Redis
    await get_redis_client()
    yield
    # Shutdown: fecha conexões
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    description="SaaS de gestão de entregas — API Backend",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers REST
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(deliveries.router, prefix="/api/v1")
app.include_router(tracking.router, prefix="/api/v1")
app.include_router(vehicles.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")

# WebSocket
app.add_api_websocket_route(
    "/ws/tracking/{delivery_id}",
    tracking_websocket_endpoint,
)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
