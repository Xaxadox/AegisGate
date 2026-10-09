# AegisGate: API de Detecção de Fraudes em E-commerce

**AegisGate** é um microsserviço REST de alta performance e resiliência focado em avaliação e mitigação de risco de fraudes em transações de checkout em tempo real, construído com conformidade estrita à **LGPD** e ao **PCI-DSS**.

---

## Visão Geral do Sistema

O **AegisGate** atua como um escudo e intermediário crítico entre o checkout da plataforma de e-commerce e o gateway de pagamento:
1. Recebe os dados comportamentais e da transação via requisição autenticada (JWT) com validação semântica estrita na borda (Pydantic V2).
2. Avalia o risco probabilístico de fraude utilizando regras comportamentais, biometria de checkout, anomalias geográficas (GeoIP2) e inteligência artificial.
3. Classifica a transação em:
   * **Aprovado** (Score < 60)
   * **Em Revisão** (Score entre 60 e 84)
   * **Bloqueado** (Score >= 85)
4. Persiste o registro de forma segura, com **criptografia em repouso (AES-256)** para dados sensíveis e **tokenização determinística (HMAC-SHA256)** para cartões.
5. Garante idempotência e semântica REST: tentativas de reprocessamento do mesmo `transaction_id` retornam **HTTP 409 Conflict**.
6. Registra logs de auditoria de forma **assíncrona em background** para manter o tempo de resposta do checkout ultrarrápido.
7. Protege os endpoints com **Rate Limiting** via Redis (com salvaguarda resiliente *Fail-Open*).

---

## Tecnologias Utilizadas

