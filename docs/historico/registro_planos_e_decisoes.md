# Registro de Planos e Decisões de Arquitetura

Este documento consolida o histórico de análises, diagnósticos de falhas, planos estratégicos e decisões técnicas implementadas no microsserviço de Detecção de Fraudes.

---

## 1. Fase 1: Diagnóstico de Travamentos e Isolamento de Testes

### Contexto e Problema
A IDE e as rotinas de execução apresentavam travamentos e falhas contínuas (Erros 500) durante a execução de testes automatizados com o pytest.

### Diagnóstico Técnico
1. **Colisão de Chaves Primárias no Banco:** O utilitário de criação de payloads fornecia um identificador estático (`transaction_id = "tx_pytest_001"`). Na execução repetida de testes sobre o mesmo arquivo de banco SQLite (`test_pytest.db`), o SQLAlchemy lançava erro de violação de unicidade (`IntegrityError`), gerando exceções não tratadas.
2. **Ausência de Chaves Randômicas:** Os testes não possuíam geração dinâmica de identificadores, causando interdependência entre os casos de teste.

### Decisão e Ações Executadas
* Implementação de gerador de UUID dinâmico no payload de teste (`uuid.uuid4().hex[:8]`).
* Isolamento dos testes em banco SQLite dedicado em memória/arquivo temporário sem afetar a base de desenvolvimento.

---

## 2. Fase 2: Auditoria de Código e Identificação de Débitos Críticos

### Contexto
Realizada varredura completa da base de código confrontando a implementação existente com os requisitos do sistema (RN01 a RN06), padrões de segurança e legislações vigentes (LGPD e PCI-DSS).

### Incongruências e Riscos Identificados
1. **Chave Criptográfica Volátil (Risco Crítico de Perda de Dados):**
   * O `TransactionService` gerava uma nova chave simétrica Fernet aleatória toda vez que a aplicação iniciava se a variável `AES_ENCRYPTION_KEY` estivesse ausente. Isso tornava irrecuperáveis todos os nomes e CPFs criptografados previamente.
2. **Tokenização Não-Determinística (Falha no Modelo Antifraude):**
   * O hash de partes do cartão (BIN e últimos 4 dígitos) utilizava `bcrypt.hashpw` com `gensalt()`. Como o salt era aleatório a cada chamada, compras diferentes com o mesmo cartão furtado geravam hashes distintos, impossibilitando a detecção de reincidência.
3. **Incompatibilidade de Datas (Fuso Horário):**
   * Subtração direta entre datetimes *naive* e *aware* na engine de IA causava `TypeError` em tempo de execução dependendo do formato ISO-8601 enviado pelo cliente.
4. **Ausência de Autenticação JWT (RN01 / RNF001):**
   * Requisito classificado como essencial nos documentos, porém inexistente no código da API (endpoints públicos e desprotegidos).
5. **Auditoria Órfã no Banco de Dados:**
   * A entidade `AuditLogEntity` existia no modelo relacional, mas nenhum registro de auditoria era persistido pelo serviço.
6. **Supressão Cega de Exceções:**
   * Rotas HTTP capturavam exceções genéricas retornando erro 500 sem registrar logs ou stack traces no servidor.

---

## 3. Fase 3: Execução do Plano de Correção e Conformidade

### Decisões Técnicas Implementadas

#### Decisão 3.1: Estabilidade de Criptografia e Conformidade LGPD
* **Implementação:** Configuração de chave Fernet estável via variável de ambiente, com validação de formato Base64 de 32 bytes e fallback determinístico documentado para ambiente local de desenvolvimento.
* **Resultado:** Prevenção contra corrupção de dados e garantia de decriptação contínua de nomes e CPFs.

#### Decisão 3.2: Tokenização Determinística com HMAC-SHA256 (PCI-DSS)
* **Implementação:** Substituição do Bcrypt por HMAC-SHA256 com chave secreta fixa (`TOKENIZATION_HMAC_SECRET`).
* **Resultado:** O mesmo número de cartão sempre produz o mesmo hash criptográfico. Permite ao sistema identificar cartões clonados reincidentes sem violar o PCI-DSS (já que o dado bruto do cartão não é armazenado).

