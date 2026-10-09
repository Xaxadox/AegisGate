# Modelagem de Ameaças (Threat Modeling) - Framework STRIDE

Análise de vetores de ataque contra a API de Detecção de Fraudes.

| Ameaça (STRIDE) | Descrição do Risco | Mitigação Implementada |
| :--- | :--- | :--- |
| **S**poofing (Falsidade Ideológica) | Um atacante se passar por um lojista parceiro para usar a API. | Autenticação obrigatória via JWT. Chaves secretas armazenadas em cofre externo/variáveis de ambiente, nunca no código. |
| **T**ampering (Violação de Dados) | Atacante alterar o score de fraude de uma transação diretamente no tráfego ou no banco. | Uso obrigatório de HTTPS (TLS). Dados sensíveis no MySQL protegidos por AES-256. |
| **R**epudiation (Repúdio) | Um lojista alegar que não enviou uma transação que resultou em fraude. | Criação de log de Auditoria Assíncrono e imutável para todas as requisições (Tabela `audit_logs`). |
| **I**nformation Disclosure (Vazamento) | Hackers acessarem o banco e roubarem cartões e CPFs dos clientes. | CVV descartado antes de entrar no Core. Partes do cartão recebem Hash irreversível (Tokenization). CPF recebe criptografia bidirecional. |
| **D**enial of Service (DDoS) | Botnet inundando a API com avaliações para travar a infraestrutura. | Implementação de Rate Limiting em memória utilizando Redis e bloqueio na Rede Colaborativa. |
| **E**levation of Privilege | Um lojista comum tentar acessar logs ou configurações sistêmicas da API. | Separação de roles no JWT. Endpoints de configuração isolados em VPC privada. |
