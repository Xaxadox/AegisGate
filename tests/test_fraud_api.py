import pytest
import uuid
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
import pybreaker

from src.main import app
from src.core.database import Base, get_db
from src.core.security import SecurityService
from src.models.domains import TransactionEntity, AuditLogEntity
from src.services.audit_service import AuditService

# 1. Configurando Banco de Dados em Memória para Testes Isolados
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_pytest.db"
engine_test = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

Base.metadata.create_all(bind=engine_test)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Injetamos o banco de teste na API
app.dependency_overrides[get_db] = override_get_db

# Isolamos a auditoria em background no banco de testes
AuditService.session_factory = TestingSessionLocal

# Instanciamos o cliente de teste do FastAPI
client = TestClient(app)

# ==========================================
# 2. Utilitários (Factory de Payloads e Auth)
# ==========================================
def get_auth_headers() -> dict:
    """Gera token JWT válido para testes autenticados."""
    token = SecurityService.create_access_token({"sub": "loja_parceira_teste"})
    return {"Authorization": f"Bearer {token}"}

def get_valid_payload() -> dict:
    now = datetime.now(timezone.utc)
    started = now - timedelta(minutes=2) # Checkout demorou 2 minutos (Normal humano)
    
    return {
        "transaction_id": f"tx_pytest_{uuid.uuid4().hex[:8]}",
        "amount": 150.00,
        "customer_name": "Caio Teste",
        "customer_cpf": "123.456.789-00",
        "customer_ip": "192.168.1.1",
        "delivery_state": "SP",
        "started_checkout_at": started.isoformat(),
        "submitted_checkout_at": now.isoformat(),
        "is_card_pasted": False,
        "card_bin": "123456",
        "card_last_four": "9999"
    }

# ==========================================
# 3. Casos de Teste (Unit & E2E Tests)
# ==========================================

