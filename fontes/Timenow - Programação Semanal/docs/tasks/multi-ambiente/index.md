---
source_prd: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
issue_count: 26
status: proposed
---

# Issues — Multi-ambiente, seletor de clientes e API de leitura

Fonte da verdade: [`docs/SPEC-MULTI-AMBIENTE.md`](../../SPEC-MULTI-AMBIENTE.md) —
70 histórias, 27 decisões e os riscos aceitos.
Ordem e critério de pronto: [`docs/PLANO-MULTI-AMBIENTE.md`](../../PLANO-MULTI-AMBIENTE.md) —
35 tarefas.

Se uma issue e a spec discordarem, **a spec vence** e a issue é que está velha.

Este diretório contém **26 issues**: as 22 derivadas das 35 tarefas originais
do plano, mais 4 acrescentadas depois da primeira revisão de tela e do
primeiro consumo real da API (Revisões 3, 4 e 5 da spec). Cada
issue é uma fatia vertical: entrega um comportamento completo e verificável por
conta própria, em vez de uma camada técnica isolada. Onde o plano separava
tarefas que só são observáveis juntas — o contexto e a porta de persistência, o
seletor e o boot, o espaço de rotas e a liberação na borda — elas viraram uma
issue só. Onde o plano concentrava testes numa tarefa única (E1.16), eles foram
distribuídos para dentro da fatia que os torna possíveis: nenhum caso de teste
da spec foi perdido, e o mapa no fim deste arquivo mostra onde cada um caiu.

Para começar a executar, use o prompt de abertura de sessão em
[`PROMPT-INICIO.md`](./PROMPT-INICIO.md) — um bloco por onda, pronto para colar
numa sessão nova.

---

## Registro de issues

