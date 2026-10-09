# Documento de Arquitetura de Software (C4 Model)

Este documento descreve a arquitetura do microsserviço de Detecção de Fraudes usando a notação C4 Model.

## 1. Contexto do Sistema (Nível 1)
Descreve como a API se encaixa no ecossistema do E-commerce.

```mermaid
graph TD
    A[Plataforma de E-commerce / Lojista] -->|Envia dados do Checkout| B(API de Detecção de Fraudes)
    B -->|Retorna Score e Status| A
    B -->|Consulta Local| C[Base GeoIP MaxMind]
```

## 2. Diagrama de Contêineres (Nível 2)
Detalha os componentes internos que serão orquestrados via Docker.

```mermaid
graph TD
    A[API do Lojista] -->|HTTPS POST| B(Gateway FastAPI / Core)
    B -->|Leitura/Escrita Rápida| C[(Redis - Rate Limit/Blacklist)]
    B -->|Leitura/Escrita Persistente| D[(MySQL - Transações/Auditoria)]
    B -->|Avaliação em Memória| E[Módulo Scikit-Learn IA]
    B -->|Background Task| F[Processador de Logs Assíncrono]
    F -->|Insere Log| D
```
