# Exportações tela a tela

Inventário obrigatório da **D12**, conferido tela a tela na aceitação (ISSUE-091): cada botão
Excel e PDF das telas, a rota que ele chama, os parâmetros de escopo que a rota exige e o teste
que a cobre. Este documento e o teste são o **mesmo inventário**: os casos de
`api/tests/plataforma/test_exportacoes_por_tela.py` saem das mesmas declarações, e um caso do
teste guarda o vínculo — toda rota declarada no teste tem de estar citada aqui, e toda rota de
exportação registrada tem de estar no inventário.

## Como o teste por tela confere cada rota

* **Excel** (`data-tn-excel`): responde 200 e abre como `.xlsx` de verdade (openpyxl); o título
  do documento aparece em todas as abas; cada tabela da tela tem o seu cabeçalho na ordem
  declarada (basta uma coluna sumir para o caso falhar); cada indicador aparece no `Resumo` com
  a **referência de gestão** (`Meta: 90%`, `Esperado: 0`, `Orçado: R$ ...`); o papel do
  documento (A4 ou A3) está no `pageSetup` da planilha.
* **PDF** (`data-tn-pdf`): responde 200 como fragmento e é a folha de impressão
  (`folha--a4`/`folha--a3`) do Design System, com o cabeçalho do documento (logo, título,
  escopo e data), os mesmos indicadores com referência e as mesmas tabelas — e **sem navegação
  nenhuma** (sem `#main-nav`, sem `<nav>`, sem sidebar, sem link). O PDF é a impressão do
  navegador: não há biblioteca de PDF no servidor nem no cliente.
* **Cobertura**: a varredura de `app/_views/`, `api/src/templates/` e `app/exemplos/exportacao.html`
  conta os botões de exportação por arquivo (atributo `data-tn-excel`, `data-tn-pdf`,
  `data-exportar` e `href` para `/excel` ou `/imprimivel`); a contagem tem de ser exatamente a
  declarada, cada endereço literal tem de apontar para uma rota do inventário, toda rota
  registrada de exportação tem de estar no inventário e todo caso do inventário tem de estar
  parametrizado — **botão fora do inventário e rota sem teste reprovam**.

O cenário do teste é a carga de demonstração na transação do teste, no escopo de um projeto
(`?projeto=`), com o relógio parado em 12/10/2026. As telas de detalhe usam os registros
conhecidos da carga (contrato `CT-2026-011`, risco `RSK-TN-2026-0001`, ata `TN-2026-0028` e SM
`SM-TN-2026-0001`).


## Exemplo de exportação (demonstração)

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `app/exemplos/exportacao.html` | Excel | `exportacao/exemplo/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[exportacao/exemplo/excel]`; existente: `tests/plataforma/test_exportacao_rotas.py` | exemplo do mecanismo; só existe no modo demonstração (403 em produção) |
| `app/exemplos/exportacao.html` | PDF | `exportacao/exemplo/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[exportacao/exemplo/excel]`; existente: `tests/plataforma/test_exportacao_rotas.py` | exemplo do mecanismo; só existe no modo demonstração (403 em produção) |

## Configurações

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `configuracoes/parametros` | Excel | `configuracoes/parametros/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[configuracoes/parametros/excel]`; existente: `tests/configuracoes/test_parametros_rotas.py` |  |
| `configuracoes/parametros` | PDF | `configuracoes/parametros/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[configuracoes/parametros/excel]`; existente: `tests/configuracoes/test_parametros_rotas.py` |  |
| `configuracoes/colaboradores` | Excel | `configuracoes/colaboradores/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[configuracoes/colaboradores/excel]`; existente: `tests/configuracoes/test_colaboradores_rotas.py` |  |
| `configuracoes/colaboradores` | PDF | `configuracoes/colaboradores/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[configuracoes/colaboradores/excel]`; existente: `tests/configuracoes/test_colaboradores_rotas.py` |  |
| `configuracoes/cadastros` | Excel | `configuracoes/cadastros/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[configuracoes/cadastros/excel]`; existente: `tests/configuracoes/test_cadastros_rotas.py` |  |
| `configuracoes/cadastros` | PDF | `configuracoes/cadastros/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[configuracoes/cadastros/excel]`; existente: `tests/configuracoes/test_cadastros_rotas.py` |  |