#### Decisão 3.3: Autenticação Baseada em Tokens JWT (RN01 / RNF001)
* **Implementação:**
  * Criação do módulo `SecurityService` (`src/core/security.py`) responsável pela emissão e verificação de tokens padrão HMAC-SHA256.
  * Criação do router `auth_router.py` com o endpoint `POST /api/v1/auth/token`.
  * Injeção da dependência `require_auth` no endpoint `POST /api/v1/transactions/evaluate`.
* **Resultado:** Requisições sem credenciais válidas passam a ser rejeitadas com status HTTP 401 Unauthorized.

#### Decisão 3.4: Auditoria Assíncrona Não-Bloqueante
* **Implementação:**
  * Criação do `AuditService` (`src/services/audit_service.py`) com suporte a injeção da fábrica de sessões do banco.
  * Agendamento de persistência de `AuditLogEntity` utilizando `BackgroundTasks` nativo do FastAPI.
* **Resultado:** O registro de auditoria imutável (IP, endpoint, timestamp) é concluído em background, sem adicionar latência à resposta crítica do checkout.

#### Decisão 3.5: Resiliência de IA e Normalização Temporal
* **Implementação:**
  * Normalização explícita de fusos horários em `fraud_ai_engine.py` antes do cálculo da velocidade de checkout.
  * Suporte a injeção de dependência do motor de IA no `TransactionService` mantendo compatibilidade com o padrão Circuit Breaker (`pybreaker`).

---

## 4. Fase 4: Governança, Testes e Organização do Repositório

### Ações Executadas
1. **Proteção de Versionamento:**
   * Criação do arquivo `.gitignore` isolando arquivos de credenciais (`.env`), bancos SQLite locais (`*.db`), ambientes virtuais (`venv/`) e caches.
2. **Expansão da Cobertura de Testes Automatizados:**
   * Ampliação da suíte para 13 testes unitários e de integração com o pytest cobrindo caminhos felizes, fraudes comportamentais, Circuit Breaker, rejeição de JWT, persistência assíncrona e conformidade LGPD. Todos os 13 testes homologados com 100% de sucesso.
3. **Padronização de Documentação:**
   * Centralização de documentos soltos da raiz para `docs/requisitos/`.
   * Criação do `README.md` técnico e limpo, sem utilização de elementos gráficos ou emojis, com instruções de execução e índice geral.

---

## 5. Fase 5: Centralização de Configurações e Blindagem de Segredos

### Contexto
Auditoria técnica identificou leituras dispersas de variáveis via `os.getenv` em múltiplos módulos, inconsistência no formato de chave AES/Fernet no `.env.example` e ausência de validação em tempo de inicialização (fail-fast), contrariando a regra de segurança §2.

### Decisões Técnicas Implementadas

#### Decisão 5.1: Módulo Centralizado de Configurações (Pydantic Settings)
* **Implementação:** Criação de `src/core/config.py` utilizando `BaseSettings` do `pydantic-settings` para validar todas as configurações da aplicação a partir de tipos estritos e arquivo `.env`.
* **Resultado:** Eliminação de chamadas redundantes a `os.getenv`, garantindo um ponto único de verdade para banco de dados, JWT, Redis e criptografia.

#### Decisão 5.2: Validação de Segurança Fail-Fast no Startup
* **Implementação:** Implementação de `@model_validator` na classe `Settings` para validar no boot do sistema se:
  * A chave `AES_ENCRYPTION_KEY` possui formato válido (Base64 URL-safe de 32 bytes).
  * Em ambiente de produção (`ENVIRONMENT=production`), bloqueia a inicialização se a chave Fernet estiver ausente/inválida ou se segredos padrão de desenvolvimento forem detectados em `JWT_SECRET_KEY` e `TOKENIZATION_HMAC_SECRET`.
* **Resultado:** Impossibilidade de deploy acidental em produção utilizando chaves ou segredos fracos de desenvolvimento.

#### Decisão 5.3: Correção do Contrato de Variáveis no `.env.example`
* **Implementação:** Atualização do `.env.example` com exemplo válido de chave Fernet, inclusão de `TOKENIZATION_HMAC_SECRET` e comando no terminal para geração de novas chaves criptográficas.
* **Resultado:** Prevenção contra fallback silencioso para a chave de desenvolvimento ao configurar ambientes reais.

