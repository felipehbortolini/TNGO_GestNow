---
id: ISSUE-081
title: "Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-040
  - ISSUE-042
  - ISSUE-044
  - ISSUE-048
  - ISSUE-063
blocks:
  - ISSUE-082
labels:
  - ready-for-agent
source_requirements:
  - HU-042
  - HU-043
  - HU-044
  - HU-045
spec_decisions:
  - D6
---

# Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 42, 43, 44, 45. Bloqueada por: ISSUE-040, ISSUE-042, ISSUE-044, ISSUE-048, ISSUE-063.

## O que construir

O botão **Análise do período** abre o modal em 02 Relato do período e KPIs, 03
KPIs de custo e Curva S financeira e 04 Painel de suprimentos. Passo 1: tipo e
período (lista com a situação: registrada, pendente ou em andamento; padrão:
período anterior). Passo 2: resumo dos indicadores do período, texto da
análise (150 a 2.500 caracteres) e um campo por desvio negativo. O endereço com
`analise`, tipo e período abre direto no passo 2.

Um registro por módulo, tipo e período; Trocar período, Copiar do período
anterior e Excluir (Gestor). Os **desvios negativos são detectados no
servidor**, com os mesmos dados do relatório: no 02, avanço acumulado e do
período abaixo do previsto, término pela tendência depois da linha de base,
áreas com desvio negativo e produtividade fora da meta; no 03, CPI e SPI de
custo abaixo de 1, VAC negativo e pacotes com sobrecusto projetado; no 04,
aderência e OTD abaixo de 100%, pedidos críticos e marcos realizados com
atraso no período. Em 02, 03 e 04, cada desvio exige comentário de ao menos 20
caracteres, gravado pela chave do desvio; um desvio novo, surgido porque os
dados mudaram, aparece como pendente.

## Critérios de aceite

- [ ] A detecção de cada desvio dos três módulos tem teste.
- [ ] Texto fora de 150 a 2.500 caracteres e comentário com menos de 20 são recusados.
- [ ] Mudar um dado que cria um desvio novo faz ele aparecer pendente (teste).
- [ ] Copiar do anterior traz o texto para revisão, e Excluir exige Gestor.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (detecção) e de fachada (gravação, pendência e cópia).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `js/components/analise.js` e `GI.api.analises.*`; README, "Análise do período por módulo: regras".

## Registro de execução

