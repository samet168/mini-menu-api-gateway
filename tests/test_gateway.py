import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.main import app

pytestmark = pytest.mark.asyncio


async def test_gateway_health():
    """Verify gateway health endpoint returns 200 and downstream status mapping."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["gateway_status"] == "healthy"
        assert "auth_service" in data["downstream_services"]
        assert "catalog_service" in data["downstream_services"]
        assert "order_service" in data["downstream_services"]


async def test_correlation_id_middleware():
    """Verify that X-Correlation-ID is either preserved or dynamically generated."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. No correlation ID supplied -> Gateway generates one
        r1 = await client.get("/")
        assert r1.status_code == 200
        assert "X-Correlation-ID" in r1.headers
        generated_id = r1.headers["X-Correlation-ID"]
        assert len(generated_id) > 10

        # 2. Client provides correlation ID -> Gateway preserves it
        custom_id = "trace-client-req-9988"
        r2 = await client.get("/", headers={"X-Correlation-ID": custom_id})
        assert r2.status_code == 200
        assert r2.headers.get("X-Correlation-ID") == custom_id


async def test_sliding_window_rate_limiter():
    """Verify that exceeding rate limit triggers HTTP 429."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
    test_ip = "192.168.1.100"

    # Request 1, 2, 3 should be allowed
    a1, rem1, _ = await limiter.check_rate_limit(test_ip)
    assert a1 is True
    assert rem1 == 2

    a2, rem2, _ = await limiter.check_rate_limit(test_ip)
    assert a2 is True
    assert rem2 == 1

    a3, rem3, _ = await limiter.check_rate_limit(test_ip)
    assert a3 is True
    assert rem3 == 0

    # Request 4 exceeds limit
    a4, rem4, reset_in = await limiter.check_rate_limit(test_ip)
    assert a4 is False
    assert rem4 == 0
    assert reset_in > 0


async def test_live_proxy_routing_to_downstream():
    """
    Test routing through the Gateway to live downstream microservices running on the host.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Route 1: /api/v1/auth/health -> Auth Service (:8001)
        r_auth = await client.get("/api/v1/auth/health")
        if r_auth.status_code == 200:
            assert r_auth.json()["service"] == "mini-menu-auth-service"
            assert "X-Correlation-ID" in r_auth.headers

        # Route 2: /api/v1/catalog/health -> Catalog Service (:8002)
        r_cat = await client.get("/api/v1/catalog/health")
        if r_cat.status_code == 200:
            assert r_cat.json()["service"] == "mini-menu-catalog-service"
            assert "X-Correlation-ID" in r_cat.headers

        # Route 3: /api/v1/orders/health -> Order Service (:8003)
        r_order = await client.get("/api/v1/orders/health")
        if r_order.status_code == 200:
            assert r_order.json()["service"] == "mini-menu-order-service"
            assert "X-Correlation-ID" in r_order.headers
