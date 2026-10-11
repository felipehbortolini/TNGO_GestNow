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

## Registro de execução

Fatia entregue em 11/10/2026: as folhas **Riscos**, **Qualidade**, **HSE** e a **Carteira de
projetos**. `REPORT_SECTIONS` ganhou riscos/qualidade/hse (seis seções no modal); a **Carteira não
é checkbox** — no Portfólio ela entra sozinha, como a **primeira folha**, como no protótipo — e
`ReportSheets` ganhou `riscos`, `qualidade`, `hse` e `carteira`. A **folha Riscos** (`_risk_sheet`)
sai na **data de referência** (o período só entra nos identificados e encerrados, do histórico, e
na janela da exposição): os KPIs do painel (ativos com "de N cadastrados", as duas faixas mais
altas com a Meta da severidade-alvo — ou atual, sem plano —, a exposição com o **saldo da reserva
de contingência** como limite, lido do `mapa_controle` do Financeiro na mesma data, a revisão
vencida com a pauta e os identificados/encerrados do período pelo `list_risks`), a **matriz P×I
residual** em grade HTML com o tom da faixa e as contagens A/O do dono (`risk_matrix`) e a
**exposição mensal** reconstruída do painel (`evolution`) à esquerda; à direita, a análise e os
**principais** (até 5, maior score residual, com o código encurtado no projeto e completo no
Portfólio — `risk_number`). A **folha Qualidade** (`_quality_sheet`) combina as três posições do
protótipo: **no corte** (em aberto — data até o corte e sem encerramento até ele, exceto
canceladas —, críticas pela mesma lista e o custo acumulado), **no período** (abertas e
encerradas, inspeções com a aprovação contra a meta do grupo `qualidade`, auditorias realizadas
com a conformidade e o custo do período) e **na referência** (a pauta e as auditorias atrasadas);
a série de RNC termina no mês do corte (`quality_series`), as reprovadas saem do registro (até 5)
e a disciplina com mais RNC, do Pareto do painel. A **folha HSE** (`_hse_sheet`) sai no **mês do
corte** — no semanal, o mês parcial com as **ocorrências da semana** (não ambientais, com os
níveis da pirâmide do mês como referência) no lugar do HHT; no mensal, o **HHT previsto** do
histograma de mão de obra do dono —, com TF, TRIF, TG, HiPo, os dias sem afastamento no corte
desde a última LTI (ou o início) e os seis **indicadores proativos** no acumulado do primeiro mês
com HHT; a **pirâmide** e a **evolução de TF e TRIF** reusam os `data-dados` do painel. A
**folha Carteira** (`_carteira_sheet`) espelha a leitura do Início (ISSUE-080) sem chamar
`home_overview`: os mesmos donos por projeto (`portfolio_weights`, `planning_kpis_overview`,
`cost_kpis_overview`, `risk_panel`, `list_panel`, `count_by_status`), a Curva S física ponderada
do Planejamento e os critérios do grupo `portfolio`; os KPIs (projetos, BAC com a linha de base do
mapa, avanço ponderado, SPI e CPI com as faixas do Início, projeção com o VAC compacto), a tabela
por projeto com o total e a situação, a curva (`curva-s-linha`) e os critérios — a situação e o
dinheiro compacto saem das funções puras do Início (`index_band`, `health_label`, `compact_brl`),
para nunca divergirem da tela. Templates novos (`folha_riscos/qualidade/hse/carteira.html`) com os
includes em `folhas.html` (Carteira primeiro) e o texto do Formato em `emissao.html`; a matriz e
os selos no `gerencial.css`; formatadores novos no contexto (`formatar_moeda`, `formatar_num2`,
`formatar_moeda_compacta`) e funções puras novas (`matrix_cell_text`, `risk_number`,
`format_money_compact`). **Correção do fechamento (principal)**: `critical_at_cut` passou a usar a
mesma regra de "em aberto no corte" do KPI 1 (situação e encerramento contra o corte), como o
protótipo — a primeira versão usava a situação atual do dono —, e os comentários que diziam
"corte" na folha Riscos viraram "data de referência". **Divergências registradas** na tabela e no
histórico: a exposição mensal é reconstruída do histórico (o mock era digitado; 45,45,57,80,72,56
no projeto 1 contra 38,41,47,67,62,56), o HHT previsto do mês sai do histograma do dono (147.200
contra 149.700 do mock) e o término pela tendência da Carteira segue o fallback do protótipo (a
tela Início sai sem a data quando a tendência não chega a 100 no calendário congelado), além dos
gráficos (barras com linha acumulada do DS) e da matriz em grade. O **oráculo estendido** afirma
na demonstração, no projeto 1 em `2026-S38` (referência 25/09): Riscos com 7 ativos de 9, Crítico
2 (1A·1O) com meta 0, Alto 1, exposição R$ 3,4 mi com limite de R$ 1,6 mi, 1 revisão vencida, 2
na pauta, matriz com P4×I4 1O em erro, principais `RSK-0004 O16` / `RSK-0003 A15` (vencida) /
`RSK-0001 A12` / `RSK-0006 A9` / `RSK-0002 A8` e evolução 45,45,57,80,72,56 (Portfólio: 16 de 19,
Crítico 4, exposição R$ 4,87 mi, principais com o código completo); Qualidade com 4 abertas, 0
críticas e 1 vencida, no período 1 aberta, 0 encerradas, 3 inspeções com 1 reprovada (66,7% x
meta 95%), 1 auditoria (82,9% x meta 90%), custo de R$ 56.700,00 acumulado e R$ 0 do período,
disciplinas Mecânica 3 (50%) / Civil 2 / Tubulação 1 e a série de setembro 3/1/4/11/90,9%; HSE
com HHT 147.150 no mês, TRIF 6,80 e pirâmide (0,2,5,32,189), acumulado 788.070 com TRIF 8,88 e
(0,16,31,190,1240), 258 dias sem afastamento, 10 ocorrências na semana com níveis (0,0,2,8) e
previsto 147.200 (mensal 2026-08: HHT 140.610 e TRIF 7,11); e a Carteira com BAC de R$ 7,02 bi,
projeção de R$ 7.116,5 mi, VAC de −R$ 96,5 mi, previsto 52,0 x real 48,9, SPI 0,94 e CPI 0,97,
pesos 55,36/29,34/15,30 com Atenção/Crítico/Atenção e os critérios 60/25/15. `ruff check`,
`ruff format --check` e `ty check` limpos; o subagente rodou `tests/relatorio` (149 testes) duas
vezes; no fechamento o principal rodou a suíte escopada 149 duas vezes (uma após a correção), a
**suíte completa (4.032 testes, 18min)** e a porta de qualidade, **5/5**. O Excel, o "Alterar
período" e o restante da impressão ficam para a ISSUE-086.

