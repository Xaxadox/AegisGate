import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.schemas import (
    DashboardMetricsResponse,
    DashboardTransactionListResponse,
    DashboardReviewRequest,
    DashboardReviewResponse,
    DashboardSimulateRequest,
)
from src.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard & Backoffice"]
)


@router.get(
    "/metrics",
    response_model=DashboardMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Métricas consolidadas de risco e volume para o dashboard"
)
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Retorna KPIs agregados em tempo real (total processado, taxas de status, score médio e anomalias)."""
    try:
        service = DashboardService(db)
        return service.get_metrics()
    except Exception as e:
        logger.error("Erro ao calcular metricas do dashboard: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao calcular métricas analíticas do painel."
        )


@router.get(
    "/transactions",
    response_model=DashboardTransactionListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listagem paginada de transações com proteção LGPD"
)
def list_dashboard_transactions(
    limit: int = 15,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lista as transações mais recentes com nomes e CPFs mascarados para proteção à privacidade."""
    try:
        clamped_limit = max(1, min(limit, 50))
        clamped_offset = max(0, offset)
        service = DashboardService(db)
        return service.list_transactions(limit=clamped_limit, offset=clamped_offset, status_filter=status)
    except Exception as e:
        logger.error("Erro ao listar transacoes no dashboard: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao carregar listagem de transações."
        )


@router.post(
    "/transactions/{transaction_id}/review",
    response_model=DashboardReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Deliberação manual do analista sobre transação em revisão"
)
def review_transaction(
    transaction_id: str,
    payload: DashboardReviewRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Permite aprovar ou bloquear manualmente transações com status 'Em Revisão'."""
    try:
        client_ip = request.client.host if request.client else "127.0.0.1"
        service = DashboardService(db)
        return service.review_transaction(
            transaction_id=transaction_id,
            new_status=payload.new_status,
            analyst_note=payload.analyst_note,
            client_ip=client_ip
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Erro ao deliberar transacao %s: %s", transaction_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha interna ao registrar deliberação manual."
        )


@router.post(
    "/simulate",
    status_code=status.HTTP_200_OK,
    summary="Simulador de checkout interativo para demonstração em tempo real"
)
def simulate_checkout(
    payload: DashboardSimulateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Executa um fluxo simulado de checkout avaliado imediatamente pelo motor de IA."""
    try:
        client_ip = request.client.host if request.client else "127.0.0.1"
        service = DashboardService(db)
        return service.simulate_transaction(request=payload, client_ip=client_ip)
    except Exception as e:
        logger.error("Erro ao executar simulacao no dashboard: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao executar simulação de checkout: {e}"
        )
