import pytest
from src.core.exceptions import (
    DomainError,
    ConflictError,
    DuplicateTransactionError,
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenCorruptedError,
    ValidationError,
    ChronologyValidationError,
    RateLimitError,
    EncryptionError
)


def test_domain_error_base_serialization():
    """Valida a serializacao da excecao base DomainError em formato de dicionario."""
    err = DomainError(
        message="Erro generico de teste",
        error_code="TEST_ERROR",
        http_status_code=400,
        details={"campo": "invalido"}
    )
    assert str(err) == "Erro generico de teste"
    data = err.to_dict()
    assert data["error_code"] == "TEST_ERROR"
    assert data["message"] == "Erro generico de teste"
    assert data["status_code"] == 400
    assert data["details"] == {"campo": "invalido"}


def test_duplicate_transaction_error_properties():
    """Valida que DuplicateTransactionError herda de ConflictError com status 409."""
    err = DuplicateTransactionError(transaction_id="tx_123456")
    assert isinstance(err, ConflictError)
    assert isinstance(err, DomainError)
    assert err.http_status_code == 409
    assert err.error_code == "AEGIS_DUPLICATE_TRANSACTION"
    assert err.transaction_id == "tx_123456"
    assert "tx_123456" in str(err)
    assert err.details["transaction_id"] == "tx_123456"


def test_invalid_credentials_error():
    """Valida erro de credenciais com codigo de status 401."""
    err = InvalidCredentialsError(client_id="loja_desconhecida")
    assert isinstance(err, AuthenticationError)
    assert err.http_status_code == 401
    assert err.error_code == "AEGIS_INVALID_CREDENTIALS"
    assert err.details["client_id"] == "loja_desconhecida"


def test_token_errors():
    """Valida excecoes especializadas para ciclo de vida de JWT."""
    exp = TokenExpiredError()
    assert exp.http_status_code == 401
    assert exp.error_code == "AEGIS_TOKEN_EXPIRED"

    corrupted = TokenCorruptedError()
    assert corrupted.http_status_code == 401
    assert corrupted.error_code == "AEGIS_TOKEN_CORRUPTED"


def test_chronology_validation_error():
    """Valida erro semantico de datas com status 422."""
    err = ChronologyValidationError(started_at="2026-10-09T10:00:00", submitted_at="2026-10-09T09:59:00")
    assert isinstance(err, ValidationError)
    assert err.http_status_code == 422
    assert err.error_code == "AEGIS_INCONSISTENT_TIMESTAMPS"
    assert "started_checkout_at" in err.details


def test_rate_limit_error():
    """Valida informacoes estruturadas de Rate Limiting com Retry-After."""
    err = RateLimitError(limit=60, window_seconds=60, retry_after=30)
    assert err.http_status_code == 429
    assert err.retry_after == 30
    assert err.details["retry_after"] == 30


def test_encryption_error():
    """Valida falhas de infraestrutura criptografica com status 500."""
    err = EncryptionError(reason="Chave corrompida")
    assert err.http_status_code == 500
    assert err.error_code == "AEGIS_ENCRYPTION_FAILURE"
