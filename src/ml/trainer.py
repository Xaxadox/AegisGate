import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

from src.ml.dataset_generator import SyntheticFraudDataGenerator

logger = logging.getLogger(__name__)


class FraudModelTrainer:
    """
    Treinador de modelo supervisionado de deteccao de fraudes (Random Forest).
    Responsavel por orquestrar a geracao dos dados, treinamento, avaliacao de metricas
    e persistencia do artefato serializado (.joblib).
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.generator = SyntheticFraudDataGenerator(random_state=random_state)

    def train_and_save(
        self,
        output_path: Optional[str] = None,
        n_samples: int = 10000
    ) -> Dict[str, Any]:
        """
        Executa a pipeline completa:
        1. Geracao do dataset sintetico deterministico
        2. Divisao treino/teste (80/20 estratificada)
        3. Treinamento da Random Forest com pesos balanceados
        4. Calculo de metricas de validacao
        5. Persistencia do artefato no caminho especificado
        """
        logger.info("Iniciando geracao do dataset sintetico com %d amostras...", n_samples)
        X, y = self.generator.generate(n_samples=n_samples)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=0.2,
            random_state=self.random_state,
            stratify=y
        )

        logger.info("Treinando modelo RandomForestClassifier (100 arvores, profundidade 6)...")
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=self.random_state,
            class_weight="balanced",
            n_jobs=-1
        )
        model.fit(X_train, y_train)

        # Avaliacao de metricas
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, y_prob)),
            "n_samples": n_samples,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "fraud_prevalence": float(y.mean())
        }

        logger.info(
            "Treinamento concluido com sucesso! Acuracia: %.4f | F1: %.4f | ROC-AUC: %.4f",
            metrics["accuracy"], metrics["f1_score"], metrics["roc_auc"]
        )

        # Destino padrao: src/ml/fraud_model.joblib
        if output_path is None:
            default_dir = Path(__file__).resolve().parent
            output_file = default_dir / "fraud_model.joblib"
        else:
            output_file = Path(output_path).resolve()

        output_file.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, output_file)
        logger.info("Modelo serializado e salvo com sucesso em: %s", output_file)

        return {
            "model": model,
            "metrics": metrics,
            "saved_path": str(output_file)
        }
