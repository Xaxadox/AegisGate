import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, Request
from src.core.rate_limiter import RateLimiter


def test_rate_limiter_fail_open_quando_redis_indisponivel():
    """Garante que falhas de conexao com Redis nao travam a aplicacao (Fail-Open)."""
    limiter = RateLimiter(times=5, seconds=60, prefix="teste_fail_open")
    
    # Mockando cliente Redis para simular ConnectionError
    mock_redis = MagicMock()
    mock_redis.pipeline.side_effect = ConnectionError("Redis cluster offline")
    limiter._redis_client = mock_redis

    # Simula requisicao FastAPI
    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "127.0.0.1"
    mock_request.url.path = "/test"

    # Deve retornar True sem levantar excecao
    result = limiter(mock_request)
    assert result is True


def test_rate_limiter_bloqueia_quando_excede_limite():
    """Garante que ultrapassar a cota de requisicoes lanca HTTP 429 Too Many Requests."""
    limiter = RateLimiter(times=2, seconds=60, prefix="teste_limite")

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    # Simula que o pipeline retornou 3 requisicoes (limite era 2)
    mock_pipe.execute.return_value = (3, True)
    mock_redis.pipeline.return_value = mock_pipe
    limiter._redis_client = mock_redis

    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "192.168.1.100"
    mock_request.url.path = "/api/v1/transactions/evaluate"

    with pytest.raises(HTTPException) as exc_info:
        limiter(mock_request)

    assert exc_info.value.status_code == 429
    assert "Limite de requisicoes excedido" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers
