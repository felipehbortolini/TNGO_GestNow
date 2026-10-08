---
id: ISSUE-049
title: "Punch list: itens, fluxo com verificação e bloqueio de sistema"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-019
blocks:
  - ISSUE-050
labels:
  - ready-for-agent
source_requirements:
  - HU-068
  - HU-069
spec_decisions:
  - D7
  - D9
  - D5a
---

# Punch list: itens, fluxo com verificação e bloqueio de sistema

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9, D5a.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 68, 69. Bloqueada por: ISSUE-019.

## O que construir

A tela **Punch list**, aba Lista, registra itens com numeração
`PL-TN-2026-0001`, hierarquia Área, Sistema, Subsistema e TAG, disciplina,
categoria (A impede o marco seguinte; B fecha até o aceite definitivo; C
conforme acordo), marco vinculado, origem, descrição, empresa executante,
responsável, prazo, identificado por, data de abertura e fotos.

Fluxo: Aberto, Em tratamento, Aguardando verificação, Fechado, voltando para
Em tratamento quando a verificação reprova; Cancelado exige justificativa. O
fechamento exige evidência (anexo) e verificação por pessoa diferente do
executante (segregação). **Sistema com item A aberto fica bloqueado** para o
marco vinculado.

Cada item gera uma ação na Central (origem Punch list) pela costura, e o
status do item e o da ação ficam sincronizados nos dois sentidos. Modais Novo
item, Fechamento com verificação, Filtros e Importação Excel.

## Critérios de aceite

- [x] Fechamento sem anexo é recusado, e o verificador igual ao executante recebe 403.
- [x] Item A aberto bloqueia o sistema para o marco vinculado.
- [x] Item e ação ficam sincronizados nos dois sentidos.
- [x] A importação recusa linhas inválidas e grava as válidas só na confirmação.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (fluxo, segregação, bloqueio, sincronização e importação) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `punch-list.html`, `GI.api.planejamento.punch`; README, "Punch list: regras".

## Registro de execução

