---
id: ISSUE-002
title: "Estrutura modular de pastas com LEIA-ME por módulo, mapa \"quero mudar X, abro Y\", ONDE-ESTA, CONTEXT unificado e ADR da convenção"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 1
onda: 1
blocked_by:
  - ISSUE-001
blocks:
  - ISSUE-003
labels:
  - ready-for-agent
source_requirements:
  - HU-146
  - HU-147
  - HU-153
spec_decisions:
  - D1
  - D3
  - D4
---

# Estrutura modular de pastas com LEIA-ME por módulo, mapa "quero mudar X, abro Y", ONDE-ESTA, CONTEXT unificado e ADR da convenção

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D1, D3, D4.
> Entrega 1 (Fundação documentada), onda 1 (Repositório, estrutura e modelo de dados).
> Histórias: 146, 147, 153. Bloqueada por: ISSUE-001.

## O que construir

Cria a estrutura de todos os módulos antes de qualquer tela, como pede a D4:
uma pasta por módulo em cada camada, com o mesmo identificador em todas
(`inicio`, `central_acoes`, `planejamento`, `programacao_semanal`, `financeiro`,
`suprimentos`, `riscos`, `qualidade`, `hse`, `governanca`, `configuracoes`,
`relatorio`): views, páginas (CSS e JS), módulo do backend, templates e
testes. No backend, cada módulo já tem `routes.py`, `service.py`,
`calculations.py`, `validation.py`, `export.py` e `models.py`, ainda sem
conteúdo além do cabeçalho de propósito, e o `function_app.py` registra o
blueprint de cada um.

Cada módulo ganha o seu `LEIA-ME.md`, escrito para quem nunca viu o código e
não tem IA à mão: o que o módulo faz, as telas que terá (spec e inventário do
protótipo), as rotas previstas, as fórmulas com a definição de negócio e o nome
que terão no código (tradução "termo de negócio para nome no código", por
exemplo score residual para `calculations.residual_score`), os fluxos de
estado, as integrações de entrada e saída, os parâmetros usados e a seção
"Onde mexer". O que depende de código ainda inexistente diz em qual issue
chega, e cada issue de módulo completa o seu LEIA-ME.

Na documentação entram: `docs/MAPA-DE-MODULOS.md` (tabela "quero mudar..." para
texto de tela, layout, estilo, gráfico, fórmula, regra de fluxo, permissão,
parâmetro, exportação, importação, integração entre módulos e tradução,
apontando pasta e arquivo); o `docs/ONDE-ESTA.md` do Padrão reescrito para o
GestNow; o `CONTEXT.md` unificando o glossário do protótipo, o do Padrão e o do
app de Programação Semanal (EAC = Estrutura Analítica de Custos, Projeção no
término, SM, MAS, ROS, VME, FP, CP, PPC, aderência, janela de programação e
afins); e o ADR da convenção de subpastas por módulo, no formato da skill
`domain-modeling`.

A porta de qualidade ganha a checagem `estrutura-dos-modulos`: todo módulo da
lista existe em todas as camadas e tem `LEIA-ME.md`; a falta falha alto.

## Critérios de aceite

- [ ] Os 12 módulos existem nas camadas de view, página, backend, template e teste, com o mesmo identificador.
- [ ] Cada módulo tem `LEIA-ME.md` com: o que faz, telas, rotas, fórmulas (com o nome no código), fluxos, integrações, parâmetros e onde mexer.
- [ ] `docs/MAPA-DE-MODULOS.md` responde "quero mudar X, abro Y" para os 12 tipos de alteração da D4.
- [ ] O `CONTEXT.md` traz o glossário unificado, sem termo com dois sentidos (EAC é sempre Estrutura Analítica de Custos; o indicador é "Projeção no término").
- [ ] O ADR da convenção de subpastas está em `docs/`, e o `ONDE-ESTA.md` aponta para a estrutura nova.
- [ ] A checagem `estrutura-dos-modulos` reprova quando falta o `LEIA-ME.md` de um módulo ou a pasta de uma camada, nomeando o módulo.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Apagar temporariamente o `LEIA-ME.md` de um módulo e rodar `npm run verificar`:
a checagem falha e nomeia o módulo; restaurar e rodar de novo: passa. Seguir
três linhas do `MAPA-DE-MODULOS.md` ao acaso até o arquivo indicado.

## Decisões em aberto

Nenhuma.

## Notas

Árvore-alvo: D4 da spec. Python em inglês; pastas de módulo e rotas em
português (D1). O LEIA-ME é documento vivo: toda issue de módulo atualiza o
seu (definição de pronto).
