---
id: ISSUE-002
title: Registro de ambientes como porta própria, com slug validado e arquivamento reversível
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
  - ISSUE-017
labels:
  - ready-for-agent
source_requirements:
  - HU-27
  - HU-28
  - HU-34
  - HU-38
  - HU-39
  - HU-42
  - HU-65
plan_tasks:
  - E1.2
  - E1.16 (parcial)
  - Documentação transversal — CONTEXT.md
spec_decisions:
  - 3
  - 4
  - 13
  - 14
  - 15
---

# Registro de ambientes como porta própria, com slug validado e arquivamento reversível

## O que construir

O cadastro global que existe acima de todos os clientes: quais ambientes
existem, quem pode entrar em cada um, e qual é o nome do projeto e do cliente
de cada um. Ele mora na raiz do diretório de dados, ao lado das pastas dos
ambientes e nunca dentro de nenhuma delas.

É uma **porta própria**, irmã da porta de persistência e não parte dela: a
porta de persistência é por ambiente, e pedir a um ambiente a lista de
ambientes inverteria a hierarquia. Fica atrás de porta — em vez de um módulo
lendo o arquivo direto — porque trocar a tecnologia de persistência precisa
continuar sendo uma variável de ambiente.

Interface estreita: listar os ambientes de um e-mail, obter um ambiente, criar,
arquivar, desarquivar, conceder acesso, revogar acesso e listar membros. Os
métodos de token ficam para a Entrega 3 e a interface reserva o lugar deles.

A implementação em JSON usa a mesma escrita atômica (arquivo temporário e
renomeação) e a mesma trava da persistência que já existe, porque é o que
sustenta o modo em rede.

O identificador do ambiente é um slug curto (`^[a-z0-9-]{2,32}$`), digitado no
formulário e não derivado do nome do cliente. Ele é **imutável** depois de
criado e **nunca reaproveitado** depois de arquivado — ele vaza para o nome da
pasta, o cookie, o cabeçalho, o prefixo das listas do SharePoint, a chave do
guarda de instâncias, o envelope da API e a trilha do registro.

Arquivar é **estado, não exclusão**: some do seletor, nada é apagado, e
desarquivar devolve tudo.

O registro é dono do nome do projeto e do cliente — uma fonte só, para que o
seletor nunca discorde da sidebar.

Toda criação, arquivamento, concessão e revogação vira evento na **trilha
própria do registro**, separada da trilha de cada ambiente.

O glossário do domínio ganha os termos que esta issue traz: Ambiente, Registro
de ambientes, Ambiente ativo, Membro do ambiente, Operador e Seletor.
"Ambiente" entra com a definição explícita, e a documentação de infraestrutura
passa a dizer "implantação" quando falar da outra coisa.

## Critérios de aceite

- [x] Criar um ambiente informando identificador, nome do projeto e nome do
      cliente resulta num ambiente ativo listável.
- [x] Listar por e-mail devolve **só os ativos** onde a pessoa é membro.
- [x] Um e-mail sem pertencimento nenhum recebe lista vazia, e não erro.
- [x] Slug fora do formato é recusado com mensagem própria.
- [x] Slug repetido é recusado, **inclusive** contra um ambiente arquivado.
- [x] Conceder acesso põe o e-mail entre os membros; revogar o tira, e a
      listagem seguinte já reflete a mudança.
- [x] Arquivar tira o ambiente da listagem por e-mail sem apagar nada;
      desarquivar devolve o ambiente e os membros como estavam.
- [x] O identificador não pode ser alterado depois da criação.
- [x] Criação, arquivamento, desarquivamento, concessão e revogação aparecem na
      trilha do registro, com quem fez e quando.
- [x] O arquivo do registro fica na raiz do diretório de dados, nunca dentro da
      pasta de um ambiente.
- [x] Uma gravação interrompida não deixa o registro pela metade.
- [x] O glossário do domínio traz os termos novos, com "ambiente" definido
      explicitamente.

## Verificação

Testes da porta do registro em diretório temporário: listagem por e-mail
(ativos, não-membro, arquivado), recusa de slug inválido e repetido,
arquivamento reversível, e a trilha recebendo um evento por operação.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

O registro deve ser modelado de forma a aceitar, depois e sem reescrita, uma
origem de pertencimento vinda de grupo do provedor de identidade — a
sincronização em si está fora do escopo desta entrega.

O nome do projeto e do cliente **saem** dos parâmetros do ambiente; a remoção
dos campos e o reapontamento dos leitores são feitos na ISSUE-008, quando já
existe tela lendo o registro.
