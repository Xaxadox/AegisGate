import os
import logging
import pybreaker
from datetime import datetime
from typing import Tuple, List

from src.core.config import settings

logger = logging.getLogger(__name__)

# Padrão Circuit Breaker: falha se o erro ocorrer 3 vezes, reinicia/tenta de novo após 5 segundos
ai_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=5)

class FraudAIEngine:
    def __init__(self):
        # Na vida real, carregaríamos o modelo scikit-learn treinado aqui
        # Exemplo: self.model = joblib.load('random_forest_model.pkl')
        self.is_ready = True
        self.geoip_db_path = settings.GEOIP_DB_PATH

    def _check_geoip(self, ip: str, uf_delivery: str) -> Tuple[int, List[str]]:
        """
        Consulta opcional e resiliente à base MaxMind GeoIP2.
        Se a base local (.mmdb) existir, cruza o estado do IP com o estado de entrega.
        Se a base não existir, faz bypass seguro sem degradar o fluxo.
        """
        score_diff = 0
        reasons = []

        if not os.path.exists(self.geoip_db_path):
            return score_diff, reasons

        try:
            import geoip2.database
            with geoip2.database.Reader(self.geoip_db_path) as reader:
                response = reader.city(ip)
                subdivisions = response.subdivisions
                if subdivisions:
                    ip_state = subdivisions[0].iso_code
                    if ip_state and ip_state.upper() != uf_delivery.upper():
                        score_diff += 30
                        reasons.append("GEO_STATE_MISMATCH")
        except Exception as e:
            logger.debug("GeoIP lookup falhou para IP %s: %s", ip, e)

        return score_diff, reasons

    @ai_breaker
    def evaluate_risk(
        self,
        amount: float,
        started_at: datetime,
        submitted_at: datetime,
        ip: str,
        uf_delivery: str,
        is_pasted: bool
    ) -> Tuple[int, List[str]]:
        """
        Avalia o risco (0 a 100).
        Atua como um Mock do algoritmo Scikit-Learn usando as features e os pesos acordados.
        """
        score = 10
        reasons = []

        # Feature 1: Velocidade de Checkout (Bots são irreais e anomalias temporais)
        time_diff = (submitted_at - started_at).total_seconds()
        if time_diff < 0:
            score += 80
            reasons.append("INCONSISTENT_CHECKOUT_TIMESTAMPS")
        elif time_diff < 1.5:
            score += 50
            reasons.append("CHECKOUT_TOO_FAST")
        elif time_diff > 3600:
            score += 10
            reasons.append("CHECKOUT_SESSION_STALE")
        
        # Feature 2: Biometria Comportamental (Ctrl+V)
        if is_pasted:
            score += 35
            reasons.append("CARD_NUMBER_PASTED")
            
        # Feature 3: Alto Risco Geográfico e Cruzamento GeoIP
        if amount > 5000:
            score += 25
            reasons.append("HIGH_AMOUNT_ANOMALY")

        geo_score, geo_reasons = self._check_geoip(ip, uf_delivery)
        score += geo_score
        reasons.extend(geo_reasons)

        # Limitador de limite estatístico
        score = min(score, 100)
        
        return score, reasons
