from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.routers import transaction_router, auth_router, dashboard_router
from src.core.database import engine, Base, get_db

STATIC_DIR = Path(__file__).resolve().parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sincroniza e cria todas as tabelas fisicamente no banco durante o startup da aplicacao
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="AegisGate - API de Detecção de Fraudes",
    description="Microsserviço de avaliação de risco em tempo real para e-commerces com Arquitetura Híbrida de IA e Dashboard.",
    version="2.1.0",
    lifespan=lifespan
)

# Servimento de arquivos estáticos (CSS, JS e Vendor)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Registro dos Controladores de Rotas
app.include_router(auth_router.router)
app.include_router(transaction_router.router)
app.include_router(dashboard_router.router)

@app.get("/dashboard", tags=["Dashboard"])
def get_dashboard_page():
    """Entrega a Single Page Application (SPA) do Dashboard de Risco e Simulador."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return {"error": "Arquivo index.html do dashboard não encontrado."}
    return FileResponse(str(index_file))

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redireciona a raiz para o dashboard visual de risco."""
    return RedirectResponse(url="/dashboard")

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
