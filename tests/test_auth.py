import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_geracao_token_parceiro_valido():
    """Valida geracao de token JWT para parceiro homologado (loja_americanas)."""
    response = client.post("/api/v1/auth/token", json={
        "client_id": "loja_americanas",
        "client_secret": "segredo123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_bloqueio_lojista_desconhecido():
    """Garante que lojistas nao cadastrados sao rejeitados com 401 Unauthorized."""
    response = client.post("/api/v1/auth/token", json={
        "client_id": "loja_invasora_desconhecida",
        "client_secret": "qualquer_segredo"
    })
    assert response.status_code == 401
    assert "não autorizadas" in response.json()["detail"]


def test_bloqueio_lojista_com_segredo_incorreto():
    """Garante que cliente valido com segredo incorreto e rejeitado com 401 Unauthorized."""
    response = client.post("/api/v1/auth/token", json={
        "client_id": "loja_americanas",
        "client_secret": "senha_errada"
    })
    assert response.status_code == 401
    assert "não autorizadas" in response.json()["detail"]


def test_bloqueio_credenciais_vazias():
    """Rejeita payloads sem client_id ou client_secret com 400 Bad Request."""
    response = client.post("/api/v1/auth/token", json={
        "client_id": "",
        "client_secret": ""
    })
    assert response.status_code == 400