- Data: 2026-10-08.
- Feito: o modelo `PunchItem` (`punch_item`, UK projeto + código; a evidência é `anexo`, D5a) em `models.py`; a migração `m042_punch_list`; os cálculos em `calculations.py` (bloco "Punch list: situação, atraso e bloqueio (ISSUE-049)": `PunchState`, `PunchKpis` com o percentual dos válidos, `punch_is_open`, `punch_age_days`, `punch_is_overdue`, `punch_kpis`, `punch_system_block_count` e `punch_action_description`); a validação em `validation.py` (situações, categorias, marcos, origens, resultados e os parsers `parse_punch_item`, `parse_punch_verification` e `parse_punch_cancellation`, com a justificativa de cancelamento de no mínimo 10 caracteres); a fachada em `service.py` (bloco Punch list: `punch_overview`, os formulários, `create_punch_item`, `update_punch_item`, `treat_punch_item`, `send_punch_item_to_verification`, `verify_punch_item`, `cancel_punch_item`, `read_punch_origin` para os anexos e `react_to_punch_action` registrada como reação da origem) com os internos `_punch_blocks`, `_create_punch_action`, `_sync_punch_action`, `_close_punch_action` e `_punch_action_link`; o `central_acoes.sync_from_origin` (função nova da API estável da Central, com `MIRRORED_FIELDS`) e o `_update` passando a aceitar `Mapping[str, Any]`; o cadastro de sistemas em `configuracoes/registers.py` (`SystemOption`, `list_systems`, `system_options_by_id`); as rotas em `routes.py` (bloco `PUNCH_BASE = "planejamento/punch"`: tela, Excel/PDF, filtros, formulários, criar/editar, tratar, enviar, verificação e cancelamento); a importação em `importers.py` (`punch_importer`, chave `punch-itens`); a exportação em `export.py` (`punch_document`, `punch_kpis`, tabela e linha); os fragmentos `punch.html`, `punch_conteudo.html`, `punch_filtros.html`, `punch_modal.html`, `punch_resposta.html`, `punch_item_form.html`, `punch_fechamento_form.html`, `punch_cancelar_form.html`, `punch_filtros_form.html` e os parciais `_punch_*`; o trio `app/_views/planejamento/punch_list.html` (a view era um esqueleto de carregando desde a criação do módulo e virou a tela real), `app/paginas/planejamento/punch_list.css` e `.js`; a carga `seed_punch.load_punch` (parte `planejamento-punch`); os testes `test_punch_servico.py` e `test_punch_rotas.py` (nomes únicos) com o apoio em `api/tests/apoio_punch.py`; o oráculo em `test_carga_demonstracao.py`; a seção desta fatia no `LEIA-ME.md`; e a seção "Punch list" no `CONTEXT.md` com o `glossario.json` regerado.
- Oráculos: o mock traz 20 itens (16 no projeto 1 e 4 no projeto 2) e o item cancelado não deriva ação; no projeto 1, sem deslocamento, são 12 abertos, 4 da categoria A, 2 aguardando verificação, 2 vencidos e 3 fechados (15 válidos) e 15 ações na Central; o sistema 420 fica bloqueado para a Completação mecânica pelo item A aberto e os sistemas 210, 310 e 420 para o Comissionamento (o Aceite definitivo é bloqueado pelos 4 abertos do sistema); o PL-TN-2026-0001 tem a ação concluída em 20/08/2026; a carteira traz os itens dos dois projetos.
- Decisão: a sincronização nos dois sentidos usa a costura da ISSUE-019. Item → ação: a fachada espelha prazo, assunto, descrição e fechamento nas ações abertas de origem Punch list (`_sync_punch_action`, `_close_punch_action`) e a Central ganhou `sync_from_origin` para atualizar os campos que a ação copia do registro de origem. Ação → item: a reação registrada (`react_to_punch_action`) fecha o item na conclusão (na data da ação) e move o prazo no replanejamento. A Central continua sem ler a tabela alheia.
- Decisão: o bloqueio do sistema segue a regra `bloqueio` do protótipo e é calculado a cada leitura: a categoria A bloqueia o marco pedido quando o marco do item é anterior ou igual a ele; o aceite definitivo é bloqueado por qualquer item aberto do sistema; um marco fora da lista não bloqueia nada. Nenhuma coluna nova.
- Decisão: o item cancelado não gera ação na Central, como o `acaoDoPunch` do protótipo; os cancelados ficam fora dos itens válidos (o percentual de fechados usa os válidos).
- Decisão: a importação entra pelo fluxo genérico (ISSUE-018) com a chave `punch-itens` (prévia e confirmação): a linha inválida volta com a mensagem e nada é gravado antes da confirmação; sistema, empresa e responsável são resolvidos pelo cadastro (código e nome).
- Decisão: a numeração usa o tipo `punch` do projeto (`PL-TN-2026-0001`) e a carga continua a série de cada projeto depois do maior código do mock, para o primeiro item gerado por uma pessoa não colidir.
- Decisão: o cadastro `sistema` já existia desde a `0001_plataforma`; a migração desta fatia só cria `punch_item`, como o diagrama de `docs/MODELO-DE-DADOS.md` já previa — o diagrama não mudou.
- Decisão: os termos novos de domínio (Punch list, Categoria do item, Bloqueio do sistema, Verificação do item) entraram no `CONTEXT.md` e o `glossario.json` foi regerado.
- Verificação: suíte escopada (`api/tests/planejamento api/tests/plataforma api/tests/central_acoes api/tests/configuracoes`) verde com 1736 testes; os testes do punch verdes de novo após os ajustes de lint (55); a migração `m042` sobe em banco vazio (`gestnow_m042_check`, tabela criada e banco apagado); `ruff check`, `ruff format --check` e `ty check` verdes (com o `PLR0913` justificado em `tests/apoio_punch.py`); porta de qualidade completa (`node scripts/verificar.mjs`) verde nas cinco etapas. Sem pendência e sem divergência de spec.
