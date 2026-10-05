---
id: ISSUE-006
title: "Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea"
status: done
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

- [x] Uma falha provocada no meio de uma gravação de dois registros não deixa nenhum dos dois gravado.
- [x] Toda gravação pelas fachadas deixa linha na trilha com antes e depois, na mesma transação.
- [x] Duas gravações concorrentes de numeração recebem números diferentes e consecutivos.
- [x] Gravar com `versao` antiga devolve 409 com o nome de quem gravou e a hora, e o formulário volta com o que foi digitado.
- [x] O tipo de dinheiro guarda centavos e formata em reais só na apresentação.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes na costura de fachada: atomicidade, trilha, sequência concorrente (duas
conexões) e conflito de versão. Teste de rota: 409 com o formulário
preenchido. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedente da trilha: auditoria do app de Programação Semanal. Integrações
entre módulos chamam a fachada do dono, nunca a tabela de outro módulo (D5).

## Registro de execução

- Decisão da execução (ISSUE-006), pendente de revisão do dono: a gravação auditada das fachadas ficou em `api/src/core/recording.py` (`create`, `update` e `delete`), que reúne instantâneo, controle de versão e linha de trilha na mesma transação; a entidade da trilha é o nome da tabela do registro. Fachadas de agregado podem compor `audit.py` e `versioning.py` diretamente, dentro da mesma unidade de trabalho. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-006), pendente de revisão do dono: a trilha é só de inclusão por gatilho no banco (migração `0002_gravacao_segura`), que recusa `UPDATE` e `DELETE` em `auditoria`; os testes provam as duas recusas. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-006), pendente de revisão do dono: a mensagem de conflito lê o autor e a hora da última linha da trilha do registro e apresenta a hora no fuso do produto (`America/Sao_Paulo`, via `zoneinfo`); sem trilha, cai na mensagem genérica "alterada por outra pessoa". A centralização do calendário é da ISSUE-007. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-006), pendente de revisão do dono: os formatos de numeração seguem o protótipo — `ata`, `SM`, `RNC`, `risco`, `punch`, `claim`, `EOT` e `lição` usam o padrão do projeto (`SM-TN-2026-0001`) com quatro dígitos; `pedido` e `contrato` usam o ano com três dígitos (`PED-2026-001`, `CT-2026-001`), como o protótipo imprimia. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-006), pendente de revisão do dono: o decorador único de rota ficou em `api/src/core/routing.py` (`fragment_route`) com gate do Alpine, unidade de trabalho e o mapa 403/409/422, mais o gancho `on_error` que re-renderiza o formulário do módulo no 422 e no 409; a resolução de usuário e a permissão entram de forma aditiva na ISSUE-011. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-006), pendente de revisão do dono: o dinheiro ganhou o tipo `Centavos` (TypeDecorator sobre `bigint`, valores Python em centavos) aplicado a `projeto.orcamento_centavos`, e a formatação em reais ficou em `format_brl` e no filtro Jinja `brl`, só na apresentação. Anotado no Histórico de decisões da spec.
- Verificação: `api/.venv/Scripts/python.exe -m pytest` — 20 testes passaram, incluindo atomicidade (falha no meio desfaz os dois registros), trilha com antes e depois na mesma transação (e desfeita com ela), recusa de `UPDATE` e `DELETE` na trilha, versão antiga recusada com "Ana Souza" e hora, numeração concorrente com duas conexões (a segunda travada até o commit da primeira, depois `0001`/`0002`), número devolvido quando a transação desfaz (sem buraco), formato da numeração e centavos formatados só na apresentação; teste de rota com 409, formulário preenchido com o texto digitado, toast e mensagem com autor e hora (o formulário de teste faz o papel do formulário de um módulo, pelo gancho `on_error`).
- Porta de qualidade: `npm run verificar` passou nas cinco etapas, sem regra desligada (o único ajuste de configuração é o `ARG002` de `src/core/money.py`, com comentário: o `dialect` é contrato do SQLAlchemy e o ty exige o nome do método sobrescrito).
- Divergência com o protótipo: nenhuma; esta issue não porta fórmula e a numeração reproduz o formato do protótipo.
