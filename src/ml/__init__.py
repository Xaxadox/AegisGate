"""
Pacote de Machine Learning do AegisGate.
Contém gerador de datasets sintéticos determinísticos,
treinamento de modelos Scikit-Learn e utilitários de inferência.
"""

from src.ml.dataset_generator import SyntheticFraudDataGenerator
from src.ml.trainer import FraudModelTrainer

__all__ = ["SyntheticFraudDataGenerator", "FraudModelTrainer"]
