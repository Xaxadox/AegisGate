"""
Script executavel de treinamento do modelo de Machine Learning do AegisGate.
Gera dataset sintetico deterministico, treina Random Forest e salva o artefato.
"""

import sys
import logging
from pathlib import Path

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.ml.trainer import FraudModelTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def main():
    print("=" * 60)
    print(" AegisGate - Pipeline de Treinamento de Machine Learning")
    print("=" * 60)

    trainer = FraudModelTrainer(random_state=42)
    output_target = ROOT_DIR / "src" / "ml" / "fraud_model.joblib"

    result = trainer.train_and_save(
        output_path=str(output_target),
        n_samples=10000
    )

    metrics = result["metrics"]
    print("\nMetricas de Avaliacao do Modelo:")
    print("-" * 40)
    print(f" Amostras de Treino:    {metrics['train_samples']}")
    print(f" Amostras de Teste:     {metrics['test_samples']}")
    print(f" Prevalencia de Fraude: {metrics['fraud_prevalence'] * 100:.2f}%")
    print(f" Acuracia:              {metrics['accuracy'] * 100:.2f}%")
    print(f" Precisao:              {metrics['precision'] * 100:.2f}%")
    print(f" Recall (Revocacao):    {metrics['recall'] * 100:.2f}%")
    print(f" F1-Score:              {metrics['f1_score'] * 100:.2f}%")
    print(f" Area sob ROC (ROC-AUC):{metrics['roc_auc'] * 100:.2f}%")
    print("-" * 40)
    print(f" Artefato salvo em: {result['saved_path']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
