---
id: ISSUE-021
title: Tela de tokens na área do operador — emitir uma vez, listar e revogar
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 3
blocked_by:
  - ISSUE-011
  - ISSUE-017
blocks:
  - ISSUE-024
labels:
  - ready-for-agent
source_requirements:
  - HU-47
  - HU-48
  - HU-49
  - HU-50
  - HU-51
  - HU-52
plan_tasks:
  - E3.8
spec_decisions:
  - 22
  - 24
---

# Tela de tokens na área do operador — emitir uma vez, listar e revogar

## O que construir

A tela de tokens dentro da área do operador: emitir um token vinculado a um
ambiente, listar os que existem e revogar.

A emissão mostra o valor completo **uma vez** — com o aviso claro de que ele
não será exibido de novo — e depois só o prefixo. Cada token tem um rótulo,
para o operador saber qual integração usa qual, e uma data de validade
opcional, para que uma integração temporária expire sozinha.

A listagem mostra rótulo, prefixo, ambiente, quem emitiu, quando, validade e
**último uso aproximado**, para revogar os que ninguém consome.

E a tela **diz em palavras o que a credencial entrega**: a base daquele cliente
inteira, sem recorte por empresa contratada, porque não há pessoa atrás do
token. Emitir token é, na prática, publicar a base do cliente para quem tiver a
credencial. Essa frase é parte da entrega, não enfeite.

## Critérios de aceite

- [x] Emitir mostra o valor completo uma vez, com o aviso de que ele não será
      exibido de novo.
- [x] Recarregar a tela depois da emissão não mostra o valor em lugar nenhum.
- [x] A listagem mostra rótulo, prefixo, ambiente, quem emitiu, quando,
      validade e último uso aproximado.
- [x] Revogar pela tela faz o token parar de funcionar na requisição seguinte.
- [x] A tela enuncia, antes da emissão, que o token entrega a base inteira
      daquele cliente sem recorte por empresa contratada.
- [x] O rótulo é obrigatório e a validade é opcional.
- [x] A tela é visível apenas ao operador e não existe no DOM de quem não é.
- [x] O fragmento novo não traz `<link>` nem `<script src>` e não cria classe
      visual fora do Design System.

## Verificação

Revisão de tela: emitir, copiar o valor, recarregar e conferir que ele sumiu;
usar o token na API; revogar e conferir que a chamada seguinte é recusada.

Conferência do enunciado sobre o alcance da credencial antes da emissão.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

O enunciado sobre o alcance do token é a compensação do risco aceito nº 3 da
spec — a tela precisa dizer o que a credencial entrega, porque nada no
mecanismo impede o consumidor de ler tudo.