#### Decisão 5.4: Expansão da Suíte de Testes
* **Implementação:** Criação de `tests/test_config.py` com 6 novos testes unitários validando o carregamento de configurações, bloqueios em ambiente de produção e geração de URLs de banco para SQLite e MySQL.
* **Resultado:** Suíte expandida de 13 para 19 testes automatizados com 100% de aprovação.

---

## 6. Fase 6: Blindagem de Schemas no Pydantic V2 e Defesa em Profundidade na Engine de IA

### Contexto
Auditoria técnica constatou que a borda de entrada da API não realizava validações semânticas em campos cruciais (IP, UF, BIN, últimos 4 dígitos do cartão, CPF e ordenação cronológica de checkout). Isso permitia que fraudadores enviassem timestamps de submissão retroativos (`submitted_checkout_at < started_checkout_at`), distorcendo a regra comportamental de IA com tempo negativo e classificando-a erroneamente como checkout rápido.

### Decisões Técnicas Implementadas

#### Decisão 6.1: Validação Estrita na Borda com Pydantic V2
* **Implementação:** No schema `TransactionRequest` (`src/models/schemas.py`), implementação de validadores de campo e de modelo:
  * `@model_validator`: Garante que `submitted_checkout_at >= started_checkout_at`. Rejeita inconsistências temporais na borda com status HTTP 422 Unprocessable Entity.
  * `@field_validator("delivery_state")`: Valida contra o conjunto oficial de 27 UFs brasileiras e normaliza para caixa alta sem espaços.
  * `@field_validator("customer_ip")`: Utiliza o módulo nativo `ipaddress` para assegurar que apenas IPv4 ou IPv6 legítimos alcancem as camadas de serviço e auditoria.
  * `@field_validator("customer_cpf")`: Valida a presença de exatamente 11 dígitos numéricos.
  * `@field_validator("card_bin")` e `@field_validator("card_last_four")`: Exigem que apenas sequências numéricas (6/8 dígitos para BIN e 4 para final) sejam aceitas para tokenização.
* **Resultado:** Prevenção contra injeção de dados corrompidos nas camadas de negócio, banco e IA, respondendo com HTTP 422 padronizado.

#### Decisão 6.2: Defesa em Profundidade em `FraudAIEngine`
* **Implementação:** Em `src/services/fraud_ai_engine.py`:
  * Adição de anotações de tipo explícitas `started_at: datetime` e `submitted_at: datetime`.
  * Criação de salvaguarda defensiva: caso um cálculo de tempo negativo ocorra, a transação recebe pontuação de alto risco (`score += 80`) e justificativa explícita de anomalia (`INCONSISTENT_CHECKOUT_TIMESTAMPS`), em vez de ser mascarada como bot veloz.
* **Resultado:** O motor de IA é protegido contra relógios descalibrados ou bypasses de validação externa.

#### Decisão 6.3: Expansão da Suíte de Testes
* **Implementação:** Criação de `tests/test_schemas.py` com 9 casos de teste unitários e de integração cobrindo rejeição de UFs inexistentes, normalização de estados minúsculos, rejeição de IPs inválidos, suporte a IPv6, bloqueio de datas retroativas e retorno HTTP 422 na API.
* **Resultado:** Suíte de testes expandida para 28 testes automatizados, todos aprovados com 100% de sucesso.

---

## 7. Fase 7: Resiliência de Transações (HTTP 409 Conflict), Modernização do ORM e Lifespan

### Contexto
Auditoria técnica identificou três pontos críticos de operação:
1. Retentativas ou reenvios da mesma transação pelo gateway de pagamento causavam `IntegrityError` não tratado, resultando em erro 500 no servidor.
2. A criação de tabelas (`Base.metadata.create_all`) era executada no escopo global de importação de `main.py`, quebrando o ciclo de vida assíncrono do FastAPI.
3. As entidades ORM utilizavam `declarative_base()` legado e `datetime.utcnow()` depreciado, carecendo de índices em colunas vitais para consultas de auditoria e antifraude.

### Decisões Técnicas Implementadas

