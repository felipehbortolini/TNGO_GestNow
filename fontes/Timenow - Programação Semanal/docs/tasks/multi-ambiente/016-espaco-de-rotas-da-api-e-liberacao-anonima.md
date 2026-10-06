---
id: ISSUE-016
title: Espaço de rotas versionado da API, liberado como anônimo na borda e guardado por teste de prefixo
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 3
blocked_by:
  - ISSUE-010
blocks:
  - ISSUE-018
  - ISSUE-022
labels:
  - ready-for-agent
source_requirements:
  - HU-46
  - HU-61
plan_tasks:
  - E3.1
  - E3.7
  - E3.9 (parcial)
  - Documentação transversal — ARCHITECTURE.md
spec_decisions:
  - 22
---

# Espaço de rotas versionado da API, liberado como anônimo na borda e guardado por teste de prefixo

## O que construir

O espaço de rotas próprio e versionado onde a API de leitura vai morar,
separado das rotas de fragmento e **fora do decorador de fragmento** — o gate
do Alpine AJAX e a sessão da borda não se aplicam ali, porque o consumidor não
é o navegador da aplicação. A palavra que distingue o espaço está no caminho de
propósito, para que nenhum endpoint de fragmento caia no espaço sem sessão por
acidente de nome.

E a metade que quebra em produção sem quebrar em desenvolvimento: a
configuração de rotas da borda precisa liberar esse espaço como anônimo, com a
entrada **acima** da entrada geral da API no array. A borda avalia as rotas na
ordem em que aparecem e a primeira que casa vence; colocada abaixo, a entrada
anônima nunca é alcançada e o consumidor leva um redirecionamento para o login
em vez de JSON. Nem o executável local nem o servidor de desenvolvimento
aplicam esse arquivo, então nada disso aparece antes de publicar.

Por isso entra junto o teste que varre as rotas registradas afirmando que
**nenhuma rota de fragmento começa com o prefixo da API**. Ele substitui a
revisão humana de um arquivo de configuração, que não é garantia.

As decisões de arquitetura do projeto passam a registrar a terceira exceção
consciente à hipermídia: JSON para consumidor que não é o navegador da
aplicação, ao lado do health check e do payload dos gráficos.

## Critérios de aceite

- [x] Existe um endpoint no espaço novo que responde **sem** cabeçalho do
      Alpine e **sem** cookie de sessão.
- [x] Nenhuma rota de fragmento existente responde sob o prefixo da API.
- [x] O teste de varredura falha se alguém registrar uma rota de fragmento sob
      o prefixo.
- [x] A entrada anônima está **acima** da entrada geral da API no array da
      configuração de rotas da borda — conferido lendo o arquivo, não de
      memória.
- [x] O espaço é versionado no caminho, e a versão aparece em toda rota nova.
- [x] As decisões de arquitetura citam a exceção de hipermídia.

## Verificação

Teste automatizado de varredura das rotas registradas, afirmando o prefixo.

Leitura do arquivo de configuração de rotas conferindo a posição da entrada
anônima no array.

Depois de publicar, uma requisição sem sessão ao endpoint do espaço novo
devolve JSON e não redirecionamento para o login.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Este é o item que a spec avisa ser **o mais fácil de esquecer e o que quebra a
integração em produção sem quebrar nada em desenvolvimento**. Ele vem primeiro
na Entrega 3 de propósito: o resto da entrega é inútil se o espaço não for
alcançável.

A autenticação por token e os recursos vêm nas ISSUE-017 a ISSUE-019; aqui o
endpoint pode ser o mínimo que prova que o espaço responde.
