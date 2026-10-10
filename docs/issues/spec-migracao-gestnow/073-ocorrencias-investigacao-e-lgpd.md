---
id: ISSUE-073
title: "Ocorrências com investigação, prazos legais e dados restritos (LGPD)"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 15
blocked_by:
  - ISSUE-072
  - ISSUE-019
  - ISSUE-027
blocks:
  - ISSUE-075
labels:
  - ready-for-agent
source_requirements:
  - HU-120
  - HU-124
spec_decisions:
  - D5a
  - D5b
  - D7
  - D9
---

# Ocorrências com investigação, prazos legais e dados restritos (LGPD)

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5a, D5b, D7, D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 15 (07 HSE).
> Histórias: 120, 124. Bloqueada por: ISSUE-072, ISSUE-019, ISSUE-027.

## O que construir

A tela **Ocorrências** registra, investiga e trata. **Nova ocorrência**: data e
hora, área e local, empresa, tipo, descrição, gravidade real e **potencial**
(matriz 5x5), marcação de **alto potencial (HiPo)**, pessoas envolvidas e
função (sem nome no registro geral), dias perdidos e debitados, comunicação
legal quando aplicável, causa imediata e evidências (anexos). O tipo define o
nível da pirâmide; ocorrência Ambiental tem severidade própria e fica fora
dela.

Fluxo: Registrada, Em investigação, Ações definidas, Em tratamento, Encerrada
(eficácia verificada). Prazos de comunicação, investigação preliminar e
relatório final (LTI e HiPo) vêm dos parâmetros e o **prazo vigente fica
gravado na ocorrência** (D5b). Investigação com método registrado; ações
corretivas pela costura da Central (origem HSE; o link distingue ocorrência de
estudo de risco). **HiPo encerrada gera lição obrigatória** em Rascunho.

**LGPD:** nome e dados médicos ficam em tabela de acesso restrito. Membro
preenche, mas só Gestor e Admin leem esse campo e os anexos com esses dados
(decisão Q35).

## Critérios de aceite

- [ ] O prazo vigente fica gravado, e mudar o parâmetro depois não muda a ocorrência.
- [ ] Fluxo com prazos vencidos sinalizados pela data de hoje.
- [ ] Ações corretivas nascem na Central com link de volta à ocorrência.
- [ ] HiPo encerrada sem lição é recusada.
- [ ] Quem não é Gestor ou Admin não lê o campo restrito nem baixa os anexos com dados pessoais (403).
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (fluxo, prazos, ações, lição e acesso restrito) e de rota (403 no campo e no anexo).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `ocorrencias.html`, `js/pages/hse/ocorrencias.js` e `hse.js`; README, "07 HSE" (classificação, campos, fluxo e privacidade).

## Registro de execução