def test_health_check_esta_online():
    """Garante que a API subiu corretamente."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_endpoint_geracao_token_jwt():
    """Testa geração de token para lojista parceiro (RN01)."""
    response = client.post("/api/v1/auth/token", json={
        "client_id": "loja_americanas",
        "client_secret": "segredo123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_bloqueio_sem_token_jwt():
    """Garante conformidade com RN01 e RNF001: 401 Unauthorized se faltar token."""
    payload = get_valid_payload()
    response = client.post("/api/v1/transactions/evaluate", json=payload)
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]

def test_bloqueio_com_token_jwt_invalido():
    """Garante que token forjado ou expirado é rejeitado."""
    payload = get_valid_payload()
    response = client.post(
        "/api/v1/transactions/evaluate",
        json=payload,
        headers={"Authorization": "Bearer token_falso_invalido"}
    )
    assert response.status_code == 401

def test_caminho_feliz_transacao_aprovada():
    """Cenário Caminho Feliz: Usuário normal, sem indícios de fraude."""
    payload = get_valid_payload()
    response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Aprovado"
    assert data["score"] < 60
    assert len(data["reasons"]) == 0

def test_fraude_robo_checkout_muito_rapido():
    """Cenário de Fraude: Checkout efetuado em menos de 1.5 segundos (Robô via API)."""
    payload = get_valid_payload()
    now = datetime.now(timezone.utc)
    # Usuário iniciou e clicou no botão de comprar no mesmo milissegundo!
    payload["started_checkout_at"] = now.isoformat()
    payload["submitted_checkout_at"] = now.isoformat()

    response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    
    assert response.status_code == 200
    data = response.json()
    assert "Em Revisão" in data["status"] or "Bloqueado" in data["status"]
    assert "CHECKOUT_TOO_FAST" in data["reasons"]

def test_fraude_biometria_cartao_colado():
    """Cenário de Fraude: Comprador colou o número do cartão com Ctrl+V (Cartão furtado)."""
    payload = get_valid_payload()
    payload["is_card_pasted"] = True

    response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    
    assert response.status_code == 200
    data = response.json()
    assert "CARD_NUMBER_PASTED" in data["reasons"]
    assert data["score"] >= 35 # O peso dessa regra é massivo

def test_protecao_pci_dss_schema_validation():
    """Garante que o Pydantic bloqueia payloads inválidos e protege o banco."""
    payload = get_valid_payload()
    del payload["amount"] # Remove um campo obrigatório

    response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    
    assert response.status_code == 422 # Erro de Schema (Unprocessable Entity)

def test_lgpd_dados_anonimizados_no_banco():
    """Garante que os dados do cliente (Nome, CPF e Cartão) nunca são salvos em texto claro no banco de dados."""
    payload = get_valid_payload()
    payload["customer_name"] = "Nome Super Secreto"
    payload["customer_cpf"] = "111.222.333-44"
    
    response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    assert response.status_code == 200
    
    # Conferindo no banco de dados isolado
    db = TestingSessionLocal()
    transaction = db.query(TransactionEntity).filter(TransactionEntity.id == payload["transaction_id"]).first()
    db.close()
    
    assert transaction is not None
    assert transaction.customer_name_encrypted != "Nome Super Secreto" # Está criptografado com Fernet
    assert transaction.customer_cpf_encrypted != "111.222.333-44"
    assert transaction.card_bin_tokenized != payload["card_bin"] # É um hash determinístico HMAC

def test_tokenizacao_hmac_deterministica():
    """Garante que a tokenização por HMAC é determinística para permitir detecção de cartões clonados reincidentes."""
    payload1 = get_valid_payload()
    payload2 = get_valid_payload()
    # Mesmo cartão usado em duas compras diferentes
    payload1["card_bin"] = "411111"
    payload1["card_last_four"] = "1111"
    payload2["card_bin"] = "411111"
    payload2["card_last_four"] = "1111"

    client.post("/api/v1/transactions/evaluate", json=payload1, headers=get_auth_headers())
    client.post("/api/v1/transactions/evaluate", json=payload2, headers=get_auth_headers())

    db = TestingSessionLocal()
    t1 = db.query(TransactionEntity).filter(TransactionEntity.id == payload1["transaction_id"]).first()
    t2 = db.query(TransactionEntity).filter(TransactionEntity.id == payload2["transaction_id"]).first()
    db.close()

    assert t1.card_bin_tokenized is not None
    assert t1.card_bin_tokenized == t2.card_bin_tokenized # Hashes idênticos para o mesmo cartão
    assert t1.card_last4_tokenized == t2.card_last4_tokenized

def test_circuit_breaker_fallback():
    """Cenário de Resiliência: Se o Circuit Breaker abrir, a transação recebe status fallback."""
    with patch('src.services.transaction_service.ai_engine.evaluate_risk') as mock_evaluate:
        # Simulamos que o circuit breaker abriu e lançou a exceção
        mock_evaluate.side_effect = pybreaker.CircuitBreakerError("Breaker is open")
        
        payload = get_valid_payload()
        response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 65
        assert "CIRCUIT_BREAKER_FAIL_SAFE" in data["reasons"]
        assert "Em Revisão" in data["status"]

def test_falha_risco_alto_anomalia_geografica():
    """Cenário de Fraude: Valor da transação muito alto levanta suspeita."""
    payload = get_valid_payload()
    payload["amount"] = 6000.00
    
    response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    assert response.status_code == 200
    data = response.json()
    
    assert "HIGH_AMOUNT_ANOMALY" in data["reasons"]
    assert data["score"] >= 35 # Base 10 + 25 de anomalia = 35 ou mais

def test_auditoria_assincrona_gravada_no_banco():
    """Garante que a transação gera registro de auditoria imutável (AuditLogEntity) via BackgroundTask."""
    payload = get_valid_payload()
    response = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    assert response.status_code == 200

    db = TestingSessionLocal()
    audit = db.query(AuditLogEntity).filter(AuditLogEntity.transaction_id == payload["transaction_id"]).first()
    db.close()

    assert audit is not None
    assert audit.endpoint_accessed == "/api/v1/transactions/evaluate"
    assert audit.client_ip is not None


def test_transacao_duplicada_retorna_409_conflict():
    """Garante que a tentativa de reprocessamento do mesmo transaction_id retorna 409 Conflict."""
    payload = get_valid_payload()
    # Primeira requisicao: sucesso (200)
    res1 = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    assert res1.status_code == 200

    # Segunda requisicao identica: conflito (409)
    res2 = client.post("/api/v1/transactions/evaluate", json=payload, headers=get_auth_headers())
    assert res2.status_code == 409
    assert "ja processada anteriormente" in res2.json()["detail"]


def test_health_check_detalhes_conectividade():
    """Garante que o health check ativo executa probe no banco e informa conectividade."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"

