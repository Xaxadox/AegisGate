import numpy as np
from typing import Tuple, List


class SyntheticFraudDataGenerator:
    """
    Gerador de dataset sintetico para treinamento de modelos antifraude.
    Utiliza sementes deterministicas (random_state) para garantir
    reprodutibilidade cientifica e estabilidade nos testes.
    """

    FEATURE_NAMES: List[str] = [
        "amount",
        "checkout_duration",
        "is_card_pasted",
        "geo_mismatch"
    ]

    def __init__(self, random_state: int = 42):
        self.random_state = random_state

    def generate(self, n_samples: int = 10000) -> Tuple[np.ndarray, np.ndarray]:
        """
        Gera amostras de transacoes com features e rotulo binario de fraude.

        Retorna:
            X: Matriz de features de dimensao (n_samples, 4)
            y: Vetor de rotulos binarios (0 = Legítimo, 1 = Fraude) de dimensao (n_samples,)
        """
        rng = np.random.RandomState(self.random_state)

        # 1. Feature: Valor da transacao (distribuicao log-normal para simular e-commerce real)
        # Maioria das compras entre R$ 20 e R$ 800, com cauda longa ate R$ 10.000
        amount = np.exp(rng.normal(loc=5.0, scale=1.1, size=n_samples))
        amount = np.clip(amount, 10.0, 10000.0)

        # 2. Feature: Duracao do checkout em segundos
        # Maioria humana entre 10s e 300s. Injetamos bots (<1.5s) e sessoes lentas (>3600s)
        checkout_duration = rng.exponential(scale=60.0, size=n_samples) + 2.0
        # Injeta ~10% de checouts ultra-rapidos (bots/scripts)
        bot_indices = rng.choice(n_samples, size=int(n_samples * 0.10), replace=False)
        checkout_duration[bot_indices] = rng.uniform(0.1, 1.4, size=len(bot_indices))

        # 3. Feature: Biometria comportamental (Ctrl+V no cartao)
        # Em transacoes normais, ocorre em ~5% dos casos. Em bots, ocorre com frequencia
        is_card_pasted = rng.binomial(n=1, p=0.08, size=n_samples)
        is_card_pasted[bot_indices] = rng.binomial(n=1, p=0.85, size=len(bot_indices))

        # 4. Feature: Anomalia geografica (IP diferente do endereco de entrega)
        # Ocorre em ~8% dos casos normais e ~45% de casos suspeitos
        geo_mismatch = rng.binomial(n=1, p=0.08, size=n_samples)
        high_amount_idx = np.where(amount > 5000)[0]
        if len(high_amount_idx) > 0:
            geo_mismatch[high_amount_idx] = rng.binomial(n=1, p=0.35, size=len(high_amount_idx))

        # 5. Calculo da probabilidade latente de fraude baseada em fatores de risco
        risk_score = np.zeros(n_samples, dtype=float)

        # Regra de bot: checkout ultra-rapido
        risk_score += np.where(checkout_duration < 1.5, 0.65, 0.0)

        # Regra comportamental: cartao colado
        risk_score += np.where(is_card_pasted == 1, 0.40, 0.0)

        # Regra de valor: anomalia de alto valor (> 5000)
        risk_score += np.where(amount > 5000.0, 0.35, 0.0)

        # Regra geografica: estado divergente
        risk_score += np.where(geo_mismatch == 1, 0.30, 0.0)

        # Comportamento estavel humano reduz risco
        risk_score -= np.where((checkout_duration >= 20.0) & (is_card_pasted == 0) & (amount < 1000.0), 0.20, 0.0)

        # Converte risco latente em probabilidade via funcao logistica (sigmoide)
        probability = 1.0 / (1.0 + np.exp(-3.5 * (risk_score - 0.45)))
        probability = np.clip(probability, 0.001, 0.999)

        # Gera rotulos binarios a partir da probabilidade
        y = (rng.uniform(0.0, 1.0, size=n_samples) < probability).astype(int)

        # Monta matriz X ordenada
        X = np.column_stack([amount, checkout_duration, is_card_pasted, geo_mismatch])

        return X, y
