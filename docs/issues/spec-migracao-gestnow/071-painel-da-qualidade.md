---
id: ISSUE-071
title: "Painel da qualidade"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 14
blocked_by:
  - ISSUE-069
  - ISSUE-070
blocks:
  - ISSUE-079
  - ISSUE-082
labels:
  - ready-for-agent
source_requirements:
  - HU-119
spec_decisions:
  - D11
---

# Painel da qualidade

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 7 (Qualidade, HSE e Configurações), onda 14 (06 Qualidade).
> Histórias: 119. Bloqueada por: ISSUE-069, ISSUE-070.

## O que construir

O **Painel** da Qualidade mostra os KPIs (RNC em aberto com vencidas e
críticas, tempo médio de tratamento, eficácia na 1ª verificação, aprovação em
inspeções x meta, conformidade em auditorias x meta, aderência ao programa e
custo da não qualidade), o aviso de auditorias atrasadas, RNC por mês (abertas
e encerradas), aprovação em inspeções por mês com a meta, Pareto de RNC por
disciplina, RNC por origem, a pauta de tratamento e o desempenho por empresa.

Fórmulas: aprovação = (aprovadas + com ressalva) ÷ inspeções; conformidade =
conformes ÷ verificados; aderência = realizadas ÷ previstas até a data de
referência; tempo médio = abertura até encerramento; eficácia = encerradas
sem reincidência ÷ encerradas.

## Critérios de aceite

- [ ] Cada fórmula tem teste com fronteira.
- [ ] As metas vêm dos parâmetros vigentes.
- [ ] O Pareto por disciplina sai em ordem decrescente com o acumulado.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo do painel.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `painel.html` da Qualidade, `GI.api.qualidade.indicadores`. O botão Análise do período chega na ISSUE-082.

## Registro de execução

Fatia entregue em 10/10/2026: o painel é uma leitura calculada (D6/D11), sem tabela nova e sem
migração. `painel_service.quality_indicators` devolve os indicadores do protótipo
(`indicadoresQualidadeDe`) — RNC abertas/encerradas/vencidas, verificações vencidas, críticas,
tempo médio de tratamento, eficácia na 1ª verificação, inspeções com aprovação e meta,
conformidade e meta, auditorias realizadas e previstas, aderência ao programa, atrasadas, NC de
auditoria em aberto, ITP e sem aprovação, e o custo da não qualidade —, e é **pública de
propósito**: a ISSUE-079 (Início) vai consumir a mesma função. `quality_panel` acrescenta a
série dos seis meses terminando no mês da data de referência, o Pareto por disciplina, o RNC
por origem, o desempenho por empresa, a pauta de tratamento e o alerta de auditorias atrasadas.
As fórmulas reaproveitam `calculations`/`service` (reincidência pela trilha, vencimentos,
concessão pendente, aprovação com ressalva) e recebem a data de referência como argumento; as
metas saem dos parâmetros vigentes do grupo `qualidade` (`metaAprovacaoInspecaoPct`,
`metaConformidadeAuditoriaPct`) e o limite do tratamento é a faixa `15 a 45 dias` de
`prazoTratamentoDias`. A eficácia na 1ª verificação ganhou fórmula própria
(`calculations.first_time_effectiveness_pct`: encerradas sem reincidência ÷ encerradas, vazio
`·`). As rotas novas vivem em `painel_routes.py` (`quality_panel_view`/`excel`/`printable`,
prefixo único no app), com o alvo `painel-conteudo` e `Access` de leitura; o fragmento
(`api/src/templates/qualidade/painel.html`) traz os cinco KPIs (formatados como o protótipo: o
valor com uma casa fixa — `85,0` —, a meta e a eficácia/aderência arredondadas à unidade — `67`
—, e o custo por extenso, divergência já registrada), o alerta de auditorias atrasadas oculto
quando vazio, os quatro visuais da biblioteca por `data-grafico`/`data-dados` (Curva S Barra e
Linha, Linhas Múltiplas com a meta tracejada, Pareto e Comparativo de Barras) e as duas tabelas;
no Portfólio a pauta abre com a coluna Projeto e a de empresas segue agregada por empresa, como
o protótipo. O trio da tela (view/CSS/JS) registra `TN.paginas["qualidade/painel"]` e carrega o
fragmento no alvo `painel-conteudo`, com o vazio de origem vindo do servidor (`data-situacao`).
Excel e PDF saem pelos mecanismos genéricos, com os números de cada gráfico em tabela (o Excel
não carrega gráficos). O oráculo afirma o projeto 1 em 25/09/2026: **4 RNC abertas e 2
encerradas, 1 vencida, tempo médio de 31 dias, eficácia de 100,0%, aprovação de 85,0% contra a
meta de 95%, conformidade de 86,7% contra a meta de 90%, aderência de 66,7%, 1 auditoria
atrasada (AUD-TN-2026-05), 1 NC de auditoria aberta, 5 ITP com 1 sem aprovação, custo de R$
56.700,00; série de abril a setembro fechando em 3 aberturas, 1 encerramento, 4 em aberto, 11
inspeções e 90,9% de aprovação; Pareto Mecânica 3 → Civil 2 → Tubulação 1 (50,0 / 83,3 / 100,0);
pauta só a RNC-TN-2026-0004 com 8 dias**. `ruff check`, `ruff format --check` e `ty check`
limpos; a suíte (qualidade, Central, Governança, Configurações, plataforma e oráculo — 1.525
testes) passa; a porta de qualidade, 5/5.

- DECISAO: visuais do painel | os quatro gráficos usam os visuais da biblioteca (D11) — Curva S Barra e Linha no RNC por mês, Linhas Múltiplas na aprovação com a meta tracejada, Pareto por disciplina e Comparativo de Barras por origem —, no lugar das barras/linha do protótipo; os números de cada um vão em tabela no Excel e no PDF | D11, ISSUE-071
- DECISAO: indicadores públicos | `painel_service.quality_indicators` nasce pública e documentada porque a ISSUE-079 (Início) lê os mesmos números, como o protótipo (`indicadoresQualidadeDe`) | D6, ISSUE-071
- DECISAO: eficácia na 1ª verificação | fórmula própria em `calculations.first_time_effectiveness_pct`, com a reincidência lida da trilha (D5b); sem encerradas, `·` | D5b, ISSUE-071
- DECISAO: formatos do KPI | o valor percentual sai com uma casa fixa (`85,0`) e a meta e a eficácia/aderência arredondadas à unidade (`67`), como o protótipo (`F.num(..., 1)` e `F.pct(..., 0)`); o custo da não qualidade sai por extenso, como as demais telas (divergência da ISSUE-068) | D1, ISSUE-071