| ID | Título | Entrega | Tipo | Situação | Rótulo | Bloqueada por | Arquivo |
|---|---|---|---|---|---|---|---|
| ISSUE-001 | Ambiente ativo por contexto, com base e trilha isoladas e falha fechada | 1 | task | done | ready-for-agent | — | [001](./001-ambiente-ativo-e-isolamento-na-persistencia.md) |
| ISSUE-002 | Registro de ambientes como porta própria, com slug validado e arquivamento reversível | 1 | task | done | ready-for-agent | — | [002](./002-registro-de-ambientes.md) |
| ISSUE-003 | Administração do registro por linha de comando, com clonagem enxuta na criação | 1 | task | done | ready-for-agent | ISSUE-001, ISSUE-002 | [003](./003-script-de-administracao-do-registro.md) |
| ISSUE-004 | Perfil operador vindo da configuração da implantação, com acesso implícito a todo ambiente | 1 | task | done | ready-for-agent | ISSUE-001, ISSUE-002 | [004](./004-perfil-operador-global.md) |
| ISSUE-005 | Costura HTTP do ambiente ativo — resolução por requisição, recusa por redirecionamento e guarda que nomeia a causa | 1 | task | done | ready-for-agent | ISSUE-001, ISSUE-002, ISSUE-004 | [005](./005-costura-http-do-ambiente-ativo.md) |
| ISSUE-006 | Seletor de ambientes depois do SSO, com a escolha recarregando para o destino certo | 1 | task | done | ready-for-agent | ISSUE-005 | [006](./006-seletor-de-ambientes-e-boot.md) |
| ISSUE-007 | Sidebar mostra o ambiente ativo e oferece a troca a quem tem mais de um | 1 | task | done | ready-for-agent | ISSUE-006 | [007](./007-sidebar-com-ambiente-ativo.md) |
| ISSUE-008 | Nome do projeto e do cliente saem dos parâmetros e passam a ter fonte única no registro | 1 | task | done | ready-for-agent | ISSUE-007 | [008](./008-projeto-e-cliente-saem-dos-parametros.md) |
| ISSUE-009 | Modo demonstração com dois ambientes semeados e carga inicial restrita à demonstração | 1 | task | done | ready-for-agent | ISSUE-003, ISSUE-006 | [009](./009-modo-demonstracao-com-dois-ambientes.md) |
| ISSUE-010 | Primeira publicação com SSO real e dois clientes isolados em produção | 1 | task | proposed | ready-for-agent | ISSUE-008, ISSUE-009 | [010](./010-primeira-publicacao-com-sso-real.md) |
| ISSUE-011 | Área do operador dentro do seletor, com a listagem de todos os ambientes | 2 | task | done | ready-for-agent | ISSUE-010 | [011](./011-area-do-operador-e-listagem-de-ambientes.md) |
| ISSUE-012 | Criar ambiente pela tela, enunciando o que é copiado e o que não é | 2 | task | done | ready-for-agent | ISSUE-003, ISSUE-011 | [012](./012-criar-ambiente-pela-tela.md) |
| ISSUE-013 | Membros do ambiente pela tela — conceder, revogar e listar quem tem acesso | 2 | task | done | ready-for-agent | ISSUE-011 | [013](./013-membros-conceder-revogar-listar.md) |
| ISSUE-014 | Arquivar e desarquivar ambiente pela tela, com a mensagem própria para quem está dentro | 2 | task | done | ready-for-agent | ISSUE-011 | [014](./014-arquivar-e-desarquivar-pela-tela.md) |
| ISSUE-015 | Tela de Colaboradores mostra o operador da Timenow como linha marcada e não removível | 2 | task | done | ready-for-agent | ISSUE-004, ISSUE-011 | [015](./015-colaboradores-marca-o-operador.md) |
| ISSUE-016 | Espaço de rotas versionado da API, liberado como anônimo na borda e guardado por teste de prefixo | 3 | task | done | ready-for-agent | ISSUE-010 | [016](./016-espaco-de-rotas-da-api-e-liberacao-anonima.md) |
| ISSUE-017 | Token de leitura por ambiente — emissão, guarda por hash e ciclo de vida | 3 | task | done | ready-for-agent | ISSUE-002, ISSUE-010 | [017](./017-token-de-leitura-modelo-e-guarda.md) |
| ISSUE-018 | Autenticação por token na API, com o ambiente resolvido pela própria credencial | 3 | task | done | ready-for-agent | ISSUE-016, ISSUE-017 | [018](./018-autenticacao-bearer-e-ambiente-pelo-token.md) |
| ISSUE-019 | Os quatro recursos de leitura em JSON, com envelope e semana obrigatória | 3 | task | done | ready-for-agent | ISSUE-018 | [019](./019-quatro-recursos-de-leitura-com-envelope.md) |
| ISSUE-020 | Consumo da API registrado em trilha append-only, com último uso amortizado | 3 | task | done | ready-for-agent | ISSUE-018 | [020](./020-escrita-amortizada-do-consumo-da-api.md) |
| ISSUE-021 | Tela de tokens na área do operador — emitir uma vez, listar e revogar | 3 | task | done | ready-for-agent | ISSUE-011, ISSUE-017 | [021](./021-tela-de-tokens.md) |
| ISSUE-022 | Documentação de produção e contrato da API para o analista do cliente | 3 | task | proposed | ready-for-agent | ISSUE-016, ISSUE-019 | [022](./022-documentacao-de-producao-e-contrato-da-api.md) |
| ISSUE-023 | Cadastrar a pessoa no ambiente passa a ser o ato de conceder acesso, com o registro como índice | 4 | task | done | ready-for-agent | ISSUE-013, ISSUE-015 | [023](./023-pertencimento-com-uma-edicao-so.md) |
| ISSUE-024 | Promover e rebaixar operadores pela área de administração, com a variável de ambiente como piso | 4 | task | done | ready-for-agent | ISSUE-011, ISSUE-021 | [024](./024-promover-operador-pela-tela.md) |
| ISSUE-025 | O seletor vira a tela inicial permanente — toda visita nova começa escolhendo o ambiente | 4 | task | done | ready-for-agent | ISSUE-006, ISSUE-011 | [025](./025-seletor-como-tela-inicial-permanente.md) |
| ISSUE-026 | Recurso /api/dados/v1/geral — as atividades de sempre, com o ambiente repetido em cada linha | 5 | task | done | ready-for-agent | ISSUE-019 | [026](./026-recurso-geral-com-ambiente-por-linha.md) |

