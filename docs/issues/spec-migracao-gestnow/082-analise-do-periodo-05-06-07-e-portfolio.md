---
id: ISSUE-082
title: "Análise do período de 05, 06, 07 e do Portfólio"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-081
  - ISSUE-066
  - ISSUE-071
  - ISSUE-075
blocks:
  - ISSUE-083
labels:
  - ready-for-agent
source_requirements:
  - HU-042
  - HU-044
spec_decisions:
  - D6
  - D8
---

# Análise do período de 05, 06, 07 e do Portfólio

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D8.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 42, 44. Bloqueada por: ISSUE-081, ISSUE-066, ISSUE-071, ISSUE-075.

## O que construir

O mesmo modal entra em 05 Painel de riscos, 06 Painel da qualidade e 07 Painel
HSE. Em 05 e 07, só o texto é obrigatório. No 06, os desvios são listados sem
comentário obrigatório: RNC com prazo de tratamento vencido, aprovação em
inspeções e conformidade em auditorias abaixo da meta e auditorias atrasadas.

A análise do **Portfólio** existe para cada módulo, com projeto nulo, escrita
pelo PMO sobre os números consolidados.

## Critérios de aceite

- [ ] Em 05 e 07 só o texto é exigido; no 06, os desvios aparecem sem exigir comentário.
- [ ] A análise do Portfólio grava com projeto nulo e não se mistura com a dos projetos.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada das regras por módulo e do Portfólio.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: README, "Análise do período por módulo: regras" e "Gestão de portfólio".

## Registro de execução

Fatia entregue em 11/10/2026: o modal **Análise do período** abriu nos módulos 05 Painel de
riscos, 06 Painel da qualidade e 07 Painel HSE (botão `data-analise` nas views e
`TN.analise.abrirDoEndereco` nos `iniciar`) e a análise do **Portfólio** passou a existir, com
projeto nulo. `ANALYSIS_MODULES` tem os seis módulos ("05 Gestão de Riscos", "06 Gestão da
Qualidade", "07 HSE") e `DEVIATION_REQUIRED` é `False` nos três novos: em 05 e 07 só o texto é
exigido e não há detecção (o protótipo não define regra); no 06 os desvios são listados sem
comentário obrigatório — comentário existente aparece no campo, comentário curto é aceito e o
longo (> 600) é recusado. A detecção da qualidade (`calculations.quality_deviations`) tem as
quatro chaves do protótipo: `rnc_vencidas` (prazo de tratamento vencido, dias de atraso),
`aprovacao_inspecao` (abaixo da meta vigente; no limite, não é desvio), `conformidade_auditoria`
(idem) e `auditorias_atrasadas`. A coleta não duplica fórmula: no 05 chama
`panel_service.risk_panel` (resumo, exposição VME, revisão vencida e redução média) e
`service.list_risks` (identificados e encerrados no período); no 06, `list_rncs`,
`list_inspections` e `list_audits` recortados pelo período/corte com os cálculos do dono
(`inspection_approval_rate`, `audit_conformity_rate`) e as metas do grupo `qualidade`; no 07, o
painel HSE (`panel`, com o mês do corte no Semanal) e a tela de ocorrências
(`occurrences_screen`), com as taxas `num2` (duas casas) no resumo. No **Portfólio** a análise
nasce com `projeto_id` nulo, a faixa de períodos vai do início mais antigo da carteira
(`_project_start`) e o rótulo é "Portfólio · N projetos"; a UK com `NULLS NOT DISTINCT` e o
`_find`/`_record_of`/`_previous_of` por `project_id` (inclusive `IS NULL`) mantêm a análise do
Portfólio separada da de cada projeto. **Consistência dos donos**: `parameters()` de riscos e
qualidade estourava 422 num corte anterior à vigência da primeira versão; agora cai nos valores
iniciais da plataforma, como planejamento, suprimentos, HSE e financeiro já faziam — sem isso a
análise de qualquer período passado não funcionaria. A carga ganhou a parte
`relatorio-analises-050607` (18 registros: 12 de projeto e 6 do Portfólio) e a parte
`relatorio-analises` da 081 ficou pinada aos módulos 02/03/04, para a base já carregada receber
os novos registros sem duplicar (juntas, as duas partes são os 40 registros do mock).
**Divergência registrada**: no Portfólio, o mock cita `avanco_periodo` em S38 e
`aderencia`/`otd` em agosto que os dados da carteira não sustentam — a detecção segue o motor e
o oráculo afirma as chaves sustentadas (`UNSUPPORTED_KEYS` estendido), em
`docs/DIVERGENCIAS-DO-PROTOTIPO.md`. Os testes estendem os quatro arquivos da 081: detecção e
textos da qualidade, resumos dos 05/06/07, `format_number2`, Portfólio (grava com projeto nulo,
coexiste com a do projeto, exclusão não mistura, faixa e rótulo da carteira, período anterior ao
início recusado), regras por módulo e o oráculo dos 05/06/07 (05/07 vazios; 06 pelas chaves que
a demonstração sustenta; as 18 análises novas na carga). `ruff check`, `ruff format --check` e
`ty check` limpos; as rodadas do fechamento (relatório, riscos, qualidade, HSE, planejamento,
financeiro e suprimentos — 2.143 testes, duas vezes no subagente e uma no fechamento) passam; a
porta de qualidade, 5/5.

- DECISAO: Portfólio com projeto nulo | a análise do Portfólio existe por módulo, sobre os números consolidados, com a faixa de períodos do início mais antigo da carteira e o rótulo "Portfólio · N projetos"; a UK com `NULLS NOT DISTINCT` e as leituras por `project_id` a mantêm separada da de cada projeto | D6, ISSUE-082
- DECISAO: 05 e 07 só o texto | sem detecção de desvios, como o protótipo (`DESVIO_OBRIGATORIO` falso); o resumo vem do painel de riscos e do painel HSE no corte | D6, ISSUE-082
- DECISAO: 06 sem comentário obrigatório | os quatro desvios do protótipo são listados com comentário opcional (curto aceito; até 600); o comentário é gravado pela chave, como nos demais | D6, ISSUE-082
- DECISAO: parâmetros vigentes no corte | sem versão vigente na data, riscos e qualidade usam os valores iniciais da plataforma, como planejamento, suprimentos, HSE e financeiro — a análise de um período passado não pode estourar por falta de versão | ISSUE-082
- DECISAO: parte nova da carga | `relatorio-analises-050607` grava os 18 registros dos 05/06/07 e a parte `relatorio-analises` fica pinada aos 02/03/04: num banco novo as duas somam 40 e num banco já carregado só a nova roda | ISSUE-082