## Início

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `inicio/home` | Excel | `inicio/resumo/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[inicio/resumo/excel]`; existente: `tests/inicio/test_inicio_rotas.py` |  |
| `inicio/home` | PDF | `inicio/resumo/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[inicio/resumo/excel]`; existente: `tests/inicio/test_inicio_rotas.py` |  |

## Relatório gerencial

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `relatorio/gerencial` | Excel | `relatorio/gerencial/excel` — escopo `?projeto=` e `tipo`, `periodo` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[relatorio/gerencial/excel]`; existente: `tests/relatorio/test_relatorio_export.py` | o PDF/Imprimir é a impressão da tela (`data-relatorio-imprimir`), sem rota própria; exige `tipo`, `periodo` |
| `relatorio/gerencial` | Imprimir / PDF | — | `relatorio/test_relatorio_export.py::test_o_contrato_da_impressao_esta_na_tela_na_barra_e_no_estilo` | a impressão da tela (`window.print()`), com o CSS `@media print` |

## 01 · Central de Ações

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `central_acoes/acoes` | Excel | `central-acoes/acoes/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/acoes/excel]`; existente: `tests/central_acoes/test_acoes_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `central_acoes/acoes` | PDF | `central-acoes/acoes/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/acoes/excel]`; existente: `tests/central_acoes/test_acoes_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `central_acoes/atas` | Excel | `central-acoes/atas/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/atas/excel]`; existente: `tests/central_acoes/test_atas_rotas.py` | respeita os filtros da tela |
| `central_acoes/atas` | PDF | `central-acoes/atas/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/atas/excel]`; existente: `tests/central_acoes/test_atas_rotas.py` | respeita os filtros da tela |
| `central_acoes/ata` | Excel | `central-acoes/ata/excel` — escopo `?projeto=` e `id` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/ata/excel]`; existente: `tests/central_acoes/test_atas_rotas.py` | tela de detalhe: exige `id` |
| `central_acoes/ata` | PDF | `central-acoes/ata/imprimivel` — escopo `?projeto=` e `id` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/ata/excel]`; existente: `tests/central_acoes/test_atas_rotas.py` | tela de detalhe: exige `id` |
| `central_acoes/dashboard` | Excel | `central-acoes/painel/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/painel/excel]`; existente: `tests/central_acoes/test_painel.py` | a leitura do painel |
| `central_acoes/dashboard` | PDF | `central-acoes/painel/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[central-acoes/painel/excel]`; existente: `tests/central_acoes/test_painel.py` | a leitura do painel |

## 02 · Planejamento

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `planejamento/relato` | Excel | `planejamento/relatos/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/relatos/excel]`; existente: `tests/planejamento/test_relato_rotas.py` |  |
| `planejamento/relato` | PDF | `planejamento/relatos/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/relatos/excel]`; existente: `tests/planejamento/test_relato_rotas.py` |  |
| `planejamento/6wla` | Excel | `planejamento/6wla/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/6wla/excel]`; existente: `tests/planejamento/test_6wla_rotas.py` |  |
| `planejamento/6wla` | PDF | `planejamento/6wla/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/6wla/excel]`; existente: `tests/planejamento/test_6wla_rotas.py` |  |
| `planejamento/eap` | Excel | `planejamento/eap/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/eap/excel]`; existente: `tests/planejamento/test_eap_rotas.py` |  |
| `planejamento/eap` | PDF | `planejamento/eap/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/eap/excel]`; existente: `tests/planejamento/test_eap_rotas.py` |  |
| `planejamento/curva_s` | Excel | `planejamento/curva-fisica/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/curva-fisica/excel]`; existente: `tests/planejamento/test_curva_fisica_rotas.py` |  |
| `planejamento/curva_s` | PDF | `planejamento/curva-fisica/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/curva-fisica/excel]`; existente: `tests/planejamento/test_curva_fisica_rotas.py` |  |
| `planejamento/kpis` | Excel | `planejamento/kpis/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/kpis/excel]`; existente: `tests/planejamento/test_kpis_rotas.py` |  |
| `planejamento/kpis` | PDF | `planejamento/kpis/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/kpis/excel]`; existente: `tests/planejamento/test_kpis_rotas.py` |  |
| `planejamento/produtividade` | Excel | `planejamento/produtividade/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/produtividade/excel]`; existente: `tests/planejamento/test_produtividade_rotas.py` |  |
| `planejamento/produtividade` | PDF | `planejamento/produtividade/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/produtividade/excel]`; existente: `tests/planejamento/test_produtividade_rotas.py` |  |
| `planejamento/produtividade` | Excel | `planejamento/produtividade/horas-efetivas/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/produtividade/horas-efetivas/excel]`; existente: `tests/planejamento/test_campo_rotas.py` |  |
| `planejamento/produtividade` | PDF | `planejamento/produtividade/horas-efetivas/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/produtividade/horas-efetivas/excel]`; existente: `tests/planejamento/test_campo_rotas.py` |  |
| `planejamento/produtividade` | Excel | `planejamento/produtividade/kpis/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/produtividade/kpis/excel]`; existente: `tests/planejamento/test_kpis_performance_rotas.py` |  |
| `planejamento/produtividade` | PDF | `planejamento/produtividade/kpis/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/produtividade/kpis/excel]`; existente: `tests/planejamento/test_kpis_performance_rotas.py` |  |
| `planejamento/punch_list` | Excel | `planejamento/punch/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/punch/excel]`; existente: `tests/planejamento/test_punch_rotas.py` | respeita os filtros da tela (situação, categoria, sistema, disciplina, empresa) |
| `planejamento/punch_list` | PDF | `planejamento/punch/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/punch/excel]`; existente: `tests/planejamento/test_punch_rotas.py` | respeita os filtros da tela (situação, categoria, sistema, disciplina, empresa) |
| `planejamento/punch_list` | Excel | `planejamento/punch/painel/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/punch/painel/excel]`; existente: `tests/planejamento/test_punch_rotas.py` | respeita os filtros da tela (situação, categoria, sistema, disciplina, empresa) |
| `planejamento/punch_list` | PDF | `planejamento/punch/painel/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento/punch/painel/excel]`; existente: `tests/planejamento/test_punch_rotas.py` | respeita os filtros da tela (situação, categoria, sistema, disciplina, empresa) |

## 02 · Planejamento · Programação Semanal

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `programacao_semanal/governanca` | Excel | `programacao-semanal/governanca/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[programacao-semanal/governanca/excel]`; existente: `tests/programacao_semanal/test_programacao_governanca_rotas.py`, `tests/programacao_semanal/test_programacao_rotas.py` | a lista de controle e a fila de pedidos |
| `programacao_semanal/governanca` | PDF | `programacao-semanal/governanca/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[programacao-semanal/governanca/excel]`; existente: `tests/programacao_semanal/test_programacao_governanca_rotas.py`, `tests/programacao_semanal/test_programacao_rotas.py` | a lista de controle e a fila de pedidos |
| `programacao_semanal/programacao` | Excel | `programacao-semanal/semana/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[programacao-semanal/semana/excel]`; existente: `tests/programacao_semanal/test_programacao_importacao_rotas.py`, `tests/programacao_semanal/test_programacao_rotas.py` | semana pelo seletor (`semana`); a planilha e o relatório de impressão são documentos próprios |
| `programacao_semanal/programacao` | PDF | `programacao-semanal/semana/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[programacao-semanal/semana/excel]`; existente: `tests/programacao_semanal/test_programacao_importacao_rotas.py`, `tests/programacao_semanal/test_programacao_rotas.py` | semana pelo seletor (`semana`); a planilha e o relatório de impressão são documentos próprios; o relatório de impressão da semana é mais enxuto que a planilha |
| `programacao_semanal/dashboard` | Excel | `programacao-semanal/dashboard/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[programacao-semanal/dashboard/excel]`; existente: `tests/programacao_semanal/test_programacao_dashboard_rotas.py`, `tests/programacao_semanal/test_programacao_rotas.py` | semana pelo seletor (`semana`) |
| `programacao_semanal/dashboard` | PDF | `programacao-semanal/dashboard/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[programacao-semanal/dashboard/excel]`; existente: `tests/programacao_semanal/test_programacao_dashboard_rotas.py`, `tests/programacao_semanal/test_programacao_rotas.py` | semana pelo seletor (`semana`) |
| `programacao_semanal/importacao` | Excel | `programacao-semanal/importacao/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[programacao-semanal/importacao/modelo]`; existente: `tests/programacao_semanal/test_programacao_importacao_rotas.py`, `tests/programacao_semanal/test_programacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |

