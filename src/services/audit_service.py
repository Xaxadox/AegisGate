import logging
from datetime import datetime, timezone
from src.core.database import SessionLocal
from src.models.domains import AuditLogEntity

logger = logging.getLogger(__name__)

class AuditService:
    session_factory = SessionLocal

    @classmethod
    def record_audit(cls, transaction_id: str, client_ip: str, endpoint: str):
        """
        Grava o log de auditoria em background (Assincronicidade) conforme o
        documento de requisitos e o MER (AuditLogEntity).
        Isola a operação para não degradar a latência do checkout.
        """
        db = cls.session_factory()
        try:
            audit_entry = AuditLogEntity(
                transaction_id=transaction_id,
                client_ip=client_ip or "127.0.0.1",
                endpoint_accessed=endpoint,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(audit_entry)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Erro ao persistir log de auditoria para transação {transaction_id}: {e}")
        finally:
            db.close()
