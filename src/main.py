from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.routers import transaction_router, auth_router
from src.core.database import engine, Base, get_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sincroniza e cria todas as tabelas fisicamente no banco durante o startup da aplicacao
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="AegisGate - API de Detecção de Fraudes",
    description="Microsserviço de avaliação de risco em tempo real para e-commerces, focado em LGPD e IA.",
    version="1.0.0",
    lifespan=lifespan
)

# Registro dos Controladores de Rotas
app.include_router(auth_router.router)
app.include_router(transaction_router.router)

@app.get("/health", tags=["Monitoramento"])
def health_check(db: Session = Depends(get_db)):
    """Health check ativo que executa probe de leitura no banco de dados."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "message": "AegisGate operacional."
    }
