# Gestão de Riscos

Módulo `riscos`. Mantém ameaças e oportunidades, avaliações, respostas, revisões e encerramentos.
Score e severidade são calculados no servidor a partir da escala vigente (ISSUE-064, D6); o plano
de resposta, as revisões, o encerramento e a reabertura vivem na ficha (ISSUE-065); a matriz P x I
e o painel de exposição, evolução e pauta de escalonamento vivem na ISSUE-066; as integrações que
chegam dos outros módulos (diligenciamento, claim, lição aplicada e cobertura da contingência)
foram ligadas na ISSUE-067.

## Telas

| Tela | Conteúdo | Issue | Situação |
|---|---|---|---|
| Registro de riscos | Contexto, KPIs, alternador Inerente/Residual, filtros, tabela, avaliação e exclusão lógica | ISSUE-064 | pronta |
| Matriz P x I | Mapa 5x5 inerente e residual, legenda pelas faixas e movimentação inerente-residual | ISSUE-066 | pronta |
| Ficha do risco | Alertas, faixa com inerente e residual, plano de resposta, ações, claims vinculados, revisões, encerramento, reabertura e histórico | ISSUE-065 | pronta |
| Painel de riscos | KPIs, exposição por categoria da RBS, evolução mensal do score residual e pauta de escalonamento com envio ao gerente | ISSUE-066 | pronta |

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

A ficha é **tela de detalhe** (`detalhe_de: riscos/registro`): não tem aba na barra lateral e o
Voltar leva ao Registro. Ela abre por `?codigo=RSK-...`, o mesmo parâmetro que o registro usa em
`_record_link`; o conteúdo é o fragmento `ficha-conteudo`, carregado pela view e atualizado por
cada gravação dos modais. O `registro.js` só abre os modais do registro e cuida dos cinco estados.

## Rotas

Prefixo: `/api/riscos/`. No registro, a tela inteira é um fragmento só, `registro-conteudo`.
Na ficha, a tela é `ficha-conteudo` e cada modal é um formulário do servidor (`ficha-modal-corpo`).

| Rota | Uso |
|---|---|
| `GET registro` | A tela do registro: contexto, KPIs, aviso, chips, barra e tabela |
| `GET registro/excel` e `registro/imprimivel` | As duas exportações do filtro aplicado |
| `GET/POST novo` | Novo risco; no Portfólio o projeto é pedido antes |
| `GET/POST {codigo}/editar` | Edição da identificação |
| `GET/POST {codigo}/avaliar` e `GET previa` | Avaliação e a prévia do score |
| `GET/POST {codigo}/excluir` | Exclusão lógica (Gestor) |
| `POST {codigo}/restaurar` | Restauração (Admin) |
| `GET categorias/nova` e `POST categorias` | Cadastro rápido da RBS |
| `GET ficha` | A ficha: alertas, faixa, botões e as cinco abas |
| `GET ficha/excel` e `ficha/imprimivel` | As duas exportações da ficha (ISSUE-065) |
| `GET/POST {codigo}/ficha/editar` e `{codigo}/ficha/avaliar` | Identificação e avaliação, respondidas na ficha |
| `GET/POST {codigo}/plano` | Plano de resposta |
| `GET/POST {codigo}/plano/aprovacao` | Aprovação da gerência (Gestor; o responsável pelo plano não aprova) |
| `GET/POST {codigo}/acoes` | Ação de mitigação, pela costura da Central (origem Risco) |
| `GET/POST {codigo}/revisoes` | Revisão periódica |
| `GET/POST {codigo}/encerramento` | Encerramento (Gestor) |
| `GET/POST {codigo}/reabertura` | Reabertura (Gestor) |
| `GET matriz` e `matriz/excel`/`matriz/imprimivel` | A matriz P x I e as duas exportações (ISSUE-066) |
| `GET painel` e `painel/excel`/`painel/imprimivel` | O painel e as duas exportações (ISSUE-066) |
| `GET/POST painel/pauta` | O modal do envio da pauta ao gerente e o envio (ISSUE-066) |

