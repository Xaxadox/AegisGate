import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models.domains import TransactionEntity, AuditLogEntity
from src.models.schemas import (
    TransactionStatus,
    TransactionRequest,
    DashboardMetricsResponse,
    DashboardTransactionItem,
    DashboardTransactionListResponse,
    DashboardReviewResponse,
    DashboardSimulateRequest,
)
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Serviço analítico de Backoffice e Monitoramento de Risco (Dashboard).
    Responsável por consultas agregadas, mascaramento LGPD em tempo de visualização,
    intervenção manual de analistas e orquestração do simulador interativo.
    """

    def __init__(self, db: Session):
        self.db = db
        self.cipher = settings.get_cipher_suite()

    # -------------------------------------------------------------------------
    # 1. Mascaramento LGPD (Privacy by Design na camada de apresentação)
    # -------------------------------------------------------------------------
    def _mask_name(self, raw_name: str) -> str:
        """Exemplo: 'Caio Silva Santos' -> 'C*** S**** S*****'"""
        if not raw_name:
            return "[Não informado]"
        parts = raw_name.strip().split()
        masked_parts = []
        for part in parts:
            if len(part) <= 1:
                masked_parts.append(part)
            else:
                masked_parts.append(part[0] + "*" * (len(part) - 1))
        return " ".join(masked_parts)

    def _mask_cpf(self, raw_cpf: str) -> str:
        """Exemplo: '12345678900' ou '123.456.789-00' -> '***.***.789-00'"""
        digits = "".join(filter(str.isdigit, raw_cpf or ""))
        if len(digits) == 11:
            return f"***.***.{digits[6:9]}-{digits[9:11]}"
        return "***.***.***-**"

    def _decrypt_safe(self, encrypted_data: str) -> Optional[str]:
        """Tenta descriptografar defensivamente; evita Erro 500 caso o token seja inválido."""
        if not encrypted_data:
            return None
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.debug("Falha defensiva na decriptação de dado sensível: %s", e)
            return None

    # -------------------------------------------------------------------------
    # 2. Métricas Agregadas do Dashboard (Cards & Gráficos)
    # -------------------------------------------------------------------------
    def get_metrics(self) -> DashboardMetricsResponse:
        """Calcula agregações diretamente no banco de dados via SQL."""
        total = self.db.query(func.count(TransactionEntity.id)).scalar() or 0
        total_amount = float(
            self.db.query(func.coalesce(func.sum(TransactionEntity.amount), 0.0)).scalar() or 0.0
        )
        approved = (
            self.db.query(func.count(TransactionEntity.id))
            .filter(TransactionEntity.status == "Aprovado")
            .scalar()
            or 0
        )
        review = (
            self.db.query(func.count(TransactionEntity.id))
            .filter(TransactionEntity.status == "Em Revisão")
            .scalar()
            or 0
        )
        blocked = (
            self.db.query(func.count(TransactionEntity.id))
            .filter(TransactionEntity.status == "Bloqueado")
            .scalar()
            or 0
        )
        avg_score = float(
            self.db.query(func.coalesce(func.avg(TransactionEntity.risk_score), 0.0)).scalar()
            or 0.0
        )

        approval_rate = round((approved / total * 100), 2) if total > 0 else 0.0
        review_rate = round((review / total * 100), 2) if total > 0 else 0.0
        blocked_rate = round((blocked / total * 100), 2) if total > 0 else 0.0

        # Contagem dos principais motivos de fraude (últimas 200 transações)
        top_reasons_dict: Dict[str, int] = {}
        recent_txs = (
            self.db.query(TransactionEntity.reasons)
            .order_by(TransactionEntity.created_at.desc())
            .limit(200)
            .all()
        )
        for (reasons_list,) in recent_txs:
            if isinstance(reasons_list, list):
                for reason in reasons_list:
                    top_reasons_dict[reason] = top_reasons_dict.get(reason, 0) + 1

        return DashboardMetricsResponse(
            total_transactions=total,
            total_amount=round(total_amount, 2),
            approved_count=approved,
            review_count=review,
            blocked_count=blocked,
            approval_rate=approval_rate,
            review_rate=review_rate,
            blocked_rate=blocked_rate,
            average_risk_score=round(avg_score, 1),
            top_reasons=top_reasons_dict,
        )

    # -------------------------------------------------------------------------
    # 3. Listagem de Transações com Paginação e Mascaramento
    # -------------------------------------------------------------------------
    def list_transactions(
        self,
        limit: int = 15,
        offset: int = 0,
        status_filter: Optional[str] = None
    ) -> DashboardTransactionListResponse:
        """Retorna transações recentes formatadas com dados anonimizados para a tela."""
        query = self.db.query(TransactionEntity)

        if status_filter:
            clean_status = status_filter.strip()
            if clean_status in ("Aprovado", "Em Revisão", "Bloqueado"):
                query = query.filter(TransactionEntity.status == clean_status)

        total = query.count()
        entities = (
            query.order_by(TransactionEntity.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items: List[DashboardTransactionItem] = []
        for ent in entities:
            raw_name = self._decrypt_safe(ent.customer_name_encrypted)
            raw_cpf = self._decrypt_safe(ent.customer_cpf_encrypted)

            masked_name = self._mask_name(raw_name) if raw_name else "[Protegido LGPD]"
            masked_cpf = self._mask_cpf(raw_cpf) if raw_cpf else "***.***.***-**"

            created_str = (
                ent.created_at.isoformat()
                if isinstance(ent.created_at, datetime)
                else str(ent.created_at)
            )

            # Extração de cartão seguro dos metadados ou tokens
            card_last4 = None
            if isinstance(ent.metadata_info, dict):
                card_last4 = ent.metadata_info.get("card_last_four")

            items.append(
                DashboardTransactionItem(
                    id=ent.id,
                    amount=round(ent.amount, 2),
                    customer_name_masked=masked_name,
                    customer_cpf_masked=masked_cpf,
                    card_bin=None,
                    card_last4=card_last4,
                    status=ent.status,
                    risk_score=ent.risk_score,
                    reasons=ent.reasons if isinstance(ent.reasons, list) else [],
                    metadata_info=ent.metadata_info if isinstance(ent.metadata_info, dict) else {},
                    created_at=created_str,
                )
            )

        return DashboardTransactionListResponse(
            transactions=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    # -------------------------------------------------------------------------
    # 4. Intervenção Manual de Analista de Risco
    # -------------------------------------------------------------------------
    def review_transaction(
        self,
        transaction_id: str,
        new_status: TransactionStatus,
        analyst_note: str,
        client_ip: str
    ) -> DashboardReviewResponse:
        """
        Permite a aprovação ou bloqueio manual de uma transação 'Em Revisão'.
        Preserva o score e as razões originais da IA na íntegra para fins de auditoria.
        """
        tx = self.db.query(TransactionEntity).filter(TransactionEntity.id == transaction_id).first()
        if not tx:
            raise KeyError(f"Transação '{transaction_id}' não encontrada.")

        if tx.status != "Em Revisão":
            raise ValueError(
                f"Transação com status '{tx.status}' não pode ser alterada. "
                "Apenas transações em estado 'Em Revisão' admitem deliberação manual."
            )

        prev_status = tx.status
        tx.status = new_status.value

        # Registra a decisão humana nos metadados sem alterar as features da IA
        meta = dict(tx.metadata_info or {})
        now_utc = datetime.now(timezone.utc).isoformat()
        meta["manual_review"] = {
            "previous_status": prev_status,
            "new_status": new_status.value,
            "analyst_note": analyst_note,
            "reviewed_at": now_utc,
            "client_ip": client_ip,
        }
        tx.metadata_info = meta

        # Cria registro auditável na tabela audit_logs
        audit = AuditLogEntity(
            transaction_id=tx.id,
            client_ip=client_ip,
            endpoint_accessed=f"/api/v1/dashboard/transactions/{tx.id}/review",
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        self.db.commit()

        return DashboardReviewResponse(
            transaction_id=tx.id,
            previous_status=prev_status,
            new_status=new_status.value,
            analyst_note=analyst_note,
            reviewed_at=now_utc,
        )

    # -------------------------------------------------------------------------
    # 5. Simulador Integrado de Checkout (Sandbox de Demonstração)
    # -------------------------------------------------------------------------
    def simulate_transaction(
        self,
        request: DashboardSimulateRequest,
        client_ip: str
    ) -> Dict:
        """
        Gera uma transação simulada e a processa imediatamente pelo motor de IA.
        Permite ao usuário da interface testar cenários com 1 clique.
        """
        now = datetime.now(timezone.utc)
        scenario = (request.scenario or "legitimate").lower()

        tx_id = f"tx_sim_{uuid.uuid4().hex[:8]}"

        if scenario == "bot_speed":
            # Bot ultra-rápido: checkout concluído em 150ms
            started = now - timedelta(milliseconds=150)
            submitted = now
            amount = request.amount or 189.90
            name = request.customer_name or "Bot Automation Test"
            cpf = request.customer_cpf or "11122233344"
            ip = request.customer_ip or client_ip
            uf = request.delivery_state or "SP"
            pasted = request.is_card_pasted if request.is_card_pasted is not None else False
            card_bin = request.card_bin or "411111"
            card_last4 = request.card_last_four or "1234"

        elif scenario == "pasted_card":
            # Biometria suspeita: colou o cartão com Ctrl+V
            started = now - timedelta(seconds=45)
            submitted = now
            amount = request.amount or 380.00
            name = request.customer_name or "Lucas Cartao Colado"
            cpf = request.customer_cpf or "22233344455"
            ip = request.customer_ip or client_ip
            uf = request.delivery_state or "RJ"
            pasted = True
            card_bin = request.card_bin or "555555"
            card_last4 = request.card_last_four or "9999"

        elif scenario == "high_amount":
            # Anomalia de alto valor com checkout rápido
            started = now - timedelta(seconds=1)
            submitted = now
            amount = request.amount or 7490.00
            name = request.customer_name or "Carlos Alvo Fraude"
            cpf = request.customer_cpf or "33344455566"
            ip = request.customer_ip or client_ip
            uf = request.delivery_state or "AM"
            pasted = True
            card_bin = request.card_bin or "606282"
            card_last4 = request.card_last_four or "4444"

        else:
            # Caminho Feliz / Cliente Legítimo
            started = now - timedelta(minutes=2)
            submitted = now
            amount = request.amount or 149.90
            name = request.customer_name or "Caio Cliente Legitimo"
            cpf = request.customer_cpf or "44455566677"
            ip = request.customer_ip or client_ip
            uf = request.delivery_state or "SP"
            pasted = request.is_card_pasted if request.is_card_pasted is not None else False
            card_bin = request.card_bin or "411111"
            card_last4 = request.card_last_four or "1111"

        req_payload = TransactionRequest(
            transaction_id=tx_id,
            amount=amount,
            customer_name=name,
            customer_cpf=cpf,
            customer_ip=ip,
            delivery_state=uf,
            started_checkout_at=started,
            submitted_checkout_at=submitted,
            is_card_pasted=pasted,
            card_bin=card_bin,
            card_last_four=card_last4,
        )

        service = TransactionService(self.db)
        eval_resp = service.process_transaction(req_payload)

        # Registra auditoria da simulação
        audit = AuditLogEntity(
            transaction_id=tx_id,
            client_ip=client_ip,
            endpoint_accessed="/api/v1/dashboard/simulate",
            timestamp=now,
        )
        self.db.add(audit)
        self.db.commit()

        return {
            "transaction_id": eval_resp.transaction_id,
            "status": eval_resp.status.value,
            "score": eval_resp.score,
            "reasons": eval_resp.reasons,
            "scenario": scenario,
            "amount": amount,
            "customer_name_masked": self._mask_name(name),
            "simulated_at": now.isoformat(),
        }
