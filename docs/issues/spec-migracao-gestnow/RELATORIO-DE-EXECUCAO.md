# Relatório de execução da migração

> Documento do orquestrador. Uma seção por entrega fechada, na ordem da fila.
> Situações: as issues `done`, as `blocked` com a causa, as divergências
> pendentes de aceite e as decisões da execução pendentes de revisão do dono.

## Entrega 1 — Fundação documentada (ISSUE-001 a ISSUE-004)

**Fechada em:** 05/10/2026.

**O que a entrega trouxe:**

* **ISSUE-001** — repositório `Timenow - GestNow` copiado do Padrão de
  Desenvolvimento e renomeado, sem as telas de exemplo; `run.bat` que cria o
  ambiente Python e sobe o shell local (sem Azure Functions Core Tools);
  referências preservadas em `docs/referencia/` (22 visuais, README/HANDOVER e
  `_dev` do protótipo, documentos do app de Programação Semanal); skills de
  `.agents`/`.claude` copiadas; git local iniciado (Q33), sem remoto; porta de
  qualidade verde.
* **ISSUE-002** — estrutura modular com os 12 módulos nas cinco camadas
  (view, página, backend, template, teste), `LEIA-ME.md` por módulo,
  `docs/MAPA-DE-MODULOS.md` ("quero mudar X, abro Y"), `docs/ONDE-ESTA.md`
  reescrito, `CONTEXT.md` unificado (EAC = Estrutura Analítica de Custos;
  "Projeção no término" para o indicador) e ADR da convenção de subpastas;
  checagem `estrutura-dos-modulos` na porta de qualidade, comprovada por
  verificação negativa.
* **ISSUE-003** — modelo de dados, parte 1 (plataforma, cadastros de apoio, 01
  Central de Ações, 08 Governança e 03 Financeiro) em `docs/MODELO-DE-DADOS.md`,
  com diagramas Mermaid, uma linha de descrição por tabela com o módulo dono,
  exceções da D5b anotadas e tabela de cobertura de 100% das coleções dos mocks
  de base, configuração, Central, Governança e Financeiro (parte da issue no
  portfólio incluída).
* **ISSUE-004** — modelo de dados, parte 2 (02 Planejamento, 02 Programação
  Semanal, 04 Suprimentos, 05 Riscos, 06 Qualidade, 07 HSE, análise do período
  e relatório), completando o diagrama com as ligações entre módulos e a
  cobertura de 100% de todos os mocks (56 coleções distintas) e do repositório
  JSON do app de Programação Semanal (13 chaves e 2 arquivos de trilha);
  `ocorrencia_restrito` como tabela de acesso restrito do HSE (Q35), apontada
  no diagrama.

**Números:** 4 issues `done`, 0 `blocked`; 4 commits locais (um por issue).

**Bloqueios:** nenhum.

**Divergências pendentes de aceite (Q31):** 11 registros em
`docs/DIVERGENCIAS-DO-PROTOTIPO.md` — 6 da ISSUE-003 (valores agregados da EAC,
séries da Curva S financeira, valor do marco de pagamento, reservas, ponderação
da carteira e sessão/referência/escopo) e 5 da ISSUE-004 (séries da Curva S
física, evolução do score residual, lote semanal da Programação Semanal do
protótipo, horizonte do 6WLA e situação das ocorrências de HSE).

**Decisões da execução pendentes de revisão do dono:** 13 registros no
Histórico de decisões da spec — 2 da ISSUE-001, 3 da ISSUE-002, 3 da ISSUE-003
e 5 da ISSUE-004.

**Estado da fila:** ISSUE-001 a ISSUE-004 `done`; a fila continua na entrega 2
(ISSUE-005).
