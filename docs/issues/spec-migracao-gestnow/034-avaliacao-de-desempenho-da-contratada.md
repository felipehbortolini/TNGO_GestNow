---
id: ISSUE-034
title: "Avaliação de desempenho da contratada"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-032
  - ISSUE-027
blocks:
  - ISSUE-035
  - ISSUE-057
  - ISSUE-075
labels:
  - ready-for-agent
source_requirements:
  - HU-097
spec_decisions:
  - D5b
  - D5a
---

# Avaliação de desempenho da contratada

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5b, D5a.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 97. Bloqueada por: ISSUE-032, ISSUE-027.

## O que construir

Aba **Avaliação de desempenho** da ficha do contrato: periodicidade mensal
durante a execução e avaliação final no encerramento. Critérios com nota de 1
a 5 e peso dos parâmetros vigentes (HSE, Qualidade, Prazo, Gestão contratual e
comercial, Recursos e mobilização, Documentação e comunicação). Os pesos ficam
**gravados na avaliação**: mudar o parâmetro depois não muda a nota. Nota
ponderada de 0 a 100 e classe A, B, C ou D pelas notas mínimas dos
parâmetros.

Nota 1 ou 2 em qualquer critério exige anexo de evidência e cria plano de
melhoria na Central (origem Contrato). A avaliação final gera lição de
fornecedor em Rascunho pela fachada de Lições. A atualização da qualificação do
fornecedor é ligada na ISSUE-057, e a nota HSE sugerida pelo 07, na ISSUE-075.
O desempenho ao longo do tempo usa o Gráfico de Áreas de Avaliação.

## Critérios de aceite

- [ ] Nota ponderada e classe têm testes de fronteira (84 e 85, 69 e 70, 49 e 50).
- [ ] Mudar os pesos nos parâmetros não muda avaliação já gravada.
- [ ] Nota 1 ou 2 sem anexo é recusada; com anexo, cria ação na Central com origem Contrato.
- [ ] A avaliação final cria lição em Rascunho com origem no contrato.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (nota e classe) e de fachada (evidência, ação e lição).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: regra de avaliação em `regras.js` e o grupo Avaliação de contratadas da
seção 7.4; README, "Avaliação de desempenho da contratada".
