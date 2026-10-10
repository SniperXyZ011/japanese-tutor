import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a request id and logs latency without logging headers or bodies."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        logger.info(
            "request method=%s path=%s status=%s latency_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            request_id,
        )
        return response
