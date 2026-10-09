from typing import Optional, Dict, Any


class DomainError(Exception):
    """
    Excecao base para todas as falhas de regras de negocio e dominio do AegisGate.
    Fornece integracao semantica com status HTTP, codigo padronizado de erro
    e detalhes estruturados para respostas RFC 7807 (Problem Details).
    """
    def __init__(
        self,
        message: str,
        error_code: str = "AEGIS_DOMAIN_ERROR",
        http_status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.http_status_code = http_status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o erro em formato padronizado de resposta REST."""
        payload = {
            "error_code": self.error_code,
            "message": self.message,
            "status_code": self.http_status_code
        }
        if self.details:
            payload["details"] = self.details
        return payload

    def __str__(self) -> str:
        return self.message


# =====================================================================
# 1. Conflito e Idempotencia (HTTP 409)
# =====================================================================

class ConflictError(DomainError):
    """Excecao para conflitos de estado no servidor."""
    def __init__(
        self,
        message: str,
        error_code: str = "AEGIS_CONFLICT",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            http_status_code=409,
            details=details
        )


class DuplicateTransactionError(ConflictError):
    """Lancada quando uma transacao com o mesmo identificador ja existe no banco de dados."""
    def __init__(self, transaction_id: str, details: Optional[Dict[str, Any]] = None):
        self.transaction_id = transaction_id
        merged_details = {"transaction_id": transaction_id}
        if details:
            merged_details.update(details)
        super().__init__(
            message=f"Transacao com identificador '{transaction_id}' ja processada anteriormente.",
            error_code="AEGIS_DUPLICATE_TRANSACTION",
            details=merged_details
        )


# =====================================================================
# 2. Seguranca e Autenticacao (HTTP 401 e 403)
# =====================================================================

class AuthenticationError(DomainError):
    """Excecao base para falhas de identidade e credenciais."""
    def __init__(
        self,
        message: str = "Falha de autenticacao.",
        error_code: str = "AEGIS_UNAUTHORIZED",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            http_status_code=401,
            details=details
        )


class InvalidCredentialsError(AuthenticationError):
    """Lancada quando as credenciais do parceiro sao rejeitadas."""
    def __init__(self, client_id: Optional[str] = None):
        details = {"client_id": client_id} if client_id else None
        super().__init__(
            message="Credenciais de parceiro invalidas ou nao autorizadas.",
            error_code="AEGIS_INVALID_CREDENTIALS",
            details=details
        )


class TokenError(AuthenticationError):
    """Excecao para problemas na validacao de tokens JWT."""
    def __init__(
        self,
        message: str = "Token de autenticacao invalido.",
        error_code: str = "AEGIS_TOKEN_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class TokenExpiredError(TokenError):
    """Lancada quando o token JWT ultrapassou seu tempo de expiracao."""
    def __init__(self):
        super().__init__(
            message="Token de autenticacao expirado.",
            error_code="AEGIS_TOKEN_EXPIRED"
        )


class TokenCorruptedError(TokenError):
    """Lancada quando a assinatura ou payload do JWT esta corrompido."""
    def __init__(self):
        super().__init__(
            message="Token de autenticacao invalido ou corrompido.",
            error_code="AEGIS_TOKEN_CORRUPTED"
        )


# =====================================================================
# 3. Validacao de Dados e Borda (HTTP 422)
# =====================================================================

class ValidationError(DomainError):
    """Excecao para violacoes semanticas nos dados de entrada."""
    def __init__(
        self,
        message: str,
        error_code: str = "AEGIS_VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            http_status_code=422,
            details=details
        )


class ChronologyValidationError(ValidationError):
    """Lancada quando a ordem temporal de checkout e inconsistente."""
    def __init__(self, started_at: str, submitted_at: str):
        super().__init__(
            message="Inconsistencia temporal: submitted_checkout_at nao pode ser anterior a started_checkout_at.",
            error_code="AEGIS_INCONSISTENT_TIMESTAMPS",
            details={"started_checkout_at": started_at, "submitted_checkout_at": submitted_at}
        )


# =====================================================================
# 4. Resiliencia, Rate Limiting e Criptografia (HTTP 429 e 500)
# =====================================================================

class RateLimitError(DomainError):
    """Lancada quando a cota de requisicoes e ultrapassada."""
    def __init__(self, limit: int, window_seconds: int, retry_after: int):
        self.retry_after = retry_after
        super().__init__(
            message=f"Limite de requisicoes excedido ({limit} reqs por {window_seconds}s).",
            error_code="AEGIS_RATE_LIMIT_EXCEEDED",
            http_status_code=429,
            details={"limit": limit, "window_seconds": window_seconds, "retry_after": retry_after}
        )


class InfrastructureError(DomainError):
    """Excecao para falhas internas de infraestrutura e persistencia."""
    def __init__(
        self,
        message: str,
        error_code: str = "AEGIS_INFRASTRUCTURE_ERROR",
        http_status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            http_status_code=http_status_code,
            details=details
        )


class EncryptionError(InfrastructureError):
    """Lancada quando ocorre falha na cifragem ou decifragem Fernet (LGPD)."""
    def __init__(self, reason: str):
        super().__init__(
            message=f"Falha na operacao criptografica de protecao de dados: {reason}",
            error_code="AEGIS_ENCRYPTION_FAILURE"
        )
