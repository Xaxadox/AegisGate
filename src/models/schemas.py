import ipaddress
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from datetime import datetime
from typing import List, Optional
from enum import Enum

# Conjunto oficial de Unidades Federativas do Brasil (26 Estados + DF)
BRAZILIAN_STATES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO"
}

class TransactionStatus(str, Enum):
    APPROVED = "Aprovado"
    REVIEW = "Em Revisão"
    BLOCKED = "Bloqueado"

class TransactionRequest(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=255, description="ID único da transação gerado pelo lojista")
    amount: float = Field(..., gt=0, description="Valor da compra em reais")
    customer_name: str = Field(..., min_length=2, max_length=255, description="Nome completo do comprador")
    customer_cpf: str = Field(..., description="CPF do comprador")
    customer_ip: str = Field(..., description="IP de origem da requisição do cliente")
    delivery_state: str = Field(..., description="UF do endereço de entrega (ex: SP, RJ)")
    started_checkout_at: datetime = Field(..., description="Timestamp de quando o usuário iniciou o checkout")
    submitted_checkout_at: datetime = Field(..., description="Timestamp de quando o usuário clicou em comprar")
    is_card_pasted: bool = Field(default=False, description="Flag que indica se o número do cartão foi colado (Ctrl+V)")
    card_bin: Optional[str] = Field(None, min_length=6, max_length=8, description="6 ou 8 primeiros dígitos do cartão")
    card_last_four: Optional[str] = Field(None, min_length=4, max_length=4, description="4 últimos dígitos do cartão")

    model_config = ConfigDict(
        # extra='ignore' garante que se o frontend enviar o CVV de forma negligente, 
        # ele será descartado imediatamente pelo Pydantic, garantindo o PCI-DSS.
        extra='ignore',
        str_strip_whitespace=True
    )

    @field_validator("delivery_state")
    @classmethod
    def validate_delivery_state(cls, value: str) -> str:
        uf = value.strip().upper()
        if uf not in BRAZILIAN_STATES:
            raise ValueError(f"UF de entrega inválida: '{value}'. Deve ser uma sigla válida de estado brasileiro.")
        return uf

    @field_validator("customer_ip")
    @classmethod
    def validate_customer_ip(cls, value: str) -> str:
        ip_str = value.strip()
        try:
            ipaddress.ip_address(ip_str)
            return ip_str
        except ValueError:
            raise ValueError(f"Endereço IP inválido: '{value}'. Deve ser um IPv4 ou IPv6 válido.")

    @field_validator("customer_cpf")
    @classmethod
    def validate_customer_cpf(cls, value: str) -> str:
        digits = "".join(filter(str.isdigit, value))
        if len(digits) != 11:
            raise ValueError("CPF deve conter exatamente 11 dígitos numéricos.")
        return value.strip()

    @field_validator("card_bin")
    @classmethod
    def validate_card_bin(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            clean = value.strip()
            if not clean.isdigit() or len(clean) not in (6, 8):
                raise ValueError("card_bin deve conter apenas dígitos numéricos (6 ou 8 dígitos).")
            return clean
        return None

    @field_validator("card_last_four")
    @classmethod
    def validate_card_last_four(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            clean = value.strip()
            if not clean.isdigit() or len(clean) != 4:
                raise ValueError("card_last_four deve conter exatamente 4 dígitos numéricos.")
            return clean
        return None

    @model_validator(mode="after")
    def validate_checkout_chronology(self) -> "TransactionRequest":
        if self.submitted_checkout_at < self.started_checkout_at:
            raise ValueError(
                "Inconsistência temporal: submitted_checkout_at não pode ser anterior a started_checkout_at."
            )
        return self

class EvaluationResponse(BaseModel):
    transaction_id: str
    status: TransactionStatus
    score: int = Field(..., ge=0, le=100, description="Score probabilístico de fraude (0 a 100)")
    reasons: List[str] = Field(default_factory=list, description="Justificativas para o score (LGPD Explicabilidade)")


# =====================================================================
# DTOs para o Dashboard de Risco & Simulador (Backoffice)
# =====================================================================

class DashboardMetricsResponse(BaseModel):
    """Métricas agregadas em tempo real para os cards e gráficos do dashboard."""
    total_transactions: int
    total_amount: float
    approved_count: int
    review_count: int
    blocked_count: int
    approval_rate: float
    review_rate: float
    blocked_rate: float
    average_risk_score: float
    top_reasons: dict[str, int]


class DashboardTransactionItem(BaseModel):
    """Item individual da tabela de transações com proteção LGPD por padrão."""
    id: str
    amount: float
    customer_name_masked: str
    customer_cpf_masked: str
    card_bin: Optional[str] = None
    card_last4: Optional[str] = None
    status: str
    risk_score: int
    reasons: List[str]
    metadata_info: Optional[dict] = None
    created_at: str


class DashboardTransactionListResponse(BaseModel):
    """Resposta paginada da listagem de transações para o analista."""
    transactions: List[DashboardTransactionItem]
    total: int
    limit: int
    offset: int


class DashboardReviewRequest(BaseModel):
    """Payload para ação manual do analista de risco sobre transação em revisão."""
    new_status: TransactionStatus = Field(..., description="Novo status deliberado pelo analista (Aprovado ou Bloqueado)")
    analyst_note: str = Field(..., min_length=3, max_length=500, description="Justificativa da intervenção humana")


class DashboardReviewResponse(BaseModel):
    """Confirmação da revisão manual da transação."""
    transaction_id: str
    previous_status: str
    new_status: str
    analyst_note: str
    reviewed_at: str


class DashboardSimulateRequest(BaseModel):
    """Configuração para o simulador de checkout integrado no frontend."""
    scenario: str = Field(default="legitimate", description="Cenário predefinido: legitimate, bot_speed, pasted_card, high_amount")
    amount: Optional[float] = Field(default=None, gt=0)
    customer_name: Optional[str] = None
    customer_cpf: Optional[str] = None
    customer_ip: Optional[str] = None
    delivery_state: Optional[str] = None
    is_card_pasted: Optional[bool] = None
    card_bin: Optional[str] = None
    card_last_four: Optional[str] = None
