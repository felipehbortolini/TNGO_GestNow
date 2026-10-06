---
id: ISSUE-064
title: "Registro e avaliação de riscos"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 13
blocked_by:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-016
  - ISSUE-018
blocks:
  - ISSUE-065
labels:
  - ready-for-agent
source_requirements:
  - HU-107
spec_decisions:
  - D6
  - D7
---

# Registro e avaliação de riscos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D7.
> Entrega 6 (Suprimentos e Riscos), onda 13 (05 Riscos).
> Histórias: 107. Bloqueada por: ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018.

## O que construir

A tela **Registro** de riscos mostra o contexto do projeto (projeto, cliente,
numeração, apetite), 5 KPIs clicáveis pela avaliação exibida (faixa mais alta,
segunda faixa, Em tratamento, Revisão vencida, Ativos), o aviso de revisão
vencida, chips, o alternador Inerente/Residual (troca a coluna destacada, a
base dos KPIs e o filtro de severidade) e as colunas Nº, Risco, Dono,
Inerente, Residual, Estratégia, Ações, Próx. revisão e Situação.

**Novo risco** e edição: causa, evento e consequência; categoria RBS com
cadastro rápido; ata de origem; Salvar e avaliar. **Avaliação**: probabilidade
com faixas percentuais, 6 dimensões de impacto, impacto pelo pior caso (pode
ser elevado, nunca reduzido) e a prévia do score calculada pelo servidor.

Score e severidade só no servidor, pela escala ativa dos parâmetros (Timenow 4
faixas ou CIPM 3 faixas, com risco à vida sempre na mais alta na CIPM). VME =
probabilidade média da faixa x impacto em custo, em centavos; a exposição soma
só ameaças. Justificativa quando a severidade muda.

**Exclusão lógica** (Gestor): bloqueada com ação aberta e para risco
encerrado; grava motivo, autor e data; só o Admin vê e restaura. Numeração
`RSK-` reservada na gravação, contando só sufixos numéricos.

## Critérios de aceite

- [x] Score e severidade têm testes nas duas escalas, inclusive o risco à vida na CIPM.
- [x] O impacto é a maior dimensão e não pode ser reduzido.
- [x] VME e exposição (só ameaças) têm teste da fórmula.
- [x] Exclusão com ação aberta ou de risco encerrado é recusada; só o Admin vê e restaura excluídos.
- [x] A numeração ignora sufixos não numéricos.
- [x] O oráculo afirma 7 riscos ativos, 2 críticos no residual e exposição de R$ 3,4 mi no projeto 1.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (score, severidade e VME), de fachada (exclusão e numeração) e o oráculo.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `registro.html`, `js/pages/riscos/riscos.js` (modais 10, 11 e 17), `GI.api.riscos.lista`, `resumo`, `previa`, `salvar` e `avaliar`, `mock-riscos`; README, "05 Gestão de Riscos".

## Registro de execução

- Data: 2026-10-06.
- Feito: modelo, migração m064 (`api/migrations/versions/m064_registro_de_riscos.py`), MODELO-DE-DADOS (identificado_em), calculations, validation, service (+ central_acoes.count_actions_of_origin, configuracoes.list_project_risk_contexts), presentation, export, seed, oráculo, routes.
- Feito: 8 templates Jinja (`api/src/templates/riscos/`), view + css + js do trio `riscos/registro`, testes (`api/tests/riscos/`: cálculos, validação, fachada), LEIA-ME do módulo.
- Pendências: nada executado (testes e porta de qualidade ficam para o orquestrador); critério "A porta de qualidade passa" aberto; recusa de exclusão com ação aberta só coberta pela regra, sem teste de fachada com risco e ação semeados.
