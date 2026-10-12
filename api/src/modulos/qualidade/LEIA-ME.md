# Gestão da Qualidade

Módulo `qualidade`. Registra não conformidades (RNC), inspeções/ITP e auditorias, com controle
de tratamento e eficácia. A ISSUE-068 entrega a tela **Não conformidades (RNC)**, a ISSUE-069 a
tela **Inspeções e ITP** (com o FAT do diligenciamento ligado), a ISSUE-070 a tela
**Auditorias** e a ISSUE-071 o **Painel da qualidade** (com os indicadores que o Início
consome).

## Telas

| Tela | Conteúdo | Situação |
|---|---|---|
| Não conformidades (RNC) | Filtros (busca, situação, severidade, disciplina e origem), cinco KPIs, lista com a próxima etapa e as ações, ficha em modal (contenção, causa raiz, disposição e concessão, verificação, ações da Central, evidências e histórico) e os formulários do fluxo | Entregue na ISSUE-068 |
| Painel da qualidade | Cinco KPIs, alerta de auditorias atrasadas, RNC por mês, aprovação em inspeções com a meta, Pareto por disciplina, RNC por origem, pauta de tratamento e desempenho por empresa | Entregue na ISSUE-071 |
| Inspeções e ITP | Planos com pontos H/W/R (filtros por busca, ITP, resultado e tipo), cinco KPIs, ficha do ITP com os pontos, novo ITP, nova revisão, aprovação do cliente e registro de inspeção | Entregue na ISSUE-069 |
| Auditorias | Programa (filtros por busca, situação e tipo), cinco KPIs, ficha com constatações e reprogramações, planejar/reprogramar (justificativa obrigatória ao mudar a data) e registrar o resultado (cada Não conformidade abre RNC) | Entregue na ISSUE-070 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a
view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view
(`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra
`TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A
verificação `trio-da-tela` confere o conjunto. Convenção completa em
`docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Painel da qualidade | `app/_views/qualidade/painel.html` | `app/paginas/qualidade/painel.css` | `app/paginas/qualidade/painel.js` |
| Não conformidades (RNC) | `app/_views/qualidade/rnc.html` | `app/paginas/qualidade/rnc.css` | `app/paginas/qualidade/rnc.js` |
| Inspeções e ITP | `app/_views/qualidade/inspecoes.html` | `app/paginas/qualidade/inspecoes.css` | `app/paginas/qualidade/inspecoes.js` |
| Auditorias | `app/_views/qualidade/auditorias.html` | `app/paginas/qualidade/auditorias.css` | `app/paginas/qualidade/auditorias.js` |

O JS da RNC chama os fragmentos do servidor: a lista carrega no alvo `rnc-conteudo` e a ficha e
os formulários abrem no modal do Design System, no alvo `rnc-modal-corpo`. Depois de uma
gravação, o fragmento da lista traz um marcador oculto que reabre a ficha com o estado novo. O
JS das Inspeções e ITP segue o mesmo padrão: a lista no alvo `inspecoes-conteudo` e a ficha do
ITP e os formulários no alvo `inspecoes-modal-corpo` (`api/src/modulos/qualidade/inspecoes_routes.py`).
O JS das Auditorias repete o padrão: a lista no alvo `auditorias-conteudo` e a ficha, o
formulário de planejar/reprogramar e o do resultado no alvo `auditorias-modal-corpo`
(`api/src/modulos/qualidade/auditorias_routes.py`). O JS do Painel carrega o fragmento no alvo
`painel-conteudo`; o vazio de origem vem do servidor (o marcador `data-situacao`) e erro/sem
permissão saem do `ajax:error`, como no painel dos riscos
(`api/src/modulos/qualidade/painel_routes.py`).

## Rotas

Prefixo: `/api/qualidade/`. Todas passam pelo `fragment_route` (gate do Alpine, usuário, escopo
e permissão) e desenham fragmentos; as exportações usam os mecanismos genéricos (D12).

| Rota | Método | Uso | Permissão |
|---|---|---|---|
| `painel` | GET | O painel do escopo (KPIs, alerta, quatro gráficos e as duas tabelas) | Ver |
| `painel/excel` e `painel/imprimivel` | GET | Excel e PDF do painel (KPIs, números dos gráficos e as duas tabelas) | Ver |
| `rnc` | GET | A lista (`busca`, `situacao`, `severidade`, `disciplina`, `origem`, `empresa`, `pagina`) | Ver |
| `rnc/excel` e `rnc/imprimivel` | GET | Excel e PDF do mesmo filtro (KPIs + tabela) | Ver |
| `rnc/{codigo}/ficha` | GET | A ficha, com as ações da Central, as evidências e o histórico | Ver |
| `rnc/nova` | GET/POST | Abrir a RNC (no Portfólio pede o projeto antes) | Membro |
| `rnc/{codigo}/responsavel` | GET/POST | Atribuir a análise de causa | Membro |
| `rnc/{codigo}/analise` | GET/POST | Registrar causa raiz, disposição, concessão, custo e as ações (Central) | Membro |
| `rnc/{codigo}/acoes` | GET/POST | Nova ação corretiva na etapa Ação corretiva | Membro |
| `rnc/{codigo}/verificacao` | GET/POST | Enviar para verificação de eficácia | Membro |
| `rnc/{codigo}/eficacia` | GET/POST | Verificar a eficácia (encerra ou volta para Ação corretiva) | Gestor |
| `rnc/{codigo}/cancelamento` | GET/POST | Cancelar a RNC (só antes da ação corretiva) | Gestor |
| `rnc/{codigo}/custo` | GET/POST | Atualizar o custo da não qualidade | Membro |
| `inspecoes` | GET | A lista das Inspeções e ITP (`busca`, `itp`, `resultado`, `tipo`, `pagina`) | Ver |
| `inspecoes/excel` e `inspecoes/imprimivel` | GET | Excel e PDF do mesmo filtro (KPIs + as duas tabelas) | Ver |
| `inspecoes/{codigo}/ficha` | GET | A ficha do ITP com os pontos da revisão vigente | Ver |
| `inspecoes/itp/novo` | GET/POST | Criar o ITP (revisão 0; no Portfólio pede o projeto antes) | Membro |
| `inspecoes/itp/{codigo}/revisao` | GET/POST | Nova revisão (volta a pedir a aprovação; não retira ponto com inspeção) | Membro |
| `inspecoes/itp/{codigo}/aprovacao` | GET/POST | Aprovação do cliente da revisão vigente | Gestor |
| `inspecoes/inspecao` | GET/POST | Registrar inspeção em ponto de ITP aprovado (no Portfólio pede o projeto antes) | Membro |
| `auditorias` | GET | A lista do programa (`busca`, `situacao`, `tipo`) | Ver |
| `auditorias/excel` e `auditorias/imprimivel` | GET | Excel e PDF do mesmo filtro (KPIs + tabela) | Ver |
| `auditorias/{codigo}/ficha` | GET | A ficha, com as constatações e as reprogramações | Ver |
| `auditorias/nova` | GET/POST | Planejar a auditoria (no Portfólio pede o projeto antes) | Membro |
| `auditorias/{codigo}/reprogramacao` | GET/POST | Reprogramar (só Planejada; mudar a data exige justificativa) | Membro |
| `auditorias/{codigo}/resultado` | GET/POST | Registrar o resultado; cada Não conformidade abre a RNC | Membro |

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Prazo de tratamento | Data da constatação + `prazoTratamentoDias` da severidade (parâmetro) | `calculations.treatment_deadline` |
| RNC ativa | Situação fora de `Encerrada` e `Cancelada` | `calculations.is_active` |
| Prazo vencido | Em tratamento (Aberta a Ação corretiva) e prazo **anterior** à data de referência (a fronteira: o dia do prazo ainda não vence) | `calculations.is_overdue`, `days_overdue` |
| Verificação vencida | Em verificação de eficácia e prevista anterior à data de referência | `calculations.is_verification_overdue` |
| Dias aberta | Da data da constatação até o encerramento, ou até a data de referência | `calculations.days_open` |
| Próxima etapa | O degrau do fluxo que a situação aguarda | `calculations.next_step` |
| Reincidência | Quantas verificações **ineficazes** a RNC já teve: as transições da trilha de auditoria (`rnc`) que voltam de Verificação de eficácia para Ação corretiva; não há coluna (D5b) | `calculations.recurrence_count` |
| Tempo médio de tratamento | Média dos dias das RNC encerradas, arredondada para cima na metade (a regra do protótipo) | `calculations.average_treatment_days` |
| Custo da não qualidade | Soma dos custos das RNC do universo da lista (o KPI do protótipo soma todas) | `service._summary` |
| Aprovação em inspeções | Inspeções aprovadas ou com ressalva divididas pelo total | `calculations.inspection_approval_rate` (ISSUE-069) |
| Inspeção aprovada | Resultado `Aprovado` ou `Aprovado com ressalva` (a ressalva conta como aprovada) | `calculations.approved_inspection` |
| Antecedência da notificação | Horas entre a data da notificação ao cliente e a inspeção (`dias × 24`); o ponto R não tem notificação | `calculations.notification_hours` |
| Aviso da notificação | Ponto H/W sem notificação ou com antecedência **menor** que `notificacaoClienteHoras` avisa; exatamente o parâmetro passa | `calculations.notification_warning` |
| Pontos já inspecionados | Pontos distintos com ao menos um registro, somados por ITP | `calculations.covered_points` |
| Código do ITP | `ITP-<padrão do projeto>-<sigla da disciplina>-NN`, dois dígitos, sequência do projeto e do prefixo (o protótipo não usava a sequência travada) | `service._next_itp_code` |
| Código da inspeção | Série global `INS-<ano>-NNNN`, quatro dígitos, pelo maior número existente | `service._next_inspection_code` (`numbering.next_series_number`) |
| Conformidade em auditorias | Itens conformes divididos pelos itens verificados | `calculations.audit_conformity_rate` (ISSUE-070) |
| Auditoria atrasada | Planejada com a data **anterior** à referência (a fronteira: o dia planejado ainda não atrasa); os dias de atraso saem da mesma conta | `calculations.audit_overdue`, `audit_days_overdue` |
| Aderência ao programa de auditorias | Auditorias realizadas divididas pelas previstas até a data de referência (data ≤ referência); vazio devolve `·` | `calculations.audit_program_adherence` |
| Contagens por tipo de constatação | NC, Observação e Oportunidade de melhoria, na ordem do vocabulário; NC em aberto conta a RNC ativa (situação fora de Encerrada e Cancelada) | `calculations.finding_type_counts`, `service._build_audit_lines` |
| Código da auditoria | `AUD-<padrão da ata do projeto>-NN`, dois dígitos, pelo maior código do projeto (o protótipo também contava os códigos) | `service._next_audit_code` |
| Contenção da RNC da NC | `"Contenção a definir pelo auditado em até 48 horas da auditoria <AUD>."`, gravada quando a constatação abre a RNC | `service.AUDIT_CONTAINMENT` (`record_result`) |
| Indicadores do painel | Os números do protótipo (RNC abertas, encerradas, vencidas, verificações vencidas, críticas, tempo médio, eficácia, inspeções, aprovação e meta, conformidade e meta, auditorias realizadas e previstas, aderência, atrasadas, NC de auditoria, ITP, sem aprovação e custo); a ISSUE-079 (Início) consome a mesma função | `painel_service.quality_indicators` |
| Eficácia na 1ª verificação | RNC encerradas **sem reincidência** divididas pelas encerradas; a reincidência vem da trilha (D5b); vazio devolve `·` | `calculations.first_time_effectiveness_pct` |
| Série dos 6 meses | Aberturas, encerramentos, em aberto e inspeções de cada mês, com a aprovação do mês; os seis meses terminam no mês da data de referência | `painel_service.quality_series` |
| Pareto por disciplina e RNC por origem | RNC não canceladas agrupadas, em ordem decrescente de total (empate pelo custo), com o percentual e o acumulado; o visual Pareto date da quantidade | `painel_service._group_lines` |
| Desempenho por empresa | Inspeções e reprovações das inspeções, RNC e custo das não canceladas; aprovação = (inspeções − reprovadas) ÷ inspeções (sem inspeção, `·`); ordem por RNC desc e custo desc | `painel_service._company_lines` |
| Pauta de tratamento | RNC com prazo vencido, verificação vencida, severidade crítica ativa ou concessão pendente, com os motivos do protótipo e ordem pelo atraso desc | `painel_service._agenda` |
| Limite do tratamento | A faixa `"X a Y dias"` do menor ao maior `prazoTratamentoDias` vigente | `painel_service.treatment_limit_days` |

## Fluxos

RNC: **Aberta → Em análise de causa → Ação corretiva → Verificação de eficácia → Encerrada**;
**Cancelada** só antes da ação corretiva (Gestor, com motivo). A abertura exige a descrição (o
que, onde e o requisito) e a contenção imediata; o prazo de tratamento vem da severidade e vale
até a ação corretiva concluída. A análise (5 porquês, Ishikawa ou árvore de causas; causa raiz;
disposição) cria ao menos uma **ação corretiva na Central** (origem `RNC`), na mesma transação;
Reparo e Usar como está exigem a **concessão do cliente** (documento e data). Com as ações
concluídas, a RNC vai para a verificação, prevista para `verificacaoEficaciaDias` à frente. A
verificação é do **Gestor** e não pode ser feita por quem respondeu pela análise (segregação,
403); eficaz encerra e pode abrir a **lição em Rascunho** no 08 (origem `RNC <código>`, gravando
`rnc.licao_id`); ineficaz volta para Ação corretiva e conta reincidência. O custo da não
qualidade é atualizável com a composição enquanto a RNC está ativa.

Permissões (D7): ver a lista e a ficha, qualquer perfil; abrir e gravar, Membro; verificar a
eficácia e cancelar, Gestor; o vínculo Fornecedor não alcança o módulo (403).

ITP e inspeções: o ITP nasce na revisão 0 com os pontos (H = espera obrigatória; W = testemunho
do cliente; R = revisão de registros), cada um com o critério e quem executa/inspeciona. A
**aprovação do cliente** é do Gestor, uma vez por revisão; a **nova revisão** volta a pedir a
aprovação, casa os pontos pela atividade normalizada (o ponto preserva o id e a inspeção
continua ligada a ele) e **não pode retirar ponto que já tem inspeção**. A inspeção só entra em
ITP aprovado; a ressalva conta como aprovada; a **reprovação abre a RNC** (origem `Inspeção`,
referência o número da inspeção, descrição `<ponto> (<ITP>): <observação>`, com a severidade e a
contenção do próprio registro) na mesma transação. No ponto W (e no H), a notificação ao
cliente é registrada e a antecedência mínima vem do parâmetro `notificacaoClienteHoras`: sem
notificação, ou com menos horas que o parâmetro, a tela avisa. O **FAT** do diligenciamento
(Suprimentos) grava a inspeção sem ponto de ITP, identificada pelo `pedido_id`; a inspeção
aprovada conclui o marco e a reprovada não conclui e exige a nova previsão do reteste
(`suprimentos.service.update_order_milestone` → `qualidade.service.record_fat_inspection`).

Permissões do ITP: ver a lista e a ficha, qualquer perfil; criar ITP, nova revisão e inspeção,
Membro; aprovar o cliente, Gestor; o Fornecedor não alcança o módulo (403).

Auditorias: o programa (Contratada, Fornecedor ou Interna) nasce com o escopo, os critérios, o
auditado, o auditor líder e a data; a data vencida sem resultado é **atrasada**. A
**reprogramação** só vale na auditoria **Planejada**, exige a **justificativa** (mínimo de 10
caracteres) quando a data muda e fica registrada em `auditoria_reprogramacao` com o autor e o
momento; a trilha de auditoria guarda o antes e o depois da edição. O **resultado** (só na
Planejada) grava a data de realização (até a referência), os itens verificados e conformes
(conformes entre zero e o verificado) e as constatações (Não conformidade, Observação e
Oportunidade de melhoria; descrição mínima de 10 caracteres, e a NC exige requisito, disciplina
e severidade). **Cada Não conformidade abre a RNC** (origem `Auditoria`, referência o número da
auditoria, empresa o auditado, descrição `<descrição> Requisito: <requisito>.`, contenção
padrão da auditoria) na mesma transação, e o vínculo fica em `auditoria_constatacao.rnc_id`;
**não pode haver mais NC que itens não conformes** ("Há mais não conformidades (n) que itens
não conformes (m)."). A RNC da constatação mostra a situação lida da própria RNC.

Permissões da Auditoria: ver a lista e a ficha, qualquer perfil; planejar, reprogramar e
registrar o resultado, Membro; o Fornecedor não alcança o módulo (403).

Painel (ISSUE-071): é uma leitura calculada de tudo o que já existe (D6) — KPIs, série dos seis
meses, Pareto por disciplina, RNC por origem, desempenho por empresa, pauta de tratamento e o
alerta de auditorias atrasadas —, sem gravação nem tabela nova. As metades e as metas vêm dos
parâmetros vigentes; as RNC canceladas ficam fora das agregações (o custo da não qualidade soma
todas, como no protótipo). A ordem do Pareto é total desc e, no empate, custo desc; a da pauta é
atraso desc; a das empresas é RNC desc e custo desc. No Portfólio a pauta abre com a coluna
Projeto (também nas exportações) e a tabela de empresas continua agregada por empresa, sem a
coluna. Os quatro gráficos saem da biblioteca do Design System (D11): Curva S Barra e Linha
(barras de aberturas e encerramentos por mês), Linhas Múltiplas (aprovação mensal com a meta
tracejada), Pareto (disciplina) e Comparativo de Barras (origem); o visual do protótipo é
registrado em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`. O Excel e o PDF levam os KPIs, os números de
cada gráfico em tabela e as duas tabelas. O botão "Análise do período" abriu na ISSUE-082: ele
abre o modal do módulo `relatorio` (`/api/relatorio/analise/...`), com o resumo do módulo no
corte, os desvios detectados sem comentário obrigatório (RNC com prazo de tratamento vencido,
aprovação em inspeções e conformidade em auditorias abaixo da meta e auditorias atrasadas) e a
análise do Portfólio. Permissão: ver, qualquer perfil; o Fornecedor não alcança o módulo (403).

## Integrações

* **Central de Ações (saída):** as ações corretivas nascem pela fachada da Central
  (`create_action`), na transação da análise ou da ação nova, com origem `RNC`, referência do
  número e item sequencial; a ficha lê as ações por `actions_of_origin`.
* **Central de Ações (entrada):** `origin_links.register("RNC", ...)` resolve o link de volta
  para `qualidade/rnc?busca=<código>`.
* **Governança (saída):** a lição do encerramento eficaz entra pela fachada
  (`lessons_service.create_draft_lesson`), em Rascunho, origem `RNC`, na mesma transação.
* **Governança (entrada):** o módulo registra `register_origin("RNC", ...)`, então o formulário
  de lição passa a oferecer a origem RNC e confere o número pela fachada da Qualidade.
* **Anexos (D5a):** `attachment_origins.register(table="rnc", ...)`; a ficha carrega o painel
  genérico de anexos (evidências da abertura, concessão e verificação) e o download checa a
  permissão do registro de origem. A inspeção não tem registro de origem de anexo nesta fatia
  (divergência registrada em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`).
* **Diligenciamento (entrada, ISSUE-069):** o FAT de Suprimentos grava a inspeção pela fachada
  (`record_fat_inspection`), na transação da atualização do marco (D9); a inspeção não tem
  ponto de ITP e é identificada pelo `pedido_id`; a reprovação não abre RNC (o FAT reprovado
  apenas não conclui o marco e exige a nova previsão do reteste).
* **Auditorias → RNC (ISSUE-070):** a constatação Não conformidade abre a RNC pela própria
  fachada (`record_result` chama `open_rnc`), na mesma transação, com origem `Auditoria` e
  referência o número da auditoria; o vínculo é a FK `auditoria_constatacao.rnc_id` (D9), e a
  ficha da auditoria linka a RNC pelo `origin_links` (`qualidade/rnc?busca=<código>`).

## Parâmetros

Grupo `qualidade` em Configurações > Parâmetros, versionado: `prazoTratamentoDias`
`{critica: 15, maior: 30, menor: 45}` (crescentes de Crítica para Menor, entre 1 e 180 dias),
`verificacaoEficaciaDias` (30; entre 0 e 180), `metaAprovacaoInspecaoPct` (95) e
`metaConformidadeAuditoriaPct` (90) — entre 0 e 100% — e `notificacaoClienteHoras` (48; entre 0 e
240). As metas e a antecedência valem para as telas das ISSUE-069/070/071.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas e fragmentos da RNC | `routes.py` e `api/src/templates/qualidade/rnc*.html` |
| Rotas e fragmentos das Inspeções e ITP | `inspecoes_routes.py` e `api/src/templates/qualidade/inspecoes*.html` |
| Rotas e fragmentos das Auditorias | `auditorias_routes.py` e `api/src/templates/qualidade/auditorias*.html` |
| Rotas, KPIs e gráficos do Painel | `painel_routes.py` e `api/src/templates/qualidade/painel.html` |
| Indicadores e agregações do Painel (o Início consome os indicadores) | `painel_service.py` |
| Transições, permissões e integrações (RNC, ITP, FAT e auditorias) | `service.py` |
| Fórmulas da RNC, do ITP, da inspeção e da auditoria | `calculations.py` |
| Validações e mensagens do formulário | `validation.py` |
| Exportação (Excel e PDF) | `export.py` |
| Persistência | `models.py`; entidades `rnc`, `itp`, `itp_revisao`, `itp_ponto`, `inspecao`, `auditoria_qualidade`, `auditoria_constatacao` e `auditoria_reprogramacao` em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` (partes `qualidade-rnc`, `qualidade-inspecoes` e `qualidade-auditorias`) |
| Tela, estilo e comportamento | `app/_views/qualidade/` e `app/paginas/qualidade/` |
| Testes | `api/tests/qualidade/` e `api/tests/oraculo/test_oraculo_qualidade.py` |

## Idioma (ISSUE-088)

A parte 2 do inglês (D13) completa o catálogo: o namespace `qualidade` vive em
`api/src/core/translations.py`, alimentado pelo `en.js` do protótipo (e, na Programação
Semanal, por chaves novas escritas com o inglês da casa). O idioma vem do cookie
`gestnow_idioma`, gravado pela rota `POST /api/idioma`, e o seletor PT | EN fica na barra
lateral. O bloco 06 do `en.js` é a fonte; a RNC vira NCR e o ITP fica ITP. As recusas de fluxo (eficácia, cancelamento) são traduzidas no render, como as demais.
Os templates chamam `{{ t('qualidade', 'Texto') }}`; as views e o JS estáticos usam
`data-i18n`/`TN.t`; as datas saem do `data()`/`data_hora()` do contexto e do
`translations.format_date`/`mes_curto`/`semana_label` (a semana ISO é `S38` em português e
`W38` em inglês). As rotas traduzem avisos, recusas e erros por campo no idioma do request,
e os gráficos passam por `_chart_data`, que traduz os textos do `data-dados` e acrescenta os
`rotulos` do motor de gráficos. Títulos e colunas das planilhas e da folha imprimível são
traduzidos pelo namespace do documento (`Document.namespace`/`Document.idioma`) em
`core/export_document`; o `RequestContext.idioma` leva o idioma resolvido às costuras das
rotas. Para acrescentar tradução, some a chave ao namespace `qualidade`; a cobertura em
`api/tests/plataforma/test_traducoes.py` e a revisão de tela em
`api/tests/plataforma/test_idioma_nas_areas_2.py` reprovam chave marcada sem tradução.