Os formulários abrem em modal; uma recusa (403, 409, 422) volta no próprio modal com a mensagem ao
lado do campo, e o sucesso atualiza a ficha atrás dele. O fragmento do registro traz um `<template>`
com os filtros completos e, depois de "Salvar e avaliar", um marcador oculto que reabre a avaliação;
o da ficha usa o mesmo marcador para reabrir a avaliação, o encerramento de um risco materializado
ou a próxima ação de "Salvar e nova".

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Score | Probabilidade multiplicada pelo impacto (1 a 25) | `calculations.risk_score` |
| Severidade | Faixa da escala vigente para o score; risco à vida é sempre a mais alta na CIPM | `calculations.risk_severity` |
| Impacto resultante | Maior das seis dimensões (pior caso); pode ser elevado, nunca reduzido | `calculations.resulting_impact` |
| VME | Probabilidade média da faixa multiplicada pelo impacto em custo, em centavos | `calculations.expected_monetary_value` |
| Exposição | Soma do VME só das ameaças | `calculations.threat_exposure` |
| Cadência de revisão | Dias entre revisões da faixa; a maior quando a faixa não tem valor | `calculations.review_cadence` |
| Limite da próxima revisão | Data da revisão mais a cadência da faixa; antecipar é permitido, postergar não | `calculations.next_review_limit` |
| Situação apurada | Reduzido, agravado, sem mudança ou avaliação inicial, pelo score antes e depois | `calculations.assessed_situation` |
| Sem redução | Ameaça cujo residual não caiu abaixo do inerente | `calculations.has_no_reduction` |
| Ação obrigatória | Ameaça inerente Alto ou mais pesada exige ação, exceto na estratégia Aceitar | `calculations.requires_response_action` |
| Aprovação obrigatória | Plano de inerente na faixa mais alta (ou marcado) aguarda a gerência | `calculations.is_top_band` |
| Pauta de escalonamento | Motivos calculados do risco (sem avaliação, topo sem plano, alvo a menos de 30 dias, sem redução, aprovação pendente, revisão vencida, gatilho) | `calculations.pauta_reasons` |
| Alvo acima da inerente | Proibido para ameaça | `calculations.is_target_above` |
| Teto da faixa | Maior score da faixa: o piso da seguinte menos um; 25 na mais pesada | `calculations.band_ceiling` |
| Célula da matriz | O risco entra pela avaliação escolhida: a residual ou, sem ela, a inerente; sem inherent fica fora e conta na nota | `panel_service.risk_matrix` (com `calculations.risk_score` e `risk_severity`) |
| Evolução mensal do score residual | Para cada mês, a soma do evento mais recente (avaliação ou revisão) de cada ameaça ativa ao fim do mês; sem série gravada (D6) | `calculations.monthly_residual_scores` |
| Redução média | Média de (inerente − residual) ÷ inerente das ameaças com residual; a meta é a média da redução que leva cada ameaça ao teto da faixa-alvo | `panel_service._reduction_average` e `_reduction_target` |
| Exposição por categoria (RBS) | Score residual somado das ameaças ativas por grupo, a mais pesada primeiro | `panel_service._categories` |
| Numeração | Próximo sufixo numérico do projeto: ``RSK-0001``; sufixos não numéricos não movem a série | `calculations.next_code_number` e `service.reserve_code` |
| Histórico da ficha | Linhas da trilha de auditoria (`risco`, `risco_avaliacao`, `risco_revisao`, `risco_plano_aprovacao`, `risco.historico`), com o antes e o depois lidos por coluna | `ficha_service._history_of` |

## Fluxos

