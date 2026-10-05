---
id: ISSUE-032
title: "Ficha do contrato: cascata de valor, medições e aditivos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-031
blocks:
  - ISSUE-033
  - ISSUE-034
  - ISSUE-060
labels:
  - ready-for-agent
source_requirements:
  - HU-095
spec_decisions:
  - D5a
  - D9
---

# Ficha do contrato: cascata de valor, medições e aditivos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5a, D9.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 95. Bloqueada por: ISSUE-031.

## O que construir

Os contratos (nascem da adjudicação no 04, ligada na ISSUE-060; na
demonstração vêm do mock) passam a ter a **ficha do contrato**, tela de
detalhe com o Financeiro destacado na barra lateral e o Voltar.

Aba **Resumo**: campos comuns (Nº, contratada, objeto, modalidade, valor
original, início, término original e vigente, gestor, fiscal, retenção, prazo
de notificação de claims) e a cascata de valor (valor original, aditivos
aprovados, medido, saldo a faturar) no visual de cascata da biblioteca. Valor
atual = original + aditivos aprovados; Saldo a faturar = valor atual − medido
aprovado.

Aba **Medições** (boletins): Nº, período, itens medidos (quantidade x preço
unitário, ou % do marco), valor bruto, retenção e líquido; situação Em
análise, Aprovada, Faturada, Paga, ou Devolvida com motivo. A medição aprovada
alimenta o realizado do item da EAC, pela fachada do Financeiro, como no
protótipo.

Aba **Aditivos**: novo aditivo com valor e prazo; aprovado, muda o valor atual
e, quando há prazo, o término vigente. Os registros que pedem documento
aceitam anexos.

## Critérios de aceite

- [ ] Cascata, valor atual e saldo a faturar batem com as fórmulas (teste).
- [ ] A medição só anda nas transições permitidas, e a devolução exige motivo.
- [ ] A medição aprovada aparece no realizado do item da EAC.
- [ ] O aditivo aprovado muda o valor atual e o término vigente.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (cascata) e de fachada (fluxo da medição, efeito na EAC e aditivo).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `contrato.html`, `GI.api.financeiro.contrato` e `salvarAditivo`,
`mock-financeiro`; README, "Administração contratual".
