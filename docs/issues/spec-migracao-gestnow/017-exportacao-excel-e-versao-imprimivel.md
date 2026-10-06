---
id: ISSUE-017
title: "Exportação Excel e versão imprimível (PDF pelo navegador) genéricas"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-011
  - ISSUE-014
blocks:
  - ISSUE-018
labels:
  - ready-for-agent
source_requirements:
  - HU-016
  - HU-136
  - HU-137
  - HU-138
spec_decisions:
  - D12
  - D14
---

# Exportação Excel e versão imprimível (PDF pelo navegador) genéricas

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D14.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 16, 136, 137, 138. Bloqueada por: ISSUE-011, ISSUE-014.

## O que construir

O **Excel** é gerado no servidor com openpyxl, por um construtor genérico que
toda tela usa: logo, título, escopo (Portfólio ou projeto), data de geração,
KPIs com a referência de gestão, tabelas com filtro e cores das células pelos
tokens, valores em reais (integral) e datas formatadas. No Portfólio, a coluna
Projeto entra sempre. A rota de download segue a exceção de download do Padrão
e passa pelo mesmo decorador de permissão.

O **PDF** é a impressão do navegador: o servidor renderiza a versão imprimível
da tela (cabeçalho com logo e contexto, KPIs, gráficos e tabelas) pela folha
de impressão do Design System; o botão PDF a abre e aciona a impressão, e a
pessoa escolhe "Salvar como PDF". `@page` A4 paisagem por padrão, com opção A3
paisagem; sem navegação no papel; cabeçalho de tabela repetido; linha que não
parte entre páginas; fundos preservados. Sem biblioteca de PDF no servidor nem
no navegador.

Os dois mecanismos são demonstrados numa tela de exemplo do styleguide ou numa
rota de teste, para que as issues de módulo só os usem.

## Critérios de aceite

- [x] O Excel gerado abre e tem logo, título, escopo, data, KPIs com referência e a tabela com filtro; no Portfólio, a coluna Projeto.
- [x] As cores das células do Excel vêm dos tokens.
- [x] A versão imprimível não tem barra lateral nem navegação, repete o cabeçalho da tabela em cada página e não parte linha.
- [x] A3 paisagem funciona quando a tela pede.
- [x] Nenhuma biblioteca de PDF foi adicionada.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste que abre o Excel gerado com openpyxl e confere planilha, cabeçalho, KPIs
e colunas; teste de rota do download (tipo e permissão); teste do template
imprimível sem navegação. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedentes: exportação, planilha, `print.css` e relatório de impressão do app
de Programação Semanal. O conteúdo de cada exportação vem do protótipo
(`js/components/exportar.js` e `logo-pdf.js`): o que o protótipo exporta, o
GestNow exporta, nem uma coluna a menos.

## Registro de execução

Data: 05/10/2026 (retomada e fechamento em 06/10/2026).
Feito: `core/export_document.py` (o `Document`, uma descrição para as duas saídas), `core/excel.py` (openpyxl: logo, título, escopo, data, KPIs com referência, tabela com filtro, cores pelos tokens, reais cheios, coluna Projeto no Portfólio), `core/printable.py` + `comum/imprimivel.html` + `app/ds/print.css` (A4/A3 paisagem, sem navegação, cabeçalho repetido, linha que não parte), `core/design_tokens.py`, `responses.file_response`, rotas de exemplo (`blueprints/exports.py`, só em demonstração), página `app/exemplos/exportacao.html`, botões `data-tn-excel` e `data-tn-pdf` em `app/ds/ui.js`; testes `test_exportacao_{documento,excel,imprimivel,rotas}.py` e `test_ativos_da_exportacao.py`; seção "Exportação" em `api/README.md` (API pública para a ISSUE-018). Nada rodado (política do dono): só `ruff` e `node --check`.
Pendências: rodar pytest, `ty check` e `npm run verificar` no fim da entrega (o `.venv` precisa de openpyxl e pillow); porta de qualidade `[ ]` (o orquestrador marca). Compartilhados tocados: `function_app.py`, `dev_local.py`, `index.html`, `pyproject.toml`, `requirements.txt`, `uv.lock`, `ui.js`, `shell.css`. `responses.file_response` repete a lógica do `_content_disposition` da ISSUE-012 (unificar depois).
DECISÃO: Excel no servidor | o openpyxl gera o .xlsx e o pillow entra só porque o openpyxl precisa dele para inserir o logo; nenhuma biblioteca de PDF no servidor nem no navegador | D12, ISSUE-017
DECISÃO: Cores e logo do Excel | vêm do Design System por cópia gerada (`api/src/core/tokens_ds.json` e `logo_timenow.png`, escritos por `scripts/generate_ds_assets.py`) porque só `api/` vai para o Azure; um teste falha se a cópia defasar | D12, ISSUE-017
DECISÃO: Download do Excel | usa o `file_route` da ISSUE-012 (sem gate do Alpine, recusa em texto simples) e `responses.file_response`; o botão baixa por fetch e mostra a recusa em toast | D14, ISSUE-017
DECISÃO: Folha imprimível | o botão PDF monta a folha no fim do body, espera os gráficos e chama `window.print()`; só a folha sai no papel; A4 paisagem por padrão e A3 paisagem pelo `Paper.A3` do documento; `print.css` ligado com `media="print"` e a espera da folha na tela em `shell.css` | D12, ISSUE-017
DECISÃO: Exemplo de exportação | rotas `/api/exportacao/exemplo/excel` e `/imprimivel` com dados fictícios, só no modo demonstração (403 em produção), e a página `app/exemplos/exportacao.html` | D12, ISSUE-017
DECISÃO: Excel e folha do mesmo documento | um `Document` (`export_document.py`) alimenta os dois; no Portfólio toda tabela por projeto abre com a coluna Projeto (HU-016) | D12, ISSUE-017
DECISÃO: API pública da exportação | os nomes de `core.export_document`, `core.excel` (`build_workbook`, `excel_response`), `core.printable`, `responses.file_response` e `routing.file_route` ficam estáveis e documentados no `api/README.md` (seção "Exportação"); o modelo de importação da ISSUE-018 é um `Document` com `Table` sem linhas | D12, ISSUE-017
