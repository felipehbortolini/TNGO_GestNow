# Financeiro

Módulo `financeiro`. Mantém a Estrutura Analítica de Custos, o desempenho de custo, desembolso, reservas e administração de contratos. Valores persistidos são centavos inteiros; a formatação acontece na saída.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| EAC | Árvore de custo, itens, revisões, remanejamentos e importação | ISSUE-029, ISSUE-030 |
| Mapa de controle | Orçado, comprometido, realizado, saldo, projeção no término e desvio, com mapa de calor | ISSUE-031 |
| Cronograma de desembolso | Saldo futuro por item/mês, previsto e realizado | ISSUE-043 |
| KPIs de custo e Curva S financeira | Índices de custo, valor agregado e séries | ISSUE-042 |
| Contingência | Reservas, consumo, liberações, exposição e cobertura | ISSUE-041 |
| Contratos e ficha do contrato | Medições, aditivos, marcos, claims, EOT e avaliações | ISSUE-032 a ISSUE-035 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| EAC | `app/_views/financeiro/eac.html` | `app/paginas/financeiro/eac.css` | `app/paginas/financeiro/eac.js` |
| Mapa de controle | `app/_views/financeiro/mapa_controle.html` | `app/paginas/financeiro/mapa_controle.css` | `app/paginas/financeiro/mapa_controle.js` |
| Cronograma de desembolso | `app/_views/financeiro/desembolso.html` | `app/paginas/financeiro/desembolso.css` | `app/paginas/financeiro/desembolso.js` |
| KPIs de custo | `app/_views/financeiro/kpis.html` | `app/paginas/financeiro/kpis.css` | `app/paginas/financeiro/kpis.js` |
| Curva S financeira | `app/_views/financeiro/curva_s.html` | `app/paginas/financeiro/curva_s.css` | `app/paginas/financeiro/curva_s.js` |
| Contingência | `app/_views/financeiro/contingencia.html` | `app/paginas/financeiro/contingencia.css` | `app/paginas/financeiro/contingencia.js` |
| Contratos | `app/_views/financeiro/contratos.html` | `app/paginas/financeiro/contratos.css` | `app/paginas/financeiro/contratos.js` |
| Contrato | `app/_views/financeiro/contrato.html` | `app/paginas/financeiro/contrato.css` | `app/paginas/financeiro/contrato.js` |

## Rotas previstas

