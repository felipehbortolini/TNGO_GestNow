# Gestão de Riscos

Módulo `riscos`. Mantém ameaças e oportunidades, avaliações, respostas, revisões e encerramentos.
Score e severidade são calculados no servidor a partir da escala vigente (ISSUE-064, D6).

## Telas

| Tela | Conteúdo | Issue | Situação |
|---|---|---|---|
| Registro de riscos | Contexto, KPIs, alternador Inerente/Residual, filtros, tabela, avaliação e exclusão lógica | ISSUE-064 | pronta |
| Matriz P x I | Contagem e navegação por probabilidade e impacto | ISSUE-066 | prevista |
| Ficha do risco | Identificação, avaliação, resposta, monitoramento e histórico | ISSUE-065 | prevista |
| Painel de riscos | Exposição, tendência residual e pauta de escalonamento | ISSUE-066 | prevista |

As integrações que chegam de Suprimentos, Contratos, Governança e Financeiro são ligadas na
ISSUE-067.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a
view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view
(`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra
`TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A
verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`,
seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Registro de riscos | `app/_views/riscos/registro.html` | `app/paginas/riscos/registro.css` | `app/paginas/riscos/registro.js` |
| Matriz de riscos 5x5 | `app/_views/riscos/matriz.html` | `app/paginas/riscos/matriz.css` | `app/paginas/riscos/matriz.js` |
| Ficha do risco | `app/_views/riscos/ficha.html` | `app/paginas/riscos/ficha.css` | `app/paginas/riscos/ficha.js` |
| Painel de riscos | `app/_views/riscos/painel.html` | `app/paginas/riscos/painel.css` | `app/paginas/riscos/painel.js` |

O `registro.js` só abre os modais (filtros, categoria, novo/editar, avaliar, excluir) e cuida dos
cinco estados; tudo o que muda a lista é link ou formulário GET com `x-target` no fragmento.

## Rotas (ISSUE-064)

Prefixo: `/api/riscos/`. A tela inteira é um fragmento só, `registro-conteudo`: um KPI, um chip, o
alternador, a página e a busca são o mesmo GET com os filtros na consulta.

| Rota | Uso |
|---|---|
| `GET registro` | A tela: contexto, KPIs, aviso, chips, barra e tabela |
| `GET registro/excel` e `registro/imprimivel` | As duas exportações do filtro aplicado |
| `GET/POST novo` | Novo risco; no Portfólio o projeto é pedido antes |
| `GET/POST {codigo}/editar` | Edição da identificação |
| `GET/POST {codigo}/avaliar` e `GET previa` | Avaliação e a prévia do score |
| `GET/POST {codigo}/excluir` | Exclusão lógica (Gestor) |
| `POST {codigo}/restaurar` | Restauração (Admin) |
| `GET categorias/nova` e `POST categorias` | Cadastro rápido da RBS |

Os formulários abrem em modal (`registro-modal-corpo`); uma recusa (403, 409, 422) volta no
próprio modal com a mensagem ao lado do campo, e o sucesso atualiza a tela atrás dele. O fragmento
`riscos/registro.html` traz um `<template>` com os filtros completos e, depois de "Salvar e
avaliar", um marcador oculto que reabre a avaliação.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Score | Probabilidade multiplicada pelo impacto (1 a 25) | `calculations.risk_score` |
| Severidade | Faixa da escala vigente para o score; risco à vida é sempre a mais alta na CIPM | `calculations.risk_severity` |
| Impacto resultante | Maior das seis dimensões (pior caso); pode ser elevado, nunca reduzido | `calculations.resulting_impact` |
| VME | Probabilidade média da faixa multiplicada pelo impacto em custo, em centavos | `calculations.expected_monetary_value` |
| Exposição | Soma do VME só das ameaças | `calculations.threat_exposure` |
| Cadência de revisão | Dias entre revisões da faixa; a maior quando a faixa não tem valor | `calculations.review_cadence` |
| Numeração | Próximo sufixo numérico do projeto: ``RSK-0001``; sufixos não numéricos não movem a série | `calculations.next_code_number` e `service.reserve_code` |

## Fluxos

Identificado → Em análise → Em tratamento → Monitorado → Materializado ou Encerrado. A avaliação
residual só habilita depois do plano de resposta; para ameaças o residual não supera o inerente e
um score novo exige justificativa. Exclusão lógica é do Gestor, bloqueada com ação aberta e para
risco encerrado, e só o Admin vê e restaura. Aprovar plano é segregado da elaboração (ISSUE-065).

## Integrações

O registro lê as ações da origem `Risco` na Central de Ações (`central_acoes`), usa os projetos,
pessoas e a RBS de Configurações e as atas da Central para a origem "Ata de reunião". Recebe
sugestões do diligenciamento, claims, lições aplicadas e dados de exposição nas ISSUE-067;
somente a fachada dona grava em cada módulo.

## Parâmetros

Escala ativa (Timenow de 4 faixas ou CIPM de 3), probabilidades médias por faixa, cadência de
revisão por faixa, impactos e os dias do alerta de revisão, no grupo Riscos dos parâmetros em
`Configurações > Parâmetros` (ISSUE-076).

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas e templates dos modais | `routes.py`; `api/src/templates/riscos/` |
| Fluxo, exclusão e numeração | `service.py` |
| Score, severidade, VME e exposição | `calculations.py` |
| Validação de identificação/avaliação/exclusão | `validation.py` |
| Exportação (Excel e imprimível) | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` |
| Tela, estilo e comportamento | `app/_views/riscos/` e `app/paginas/riscos/` |
| Testes | `api/tests/riscos/` e `api/tests/oraculo/test_oraculo_riscos.py` |

As ISSUE-065 a ISSUE-067 completam ficha, matriz, painel e as integrações.
