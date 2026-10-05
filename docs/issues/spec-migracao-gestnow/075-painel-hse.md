---
id: ISSUE-075
title: "Painel HSE"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 15
blocked_by:
  - ISSUE-072
  - ISSUE-073
  - ISSUE-074
  - ISSUE-034
blocks:
  - ISSUE-079
  - ISSUE-082
labels:
  - ready-for-agent
source_requirements:
  - HU-122
spec_decisions:
  - D6
  - D11
---

# Painel HSE

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11.
> Entrega 7 (Qualidade, HSE e Configurações), onda 15 (07 HSE).
> Histórias: 122. Bloqueada por: ISSUE-072, ISSUE-073, ISSUE-074, ISSUE-034.

## O que construir

O **Painel HSE** tem filtro de Ano e Mês e os KPIs reativos (TF, TRIF, TG e
HiPo) em dois blocos, "No mês selecionado" e "Acumulado" (do primeiro mês com
HHT até o mês escolhido); "Dias sem afastamento" e "Ações HSE no prazo" ficam
só no acumulado. Duas pirâmides (mês e acumulado), no visual da ISSUE-016,
comparadas com a proporção de referência do parâmetro (Bird ou Heinrich). Os
proativos (relato de quase acidentes, DDS realizados ÷ programados,
observações por 10 mil HHT com a meta, conformidade em inspeções, ações no
prazo, recomendações fechadas, incidentes ambientais), a evolução mensal de TF
e TRIF (linhas múltiplas) e as ocorrências por empresa e área.

Taxas na base do parâmetro (1.000.000 de HHT, NBR 14280, ou 200.000, OSHA):
TF = (fatalidades + afastamentos) x base ÷ HHT; TRIF = (fatalidades +
afastamentos + trabalho restrito + tratamento médico) x base ÷ HHT; TG = (dias
perdidos + debitados) x base ÷ HHT. Dias sem afastamento: desde a última LTI;
sem LTI, desde o início do projeto.

A nota HSE da contratada alimenta o critério HSE da avaliação de desempenho
(03), como no protótipo.

## Critérios de aceite

- [ ] TF, TRIF e TG têm teste, inclusive HHT zero.
- [ ] Trocar a base ou a referência no parâmetro recalcula na hora.
- [ ] Dias sem afastamento conta da última LTI ou do início do projeto.
- [ ] O oráculo afirma 263 dias sem afastamento e a pirâmide acumulada 0/16/31/190/1.240.
- [ ] A avaliação de desempenho recebe a nota HSE da contratada.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo das taxas, o oráculo do HSE e o teste da ligação com a avaliação.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `painel.html` do HSE, `GI.api.hse.indicadores`, nível da pirâmide em `regras.js`; README, "07 HSE". O botão Análise do período chega na ISSUE-082.
