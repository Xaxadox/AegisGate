import secrets
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict

from src.core.config import settings

security_scheme = HTTPBearer(auto_error=False)

class SecurityService:
    @staticmethod
    def authenticate_merchant(client_id: str, client_secret: str) -> bool:
        """
        Valida as credenciais do lojista utilizando comparacao em tempo constante
        para mitigar ataques de temporizacao (Timing Attacks).
        """
        if not client_id or not client_secret:
            return False
        expected_secret = settings.MERCHANT_CREDENTIALS.get(client_id)
        if not expected_secret:
            return False
        return secrets.compare_digest(expected_secret, client_secret)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Gera um JWT assinado com tempo de expiração."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Dict:
        """Decodifica e valida a integridade do token JWT."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticação expirado.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticação inválido ou corrompido.",
                headers={"WWW-Authenticate": "Bearer"},
            )

def require_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> Dict:
    """
    Dependência do FastAPI para assegurar conformidade com RN01 e RNF001:
    Bloqueia chamadas sem token JWT válido.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória (Header Authorization: Bearer <token> ausente).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return SecurityService.verify_token(credentials.credentials)