Prefixo: `/api/financeiro/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `eac` e `eac/revisoes` | Consultar itens, importar e aplicar revisão aprovada | ISSUE-029, ISSUE-030 |
| `mapa-de-controle` e `custos` | Consultar mapa, importar ERP e atualizar projeções com justificativa | ISSUE-031 |
| `kpis` e `curva-s` | Consultar indicadores, valor agregado e série financeira | ISSUE-042 |
| `contingencia` | Consultar reservas e seus movimentos | ISSUE-041 |
| `desembolso` | Consultar e exportar previsão de caixa | ISSUE-043 |
| `contrato` | Ficha do contrato pelo número: resumo, medições, aditivos e exports | ISSUE-032 a ISSUE-034 |
| `contratos` | Lista consolidada e indicadores da administração contratual | ISSUE-035 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## O que a ISSUE-029 trouxe

* **Tela EAC** (`financeiro/eac`): árvore (linha 0 do projeto, pacote, subpacote, item) com recolher e expandir, filtros de busca, nível e tipo de custo, KPIs e total filtrado. Totais de pacote e subpacote somados no servidor, em centavos. No Portfólio a árvore é somente leitura: linha 0 = portfólio, nível 1 = projeto ("código · nome"), nível 2 = pacotes principais, com a coluna de peso na carteira.
* **Rotas** (`routes.py`): `GET /api/financeiro/eac` (conteúdo), `GET /eac/itens/{id}/editar` (formulário cadastral com histórico), `POST /eac/itens/{id}` (grava), `GET /eac/excel` e `GET /eac/imprimivel` (mesmo conteúdo e filtros da tela; no Portfólio com a coluna Projeto).
* **Edição cadastral**: descrição, tipo de custo, classificação CAPEX/OPEX, centro de custo e responsável. Não muda valor, dispensa SM, exige justificativa e fica no histórico do item (`service.edit_item_registry`, `service.item_history`); controle de versão com 409.
* **Ponderação da carteira**: `service.portfolio_weights` lê o orçamento vigente da EAC e as notas dos projetos e aplica `calculations.portfolio_weights` (critérios normalizados) fechado em 100,00 por `calculations.largest_remainder`. A edição da ponderação é da ISSUE-080.
* **Carga e oráculo**: `seed.py` grava a EAC dos mocks; `tests/financeiro/test_eac_oraculo.py` afirma BAC de R$ 44,6 mi no projeto 1 e pesos 55,36 / 29,34 / 15,30.

## O que a ISSUE-030 trouxe

* **Tela EAC** (ISSUE-029 + ISSUE-030): a árvore da ISSUE-029 ganhou os painéis "Revisões do orçamento" (linha de base, variação, SM e autor) e "Remanejamentos" (aplicados e pendentes, com o saldo livre da origem e o pendente em destaque), carregados por GET depois do conteúdo. No painel das revisões, os botões **Nova revisão** (formulário no próprio painel, com SM aprovada, item, valor e justificativa) e **Importar itens** (modal com a SM, a justificativa e a planilha do modelo); no painel dos remanejamentos, **Remanejar** (origem com saldo livre, destino, valor, prioridade e justificativa) e **Novo item** (subpacotes, código sugerido pelo `next_item_code`, cadastro e a origem do recurso: remanejamento de outro item ou nova revisão). Permissões só no servidor: sem escrita, os botões e formulários não são renderizados; no Portfólio os painéis são só leitura.
* **Toda alteração de valor passa pela SM.** Remanejamento entre itens e item novo com recurso de outro item abrem uma SM do tipo "Remanejamento de orçamento" (`service.reallocate`); até a decisão o valor fica reservado na origem e aparece em "Remanejamentos" como pendente. A aprovação aplica as transferências na EAC, na mesma transação da decisão, conferindo o saldo livre de novo (`service.apply_reallocations`); a rejeição libera a reserva. O item novo nasce na abertura da SM com base zero e recebe o valor na aprovação.
* **Acréscimo ao total só por revisão** a partir de SM aprovada com custo (papel Gestor): `service.create_revision` exige a SM, confere o custo aprovado, consolida os remanejamentos aplicados e congela a linha de base de todos os itens de nível 3 em `eac_revisao_item`. Rev 0 é a linha de base; `mudanca.eac_revisao_incorporada` guarda a revisão que incorporou o custo da SM e o encerramento da SM é recusado enquanto ela não existir.
* **Painéis e rotas** (`routes.py`): `GET /eac/revisoes` e `GET /eac/remanejamentos` leem as tabelas e trazem as opções dos formulários (itens com saldo livre, subpacotes, SM aprovadas com custo, unidades e pessoas; no Portfólio, com o projeto em cada linha e sem ações); `POST /eac/remanejamentos` abre a SM, `POST /eac/revisoes` cria a revisão e `POST /eac/itens` cria o item novo (por remanejamento ou revisão). O erro volta no próprio painel, com 422 e a mensagem. As opções vêm de `service.item_options`, `service.subpackage_options`, `service.revision_source_options` e `service.next_revision`.
* **Importação de itens por planilha**: o importador `eac-itens` (`importers.py`) confere linha a linha contra a EAC (código de três níveis, subpacote existente, código livre, unidade e responsável no cadastro). A tela abre o formulário no modal (`GET /eac/revisoes/importar/formulario`), a conferência (`POST .../importar/conferir`) mostra o resultado e atualiza os dois painéis, e a confirmação (`POST .../importar/confirmar`) checa de novo e cria a revisão vinculada à SM com os itens novos. A confirmação genérica recusa a linha: item da EAC não entra sem revisão.
* **Exportação**: o Excel e a versão imprimível da tela levam as tabelas "Revisões do orçamento" e "Remanejamentos" no mesmo documento da árvore.
* **Carga e oráculo**: a parte `governanca-eac` (`governanca/seed.py`) grava as transferências do protótipo em `mudanca_remanejamento` e chama `financeiro/seed.py::load_revisions`, que grava as revisões com a linha de base congelada e os remanejamentos aplicados apontando para a próxima revisão; `tests/financeiro/test_eac_revisoes_oraculo.py` confere os números do mock.

## O que a ISSUE-031 trouxe

* **Tela Mapa de controle** (`financeiro/mapa_controle`): os cinco KPIs do escopo (orçado atual, comprometido, realizado, projeção no término e desvio no término, cada um com a faixa do desvio no rótulo) e a grade item a item, com subtotal de pacote e subpacote e a linha do projeto; na carteira, um registro por projeto e a coluna Projeto. A grade visível é o visual **Tabela Heatmap** (`data-grafico`/`data-dados`, D11): os valores em R$ mil e o desvio pintado pelas faixas vigentes — sobrecusto na família `erro` e economia na família `ok` —, sempre com sinal, ícone e o nome da faixa na dica e para o leitor de tela; a cor nunca é o único sinal. A tabela servidora que vai dentro do visual (em reais integrais) é a versão sem JavaScript e a que os testes de rota leem. Botões **Excel** e **PDF** pelos mecanismos genéricos da plataforma (D12, ISSUE-017), com o mesmo conteúdo em reais integrais.
* **Projeção no término por item**: o botão de projeção da tabela, ou a célula pintada do desvio no visual, abre o formulário no alvo `mapa-projecao-formulario` (`GET /mapa-de-controle/projecao/{item_id}/formulario`); a gravação (`POST /mapa-de-controle/projecao/{item_id}`) exige justificativa, recusa valor negativo ou abaixo do realizado do ERP e entra como fato manual datado no histórico do item (`service.update_projection`, tabela `eac_projecao`). O fato mais recente é a projeção vigente e, no empate de data, o do ERP vence (`calculations.latest_projections`); sem fato algum vale o orçado atual.
* **Importação dos custos do ERP**: o botão abre o formulário genérico (`GET /custos/importar/formulario`) no modal; a conferência (`POST .../importar/conferir`) lê a planilha e não grava nada, e a confirmação (`POST .../importar/confirmar`) checa de novo e grava um fato por item e mês (`service.import_erp_costs`, tabela `erp_custo`), substituindo o mês reimportado. O importador é o `custos-erp` (`importers.py`), com o modelo da ISSUE-018; no Portfólio a rota pede o projeto.
* **Rotas** (`routes.py`): `GET /api/financeiro/mapa-de-controle` (conteúdo do escopo), `GET .../mapa-de-controle/excel` e `GET .../mapa-de-controle/imprimivel` (os dois exports, em reais integrais e com a coluna Projeto na carteira), `GET .../mapa-de-controle/projecao/{item_id}/formulario` e `POST .../mapa-de-controle/projecao/{item_id}`, `GET /api/financeiro/custos/importar/formulario`, `POST .../custos/importar/conferir` e `POST .../custos/importar/confirmar`.
* **Carga e oráculo**: a parte `financeiro-custos` (`seed.py::load_erp_costs`) grava o fechamento do ERP do protótipo no mês da data de referência; `tests/financeiro/test_eac_mapa_oraculo.py` afirma a projeção no término do projeto 1 em R$ 45,26 mi e a soma da carteira.

## O que a ISSUE-032 trouxe

* **Tela Ficha do contrato** (`financeiro/contrato`): tela de detalhe aberta pelo número (`?numero=CT-...`), com a faixa de identificação (Nº, contratada, objeto, modalidade, situação e período vigente) e as abas **Resumo**, **Medições** e **Aditivos**, cada uma carregada por AJAX. A faixa fica fora das abas e chega junto do Resumo numa resposta multi-alvo, atualizada por `x-sync`. O Resumo traz os quatro KPIs (valor atual, medido aprovado, saldo a faturar e término vigente), a **cascata de valor** no visual `cascata-contrato` (`data-grafico`/`data-dados`, D11) e os dados do contrato; Medições traz o boletim (Nº, período, bruto, retenção, líquido, situação e motivo da devolução) com as ações do fluxo; Aditivos traz número, data, valor, dias, motivo e a SM de origem. Botões **Excel** e **PDF** pelos mecanismos genéricos (D12), com o mesmo conteúdo (KPIs, cascata e tabelas).
* **Fluxo da medição**: Em análise → Aprovada → Faturada → Paga, ou Devolvida com motivo obrigatório. As transições são formulários de um botão com a versão do registro (409 em edição simultânea); a devolução abre o formulário no alvo `contrato-formulario`; a aprovação alimenta o realizado do item da EAC do contrato, no mês do período, por um fato de `custo_erp` (upsert por item e mês); a operação é de quem gere o contrato. O disponível a medir desconta as medições Em análise.
* **Aditivo**: nasce aprovado ao ser registrado, valor negativo é supressão, os dias prorrogam o término vigente na mesma transação e a SM de origem, quando informada, precisa ser aprovada e do projeto do contrato (fachada da Governança).
* **Rotas** (`routes.py`): `GET /api/financeiro/contrato/resumo`, `/contrato/medicoes` e `/contrato/aditivos` (conteúdo das abas pelo `?numero=`); `GET /contrato/medicoes/nova`, `GET /contrato/medicoes/{id}/devolucao` e `GET /contrato/aditivos/novo` (formulários); `POST /contrato/medicoes` e `POST /contrato/aditivos` (criação); `POST /contrato/medicoes/{id}/aprovar`, `.../faturar`, `.../pagar` e `.../devolver` (transições); `GET /contrato/excel` e `GET /contrato/imprimivel` (exports). As operações devolvem os painéis atualizados numa resposta multi-alvo, com o formulário vazio; o 422 volta no formulário (medição e aditivo) ou no painel das medições (transição), e o 409 no mesmo lugar.
* **Anexos**: o contrato é um tipo de origem (`contrato`) para o mecanismo genérico de anexos (D5a), com o painel embutido no Resumo (`/api/anexos?origem=contrato&registro=...`); quem lê é quem alcança o módulo.
* **Carga e verificação**: a parte `financeiro-contratos` (`seed.py::load_contracts`, registrada pela carga da Governança) grava os contratos, aditivos e medições dos mocks; `tests/financeiro/test_contrato_calculos.py`, `test_contrato_validacao.py`, `test_contrato_servico.py` e `test_contrato_rotas.py` afirmam a cascata, o fluxo, o efeito na EAC e o aditivo; `tests/plataforma/test_carga_demonstracao.py` afirma a carga (9 contratos, 3 aditivos e 33 medições).

## O que a ISSUE-033 trouxe

* **Tela Ficha do contrato** (ISSUE-032 + ISSUE-033): a ficha ganhou as abas **Marcos de pagamento**, **Claims** e **Extensões de prazo**, carregadas por AJAX como as anteriores e com os botões **Excel** e **PDF** da própria aba (`data-tn-*` sobre `/contrato/marcos|claims|extensoes`). Marcos traz Nº com descrição e critério de aceite, %, valor e retenção calculados, data prevista com o atraso dos marcos pendentes (a linha atrasada sai com fundo `--erro-50` e barra `--erro-500`, além do texto), conclusão, situação com a evidência anexada e a soma dos percentuais no pé; Claims traz código `CLM-…`, direção, tipo com causa, descrição com cláusula, notificação com o alerta fora do prazo contratual (o último dia ainda está no prazo, e a linha também sai destacada), pleiteado e reconhecido com os dias, situação e o link da SM quando acordado; Extensões de prazo traz código `EOT-…` com o claim de origem, evento causador, dias solicitados e concedidos, classificação, método com o marco afetado, situação e o link da SM da linha de base.
* **Fluxo do marco**: Previsto → Evidência enviada → Aprovado → Faturado → Pago (`validation.MILESTONE_TRANSITIONS`). O marco nasce Previsto com descrição, critério de aceite, percentual inteiro e data prevista; a soma dos percentuais não passa dos 100% do contrato (`validation.check_milestone_pct`) e o valor e a retenção saem do percentual sobre o valor atual. A evidência (`service.send_milestone_evidence`) grava a data de conclusão e um anexo de verdade pela porta de anexos (D5a, origem `contrato_marco_pagamento`); a aprovação exige esse anexo (`validation.check_milestone_evidence`). O atraso só conta em marco Previsto ou com Evidência enviada, comparando a data prevista com a data corrente; faturar e pagar acompanham a medição vinculada.
* **Fluxo do claim e a SM da Governança**: Notificado → Em análise → Em negociação → Acordado, Rejeitado, Em disputa ou Encerrado (`validation.CLAIM_TRANSITIONS`). O tipo decide o obrigatório (Prazo pede dias, Custo pede valor, Prazo e custo pede os dois); a notificação não pode ser anterior ao evento e o alerta compara a data com o evento mais o prazo do contrato — o último dia ainda está no prazo. O Acordado grava o valor e os dias reconhecidos e abre a SM na Governança pela fachada dela, na mesma transação (`service._create_claim_change`), gravando o vínculo em `mudanca_id`; a decisão de mérito (`service.decide_claim`) só aceita Acordado ou Rejeitado.
* **Fluxo da EOT**: Solicitada → Em análise → Concedida (integral ou parcialmente) ou Negada (`validation.EXTENSION_TRANSITIONS`). A concessão exige dias concedidos e classificação, prorroga o término vigente (`calculations.extension_new_end_date`) e abre a SM da linha de base do cronograma na Governança (`service._create_extension_change`), na mesma transação; a Negada encerra a análise sem efeito no contrato. O claim de origem é opcional e, quando informado, precisa ser do contrato.
* **Rotas** (`routes.py`): `GET /api/financeiro/contrato/marcos`, `/contrato/claims` e `/contrato/extensoes` (conteúdo das abas pelo `?numero=`); `GET /contrato/marcos/novo`, `/contrato/marcos/{id}/evidencia`, `/contrato/claims/novo`, `/contrato/claims/{id}/atualizar`, `/contrato/claims/{id}/decidir`, `/contrato/extensoes/nova` e `/contrato/extensoes/{id}/decidir` (formulários; o da evidência manda o arquivo); `POST /contrato/marcos`, `POST /contrato/marcos/{id}/evidencia`, `.../aprovar`, `.../faturar`, `.../pagar`, `POST /contrato/claims`, `POST /contrato/claims/{id}/atualizar`, `.../decidir`, `POST /contrato/extensoes` e `POST /contrato/extensoes/{id}/decidir` (operações); `GET .../excel` e `.../imprimivel` de cada aba (exports, D12). As operações devolvem os painéis atualizados numa resposta multi-alvo, com o formulário vazio e a faixa de identificação sincronizada (`x-sync`); o 422 volta no formulário (criação) ou no painel (transição e decisão), e o 409 no mesmo lugar.
* **Anexos**: o marco de pagamento é um tipo de origem (`contrato_marco_pagamento`) e o claim, outro (`contrato_claim`), para o mecanismo genérico de anexos (D5a); quem lê é quem alcança o módulo (`service.read_milestone_origin`, `service.read_claim_origin`). O formulário da evidência usa o campo e os limites do grupo Anexos vigentes.
* **Carga e verificação**: a parte `financeiro-contratos-fluxos` (`seed.py::load_contract_flows`, registrada pela carga dos Riscos, que roda depois de `financeiro-contratos`) grava os 14 marcos, 7 claims e 4 EOT dos mocks, liga as medições e os aditivos aos marcos e claims e o claim do mock ao risco; `tests/financeiro/test_contrato_fluxos_servico.py`, `test_contrato_marcos_calculos.py`, `test_contrato_marcos_validacao.py` e `test_contrato_fluxos_rotas.py` afirmam os fluxos, as fórmulas, o alerta de fronteira, as SMs e as abas; `tests/plataforma/test_carga_demonstracao.py` afirma a carga dos três fluxos.

## O que a ISSUE-034 trouxe

* **Tela Ficha do contrato** (ISSUE-032 a ISSUE-034): a ficha ganhou a aba **Avaliação de desempenho**, carregada por AJAX como as anteriores e com os botões **Excel** e **PDF** da própria aba (`data-tn-*` sobre `/contrato/avaliacoes`). A aba traz o **Gráfico de Áreas de Avaliação** (`data-grafico="areas-avaliacao"`, D11) — a nota ponderada de cada avaliação sobre as faixas de classe vigentes —, a tabela (período com o comentário, tipo, avaliador, nota e peso congelados de cada critério, nota ponderada, classe com a descrição e o plano de melhoria com a evidência anexada) e o formulário **Nova avaliação** no alvo `contrato-formulario`, com as notas de 1 a 5, o comentário e o arquivo de evidência. A nota no limite ou menor sai na tabela na família de erro (`contrato-avaliacao__nota-baixa`) e, no formulário, um aviso ao vivo aparece assim que alguma nota alcança o limite.
* **Avaliação**: período de um mês (`type=month`), tipo Mensal ou Final e uma nota de 1 a 5 por critério vigente; o comentário é opcional (até 400 caracteres). A avaliação não tem fluxo de situação: nasce registrada com o avaliador e a versão dos parâmetros, e o mesmo contrato não aceita duas avaliações do mesmo tipo no mesmo período (`service._check_evaluation_duplicate`). Os pesos e as notas ficam **gravados na avaliação** em `contrato_avaliacao_criterio` (D5b): mudar o parâmetro depois não muda a avaliação gravada.
* **Nota, classe e plano**: a nota ponderada vai de 0 a 100 (`calculations.evaluation_weighted_score`, meio para cima); a classe é a de maior mínimo que a nota alcança (`calculations.evaluation_class`); a nota no limite ou menor em qualquer critério (`calculations.evaluation_requires_plan`, pela `notaExigePlano` do grupo) exige o anexo de evidência — `service.create_evaluation` recusa sem ele — e abre a ação de plano de melhoria na Central com origem Contrato, grupo "Avaliação da contratada", responsável o gestor do contrato e prazo de 15 dias (`service._create_evaluation_plan_action`). A avaliação **Final** abre, na mesma transação (D9), a lição em Rascunho pela fachada de Lições, com origem no contrato: "A evitar" se exige plano e "A repetir" senão (`service._create_evaluation_lesson`).
* **Rotas** (`routes.py`): `GET /api/financeiro/contrato/avaliacoes` (aba), `GET /contrato/avaliacoes/nova` (formulário), `POST /contrato/avaliacoes` (gravação multipart, com o arquivo de evidência no campo `arquivo`), `GET /contrato/avaliacoes/excel` e `GET /contrato/avaliacoes/imprimivel` (exports, D12). A gravação devolve a aba atualizada e o formulário fechado na resposta multi-alvo; o 422 volta no formulário, com o que a pessoa digitou.
* **Anexos**: a avaliação é um tipo de origem (`contrato_avaliacao`) para o mecanismo genérico de anexos (D5a); quem lê é quem alcança o módulo (`service.read_evaluation_origin`).
* **Parâmetros**: o grupo `avaliacaoContratada` traz os critérios com peso, as classes com mínimo e descrição e a `notaExigePlano`; a versão vigente na data de referência rege a avaliação nova (os valores iniciais estão na seção Parâmetros).
* **Carga e verificação**: a parte `financeiro-contratos-avaliacoes` (`seed.py::load_evaluations`, registrada pela carga da Governança) grava as avaliações dos mocks com os pesos e as notas congelados; `tests/financeiro/test_contrato_avaliacao_calculos.py`, `test_contrato_avaliacao_validacao.py`, `test_contrato_avaliacao_servico.py` e `test_contrato_avaliacao_rotas.py` afirmam as fronteiras da nota e da classe (84/85, 69/70, 49/50), os pesos congelados, a evidência, a ação, a lição e as rotas; `tests/plataforma/test_carga_demonstracao.py` afirma a carga.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Valor orçado do item | Quantidade x preço unitário, em centavos | `calculations.budgeted_cents` |
| Orçado atual do item | Linha de base da última revisão mais os remanejamentos aplicados e ainda não consolidados | `calculations.current_base_cents` |
| Saldo livre do item | Orçado atual menos comprometido menos o reservado em outras SMs abertas | `calculations.free_balance_cents` |
| Próximo código do item | Próximo número livre entre os irmãos, sob o subpacote escolhido | `calculations.next_item_code` |
| SM aprovada com custo pendente de incorporação | SM em situação aprovada, com impacto em custo positivo, que nenhuma revisão incorporou ainda | `governanca.eac_revision_sources`, lida por `service.revision_source_options` |
| Variação da revisão | Total da revisão menos o total da revisão anterior do projeto | `service.revision_rows` |
| Total de pacote e subpacote | Soma dos itens abaixo, no servidor | `calculations.item_totals` |
| Árvore do projeto e da carteira | Linha 0, pacotes, subpacotes e itens; carteira em três níveis | `calculations.build_project_tree`, `calculations.build_portfolio_tree` |
| Maior resto | Fecha os pesos em 100,00 (duas casas) | `calculations.largest_remainder` |
| Peso do projeto na carteira | Soma dos critérios normalizados (valor financeiro, criticidade estratégica, complexidade, exposição a risco) | `calculations.portfolio_weights` |
| CPI | Valor agregado dividido pelo custo real (`EV / AC`) | `calculations.cost_performance_index` |
| SPI de custo | Valor agregado dividido pelo valor planejado (`EV / PV`) | `calculations.cost_schedule_index` |
| VAC | Orçamento no término menos Projeção no término | `calculations.variance_at_completion` |
| Linha de base do mapa | Base congelada da última revisão, sem os remanejamentos aplicados e ainda não consolidados | `calculations.baseline_base_cents` |
| Remanejamentos não consolidados | Orçado atual menos a linha de base do item | `calculations.reallocation_cents` |
| Saldo a comprometer | Orçado atual menos comprometido; negativo é sobrecusto | `calculations.saldo_a_comprometer_cents` |
| Desvio do mapa | Projeção no término menos orçado atual; positivo significa sobrecusto | `calculations.deviation_cents` |
| Desvio percentual | Desvio sobre o orçado atual, com uma casa; nenhum quando o orçado atual é zero | `calculations.deviation_percent` |
| Faixa do mapa de calor | Percentual do desvio classificado pelas faixas vigentes: neutro até a primeira, níveis 1 a 3 pelo segundo e o terceiro limites; sobrecusto na família `erro` e economia na `ok` | `calculations.deviation_band`, `calculations.deviation_heatmap_faixas` |
| Projeção no término do item e do projeto | Fato mais recente do histórico do item (manual ou do fechamento do ERP) e a soma dos filhos nos pacotes e subpacotes; sem fato, o orçado atual | `calculations.latest_projections`, `calculations.projected_total_cents` |
| Comprometido e realizado do mapa | Soma dos fatos do ERP do item até a data de corte (o mês do corte entra) | `calculations.erp_totals_until` |
| Saldo a pagar | Projeção no término menos realizado, distribuído pelos períodos futuros conforme o perfil previsto | `calculations.remaining_cash_flow` |
| Tendência financeira do relatório | `AC + (BAC - EV) / CPI` no corte do relatório, distribuída pelo perfil planejado e sem dados posteriores ao corte | `calculations.financial_eac_trend` |
| Valor atual do contrato | Valor original mais os aditivos aprovados | `calculations.contract_current_value_cents` |
| Medido aprovado do contrato | Soma do bruto das medições Aprovada, Faturada e Paga | `calculations.contract_measured_cents` |
| Saldo a faturar do contrato | Valor atual menos o medido aprovado | `calculations.contract_balance_to_invoice_cents` |
| Disponível a medir do contrato | Saldo a faturar menos as medições Em análise | `service.contract_detail` (campo `available_to_measure_cents`) |
| Retenção da medição | Bruto pela retenção contratual, meio centavo para cima | `service._retention_cents` |
| Término vigente do contrato | Término original mais os dias dos aditivos | `calculations.contract_current_end_date` |
| Degraus da cascata do contrato | Valor original (total), aditivos (variação), valor atual (total), medido (redução) e saldo a faturar (total) no contrato do visual | `calculations.contract_cascade_steps` |
| Valor do marco | Percentual do marco sobre o valor atual do contrato, meio centavo para cima | `calculations.milestone_value_cents` |
| Retenção do marco | Valor do marco pela retenção contratual, meio centavo para cima | `calculations.milestone_retention_cents` |
| Soma dos percentuais dos marcos | Soma que não passa de 100 por contrato; o cadastro recusa o que passaria | `calculations.milestone_pct_total`, `validation.check_milestone_pct` |
| Atraso do marco | Marco Previsto ou com Evidência enviada cuja data prevista é anterior à data corrente; os dias são a diferença | `calculations.milestone_is_late`, `calculations.milestone_late_days` |
| Prazo de notificação do claim | Data do evento mais os dias do contrato; notificar no último dia ainda está no prazo | `calculations.claim_notification_deadline`, `calculations.claim_notification_late` |
| Término vigente prorrogado pela EOT | Término vigente mais os dias concedidos da EOT | `calculations.extension_new_end_date` |
| Próximo código de claim e de EOT | Maior sequencial do prefixo `CLM-<padrão do projeto>-` ou `EOT-<padrão do projeto>-` mais um, com quatro dígitos | `service._code_prefix`, `service._next_code` |
| SM do claim acordado e da EOT concedida | Título, tipo, origem e descrição montados e gravados pela fachada da Governança, na mesma transação | `service._create_claim_change`, `service._create_extension_change` |
| Nota ponderada da avaliação | Soma das notas pelos pesos gravados na avaliação, dividida pelo peso somado e pela escala de 1 a 5, de 0 a 100, meio para cima; critério sem nota não conta nem o seu peso | `calculations.evaluation_weighted_score` |
| Classe da avaliação | A classe de maior mínimo que a nota alcança (a nota no próprio mínimo entra), com a descrição dos parâmetros | `calculations.evaluation_class` |
| Avaliação que exige plano | Alguma nota alcança a `notaExigePlano` do grupo (1 ou 2 inicialmente) | `calculations.evaluation_requires_plan` |
| Série do gráfico de avaliação | Um ponto por avaliação com nota, em ordem de período, para o Gráfico de Áreas de Avaliação | `calculations.evaluation_trend_points` |
| Ação do plano de melhoria | Ação da Central com origem Contrato, grupo "Avaliação da contratada", responsável o gestor e 15 dias, criada na transação da avaliação | `service._create_evaluation_plan_action` |
| Lição da avaliação final | Lição em Rascunho pela fachada de Lições, "A evitar" com plano e "A repetir" sem ele | `service._create_evaluation_lesson` |

`EAC` neste produto significa sempre Estrutura Analítica de Custos. O indicador *Estimate at Completion* é chamado **Projeção no término**. A tendência estatística por CPI do relatório é distinta da projeção bottom-up da equipe.

## Fluxos

Revisões da EAC, itens novos financiados e remanejamentos passam por SM aprovada; a aprovação aplica a mudança. A importação de itens por planilha passa pela conferência e gera uma revisão vinculada à SM aprovada. A projeção no término entra como fato datado com justificativa e a importação dos custos do ERP grava um fato por item e mês só na confirmação, substituindo o mês reimportado. Medições contratuais avançam Em análise → Aprovada → Faturada → Paga ou Devolvida com motivo; a aprovação soma o bruto ao realizado do item da EAC, no mês do período, e o aditivo nasce aprovado e prorroga o término vigente pelos dias informados. O marco de pagamento vai Previsto → Evidência enviada → Aprovado → Faturado → Pago, e a aprovação exige o anexo de evidência. O claim vai Notificado → Em análise → Em negociação → Acordado, Rejeitado, Em disputa ou Encerrado; o Acordado abre a SM na Governança na mesma transação. A EOT vai Solicitada → Em análise → Concedida (integral ou parcialmente) ou Negada; a concessão prorroga o término vigente e abre a SM da linha de base do cronograma. A avaliação de desempenho nasce registrada, sem fluxo de situação; a nota no limite exige o anexo de evidência e abre o plano de melhoria na Central, e a avaliação Final abre a lição de fornecedor em rascunho. Consumo ou liberação de reservas exige SM aprovada.

## Integrações

Suprimentos compromete custo quando emite pedido/contrato. Governança fornece SMs aprovadas e a alçada/comitê para remanejamentos, reservas e para a SM de origem do aditivo, e recebe pela fachada dela a SM do claim acordado e a da EOT concedida, na mesma transação. A avaliação da contratada entrega à Central a ação do plano de melhoria e à fachada de Lições a lição da avaliação final, na mesma transação, e guarda a evidência pela porta de anexos. Contratos alimentam o realizado do item da EAC (a medição aprovada vira fato de `custo_erp` no mês do período), o comprometido e o desembolso. O ERP entrega, por planilha, o fechamento do mês com comprometido, realizado e projeção; esses fatos são a base da Curva S financeira e do valor agregado (ISSUE-042), e a contingência compara o saldo com o desvio projetado (ISSUE-041). Riscos fornece VME para cobertura; Financeiro entrega KPIs à carteira e ao relatório. A comunicação entre módulos passa pelas fachadas donas.

## Parâmetros

Incluem faixas do mapa de calor (1%, 5%, 10% inicialmente), tolerância de consumo da contingência, cobertura mínima de exposição e critérios financeiros de gestão. São versionados em Configurações; o escopo detalhado entra nas ISSUE-041 a ISSUE-043 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Fluxo, permissões e integrações | `service.py` |
| Índices, projeções e desvios | `calculations.py` |
| Validações monetárias e de revisão | `validation.py` |
| Importadores de planilha (itens da EAC e custos do ERP) | `importers.py` |
| Carga de demonstração | `seed.py` |
| Excel/imprimível específico | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/financeiro/` |
| Tela, estilo e comportamento | `app/_views/financeiro/` e `app/paginas/financeiro/` |
| Visual Tabela Heatmap | `app/ds/graficos/tabela-heatmap.js`; contrato em `docs/styleguide-graficos.html` |
| Visual Cascata do contrato | `app/ds/graficos/cascata-contrato.js`; contrato em `docs/styleguide-graficos.html` |
| Visual Áreas de Avaliação | `app/ds/graficos/areas-avaliacao.js`; contrato em `docs/styleguide-graficos.html` |
| Testes | `api/tests/financeiro/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As issues de Financeiro completam este documento e acrescentam testes de fronteira para cada cálculo.
