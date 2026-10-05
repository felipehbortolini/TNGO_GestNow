---
id: ISSUE-085
title: "Relatório: folhas Riscos, Qualidade, HSE e Carteira de projetos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-084
  - ISSUE-080
blocks:
  - ISSUE-086
labels:
  - ready-for-agent
source_requirements:
  - HU-038
spec_decisions:
  - D12
  - D8
---

# Relatório: folhas Riscos, Qualidade, HSE e Carteira de projetos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D8.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 38. Bloqueada por: ISSUE-084, ISSUE-080.

## O que construir

Folha **Riscos**: ativos (ameaças e oportunidades), faixas, exposição,
revisão vencida, identificados e encerrados no período (do histórico); matriz
residual (A e O) e exposição mensal das ameaças; análise; principais riscos
(até 5). Folha **Qualidade**: RNC em aberto no corte, abertas e encerradas,
aprovação e conformidade x metas, custo da não qualidade, disciplina com mais
RNC, RNC por mês e inspeções reprovadas, análise e pauta. Folha **HSE**: TF,
TRIF, TG e HiPo do mês com o acumulado, dias sem afastamento no corte, HHT,
pirâmide mês x acumulado, análise, evolução de TF e TRIF e proativos.

No **Portfólio** entra a folha **Carteira de projetos** (KPIs da carteira,
tabela por projeto, Curva S física ponderada e critérios de ponderação), e as
demais folhas trazem os consolidados com o código do projeto (Planejamento com
avanço por projeto e, na segunda folha, a análise da carteira, a situação dos
relatos e os pontos de atenção de todos; Financeiro com a EAC por projeto).

## Critérios de aceite

- [ ] Identificados e encerrados no período saem do histórico, e as demais posições da data de referência, como a folha informa.
- [ ] No Portfólio, a folha Carteira entra e as demais trazem o código do projeto.
- [ ] As folhas mostram os mesmos números das telas no mesmo corte.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo das folhas e do Portfólio.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: README, "Relatório gerencial: regras" (folhas 5 a 7) e "Gestão de portfólio".