Fatia entregue em 10/10/2026: o modal **Análise do período** abre das cinco telas (02 KPIs de
planejamento e Relato do período, 03 KPIs de custo e Curva S financeira, 04 Painel de
suprimentos) e grava um registro por projeto, módulo, tipo e período. A migração `m075` cria
`analise_periodo` (texto, autores, `versao`; `projeto_id` nulo identifica o Portfólio da 082; UK
por projeto/módulo/tipo/período com `NULLS NOT DISTINCT`) e `analise_periodo_desvio` (chave,
indicador e comentário, sem versão própria). O módulo dono é o `relatorio` (D9): a fachada
(`service.py`) traz a leitura do passo 1 (`analysis_options`: períodos do início do projeto ao
corrente, o mais recente primeiro, com a situação e o padrão no período anterior), a leitura do
passo 2 (`analysis_view`: resumo, desvios detectados com o comentário gravado, registro,
pendentes e o anterior) e a escrita (`save_analysis` — Membro, 422 por campo, 409 de versão
vencida, duplicado recusado mandando editar; `delete_analysis` — Gestor), com a trilha de
auditoria do agregado como no relato; `insert_analysis` é a porta da carga e `analysis_record`,
a leitura da 083. A detecção (`calculations.py`) não duplica fórmula de dono: chama as fachadas
públicas com a data de referência no corte do período — planejamento (`planning_kpis_overview`
no corte e `curva_fisica_overview` no dia anterior ao início para o avanço do período, SPI
anterior e `performance_overview` para a produtividade: `avanco`, `avanco_periodo`, `termino`,
`areas`, `produtividade`), financeiro (`cost_kpis_overview` no mês de competência — no Mensal o
próprio mês, no Semanal o último fechado; sem fechamento não há desvios — e `mapa_controle`
nível 1: `cpi`, `spi_custo`, `vac`, `pacotes`) e suprimentos (`list_panel` e `list_orders`:
`aderencia`, `otd`, `criticos` e `marcos_atrasados`, só marcos de pedido realizados no período).
Cada desvio tem o texto numérico no formato do protótipo (`deviation_description`, reutilizável
pela 083) e o resumo do passo 2 (`analysis_summary`); texto de 150 a 2.500 caracteres (trim) e
comentário de 20 a 600, gravado pela chave do desvio — comentário de desvio que sumiu da
detecção é descartado e desvio novo, surgido porque os dados mudaram, aparece pendente. As
rotas (`routes.py`, prefixo `/api/relatorio/analise`: `periodo`, `formulario`, `copiar`,
`gravar` e `excluir`, nomes `analysis_*` únicos; WRITE exceto `excluir` com MANAGE; Portfólio
recusado com 422 pelo `scope.require_project`) devolvem fragmentos no alvo `analise-modal` com a
classe `pagina--relatorio-analise`; `gravar` e `excluir` respondem os marcadores
`data-analise-salvo`/`data-analise-excluida` que fecham o modal, com o toast no cabeçalho. O
comportamento é compartilhado — não é o trio de uma tela: o par `app/paginas/relatorio/analise.js`
e `analise.css` é carregado pelo shell, o botão `data-analise="<modulo>"` vive nas views das
cinco telas, cada `iniciar()` chama `TN.analise.abrirDoEndereco("<modulo>")` e o endereço
`?analise=1&tipo=&periodo=` abre direto no passo 2 (para os links da 083). A carga de
demonstração entra pela parte `relatorio-analises` (`seed.py`, espelhando `seed_relato.py`): 22
análises dos módulos 02, 03 e 04, com os períodos deslocados em períodos inteiros e os carimbos
em dias; as seis do Portfólio ficam para a 082 (o filtro lê `service.ANALYSIS_MODULES`, que a 082
estende). **Divergência registrada**: o mock das análises cita chaves que o motor do próprio
protótipo não produz com os dados do mock-base (projeto 2 sem `avanco_periodo`, `cpi`, `vac`,
`otd`, `marcos_atrasados` e `aderencia` de agosto; projeto 3 sem `areas`) — a detecção segue o
motor e o oráculo afirma as chaves sustentadas (`UNSUPPORTED_KEYS`), em
`docs/DIVERGENCIAS-DO-PROTOTIPO.md`. Os testes novos (`test_analise_calculos.py`,
`test_analise_servico.py`, `test_analise_rotas.py` e `test_analise_oraculo.py`, com o
`conftest.py` da pasta) cobrem a detecção por chave e os limites, a gravação/edição/versão/
exclusão por perfil, a pendência do desvio novo, a cópia do anterior, o 403/422 nas rotas e o
oráculo dos três módulos. `ruff check`, `ruff format --check` e `ty check` limpos; a rodada do
fechamento (relatório, planejamento, financeiro e suprimentos — 1.636 testes, duas vezes)
passa; a migração sobe, desce e sobe num banco vazio (`gestnow_m075_check`); a porta de
qualidade, 5/5.

- DECISAO: módulo dono | `relatorio` guarda tabelas, fachada, rotas e o par compartilhado do modal; o `modulo` da linha nomeia o módulo analisado e a 083 lê as análises daqui | D9, ISSUE-081
- DECISAO: detecção no servidor pelas fachadas donas | nenhuma fórmula duplicada: planejamento no corte (com a posição do dia anterior para o avanço do período), financeiro no mês de competência (semanal = último mês fechado; sem fechamento, nenhum desvio) e suprimentos no corte (críticos e marcos de pedido realizados no período) | D9, ISSUE-081
- DECISAO: comentário pela chave do desvio | `analise_periodo_desvio` guarda chave, indicador e comentário; comentário de desvio que sumiu é descartado na gravação e desvio novo aparece pendente; obrigatório (20 a 600) nos três módulos, e a 082 estende o mapa | D6, ISSUE-081
- DECISAO: modal compartilhado | o par `analise.js`/`analise.css` carregado pelo shell (não é trio), botão `data-analise` nas views das cinco telas, `?analise=1&tipo=&periodo=` abrindo o passo 2, com Trocar período, Copiar do anterior e Excluir (Gestor) dentro do modal | D14, ISSUE-081
- DECISAO: Portfólio recusado | `scope.require_project` (422) nesta fatia; as tabelas e a fachada já aceitam `projeto_id` nulo e a 082 estende a detecção aos 05/06/07 e ao Portfólio | D9, ISSUE-081, ISSUE-082
- DECISAO: chaves do mock sem sustentação | o mock cita desvios que os dados do mock-base contradizem (projetos 2 e 3); a detecção segue o motor e o oráculo afirma as chaves sustentadas; divergência em `DIVERGENCIAS-DO-PROTOTIPO.md` | ISSUE-081
