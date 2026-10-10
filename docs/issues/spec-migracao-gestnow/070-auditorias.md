---
id: ISSUE-070
title: "Auditorias"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 14
blocked_by:
  - ISSUE-068
blocks:
  - ISSUE-071
labels:
  - ready-for-agent
source_requirements:
  - HU-118
spec_decisions:
  - D9
---

# Auditorias

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 14 (06 Qualidade).
> Histórias: 118. Bloqueada por: ISSUE-068.

## O que construir

A tela **Auditorias** mostra o programa (contratada, fornecedor, interna) com
escopo, critérios, auditado, auditor líder e data. Data vencida sem resultado
é **atrasada**; **reprogramação** exige justificativa e fica registrada. O
resultado registra itens verificados e conformes e as constatações (Não
conformidade, Observação, Oportunidade de melhoria); **cada não conformidade
abre RNC** (origem Auditoria), e não pode haver mais NC que itens não
conformes.

## Critérios de aceite

- [ ] Auditoria vencida sem resultado aparece atrasada pela data de hoje.
- [ ] Reprogramação sem justificativa é recusada.
- [ ] Cada NC abre uma RNC na mesma transação, e NC acima dos itens não conformes é recusada.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (atraso, reprogramação e RNC por NC).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `auditorias.html` da Qualidade; README, regras de auditorias.

## Registro de execução

Fatia entregue em 10/10/2026: a migração `m070` cria `auditoria_qualidade`,
`auditoria_constatacao` e `auditoria_reprogramacao` conforme o `docs/MODELO-DE-DADOS.md` (FKs de
projeto, empresa, auditor (pessoa), auditoria e RNC; UK de projeto + código; CHECKs de tipo e
situação; `versao` só na auditoria, porque constatação e reprogramação são fatos imutáveis) e
sobe/desce/sobe num banco vazio; a coluna `auditoria_qualidade.resumo` foi acrescentada na
mesma entrega com o MODELO §11 atualizado. A fachada (`service.py`) cobre o fluxo inteiro: a
lista com os filtros busca/situação (incluindo Atrasada)/tipo e a ordem data asc + código asc do
protótipo; os cinco KPIs (aderência ao programa, atrasadas, conformidade com a meta
`metaConformidadeAuditoriaPct`, NC de auditoria com as RNC em aberto e a próxima auditoria com a
linha de base da primeira reprogramação); o código `AUD-<padrão da ata do projeto>-NN` de dois
dígitos pelo maior código do projeto; a reprogramação só na planejada, com a nova data até a
referência e a justificativa de 10 caracteres, gravando `auditoria_reprogramacao` com o autor e
`registrada_em` (a trilha guarda o antes e o depois); o resultado só na planejada (data ≤
referência; itens verificados ≥ 1; conformes entre 0 e o verificado; constatação com descrição
≥ 10 e, na NC, requisito ≥ 3, disciplina e severidade; NC acima dos itens não conformes recusada
com a mensagem do protótipo) e **cada Não conformidade abre a RNC na mesma transação** pela
própria fachada `open_rnc` (origem `Auditoria`, `origem_ref` o código da auditoria, empresa o
auditado, descrição `<descrição> Requisito: <requisito>.`, severidade da constatação e a
contenção padrão `Contenção a definir pelo auditado em até 48 horas da auditoria <AUD>.`),
gravando `auditoria_constatacao.rnc_id`. As rotas novas vivem em `auditorias_routes.py` (tela,
Excel, imprimível, ficha, nova, reprogramação e resultado), com `Access` (ver = READ;
planejar/editar/resultado = WRITE) e os alvos `auditorias-conteudo`/`auditorias-modal-corpo`; o
trio da tela (view/CSS/JS) registra `TN.paginas["qualidade/auditorias"]`. No Portfólio os
formulários pedem o projeto antes e a tabela (e as exportações) trazem a coluna Projeto. A carga
nova `qualidade-auditorias` (registrada depois de `qualidade-inspecoes`) traz as 8 auditorias do
convertido com as constatações (`ordem` e o `rncRef` resolvido para `rnc_id`) e as datas
deslocadas; a numeração de cada projeto continua depois dos códigos carregados (a série é lida
dos códigos em vigor). O oráculo afirma o projeto 1 em 25/09/2026: **5 auditorias (2 realizadas
e 3 planejadas, 1 atrasada — a AUD-TN-2026-05 de 15/09/2026), conformidade de 90,0% na
AUD-TN-2026-01 e 82,9% na AUD-TN-2026-02, aderência ao programa de 66,7%, os vínculos
AUD-TN-2026-01→RNC-TN-2026-0001 e AUD-TN-2026-02→RNC-TN-2026-0005 e a NC em aberto contando só a
RNC ativa**. `ruff check`, `ruff format --check` (a migração incluída) e `ty check` limpos;
a migração e a suíte (qualidade, migrações, carga e oráculo — 161 testes) passam.

- DECISAO: conclusão da auditoria (`resumo`) | o formulário do protótipo coleta "Conclusão da auditoria" (até 600) e a ficha exibe, e o MODELO §11 não tinha a coluna; `auditoria_qualidade.resumo` (text, nula) entra na migração `m070` e o diagrama muda na mesma entrega | D5, ISSUE-070
- DECISAO: coluna textual `auditado` | o MODELO desenha `auditoria_qualidade.auditado` além de `empresa_id`, e o mock/protótipo só têm o `auditadoId`; a coluna fica como o MODELO a desenha (registro textual do auditado quando não for empresa do cadastro) e não é preenchida nesta fatia — a empresa auditada é `empresa_id` | D5, ISSUE-070
- DECISAO: código da auditoria | `AUD-<padrão da ata do projeto>-NN` (2 dígitos), pelo maior código do projeto, como o protótipo contava (sem a sequência travada); a numeração continua depois dos códigos da carga por construção | D5, ISSUE-070
- DECISAO: RNC de cada Não conformidade | a constatação NC abre a RNC pela própria fachada `open_rnc`, na mesma transação (D9), com origem `Auditoria`, `origem_ref` o código, a empresa auditada, a descrição `<descrição> Requisito: <requisito>.`, a severidade da constatação e a contenção padrão do protótipo; o vínculo é `auditoria_constatacao.rnc_id` | D9, ISSUE-070
- DECISAO: reprogramação | só na auditoria Planejada; mudar a data exige justificativa (mínimo de 10) e grava `auditoria_reprogramacao` com data anterior, nova data, autor e `registrada_em` (sem `versao`: é fato); a trilha da auditoria guarda a edição com antes e depois | D5, D5b, ISSUE-070
