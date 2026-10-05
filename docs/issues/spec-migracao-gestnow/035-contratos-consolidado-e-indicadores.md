---
id: ISSUE-035
title: "Contratos: visão consolidada e indicadores da administração contratual"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-033
  - ISSUE-034
blocks:
  - ISSUE-079
labels:
  - ready-for-agent
source_requirements:
  - HU-098
spec_decisions:
  - D11
---

# Contratos: visão consolidada e indicadores da administração contratual

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 98. Bloqueada por: ISSUE-033, ISSUE-034.

## O que construir

A tela **Contratos: registros** mostra, em abas, Contratos, Claims, Extensões
de prazo, Marcos de pagamento e Avaliações de todos os contratos do escopo, com
filtros e exportação; os registros novos nascem na ficha.

Os KPIs da administração contratual seguem a tabela do protótipo: exposição de
claims por direção, taxa de reconhecimento, tempo médio de resolução,
notificações fora do prazo, extensão de prazo acumulada, dias solicitados x
concedidos, marcos atrasados, aprovado não faturado, pago x previsto e
desempenho das contratadas (nota média, classe, tendência e número de
contratadas C ou D).

## Critérios de aceite

- [ ] Cada um dos dez indicadores tem teste da fórmula.
- [ ] As abas filtram e exportam no escopo escolhido.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo dos indicadores com a data injetada.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `contratos.html`, `GI.api.financeiro.resumoContratos` e `consolidadoContratos`.
