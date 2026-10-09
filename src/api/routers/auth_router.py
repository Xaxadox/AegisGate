from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from src.core.security import SecurityService
from src.core.rate_limiter import RateLimiter

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Autenticação"]
)

auth_limiter = RateLimiter(times=30, seconds=60, prefix="auth_token")

class TokenRequest(BaseModel):
    client_id: str = Field(..., description="Identificador do lojista/parceiro")
    client_secret: str = Field(..., description="Segredo do lojista")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int = 60

@router.post("/token", response_model=TokenResponse, dependencies=[Depends(auth_limiter)])
def generate_token(request: TokenRequest):
    """
    Emite token JWT para autenticação das chamadas de avaliação de risco.
    Atende ao requisito RN01 / RNF001, validando credenciais de parceiro homologado.
    """
    if not request.client_id or not request.client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciais de cliente inválidas (client_id e client_secret são obrigatórios)."
        )

    if not SecurityService.authenticate_merchant(request.client_id, request.client_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais de parceiro inválidas ou não autorizadas."
        )

    token = SecurityService.create_access_token({"sub": request.client_id})
    return TokenResponse(access_token=token)
