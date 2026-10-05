---
id: ISSUE-006
title: "Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 2
blocked_by:
  - ISSUE-005
blocks:
  - ISSUE-008
  - ISSUE-013
labels:
  - ready-for-agent
source_requirements:
  - HU-028
  - HU-029
  - HU-030
  - HU-031
spec_decisions:
  - D5
  - D5b
  - D14
---

# Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5, D5b, D14.
> Entrega 2 (Plataforma no ar), onda 2 (Dados).
> Histórias: 28, 29, 30, 31. Bloqueada por: ISSUE-005.

## O que construir

Toda gravação passa a abrir uma transação por requisição (unidade de
trabalho): a fachada de cada módulo recebe a sessão, e tudo o que acontece numa
requisição, inclusive as integrações entre módulos, grava junto ou não grava.

A trilha de auditoria é uma tabela só de inclusão, gravada na mesma transação
da mudança, com quem, quando, o quê, antes e depois, como a trilha do app de
Programação Semanal. Não existe rota nem função que altere ou apague uma linha
dela.

A numeração por projeto (ata, SM, RNC, risco, punch, claim, EOT, lição, pedido,
contrato) usa uma tabela de sequência com trava de linha: duas gravações ao
mesmo tempo nunca recebem o mesmo número, e não sobra buraco por concorrência.
O formato segue o padrão do projeto no protótipo (por exemplo,
`SM-TN-2026-0001`).

O controle de edição simultânea vale para todo registro editável: a tela envia
a `versao` que abriu; se outra pessoa gravou antes, a gravação é recusada com
409 e a mensagem "Este registro foi alterado por <nome> às <hora>. Recarregue
para ver a versão atual", e o formulário volta preenchido com o que a pessoa
digitou. O decorador único de rota trata o 409 como trata o 422.

Valores financeiros ganham um tipo próprio em centavos, formatado em reais só
na apresentação.

## Critérios de aceite

- [ ] Uma falha provocada no meio de uma gravação de dois registros não deixa nenhum dos dois gravado.
- [ ] Toda gravação pelas fachadas deixa linha na trilha com antes e depois, na mesma transação.
- [ ] Duas gravações concorrentes de numeração recebem números diferentes e consecutivos.
- [ ] Gravar com `versao` antiga devolve 409 com o nome de quem gravou e a hora, e o formulário volta com o que foi digitado.
- [ ] O tipo de dinheiro guarda centavos e formata em reais só na apresentação.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes na costura de fachada: atomicidade, trilha, sequência concorrente (duas
conexões) e conflito de versão. Teste de rota: 409 com o formulário
preenchido. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedente da trilha: auditoria do app de Programação Semanal. Integrações
entre módulos chamam a fachada do dono, nunca a tabela de outro módulo (D5).