## 03 · Gestão Financeira

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `financeiro/eac` | Excel | `financeiro/eac/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/eac/excel]`; existente: `tests/financeiro/test_eac_revisoes_rotas.py`, `tests/financeiro/test_eac_rotas.py` | a EAC vigente do escopo |
| `financeiro/eac` | PDF | `financeiro/eac/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/eac/excel]`; existente: `tests/financeiro/test_eac_revisoes_rotas.py`, `tests/financeiro/test_eac_rotas.py` | a EAC vigente do escopo |
| `financeiro/mapa_controle` | Excel | `financeiro/mapa-de-controle/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/mapa-de-controle/excel]`; existente: `tests/financeiro/test_eac_mapa_rotas.py` | o mapa e a projeção no término |
| `financeiro/mapa_controle` | PDF | `financeiro/mapa-de-controle/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/mapa-de-controle/excel]`; existente: `tests/financeiro/test_eac_mapa_rotas.py` | o mapa e a projeção no término |
| `financeiro/contrato` | Excel | `financeiro/contrato/excel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/excel]`; existente: `tests/financeiro/test_contrato_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | PDF | `financeiro/contrato/imprimivel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/excel]`; existente: `tests/financeiro/test_contrato_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | Excel | `financeiro/contrato/marcos/excel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/marcos/excel]`; existente: `tests/financeiro/test_contrato_fluxos_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | PDF | `financeiro/contrato/marcos/imprimivel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/marcos/excel]`; existente: `tests/financeiro/test_contrato_fluxos_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | Excel | `financeiro/contrato/claims/excel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/claims/excel]`; existente: `tests/financeiro/test_contrato_fluxos_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | PDF | `financeiro/contrato/claims/imprimivel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/claims/excel]`; existente: `tests/financeiro/test_contrato_fluxos_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | Excel | `financeiro/contrato/extensoes/excel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/extensoes/excel]`; existente: `tests/financeiro/test_contrato_fluxos_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | PDF | `financeiro/contrato/extensoes/imprimivel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/extensoes/excel]`; existente: `tests/financeiro/test_contrato_fluxos_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | Excel | `financeiro/contrato/avaliacoes/excel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/avaliacoes/excel]`; existente: `tests/financeiro/test_contrato_avaliacao_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contrato` | PDF | `financeiro/contrato/avaliacoes/imprimivel` — escopo `?projeto=` e `numero` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contrato/avaliacoes/excel]`; existente: `tests/financeiro/test_contrato_avaliacao_rotas.py` | aba da ficha do contrato: exige `numero` |
| `financeiro/contratos` | Excel | `financeiro/contratos/consolidado/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contratos/consolidado/excel]`; existente: `tests/financeiro/test_contratos_consolidado_rotas.py` | filtro `contrato` opcional |
| `financeiro/contratos` | PDF | `financeiro/contratos/consolidado/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contratos/consolidado/excel]`; existente: `tests/financeiro/test_contratos_consolidado_rotas.py` | filtro `contrato` opcional |
| `financeiro/contingencia` | Excel | `financeiro/contingencia/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contingencia/excel]`; existente: `tests/financeiro/test_contingencia_rotas.py` | as reservas e a cobertura da exposição |
| `financeiro/contingencia` | PDF | `financeiro/contingencia/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/contingencia/excel]`; existente: `tests/financeiro/test_contingencia_rotas.py` | as reservas e a cobertura da exposição |
| `financeiro/curva_s` | Excel | `financeiro/curva-s/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/curva-s/excel]`; existente: `tests/financeiro/test_curva_financeira_rotas.py` | a curva financeira mensal |
| `financeiro/curva_s` | PDF | `financeiro/curva-s/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/curva-s/excel]`; existente: `tests/financeiro/test_curva_financeira_rotas.py` | a curva financeira mensal |
| `financeiro/kpis` | Excel | `financeiro/kpis/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/kpis/excel]`; existente: `tests/financeiro/test_custos_kpis_rotas.py` | avaliação por valor agregado na data de corte |
| `financeiro/kpis` | PDF | `financeiro/kpis/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/kpis/excel]`; existente: `tests/financeiro/test_custos_kpis_rotas.py` | avaliação por valor agregado na data de corte |
| `financeiro/desembolso` | Excel | `financeiro/desembolso/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/desembolso/excel]`; existente: `tests/financeiro/test_desembolso_rotas.py` | o cronograma de desembolso por mês |
| `financeiro/desembolso` | PDF | `financeiro/desembolso/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro/desembolso/excel]`; existente: `tests/financeiro/test_desembolso_rotas.py` | o cronograma de desembolso por mês |

## 04 · Suprimentos

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `suprimentos/fornecedores` | Excel | `suprimentos/fornecedores/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/fornecedores/excel]` | respeita os filtros da tela |
| `suprimentos/fornecedores` | PDF | `suprimentos/fornecedores/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/fornecedores/excel]` | respeita os filtros da tela |
| `suprimentos/plano_compras` | Excel | `suprimentos/plano-de-compras/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/plano-de-compras/excel]` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `suprimentos/plano_compras` | PDF | `suprimentos/plano-de-compras/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/plano-de-compras/excel]` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `suprimentos/processos` | Excel | `suprimentos/processos/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/processos/excel]`; existente: `tests/suprimentos/test_processos_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `suprimentos/processos` | PDF | `suprimentos/processos/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/processos/excel]`; existente: `tests/suprimentos/test_processos_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `suprimentos/diligenciamento` | Excel | `suprimentos/diligenciamento/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/diligenciamento/excel]`; existente: `tests/suprimentos/test_diligenciamento_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `suprimentos/diligenciamento` | PDF | `suprimentos/diligenciamento/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/diligenciamento/excel]`; existente: `tests/suprimentos/test_diligenciamento_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `suprimentos/mas` | Excel | `suprimentos/mas/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/mas/excel]`; existente: `tests/suprimentos/test_mas_rotas.py` | A3 paisagem (a folha e a planilha) |
| `suprimentos/mas` | PDF | `suprimentos/mas/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/mas/excel]`; existente: `tests/suprimentos/test_mas_rotas.py` | A3 paisagem (a folha e a planilha) |
| `suprimentos/painel` | Excel | `suprimentos/painel/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/painel/excel]`; existente: `tests/suprimentos/test_painel_rotas.py` |  |
| `suprimentos/painel` | PDF | `suprimentos/painel/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos/painel/excel]`; existente: `tests/suprimentos/test_painel_rotas.py` |  |

## 05 · Gestão de Riscos

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `riscos/registro` | Excel | `riscos/registro/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/registro/excel]`; existente: `tests/riscos/test_riscos_rotas.py` | A3 paisagem (a folha e a planilha) |
| `riscos/registro` | PDF | `riscos/registro/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/registro/excel]`; existente: `tests/riscos/test_riscos_rotas.py` | A3 paisagem (a folha e a planilha) |
| `riscos/matriz` | Excel | `riscos/matriz/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/matriz/excel]`; existente: `tests/riscos/test_riscos_matriz_painel_rotas.py` | A3 paisagem (a folha e a planilha) |
| `riscos/matriz` | PDF | `riscos/matriz/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/matriz/excel]`; existente: `tests/riscos/test_riscos_matriz_painel_rotas.py` | A3 paisagem (a folha e a planilha) |
| `riscos/painel` | Excel | `riscos/painel/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/painel/excel]`; existente: `tests/riscos/test_riscos_matriz_painel_rotas.py` |  |
| `riscos/painel` | PDF | `riscos/painel/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/painel/excel]`; existente: `tests/riscos/test_riscos_matriz_painel_rotas.py` |  |
| `riscos/ficha` | Excel | `riscos/ficha/excel` — escopo `?projeto=` e `codigo` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/ficha/excel]`; existente: `tests/riscos/test_riscos_ficha_rotas.py` | tela de detalhe: exige `codigo` |
| `riscos/ficha` | PDF | `riscos/ficha/imprimivel` — escopo `?projeto=` e `codigo` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[riscos/ficha/excel]`; existente: `tests/riscos/test_riscos_ficha_rotas.py` | tela de detalhe: exige `codigo` |

## 06 · Gestão da Qualidade

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `qualidade/rnc` | Excel | `qualidade/rnc/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/rnc/excel]`; existente: `tests/qualidade/test_qualidade_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `qualidade/rnc` | PDF | `qualidade/rnc/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/rnc/excel]`; existente: `tests/qualidade/test_qualidade_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `qualidade/painel` | Excel | `qualidade/painel/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/painel/excel]`; existente: `tests/qualidade/test_qualidade_painel_rotas.py` |  |
| `qualidade/painel` | PDF | `qualidade/painel/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/painel/excel]`; existente: `tests/qualidade/test_qualidade_painel_rotas.py` |  |
| `qualidade/auditorias` | Excel | `qualidade/auditorias/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/auditorias/excel]`; existente: `tests/qualidade/test_qualidade_auditorias_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `qualidade/auditorias` | PDF | `qualidade/auditorias/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/auditorias/excel]`; existente: `tests/qualidade/test_qualidade_auditorias_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `qualidade/inspecoes` | Excel | `qualidade/inspecoes/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/inspecoes/excel]`; existente: `tests/qualidade/test_qualidade_inspecoes_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `qualidade/inspecoes` | PDF | `qualidade/inspecoes/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[qualidade/inspecoes/excel]`; existente: `tests/qualidade/test_qualidade_inspecoes_rotas.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |

## 07 · HSE

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `hse/painel` | Excel | `hse/painel/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/painel/excel]`; existente: `tests/hse/test_hse_painel_rotas.py` | respeita a competência escolhida na tela |
| `hse/painel` | PDF | `hse/painel/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/painel/excel]`; existente: `tests/hse/test_hse_painel_rotas.py` | respeita a competência escolhida na tela |
| `hse/ocorrencias` | Excel | `hse/ocorrencias/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/ocorrencias/excel]`; existente: `tests/hse/test_hse_ocorrencias_rotas.py` | respeita os filtros da tela |
| `hse/ocorrencias` | PDF | `hse/ocorrencias/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/ocorrencias/excel]`; existente: `tests/hse/test_hse_ocorrencias_rotas.py` | respeita os filtros da tela |
| `hse/inspecoes` | Excel | `hse/inspecoes/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/inspecoes/excel]` | respeita o período da tela |
| `hse/inspecoes` | PDF | `hse/inspecoes/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/inspecoes/excel]` | respeita o período da tela |
| `hse/analises_risco` | Excel | `hse/analises-risco/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/analises-risco/excel]`; existente: `tests/hse/test_hse_analises_risco_rotas.py` | respeita os filtros da tela |
| `hse/analises_risco` | PDF | `hse/analises-risco/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/analises-risco/excel]`; existente: `tests/hse/test_hse_analises_risco_rotas.py` | respeita os filtros da tela |
| `hse/hht` | Excel | `hse/hht/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/hht/excel]` | respeita o período da tela |
| `hse/hht` | PDF | `hse/hht/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse/hht/excel]` | respeita o período da tela |

## 08 · Governança

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `governanca/mudancas` | Excel | `governanca/mudancas/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[governanca/mudancas/excel]`; existente: `tests/governanca/test_painel_mudancas.py` | respeita os filtros da tela |
| `governanca/mudancas` | PDF | `governanca/mudancas/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[governanca/mudancas/excel]`; existente: `tests/governanca/test_painel_mudancas.py` | respeita os filtros da tela |
| `governanca/mudanca` | Excel | `governanca/mudanca/excel` — escopo `?projeto=` e `codigo` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[governanca/mudanca/excel]` | tela de detalhe: exige `codigo` |
| `governanca/mudanca` | PDF | `governanca/mudanca/imprimivel` — escopo `?projeto=` e `codigo` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[governanca/mudanca/excel]` | tela de detalhe: exige `codigo` |
| `governanca/licoes` | Excel | `governanca/licoes/excel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[governanca/licoes/excel]`; existente: `tests/governanca/test_painel_licoes.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |
| `governanca/licoes` | PDF | `governanca/licoes/imprimivel` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[governanca/licoes/excel]`; existente: `tests/governanca/test_painel_licoes.py` | respeita os filtros da tela; A3 paisagem (a folha e a planilha) |

## Modelos de importação

| Tela | Botão | Rota | Teste que cobre | Observação |
|---|---|---|---|---|
| `financeiro/eac` | Excel | `importacao/eac-itens/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro-eac-eac-itens]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `financeiro/mapa_controle` | Excel | `importacao/custos-erp/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[financeiro-mapa_controle-custos-erp]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `hse/hht` | Excel | `importacao/hht/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse-hht-hht]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `hse/inspecoes` | Excel | `importacao/hse-mensal/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[hse-inspecoes-hse-mensal]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `planejamento/eap` | Excel | `importacao/eap-avanco/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento-eap-eap-avanco]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `planejamento/eap` | Excel | `importacao/eap-pacotes/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento-eap-eap-pacotes]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `planejamento/produtividade` | Excel | `importacao/produtividade-itens/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento-produtividade-produtividade-itens]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `planejamento/punch_list` | Excel | `importacao/punch-itens/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[planejamento-punch_list-punch-itens]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `suprimentos/plano_compras` | Excel | `importacao/plano-de-compras/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos-plano_compras-plano-de-compras]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |
| `suprimentos/diligenciamento` | Excel | `importacao/diligenciamento/modelo` — escopo `?projeto=` | `test_exportacoes_por_tela.py::test_excel_e_imprimivel_da_tela[suprimentos-diligenciamento-diligenciamento]`; existente: `tests/plataforma/test_importacao_rotas.py` | modelo vazio de importação (o botão «Baixar modelo») |


