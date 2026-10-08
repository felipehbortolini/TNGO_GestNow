---
id: ISSUE-048
title: "Produtividade: KPIs de performance e plano de ação na Central"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-046
  - ISSUE-047
  - ISSUE-019
blocks:
  - ISSUE-081
labels:
  - ready-for-agent
source_requirements:
  - HU-067
spec_decisions:
  - D6
  - D9
---

# Produtividade: KPIs de performance e plano de ação na Central

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D9.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 67. Bloqueada por: ISSUE-046, ISSUE-047, ISSUE-019.

## O que construir

A aba **KPIs de performance** mostra, geral e por empresa, na janela de N
semanas do parâmetro até a semana de corte: avanço, SPI de quantidades,
aderência, fator de produtividade (FP), tendência de atraso, CP e utilização,
% trabalhando, Hhora e Mhora (com % das HH disponíveis), e a tendência semanal
por empresa (FP, aderência, % trabalhando, CP), com as cores pelas faixas dos
parâmetros.

Fórmulas: horas ganhas (HG) = realizado x índice orçado; avanço = HG ÷ HH
orçadas; SPI de quantidades = HG ÷ horas previstas na linha de base; aderência
semanal = realizado ÷ previsto, limitada a 100% por item e ponderada pelas HH
orçadas; FP = HH apropriadas ÷ HG; tendência pelo prazo agregado (SPI(t) =
semanas da linha de base equivalentes ao realizado ÷ semanas decorridas);
apontamento pendente = item ativo sem apontamento na semana de corte.

Empresa com indicador fora da faixa pode gerar **plano de ação na Central**
(origem Produtividade, referência semana e empresa, como `PRD-2026-S39-01`):
uma ação aberta por empresa e semana, com o link da Central voltando para esta
aba com a empresa e a semana.

## Critérios de aceite

