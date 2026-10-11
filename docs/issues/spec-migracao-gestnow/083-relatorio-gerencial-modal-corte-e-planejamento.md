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

## Registro de execução

Fatia entregue em 11/10/2026: o **modal de emissão**, o **motor de corte** e as **duas folhas de
Planejamento**. As rotas (`routes.py`, `/api/relatorio/gerencial`, nomes `report_*`) são READ —
o Visualizador vê as folhas e a situação que o modal mostra: `GET gerencial` desenha as folhas no
escopo do request (`?projeto=portfolio|<id>`) e no corte do período (`tipo`, `periodo`,
`secoes`); `GET|POST gerencial/emissao` abre e redesenha o modal, que traz **Relatório de**
(Portfólio ou projeto; trocar re-renderiza pelo servidor), **Tipo**, **Período** (do início do
escopo ao corrente, mais recente primeiro, com "(em andamento)"/"(padrão)"), a **situação real
do relato** (registrado/pendente com o link `?abrir=1`; no Portfólio, uma linha por projeto) e
das **análises dos seis módulos** (registrada / N desvios sem comentário / pendente, com o link
`?analise=1` da tela de cada um — mapa `REPORT_ANALYSIS_SCREENS`), **Conteúdo** (só Planejamento
nesta fatia: `REPORT_SECTIONS` cresce nas 084/085) e **Formato**; **Emitir** navega para
`/relatorio/gerencial?projeto=&tipo=&periodo=&secoes=`. A tela (`gerencial.html/.css/.js`
reescritos) tem os botões **Emitir relatório** e **Imprimir / PDF**, abre o modal sem
`tipo`/`periodo` ou com `?relatorio=1`, carrega as folhas no alvo `gerencial-conteudo` e, depois
de renderizar, **encaixa a fonte** de cada folha que passar da altura útil, de 8,6 pt até o
mínimo de 6,4 pt (o `ajustar` do protótipo); a impressão é a do navegador, A4 na horizontal, uma
folha por página, com a página nomeada `@page relatorio-gerencial` (sem margem — a margem está
dentro da folha) e a navegação fora pelo mecanismo do DS — a página nomeada é o que impede o
`margin: 0` do relatório de mexer no `@page` do imprimível genérico da 017. O **motor de corte**
(`calculations.py`) tem `report_period_cutoff` (fim do período limitado à referência),
`is_partial_period`, `bar_periods`/`period_bars` (8 semanas ou 6 meses até o corte, sem períodos
antes do início) e `chart_reading` (a leitura semanal do dono: o previsto interpolado dentro do
mês e o real medido). A **folha 1** sai da leitura das fachadas donas no corte — no Mensal a
posição é o ponto do mês (o mesmo das telas); no Semanal o previsto interpola dentro do mês e o
real é o medido (a semana do gráfico da Curva S do dono), com SPI anterior, avanço do período,
término pela tendência x linha de base, desvio acumulado, produtividade da janela (SPI de
quantidades, FP, aderência, pessoas trabalhando, utilização, HH paralisadas e empresas em
alerta), a Curva S física do dono, as barras e o avanço por área (por projeto, no Portfólio). A
**folha 2** usa a leitura da análise do período do próprio módulo (texto e desvios com o
comentário; sem comentário, "Comentário pendente"; sem análise, aviso e link) e o relato pela
fachada do Planejamento (`find_report` no projeto; `list_reports` no Portfólio, uma vez, para a
situação de cada projeto), com as atividades do período e do próximo e os pontos de atenção com
o risco atrelado; no Portfólio, os relatos dos projetos e os pontos de todos. **Correção do
fechamento**: o subagente registrou como divergência a posição do mês no corte semanal, mas o
critério desta issue exige a interpolação semanal — a folha 1 passou a usar a leitura semanal do
dono (previsto 61,7% em `2026-S38`, contra 65,7% do ponto do mês) e o real medido (61,8%),
nunca interpolado, como em toda a plataforma; o oráculo e a divergência foram ajustados (só o
real medido permanece divergência do protótipo, que o interpolava). O oráculo
(`test_relatorio_oraculo.py`) afirma no projeto 1 em `2026-S38`: corte 20/09, posição 61,7/61,8,
desvio +0,1 p.p., SPI 1,00, posição anterior 58,8/61,8 (SPI 1,05), avanço do período 2,9 x 0,0
p.p., a produtividade da janela, os términos abr/27 x mar/27, as 8 barras e a análise e o relato
registrados; o custo segue no mês de competência (2026-08 no semanal). `ruff check`, `ruff
format --check` e `ty check` limpos; as rodadas do fechamento (relatório, planejamento,
financeiro, suprimentos, riscos, qualidade e HSE — 2.183 testes, duas vezes no subagente e uma no
fechamento, com a correção) passam; a porta de qualidade, 5/5. Excel e "Alterar período" ficam
para a ISSUE-086; as folhas 3 a 7 e a Carteira, para as 084/085.

- DECISAO: posição semanal da folha 1 | o previsto interpola dentro do mês (a leitura semanal do dono) e o real é o medido, nunca interpolado; no Mensal vale o ponto do mês, como as telas | D12, D6, ISSUE-083
- DECISAO: modal READ com a situação real | o Visualizador vê as folhas e a situação (a composição do passo 2 sem exigir WRITE); os links levam ao relato (`?abrir=1`) e à análise (`?analise=1`) de cada módulo | D12, ISSUE-083
- DECISAO: impressão | A4 na horizontal com a página nomeada `@page relatorio-gerencial` (sem margem; a margem é da folha), navegação escondida pelo mecanismo do DS e encaixe da fonte até 6,4 pt; Excel e Alterar período ficam para a 086 | D12, ISSUE-083
- DECISAO: seções | `REPORT_SECTIONS` só com Planejamento nesta fatia; a lista do Conteúdo cresce nas 084/085, e as folhas novas entram pelo mesmo motor | D12, ISSUE-083
- DECISAO: barras e curva | as barras e a posição semanal saem da mesma leitura do dono (a semana do gráfico da curva) e o mês de competência do custo segue `competence_month` — a 084 usa para a folha Financeiro | D12, D6, ISSUE-083
