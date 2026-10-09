class DomainError(Exception):
    """Excecao base para erros de regras de negocio e dominio."""
    pass


class DuplicateTransactionError(DomainError):
    """Lancada quando uma transacao com o mesmo identificador ja existe no banco de dados."""
    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"Transacao com identificador '{transaction_id}' ja processada anteriormente.")
