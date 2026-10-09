# Relatório de Impacto à Proteção de Dados Pessoais (RIPD / DPIA)

**Sistema:** API de Detecção de Fraudes
**Finalidade:** Avaliação de risco financeiro e prevenção à fraude no e-commerce.

## 1. Natureza dos Dados Tratados
O sistema atua como **Operador** de dados. O lojista é o **Controlador**.
*   **Dados Pessoais Sensíveis:** CPF, Nome do Titular.
*   **Dados Comportamentais:** IP, Geolocalização, Velocidade de digitação.
*   **Dados Financeiros:** Valor, BIN e últimos 4 dígitos do cartão. *(CVV não é processado).*

## 2. Base Legal (LGPD)
O processamento é amparado pelo **Artigo 7º, inciso X** (Para proteção do crédito) e **inciso VI** (Exercício regular de direitos em contrato).

## 3. Avaliação de Riscos à Privacidade
*   **Risco:** Vazamento da base de dados expondo a identidade de compradores de e-commerces.
*   **Gravidade:** Alta.
*   **Medidas Protetivas:** 
    1. Criptografia AES-256 em repouso no banco de dados.
    2. Política de Retenção Limitada: Dados pessoais podem ser anonimizados após 5 anos.

## 4. Direito à Explicação (Explicabilidade de IA)
Para cumprir as exigências da LGPD referentes a decisões automatizadas, o sistema adota modelo *White-Box*. A API **não** responde apenas com bloqueios silenciosos. O JSON de retorno garante a explicabilidade preenchendo o array `reasons`, permitindo que o titular dos dados compreenda os fatores que levaram à restrição (ex: divergência geográfica).
