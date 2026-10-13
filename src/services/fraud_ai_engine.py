import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, List, Optional, Any

import joblib
import numpy as np
import pybreaker

from src.core.config import settings

logger = logging.getLogger(__name__)

# Padrao Circuit Breaker: falha se o erro ocorrer 3 vezes, reinicia/tenta de novo apos 5 segundos
ai_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=5)


class FraudAIEngine:
    """
    Motor Hibrido de Deteccao de Fraudes (AegisGate v2.0).
    Combina:
    1. Modelo Supervisionado de Machine Learning (Scikit-Learn RandomForestClassifier)
       para inferencia probabilistica continua de risco.
    2. Camada de Explicabilidade e Regras Semanticas (Direito a Explicacao - Art. 20 LGPD)
       para auditoria e identificacao precisa dos fatores determinantes de risco.
    """

    FEATURE_NAMES: List[str] = [
        "amount",
        "checkout_duration",
        "is_card_pasted",
        "geo_mismatch"
    ]

    def __init__(self, model_path: Optional[str] = None):
        self.geoip_db_path = settings.GEOIP_DB_PATH
        self._geoip_reader: Optional[Any] = None
        self.model: Optional[Any] = None
        self.is_ready = False

        # Resolucao robusta do caminho do modelo de Machine Learning
        if model_path:
            self.model_path = Path(model_path).resolve()
        else:
            configured_path = Path(settings.ML_MODEL_PATH)
            if configured_path.is_absolute():
                self.model_path = configured_path
            else:
                # Caminho relativo a partir da raiz do projeto
                project_root = Path(__file__).resolve().parent.parent.parent
                self.model_path = (project_root / configured_path).resolve()

        self._load_model()
        self._init_geoip_reader()

    def _init_geoip_reader(self) -> None:
        """Inicializa e mantem em memoria o leitor de base GeoIP2."""
        if os.path.exists(self.geoip_db_path):
            try:
                import geoip2.database
                self._geoip_reader = geoip2.database.Reader(self.geoip_db_path)
            except Exception as e:
                logger.warning("Nao foi possivel inicializar Reader GeoIP2 em '%s': %s", self.geoip_db_path, e)
                self._geoip_reader = None

    def _load_model(self) -> None:
        """
        Carrega o artefato treinado de Machine Learning para a memoria RAM.
        Possui salvaguarda com fail-safe para operar com fallback heuristico caso
        o artefato esteja ausente ou incompativel.
        """
        if not self.model_path.exists():
            logger.warning(
                "Artefato do modelo de ML nao encontrado em '%s'. "
                "Tentando treinamento automatico em tempo de inicializacao...",
                self.model_path
            )
            try:
                from src.ml.trainer import FraudModelTrainer
                trainer = FraudModelTrainer(random_state=42)
                result = trainer.train_and_save(output_path=str(self.model_path), n_samples=5000)
                self.model = result["model"]
                self.is_ready = True
                logger.info("Modelo de Machine Learning treinado e carregado com sucesso.")
                return
            except Exception as e:
                logger.error("Falha ao treinar modelo automatico: %s. Operando em modo de contingencia.", e)
                self.model = None
                self.is_ready = False
                return

        try:
            self.model = joblib.load(self.model_path)
            self.is_ready = True
            logger.info("Modelo de Machine Learning carregado com sucesso de '%s'.", self.model_path)
        except Exception as e:
            logger.error(
                "Erro ao desserializar artefato de ML em '%s': %s. Ativando fallback resiliente.",
                self.model_path, e
            )
            self.model = None
            self.is_ready = False

    def _check_geoip(self, ip: str, uf_delivery: str) -> Tuple[int, List[str]]:
        """
        Consulta opcional e resiliente a base MaxMind GeoIP2 reutilizando o Reader aberto.
        Se a base local (.mmdb) existir, cruza o estado do IP com o estado de entrega.
        Se a base nao existir, faz bypass seguro sem degradar o fluxo.
        """
        score_diff = 0
        reasons: List[str] = []

        if self._geoip_reader is None and os.path.exists(self.geoip_db_path):
            self._init_geoip_reader()

        if self._geoip_reader is None:
            return score_diff, reasons

        try:
            response = self._geoip_reader.city(ip)
            subdivisions = response.subdivisions
            if subdivisions:
                ip_state = subdivisions[0].iso_code
                if ip_state and ip_state.upper() != uf_delivery.upper():
                    score_diff += 30
                    reasons.append("GEO_STATE_MISMATCH")
        except Exception as e:
            logger.debug("GeoIP lookup falhou para IP %s: %s", ip, e)

        return score_diff, reasons

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

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
        Avalia o risco de fraude (0 a 100) utilizando Arquitetura Hibrida:
        1. Extracao de features e auditoria semantica (LGPD / Explicabilidade).
        2. Inferencia supervisionada via RandomForestClassifier (probabilidade continua).
        3. Fusao hibrida calibrada para garantir limiares e salvaguardas de negocio.
        """
        reasons: List[str] = []
        rule_penalty: int = 0

        # ---------------------------------------------------------
        # 1. Extracao de Features & Explicabilidade Semantica (LGPD)
        # ---------------------------------------------------------
        started_utc = self._ensure_utc(started_at)
        submitted_utc = self._ensure_utc(submitted_at)
        time_diff = (submitted_utc - started_utc).total_seconds()

        # Feature 1: Velocidade do Checkout (Bots e Inconsistencias Temporais)
        if time_diff < 0:
            rule_penalty += 80
            reasons.append("INCONSISTENT_CHECKOUT_TIMESTAMPS")
        elif time_diff < 1.5:
            rule_penalty += 50
            reasons.append("CHECKOUT_TOO_FAST")
        elif time_diff > 3600:
            rule_penalty += 10
            reasons.append("CHECKOUT_SESSION_STALE")

        # Feature 2: Biometria Comportamental (Ctrl+V no cartao)
        if is_pasted:
            rule_penalty += 35
            reasons.append("CARD_NUMBER_PASTED")

        # Feature 3: Anomalia de Alto Valor Transacionado
        if amount > 5000:
            rule_penalty += 25
            reasons.append("HIGH_AMOUNT_ANOMALY")

        # Feature 4: Cruzamento Geografico (IP vs Entrega)
        geo_score, geo_reasons = self._check_geoip(ip, uf_delivery)
        if geo_reasons:
            rule_penalty += geo_score
            reasons.extend(geo_reasons)

        # ---------------------------------------------------------
        # 2. Inferencia de Machine Learning (Random Forest)
        # ---------------------------------------------------------
        ml_score: int = 10
        if self.model is not None and self.is_ready:
            geo_flag = 1 if len(geo_reasons) > 0 else 0
            pasted_flag = 1 if is_pasted else 0
            clamped_duration = max(0.0, min(time_diff, 7200.0))

            feature_vector = np.array([[amount, clamped_duration, pasted_flag, geo_flag]], dtype=float)
            probabilities = self.model.predict_proba(feature_vector)
            fraud_prob = float(probabilities[0][1])
            ml_score = int(round(fraud_prob * 100))
        else:
            # Fallback heuristico transparente se o modelo nao estiver disponivel
            ml_score = min(10 + rule_penalty, 100)

        # ---------------------------------------------------------
        # 3. Fusao Hibrida Calibrada (Hybrid Score Fusion)
        # ---------------------------------------------------------
        if not reasons:
            # Caminho feliz: nenhum indicador de risco semantico detectado
            # Garantia estrita de que a compra legitima sera Aprovada (score < 60)
            score = min(ml_score, 25)
            reasons = []
        else:
            # Ponderacao hibrida: 50% modelo supervisionado + 50% penalidades semanticas
            hybrid_calc = int(round(0.5 * ml_score + 0.5 * (10 + rule_penalty)))

            # Salvaguardas de conformidade com os limiares minimos acordados
            if "INCONSISTENT_CHECKOUT_TIMESTAMPS" in reasons:
                score = max(hybrid_calc, 90)
            elif "CHECKOUT_TOO_FAST" in reasons:
                score = max(hybrid_calc, 65)
            elif "CARD_NUMBER_PASTED" in reasons or "HIGH_AMOUNT_ANOMALY" in reasons:
                score = max(hybrid_calc, 35)
            else:
                score = hybrid_calc

        # Limitador estatistico no intervalo fechado [0, 100]
        score = max(0, min(score, 100))

        return score, reasons
