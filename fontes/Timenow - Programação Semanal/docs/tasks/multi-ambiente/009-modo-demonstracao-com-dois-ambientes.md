---
id: ISSUE-009
title: Modo demonstração com dois ambientes semeados e carga inicial restrita à demonstração
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-003
  - ISSUE-006
blocks:
  - ISSUE-010
labels:
  - ready-for-agent
source_requirements:
  - HU-66
  - HU-67
plan_tasks:
  - E1.14
  - E1.15
  - E1.16 (parcial)
  - Documentação transversal — README.md
spec_decisions:
  - 20
---

# Modo demonstração com dois ambientes semeados e carga inicial restrita à demonstração

## O que construir

O modo demonstração — o duplo clique que roda a aplicação sem provedor de
identidade — precisa continuar funcionando, e ele **não sobrevive sozinho** a
esta entrega: a identidade de hoje é resolvida lendo o cadastro de
colaboradores, que passou a viver dentro de um ambiente, e o seletor roda antes
de qualquer ambiente existir.

A identidade fixa e sempre operadora **já veio na ISSUE-005**, junto do
decorador que a exige — sem ela o seletor não seria verificável localmente. O
que falta aqui é o resto: o registro passa a **nascer com dois ambientes
semeados**, cada um com o histórico determinístico de sempre, e o seletor de
perfil da sidebar continua trocando o papel **dentro** do ambiente escolhido.

Isto substitui a preparação manual pelo comando da ISSUE-003, que é como as
ISSUE-006 a ISSUE-008 foram revisadas: a partir daqui o duplo clique numa pasta
limpa já abre com dois ambientes, sem nenhum passo prévio.

Dois ambientes e não um: a troca de ambiente é a tela mais nova da entrega, e
com um ambiente só ela seria a única que ninguém consegue ver antes de
publicar.

E a semeadura do histórico fictício passa a valer **apenas** para a
demonstração. Um ambiente criado em produção nasce com a configuração clonada e
**zero** atividades — nunca com atividade fictícia, que num cliente real é dado
falso na tela de planejamento.

O texto de instalação e uso passa a descrever o boot novo: o duplo clique agora
abre um seletor com duas caixas.

## Critérios de aceite

- [x] O duplo clique no atalho de execução abre o seletor com duas caixas.
- [x] Entrar em qualquer uma delas mostra a base daquele ambiente, com o
      histórico determinístico.
- [x] Trocar entre os dois ambientes funciona pela sidebar.
- [x] O seletor de perfil continua trocando o papel dentro de cada ambiente.
- [x] Um ambiente criado fora do modo demonstração nasce com **zero**
      atividades.
- [x] Um ambiente de demonstração continua nascendo com o histórico completo.
- [x] A identidade fixa da demonstração, herdada da ISSUE-005, continua sempre
      operadora e não depende de nenhum cadastro de colaboradores existir antes.
- [x] Uma pasta limpa, sem nenhum comando prévio, abre com os dois ambientes.
- [x] A documentação de uso descreve o boot com o seletor.

## Verificação

Duplo clique numa cópia limpa da pasta, com o diretório de dados vazio: o
seletor abre com duas caixas, entra-se em cada uma, troca-se entre elas e o
seletor de perfil funciona dentro de cada uma.

Teste automatizado afirmando que um ambiente criado com o modo de produção
nasce sem atividades e que um ambiente de demonstração nasce com o histórico.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

A restrição da semeadura é uma condição no ponto onde o histórico é gerado, não
um refatoramento: esse ponto tem um único chamador.

Esta issue é o que torna a Entrega 1 revisável sem publicar — e é o ensaio do
roteiro que a ISSUE-010 vai repetir contra o SSO real.
