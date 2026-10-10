import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier

from src.ml.dataset_generator import SyntheticFraudDataGenerator
from src.ml.trainer import FraudModelTrainer
from src.services.fraud_ai_engine import FraudAIEngine


def test_ml_dataset_generator_determinism():
    """Garante que a geracao do dataset sintetico e 100% deterministica com mesma semente."""
    gen1 = SyntheticFraudDataGenerator(random_state=42)
    gen2 = SyntheticFraudDataGenerator(random_state=42)

    X1, y1 = gen1.generate(n_samples=500)
    X2, y2 = gen2.generate(n_samples=500)

    assert X1.shape == (500, 4)
    assert y1.shape == (500,)
    assert (X1 == X2).all()
    assert (y1 == y2).all()


def test_ml_trainer_metrics_and_serialization(tmp_path):
    """Garante que o treinador produz modelo valido com metricas aceitaveis."""
    trainer = FraudModelTrainer(random_state=42)
    target_file = tmp_path / "test_fraud_model.joblib"

    result = trainer.train_and_save(output_path=str(target_file), n_samples=1000)

    assert isinstance(result["model"], RandomForestClassifier)
    assert target_file.exists()
    assert result["metrics"]["accuracy"] > 0.70
    assert result["metrics"]["roc_auc"] > 0.65


def test_hybrid_engine_model_carregado():
    """Garante que a FraudAIEngine carrega com sucesso o modelo treinado."""
    engine = FraudAIEngine()
    assert engine.is_ready is True
    assert engine.model is not None
    assert isinstance(engine.model, RandomForestClassifier)


def test_hybrid_engine_predicao_e_explicabilidade():
    """Garante que o motor hibrido gera scores proporcionais e mantem explicabilidade LGPD."""
    engine = FraudAIEngine()
    now = datetime.now(timezone.utc)

    # 1. Checkout Humano Legítimo
    score_humano, reasons_humano = engine.evaluate_risk(
        amount=120.0,
        started_at=now - timedelta(minutes=2),
        submitted_at=now,
        ip="192.168.1.1",
        uf_delivery="SP",
        is_pasted=False
    )
    assert score_humano < 60
    assert len(reasons_humano) == 0

    # 2. Checkout de Bot Ultra-Rápido
    score_bot, reasons_bot = engine.evaluate_risk(
        amount=120.0,
        started_at=now - timedelta(milliseconds=200),
        submitted_at=now,
        ip="192.168.1.1",
        uf_delivery="SP",
        is_pasted=True
    )
    assert score_bot >= 65
    assert "CHECKOUT_TOO_FAST" in reasons_bot
    assert "CARD_NUMBER_PASTED" in reasons_bot


def test_hybrid_engine_fallback_resiliente_quando_modelo_ausente(tmp_path):
    """Garante que o sistema ativa fallback heuristico caso o modelo esteja inacessivel."""
    caminho_inexistente = tmp_path / "arquivo_fantasma.joblib"
    engine = FraudAIEngine(model_path=str(caminho_inexistente))

    # O motor tenta treinar automatico ou faz fallback seguro
    now = datetime.now(timezone.utc)
    score, reasons = engine.evaluate_risk(
        amount=500.0,
        started_at=now - timedelta(seconds=60),
        submitted_at=now,
        ip="127.0.0.1",
        uf_delivery="RJ",
        is_pasted=False
    )
    assert 0 <= score <= 100
    assert isinstance(reasons, list)
