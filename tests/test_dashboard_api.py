import pytest
import uuid
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.core.database import Base, get_db
from src.core.config import settings
from src.models.domains import TransactionEntity
from src.models.schemas import TransactionStatus
from src.services.audit_service import AuditService

# Configurando banco isolado para testes do Dashboard
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_pytest.db"
engine_test = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

Base.metadata.create_all(bind=engine_test)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
AuditService.session_factory = TestingSessionLocal
client = TestClient(app)


def test_dashboard_page_serves_html():
    """Garante que a rota /dashboard entrega o HTML do SPA com sucesso."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "AegisGate" in response.text
    assert "Risk & Security Dashboard" in response.text


def test_dashboard_metrics_calculation():
    """Garante que o endpoint de metricas agrega valores corretamente via SQL."""
    response = client.get("/api/v1/dashboard/metrics")
    assert response.status_code == 200
    data = response.json()

    assert "total_transactions" in data
    assert "total_amount" in data
    assert "approval_rate" in data
    assert "review_rate" in data
    assert "blocked_rate" in data
    assert "average_risk_score" in data
    assert isinstance(data["top_reasons"], dict)


def test_dashboard_simulation_scenarios():
    """Garante que o simulador executa cenarios predefinidos e retorna scores corretos."""
    # 1. Simulação de Cliente Legítimo
    res_legit = client.post("/api/v1/dashboard/simulate", json={"scenario": "legitimate"})
    assert res_legit.status_code == 200
    data_legit = res_legit.json()
    assert data_legit["status"] == "Aprovado"
    assert data_legit["score"] < 60

    # 2. Simulação de Bot Ultra-Rápido
    res_bot = client.post("/api/v1/dashboard/simulate", json={"scenario": "bot_speed"})
    assert res_bot.status_code == 200
    data_bot = res_bot.json()
    assert data_bot["score"] >= 65
    assert "CHECKOUT_TOO_FAST" in data_bot["reasons"]


def test_dashboard_transactions_list_e_mascaramento_lgpd():
    """Garante que a listagem de transacoes mascara dados sensiveis (Nome e CPF) em conformidade com a LGPD."""
    # Cria uma transação no banco com dados sensíveis
    cipher = settings.get_cipher_suite()
    db = TestingSessionLocal()
    tx_id = f"tx_lgpd_test_{uuid.uuid4().hex[:6]}"

    tx = TransactionEntity(
        id=tx_id,
        amount=250.00,
        customer_name_encrypted=cipher.encrypt("Roberto Carlos Silva".encode()).decode(),
        customer_cpf_encrypted=cipher.encrypt("98765432100".encode()).decode(),
        status="Aprovado",
        risk_score=20,
        reasons=[],
        metadata_info={"ip": "127.0.0.1"}
    )
    db.add(tx)
    db.commit()
    db.close()

    response = client.get("/api/v1/dashboard/transactions?limit=20&offset=0")
    assert response.status_code == 200
    data = response.json()

    # Localiza a transação criada
    found = next((t for t in data["transactions"] if t["id"] == tx_id), None)
    assert found is not None

    # O nome e CPF brutos NUNCA devem estar presentes na resposta
    assert found["customer_name_masked"] != "Roberto Carlos Silva"
    assert "R***" in found["customer_name_masked"]
    assert "***.***.321-00" in found["customer_cpf_masked"]


def test_dashboard_review_transaction_workflow():
    """Garante que apenas transacoes 'Em Revisao' podem ser deliberadas manualmente."""
    cipher = settings.get_cipher_suite()
    db = TestingSessionLocal()
    tx_id = f"tx_rev_{uuid.uuid4().hex[:6]}"

    tx = TransactionEntity(
        id=tx_id,
        amount=500.00,
        customer_name_encrypted=cipher.encrypt("Usuario Suspeito".encode()).decode(),
        customer_cpf_encrypted=cipher.encrypt("11122233344".encode()).decode(),
        status="Em Revisão",
        risk_score=72,
        reasons=["CARD_NUMBER_PASTED"],
        metadata_info={"ip": "127.0.0.1"}
    )
    db.add(tx)
    db.commit()
    db.close()

    # 1. Deliberação de Sucesso (Em Revisão -> Aprovado)
    res_review = client.post(
        f"/api/v1/dashboard/transactions/{tx_id}/review",
        json={
            "new_status": "Aprovado",
            "analyst_note": "Cliente contatado por telefone e validado com sucesso."
        }
    )
    assert res_review.status_code == 200
    rev_data = res_review.json()
    assert rev_data["previous_status"] == "Em Revisão"
    assert rev_data["new_status"] == "Aprovado"

    # 2. Tentativa de deliberar novamente uma transação que agora está "Aprovada" (Deve falhar com 400)
    res_repeat = client.post(
        f"/api/v1/dashboard/transactions/{tx_id}/review",
        json={
            "new_status": "Bloqueado",
            "analyst_note": "Tentativa indevida de alterar transacao ja deliberada."
        }
    )
    assert res_repeat.status_code == 400
    assert "Em Revisão" in res_repeat.json()["detail"]


def test_dashboard_reset_endpoint():
    """Garante que o endpoint POST /api/v1/dashboard/reset limpa as transações e auditorias do banco."""
    # Cria uma transação para garantir que o banco não está vazio
    db = TestingSessionLocal()
    tx = TransactionEntity(
        id=f"tx_to_reset_{uuid.uuid4().hex[:6]}",
        amount=99.00,
        customer_name_encrypted="enc_name",
        customer_cpf_encrypted="enc_cpf",
        status="Aprovado",
        risk_score=10,
        reasons=[],
        metadata_info={}
    )
    db.add(tx)
    db.commit()
    db.close()

    # Chama o endpoint de reset
    res_reset = client.post("/api/v1/dashboard/reset")
    assert res_reset.status_code == 200
    data = res_reset.json()
    assert data["status"] == "success"
    assert data["deleted_count"] >= 1

    # Verifica se as métricas agora refletem zero transações
    res_metrics = client.get("/api/v1/dashboard/metrics")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert metrics["total_transactions"] == 0
    assert metrics["total_amount"] == 0.0
