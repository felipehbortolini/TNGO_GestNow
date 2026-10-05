---
id: ISSUE-083
title: "Relatório gerencial: modal, motor de corte e folhas de Planejamento"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-082
  - ISSUE-044
blocks:
  - ISSUE-084
labels:
  - ready-for-agent
source_requirements:
  - HU-036
  - HU-037
  - HU-038
  - HU-040
spec_decisions:
  - D12
  - D6
---

# Relatório gerencial: modal, motor de corte e folhas de Planejamento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D6.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 36, 37, 38, 40. Bloqueada por: ISSUE-082, ISSUE-044.

## O que construir

O botão **Relatório gerencial** do Início abre o modal: Relatório de
(Portfólio ou projeto), Tipo (Semanal ou Mensal), Período (padrão: semana ou
mês anterior; lista do início do projeto até o corrente), a situação do relato
e da análise de cada módulo (registrada, pendente ou com desvio sem
comentário, com link para registrar), Conteúdo e Formato.

O relatório é uma view do shell (com a barra lateral na tela) com folhas A4 na
horizontal, uma por seção, e o encaixe da fonte (reduzida até caber, mínimo
6,4 pt). O cálculo é **uma única função do servidor** com as regras de corte da
seção 3 do README: corte = fim do período limitado à data de referência;
período em andamento sai marcado como **parcial**; a Curva S física é mensal e,
no semanal, interpolada dentro do mês; o custo é apurado por mês (no semanal,
o último mês fechado).

Esta issue entrega o modal, o motor e as duas folhas de **Planejamento**: (1)
Curva S, KPIs e produtividade (janela de 4 semanas até o corte, metas e
empresas em alerta), com barras do avanço por período e avanço por área; (2)
análise e relato do período, com os pontos de atenção e o aviso com link
quando falta relato ou análise.

## Critérios de aceite

- [ ] As regras de corte têm teste: interpolação semanal, último mês fechado e corte limitado à data de referência.
- [ ] O período em andamento sai marcado como parcial.
- [ ] O modal mostra a situação real de relatos e análises, com os links.
- [ ] A fonte encaixa até 6,4 pt, e a impressão sai sem navegação.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo do motor de corte e de rota da view do relatório.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `relatorio.html` e `js/pages/relatorio.js`, `GI.api.relatorioGerencial` e `periodoPadraoRelatorio`, `css/relatorio.css`; README, "Relatório gerencial: regras".
