---
id: ISSUE-003
title: Administração do registro por linha de comando, com clonagem enxuta na criação
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-001
  - ISSUE-002
blocks:
  - ISSUE-009
  - ISSUE-012
labels:
  - ready-for-agent
source_requirements:
  - HU-28
  - HU-29
  - HU-30
  - HU-31
  - HU-33
  - HU-35
  - HU-36
  - HU-37
  - HU-38
  - HU-39
  - HU-41
  - HU-45
plan_tasks:
  - E1.13
  - E1.16 (parcial)
  - Documentação transversal — ONDE-ESTA.md
spec_decisions:
  - 12
  - 21
---

# Administração do registro por linha de comando, com clonagem enxuta na criação

## O que construir

O operador passa a criar ambientes, conceder e revogar acesso, arquivar,
desarquivar e listar — tudo por linha de comando, chamando **exatamente as
mesmas funções** que a tela da Entrega 2 vai chamar. A regra nasce e roda antes
de existir tela; a tela depois só desenha.

Criar um ambiente informa identificador, nome do projeto, nome do cliente e,
opcionalmente, um ambiente base do qual herdar configuração. A clonagem é
deliberadamente enxuta:

- **Copiado do ambiente base:** unidades de medida e parâmetros numéricos do
  projeto (metas de aderência e de PPC, regra e limite de justificativa de
  desvio). É o que se repete entre clientes sem pertencer a nenhum — o segundo
  cliente de papel e celulose quer as unidades do primeiro.
- **Nunca copiado:** atividades, realizado, solicitações de governança, trilha
  de auditoria, sequência e contagem de itens por semana, locais, empresas
  contratadas, janelas de programação e cadastro de colaboradores.
- **Vindo do formulário:** identificador, nome do projeto e nome do cliente —
  nunca herdados do base, para não nascer com o nome errado.
- **Criado automaticamente:** quem criou, como administrador do ambiente novo,
  para conseguir concluir a configuração inicial.

Janela fica fora por motivo estrutural: janela é registro por empresa e carrega
as semanas liberadas da obra do cliente base; copiá-la levaria a lista de
fornecedores e o calendário de outro cliente, e produziria janela órfã
apontando para empresa que não existe no cadastro (agora vazio) do ambiente
novo. Colaboradores ficam fora porque copiá-los não é cadastro sujo — é acesso
concedido por engano.

O mapa de onde as coisas estão passa a listar os módulos novos.

## Critérios de aceite

- [x] Dá para criar dois ambientes, conceder acesso a e-mails, listar e revogar
      sem editar nenhum JSON à mão.
- [x] A listagem mostra, por ambiente, cliente, situação e quantidade de
      pessoas com acesso.
- [x] Um ambiente criado a partir de um base nasce com as unidades de medida e
      os parâmetros do base.
- [x] O mesmo ambiente nasce com **zero** atividades, solicitações, eventos de
      trilha, locais, empresas contratadas e janelas.
- [x] O único colaborador do ambiente novo é quem o criou, como administrador.
- [x] O nome do projeto e o nome do cliente do ambiente novo são os informados
      no comando, e não os do base.
- [x] Criar sem informar base produz um ambiente vazio e utilizável.
- [x] Slug inválido ou repetido é recusado com a mensagem da porta, e nenhuma
      pasta fantasma é criada no diretório de dados.
- [x] Arquivar pelo comando tira o ambiente da listagem por e-mail;
      desarquivar devolve.
- [x] `docs/ONDE-ESTA.md` aponta para os módulos e para o script novos.

## Verificação

Executar a sequência completa numa instalação limpa, em diretório temporário:
criar dois ambientes (um com base, um sem), conceder acesso, listar, revogar,
arquivar e desarquivar.

Testes automatizados da clonagem: o que veio, o que **não** veio (um caso por
agregado que não pode ser copiado), a origem dos nomes e o criador como
administrador.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Este é o primeiro entregável de valor observável da Entrega 1: os ambientes
passam a existir e a ser administráveis, ainda sem tela.

O script também serve para preparar demonstração e para consertar o registro
sem editar JSON à mão — onde um slug digitado errado criaria uma pasta fantasma
em silêncio.

Se uma validação precisar existir, ela desce para a porta do registro, não para
o script: a tela da Entrega 2 chama a mesma função e não pode revalidar nada
por conta própria.
