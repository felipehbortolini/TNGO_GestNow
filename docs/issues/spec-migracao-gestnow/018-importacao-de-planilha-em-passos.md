---
id: ISSUE-018
title: "Importação de planilha em passos com conferência linha a linha"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-017
blocks:
  - ISSUE-019
  - ISSUE-023
  - ISSUE-029
  - ISSUE-044
  - ISSUE-045
  - ISSUE-051
  - ISSUE-064
  - ISSUE-072
labels:
  - ready-for-agent
source_requirements:
  - HU-139
spec_decisions:
  - D12
---

# Importação de planilha em passos com conferência linha a linha

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 139. Bloqueada por: ISSUE-017.

## O que construir

A importação vira um fluxo genérico do servidor, em passos: baixar o modelo
(Excel gerado pelo construtor da ISSUE-017), enviar o arquivo, conferir linha a
linha com pré-visualização (erro bloqueia a linha, aviso não) e confirmar.
Nada grava antes da confirmação, e a confirmação grava tudo numa transação só.
Cada módulo registra o seu importador: colunas, validação por linha e gravação
pela fachada.

Substitui a leitura de planilha no navegador do protótipo (SheetJS) e elimina o
risco registrado lá.

## Critérios de aceite

- [x] Um importador de teste percorre os passos: modelo, envio, conferência e confirmação.
- [x] Linha com erro não grava; linha com aviso grava; a conferência mostra o motivo de cada uma.
- [x] Cancelar na conferência não grava nada.
- [x] A confirmação grava tudo ou nada.
- [x] Arquivo que não é planilha é recusado com 422.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada do fluxo com o importador de teste e testes de rota do envio
e da confirmação. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedente: importação do app de Programação Semanal (conferência e
resultado). Fonte dos passos e da validação: `js/components/importar.js` do
protótipo.

## Registro de execução

Data: 06/10/2026.
Feito: `core/importing.py` (`Importer`, `ImportColumn`, `RowCheck`, `model_document`, `check`, `confirm`, registro de importadores), `core/spreadsheet_reader.py` (só `.xlsx`, conferido antes de abrir, 422 para o resto), `core/import_values.py` (conversão de célula: texto, lista, número, percentual, dinheiro em centavos, data), `blueprints/importing.py` (4 rotas `/api/importacao/{chave}`: tela dos passos, modelo, conferir, confirmar), fragmentos `comum/importacao*.html`, `.kpi--estatico` em `app/ds/patterns.css`, seção "Importação" em `api/README.md`; testes `test_importacao_{valores,leitura,fluxo,rotas}.py` com os importadores de `tests/importadores_de_teste.py`. Modelo gerado pelo `Document` da ISSUE-017 (`Table` sem linhas); botão do modelo é o `data-tn-excel` da 017. Nada rodado (política do dono): só `ruff`.
Pendências: rodar pytest, `ty check` e `npm run verificar` no fim da entrega (o `.venv` precisa de openpyxl); porta de qualidade `[ ]` (o orquestrador marca). Compartilhados tocados: `function_app.py`, `dev_local.py`, `pyproject.toml` (só `openpyxl>=3.1.5`; o orquestrador reconcilia lockfile e requirements), `patterns.css`. Sem migração, sem carga e sem oráculo (fluxo genérico, sem número do protótipo).
DECISÃO: Importação sem estado no servidor | a conferência e a confirmação recebem o mesmo arquivo; a confirmação lê e confere de novo e só vale para o arquivo conferido (SHA-256 em `conferido`); nada fica guardado entre os passos, então cancelar é só fechar a conferência | D12, ISSUE-018
DECISÃO: Confirmação tudo ou nada | as linhas sem erro são gravadas dentro de um savepoint; a recusa de uma linha desfaz as anteriores e a mensagem 422 diz a linha | D5, ISSUE-018
DECISÃO: Modelo de importação | é um `Document` da ISSUE-017: a aba Dados só com o cabeçalho e a aba Instruções com obrigatória, formato e exemplo de cada coluna; o exemplo não vai em Dados para não ser importado por engano (o protótipo o punha na primeira aba) | D12, ISSUE-018
DECISÃO: Formatos e limites da importação | só `.xlsx`, até 5 MB, 5.000 linhas de dados e 50 MB expandidos; o `.xls` e o `.csv` que o protótipo aceitava são recusados com 422 e a orientação de usar o modelo | D12, ISSUE-018
DECISÃO: Linhas com erro na confirmação | se há linha com erro a pessoa marca "estou ciente" (como o passo 4 do protótipo) e só as linhas sem erro entram; o servidor exige a marca | D12, ISSUE-018
DECISÃO: Acesso da importação | o importador declara o módulo e a permissão (`WRITE` por padrão); as rotas pedem `WRITE` e a fachada confere o módulo; o fornecedor não importa | D7, ISSUE-018
