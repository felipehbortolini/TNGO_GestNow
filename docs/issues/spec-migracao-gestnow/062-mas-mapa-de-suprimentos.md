---
id: ISSUE-062
title: "MAS: Mapa de Suprimentos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-061
blocks:
  - ISSUE-063
labels:
  - ready-for-agent
source_requirements:
  - HU-102
spec_decisions:
  - D11
  - D12
---

# MAS: Mapa de Suprimentos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11, D12.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 102. Bloqueada por: ISSUE-061.

## O que construir

O **MAS** não tem cadastro próprio: é montado no servidor a partir do plano de
compras, dos processos e do diligenciamento. Uma linha por pacote e 12 marcos
em dois grupos (Aquisição e Fabricação e entrega), cada um com linha de base,
previsão e realizado.

Situação do marco (`situacaoMarco`): realizado no prazo; realizado com atraso;
vencido sem realização; previsão após a linha de base; a vencer; não se aplica
(fabricação de serviço e EPC). Desvio em dias em relação à linha de base.
Pacote ainda sem pedido tem a linha de base de fabricação **estimada** (itálico
e aviso "LB estimada"), pelas proporções da emissão.

Alternância Datas / Desvio em dias; filtro de fase; filtros por disciplina,
tipo, LLI, comprador, fornecedor e situação, com ordenação; ROS, previsão de
entrega, folga, avanço (real x linha de base) e situação; rodapé com
realizados x previstos por marco; clique na célula abre o detalhe. Avanço de
suprimentos pelos pesos dos marcos do parâmetro (serviço renormaliza só a
aquisição), ponderado pelo valor do pacote; índice = real ÷ previsto.

Exportação Excel (linha de base, previsão ou real e situação de cada marco) e
**PDF A3 paisagem com as células coloridas**.

## Critérios de aceite

- [ ] A situação do marco tem um teste para cada uma das seis regras.
- [ ] Pacote sem pedido mostra a linha de base estimada com o aviso.
- [ ] O avanço de suprimentos e o índice têm teste da fórmula.
- [ ] O PDF sai em A3 paisagem com as células coloridas, e o Excel tem as colunas do protótipo.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (situação, estimativa e avanço) e teste do Excel e da versão imprimível em A3.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `mas.html`, `GI.api.suprimentos.mas`, `GI.regras.situacaoMarco`; README, "MAS (Mapa de Suprimentos): regras".