- DECISAO: seções novas e Carteira automática | riscos/qualidade/hse entram em `REPORT_SECTIONS`; a Carteira não é escolhível — entra sozinha e primeiro no Portfólio, como o protótipo | D12, ISSUE-085
- DECISAO: posições por folha | Riscos na data de referência (período só em identificados/encerrados e na janela); Qualidade no corte, no período e na referência conforme o dado; HSE no mês do corte (semanal parcial com as ocorrências da semana) e o acumulado do primeiro mês com HHT | D12, ISSUE-085
- DECISAO: Carteira espelha o Início sem `home_overview` | os mesmos donos por projeto, a curva ponderada do Planejamento e os critérios do grupo `portfolio`; situação e dinheiro compacto pelas funções puras do Início | D9, ISSUE-080, ISSUE-085
- DECISAO: matriz P x I em grade HTML | o tom da faixa do dono e as contagens A/O por célula; a matriz interativa da tela não serve ao papel | D11, ISSUE-085
- DECISAO: gráficos pelo DS | exposição mensal e RNC por mês em `curva-s-barra-linha`; a pirâmide e a evolução HSE reusam os `data-dados` do painel do dono | D11, ISSUE-085
- DECISAO: HHT previsto do dono | o KPI do mês usa o histograma de mão de obra (147.200 no projeto 1 contra 149.700 do mock) — divergência registrada | ISSUE-085
- DECISAO: em aberto no corte | `open_at_cut` e `critical_at_cut` pela regra do protótipo (data até o corte, encerramento posterior a ele, exceto canceladas), não pela situação atual do dono | ISSUE-085
