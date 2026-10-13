import logging
from typing import Optional
from fastapi import Request, HTTPException, status
import redis

from src.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Controlador de taxa de requisicoes (Rate Limiting) backed por Redis.
    Aplica o principio de resiliencia Fail-Open: se o cluster Redis estiver
    inacessivel ou offline, permite a passagem da requisicao sem degradar o checkout.
    """
    def __init__(self, times: int = 60, seconds: int = 60, prefix: str = "general"):
        self.times = times
        self.seconds = seconds
        self.prefix = prefix
        self._redis_client: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        if self._redis_client is None:
            self._redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                socket_timeout=0.2,
                socket_connect_timeout=0.2,
                decode_responses=True
            )
        return self._redis_client

    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        if hasattr(request, "headers") and request.headers is not None:
            try:
                forwarded_for = request.headers.get("x-forwarded-for")
                if forwarded_for and isinstance(forwarded_for, str):
                    return forwarded_for.split(",")[0].strip()
            except Exception:
                pass
        return request.client.host if request.client else "unknown_ip"

    def __call__(self, request: Request):
        client_ip = self._extract_client_ip(request)
        key = f"rate_limit:{self.prefix}:{client_ip}"

        try:
            r = self._get_client()
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.seconds, nx=True)
            current_requests, _ = pipe.execute()

            if current_requests > self.times:
                logger.warning(
                    "Limite de taxa excedido para IP %s no endpoint %s (%d/%d)",
                    client_ip, request.url.path, current_requests, self.times
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Limite de requisicoes excedido ({self.times} reqs por {self.seconds}s). Tente novamente mais tarde.",
                    headers={"Retry-After": str(self.seconds)}
                )
        except HTTPException:
            raise
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError, ConnectionError, OSError) as e:
            logger.debug("Redis inacessivel para rate limiting (%s). Prosseguindo em modo fail-open.", e)
            return True