## O que a D12 pede, e onde está

| O que a D12 pede | Onde está |
|---|---|
| Botões Excel e PDF em toda tabela e painel, inclusive Início e Configurações | As seções Início e Configurações acima; o Início tem Excel e PDF e cada tela de Configurações tem os dois |
| PDF das ações | `central-acoes/acoes/imprimivel` (`data-tn-pdf` da tela de Ações), em A3 paisagem |
| PDF A3 paisagem do MAS com células coloridas | `suprimentos/mas/imprimivel`, com `paper=A3` no documento; as cores das células são os tons do Design System |
| Relatório gerencial com Imprimir / PDF, Excel e Alterar período | A tela `relatorio/gerencial` imprime pela folha de impressão da página (`data-relatorio-imprimir`) e o Excel sai por `relatorio/gerencial/excel?tipo=&periodo=&secoes=` |
| Relatório de impressão e planilha da Programação Semanal | `programacao-semanal/semana/imprimivel` (relatório) e `programacao-semanal/semana/excel` (planilha), com a semana pelo seletor |
| Modelos de importação | A seção Modelos de importação; o botão «Baixar modelo» de cada tela |

## Notas

* O teste de cada tela vive em `api/tests/plataforma/test_exportacoes_por_tela.py`; os testes de
  exportação dos módulos (`tests/<modulo>/...`) continuam valendo para os detalhes de cada
  documento, e são citados na coluna *Teste que cobre*.
* O exemplo de exportação é o mecanismo em vitrine: existe só no modo demonstração (403 em
  produção) e a página é `app/exemplos/exportacao.html`.
* A Programação Semanal é a única tela com dois documentos: a planilha (`week_document`) e o
  relatório de impressão (`week_report_document`) têm tabelas e indicadores próprios.
