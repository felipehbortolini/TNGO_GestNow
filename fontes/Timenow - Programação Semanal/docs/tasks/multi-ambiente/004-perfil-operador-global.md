---
id: ISSUE-004
title: Perfil operador vindo da configuração da implantação, com acesso implícito a todo ambiente
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-001
  - ISSUE-002
blocks:
  - ISSUE-005
  - ISSUE-015
labels:
  - ready-for-agent
source_requirements:
  - HU-19
  - HU-41
  - HU-43
plan_tasks:
  - E1.5
  - E1.16 (parcial)
spec_decisions:
  - 2
  - 11
---

# Perfil operador vindo da configuração da implantação, com acesso implícito a todo ambiente

## O que construir

O perfil global que administra o registro de ambientes. Ele vem de uma variável
de ambiente da implantação — e **só dela**. Nenhuma tela promove operador, e
não existe regra de "último operador", porque não existe remoção: trocar quem
opera é trocar a variável e reiniciar.

Três razões para o poder máximo morar fora do dado: numa instalação limpa o
registro nasce vazio e ainda assim precisa existir porta de entrada; um
registro apagado ou corrompido não pode deixar a instalação sem quem a
administre; e um registro comprometido não pode fabricar o papel que enxerga
todos os clientes.

**O operador entra em todo ambiente, implicitamente**, presente e futuro, sem
depender de concessão. Com qual perfil ele entra:

- Se o e-mail já constar no cadastro de colaboradores daquele ambiente, **vale
  o cadastro** — o que permite a um operador que também é fiscal de um projeto
  entrar como fiscal lá.
- Se não constar, entra como administrador, com vínculo Timenow, montado em
  memória e sem ser gravado no cadastro do cliente.

As permissões novas que o papel carrega cobrem administrar o registro,
conceder e revogar acesso, e emitir e revogar token.

A regra das duas camadas continua intacta para todo mundo que não é operador:
um e-mail que consta no registro mas não no cadastro de colaboradores daquele
ambiente **não entra**.

## Critérios de aceite

- [x] Um e-mail listado na variável entra num ambiente onde não é colaborador,
      como administrador e com vínculo Timenow.
- [x] O mesmo e-mail, quando **consta** no cadastro daquele ambiente, entra com
      o perfil do cadastro — e não como administrador.
- [x] Um e-mail fora da variável e fora do cadastro continua não entrando.
- [x] O operador conta na quantidade de pessoas com acesso ao ambiente.
- [x] O operador aparece na listagem de colaboradores do ambiente marcado como
      operador da Timenow, e a listagem não permite removê-lo.
- [x] As permissões de administração do registro pertencem ao operador e a
      nenhum outro perfil.
- [x] A variável vazia ou ausente não quebra a resolução de usuário: apenas não
      há operador.
- [x] O perfil de administrador de um ambiente continua sem enxergar ou tocar
      qualquer outro ambiente.

## Verificação

Testes de resolução de usuário: entrada sem cadastro, entrada com cadastro,
recusa de quem não é nem uma coisa nem outra, contagem de pessoas com acesso
incluindo o operador e a marcação não removível na listagem.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma. A lista de e-mails que ocupa o papel é configuração de implantação,
definida no momento da publicação (ISSUE-010).

## Notas

Este é o risco aceito nº 2 da spec: o administrador do cliente vê que existe
gente da Timenow com acesso e **não pode tirá-la**. A compensação é a
visibilidade — a linha marcada na tela de Colaboradores, que a ISSUE-015
desenha — e a trilha, que registra com o e-mail do operador o que ele fez
dentro do ambiente.

Aqui entra a marcação na resolução e na contagem; a apresentação da linha na
tela de Colaboradores é a ISSUE-015.
