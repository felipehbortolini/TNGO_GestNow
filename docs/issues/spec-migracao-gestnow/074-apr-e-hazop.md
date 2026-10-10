---
id: ISSUE-074
title: "Análises de risco APR e HAZOP"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 15
blocked_by:
  - ISSUE-019
blocks:
  - ISSUE-075
labels:
  - ready-for-agent
source_requirements:
  - HU-123
spec_decisions:
  - D9
---

# Análises de risco APR e HAZOP

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 15 (07 HSE).
> Histórias: 123. Bloqueada por: ISSUE-019.

## O que construir

A tela **Análises de risco** registra os estudos (tipo APR/JSA ou HAZOP, área,
data, participantes) e as recomendações (responsável, prazo, situação). Cada
recomendação vira ação na Central pela costura (origem HSE), com o link de
volta para o estudo, e a situação fica sincronizada. O indicador de
recomendações fechadas ÷ emitidas fica disponível para o painel.

## Critérios de aceite

- [ ] A recomendação cria a ação na Central com link de volta ao estudo.
- [ ] Recomendação e ação ficam sincronizadas.
- [ ] Recomendações fechadas ÷ emitidas tem teste da fórmula.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (recomendação e sincronização) e de cálculo.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `analises-risco.html` e `js/pages/hse/analises-risco.js`.

## Registro de execução

Fatia entregue em 10/10/2026: a migração `m074` (down `m073`) cria `analise_risco`,
`analise_risco_participante` e `analise_risco_recomendacao` conforme o `docs/MODELO-DE-DADOS.md`
§12 (UK de projeto + código; CHECKs de tipo APR/HAZOP e situação Aberta/Fechada; FKs de projeto,
estudo e pessoa; `versao` onde o MODELO tem) e sobe/desce/sobe num banco vazio; as colunas
`data_conclusao` e `evidencia` foram acrescentadas à recomendação no MODELO §12 na mesma entrega
(o protótipo guardava o fechamento e o diagrama não tinha onde — divergência registrada). A
fachada (`service.py`) cobre o registro do estudo de uma vez (tipo, área, título, data ≤ a
referência, participantes e recomendações, todas Aberta) com o código nascendo da **série do
projeto e do tipo** — `APR-<padrão da ata>-NNNN` e `HAZOP-<padrão da ata>-NNNN`, quatro dígitos,
kinds novos `apr` e `hazop` do núcleo de numeração — e a validação com as mensagens do protótipo
(título mínimo de 5; responsável e prazo por recomendação). Cada recomendação pode virar **uma**
ação na Central pela costura única (origem `HSE` — a mesma das ocorrências —, `origem_ref` o
código do estudo, `item` a ordem, grupo `<TIPO> · Recomendação`, assunto a descrição, descrição
`<título> (<área>)`, responsável e prazo da recomendação); a segunda tentativa é recusada com a
mensagem do protótipo, conferida em `central.actions_of_origin` pelo item (sem a coluna
`acao_criada`). A **sincronização** (D9, padrão da ISSUE-049) vale nas duas direções com uma só
reação registrada para a origem `HSE` (`react_to_hse_action`, que ignora as ações `OCR-` das
ocorrências): concluir a ação na Central fecha a recomendação na data da conclusão e replanejar
move o prazo; fechar a recomendação na tela do estudo (data de conclusão ≤ a referência e
evidência opcional) conclui a ação vinculada na mesma transação. O construtor do link de volta da
origem `HSE` passou a rotear pelo prefixo do código: `APR-`/`HAZOP-` vão para `hse/analises_risco`
e `OCR-` continua em `hse/ocorrencias`, ambos com a busca do código. As rotas novas vivem em
`analises_risco_routes.py` (blueprint `hse_analises_risco_bp`: lista com filtros busca/tipo/abertas
e páginas, Excel, imprimível, ficha, nova, fechar e criar ação), com nomes únicos no app
(`risk_study_*`) e os alvos `analises-risco-conteudo`/`analises-risco-modal-corpo`; o trio da tela
(view/CSS/JS) registra `TN.paginas["hse/analises_risco"]` e o JS cuida das linhas repetíveis de
recomendação (acrescentar/remover, renumerando `rec_*_N`). No Portfólio a lista e as exportações
trazem a coluna Projeto e a inclusão pede o projeto antes do formulário. A carga nova
`hse-analises-risco` (registrada depois de `hse-ocorrencias`) traz os 8 estudos do convertido
(projetos 1 a 3) com participantes e recomendações, datas deslocadas e a numeração continuando por
projeto e tipo; a recomendação já Fechada do mock recebe a data de conclusão no próprio prazo (o
mock não guardava a data). O oráculo afirma o projeto 1 em 25/09/2026: **5 estudos (3 APR e 2
HAZOP), 17 recomendações (8 abertas e 9 fechadas), 3 atrasadas (prazos 20/08, 10/09 e 20/09/2026),
o indicador fechadas ÷ emitidas em 52,9% e a HAZOP-TN-2026-01 com 6 recomendações (3/3), 1
atrasada e 4 participantes**; o indicador fica pronto para o painel da 075 em
`service.recommendation_share`. Divergências registradas: as colunas do fechamento
(`data_conclusao`/`evidencia`) e o fechamento manual concluindo a ação vinculada (o protótipo
fechava sem tocar na ação e marcava `acaoCriada`). `ruff check`, `ruff format --check` e `ty check`
limpos; a suíte (HSE, Central, Governança, Qualidade, plataforma e oráculo — 1.631 testes) passa; a
porta de qualidade, 5/5.

- DECISAO: fechamento da recomendação | `analise_risco_recomendacao.data_conclusao` (date) e `evidencia` (text) acrescentadas ao MODELO §12 na mesma entrega; o protótipo as gravava e o diagrama não tinha onde | D5b, ISSUE-074
- DECISAO: sincronização nas duas direções | uma só reação registrada para a origem `HSE` (`react_to_hse_action`): concluir a ação fecha a recomendação na data da conclusão, replanejar move o prazo, e a ação `OCR-` das ocorrências não reage; o fechamento manual da recomendação conclui a ação vinculada na mesma transação, sem a coluna `acao_criada` do protótipo | D9, ISSUE-074
- DECISAO: numeração por tipo | séries separadas por projeto e tipo de estudo, kinds `apr` e `hazop` (`APR-<padrão da ata>-NNNN` e `HAZOP-<padrão da ata>-NNNN`, quatro dígitos); a carga continua cada série do maior código carregado | D5, ISSUE-074
- DECISAO: link de volta da origem `HSE` por prefixo | `APR-`/`HAZOP-` roteiam para `hse/analises_risco` e `OCR-` para `hse/ocorrencias`, com a busca do código | D9, ISSUE-074
- DECISAO: uma ação por recomendação | a duplicata é recusada com a mensagem do protótipo, conferida em `central.actions_of_origin` pelo item (a ordem), sem coluna no estudo | D9, ISSUE-074