---

## Ordem de execução — uma fila só, do começo ao fim

A numeração **é** a ordem de execução. Ela é uma linearização válida do grafo de
dependências: ao chegar em qualquer issue, tudo de que ela precisa já foi
fechado. Executar de 001 a 026 em sequência, sem pular e sem paralelizar, não
deixa nenhuma pendência para trás e cobre 100% do desenvolvimento.

**Regra de execução contínua:** só se avança para a issue seguinte quando todos
os critérios de aceite da atual estão marcados e a porta de qualidade das cinco
etapas passa (`npm run verificar`). Nenhuma issue fica "quase pronta" enquanto a
seguinte começa — é exatamente isso que produziria pendência fora de sequência.

As dez ondas abaixo agrupam a fila em entregáveis de valor. A onda é um ponto
de parada seguro e demonstrável; dentro dela, a ordem das issues é obrigatória.

### Onda 1 — O isolamento existe e está provado · ISSUE-001, ISSUE-002

O ambiente vira contexto de requisição, cada cliente ganha a própria base e a
própria trilha, e o código passa a falhar fechado fora de qualquer ambiente. O
registro global nasce, com slug validado e arquivamento reversível.

**Valor entregue:** a garantia central da entrega — dado de um cliente não
alcança o outro — existe e é verificável por teste automatizado.
**Pronto quando:** os cinco testes de isolamento por agregado, o de
concorrência e os de falha fechada passam.
**Atenção — a janela vermelha começa aqui.** A partir da ISSUE-001 a aplicação
HTTP **não responde**, porque os endpoints ainda não abrem ambiente por
requisição. O sintoma esperado, e correto, é este: a sidebar fica vazia, o
cabeçalho estático da view aparece, e todo fragmento que toca a base falha com
"Não foi possível concluir a operação" — um erro por fragmento da tela. Por
baixo é sempre a mesma exceção, a de que não há ambiente ativo. **Não conserte
isso com um ambiente padrão**: é a decisão 7 da spec, e um padrão silencioso é
exatamente o defeito que a entrega existe para impedir. A janela fecha na
Onda 3, com a ISSUE-006.

### Onda 2 — Ambientes existem e são operáveis · ISSUE-003, ISSUE-004

O operador cria ambientes, concede e revoga acesso, arquiva e lista — por linha
de comando, chamando as mesmas funções que a tela da Entrega 2 vai chamar. A
clonagem enxuta (só unidades e parâmetros) roda aqui. O perfil operador nasce
da configuração da implantação.

**Valor entregue:** um cliente novo do portfólio pode ser aberto sem publicar
outra instalação e sem editar JSON à mão.
**Pronto quando:** dois ambientes criados pelo comando, um deles clonado de
outro, com zero dado operacional herdado.

### Onda 3 — A aplicação volta, agora multi-ambiente · ISSUE-005, ISSUE-006

A costura HTTP resolve o ambiente por requisição, confere cookie contra
cabeçalho, recusa por redirecionamento e nomeia a causa da recusa. O seletor
entra no boot e a escolha recarrega para o destino certo.

**Valor entregue:** a experiência completa do usuário final — entra, escolhe o
cliente, trabalha na base dele.
**Pronto quando:** os cinco casos de recusa recusam, o link direto sobrevive à
primeira escolha, a troca volta à tela inicial e duas abas em ambientes
diferentes não se atropelam. **A janela vermelha fecha aqui.**

### Onda 4 — A tela nunca mente sobre onde você está · ISSUE-007, ISSUE-008

