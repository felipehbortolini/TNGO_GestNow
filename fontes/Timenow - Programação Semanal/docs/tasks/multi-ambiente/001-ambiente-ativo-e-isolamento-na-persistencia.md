---
id: ISSUE-001
title: Ambiente ativo por contexto, com base e trilha isoladas e falha fechada
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by: []
blocks:
  - ISSUE-003
  - ISSUE-004
  - ISSUE-005
labels:
  - ready-for-agent
source_requirements:
  - HU-15
  - HU-16
  - HU-17
  - HU-18
  - HU-20
  - HU-21
  - HU-23
  - HU-24
  - HU-68
  - HU-69
  - HU-70
plan_tasks:
  - E1.1
  - E1.3
  - E1.4
  - E1.16 (parcial)
spec_decisions:
  - 7
  - 8
  - 10
  - 14
---

# Ambiente ativo por contexto, com base e trilha isoladas e falha fechada

## O que construir

O dado de cada cliente passa a viver na própria pasta, e o código só alcança
essa pasta dizendo de qual ambiente está falando. O ambiente ativo é um valor
de contexto por requisição — não uma variável de módulo — aberto e fechado por
um gerenciador de contexto que também limpa o estado quando há exceção.

A porta de persistência deixa de ser resolvida uma vez por processo e passa a
ser resolvida por ambiente ativo, com uma instância por ambiente guardada para
sempre — o que se guarda é a **trava**, não o objeto: duas instâncias para o
mesmo ambiente seriam duas travas, e o ciclo ler-modificar-gravar de duas
threads deixaria de ser serializado, fazendo uma gravação sumir em silêncio.
Por isso o guarda não tem expiração nem limite, e o código diz isso por
escrito, para que ninguém o "otimize" depois.

A trilha de auditoria resolve o próprio caminho pelo mesmo contexto e continua
sendo o acréscimo barato de uma linha que nunca lê o conteúdo anterior.

Fora de qualquer ambiente, **os dois levantam**: nunca um ambiente padrão,
nunca um palpite. É a garantia de que uma requisição jamais será respondida
com dado alheio, e é o que torna o teste de isolamento duas linhas.

Esta é também a primeira vez que o projeto tem teste que toca disco: entra a
infraestrutura de teste com diretório temporário, hoje inexistente, e com ela a
matriz de isolamento por agregado e o teste de concorrência.

Nenhuma assinatura da facade de domínio muda, e nem os blueprints, nem os
templates, nem as regras de domínio precisam saber que ambientes existem.

## Critérios de aceite

- [x] Um bloco de ambiente aninhado dentro de outro devolve o ambiente de
      dentro enquanto está dentro e o de fora depois de sair.
- [x] Uma exceção lançada dentro do bloco não deixa o ambiente ativo sujo para
      o próximo uso.
- [x] Pedir a porta de persistência fora de qualquer ambiente levanta.
- [x] Registrar na trilha fora de qualquer ambiente levanta, em vez de escrever
      na raiz do diretório de dados.
- [x] Escrever dentro do ambiente `a` cria a base e a trilha de `a` e não toca
      em nada de `b`.
- [x] Duas chamadas à porta dentro do mesmo ambiente devolvem a **mesma**
      instância; dentro de ambientes diferentes, instâncias diferentes.
- [x] O ponto de troca usado pelos testes aceita a chave do ambiente e afeta
      **somente** aquele ambiente.
- [x] O guarda de instâncias não tem expiração nem limite, e há comentário no
      código explicando que ele existe pela trava e não pelo objeto.
- [x] Os **cinco** agregados — atividade, cadastro de apoio, janela,
      colaborador e parâmetro — escritos no ambiente A estão ausentes no
      ambiente B, com um caso de teste por agregado.
- [x] Duas threads dentro de dois ambientes diferentes ao mesmo tempo escrevem
      e leem cada uma a própria base, sem interferência.
- [x] Os testes rodam em diretório temporário e não tocam a base real.

## Verificação

Suíte de testes nova, rodando sem servidor: aninhamento e limpeza do contexto,
falha fechada nos dois pontos, isolamento por agregado (cinco casos),
concorrência com duas threads e identidade das instâncias por ambiente.

A porta de qualidade das cinco etapas passa (`npm run verificar`).

Nenhum teste afirma em qual pasta o arquivo caiu nem como a chave do guarda foi
montada — o comportamento observável é a ausência do dado de A na consulta de
B, e ele precisa continuar passando se o layout de armazenamento mudar.

## Decisões humanas em aberto

Nenhuma.

## Notas

**A partir desta issue e até a ISSUE-005 a aplicação HTTP não responde.** Todo
endpoint que hoje resolve a porta passa a exigir um ambiente ativo que ainda
não é aberto por requisição. É a única janela vermelha da Entrega 1, é
consciente, e ela fecha na ISSUE-006, quando o seletor entra no boot.

O mecanismo de contexto precisa sobreviver a requisições concorrentes no mesmo
processo — em Azure Functions o handler síncrono roda num pool de threads — e
precisa continuar correto se algum endpoint virar assíncrono no futuro.

O módulo do ambiente ativo não importa nada do núcleo, de propósito: a
persistência e a trilha importam dele, e o caminho inverso criaria ciclo.

O buraco conhecido da trilha em `.jsonl` sobre SharePoint e sobre Azure
Functions **já existe hoje, idêntico**, e não é desta entrega consertá-lo.
