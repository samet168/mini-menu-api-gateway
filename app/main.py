from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import Dict
from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
import httpx

from app.core.config import settings
from app.core.rate_limiter import enforce_rate_limit
from app.core.reverse_proxy import proxy_request
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.cors import setup_cors

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api_gateway")

HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the API Gateway."""
    logger.info(f"Starting {settings.PROJECT_NAME} on port {settings.PORT}...")
    logger.info(f"  Downstream Auth:    {settings.AUTH_SERVICE_URL}")
    logger.info(f"  Downstream Catalog: {settings.CATALOG_SERVICE_URL}")
    logger.info(f"  Downstream Orders:  {settings.ORDER_SERVICE_URL}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


app = FastAPI(
    title="Mini Menu API Gateway",
    description="Unified Ingress, Reverse Proxy, Routing & Security Layer for Mini Menu Microservices.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Attach Middlewares
setup_cors(app)
app.add_middleware(CorrelationIdMiddleware)


# ==============================================================================
# ROUTING CONTRACT
# ==============================================================================

# 1. Auth Service Routing: /api/v1/auth/* -> AUTH_SERVICE_URL (:8001)
@app.api_route(
    "/api/v1/auth",
    methods=HTTP_METHODS,
    tags=["Auth Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
@app.api_route(
    "/api/v1/auth/{path:path}",
    methods=HTTP_METHODS,
    tags=["Auth Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
async def proxy_auth(request: Request, path: str = ""):
    target_path = f"/api/v1/auth/{path}" if path else "/api/v1/auth"
    return await proxy_request(
        target_base_url=settings.AUTH_SERVICE_URL,
        target_path=target_path,
        request=request,
        correlation_id=request.state.correlation_id,
    )


# 2. Catalog Service Routing: /api/v1/catalog/* -> CATALOG_SERVICE_URL (:8002)
@app.api_route(
    "/api/v1/catalog",
    methods=HTTP_METHODS,
    tags=["Catalog Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
@app.api_route(
    "/api/v1/catalog/{path:path}",
    methods=HTTP_METHODS,
    tags=["Catalog Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
async def proxy_catalog(request: Request, path: str = ""):
    target_path = f"/api/v1/catalog/{path}" if path else "/api/v1/catalog"
    return await proxy_request(
        target_base_url=settings.CATALOG_SERVICE_URL,
        target_path=target_path,
        request=request,
        correlation_id=request.state.correlation_id,
    )


# 3. Store Routing: /api/v1/stores/* -> CATALOG_SERVICE_URL (:8002)
@app.api_route(
    "/api/v1/stores",
    methods=HTTP_METHODS,
    tags=["Stores Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
@app.api_route(
    "/api/v1/stores/{path:path}",
    methods=HTTP_METHODS,
    tags=["Stores Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
async def proxy_stores(request: Request, path: str = ""):
    target_path = f"/api/v1/stores/{path}" if path else "/api/v1/stores"
    return await proxy_request(
        target_base_url=settings.CATALOG_SERVICE_URL,
        target_path=target_path,
        request=request,
        correlation_id=request.state.correlation_id,
    )


# 4. Public Menu Routing: /api/v1/public/* -> CATALOG_SERVICE_URL (:8002)
@app.api_route(
    "/api/v1/public",
    methods=HTTP_METHODS,
    tags=["Public Menu Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
@app.api_route(
    "/api/v1/public/{path:path}",
    methods=HTTP_METHODS,
    tags=["Public Menu Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
async def proxy_public(request: Request, path: str = ""):
    target_path = f"/api/v1/public/{path}" if path else "/api/v1/public"
    return await proxy_request(
        target_base_url=settings.CATALOG_SERVICE_URL,
        target_path=target_path,
        request=request,
        correlation_id=request.state.correlation_id,
    )


# 5. Orders Routing: /api/v1/orders/* -> ORDER_SERVICE_URL (:8003)
@app.api_route(
    "/api/v1/orders",
    methods=HTTP_METHODS,
    tags=["Orders Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
@app.api_route(
    "/api/v1/orders/{path:path}",
    methods=HTTP_METHODS,
    tags=["Orders Proxy"],
    dependencies=[Depends(enforce_rate_limit)],
)
async def proxy_orders(request: Request, path: str = ""):
    target_path = f"/api/v1/orders/{path}" if path else "/api/v1/orders"
    return await proxy_request(
        target_base_url=settings.ORDER_SERVICE_URL,
        target_path=target_path,
        request=request,
        correlation_id=request.state.correlation_id,
    )


# ==============================================================================
# GATEWAY HEALTH & METADATA
# ==============================================================================

@app.get("/ping", tags=["Gateway Health"])
@app.get("/api/v1/ping", tags=["Gateway Health"])
async def gateway_ping():
    """Ultra-fast zero-dependency liveness check for container orchestrators."""
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/health", tags=["Gateway Health"])
@app.get("/api/v1/health", tags=["Gateway Health"])
async def gateway_health() -> Dict:
    """
    Checks gateway status and performs quick concurrent probes to downstream services.
    """
    import asyncio

    async def check_service(name: str, url: str) -> tuple:
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                r = await client.get(url)
                return name, "healthy" if r.status_code == 200 else f"status_{r.status_code}"
        except Exception:
            return name, "unreachable"

    results = await asyncio.gather(
        check_service("auth_service", f"{settings.AUTH_SERVICE_URL}/api/v1/auth/health"),
        check_service("catalog_service", f"{settings.CATALOG_SERVICE_URL}/api/v1/catalog/health"),
        check_service("order_service", f"{settings.ORDER_SERVICE_URL}/api/v1/orders/health"),
    )
    downstream_health = dict(results)
    all_healthy = all(status == "healthy" for status in downstream_health.values())

    return {
        "gateway_status": "healthy",
        "system_status": "operational" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc),
        "downstream_services": downstream_health,
        "routes": {
            "/api/v1/auth/*": settings.AUTH_SERVICE_URL,
            "/api/v1/catalog/*": settings.CATALOG_SERVICE_URL,
            "/api/v1/stores/*": settings.CATALOG_SERVICE_URL,
            "/api/v1/public/*": settings.CATALOG_SERVICE_URL,
            "/api/v1/orders/*": settings.ORDER_SERVICE_URL,
        },
    }


@app.get("/", tags=["Root"])
async def root():
    """Gateway root overview."""
    return {
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }
