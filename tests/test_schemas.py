import pytest
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
from fastapi.testclient import TestClient

from src.main import app
from src.models.schemas import TransactionRequest
from src.core.security import SecurityService

client = TestClient(app)

def get_auth_headers():
    token = SecurityService.create_access_token({"sub": "loja_teste"})
    return {"Authorization": f"Bearer {token}"}

def get_base_data():
    now = datetime.now(timezone.utc)
    return {
        "transaction_id": "tx_schema_test_01",
        "amount": 250.00,
        "customer_name": "Maria Silva",
        "customer_cpf": "123.456.789-00",
        "customer_ip": "177.18.20.1",
        "delivery_state": "RJ",
        "started_checkout_at": (now - timedelta(minutes=1)).isoformat(),
        "submitted_checkout_at": now.isoformat(),
        "is_card_pasted": False,
        "card_bin": "411111",
        "card_last_four": "1234"
    }


def test_schema_valido_sucesso():
    """Garante que dados conformes sao aceitos e normalizados."""
    data = get_base_data()
    req = TransactionRequest(**data)
    assert req.delivery_state == "RJ"
    assert req.customer_ip == "177.18.20.1"
    assert req.card_bin == "411111"
    assert req.card_last_four == "1234"


def test_schema_uf_minuscula_e_normalizada():
    """Garante que 'sp' ou ' rj ' sao normalizados para maiusculas sem espacos."""
    data = get_base_data()
    data["delivery_state"] = " sp "
    req = TransactionRequest(**data)
    assert req.delivery_state == "SP"


def test_schema_rejeita_uf_invalida():
    """Bloqueia siglas que nao pertencem aos 26 estados ou DF."""
    data = get_base_data()
    data["delivery_state"] = "XX"
    with pytest.raises(ValidationError, match="UF de entrega inválida"):
        TransactionRequest(**data)


def test_schema_rejeita_ip_invalido():
    """Bloqueia strings que nao sao IPv4 ou IPv6 validos."""
    data = get_base_data()
    data["customer_ip"] = "999.999.999.999"
    with pytest.raises(ValidationError, match="Endereço IP inválido"):
        TransactionRequest(**data)


def test_schema_aceita_ipv6_valido():
    """Garante que clientes sob IPv6 sao aceitos normalmente."""
    data = get_base_data()
    data["customer_ip"] = "2804:14d:5c73:8000::1"
    req = TransactionRequest(**data)
    assert req.customer_ip == "2804:14d:5c73:8000::1"


def test_schema_rejeita_datas_retroativas():
    """Bloqueia envio fraudulento com checkout submetido antes de ser iniciado."""
    now = datetime.now(timezone.utc)
    data = get_base_data()
    data["started_checkout_at"] = now.isoformat()
    data["submitted_checkout_at"] = (now - timedelta(seconds=10)).isoformat()
    with pytest.raises(ValidationError, match="Inconsistência temporal"):
        TransactionRequest(**data)


def test_schema_rejeita_cpf_com_quantidade_incorreta_de_digitos():
    """Bloqueia CPFs com mais ou menos de 11 digitos."""
    data = get_base_data()
    data["customer_cpf"] = "123.456"
    with pytest.raises(ValidationError, match="CPF deve conter exatamente 11 dígitos"):
        TransactionRequest(**data)


def test_schema_rejeita_card_bin_com_letras_ou_tamanho_errado():
    """Garante integridade de formato no BIN do cartao."""
    data = get_base_data()
    data["card_bin"] = "1234A6"
    with pytest.raises(ValidationError, match="card_bin deve conter apenas dígitos numéricos"):
        TransactionRequest(**data)


def test_api_rejeita_payload_inconsistente_com_status_422():
    """Valida que a rota HTTP responde com 422 Unprocessable Entity para dados invalidos."""
    now = datetime.now(timezone.utc)
    data = get_base_data()
    data["started_checkout_at"] = now.isoformat()
    data["submitted_checkout_at"] = (now - timedelta(minutes=5)).isoformat() # Inconsistencia temporal
    
    response = client.post("/api/v1/transactions/evaluate", json=data, headers=get_auth_headers())
    assert response.status_code == 422
    assert "Inconsistência temporal" in str(response.json())