#### Decisão 7.1: Exceção de Domínio e Tratamento de Conflito HTTP 409
* **Implementação:**
  * Criação de `src/core/exceptions.py` com a exceção especializada `DuplicateTransactionError`.
  * Em `TransactionService` (`src/services/transaction_service.py`), captura de `IntegrityError` no commit com rollback explícito e lançamento de `DuplicateTransactionError`.
  * No router (`src/api/routers/transaction_router.py`), captura de `DuplicateTransactionError` respondendo com status HTTP 409 Conflict e detalhe semântico.
* **Resultado:** Transformação de falhas catastróficas (HTTP 500) em respostas semânticas padronizadas (HTTP 409), preservando a estabilidade da integração dos lojistas.

#### Decisão 7.2: Ciclo de Vida Assíncrono com Lifespan no FastAPI
* **Implementação:** Em `src/main.py`, substituição do DDL global por um gerenciador assíncrono de contexto `@asynccontextmanager async def lifespan(app: FastAPI)`.
* **Resultado:** Criação de tabelas controlada no boot do servidor, desacoplando importações e viabilizando pipelines de migração sem efeitos colaterais.

#### Decisão 7.3: Health Check Ativo com Probe de Leitura
* **Implementação:** O endpoint `/health` passou a receber injeção de sessão do banco (`get_db`) e executar um `SELECT 1` ativo via SQLAlchemy.
* **Resultado:** O endpoint atua como uma Readiness Probe real para Docker e orquestradores, retornando o estado ativo da conexão.

#### Decisão 7.4: SQLAlchemy 2.0 (DeclarativeBase) e Indexação de Colunas
* **Implementação:**
  * Migração para `class Base(DeclarativeBase)` em `src/core/database.py`.
  * Em `src/models/domains.py`, inclusão de `index=True` em colunas estratégicas (`transactions`: `status`, `card_bin_tokenized`, `card_last4_tokenized`, `created_at`; `audit_logs`: `transaction_id`, `client_ip`, `timestamp`).
  * Substituição de `datetime.utcnow` pelo padrão moderno `datetime.now(timezone.utc)`.
* **Resultado:** Prevenção contra degradação de I/O em consultas de reincidência de cartões clonados e conformidade técnica com o Python 3.12+.

---

## 8. Fase 8: Autenticação Estrita, Rate Limiting com Redis e Inteligência Geográfica

### Contexto
Conclusão dos 4 pontos finais do plano de excelência:
1. O endpoint de emissão de token JWT aceitava qualquer segredo não vazio sem validar credenciais reais.
2. Os endpoints críticos careciam de controle de taxa (Rate Limiting), deixando o serviço vulnerável a saturação de chamadas e força bruta.
3. O pacote MaxMind GeoIP2 (`geoip2`) constava nas dependências mas não possuía integração resiliente ativa.
4. O `README.md` encontrava-se desatualizado em relação à arquitetura moderna e à suíte de testes.

### Decisões Técnicas Implementadas

#### Decisão 8.1: Autenticação em Tempo Constante (Timing Attacks)
* **Implementação:**
  * Configuração de credenciais de parceiros homologados em `src/core/config.py`.
  * Implementação de `SecurityService.authenticate_merchant` com `secrets.compare_digest` para validação resistente a ataques de temporização.
  * Resposta com status HTTP 401 Unauthorized para qualquer credencial inválida em `src/api/routers/auth_router.py`.
* **Resultado:** Impossibilidade de emissão de tokens JWT forjados por atacantes externos.

#### Decisão 8.2: Rate Limiting com Redis e Resiliência Fail-Open
* **Implementação:**
  * Criação do componente `RateLimiter` (`src/core/rate_limiter.py`) utilizando Redis com pipelines atômicos de incremento e expiração.
  * Aplicação da política de resiliência *Fail-Open*: caso o Redis esteja indisponível, a chamada é liberada com log de debug, garantindo que o checkout nunca seja interrompido por indisponibilidade transitória do cache.
  * Injeção de dependência nos endpoints `/api/v1/auth/token` e `/api/v1/transactions/evaluate`.
* **Resultado:** Proteção ativa contra abuso e DoS, respondendo com HTTP 429 Too Many Requests quando o limite é excedido.