A sidebar mostra o ambiente ativo e oferece a troca; o nome do projeto e do
cliente passam a ter fonte única no registro e somem dos parâmetros.

**Valor entregue:** ninguém lança produção no cliente errado por não saber onde
está, e não há duas moradas para o mesmo nome.
**Pronto quando:** nenhum nome de cliente específico sobra no código, e
sidebar, dashboard, planilha e relatório trazem o nome do ambiente ativo.

### Onda 5 — Demonstrável por duplo clique e publicado com SSO · ISSUE-009, ISSUE-010

O modo demonstração nasce com dois ambientes semeados, a carga fictícia fica
restrita a eles, e a Entrega 1 vai ao ar com o provedor de identidade real.

**Valor entregue:** a Entrega 1 fechada — dois clientes reais na mesma
instalação, sem se enxergarem.
**Pronto quando:** duas pessoas reais em dois ambientes reais trabalham sem se
encontrar em nenhuma tela, e o roteiro de seis passos está registrado com o
resultado de cada um.

### Onda 6 — Administração em tela · ISSUE-011 a ISSUE-015

A área do operador dentro do seletor: listar, criar, conceder, revogar,
arquivar e desarquivar. E a tela de Colaboradores do cliente passa a mostrar o
operador da Timenow, marcado e não removível.

**Valor entregue:** a Entrega 2 fechada — o operador administra a carteira sem
linha de comando.
**Pronto quando:** criar pela tela produz o mesmo resultado que criar pelo
comando, e **nenhuma regra de negócio nova** aparece no blueprint da tela.

### Onda 7 — O dado sai por HTTPS · ISSUE-016 a ISSUE-020

O espaço de rotas versionado, liberado como anônimo na borda e guardado por
teste de prefixo; o token por ambiente; a autenticação; os quatro recursos com
envelope; e o registro amortizado do consumo.

**Valor entregue:** o analista do cliente consome a programação em JSON sem
exportar planilha à mão.
**Pronto quando:** nenhuma rota de escrita existe no espaço de nomes, o teste
do prefixo passa, e cem chamadas seguidas produzem cem linhas de trilha e no
máximo uma reescrita do registro.

### Onda 8 — Emissão e documentação · ISSUE-021, ISSUE-022

A tela de tokens na área do operador e a documentação de produção e do contrato
para o analista.

**Valor entregue:** a Entrega 3 fechada e o escopo completo da spec entregue.
**Pronto quando:** um analista monta a primeira consulta lendo só a
documentação, com um token emitido pela tela.

### Onda 9 — Modelo de acesso da revisão 3 · ISSUE-023, ISSUE-024, ISSUE-025

Acrescentada depois da primeira revisão de tela da Entrega 2, com as três
entregas já implementadas. Cadastrar a pessoa no ambiente passa a ser o ato de
conceder acesso, e a área de administração passa a promover operadores com a
variável de ambiente como piso.

**Valor entregue:** uma edição só por pessoa nova, e a troca de quem administra
a carteira sem reiniciar a instalação.
O seletor também deixa de ser um passo de primeira visita e vira a tela
inicial permanente: toda visita nova escolhe o ambiente, inclusive quem tem um
só.

**Pronto quando:** cadastrar alguém num ambiente faz aquele ambiente aparecer
no seletor dela sem nenhum passo na área do operador; um operador da variável
não pode ser rebaixado pela tela; e abrir uma aba nova cai no seletor sem que a
escolha entre em laço.

---

### Onda 10 — Recurso geral da API, para combinar ambientes fora do sistema · ISSUE-026

Acrescentada consumindo a API pela primeira vez de verdade: `/geral` devolve
as mesmas linhas de `/atividades`, com o ambiente repetido em cada uma, para
quem combina respostas de vários tokens numa tabela só (Power BI, data
warehouse). O token continua vinculado a um ambiente — nada muda no acesso.