* **Linguagem & Framework:** Python 3.11 + [FastAPI](https://fastapi.tiangolo.com/) com ciclo de vida assíncrono (*Lifespan*)
* **Configuração & Validação:** [Pydantic V2](https://docs.pydantic.dev/) e [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) com validação de segurança *fail-fast* no boot
* **ORM & Banco de Dados:** [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (`DeclarativeBase`) com índices otimizados, suporte a MySQL 8.0 e SQLite para testes locais
* **Cache & Rate Limiting:** [Redis](https://redis.io/) com política de resiliência *Fail-Open*
* **Resiliência:** [PyBreaker](https://github.com/danielfm/pybreaker) (Circuit Breaker Pattern)
* **Segurança e Criptografia:** `cryptography` (Fernet/AES-256), `hmac` (SHA-256), `secrets` e `PyJWT`
* **Inteligência Geográfica:** MaxMind GeoIP2 (`geoip2`) com consulta opcional e defensiva
* **Testes Automatizados:** [Pytest](https://docs.pytest.org/) com 43 testes automatizados cobrindo 100% dos cenários críticos

---

## Princípios de Segurança e Compliance

* **LGPD (Lei Geral de Proteção de Dados):**
  * Dados pessoais do titular (Nome, CPF) são encriptados com AES-256 no banco de dados.
  * O retorno da API inclui o array explicativo `reasons` para garantir o **Direito à Explicação** em decisões automatizadas.
* **PCI-DSS:**
  * O código de segurança (CVV) **nunca** é recebido nem armazenado.
  * BIN e últimos 4 dígitos do cartão são tokenizados via HMAC determinístico com salt seguro, permitindo identificar reincidência de cartões clonados sem expor os dígitos reais.
* **Autenticação e Rate Limiting Obrigatórios (RN01 / RNF001):**
  * Emissão de JWT condicionada à validação estrita de credenciais de parceiros homologados via comparação em tempo constante (`secrets.compare_digest`).
  * Endpoints sensíveis protegidos por limitador de taxa (*Rate Limiting*) para prevenção de ataques de força bruta e DoS.
* **Validação Estrita na Borda (Perimeter Defense):**
  * Bloqueio imediato (HTTP 422) de timestamps retroativos (`submitted < started`), siglas de UFs inexistentes, formatos de IP inválidos e CPFs malformados.
* **Circuit Breaker (RN06):**
  * Caso o motor de IA falhe repetidamente ou fique indisponível, o circuito abre automaticamente e ativa a regra de contingência (*fallback*), enviando a transação para `"Em Revisão"` sem interromper as vendas do lojista.

---

## Estrutura do Projeto

```text
Projeto/
├── docs/                           # Documentação técnica e de negócio
│   ├── api/                        # Contrato OpenAPI (openapi.yaml)
│   ├── arquitetura/                # Diagramas C4 Model
│   ├── banco_de_dados/             # Modelagem MER e schemas DDL
│   ├── compliance/                 # Relatório de Impacto à Privacidade (RIPD / LGPD)
│   ├── requisitos/                 # Documentos de Requisitos e Definição do Projeto
│   └── historico/                  # Registro de Planos e Decisões de Arquitetura
├── src/
│   ├── api/                        # Controladores e rotas HTTP (FastAPI)
│   │   └── routers/                # auth_router.py e transaction_router.py
│   ├── core/                       # Configurações centrais, segurança, banco, exceções e rate limiting
│   │   ├── config.py               # Pydantic Settings com validações fail-fast de produção
│   │   ├── database.py             # SQLAlchemy 2.0 DeclarativeBase e engine pool
│   │   ├── exceptions.py           # Exceções de domínio (DuplicateTransactionError)
│   │   ├── rate_limiter.py         # Rate limiter resiliente backed por Redis
│   │   └── security.py             # JWT Service e autenticação em tempo constante
│   ├── models/                     # Entidades ORM (domains) e DTOs Pydantic V2 (schemas)
│   └── services/                   # Regras de negócio (TransactionService, FraudAI, Audit)
├── tests/                          # Suíte de testes automatizados com pytest (43 testes)
│   ├── test_auth.py                # Testes de autenticação de lojistas parceiros
│   ├── test_config.py              # Testes de configurações e invariantes de segurança
│   ├── test_exceptions.py          # Testes da hierarquia semântica de exceções DDD
│   ├── test_fraud_api.py           # Testes de fluxos E2E, antifraude e Circuit Breaker
│   ├── test_rate_limiter.py        # Testes de fail-open e limites de taxa
│   └── test_schemas.py             # Testes de borda e validações Pydantic V2
├── docker-compose.yml              # Serviços de infraestrutura (MySQL 8 e Redis)
├── requirements.txt                # Dependências do projeto
└── README.md                       # Documentação principal
```

---

## Como Executar Localmente

### 1. Pré-requisitos
* Python 3.11 instalado
* Docker e Docker Compose instalados

### 2. Configurar o Ambiente Virtual
No terminal (PowerShell no Windows):
```powershell
# Criação do ambiente virtual
python -m venv venv

# Ativação do venv
.\venv\Scripts\Activate.ps1

# Instalação das dependências
pip install -r requirements.txt
```

### 3. Configurar as Variáveis de Ambiente
Copie o arquivo de exemplo `.env.example` para `.env`:
```powershell
Copy-Item .env.example .env
```

### 4. Subir a Infraestrutura (MySQL e Redis - Opcional)

Se desejar executar a infraestrutura idêntica à de produção:
```powershell
docker compose up -d
```
> **Nota:** Em desenvolvimento local, o uso do Docker é **opcional**. Por padrão (`ENVIRONMENT=development`), o sistema utiliza banco SQLite local (`fraud_test.db`) e possui resiliência com *fail-open* para o rate limiter caso o Redis não esteja ativo.


### 5. Iniciar a API
```powershell
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
Acesse a documentação interativa Swagger em: [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Executando os Testes Automatizados

A suíte de testes utiliza um banco SQLite em memória isolado para garantir que a base de dados de desenvolvimento não seja poluída:

```powershell
pytest -v
```

A suíte abrange 43 testes automatizados organizados em 6 módulos coesos:
* `tests/test_auth.py`: Autenticação e bloqueio de lojistas não autorizados.
* `tests/test_config.py`: Validação de invariantes de segurança e URLs de banco.
* `tests/test_exceptions.py`: Hierarquia semântica de exceções DDD (Conflict, Auth, Validation, Infra).
* `tests/test_schemas.py`: Validações de borda (datas retroativas, UFs brasileiras, IPv4/IPv6, CPF, cartões).
* `tests/test_rate_limiter.py`: Política de resiliência fail-open e bloqueio HTTP 429.
* `tests/test_fraud_api.py`: Caminhos felizes, regras comportamentais, Circuit Breaker, 409 Conflict, anonimização LGPD e auditoria em background.

---

## Documentação Complementar

* [Modelagem do Banco de Dados (MER)](docs/banco_de_dados/Modelagem_MER.md)
* [Relatório de Impacto à Proteção de Dados (RIPD / LGPD)](docs/compliance/RIPD_LGPD.md)
* [Modelagem de Ameaças (STRIDE)](docs/seguranca/Threat_Modeling_STRIDE.md)
* [Arquitetura C4 Model](docs/arquitetura/C4_Model.md)
* [Especificação de Requisitos](docs/requisitos/documento_requisitos_sistema.txt)
* [Registro de Planos e Decisões de Arquitetura](docs/historico/registro_planos_e_decisoes.md)

---

## Licença

Este projeto é distribuído sob os termos da licença **MIT**. Consulte o arquivo [LICENSE](LICENSE) para obter os termos legais completos.
