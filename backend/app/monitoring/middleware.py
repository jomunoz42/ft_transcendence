import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.monitoring.metrics import HTTP_REQUESTS, HTTP_DURATION


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.perf_counter() - start

            route = request.scope.get("route")
            route_path = route.path if route else "unmatched"

            HTTP_REQUESTS.labels(
                method=request.method,
                route=route_path,
                status=status,
            ).inc()

            HTTP_DURATION.labels(
                method=request.method,
                route=route_path,
            ).observe(duration)