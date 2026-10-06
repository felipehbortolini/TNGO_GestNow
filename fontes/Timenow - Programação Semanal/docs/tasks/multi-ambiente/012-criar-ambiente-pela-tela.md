---
id: ISSUE-012
title: Criar ambiente pela tela, enunciando o que é copiado e o que não é
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 2
blocked_by:
  - ISSUE-003
  - ISSUE-011
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-28
  - HU-29
  - HU-30
  - HU-31
  - HU-32
  - HU-33
  - HU-34
  - HU-41
plan_tasks:
  - E2.3
  - E2.7 (parcial)
spec_decisions:
  - 3
  - 12
---

# Criar ambiente pela tela, enunciando o que é copiado e o que não é

## O que construir

O formulário de criação de ambiente dentro da área do operador: identificador,
nome do projeto, nome do cliente e, opcionalmente, um ambiente base do qual
herdar as unidades de medida do segmento.

Antes da confirmação, a tela **enuncia em palavras** o que será copiado e o que
não será. Copiar configuração de um cliente para outro é decisão consciente e
precisa parecer uma:

- **Copiado:** unidades de medida e parâmetros numéricos do projeto.
- **Não copiado:** atividades, realizado, solicitações de governança, trilha de
  auditoria, locais, empresas contratadas, janelas de programação e cadastro de
  colaboradores.

A tela chama a **mesma função** de criação que o comando de linha já usa: não
revalida slug, não reimplementa a clonagem e não decide nada por conta própria.
Recusa de slug inválido ou repetido aparece com a mensagem que a porta do
registro devolve, e não como erro genérico.

## Critérios de aceite

- [x] Criar pela tela produz **o mesmo resultado** que criar pelo comando, com
      os mesmos dados.
- [x] O enunciado antes da confirmação lista corretamente os dois grupos — o
      que é copiado e o que não é.
- [x] Slug fora do formato é recusado na tela com a mensagem da porta.
- [x] Slug repetido é recusado na tela, inclusive contra ambiente arquivado.
- [x] O ambiente criado nasce com as unidades e os parâmetros do base e com
      zero dado operacional.
- [x] O nome do projeto e o nome do cliente são os do formulário, e não os do
      base.
- [x] Quem criou aparece como administrador do ambiente novo.
- [x] O ambiente novo aparece imediatamente na listagem e no seletor de quem
      tem acesso a ele.
- [x] O identificador não é oferecido para edição depois da criação.
- [x] Nenhuma regra de negócio nova aparece no blueprint da tela.

## Verificação

Criar um ambiente pela tela e outro pelo comando com os mesmos dados e comparar
o resultado — devem ser equivalentes.

Revisão de tela do enunciado antes da confirmação e das duas recusas de slug.

Teste automatizado afirmando que a criação pela tela produz o mesmo resultado
que a criação pelo comando.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Se a tela precisar de uma validação que a porta não tem, a validação desce para
a porta — é o aceite da Entrega 2.
