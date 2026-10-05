---
id: ISSUE-022
title: "Anotações e ações da ata por grupo, revisões da ata, histórico e justificativas"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 5
blocked_by:
  - ISSUE-021
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-052
spec_decisions:
  - D9
---

# Anotações e ações da ata por grupo, revisões da ata, histórico e justificativas

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 3 (Central de Ações e Governança), onda 5 (01 Central de Ações).
> Histórias: 52. Bloqueada por: ISSUE-021.

## O que construir

A ficha da ata ganha as abas **Anotações** e **Ações**: itens por Grupo/Área
com a numeração 1 / 1.1, status calculado, colunas configuráveis (modal Colunas
da tabela) e KPIs no rodapé. O modal Nova/editar anotação ou ação (Tipo,
Grupo/Área, Assunto, Descrição, Solicitante, Responsável, Prevista,
Replanejada, Conclusão) grava a anotação como item da ata e a ação pela costura
da Central (origem Ata), de modo que ela aparece na lista da ISSUE-019 com o
link de volta para a ata.

**Gerar nova revisão** (com data) cria a revisão seguinte na mesma linhagem,
levando os itens, e a lista de atas passa a mostrar a nova revisão. Os modais
**Justificativas** (de replanejamento) e **Histórico da ata** mostram a
rastreabilidade.

## Critérios de aceite

- [ ] Os itens saem numerados 1 / 1.1 por grupo, na ordem.
- [ ] A ação criada na ata aparece na lista da Central com origem Ata e link de volta.
- [ ] A nova revisão mantém a linhagem, e a lista passa a mostrar só ela.
- [ ] Histórico e justificativas mostram cada mudança com autor e data.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (numeração por grupo, revisão e criação de ação pela
costura) e revisão de tela da ficha.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `ata.html` e `js/pages/central-acoes/ata.js` do protótipo (modais da
ata listados no README).
