import logging
from typing import AsyncGenerator, Optional
from urllib.parse import urljoin
from fastapi import HTTPException, Request, status
from fastapi.responses import Response
import httpx

logger = logging.getLogger("gateway.reverse_proxy")

# Standard HTTP hop-by-hop headers to strip when proxying
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",  # Recalculated by response
}


def _clean_proxy_headers(request: Request, correlation_id: str) -> dict:
    """
    Constructs clean forwarding headers with injected tracing metadata.
    """
    headers = {}
    for key, value in request.headers.items():
        lower_key = key.lower()
        if lower_key not in HOP_BY_HOP_HEADERS:
            headers[key] = value

    # Client IP detection and X-Forwarded-For injection
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "127.0.0.1")
    )
    existing_xff = request.headers.get("x-forwarded-for")
    headers["X-Forwarded-For"] = f"{existing_xff}, {client_ip}" if existing_xff else client_ip
    headers["X-Forwarded-Proto"] = request.url.scheme
    headers["X-Forwarded-Host"] = request.headers.get("host", str(request.url.hostname or "localhost"))
    headers["X-Correlation-ID"] = correlation_id

    return headers


async def stream_request_body(request: Request) -> AsyncGenerator[bytes, None]:
    """Asynchronously streams chunks from the incoming request body."""
    async for chunk in request.stream():
        yield chunk


async def proxy_request(
    target_base_url: str,
    target_path: str,
    request: Request,
    correlation_id: str,
    timeout: float = 60.0,
) -> Response:
    """
    Forwards an incoming HTTP request to the designated downstream microservice.
    Reads complete payload to prevent socket truncation on client exit.
    """
    # Build complete destination URL
    dest_url = f"{target_base_url.rstrip('/')}/{target_path.lstrip('/')}"
    query_params = request.url.query
    if query_params:
        dest_url = f"{dest_url}?{query_params}"

    clean_headers = _clean_proxy_headers(request, correlation_id)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        try:
            req_body = await request.body()
            upstream_req = client.build_request(
                method=request.method,
                url=dest_url,
                headers=clean_headers,
                content=req_body,
            )

            upstream_resp = await client.send(upstream_req)
            content = await upstream_resp.aread()

            # Filter response headers
            response_headers = {}
            for k, v in upstream_resp.headers.items():
                if k.lower() not in HOP_BY_HOP_HEADERS:
                    response_headers[k] = v
            response_headers["X-Correlation-ID"] = correlation_id
            response_headers["Content-Length"] = str(len(content))

            return Response(
                content=content,
                status_code=upstream_resp.status_code,
                headers=response_headers,
                media_type=upstream_resp.headers.get("content-type"),
            )

        except httpx.ConnectError as exc:
            logger.error(f"Failed to connect to downstream service at {dest_url}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Downstream service unavailable at {target_base_url}. Please try again shortly.",
            )
        except httpx.TimeoutException as exc:
            logger.error(f"Downstream service timeout for {dest_url}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Gateway timed out waiting for downstream service response.",
            )
        except Exception as exc:
            logger.exception(f"Unexpected error proxying to {dest_url}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Bad Gateway: Error communicating with downstream service: {str(exc)}",
            )
