from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from src.core.database import Base

class TransactionEntity(Base):
    __tablename__ = "transactions"

    # Geração automática de UUID para não depender de IDs sequenciais previsíveis (Boa prática de Segurança)
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    amount = Column(Float, nullable=False)
    
    # Valores já chegam aqui devidamente blindados pela camada de Serviço
    customer_name_encrypted = Column(String(512), nullable=False)
    customer_cpf_encrypted = Column(String(512), nullable=False)
    card_bin_tokenized = Column(String(255), nullable=True, index=True)
    card_last4_tokenized = Column(String(255), nullable=True, index=True)
    
    status = Column(Enum('Aprovado', 'Em Revisão', 'Bloqueado', name="transaction_status"), nullable=False, index=True)
    risk_score = Column(Integer, nullable=False)
    
    reasons = Column(JSON, nullable=True) # Explicabilidade LGPD
    metadata_info = Column(JSON, nullable=True) # Dados comportamentais para retreinar IA no futuro
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Rastreabilidade para Segurança
    audit_logs = relationship("AuditLogEntity", back_populates="transaction")


class AuditLogEntity(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(255), ForeignKey("transactions.id"), nullable=False, index=True)
    client_ip = Column(String(45), nullable=False, index=True)
    endpoint_accessed = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    transaction = relationship("TransactionEntity", back_populates="audit_logs")
