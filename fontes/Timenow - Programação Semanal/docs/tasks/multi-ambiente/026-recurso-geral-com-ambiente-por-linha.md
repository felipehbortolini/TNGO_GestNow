---
id: ISSUE-026
title: Recurso /api/dados/v1/geral — as atividades de sempre, com o ambiente repetido em cada linha
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 5
blocked_by:
  - ISSUE-019
blocks: []
labels:
  - ready-for-agent
source_requirements: []
spec_decisions:
  - 22
  - 23
  - "Revisão 4"
  - "Revisão 5"
---

# Recurso /api/dados/v1/geral — as atividades de sempre, com o ambiente repetido em cada linha

## O que construir

Um quinto recurso de leitura, ao lado dos quatro que já existem:
`/api/dados/v1/geral`.

**As linhas são as mesmas de `/atividades`** — item, ID exclusiva, atividade,
local, empresa, encarregado, fiscal, unidade, previsto por dia, realizado por
dia e noite, situação, aprovação do realizado e PPC — vindas da mesma função
de domínio (`dados.listar_atividades` com semana, ou
`dados.listar_todas_atividades` sem semana, exatamente como `/atividades`
resolve desde a Revisão 4). Os mesmos filtros continuam valendo: `semana`
(opcional), `empresa`, `local`, `situacao`.

**A diferença é só isto:** cada linha ganha três campos a mais —
`ambiente_id`, `ambiente_projeto`, `ambiente_cliente` — com os mesmos valores
que já aparecem uma vez no envelope de toda resposta da API. O prefixo
`ambiente_` evita colidir com qualquer campo existente da atividade (nenhum
campo hoje começa com esse prefixo — conferido contra a lista completa de
campos de `/atividades`).

**Por que um recurso novo, e não um parâmetro em `/atividades`:** ver
Revisão 5 na spec. Resumindo — são dois públicos diferentes (um ambiente por
vez, ou vários combinados do lado de fora), e um caminho próprio aparece
sozinho ao listar os recursos; uma flag de query string não.

**O que não muda:** o token continua vinculado a um ambiente só (decisão 22).
`geral` não lê mais de um ambiente por chamada — resolve a coluna que falta
quando o consumidor combina **várias respostas de tokens diferentes** do lado
de fora, não cria nenhum acesso cruzado. Nenhum cálculo é reimplementado: as
linhas vêm das mesmas funções de domínio que `/atividades` já usa.

## Onde tocar

- `api/src/blueprints/dados_api.py` — a rota nova (`@bp.route(route="dados/v1/geral")`,
  decorada com `@com_token`, mesma forma de `recurso_atividades`). Reaproveita
  `_semana_pedida`, os mesmos três filtros e `dados.listar_atividades` /
  `dados.listar_todas_atividades`. A única lógica nova é acrescentar os três
  campos de ambiente a cada dicionário de atividade antes de montar o envelope
  — não precisa de função de domínio nova, é uma transformação da camada da
  API, como o `/resumo` sem semana já faz hoje.
- `api/tests/test_ambientes.py` — os testes descritos abaixo.
- `docs/ARCHITECTURE.md` ou onde o contrato da API estiver documentado
  (ISSUE-022, se já existir por lá) — acrescentar `geral` à lista de recursos.

Não toca `dados.py`, `registro.py`, nem nenhum blueprint de tela. O espaço de
rotas (`/api/dados/v1/*`), a guarda do token e o envelope não mudam de forma.

## Critérios de aceite

- [x] `/api/dados/v1/geral` responde com token válido, dentro do ambiente do
      token.
- [x] Cada linha traz todos os campos que `/atividades` já traz, mais
      `ambiente_id`, `ambiente_projeto` e `ambiente_cliente`.
- [x] Os três campos de ambiente são **iguais em todas as linhas** de uma
      mesma resposta, e iguais ao `ambiente` do envelope daquela resposta.
- [x] Sem `semana`, devolve todas as atividades de todas as semanas do
      ambiente (mesmo comportamento de `/atividades` pós-Revisão 4).
- [x] Com `semana`, filtra para aquela semana só.
- [x] Os filtros `empresa`, `local` e `situacao` continuam restringindo.
- [x] Um token do ambiente A nunca traz `ambiente_id` de outro ambiente —
      óbvio pela guarda do token, mas precisa de teste próprio porque é
      exatamente o defeito mais caro possível aqui.
- [x] **Nenhum verbo de escrita** é registrado sob este recurso — continua
      coberto pelo teste de varredura que já existe para o espaço de nomes.
- [x] O envelope da resposta (`ambiente`, `gerado_em`, `dados`) continua no
      mesmo formato dos outros recursos.
- [x] Nenhum cálculo de domínio é reimplementado nesta rota.

## Verificação

Testes automatizados, ao lado dos que já cobrem `/atividades`:

1. Resposta com token válido traz o envelope e as linhas com os três campos de
   ambiente presentes e corretos.
2. Os valores de `ambiente_id`/`ambiente_projeto`/`ambiente_cliente` batem com
   o `ambiente` do envelope, em toda linha.
3. Sem `semana`, o total de linhas bate com `/atividades` sem `semana` no
   mesmo ambiente (mesma fonte de dados, só a coluna extra muda).
4. Filtro `empresa` restringe igual a `/atividades`.
5. Dois ambientes, dois tokens: a chamada de cada um só traz o próprio
   `ambiente_id`.

Verificação manual, o cenário que motivou o recurso: emitir tokens de dois
ambientes de demonstração, montar duas chamadas a `/geral` no Power Query e
`Table.Combine` as duas — a tabela resultante distingue as linhas de cada
ambiente pela coluna nova, sem nenhuma coluna adicionada à mão na consulta M.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma. A forma do recurso (linhas de `/atividades` + três colunas de
ambiente, caminho próprio em vez de parâmetro) já foi decidida — ver
**Revisão 5** na spec.

## Notas

Este recurso é uma transformação fina sobre o que `/atividades` já faz —
não introduz cálculo, não introduz um jeito novo de autenticar, não muda o
que o token alcança. O nome `geral` descreve o formato da resposta (uma
tabela pronta para combinar entre ambientes), não um novo nível de acesso.

Exemplo de uso no Power Query, combinando dois ambientes numa tabela só:

```m
let
  Buscar = (token as text) =>
    Table.FromRecords(
      Json.Document(
        Web.Contents("http://SEU-ENDERECO/api/dados/v1/geral",
          [Headers=[Authorization="Bearer " & token]])
      )[dados]
    ),
  McCain = Buscar("tn_TOKEN_DO_AMBIENTE_A"),
  Suzano = Buscar("tn_TOKEN_DO_AMBIENTE_B"),
  Combinado = Table.Combine({McCain, Suzano})
in
  Combinado
```

Cada linha de `Combinado` já sabe de qual ambiente veio, sem nenhum passo
extra na consulta.
