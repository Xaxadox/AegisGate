# Modelagem do Banco de Dados

## Diagrama Entidade-Relacionamento (ERD)

```mermaid
erDiagram
    TRANSACTIONS {
        string id PK
        decimal amount
        string customer_name_encrypted
        string customer_cpf_encrypted
        string card_bin_tokenized
        string card_last4_tokenized
        string status "Aprovado, Em Revisão, Bloqueado"
        int risk_score
        json reasons "Array de justificativas"
        json metadata_info "IP, Geoloc, Timestamps"
        datetime created_at
    }
    
    AUDIT_LOGS {
        int id PK
        string transaction_id FK
        string client_ip
        string endpoint_accessed
        datetime timestamp
    }

    TRANSACTIONS ||--o{ AUDIT_LOGS : "gera"
```

## Schemas DDL (MySQL)

```sql
CREATE TABLE transactions (
    id VARCHAR(255) PRIMARY KEY,
    amount DECIMAL(10,2) NOT NULL,
    customer_name_encrypted VARCHAR(512) NOT NULL,
    customer_cpf_encrypted VARCHAR(512) NOT NULL,
    card_bin_tokenized VARCHAR(255),
    card_last4_tokenized VARCHAR(255),
    status ENUM('Aprovado', 'Em Revisão', 'Bloqueado') NOT NULL,
    risk_score INT NOT NULL,
    reasons JSON,
    metadata_info JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(255),
    client_ip VARCHAR(45) NOT NULL,
    endpoint_accessed VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);
```
*(Nota: O campo CVV não existe no schema em conformidade com o PCI-DSS).*