**Valor entregue:** combinar dois ambientes numa consulta sem adicionar
coluna de origem à mão.
**Pronto quando:** duas chamadas a `/geral` com tokens de ambientes
diferentes, combinadas, produzem uma tabela onde cada linha aponta para o
ambiente certo.

---

## Grafo de dependências

```
Onda 1   001 ──┬─► 003 ──┬────────────────────────────────► 012
         002 ──┤         │
Onda 2         └─► 004 ──┼─► 005 ─► 006 ─► 007 ─► 008 ──┐
                         │            └──► 009 ─────────┴─► 010
Onda 6                                                      010 ─► 011 ─┬─► 012
                                                                        ├─► 013
                                                                        ├─► 014
                                                                        ├─► 015   (também depende de 004)
                                                                        └─► 021
Onda 7                                                      010 ─► 016 ─┬─► 018 ─┬─► 019 ─► 022
                                                            002 ─► 017 ─┘        └─► 020
                                                                        016 ─────────────► 022
                                                                        017 ─────────────► 021
```

**Quatro issues destravam quase tudo:** ISSUE-001, ISSUE-002, ISSUE-005 e
ISSUE-011. Enquanto elas não fecharem, o que vem depois fica esperando.

---

## Mapa: tarefa do plano → issue

As 35 tarefas do plano estão todas cobertas.

| Tarefa do plano | Issue |
|---|---|
| E1.1, E1.3, E1.4 | ISSUE-001 |
| E1.2 | ISSUE-002 |
| E1.5 | ISSUE-004 |
| E1.6, E1.7, E1.8 | ISSUE-005 |
| E1.9, E1.10 | ISSUE-006 |
| E1.11 | ISSUE-007 |
| E1.12 | ISSUE-008 |
| E1.13 | ISSUE-003 |
| E1.14, E1.15 | ISSUE-009 |
| E1.16 | distribuída: ISSUE-001 (infra de teste com disco, isolamento por agregado, concorrência, falha fechada), ISSUE-002 (registro), ISSUE-005 (ambiente ativo), ISSUE-004 (operador), ISSUE-003 (clonagem), ISSUE-009 (carga inicial) |
| E1.17 | ISSUE-010 |
| E2.1, E2.2 | ISSUE-011 |
| E2.3 | ISSUE-012 |
| E2.4 | ISSUE-013 |
| E2.5 | ISSUE-014 |
| E2.6 | ISSUE-015 |
| E2.7 | distribuída: ISSUE-012, ISSUE-013, ISSUE-014 |
| E3.1, E3.7 | ISSUE-016 |
| E3.2 | ISSUE-017 |
| E3.3 | ISSUE-018 |
| E3.4, E3.5 | ISSUE-019 |
| E3.6 | ISSUE-020 |
| E3.8 | ISSUE-021 |
| E3.9 | distribuída: ISSUE-016, ISSUE-018, ISSUE-019 |
| E3.10 | ISSUE-022 |
| Doc — CONTEXT.md (glossário) | ISSUE-002 |
| Doc — ARCHITECTURE.md (decisões) | ISSUE-005 e ISSUE-016 |
| Doc — ONDE-ESTA.md | ISSUE-003 |
| Doc — README.md | ISSUE-009 |

---

## Definição de pronto — vale para toda issue

Em cima dos critérios de aceite de cada uma:

1. As cinco etapas da porta de qualidade passam: lint e formatação do Python,
   verificação de tipos, testes de domínio, lint de JS/CSS/HTML e o verificador
   do padrão Timenow (`npm run verificar`).
2. Nenhuma supressão solta de regra. Falso positivo estrutural se resolve na
   configuração, com comentário explicando.
3. Fragmento novo não traz `<link>` nem `<script src>` — contrato visual.
4. Classe visual nova, se houver, nasce no Design System e em um só dos três
   CSS.
5. Decisão que contraria o que está escrito na spec é anotada **na spec antes**
   de ser codificada, não depois.
