import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.security import require_auth
from src.core.exceptions import DuplicateTransactionError
from src.models.schemas import TransactionRequest, EvaluationResponse
from src.services.transaction_service import TransactionService
from src.services.audit_service import AuditService

from src.core.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Definição do prefixo padrão para todas as rotas de fraude deste módulo
router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["Transações de Fraude"]
)

evaluate_limiter = RateLimiter(times=120, seconds=60, prefix="evaluate_tx")

@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_auth), Depends(evaluate_limiter)]
)
def evaluate_transaction(
    request_body: TransactionRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Recebe os dados de checkout em JSON, exige autenticação JWT (RN01),
    realiza a injeção de dependência do banco, delega para o Serviço (MVC/POO)
    e agenda o log de auditoria assíncrono em background.
    """
    try:
        service = TransactionService(db)
        response = service.process_transaction(request_body)

        # Auditoria em background: disparada sem reter o retorno do checkout
        client_ip = raw_request.client.host if raw_request.client else request_body.customer_ip
        background_tasks.add_task(
            AuditService.record_audit,
            transaction_id=request_body.transaction_id,
            client_ip=client_ip,
            endpoint="/api/v1/transactions/evaluate"
        )

        return response
    except DuplicateTransactionError as e:
        logger.warning(f"Conflito de transação duplicada {request_body.transaction_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erro inesperado ao avaliar transação {request_body.transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocorreu um erro interno crítico ao avaliar a transação."
        )