Identificado → Em análise → Em tratamento → Monitorado → Materializado ou Encerrado. A avaliação
residual só habilita depois do plano de resposta; para ameaças o residual não supera o inerente e
um score novo exige justificativa. Exclusão lógica é do Gestor, bloqueada com ação aberta e para
risco encerrado, e só o Admin vê e restaura.

**Plano de resposta** (`ficha_service.save_plan`): o residual só habilita depois do plano; para
ameaça o alvo não supera a inerente; o prazo é futuro; Evitar exige 80 caracteres e SM (existente
ou "nova", que gera ação na Central); Transferir exige instrumento; Aceitar exige 30 caracteres;
ameaça inerente Alto ou Crítico exige ao menos uma ação, exceto Aceitar. Inerente na faixa mais
alta (ou o campo marcado) cria a aprovação **Pendente** e o risco vai a Em análise; a aprovação é
do Gestor e o **responsável pelo plano não pode aprová-la** (D7, 403). Devolvida, a ficha avisa e o
plano pode ser reenviado. Salvar plano em risco encerrado é 422.

**Revisão periódica** (`ficha_service.review_risk`): a data não pode ser futura nem anterior à
última revisão; a próxima revisão não passa da cadência da faixa do novo score (antecipa, nunca
posterga); a situação apurada precisa bater com a variação do score; o comentário é obrigatório
(10 a 1000 caracteres). A revisão grava a nova avaliação vigente (inerente ou residual) e a linha
da linha do tempo, ambas fatos; o gatilho ocorrido força a reavaliação e entra na pauta. O
"notificar" passa pela porta de notificação (`notification.RISK_REVIEW`), sem e-mail cadastrado a
ficha avisa que nada foi enviado.

**Encerramento** (`ficha_service.close_risk`, Gestor): bloqueado com ação aberta, salvo
Materializado; Duplicado exige o risco original do mesmo projeto; a lição aprendida é sempre
obrigatória (20 a 1000 caracteres) e nasce em **Rascunho** pela fachada de Lições, com origem
`Risco`; Materializado de ameaça cria a ação do problema na Central (grupo `Problema`) e, se
marcado, a **SM Registrada** no 08 — tudo na mesma transação (D9). Para oportunidade materializada
o motivo aparece como "Capturada" e não há problema nem SM. O risco vai a Materializado ou
Encerrado e a próxima revisão é limpa.

**Reabertura** (`ficha_service.reopen_risk`, Gestor): exige justificativa (10 a 500 caracteres);
a situação volta à que a trilha guardou antes do encerramento (com o fallback do protótipo) e os
campos de encerramento são limpos, inclusive o vínculo com a lição e a SM; a lição permanece no
acervo. A justificativa entra no histórico pela entidade `risco.historico`.

**Ação de mitigação** (`ficha_service.create_risk_action`): registro da Central de Ações com
origem `Risco`, item sequencial dentro do risco, grupo `Plano de resposta`; o risco Monitorado com
estratégia volta a Em tratamento. "Salvar e nova" reabre o formulário.

**Matriz P x I** (`panel_service.risk_matrix`): só riscos ativos entram, como no protótipo; a
avaliação exibida é a inerente ou a residual (que cai para a inerente quando não existe); o risco
sem avaliação inerente fica fora e a nota o conta. A cor da célula é da posição (probabilidade x
impacto) e a oportunidade inverte a escala (frio e verde); a célula com risco leva ao Registro
filtrado pelo parâmetro `celula` (`p3|i4`, que o registro traduz em probabilidade e impacto) e a
vazia fica esmaecida. A movimentação mostra o score inerente e o residual sobrepostos, ordenados
pelo inerente, e destaca quem não reduziu — esse risco é o que entra na pauta.

