import hmac
import hashlib
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import pybreaker

from src.core.config import settings
from src.core.exceptions import DuplicateTransactionError
from src.models.schemas import TransactionRequest, EvaluationResponse, TransactionStatus
from src.models.domains import TransactionEntity
from src.services.fraud_ai_engine import FraudAIEngine

logger = logging.getLogger(__name__)

# Instância de criptografia validada pelas configurações centralizadas
cipher_suite = settings.get_cipher_suite()
TOKENIZATION_SECRET = settings.TOKENIZATION_HMAC_SECRET

# Singleton do motor de IA (mantido para compatibilidade com mocks existentes)
ai_engine = FraudAIEngine()

class TransactionService:
    def __init__(self, db: Session, engine: Optional[FraudAIEngine] = None):
        # Injeção da sessão de banco e do motor de IA (Inversão de Dependência)
        self.db = db
        self.ai_engine = engine or ai_engine

    def _encrypt(self, data: str) -> str:
        return cipher_suite.encrypt(data.encode()).decode()

    def _hash_token(self, data: Optional[str]) -> Optional[str]:
        """
        Gera um token determinístico usando HMAC-SHA256.
        Garante conformidade com PCI-DSS e LGPD enquanto permite identificar
        recorrência de cartões fraudados no banco de dados.
        """
        if not data:
            return None
        return hmac.new(
            TOKENIZATION_SECRET.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

    def process_transaction(self, request: TransactionRequest) -> EvaluationResponse:
        # 1. Proteção de Dados (LGPD) e Anonimização
        enc_name = self._encrypt(request.customer_name)
        enc_cpf = self._encrypt(request.customer_cpf)
        hash_bin = self._hash_token(request.card_bin)
        hash_last4 = self._hash_token(request.card_last_four)

        # 2. Delegação para IA / Circuit Breaker
        try:
            score, reasons = self.ai_engine.evaluate_risk(
                amount=request.amount,
                started_at=request.started_checkout_at,
                submitted_at=request.submitted_checkout_at,
                ip=request.customer_ip,
                uf_delivery=request.delivery_state,
                is_pasted=request.is_card_pasted
            )
        except pybreaker.CircuitBreakerError:
            # Regra de Negócio Crítica (RN06): Circuit Breaker Aberto. A IA caiu. 
            # Colocamos "Em Revisão" provisório para que a venda não seja perdida 100%.
            score = 65 
            reasons = ["AI_SERVICE_UNAVAILABLE", "CIRCUIT_BREAKER_FAIL_SAFE"]
        except Exception as e:
            logger.error("Falha inesperada no motor de avaliacao de risco para %s: %s", request.transaction_id, e, exc_info=True)
            score = 70
            reasons = ["INTERNAL_EVALUATION_ERROR"]

        # 3. Regras de Negocio Estaticas (Limiares Base)
        if score >= 85:
            status = TransactionStatus.BLOCKED
        elif 60 <= score <= 84:
            status = TransactionStatus.REVIEW
        else:
            status = TransactionStatus.APPROVED

        # 4. Persistencia com protecao contra duplicidade e colisao de transacao
        transaction_entity = TransactionEntity(
            id=request.transaction_id,
            amount=request.amount,
            customer_name_encrypted=enc_name,
            customer_cpf_encrypted=enc_cpf,
            card_bin_tokenized=hash_bin,
            card_last4_tokenized=hash_last4,
            status=status.value,
            risk_score=score,
            reasons=reasons,
            metadata_info={
                "ip": request.customer_ip,
                "is_pasted": request.is_card_pasted,
                "delivery_state": request.delivery_state,
                "card_last_four": request.card_last_four,
            }
        )
        
        try:
            self.db.add(transaction_entity)
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.warning("Tentativa de reprocessamento detectada para transaction_id=%s: %s", request.transaction_id, e)
            raise DuplicateTransactionError(request.transaction_id)
        except Exception as e:
            self.db.rollback()
            logger.error("Erro inesperado ao persistir transacao %s: %s", request.transaction_id, e, exc_info=True)
            raise

        # 5. Saída e Conformidade com Contrato
        return EvaluationResponse(
            transaction_id=request.transaction_id,
            status=status,
            score=score,
            reasons=reasons
        )
