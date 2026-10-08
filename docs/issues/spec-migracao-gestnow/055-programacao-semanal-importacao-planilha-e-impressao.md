---
id: ISSUE-055
title: "Importação da semana, planilha e relatório de impressão"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-052
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-082
  - HU-083
spec_decisions:
  - D10
  - D12
---

# Importação da semana, planilha e relatório de impressão

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D12.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 82, 83. Bloqueada por: ISSUE-052.

## O que construir

Importar a semana pela planilha modelo do app, com conferência linha a linha
antes de gravar (fluxo genérico da plataforma com as regras do importador do
app). Baixar a semana em Excel com o mesmo conteúdo da planilha do app, e gerar
o relatório para imprimir (a folha do app) pela folha de impressão do Design
System.

## Critérios de aceite

- [x] A importação confere linha a linha e só grava na confirmação, com as regras do app.
- [x] O Excel da semana tem as mesmas colunas e abas da planilha do app.
- [x] O relatório de impressão sai sem navegação e com o conteúdo da folha do app.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes portados da importação e da planilha; teste do relatório imprimível.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: importação, planilha e relatório (folha) do app.

## Registro de execução

Data: 2026-10-08.
Feito: `importers.py` (novo: `programacao_importer`, chave `programacao-semanal`, colunas do app com `Prev/Real`, obrigatórias e `_Conferencia` linha a linha — cadastros do projeto, semana ISO, soma dos dias com tolerância de 0,51, ID sem repetir no arquivo e no banco —, `validate`/`save` pela fachada e `register_importers`), `permissions.py` (`can_import` = Planejador no projeto ou Admin, como o `importar` do app), `service.py` (`import_done_days` — a linha `Real.` grava o turno dia pelo `recording`, com a trilha de cada dia —, `week_curve` com o horizonte de treze semanas e `CURVE_BACK_WEEKS`), `calculations.py` (`CurveActivity`, `CurvePoint` e `curve_points`, porte de `indicadores.curva_s`), `export.py` (`week_document` com as sete abas do app — Resumo, Programação, Por contratada, Por frente, Por encarregado, Dia a dia e Curva S —, `week_report_document` com a folha do app, os KPIs, a matriz de duas linhas por atividade, as quebras e o dia a dia compartilhados), `screen.py` (`import_context`, as URLs novas e os `cadastros` do painel), `routes.py` (`week_import` GET, `week_import_model` GET em `file_route`, `week_import_check` POST, `week_import_confirm` POST com o digest e o `ciente`, `week_excel` e `week_printable`; os nomes levam `week_` porque o blueprint genérico da plataforma já é dono de `import_check`/`import_confirm` no host), fragmentos (`importacao.html`, `importacao_conferencia.html` sobre o parcial genérico e `importacao_resultado.html`); a tela `app/_views/programacao_semanal/importacao.html` e o trio CSS/JS (o painel com o seletor da semana, os botões da semana e os passos, e os avisos de Portfólio e de permissão); testes `test_programacao_importacao.py`, `test_programacao_importacao_rotas.py` e `test_programacao_exportacao.py`; `test_programacao_rotas.py` (o `Access` das rotas novas); `pyproject.toml` (per-file-ignore de `PLR0913` em `export.py` e nos três testes novos, com comentário); LEIA-ME do módulo.
Verificação: pytest de `programacao_semanal`, `plataforma` e `configuracoes` — 1220 passaram; `ruff check`, `ruff format --check` e `ty check` verdes; `node scripts/verificar.mjs` com as cinco etapas verdes, sem regra desligada; sem migração (a importação grava pelas tabelas da `m051` e não há tabela nova — seção 8 do MODELO-DE-DADOS inalterada).
DECISÃO: importador e fluxo | importador do módulo na chave `programacao-semanal` sobre o `core.importing` (modelo `Dados`/`Instruções`, conferência que não grava e confirmação tudo ou nada com o digest); a linha `Prev.` cria a atividade em elaboração (`store_activity`, o mesmo caminho da tela) e a `Real.` completa o turno dia (`import_done_days`); sem `Prev.`, a `Real.` é ignorada, como no app | D12, D10, ISSUE-055
DECISÃO: papel da importação | a permissão genérica do importador é a leitura do módulo (`Permission.VIEW`), porque o app dava `importar` a Planejador e Admin e o GestNow decide papéis por projeto (D7); `permissions.can_import` decide nas rotas e na validação; o fornecedor é recusado pelo vínculo no `core.rbac` | D7, D10, ISSUE-055
DECISÃO: linha `Real.` e turno | o modelo do app só carregava um conjunto de dias realizados; no GestNow ele vira o turno dia (o turno noite fica zero), como o app importava | D10, ISSUE-055
DECISÃO: modelo do GestNow | o modelo é o genérico da plataforma (`Dados` + `Instruções` com obrigatoriedade, formato e exemplo), e não o arquivo de exemplo com "Como preencher"/"Listas válidas" do app; os cadastros aceitos aparecem no painel da aba e as obrigatórias condicionais da linha `Prev.` são checadas por `validate` (as três sempre obrigatórias — Semana, ID Exclusiva e Prev/Real — viajam como `required` e as demais como mensagem do app) | D12, D10, ISSUE-055
DECISÃO: Excel e relatório | dois `Document` do mesmo `export.py`: `week_document` (as sete abas do app, inclusive Resumo e Curva S) e `week_report_document` (a folha do app: quatro indicadores, matriz, contratada, frente e dia a dia), porque a folha do app não tem a curva nem as abas de capa; a matriz de duas linhas por atividade é a mesma nos dois | D12, D10, ISSUE-055
DECISÃO: curva S | porte fiel de `indicadores.curva_s` para `calculations.curve_points`, com o horizonte de treze semanas de `service.week_curve` (a semana e as doze anteriores) e o escopo da atividade somado no horizonte; nomes em inglês (D1) | D10, D11, ISSUE-055
DECISÃO: Portfólio e fornecedor | a importação exige projeto (422 no Portfólio; a tela pede um projeto) e só o Planejador/Admin importa; o Excel e o imprimível ficam disponíveis e, no Portfólio, a matriz leva a coluna Projeto (HU-016); o fornecedor exporta só a própria empresa (o corte é da fachada) e não importa | D8, D7, HU-016, ISSUE-055
DECISÃO: nomes das rotas e funções | `week_import`, `week_import_model`, `week_import_check`, `week_import_confirm`, `week_excel` e `week_printable`; o prefixo `week_` evita a colisão de nomes de função do host com o blueprint genérico (`import_check`/`import_confirm`) | D14, ISSUE-055
DECISÃO: sem migração | a importação grava apenas por `programacao_atividade`/`programacao_dia` e a trilha única; nenhuma tabela nova, e a seção 8 do `docs/MODELO-DE-DADOS.md` não mudou | D5, ISSUE-055
DECISÃO: glossário | nenhum termo novo de domínio nasceu nesta fatia (importar, conferir e imprimir já são o vocabulário da plataforma); `CONTEXT.md` e `glossario.json` não mudaram | D10, ISSUE-055
