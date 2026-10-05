---
id: ISSUE-093
title: "Consolidação dentro do GestNow e desativação das pastas de origem"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 20
blocked_by:
  - ISSUE-092
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-157
spec_decisions:
  - D15
---

# Consolidação dentro do GestNow e desativação das pastas de origem

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D15.
> Entrega 9 (Produto final), onda 20 (Consolidação).
> Histórias: 157. Bloqueada por: ISSUE-092.

## O que construir

Fecha a migração. Primeiro, as **pré-condições**: referências copiadas para
`docs/referencia/`, carga de demonstração convertida dentro do GestNow,
oráculo e varredura verdes, porta de qualidade verde. Uma busca confirma que
nenhum arquivo do GestNow aponta para as pastas de origem.

Depois, a **consolidação**: as pastas ocultas de ferramenta da raiz (`.claude`
e `.agents`) e o `skills-lock.json` passam para dentro do `Timenow - GestNow`,
mescladas com as skills do Padrão que já estão lá. Para as skills com o mesmo
nome (grill-me e grilling), fica a versão da raiz (decisão Q34). O README do
GestNow passa a dizer que as sessões de trabalho abrem dentro da pasta do
projeto.

Por fim, a **desativação** (decisão Q32): é a única pergunta da execução, no
último passo, quando nada mais depende dela. Um pop-up pede ao dono a
confirmação explícita para excluir `Sistema`, `Padrao Desenvolvimento`,
`Graficos HTML` e `Timenow - Programação Semanal`. Confirmado, as quatro pastas
são excluídas (no OneDrive, vão para a lixeira, que fica como rede de
segurança), e a raiz termina só com a pasta do projeto. Recusado, nada é
excluído e o roteiro de exclusão fica em `docs/` para o dono executar depois.

## Critérios de aceite

- [ ] Nenhum arquivo do GestNow aponta para as pastas de origem.
- [ ] `.claude`, `.agents` e `skills-lock.json` estão dentro do GestNow, com a versão da raiz para grill-me e grilling.
- [ ] A exclusão só acontece depois da confirmação explícita do dono no pop-up.
- [ ] Depois da confirmação, a raiz tem só `Timenow - GestNow`; sem a confirmação, o roteiro de exclusão está em `docs/`.
- [ ] O app sobe pelo `run.bat` e a porta de qualidade passa depois da consolidação.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Busca por caminhos das pastas de origem dentro do GestNow; `run.bat`; `npm run verificar`; listagem da raiz.

## Decisões em aberto

Nenhuma. A exclusão foi decidida na Q32 (pergunta só no fim) e a versão das skills na Q34 (a da raiz).

## Notas

D15, item 9, e Further Notes da spec ("Desativação das pastas de origem").