- [x] HG, avanço, SPI de quantidades, aderência, FP e SPI(t) têm teste com fronteira.
- [x] Gerar o plano duas vezes para a mesma empresa e semana não duplica a ação.
- [x] O link da ação na Central volta para a aba KPIs com a empresa e a semana.
- [x] O oráculo afirma avanço de 59,2% x 67,5% (SPI 0,88), FP de 1,12 nas últimas 4 semanas, CP de 6,81 h/dia e 55,3% trabalhando.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo, de fachada (plano de ação sem duplicar) e o oráculo da produtividade.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.produtividade.kpis` e `gerarAcao`; números do cenário no README, "Produtividade: regras".

## Registro de execução

- Data: 2026-10-08.
- Feito: cálculos em `calculations.py` (seção "KPIs de performance da Produtividade (ISSUE-048)": `schedule_trend` com o SPI(t) agregado e o desvio em semanas, `weekly_trend` com FP, aderência, % trabalhando e CP de cada semana, `ratio_chart` com o par cru de cada semana para o motor de períodos, `stoppage_share`, `PerformanceBands`/`performance_alerts` e `performance_action_reference`/`performance_action_parts`), fachada em `service.py` (`performance_overview` com o bloco geral e um por empresa — por projeto e empresa no Portfólio —, `PerformanceBlock`/`PerformanceOverview`, `performance_action_form`, `create_performance_action` e o registro do link de volta por `origin_links`), validação em `validation.py` (`parse_action_plan`: empresa, ação de 10 a 150, descrição de até 600, responsável e data prevista não anterior à referência), rotas em `routes.py` (aba, Excel/PDF, modal do plano e gravação multi-alvo com 422 e `X-TN-Toast`), exportação em `export.py` (`performance_document`, `performance_kpis`, tabelas e os dois gráficos), fragmentos `produtividade_kpis.html`, `produtividade_kpis_resposta.html`, `produtividade_plano_form.html` e `_prod_plano_form.html`, a terceira aba no trio da tela (`app/_views/planejamento/produtividade.html`, `produtividade.css` e `.js`), os testes `test_kpis_calculos.py`, `test_kpis_performance_servico.py` e `test_kpis_performance_rotas.py` (nomes únicos: `test_kpis_servico.py` e `test_kpis_rotas.py` são da ISSUE-040; `form_plano` no apoio), o oráculo em `test_carga_demonstracao.py` e a seção desta fatia no `LEIA-ME.md`.
- Oráculos: no projeto 1 (TN-2026-014), no corte S39 e sem deslocamento, a janela de 4 semanas fecha o avanço de 59,2% x 67,5% (SPI 0,88), o FP de 1,12, a CP de 6,81 h/dia (utilização 77,4%) e 55,26% trabalhando; a agregação da tendência dá SPI(t) 0,94 com 4 semanas de atraso; a Alfa Montagens fica em alerta (SPI 0,83, FP 1,15, aderência 78,8% em atenção e 50,9% trabalhando) e a Zeta Civil com 80,7% e FP 1,06; a janela soma 638,7 Hhora e 39,5 Mhora; e a ação do mock (`PRD-2026-S38-01`) aparece na empresa na semana S38.
- Decisão: a tendência semanal por empresa sai em **tabela** com os quatro indicadores e em **dois gráficos** da biblioteca (aderência e % trabalhando) com a meta em tracejado. O motor de períodos (D11) resume taxas por razão em percentual e não representa o FP (índice) nem a CP (média); forçar os quatro gráficos exigiria deturpar o par (num, den) ou mudar o contrato da biblioteca numa fatia de módulo. A tabela cobre o que o protótipo mostrava e entra no Excel/PDF; a decisão fica registrada.
- Decisão: o formulário do plano ganhou o select de **empresa** além dos campos do protótipo. No Portfólio o mecanismo de inclusão (`data-tn-incluir="plano"`) reabre a tela no projeto sem saber qual linha foi clicada; com o select, o formulário funciona em qualquer caminho e a empresa continua podendo ser trocada (no protótipo a empresa vinha fixa do botão da linha).
- Decisão: a leitura da ação aberta usa `central_acoes.list_actions` com o escopo do projeto, e não `count_actions_of_origin` (que agrupa só por origem e referência): como a referência é semana e empresa sem o projeto (formato da spec), duas empresas de mesmo id em projetos diferentes colidiriam; o filtro de escopo da Central desempata. A checagem vale para mostrar o link e para recusar a segunda gravação.
- Decisão (correção da carga da ISSUE-019): o seed da Central passou a reescrever a referência das ações de Produtividade com o id que o banco deu à empresa (`PRD-2026-S38-01` do mock vira `PRD-2026-S38-<id real>`), como faz com todos os ids do protótipo; sem isso a aba não encontraria a ação do mock e o link de volta abriria a empresa errada. Nenhum outro dado do mock mudou.
- Decisão: não há migração. A ação da Central já guarda a referência em `acao.origem_ref` e a origem Produtividade já existe em `origins.ORIGINS` (ISSUE-019); nenhuma coluna ou tabela nova entrou (o diagrama de `docs/MODELO-DE-DADOS.md` segue como está). Não há carga própria: os KPIs saem dos dados das 046/047 já carregados.
- Decisão: `CONTEXT.md` e `glossario.json` não mudam. Os termos desta fatia (SPI(t), tendência de atraso, plano de ação na Central) são derivações do que as ISSUES 046/047 já documentaram (HG, aderência, FP, CP, plano de ação) e ficam definidos na tabela de fórmulas do `LEIA-ME.md`; nenhum conceito novo de domínio nasceu aqui.
- Verificação: suíte escopada `pytest api/tests/planejamento api/tests/plataforma api/tests/central_acoes` verde; sem migração (nada a subir em banco vazio); `ruff check`, `ruff format --check` e `ty check` verdes; porta de qualidade completa (`node scripts/verificar.mjs`) verde nas cinco etapas. Sem pendência, sem divergência de spec; as divergências com o protótipo estão nas decisões acima (gráficos, select de empresa).