**Painel de riscos** (`panel_service.risk_panel`): os indicadores saem do resumo do registro
(faixas com a meta, exposição, revisão vencida) mais a redução média e a meta de redução; a
exposição por categoria (RBS) soma o score residual das ameaças ativas por grupo; a evolução
mensal é reconstruída do histórico de avaliações e revisões (D6, `monthly_residual_scores`), com
a ameaça ativa ao fim de cada mês entrando pelo evento mais recente até a data; a pauta é a lista
dos riscos ativos com motivo (`pauta_reasons`), o mais pesado primeiro. O envio da pauta
(`send_risk_agenda`) pertence a um projeto, vai para o gerente do cadastro pela porta de
notificação (tipo `pauta_riscos`) e fica na trilha como `simulado` enquanto o envio real está
desligado. O botão "Análise do período" abriu na ISSUE-082: ele abre o modal do módulo
`relatorio` (`/api/relatorio/analise/...`), com o resumo do painel no corte e a análise do
Portfólio; só o texto é obrigatório, sem desvios detectados.

## Integrações (D9)

- **Central de Ações** (`central_acoes.service`): a ação nasce por `create_action` (a costura
  única); a ficha lê as ações por `actions_of_origin` e conta por `count_actions_of_origin`. A
  origem `Risco` aponta de volta para `riscos/ficha?codigo=...` (`origin_links`).
- **Suprimentos** (`suprimentos.service`): o pedido crítico registra o risco sugerido pela fachada
  `create_suggested_risk` — Em análise, categoria Suprimentos > Fornecedores (criada quando o
  catálogo não a tem), origem `Diligenciamento PED-...`, gatilho "Previsão de entrega depois do
  ROS.", dimensão Prazo, impacto em prazo `max(0, -folga)` e avaliação inerente do formulário; o
  mesmo pedido não sugere duas vezes e a ficha do pedido resolve o risco por `diligence_risks`
  (pela origem, sem coluna no pedido).
- **Governança** (`governanca.service`): as SMs do projeto para o plano vêm de `change_options`;
  o encerramento materializado cria a SM por `create_change` (situação Registrada) e o vínculo
  fica em `risco.encerramento_mudanca_id`; a estratégia Evitar guarda a SM em `risco.mudanca_id`.
- **Lições** (`lessons_service`): o encerramento sempre abre a lição em Rascunho por
  `create_draft_lesson`, com origem `Risco` e o número do risco; a ficha lê a lição por
  `lesson_options`. "Aplicar em projeto" com "gerar risco" cria o risco Identificado por
  `save_risk` (ameaça para "A evitar", oportunidade para "A repetir", origem `Lições aprendidas`/
  `Lição LA-...`, impactos da lição, sem avaliação) e o reuso guarda o id em
  `licao_aplicacao.risco_id`; o módulo registra `register_origin("Risco", ...)` para a fachada de
  Lições conferir o número.
- **Financeiro** (`financeiro.service`): a ficha do risco lista os claims do contrato por
  `claims_of_risk` (leitura pela fachada, nunca da tabela); o Financeiro lê a exposição por
  `active_threats` (só as ameaças ativas, por VME) para a cobertura da Contingência e resolve os
  rótulos dos vínculos por `risk_labels`/`risk_by_code`/`risk_options`.
- **Notificação** (`core.notification`): a revisão com "notificar" envia pela porta (tipo
  `revisao_risco`) ao dono e ao gestor do projeto; a pauta do painel envia ao gerente do projeto
  (tipo `pauta_riscos`); sem o envio real, as duas ficam simuladas na trilha.
- **Configurações**: projetos, pessoas, RBS e o grupo Riscos dos parâmetros; a ficha usa
  `pautaDiasAntesDoPrazo` (30) na pauta e `revisaoAlertaDias` no registro.

Somente a fachada dona grava em cada módulo; a integração que chega aos Riscos é uma chamada de
serviço na transação do chamador (ISSUE-067).

## Parâmetros

Escala ativa (Timenow de 4 faixas ou CIPM de 3), probabilidades médias por faixa, cadência de
revisão por faixa, impactos, os dias do alerta de revisão e os dias antes do prazo da pauta, no
grupo Riscos dos parâmetros em `Configurações > Parâmetros` (ISSUE-076).

