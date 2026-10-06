---
id: ISSUE-017
title: Token de leitura por ambiente — emissão, guarda por hash e ciclo de vida
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 3
blocked_by:
  - ISSUE-002
  - ISSUE-010
blocks:
  - ISSUE-018
  - ISSUE-021
labels:
  - ready-for-agent
source_requirements:
  - HU-47
  - HU-48
  - HU-49
  - HU-50
  - HU-52
  - HU-62
plan_tasks:
  - E3.2
spec_decisions:
  - 24
---

# Token de leitura por ambiente — emissão, guarda por hash e ciclo de vida

## O que construir

Os métodos de token na porta do registro, no lugar que a ISSUE-002 reservou.

O token tem prefixo reconhecível e um segredo aleatório de cerca de 190 bits. O
registro guarda o **prefixo em claro** — rótulo para a tela e índice para a
busca, evitando comparar contra todos os tokens — e o **hash SHA-256 do valor
inteiro**. A verificação localiza pelo prefixo e compara os digests em tempo
constante.

**Sem sal e sem derivação lenta, de propósito, com o porquê escrito no código
para que ninguém "conserte" isso depois.** Token de máquina não é senha de
gente: sal e derivação lenta existem para proteger segredo que humano escolheu e
que cabe num dicionário. Um segredo aleatório desse tamanho não é adivinhável
nem com o hash em mãos, e uma derivação lenta custaria dezenas de milissegundos
em cada chamada do consumidor — mais uma dependência nova — para comprar
segurança que a entropia já deu.

O registro do token conserva rótulo, prefixo visível, ambiente, quem emitiu,
quando, validade opcional e último uso. A emissão devolve o valor completo
**uma única vez**; depois, só o prefixo. Revogar remove a capacidade na
requisição seguinte.

O token é vinculado a **um** ambiente e nunca alcança outro.

## Critérios de aceite

- [x] Emitir um token devolve o valor completo uma vez e o registra vinculado a
      um ambiente.
- [x] O valor completo **não é recuperável** depois da emissão — nem pela porta,
      nem pelo arquivo do registro.
- [x] O arquivo do registro não contém o token em texto puro.
- [x] Verificar um token válido resolve o ambiente dele.
- [x] Token revogado, expirado, malformado e inexistente são recusados, cada um
      com o motivo próprio.
- [x] Um token do ambiente A não resolve o ambiente B, mesmo com o
      identificador de B conhecido.
- [x] A validade é opcional: sem ela o token não expira sozinho; com ela, expira
      na data informada.
- [x] A listagem de tokens de um ambiente traz rótulo, prefixo, quem emitiu,
      quando e último uso — nunca o valor.
- [x] Emissão e revogação aparecem na trilha do registro.
- [x] O comentário no código explica por que não há sal nem derivação lenta.

## Verificação

Testes da porta: emissão, verificação de token válido, os quatro casos de
recusa, o cruzamento entre ambientes, a expiração por validade e a
irrecuperabilidade do valor.

Leitura do arquivo do registro conferindo a ausência do valor em texto puro.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

O token **não carrega identidade de pessoa**, logo o recorte por vínculo de
empresa contratada não se aplica a ele: ele lê o ambiente inteiro. É o risco
aceito nº 3 da spec, e a tela de emissão (ISSUE-021) precisa dizer isso em
palavras.

Escopo de token por empresa contratada está fora desta entrega e é barato de
acrescentar depois, porque o recorte já existe na facade.