#### Decisão 8.3: Consulta Geográfica Opcional e Defensiva (MaxMind GeoIP2)
* **Implementação:** Em `FraudAIEngine` (`src/services/fraud_ai_engine.py`), implementação do método `_check_geoip` que cruza o estado de entrega com a localização geográfica do IP se o arquivo `.mmdb` existir localmente, atribuindo pontuação de anomalia caso haja divergência (`GEO_STATE_MISMATCH`), ou realizando bypass limpo caso o banco ainda não tenha sido baixado.
* **Resultado:** Ativação imediata da funcionalidade geográfica assim que a base de dados for providenciada, sem quebras na ausência do arquivo.

#### Decisão 8.4: Expansão Final da Suíte de Testes e Documentação
* **Implementação:**
  * Criação de `tests/test_auth.py` e `tests/test_rate_limiter.py`.
  * Reformulação integral do `README.md` refletindo os fluxos de resiliência e diretrizes de execução, estritamente sem emojis.
* **Resultado:** Suíte de testes automatizados homologada com 100% de sucesso.

---

## 9. Fase 9: Versão 2.0 - Arquitetura Híbrida de Inteligência Artificial e Explicabilidade LGPD

### Contexto
O motor de risco da versão 1.0 operava com base em um mock de regras puramente determinístico. Para atender a exigências acadêmicas e padrões avançados de mercado em MLOps, era necessário incorporar um modelo de Machine Learning real treinado com dados supervisionados, sem comprometer os contratos de API existentes, os limiares de negócio ou a explicabilidade exigida pelo Artigo 20 da LGPD.

### Decisões Técnicas Implementadas

#### Decisão 9.1: Pipeline de Dados Sintéticos e Treinamento Determinístico
* **Implementação:**
  * Criação do pacote `src/ml/` contendo `SyntheticFraudDataGenerator` e `FraudModelTrainer`.
  * Geração determinística de 10.000 amostras sintéticas com semente fixa (`random_state=42`) para evitar não-determinismo nos testes.
  * Treinamento supervisionado com `RandomForestClassifier` (100 árvores, profundidade 6, pesos balanceados) da biblioteca Scikit-Learn.
  * Criação do script executável `scripts/train_ml_model.py` com exibição de métricas (Acurácia, F1-Score, ROC-AUC) e persistência do artefato em `src/ml/fraud_model.joblib`.
* **Resultado:** Modelo com 83.25% de acurácia e 78.93% de ROC-AUC treinado e serializado de forma reproduzível.

#### Decisão 9.2: Fusão Híbrida e Explicabilidade Semântica (LGPD Art. 20)
* **Implementação:**
  * Refatoração da classe `FraudAIEngine` (`src/services/fraud_ai_engine.py`) para operar como motor híbrido.
  * Combinação de inferência probabilística contínua (`predict_proba`) do Scikit-Learn com análise semântica de atributos (tempo de checkout, biometria colada, anomalias de valor e geolocalização).
  * Manutenção do array `reasons` preenchido com os fatores determinantes de risco para garantir o Direito à Explicação.
  * Implementação de salvaguardas de limiares (Score < 60 para compras normais e Score >= 65 para bots ultra-rápidos).
* **Resultado:** Conformidade legal plena com a LGPD e preservação de 100% dos contratos e comportamentos esperados pelo gateway de pagamento.

#### Decisão 9.3: Resiliência de Boot e Fallback de Contingência
* **Implementação:**
  * Resolução de caminhos do artefato de ML via caminhos absolutos baseados em `Path(__file__).resolve()`.
  * Auto-recuperação no startup: se o artefato `.joblib` não existir, o sistema executa o treino automático em tempo de boot ou ativa fallback heurístico defensivo.
  * Manutenção do Circuit Breaker (`@ai_breaker`) protegendo a chamada de inferência contra esgotamento de recursos.
* **Resultado:** Prevenção contra falhas `FileNotFoundError` e degradação suave em ambientes de teste.

#### Decisão 9.4: Ampliação da Cobertura com Testes Dedicados
* **Implementação:** Criação de `tests/test_hybrid_ai.py` cobrindo determinismo do gerador, métricas de treinamento, carregamento do artefato, predilção de bots vs humanos e fallback para artefatos ausentes.
* **Resultado:** Suíte expandida para 48 testes automatizados, todos aprovados com 100% de sucesso.
