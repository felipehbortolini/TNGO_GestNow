---
id: ISSUE-088
title: "Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 18
blocked_by:
  - ISSUE-087
blocks:
  - ISSUE-089
labels:
  - ready-for-agent
source_requirements:
  - HU-017
spec_decisions:
  - D13
---

# Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D13.
> Entrega 9 (Produto final), onda 18 (Idioma).
> Histórias: 17. Bloqueada por: ISSUE-087.

## O que construir

Completa a tradução com o catálogo da parte 1: Planejamento, Programação
Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e o relatório
gerencial, inclusive gráficos, Excel e PDF. Um teste de completude garante que
toda chave usada tem tradução em EN.

## Critérios de aceite

- [ ] Toda chave do catálogo tem tradução em EN (teste de completude).
- [ ] Em EN, nenhuma tela mostra texto de interface em português (dados à parte).
- [ ] O relatório gerencial sai em EN, inclusive Excel e impressão.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste de completude do catálogo e revisão de tela em EN.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: dicionário `en.js` do protótipo; a Programação Semanal, que no app era só em português, ganha as chaves novas.

## Registro de execução

Fatia entregue em 11/10/2026: o catálogo da 087 cobre as **oito áreas restantes** — Planejamento,
Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e o relatório gerencial —
em telas, gráficos, Excel e PDF. O catálogo fechou em **5.768 entradas**: as novas vieram dos
blocos do `en.js` por área (planejamento 853, suprimentos 515, riscos 395, qualidade 327, hse 288,
configurações 174, relatório 234, gráficos 122) e a **Programação Semanal** (349) entrou com
**chaves novas** — o app de origem era só em português — escritas por analogia ao inglês da casa
("Weekly Schedule", "Adherence", "PPC", "Inspector"/"Foreman"). O idioma passou a viajar no
`RequestContext` (resolvido uma vez no `authorize`) e o erro genérico do decorador traduz pelo
`comum`; semana e meses ganharam o idioma (`semana_label`: `S38` → `W38`; `mes_longo`), com a
referência canônica da Programação ("S.30/2026") ficando como identificador; os rótulos do motor
de gráficos foram de 16 para **126 chaves** (motor + todos os visuais usados pelas áreas) e as
séries que passam pelo helper levam `rotulos` no `data-dados`; os KPIs dos cadastros de
Suprimentos são traduzidos no template em vez de threadear o idioma por seis construtores. O
**relatório gerencial** sai em EN inclusive Excel e impressão (título, KPIs por partes, abas,
cabeçalhos e o nome do arquivo). Os `LEIA-ME.md` dos oito módulos ganharam a seção "Idioma
(ISSUE-088)". **Divergências registradas**: os rótulos/KPIs e títulos de gráfico compostos
dentro dos serviços de Riscos, Qualidade, HSE e Suprimentos ficam em PT no inglês, e os KPIs das
exportações fora do relatório não passam pela porta (o resto do documento sai em EN). **Testes**:
a varredura do `test_traducoes.py` cobriu as novas áreas (templates, views, JS, Python e as
constantes `_MESSAGE`/`_NOTICE`) com a completude do catálogo inteiro em EN, e o novo
`test_idioma_nas_areas_2.py` afirma um fragmento representativo de cada uma das oito áreas em EN
e em PT (não-regressão), o relatório gerencial (fragmento + Excel + impressão), o rótulo `W38` e
o dado cadastrado intocado. O subagente rodou o escopo duas vezes (**2.907 passed** em cada); o
principal revisou os diffs, rodou a **suíte completa (4.090 passed**, 19:16) e a porta de
qualidade (**5/5**).

- DECISAO: namespaces das oito áreas | cada área com o seu namespace alimentado pelo bloco do `en.js`; a Programação Semanal com chaves novas (sem fonte no protótipo), por analogia ao inglês da casa | D13, ISSUE-088
- DECISAO: idioma no contexto | `RequestContext.idioma` resolvido uma vez no `authorize`; o erro genérico do decorador traduz pelo `comum` | D13, ISSUE-088
- DECISAO: semana e meses | `semana_label` (S38 → W38) e meses longos no idioma; a referência canônica da Programação ("S.30/2026") fica como identificador | ISSUE-088
- DECISAO: gráficos | `ROTULOS_DO_GRAFICO` estendido aos visuais (126 chaves) e `rotulos` nos `data-dados` das séries que passam pelo helper | ISSUE-014, ISSUE-088
- DECISAO: KPIs de Suprimentos | traduzidos no template (`t('suprimentos', kpi.label)`) em vez de threadear o idioma pelos construtores | ISSUE-088
- DECISAO: limites registrados | os rótulos compostos no serviço (Riscos, Qualidade, HSE e Suprimentos) e os KPIs das exportações fora do relatório ficam em PT no inglês, como divergências registradas | ISSUE-088