## Carga de demonstração

A parte `riscos` (ISSUE-064) carrega os 19 riscos do protótipo com avaliações, revisões e
aprovação; a ISSUE-065 liga a ata de origem, a SM do Evitar, a lição e a SM do encerramento
materializado pelos ids que as fachadas de Central de Ações e Governança devolveram. As ações com
origem `Risco` entram pela parte `central_acoes`. Datas deslocadas da âncora (25/09/2026) para a
data do run, idempotente pela tabela `carga_demonstracao`.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas e templates do registro | `routes.py`; `api/src/templates/riscos/` |
| Rotas da ficha (plano, aprovação, ação, revisão, encerramento, reabertura) | `ficha_routes.py` |
| Rotas da matriz e do painel (e o modal do envio da pauta) | `panel_routes.py`; `api/src/templates/riscos/` |
| Fluxo do registro, exclusão, numeração e as fachadas das integrações (`create_suggested_risk`, `diligence_risks`, `risk_options`, `risk_labels`, `risk_by_code`, `active_threats`) | `service.py` |
| Ficha: plano, revisões, encerramento, reabertura e histórico | `ficha_service.py` |
| Matriz, painel, evolução do score e envio da pauta | `panel_service.py` |
| Score, severidade, VME, cadência, pauta, teto de faixa e evolução | `calculations.py` |
| Validação de identificação, avaliação, plano, revisão, encerramento, reabertura e filtros (inclusive `celula`) | `validation.py` |
| Exportação (Excel e imprimível do registro, da ficha, da matriz e do painel) | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` |
| Tela, estilo e comportamento | `app/_views/riscos/` e `app/paginas/riscos/` |
| Testes | `api/tests/riscos/` e `api/tests/oraculo/test_oraculo_riscos.py` |

A ISSUE-067 ligou as integrações de chegada: o risco sugerido do diligenciamento
(`service.create_suggested_risk`), o vínculo do claim (FK `contrato_claim.risco_id`, lida pela
fachada do Financeiro), a lição aplicada (`save_risk` + FK `licao_aplicacao.risco_id`, migração
`m067`) e a exposição para a cobertura da Contingência (`service.active_threats`).

## Idioma (ISSUE-088)

A parte 2 do inglês (D13) completa o catálogo: o namespace `riscos` vive em
`api/src/core/translations.py`, alimentado pelo `en.js` do protótipo (e, na Programação
Semanal, por chaves novas escritas com o inglês da casa). O idioma vem do cookie
`gestnow_idioma`, gravado pela rota `POST /api/idioma`, e o seletor PT | EN fica na barra
lateral. O bloco 05 do `en.js` é a fonte; o VME vira EMV e a RBS acompanha o vocabulário do protótipo. A matriz e o painel mandam os `rotulos` do motor pelo `_chart_data`.
Os templates chamam `{{ t('riscos', 'Texto') }}`; as views e o JS estáticos usam
`data-i18n`/`TN.t`; as datas saem do `data()`/`data_hora()` do contexto e do
`translations.format_date`/`mes_curto`/`semana_label` (a semana ISO é `S38` em português e
`W38` em inglês). As rotas traduzem avisos, recusas e erros por campo no idioma do request,
e os gráficos passam por `_chart_data`, que traduz os textos do `data-dados` e acrescenta os
`rotulos` do motor de gráficos. Títulos e colunas das planilhas e da folha imprimível são
traduzidos pelo namespace do documento (`Document.namespace`/`Document.idioma`) em
`core/export_document`; o `RequestContext.idioma` leva o idioma resolvido às costuras das
rotas. Para acrescentar tradução, some a chave ao namespace `riscos`; a cobertura em
`api/tests/plataforma/test_traducoes.py` e a revisão de tela em
`api/tests/plataforma/test_idioma_nas_areas_2.py` reprovam chave marcada sem tradução.
