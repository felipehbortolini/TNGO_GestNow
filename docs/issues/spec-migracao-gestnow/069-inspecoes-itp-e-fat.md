---
id: ISSUE-069
title: "Inspeções e ITP, com o FAT do diligenciamento"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 14
blocked_by:
  - ISSUE-068
  - ISSUE-061
blocks:
  - ISSUE-071
labels:
  - ready-for-agent
source_requirements:
  - HU-104
  - HU-117
spec_decisions:
  - D9
---

# Inspeções e ITP, com o FAT do diligenciamento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 14 (06 Qualidade).
> Histórias: 104, 117. Bloqueada por: ISSUE-068, ISSUE-061.

## O que construir

A tela **Inspeções e ITP** mostra os planos de inspeção e testes (pontos H, W e
R com critério, referência e responsável; revisão e aprovação do cliente) e os
registros de inspeção por ponto (filtros por ITP, resultado e tipo).

Regras: ponto H (espera) só libera a atividade seguinte com o registro
aprovado; ponto W (testemunho) exige o cliente notificado com a antecedência
mínima do parâmetro, e notificação ausente ou menor gera aviso; ponto R
(revisão de registros). Inspeção só em ITP aprovado pelo cliente; nova revisão
do ITP volta a pedir aprovação e não pode retirar ponto que já tem inspeção.
Ressalva conta como aprovada; **reprovação abre RNC** automaticamente, com a
severidade e a contenção do próprio registro, na mesma transação.

Ligação com Suprimentos: o **FAT realizado** no diligenciamento registra a
inspeção (origem Suprimentos); FAT reprovado não conclui o marco e exige nova
previsão do reteste.

## Critérios de aceite

- [ ] Inspeção em ITP não aprovado é recusada, e a revisão do ITP não retira ponto com inspeção.
- [ ] A antecedência da notificação gera aviso pela fronteira do parâmetro.
- [ ] Reprovação abre a RNC na mesma transação.
- [ ] FAT realizado grava a inspeção; FAT reprovado não conclui o marco.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (ITP, pontos, reprovação e FAT).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `inspecoes.html` da Qualidade e o FAT do diligenciamento (`inspecoesQualidade`, origem Suprimentos); README, regras do ITP.

## Registro de execução

Fatia entregue em 10/10/2026: a migração `m069` cria `itp`, `itp_revisao`, `itp_ponto` e
`inspecao` conforme o `docs/MODELO-DE-DADOS.md` (FKs de projeto, disciplina, empresa, pessoa,
RNC e pedido; UK de `itp.codigo` e de `inspecao` por projeto + código; `itp_ponto_id` e
`pedido_id` nulos porque o FAT não tem ponto de ITP; CHECKs de tipo de ponto e resultado) e
sobe/desce/sobe num banco vazio; a coluna `inspecao.notificacao` foi acrescentada na mesma
entrega com o MODELO §11 atualizado. A fachada (`service.py`) cobre o fluxo inteiro: o ITP com
a revisão vigente e os pontos H/W/R, a revisão que casa os pontos pela atividade normalizada
(preservando o id), volta a pedir a aprovação e não retira ponto com inspeção, a aprovação do
cliente uma vez por revisão (Gestor), a inspeção só em ITP aprovado, a ressalva contando como
aprovada, a reprovação abrindo a RNC na mesma transação (origem `Inspeção`, `origem_ref` o
número da inspeção e o vínculo `inspecao.rnc_id`) e os avisos da notificação pela fronteira do
parâmetro `notificacaoClienteHoras` (ausente avisa, menor avisa, exatamente o parâmetro passa).
As rotas novas vivem em `inspecoes_routes.py` (tela, Excel, imprimível, ficha do ITP, novo ITP,
nova revisão, aprovação e registro de inspeção), com `Access` (ver = READ; gravar = WRITE;
aprovar = MANAGE) e os alvos `inspecoes-conteudo`/`inspecoes-modal-corpo`; o trio da tela
(view/CSS/JS) registra `TN.paginas["qualidade/inspecoes"]`. No Portfólio os formulários pedem o
projeto antes e as tabelas (e as exportações) trazem a coluna Projeto. O FAT de Suprimentos
(`update_order_milestone`, marco Inspeção/FAT) chama `qualidade.service.record_fat_inspection`
na mesma transação: aprovado conclui o marco com realizada = previsão = data e a trilha recebe
"FAT aprovado (INS-...)."; reprovado não conclui, exige a nova previsão do reteste ≥ referência
("FAT reprovado: informe a nova previsão do reteste.") com a cascata e a trilha "FAT reprovado
(INS-...); reteste previsto. ". A carga nova `qualidade-inspecoes` (registrada depois de
`qualidade-rnc`) traz os 8 ITPs com a revisão vigente, os pontos e a aprovação do mock e as 28
inspeções com o ponto mapeado, o `rncRef` resolvido e as datas deslocadas; o oráculo afirma os
**5 ITPs (4 aprovados), 40 pontos (15 cobertos) e 20 inspeções (3 reprovadas, 17 aprovadas com
a ressalva) do projeto 1 em 25/09/2026**, com os vínculos INS-2026-0145→RNC-TN-2026-0004,
INS-2026-0155→RNC-TN-2026-0005 e INS-2026-0117→RNC-TN-2026-0002. As divergências do protótipo
desta fatia estão em `docs/DIVERGENCIAS-DO-PROTOTIPO.md` ("pendente de aceite"). `ruff check`,
`ruff format --check` e `ty check` limpos nos arquivos tocados; a migração e a suíte
(qualidade, suprimentos, migrações, carga e oráculo) passam.

- DECISAO: notificação na inspeção | o MODELO §11 não tinha a coluna e o ponto W exige a antecedência mínima do parâmetro; `inspecao.notificacao` (date, nula) entra na migração `m069` e o diagrama muda na mesma entrega | D5, D6, ISSUE-069
- DECISAO: aprovação do ITP | o protótipo exige Gestor; a fachada e a rota pedem `Permission.MANAGE` ("Registrar a aprovação do ITP exige papel Gestor.", 403) | D7, ISSUE-069
- DECISAO: numeração do ITP e da inspeção | o ITP segue `ITP-<padrão do projeto>-<SIGLA da disciplina>-NN` (2 dígitos), pelo maior código existente do projeto e do prefixo, sem a sequência travada (o protótipo também contava os códigos); a inspeção é a série global `INS-<ano>-NNNN` (4 dígitos) por `numbering.next_series_number` | D5, ISSUE-069
- DECISAO: revisão do ITP | os pontos casados pela atividade normalizada mudam para a revisão nova preservando o id (a inspeção continua ligada a eles), o ponto com inspeção não sai e a aprovação volta a pendente; a revisão nova entra em `itp_revisao` | D5, ISSUE-069
- DECISAO: FAT identificado pelo pedido | o MODELO não tem coluna de origem; a inspeção do FAT é a que tem `pedido_id` (sem ponto de ITP) e o ponto copiado carrega "Inspeção em fábrica (FAT) <PED>", com o tipo H e a empresa do fornecedor | D9, ISSUE-069
- DECISAO: anexos da inspeção | o modal do protótipo aceitava relatório, fotos e certificados; a fatia grava o registro e não liga o tipo de origem `inspecao` (a inspeção não tem tela de ficha para o painel) — divergência registrada em `docs/DIVERGENCIAS-DO-PROTOTIPO.md` | D5a, ISSUE-069
