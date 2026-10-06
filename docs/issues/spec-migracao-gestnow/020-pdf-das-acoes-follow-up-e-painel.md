---
id: ISSUE-020
title: "PDF das ações filtradas, follow-up aos responsáveis e painel da Central"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 5
blocked_by:
  - ISSUE-019
blocks:
  - ISSUE-079
labels:
  - ready-for-agent
source_requirements:
  - HU-049
  - HU-050
  - HU-144
spec_decisions:
  - D12
  - D11
---

# PDF das ações filtradas, follow-up aos responsáveis e painel da Central

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D11.
> Entrega 3 (Central de Ações e Governança), onda 5 (01 Central de Ações).
> Histórias: 49, 50, 144. Bloqueada por: ISSUE-019.

## O que construir

Na tela Ações, **Gerar PDF** produz a versão imprimível só com as ações do
filtro aplicado, no layout do PDF de ações do protótipo. **Enviar follow-up**
manda, pela porta de notificação, um aviso por responsável com as suas ações
em aberto e atrasadas; cada envio fica na trilha e a tela avisa "simulado"
enquanto o envio real estiver desligado.

A tela **Dashboards e KPIs** mostra os indicadores do motor de status único
(Concluída, Atrasada, Em andamento) por origem, por responsável e, no
Portfólio, por projeto, com os visuais da biblioteca.

## Critérios de aceite

- [x] O PDF contém exatamente as ações do filtro aplicado.
- [x] O follow-up gera uma notificação por responsável, com as ações dele, e a trilha registra cada uma.
- [x] As contagens do painel batem com as da lista no mesmo escopo.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste de fachada do follow-up (agrupamento por responsável e notificação
simulada), teste de rota do PDF com filtro e conferência de uma contagem do
painel contra a lista.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `js/pages/central-acoes/acoes.js` e `dashboard.js`, `GI.api.central.resumo`.

## Registro de execução

- Data: 2026-10-06.
- Feito: cálculos, fachada (`panel_service`: dashboard, follow-up), rotas (`panel_routes`), telas (painel, modal de follow-up, botão em Ações), Excel e PDF do painel, testes (`test_painel_calculos/servico/rotas`, incl. PDF com filtro), oráculo do painel, LEIA-ME.
- Pendências: nenhuma de escopo; testes e a porta de qualidade ainda não rodados (política do dono).