Fatia entregue em 10/10/2026: a migração `m073` (down `m070`) cria `ocorrencia`,
`ocorrencia_restrito` (um por ocorrência, UK) e `ocorrencia_investigacao` conforme o
`docs/MODELO-DE-DADOS.md` §12 (FKs de projeto, empresa, ocorrência e pessoa; UK de projeto +
código; CHECKs de tipo, situação, subtipo, severidade ambiental, potencial 1–5 e método) e
sobe/desce/sobe num banco vazio; a coluna `data_encerramento` e o texto `eficacia` foram
acrescentados à ocorrência no MODELO §12 na mesma entrega (o protótipo guardava o encerramento
e o diagrama não tinha onde — divergência registrada). A fachada (`service.py`) cobre o fluxo
inteiro: o código `OCR-<padrão da ata do projeto>-NNNN` (4 dígitos, kind novo `ocorrencia` do
núcleo de numeração, pelo maior código do projeto); **os prazos vigentes ficam gravados no
registro** (`prazo_comunicacao_horas` 24, `prazo_investigacao_horas` 48 e `prazo_relatorio_dias`
30, do grupo `hse` dos parâmetros — mudar o parâmetro depois não muda a ocorrência, D5b); o
nome e os dados médicos entram em `ocorrencia_restrito` na **mesma transação** (Membro
preenche); o tipo define o nível da pirâmide (1–4; Ambiental fora dela, com severidade própria,
subtipo e sem gravidade real, potencial, HiPo nem causa imediata); a **investigação** é fato
(método, causa raiz, data e responsável) e move a ocorrência para Em investigação; as **ações
corretivas nascem na Central** pela costura única (origem `HSE`, `origem_ref` o código, grupo
"Ação corretiva", item pela sequência da origem) e o link de volta aponta para `hse/ocorrencias`
com a busca do código (a ISSUE-074 estende para os estudos de risco); o tratamento começa
depois das ações e o **encerramento exige as ações concluídas**, grava a eficácia e, no **HiPo,
exige a lição obrigatória em Rascunho** pela fachada de Governança (`create_draft_lesson`,
origem `ORIGIN_HSE`, `origem_ref` o código — `lessons_service.code_of_origin` novo mostra o
vínculo ao dono sem ler a tabela alheia, D5). A **Q35** é aplicada pela porta de anexos: o tipo
de origem `ocorrencia` devolve `OriginRecord(restricted=True)`, então listar e baixar exige
`ver_restrito` (Gestor e Admin) e quem pode gravar ainda envia; a ficha só mostra o bloco
restrito pela rota própria (`hse/ocorrencias/{codigo}/restrito`, `Access` com `VIEW_RESTRICTED`,
403 aos demais). As rotas novas vivem em `ocorrencias_routes.py` (blueprint
`hse_ocorrencias_bp`: lista, Excel, imprimível, ficha, nova, investigar, ações, tratamento,
encerrar e o restrito), com nomes únicos no app (`occurrence_*`) e os alvos
`ocorrencias-conteudo`/`ocorrencias-modal-corpo`/`ocorrencia-restrito`; o trio da tela
(view/CSS/JS) registra `TN.paginas["hse/ocorrencias"]`. No Portfólio a lista e as exportações
trazem a coluna Projeto e a inclusão pede o projeto antes do formulário. A carga nova
`hse-ocorrencias` (registrada depois de `hse`) traz as 240 ocorrências do projeto 1 do
convertido, com o restrito e as investigações e as datas deslocadas; a numeração continua depois
dos códigos carregados. O oráculo afirma o projeto 1 em 25/09/2026: **240 ocorrências
(177 encerradas, 38 em tratamento, 17 com ações definidas, 1 em investigação e 7 registradas),
63 em aberto, 2 HiPo (1 em aberto), 7 fora do prazo (3 de comunicação e 4 de investigação
vencida), pirâmide 0/16/31/190 com 3 ambientais fora, 233 investigações, o prazo gravado
(24, 48, 30) e o HiPo OCR-TN-2026-0219 Em investigação com a investigação "Árvore de causas" e
as 2 ações de HSE do mock-central**. Divergências registradas: o protótipo contava 8 fora do
prazo porque o mock não guardava o encerramento (o GestNow grava e conta 7); o campo único
área/local (a coluna `local` fica vazia — sem fonte no mock); a investigação da carga tem a
causa raiz sintetizada (o mock só guardava o método). `ruff check`, `ruff format --check` e
`ty check` limpos; a suíte (HSE, Central, Governança, Qualidade, plataforma e oráculo — 1.592
testes) passa; a porta de qualidade, 5/5.

- DECISAO: encerramento da ocorrência | `ocorrencia.data_encerramento` (date) e `ocorrencia.eficacia` (text) acrescentadas ao MODELO §12 na mesma entrega; o relatório final vencido conta pelo encerramento gravado (o protótipo contava 8 porque o mock não guardava o fechamento; o GestNow conta 7) | D5b, ISSUE-073
- DECISAO: prazos gravados | comunicação, investigação preliminar e relatório final entram na ocorrência no registro, do grupo `hse` vigente (24 h, 48 h e 30 dias); mudar o parâmetro depois não muda a ocorrência | D5b, ISSUE-073
- DECISAO: anexos restritos | o tipo de origem `ocorrencia` devolve `OriginRecord(restricted=True)`: listar e baixar exige `ver_restrito` (Gestor e Admin), e quem pode gravar ainda envia; a ficha mostra o bloco restrito pela rota própria com `VIEW_RESTRICTED` (403 aos demais) | Q35, D7, ISSUE-073
- DECISAO: vínculo da lição | `lessons_service.code_of_origin` novo na fachada de Governança: o módulo dono da origem pergunta o código da lição por origem + referência, sem ler a tabela alheia (D5) | D5, D9, ISSUE-073
- DECISAO: campo único área/local | o protótipo tinha um campo único; a coluna textual `local` fica como o MODELO a desenha e não é preenchida nesta fatia (sem fonte no mock) | D5, ISSUE-073

