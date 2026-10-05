---
id: ISSUE-018
title: "Importação de planilha em passos com conferência linha a linha"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-017
blocks:
  - ISSUE-019
  - ISSUE-023
  - ISSUE-029
  - ISSUE-044
  - ISSUE-045
  - ISSUE-051
  - ISSUE-064
  - ISSUE-072
labels:
  - ready-for-agent
source_requirements:
  - HU-139
spec_decisions:
  - D12
---

# Importação de planilha em passos com conferência linha a linha

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 139. Bloqueada por: ISSUE-017.

## O que construir

A importação vira um fluxo genérico do servidor, em passos: baixar o modelo
(Excel gerado pelo construtor da ISSUE-017), enviar o arquivo, conferir linha a
linha com pré-visualização (erro bloqueia a linha, aviso não) e confirmar.
Nada grava antes da confirmação, e a confirmação grava tudo numa transação só.
Cada módulo registra o seu importador: colunas, validação por linha e gravação
pela fachada.

Substitui a leitura de planilha no navegador do protótipo (SheetJS) e elimina o
risco registrado lá.

## Critérios de aceite

- [ ] Um importador de teste percorre os passos: modelo, envio, conferência e confirmação.
- [ ] Linha com erro não grava; linha com aviso grava; a conferência mostra o motivo de cada uma.
- [ ] Cancelar na conferência não grava nada.
- [ ] A confirmação grava tudo ou nada.
- [ ] Arquivo que não é planilha é recusado com 422.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada do fluxo com o importador de teste e testes de rota do envio
e da confirmação. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedente: importação do app de Programação Semanal (conferência e
resultado). Fonte dos passos e da validação: `js/components/importar.js` do
protótipo.
