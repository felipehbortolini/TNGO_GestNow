# Suprimentos

Módulo `suprimentos`. Planeja compras, conduz concorrências e acompanha aquisição, fabricação e entrega. O Mapa de Suprimentos (MAS) é uma projeção dos registros do módulo, não um cadastro duplicado.

A tela **Fornecedores** (ISSUE-057) está pronta: qualificação por empresa, documentos com validade, desempenho (com o OTD dos pedidos) e a ligação com a avaliação final do Financeiro. A tela **Plano de compras** (ISSUE-058) também está pronta: pacotes vinculados à EAC, datas da linha de base, ROS, folga planejada e importação. A tela **Processos de compra** (ISSUE-059/060) está pronta do início ao fim do fluxo: RFx, propostas com PDF, encerramento, equalizações, ranking, recomendação de adjudicação, aprovação por alçada com segregação de funções e emissão do pedido (com o cronograma de fabricação e o compromisso na EAC) ou do contrato no 03. A tela **Diligenciamento e recebimento** (ISSUE-061) está pronta: marcos de fabricação, folga sobre o ROS, ação na Central sem duplicar, recebimento com evidência e importação do ERP. A tela **Mapa de Suprimentos (MAS)** (ISSUE-062) está pronta: os doze marcos de cada pacote em dois grupos, as situações, o avanço ponderado pelo valor, o detalhe do pacote e as exportações (Excel e PDF A3 paisagem com as células coloridas). A tela **Painel de suprimentos** (ISSUE-063) fecha a entrega: os nove indicadores, a curva de contratação, o avanço físico do MAS, o saving acumulado, os pacotes por etapa e os pedidos por folga, com Excel e PDF.

## Telas

| Tela | Conteúdo | Issue |
|---|---|---|
| Fornecedores | Qualificação, documentos com validade e desempenho (com o OTD) | ISSUE-057 (pronta) |
| Painel de suprimentos | Indicadores, curva de contratação, avanço do MAS e pedidos críticos | ISSUE-063 (pronta) |
| Plano de compras | Pacotes, datas de linha de base, ROS e vínculo à EAC | ISSUE-058 (pronta) |
| Processos de compra | RFx, equalizações, ranking, alçada e emissão | ISSUE-059/060 (pronta) |
| MAS | Doze marcos de aquisição, fabricação e entrega | ISSUE-062 (pronta) |
| Diligenciamento e recebimento | Marcos, folga, ação na Central, recebimento e importação do ERP | ISSUE-061 (pronta) |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Fornecedores | `app/_views/suprimentos/fornecedores.html` | `app/paginas/suprimentos/fornecedores.css` | `app/paginas/suprimentos/fornecedores.js` |
| Painel de suprimentos | `app/_views/suprimentos/painel.html` | `app/paginas/suprimentos/painel.css` | `app/paginas/suprimentos/painel.js` |
| Plano de compras | `app/_views/suprimentos/plano_compras.html` | `app/paginas/suprimentos/plano_compras.css` | `app/paginas/suprimentos/plano_compras.js` |
| Processos de compra | `app/_views/suprimentos/processos.html` | `app/paginas/suprimentos/processos.css` | `app/paginas/suprimentos/processos.js` |
| Mapa de Suprimentos (MAS) | `app/_views/suprimentos/mas.html` | `app/paginas/suprimentos/mas.css` | `app/paginas/suprimentos/mas.js` |
| Diligenciamento e recebimento | `app/_views/suprimentos/diligenciamento.html` | `app/paginas/suprimentos/diligenciamento.css` | `app/paginas/suprimentos/diligenciamento.js` |

## Rotas

Prefixo `/api/suprimentos/`.

### Fornecedores (ISSUE-057)

A tela inteira é um fragmento só, `fornecedores-conteudo`: os seis KPIs, a barra de busca e filtros, a tabela do cadastro e a paginação. Tudo que muda a visão — um KPI, uma página, a busca, um filtro — é um GET da mesma rota com os filtros na consulta. Os modais (Novo fornecedor, Atualizar qualificação e Desempenho e histórico) abrem por JavaScript (o trio da tela) e o servidor entrega o corpo no alvo `fornecedor-modal-corpo`; a recusa (422, 409, 403) devolve o formulário preenchido no próprio modal. A leitura pede `Access(module="suprimentos")` e a gravação, `Permission.WRITE` — o Visualizador vê, não grava.

| Rota | Método | O que devolve |
|---|---|---|
| `fornecedores` | GET | A tela: KPIs, barra e tabela do cadastro; filtros `busca`, `situacao`, `categoria` e `pagina` |
| `fornecedores/excel` | GET | Excel do cadastro e dos KPIs do filtro (download, `file_route`) |
| `fornecedores/imprimivel` | GET | PDF do mesmo documento (`data-tn-pdf`, imprimível genérico) |
| `fornecedores/novo` | GET/POST | Formulário de Novo fornecedor; o POST cria a empresa no cadastro e a qualificação Em qualificação |
| `fornecedores/{empresa_id}/qualificacao` | GET/POST | Formulário de Atualizar qualificação; o POST grava situação, categorias, documentos e histórico |
| `fornecedores/{empresa_id}/desempenho` | GET | Modal de Desempenho e histórico, somente leitura |

### Plano de compras (ISSUE-058)

A tela inteira é um fragmento só, `plano-compras-conteudo`: os cinco KPIs, a barra de busca e filtros, a tabela dos pacotes e a paginação. Tudo que muda a visão é um GET da mesma rota com os filtros na consulta. Os modais (Novo pacote, Editar pacote e a importação genérica de Excel) abrem por JavaScript (o trio da tela) e o servidor entrega o corpo no alvo `pacote-modal-corpo`; a recusa (422, 409, 403) devolve o formulário preenchido no próprio modal. A leitura pede `Access(module="suprimentos")` e a gravação, `Permission.WRITE` — o Visualizador vê, não grava. No Portfólio a tabela ganha a coluna Projeto (e as exportações também) e os botões de inclusão passam pelo mecanismo do shell (`data-tn-incluir`), que pede o projeto antes de abrir o formulário.

| Rota | Método | O que devolve |
|---|---|---|
| `plano-de-compras` | GET | A tela: KPIs, barra e tabela; filtros `busca`, `tipo`, `lli` e `pagina` |
| `plano-de-compras/excel` | GET | Excel do plano e dos KPIs do filtro (download, `file_route`) |
| `plano-de-compras/imprimivel` | GET | PDF do mesmo documento (`data-tn-pdf`, imprimível genérico) |
| `plano-de-compras/novo` | GET/POST | Formulário de Novo pacote; o POST cria o pacote e os sete marcos da LB |
| `plano-de-compras/{pacote_id}/editar` | GET/POST | Editar pacote: completo antes da requisição; congelado depois dela |
| `/api/importacao/plano-de-compras` | GET/POST | Importação Excel pelo importador genérico (modelo, conferência e confirmação) |

### Processos de compra (ISSUE-059)

A tela é um fragmento só, `processos-conteudo`: os cinco KPIs, a barra de busca e filtros, a régua de nove etapas de cada processo (biblioteca de gráficos, visual Etapas) e a ficha do processo selecionado. O clique numa linha carrega a ficha sozinha no alvo `processo-ficha`; os modais das ações abrem por JavaScript (o trio da tela) e o servidor entrega o corpo no alvo `processo-modal-corpo`. A leitura pede `Access(module="suprimentos")` e a gravação, `Permission.WRITE` — o Visualizador vê, não grava. No Portfólio a tabela da exportação ganha a coluna Projeto e o botão "Nova requisição" passa pelo mecanismo do shell (`data-tn-incluir`), que pede o projeto antes.

| Rota | Método | O que devolve |
|---|---|---|
| `processos` | GET | A tela: KPIs, barra, régua de etapas e ficha; filtros `busca` e `situacao` (`andamento` ou `todos`) e `pacote` (a ficha aberta) |
| `processos/excel` | GET | Excel da lista e dos KPIs; com `pacote`, o mapa de equalização do processo (download, `file_route`) |
| `processos/imprimivel` | GET | PDF do mesmo documento (`data-tn-pdf`, imprimível genérico) |
| `processos/ficha` | GET | A ficha de um processo (`pacote`), para o clique na régua |
| `processos/requisicao` | GET/POST | Nova requisição: o pacote planejado e a data realizada do marco |
| `processos/{pacote_id}/acao/{nome}` | GET/POST | As ações do fluxo: `rfx`, `proposta`, `encerrar-recebimento`, `equalizacao-tecnica`, `equalizacao-comercial`, `negociacao`, `recomendacao`, `devolver`, `aprovar` e `emitir` |

### Diligenciamento e recebimento (ISSUE-061)

A tela é um fragmento só, `diligenciamento-conteudo`: os cinco KPIs, a barra de busca e filtros, o bloco dos pedidos críticos com tratamento pendente, a tabela dos pedidos e a ficha do pedido selecionado (os seis marcos de fabricação, o recebimento, a ação da Central e as últimas atualizações). Tudo que muda a visão — um KPI, uma página, a busca, um filtro ou a abertura de um pedido — é um GET da mesma rota com os filtros na consulta. Os modais (Atualizar marco, Registrar recebimento e a importação genérica do ERP) abrem por JavaScript (o trio da tela) e o servidor entrega o corpo no alvo `diligenciamento-modal-corpo`; a recusa (422, 409, 403) devolve o formulário preenchido no próprio modal. A leitura pede `Access(module="suprimentos")` e a gravação, `Permission.WRITE` — o Visualizador vê, não grava. No Portfólio a tabela ganha a coluna Projeto (e as exportações também) e o botão de importação passa pelo mecanismo do shell (`data-tn-incluir`), que pede o projeto antes.

| Rota | Método | O que devolve |
|---|---|---|
| `diligenciamento` | GET | A tela: KPIs, barra, pendências, tabela e ficha; filtros `busca`, `situacao` (`abertos` ou `todos`), `faixa` (`critico`, `atencao` ou `vencidos`), `pagina` e `pedido` (a ficha aberta) |
| `diligenciamento/excel` | GET | Excel da lista e dos KPIs; com `pedido`, os marcos do pedido (download, `file_route`) |
| `diligenciamento/imprimivel` | GET | PDF do mesmo documento (`data-tn-pdf`, imprimível genérico) |
| `diligenciamento/{pedido_id}/marco` | GET/POST | Atualizar marco: realizado (exige o anterior e data até a referência) ou nova previsão (com cascata) |
| `diligenciamento/{pedido_id}/recebimento` | GET/POST | Registrar recebimento na obra, com a evidência (anexo de verdade, D5a) |
| `diligenciamento/{pedido_id}/acao` | POST | Abre a ação de diligenciamento na Central; recusa quando já existe uma aberta |
| `/api/importacao/diligenciamento` | GET/POST | Importação do ERP pelo importador genérico (modelo, conferência e confirmação) |

### Mapa de Suprimentos (ISSUE-062)

A tela é um fragmento só, `mas-conteudo`: os seis KPIs, a barra de busca e filtros, os segmentos do conteúdo das células (Datas ou Desvio em dias) e da fase (Todos, Aquisição, Fabricação), a legenda, a tabela dos doze marcos por pacote com o rodapé dos realizados e previstos e as duas exportações. Tudo que muda a visão é um GET da mesma rota com os filtros na consulta (`busca`, `modo`, `fase`, `disciplina`, `tipo`, `lli`, `comprador`, `fornecedor`, `situacao`, `vencidos` e `ordem`). O MAS é só leitura: não tem formulário nem gravação. O clique numa célula abre o detalhe do pacote em modal (`mas-modal-corpo`), que o servidor entrega por GET. A leitura pede `Access(module="suprimentos")` — o Visualizador vê. No Portfólio a tabela abre com a coluna Projeto, e as exportações também.

| Rota | Método | O que devolve |
|---|---|---|
| `mas` | GET | A tela: KPIs, barra, legenda, tabela e rodapé; filtros `busca`, `modo`, `fase`, `disciplina`, `tipo`, `lli`, `comprador`, `fornecedor`, `situacao`, `vencidos` e `ordem` |
| `mas/excel` | GET | Excel do mapa: LB, previsão ou realizado e situação de cada marco (download, `file_route`) |
| `mas/imprimivel` | GET | PDF do mesmo documento em A3 paisagem, com as células coloridas (`data-tn-pdf`, imprimível genérico) |
| `mas/pacote/{pacote_id}` | GET | O detalhe do pacote no modal: os doze marcos com peso, LB, previsão, realizado, desvio e situação |

### Painel de suprimentos (ISSUE-063)

A tela é um fragmento só, `painel-conteudo`: os nove KPIs do protótipo, a barra das exportações, a grade 2x2 dos visuais (curva de contratação, avanço físico de suprimentos, saving acumulado e pacotes por etapa) e a tabela dos pedidos por folga em relação ao ROS. O painel é só leitura: não tem formulário, gravação nem filtros — tudo que a tela mostra é a visão calculada do plano, dos processos, dos pedidos e dos contratos na data de referência. A leitura pede `Access(module="suprimentos")` — o Visualizador vê. No Portfólio a tabela abre com a coluna Projeto, e as exportações também. Os três KPIs que apontam para outras telas (aderência, competitividade e pedidos críticos) são links para o plano de compras, os processos e o diligenciamento. O botão Análise do período chega na ISSUE-081.

| Rota | Método | O que devolve |
|---|---|---|
| `painel` | GET | A tela: os nove KPIs, os quatro visuais e a tabela dos pedidos por folga |
| `painel/excel` | GET | Excel do painel: o Resumo com os KPIs e a tabela Pedidos por folga (download, `file_route`) |
| `painel/imprimivel` | GET | PDF do mesmo documento em A4 paisagem, com os KPIs, os gráficos e a tabela (`data-tn-pdf`, imprimível genérico) |

## Fórmulas e nomes no código

O cadastro de fornecedores é global (a qualificação pertence à empresa do cadastro, não ao projeto), e nada derivado vira coluna: documentos em dia, desempenho e valor contratado são calculados a cada leitura (D5b).

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Documento vencido | Validade anterior à data de referência; o próprio dia da validade ainda vale | `calculations.document_is_expired` |
| Documento a vencer | Vence em até 30 dias, sem estar vencido | `calculations.document_is_expiring` |
| Qualificação vencida / a vencer | Mesma fronteira, com a janela de 90 dias | `calculations.qualification_is_expired`, `calculations.qualification_is_expiring` |
| Documentos em dia | Nenhum documento vencido; o fornecedor sem documento algum conta em dia | `calculations.documents_up_to_date`, `SupplierLine.documents_up_to_date` |
| Situação pela classe da avaliação final | Classe A ou B qualifica, C restringe e D bloqueia | `calculations.situation_for_evaluation_class` |
| Justificativa da mudança | Só a mudança de situação a exige (mínimo de 10 caracteres) | `calculations.justification_is_required` |
| Nota média | Média das notas das avaliações de contrato, uma casa, meio para cima | `calculations.average_score`, `SupplierLine.mean_score` |
| Valor contratado | Soma dos contratos da empresa no escopo | `SupplierLine.contracted_cents` (contratos de `financeiro.company_performance`) |
| Etapa do pacote | A do último marco de aquisição com data real; sem nenhuma, Planejado | `calculations.package_stage` |
| LB congelada | A requisição com data real congela a linha de base do pacote | `calculations.lb_frozen` |
| Datas do plano em ordem | requisição ≤ RFx ≤ adjudicação ≤ pedido (a igualdade vale) | `calculations.plan_dates_in_order` |
| Datas intermediárias do plano | Propostas na RFx + 21 dias (encurtadas a 40% da janela), equalização comercial 7 dias antes da adjudicação e técnica no meio | `calculations.derived_plan_dates` |
| Folga planejada | ROS menos o pedido planejado (o protótipo somava o prazo de entrega, que o modelo não tem) | `calculations.planned_slack_days` |
| Faixa da folga | Crítica abaixo de zero; atenção em até 7 dias; o parâmetro chega com as compras | `calculations.slack_band` |
| Desvio da adjudicação | Real, senão previsão, senão a referência, menos a LB; positivo é atraso | `calculations.adjudication_deviation_days` |
| Adjudicação atrasada | Sem data real e com a LB ou a previsão em atraso | `calculations.adjudication_overdue` |
| Próximo código do pacote | Prefixo do último código do projeto e o número seguinte, dois dígitos | `calculations.next_package_code` |
| Saldo a comprometer do item | Orçado atual da EAC menos o comprometido do ERP, na consulta (D9) | `financeiro.calculations.saldo_a_comprometer_cents` via `financeiro.service.cost_item_balances` |
| Aderência ao plano de compras | Pacotes adjudicados até a data divididos pelos pacotes planejados até a data | `calculations.purchase_plan_adherence` (ISSUE-063) |
| Avanço de suprimentos | Pesos dos marcos realizados/aplicáveis, ponderados pelo valor do pacote; previsto usa a linha de base; índice = real ÷ previsto | `calculations.package_progress`, `calculations.procurement_progress` (ISSUE-062) |
| Ciclo médio de compra | Média dos dias entre a requisição real e o pedido real dos pacotes adjudicados; em dias inteiros, meio para cima | `calculations.average_cycle_days` (ISSUE-063) |
| Saving sobre a estimativa e saving de negociação | (base − pago) ÷ base, em percentual; a base é a soma das estimativas dos adjudicados ou a soma das primeiras propostas vencedoras, e o pago é o adjudicado | `calculations.saving_pct` (ISSUE-063) |
| Compras emergenciais | Valor emergencial adjudicado dividido pelo valor adjudicado | `calculations.emergency_share` (ISSUE-063) |
| Comprometido x orçado | Valor adjudicado dividido pelo orçado atual dos itens da EAC ligados aos pacotes adjudicados (lido do mapa de controle, D9) | `calculations.committed_over_budget`, `service._panel_budget_cents` (ISSUE-063) |
| Competitividade | Média das propostas válidas dos pacotes com processo; percentual de fornecedor único (menos convidados que o mínimo do parâmetro) | `calculations.average_offers`, `calculations.single_supplier_share` (ISSUE-063) |
| Primeira proposta vencedora | Valor da proposta do fornecedor recomendado no processo vivo; sem processo, a coluna que a carga histórica trouxe (`pacote_compra.primeira_proposta_centavos`, m050) | `service._winner_first_proposal` (ISSUE-063) |
| Curva de contratação | Pacotes adjudicados acumulados por mês: o plano pela adjudicação planejada e o real pela adjudicação realizada, nulo depois do mês do corte | `calculations.contracting_curve` (ISSUE-063) |
| Saving acumulado | Saving por mês de adjudicação acumulado, sobre a estimativa e na negociação (o pacote sem primeira proposta não soma na segunda linha); nulo depois do corte | `calculations.saving_curve` (ISSUE-063) |
| Curva do avanço do MAS | Avanço ponderado pelo valor por mês: a LB até o fim do mês, o real até o corte (a referência no mês do corte) e a tendência pelo real, previsão ou LB; serviço renormaliza os marcos aplicáveis | `calculations.procurement_curve` (ISSUE-063) |
| Faixa do índice do avanço | No ritmo a partir de 1,00; próximo a partir de 0,95; abaixo disso | `calculations.progress_band` |
| LB estimada de fabricação | Pacote sem pedido interpola entre o pedido e o ROS pelas proporções da emissão (o modelo não tem a entrega planejada) | `calculations.estimated_fabrication_date` |
| Situação da linha do MAS | Entregue ou Contratado no fim do ciclo; Crítico com folga negativa; Atenção na faixa da folga ou com marco vencido; No prazo | `calculations.mas_line_situation` |
| Folga ROS | Dias entre a data necessária no local (ROS) e a previsão de entrega | `calculations.required_on_site_slack` (ISSUE-061) |
| OTD | Entregas até a data contratual divididas pelas entregas realizadas | `calculations.on_time_delivery` (ISSUE-061) |
| Etapa do processo | A da última ação registrada no histórico; sem histórico, a das datas reais do pacote | `calculations.process_stage`, `ProcessLine.stage` |
| Passo da régua | Concluído antes da etapa, em andamento na etapa e futuro depois; no fim do fluxo, todos concluídos | `calculations.step_situation` |
| Fornecedor único | Menos convidados que o mínimo do parâmetro (a RFx só aceita assim com justificativa) | `calculations.single_supplier` |
| Número da RFx | RFQ (material/equipamento) ou RFP (serviço/EPC) + ano + o maior número + 1, global como no protótipo | `calculations.next_process_number` |
| Alçada exigida | Primeira faixa das `alcadas` cujo teto cobre o valor; sem teto, a última | `calculations.approval_band_for` |
| Nota comercial | Menor preço tecnicamente aprovado ÷ preço x 100, uma casa, meio para cima | `calculations.commercial_score` |
| Nota final | (técnica x peso técnico + comercial x peso comercial) ÷ soma dos pesos, uma casa | `calculations.final_score` |
| Ranking das propostas | Nota final decrescente e preço crescente; reprovada fica fora | `calculations.proposal_ranking` |
| Ciclo de compra | Dias da requisição real ao pedido real, ou à data de referência | `calculations.cycle_days` |
| Justificativa da recomendação | Exigida quando a recomendação não é a melhor nota final ou o fornecedor não está qualificado | `calculations.recommendation_requires_justification` |
| Cronograma de fabricação padrão | As seis datas do pedido entre a emissão e a data contratual, nas proporções do protótipo (15%, 30%, 75%, 85%, 93% e 100%) | `calculations.manufacturing_schedule` |
| Folga do pedido | ROS menos a previsão de entrega; negativa é crítica | `calculations.delivery_slack_days` |
| Situação do marco de fabricação | Prazo, atraso, vencido (com os dias), previsto em atraso, a vencer ou sem data, na data de referência; não se aplica à fabricação de pacote de serviço/EPC (ISSUE-062) | `calculations.milestone_situation` |
| Atraso contratual | Entrega (ou previsão) menos a data contratual; positivo é atraso | `calculations.contractual_delay_days` |
| Situação do pedido | Entregue, Crítico, Atenção ou No prazo, pela faixa da folga e pelos marcos vencidos | `calculations.order_situation` |
| LLI antes do gate | Requisição real anterior ao início do projeto, sem a data do gate LLI registrada no pacote | `calculations.lli_before_gate` |
| Número do pedido e do contrato | Série global do ano, maior número do prefixo + 1, três dígitos (`PED-2026-001`, `CT-2026-001`) | `core.numbering.next_series_number` |
| Limite do saldo da EAC | O valor recomendado não supera o saldo a comprometer do item (orçado atual − comprometido) | `validation.eac_balance_problem` via `financeiro.calculations.saldo_a_comprometer_cents` |

## Fluxo de qualificação (ISSUE-057)

**Novo fornecedor** cria a empresa no cadastro de Configurações (a fachada `configuracoes.create_company`) e a qualificação nasce **Em qualificação**, com o histórico de abertura; o nome repetido é recusado. **Atualizar qualificação** grava situação, validade, categorias, documentos e observação: a mudança de situação exige justificativa (mínimo de 10 caracteres) e **Restrito** ou **Bloqueado** exigem o motivo (a observação ou a justificativa); **Qualificado** exige validade futura. Só a mudança de situação gera a linha de histórico — com de/para, autor e justificativa, um fato imutável —, e gravar mantendo a mesma situação não duplica histórico, como no protótipo. Os documentos são editados por linha, cada um com a própria versão; o formulário abre os três documentos iniciais em branco.

Os seis KPIs contam o universo (os filtros cortam a tabela): cadastrados, qualificados, em qualificação, restritos ou bloqueados, documentos vencidos e qualificação a vencer (vencida ou em até 90 dias). "Sem qualificação" é a situação das empresas do cadastro ainda sem cadastro de fornecedor — inclusive as que chegaram com a Programação Semanal.

**Desempenho e histórico** mostra a classe e a nota das avaliações de contrato (as do módulo 03, lidas por `financeiro.company_performance`), os contratos e o valor contratado; a lista e o valor seguem o escopo aberto — o cadastro é global, mas no Portfólio o desempenho soma os contratos dos projetos e no projeto fica só com os dele. O OTD dos pedidos entra na ISSUE-061.

**Ligação com o Financeiro (D9)**: a avaliação final de um contrato (ISSUE-034) atualiza a qualificação existente pela porta `service.apply_final_evaluation`, registrada como ouvinte em `financeiro.register_final_evaluation_listener` e chamada na mesma transação da avaliação; A e B requalificam, C restringe e D bloqueia, e cada mudança entra no histórico com justificativa automática. Quem não tem cadastro não é criado por efeito colateral: o cadastro é um ato humano ("Novo fornecedor").

## Fluxo do plano de compras (ISSUE-058)

**Novo pacote** nasce vinculado a um item de custo (nível 3) da EAC do projeto — sem ele, a fachada recusa; o item vem do cadastro da EAC lido na consulta (o select do formulário mostra o saldo a comprometer de cada um, calculado na hora) e o código segue a sequência do projeto (`PC-01`, `CB-PC-01`...). A fachada grava o pacote e os sete marcos de aquisição (requisição, RFx, propostas, equalização técnica, equalização comercial, adjudicação/aprovação e pedido) numa transação, com a trilha e a versão; as três datas intermediárias são derivadas do RFx e da adjudicação, como no protótipo. Regras do plano: as datas crescem (requisição ≤ RFx ≤ adjudicação ≤ pedido), o plano não nasce com folga negativa (ROS menor que o pedido é recusado), a compra emergencial é marcada e justificada (mínimo de 20 caracteres) e o LLI contratado antes do gate de investimento exige a aprovação específica (gate LLI, com a data do salvamento e a referência digitada).

**Depois da requisição** (o marco com data real), a LB fica congelada: o formulário abre só com escopo, comprador, estimativa e ROS, e qualquer campo da linha de base no POST é recusado com 422. As mudanças permitidas exigem justificativa (mínimo de 10 caracteres) e ficam na trilha; nada mudando, nada é gravado. Cada marco é uma linha com as três camadas (plano/LB, previsão e real), com versão própria e o antes/depois na auditoria (decisão da ISSUE-004). O histórico do pacote (campos alterados e justificativa) vive na auditoria, na entidade `pacote_compra.historico` — o protótipo o guardava no registro, e o modelo o mandou para a trilha; a justificativa da emergência, que não tem coluna, viaja na mesma linha. A etapa, a folga e o desvio da adjudicação são calculados na leitura; adjudicado, fornecedor, saving, primeira proposta, propostas válidas e fornecedor único dependem do processo (ISSUE-059) e do pedido (ISSUE-061) e saem vazios/— até lá (decisão registrada).

**Importar Excel** usa o importador genérico (`/api/importacao/plano-de-compras`): o modelo traz as colunas do protótipo — sem a coluna do prazo de entrega, que o modelo não tem — e a conferência valida linha a linha (item de nível 3, comprador e disciplina dos cadastros, datas crescentes e folga não negativa); a gravação passa pela mesma fachada, com a nota "Importado do plano de compras (planilha)" no histórico. O modal da importação abre pelo `data-tn-incluir="importar"` (no Portfólio o projeto é pedido antes) e a tela se refaz quando ele fecha.

## Fluxo do processo de compra (ISSUE-059/060)

O processo nasce na **Emitir RFx** (a etapa do pacote é Requisição): o número sai da série global do tipo (`RFQ-2026-014` para material e equipamento, `RFP-...` para serviço e EPC), os convidados são fornecedores do cadastro — fornecedor Bloqueado é recusado e o mínimo de convidados é `propostasMinimas`, salvo fornecedor único com justificativa (mínimo de 20 caracteres) —, os pesos somam 100 e o prazo das propostas não antecede a emissão. A emissão grava a data realizada do marco `rfx`, a previsão do marco `propostas` e a linha do histórico. **Registrar proposta** aceita o fornecedor do cadastro ou um nome sem cadastro (`nome`), recusa bloqueado e repetido, exige o PDF — anexo de verdade pelo tipo de origem `processo_proposta` (D5a) — e a primeira proposta move a etapa para Propostas recebidas. **Encerrar recebimento** grava a data realizada do marco `propostas` e, abaixo do mínimo, exige justificativa. **Equalização técnica** dá nota e aprovação a cada proposta (a reprovada fica fora do mapa comercial; sem nenhuma aprovada a fachada recusa) e grava o marco `eqTecnica`; abaixo do mínimo de aprovadas exige justificativa. **Equalização comercial** grava os pesos (com a versão da tela), o marco `eqComercial` e o ranking calculado. **Registrar negociação** grava um fato imutável com uma proposta aprovada, nunca acima do valor original. Cada ação grava a linha do histórico na auditoria, na entidade `processo_compra.historico`, com a etapa que a ação alcançou, o autor e o texto do feed; a requisição é a exceção: como o processo ainda não existe, ela grava a linha no histórico do pacote (`pacote_compra.historico`), com o documento e a observação (que não têm coluna) na mesma linha. A etapa do processo sai da última linha do histórico — o PC-14 da demonstração fica em "Equalização comercial" mesmo com as datas reais parando na técnica, como o protótipo —, e a ficha mostra a régua, o resumo, o mapa de equalização (notas, ranking, desvios e anexos) e o histórico. A recomendação, a aprovação por alçada e a emissão de pedido/contrato completam o fluxo (ISSUE-060, abaixo).

**Recomendar adjudicação** (ISSUE-060) só aceita proposta aprovada tecnicamente e fornecedor do cadastro; recomendação que não é a melhor nota final, ou fornecedor que não está qualificado, exige justificativa (mínimo de 20 caracteres) e fornecedor bloqueado é recusado. A recomendação preenche as colunas `recomendacao_*` e o passo vira "Recomendação de adjudicação". **Devolver** limpa a recomendação e volta à negociação, com o motivo (mínimo de 10 caracteres) na linha do histórico. **Aprovar adjudicação** recalcula a alçada exigida a partir do valor recomendado (as faixas vêm do parâmetro `alcadas`, nunca do código), exige aprovador diferente do comprador e de quem recomendou — recusa com 403 (segregação de funções) —, recusa o LLI requisitado antes do início do projeto sem a data do gate LLI no pacote e recusa o valor acima do saldo a comprometer do item da EAC; grava `aprovacao_*` e a data real do marco `adjudicacao`. **Emitir pedido ou contrato**: equipamento e material criam o `pedido` (número global `PED-2026-001` em diante) com os seis marcos de fabricação padrão entre a emissão e a data contratual (o prazo vem da proposta), e o pedido que nasce com folga negativa (ROS menos a previsão) abre a ação de diligenciamento na Central (origem Suprimentos, grupo Diligenciamento, responsável o comprador, prazo de 7 dias); serviço e EPC criam o contrato no 03 pela fachada `financeiro.create_purchase_contract` (`CT-2026-001` em diante, ligado ao `pacote_compra`). O valor fica comprometido na EAC pelo fato de `custo_erp` do mês da emissão (`financeiro.commit_purchase_cost`) e o marco `pedido` ganha a data real — tudo na transação do chamador, ou nada. A ficha mostra a recomendação, a aprovação e o documento emitido, com o atalho para o diligenciamento ou para o contrato.

## Fluxo do diligenciamento e recebimento (ISSUE-061)

A tela lê cada pedido do escopo com os seis marcos de fabricação (`pedido_marco`, com a LB contratual, a previsão e a realizada na mesma linha), o recebimento e o histórico (na auditoria, entidade `pedido.historico`), e calcula na leitura: a situação de cada marco (`calculations.milestone_situation`), a folga contra o ROS (`required_on_site_slack`), o atraso contratual e a situação do pedido (`calculations.order_situation`). Os KPIs contam o universo (os filtros cortam a tabela): pedidos em aberto e o valor a receber, críticos (e os LLI entre eles), em atenção (folga de até 7 dias ou marco vencido), marcos vencidos e o OTD das entregas (`calculations.on_time_delivery`, meta de 90%). O bloco de pendências lista os críticos sem ação aberta na Central.

**Atualizar marco** realiza um marco ou reprograma a previsão. A realização exige o marco anterior realizado e data até a data de referência; a previsão não fica no passado; a reprogramação pode deslocar os marcos seguintes na mesma quantidade de dias (a cascata do protótipo, desligável), e as previsões seguintes nunca ficam antes da anterior. A entrega (o sexto marco) não se realiza por aqui: a mensagem manda registrar o recebimento. Cada atualização grava o comentário na trilha e, se a folga ficar negativa, abre a ação de diligenciamento — **uma só**: `_open_diligence_action` pergunta à Central quantas ações abertas o pedido tem (`central_acoes.count_actions_of_origin`) e não cria a segunda. O botão "Gerar ação" da lista de pendentes usa o mesmo caminho (`open_diligence_action`), com recusa "Já existe ação aberta na Central para o pedido" quando há uma.

**Registrar recebimento** exige o embarque realizado; a data é até a referência e nunca antes do embarque; avarias exigem a descrição (mínimo de 10 caracteres). A gravação escreve a entrega no pedido e no marco `Entrega`, cria a linha `recebimento` (data, conferência, avarias com descrição e pendências) e guarda a evidência como anexo de verdade do registro (tipo de origem `recebimento`, D5a). Um pedido já recebido é recusado.

**Importar do ERP** usa o importador genérico (`/api/importacao/diligenciamento`): uma linha por marco, com o número do pedido, o marco, a previsão e a realizada — uma das duas datas é obrigatória. A conferência recusa pedido fora do escopo, marco desconhecido, data realizada futura e previsão no passado; a gravação passa por `service.apply_order_import_row`, que grava a previsão ou a realização, cria o recebimento pendente quando a linha é a entrega e deixa a nota "Atualizado pela importação do ERP (marco)" na trilha. A linha repetida do mesmo pedido e marco é recusada pela unicidade do importador (o protótipo aplicava as duas em ordem).

O OTD dos pedidos alimenta o **desempenho do fornecedor** (ISSUE-057): a fachada lê os pedidos do escopo por empresa e a ficha de desempenho mostra o OTD, os pedidos e a entrega contra a data contratual. O risco sugerido fica anotado para a ISSUE-067 e o FAT para a ISSUE-069 (não ligados nesta fatia); a ficha do pedido mostra "sem risco registrado (ISSUE-067)".

## Fluxo do mapa de suprimentos (ISSUE-062)

O MAS não tem cadastro próprio: `list_mas` monta cada linha do escopo lendo o plano de compras (os sete marcos de aquisição com as três camadas), o pedido do pacote (os cinco marcos de fabricação do cronograma contratual) e o processo (o número e o valor recomendado); a linha calcula na consulta a situação de cada um dos doze marcos (`calculations.milestone_situation`, com o `na` da fabricação de serviço/EPC), a folga contra o ROS, a situação da linha (`calculations.mas_line_situation`) e o avanço (`calculations.package_progress`). O valor do pacote é o do pedido, o da recomendação da adjudicação ou o do contrato nascido do pacote (`financeiro.purchase_contracts_by_package`, D9 — o vínculo dos contratos do mock é fechado pela parte do painel, ISSUE-063); sem nenhum, vale a estimativa e a tela avisa "estimado". Um pacote ainda sem pedido estima a LB e a previsão dos marcos de fabricação entre o pedido e o ROS pelas proporções da emissão (`calculations.estimated_fabrication_date`), com a célula em itálico e o aviso "LB estimada" (DECISION, ISSUE-062; DIVERGENCIAS-DO-PROTOTIPO).

Os seis KPIs contam o universo (os filtros cortam a tabela): itens, críticos, em atenção, marcos vencidos, realizados com atraso e o avanço de suprimentos com o índice (`calculations.procurement_progress` pondera o avanço de cada pacote pelo valor; o índice renormaliza só a aquisição nos serviços e compara real com o previsto da LB). O rodapé conta, por marco visível, os realizados sobre os previstos na LB até a referência. A alternância Datas/Desvio em dias e o filtro de fase mudam só o desenho das colunas; os filtros por disciplina, tipo, LLI, comprador, fornecedor, situação, "só vencidos" e a ordenação (código, folga, valor, avanço) são parâmetros da consulta. O clique numa célula abre o detalhe do pacote (o modal `mas/pacote/{pacote_id}`), com os doze marcos e os atalhos para o processo, o diligenciamento, o contrato e o plano.

**Exportação (D12)**: um `Document` só (`export.build_mas_document`) gera o Excel (as colunas do protótipo: os lados do pacote, LB, previsão ou real e situação de cada marco visível, os lados da linha e a situação) e o imprimível em **A3 paisagem** (`Paper.A3`), com o tom de cada situação nas células (no prazo em verde, com atraso e vencido em vermelho, previsão após a LB em âmbar, N/A em cinza; a vencer e sem data sem tom, como no protótipo).

## Fluxo do painel de suprimentos (ISSUE-063)

O painel não tem cadastro próprio: `service.list_panel` compõe numa leitura o plano (`_package_universe`), o mapa (`list_mas`) e os pedidos (`list_orders`) do escopo e calcula os nove indicadores, as três curvas acumuladas e a distribuição por etapa. O adjudicado de cada pacote é o valor do pedido, o da recomendação da adjudicação ou o do contrato nascido do pacote (`financeiro.purchase_contracts_by_package`, D9); a primeira proposta vencedora, as propostas válidas e o fornecedor único preferem o **processo vivo** e caem nas colunas que a carga histórica trouxe em `pacote_compra` (m050) — o mock do protótipo guardava esses agregados no pacote, e a demonstração só tem processo para 2 dos 14 pacotes (DECISION, ISSUE-063; DIVERGENCIAS-DO-PROTOTIPO). Os nove KPIs são: aderência ao plano de compras, ciclo de compra (com a linha de base), saving sobre a estimativa, saving de negociação, competitividade (média de propostas válidas e % de fornecedor único), OTD, pedidos críticos (com os LLI), compras emergenciais e comprometido x orçado; as metas de aderência e OTD saem do grupo `suprimentos` (90 e 90 nos parâmetros iniciais) e o mínimo de propostas do mesmo grupo, nunca do código.

Os quatro visuais nascem de `data-grafico` + `data-dados` (`export.panel_*_chart`, D11): a **curva de contratação** (pacotes adjudicados acumulados, plano x realizado), o **avanço físico de suprimentos** (Curva S do MAS: linha de base, real e tendência; o valor de cada pacote é o adjudicado ou a estimativa, e os serviços renormalizam a aquisição), o **saving acumulado** (em R$ mil, sobre a estimativa e na negociação) e os **pacotes por etapa** (a faixa de cartões `kpi-status` da biblioteca, com a etapa do processo vivo quando existe — o PC-14 da demonstração aparece em "Equalização comercial"). A tabela lista os pacotes não serviço com previsão de entrega, por folga crescente: pacote com o pedido ou a etapa, escopo com fornecedor e LLI, próximo marco, previsão de entrega, ROS, folga e situação. No Portfólio a tabela ganha a coluna Projeto.

**Exportação (D12)**: um `Document` só (`export.build_panel_document`) gera o Excel (a aba Resumo com os nove KPIs e a aba Pedidos por folga com as colunas da tela) e o imprimível em **A4 paisagem** (`Paper.A4`), com os KPIs, os quatro gráficos e a tabela.

## Integrações

Pacotes se vinculam à EAC do Financeiro; o saldo a comprometer do item é lido na consulta pela porta `financeiro.service.cost_item_balances` e o vínculo do pacote é resolvido pelos itens de custo lidos por `financeiro.service.eac_item_labels`/`eac_item_ids_by_code` — o plano só lê a EAC, nunca a tabela (D9). A emissão (ISSUE-060) grava o pedido no próprio módulo e chama o Financeiro na mesma transação: `financeiro.create_purchase_contract` cria o contrato de um serviço/EPC ligado ao `pacote_compra` (o gestor é o gerente do projeto e o prazo de notificação do claim vem do grupo `claims`) e `financeiro.commit_purchase_cost` soma o valor ao comprometido do item em `custo_erp` no mês da emissão; o número do contrato sai de `financeiro.contract_number_by_package` e o valor original, com o número, de `financeiro.purchase_contracts_by_package` (o painel e o MAS o leem como adjudicado do serviço, ISSUE-063). O orçado atual dos itens ligados aos pacotes adjudicados, para o KPI Comprometido x orçado, sai do mapa de controle do Financeiro (`financeiro.mapa_controle`, lido projeto a projeto). A folga negativa do pedido abre a ação de diligenciamento pela costura única da Central (`central_acoes.create_action`, origem Suprimentos), sempre precedida da pergunta de quantas ações abertas existem (`central_acoes.count_actions_of_origin`) para não duplicar; o diligenciamento lê a ação aberta de cada pedido pela mesma porta, nunca da tabela `acao`. O risco sugerido entra em Riscos com a ISSUE-067 e o FAT realizado registra inspeção em Qualidade com a ISSUE-069 (não ligados nesta fatia). O cadastro de empresas e pessoas é compartilhado com Configurações; o desempenho é lido do Financeiro (mais os pedidos do próprio módulo, para o OTD) e a avaliação final atualiza a qualificação (D9). O arquivo do documento do fornecedor como anexo ainda não foi ligado: no cadastro o documento tem nome e validade, como no protótipo; no processo, o PDF da proposta é anexo de verdade e, no diligenciamento, a evidência do recebimento também (tipo de origem `recebimento`).

## Parâmetros

Mínimo de propostas (3 inicialmente), dias de alerta de folga (7), metas de aderência e de OTD (90 e 90), alçadas de aprovação e pesos dos marcos do MAS (soma 100). O grupo `suprimentos` é lido pela fachada na consulta (`configuracoes.current_group`, sem versão vigente vale o inicial): o mínimo de propostas da RFx e das equalizações e a faixa da alçada saem de `propostasMinimas` e `alcadas`, o MAS lê os pesos dos doze marcos em `pesosMarcos` (`service._milestone_weights`, nunca no código) e o painel lê as metas em `metaAderenciaPct` e `metaOtdPct` (`service._panel_targets`, com a validação de 0 a 100% em `configuracoes.validation.supply_targets_error`). O prazo de notificação do claim do contrato emitido sai do grupo `claims` (`prazoNotificacaoPadraoDias`), lido pela fachada do Financeiro. Os alertas do cadastro (30 dias do documento e 90 da qualificação), os três documentos iniciais e o alerta da folga (7 dias, `calculations.SLACK_ALERT_DAYS`, usado pelo plano e pelo diligenciamento) ainda estão no código (`calculations.py` e `validation.py`); os demais parâmetros de compras entram na ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Qualificação, desempenho (com o OTD), plano de compras, processo, diligenciamento, mapa (`list_mas`, `find_mas_package`), painel (`list_panel`) e ligações | `service.py` |
| Fronteiras de validade, folga, etapa, datas do plano, notas, ranking, alçada, cronograma de fabricação, situação do marco, atraso contratual, situação do pedido, OTD, numeração, LB estimada, situação da linha e avanço do MAS; indicadores e curvas do painel (aderência, ciclo, savings, emergenciais, comprometido x orçado, competitividade e as curvas de contratação, saving e avanço) | `calculations.py` |
| Formulários, filtros (inclusive os do MAS) e recusas; validação das metas do painel | `validation.py` e `api/src/modulos/configuracoes/validation.py` (`supply_targets_error`) |
| Importação Excel (plano e ERP do diligenciamento) | `importers.py` (registrado em `routes.py`) |
| Excel e PDF imprimível (inclusive o A3 do MAS e o painel do 04) | `export.py` (`build_mas_document`, `build_panel_document`) |
| Persistência | `models.py`; migrações `m043_fornecedores.py`, `m046_pacotes_de_compra.py`, `m047_processos_de_compra.py`, `m048_pedidos_de_compra.py`, `m049_recebimento.py` e `m050_painel_de_suprimentos.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` (`suprimentos-fornecedores`, `suprimentos-pacotes`, `suprimentos-processos`, `suprimentos-pedidos`, `suprimentos-diligenciamento` e `suprimentos-painel`) |
| Fragmentos | `api/src/templates/suprimentos/` |
| Tela, estilo e comportamento | `app/_views/suprimentos/` e `app/paginas/suprimentos/` |
| Contrato e compromisso da emissão (D9) | `api/src/modulos/financeiro/service.py` (`create_purchase_contract`, `commit_purchase_cost`, `contract_number_by_package` e `purchase_contracts_by_package`) |
| Ação de diligenciamento e leitura por origem | `api/src/modulos/central_acoes/service.py` (`create_action` e `count_actions_of_origin`) |
| Testes | `api/tests/suprimentos/`, `api/tests/apoio_diligenciamento.py`, `api/tests/apoio_processos.py` e o oráculo em `api/tests/plataforma/test_carga_demonstracao.py` |

## Testes

- `test_fornecedores_calculos.py`: as fronteiras dos documentos e da qualificação, a classe da avaliação final, a justificativa e a nota média.
- `test_fornecedores_fachada.py`: a leitura por escopo, a gravação da qualificação com versão e trilha, as recusas e a ligação com a avaliação final (D9).
- `test_pacotes_calculos.py`: as fronteiras da etapa, da ordem e da folga, a derivação das datas intermediárias, o desvio e a atrasada da adjudicação e o código a partir do 100º pacote.
- `test_pacotes_fachada.py`: a leitura do plano, o saldo a comprometer lido da EAC (D9), o vínculo de nível 3, a folga negativa, o congelamento com justificativa e a trilha do histórico.
- `test_pacotes_importacao.py`: o importador registrado, a linha válida gravando com a nota de importação e as recusas do item de nível 2, da disciplina desconhecida e da folga negativa.
- `test_pacotes_rotas.py`: a tela, o formulário com o saldo, a recusa de 422 no modal, o campo da LB no pacote congelado e o 403 do Visualizador.
- `test_processos_calculos.py`: as fronteiras da nota comercial, da nota final, do ranking, da alçada, do fornecedor único, do passo da régua, do número da RFx e do ciclo.
- `test_processos_fachada.py`: cada ação do fluxo e as recusas (mínimo, bloqueado, pesos, técnica antes da comercial, reprovada fora do ranking, teto da negociação), a trilha e a versão.
- `test_processos_rotas.py`: a tela com a régua, a ficha com o mapa, os formulários, a recusa de 422 no modal, a proposta com PDF anexado e o 403 do Visualizador.
- `test_pedidos_calculos.py`: as fronteiras do cronograma de fabricação, da folga do pedido, da justificativa da recomendação, do gate LLI, da numeração global e do limite do saldo da EAC.
- `test_pedidos_fachada.py`: a recomendação (aprovada, cadastro, justificativa e bloqueado), a aprovação (403 da segregação, fronteira da alçada e do saldo, gate LLI), a devolução, a emissão do pedido (cronograma, compromisso na EAC e ação de diligenciamento) e do contrato, e o teste transversal de atomicidade.
- `test_pedidos_rotas.py`: os formulários da recomendação, da aprovação e da emissão, a recusa de 422 no modal, o 403 do Visualizador e o pedido criado pela rota.
- `test_diligenciamento_calculos.py`: as fronteiras da situação do marco, da folga do ROS, do atraso contratual, da situação do pedido e do OTD.
- `test_diligenciamento_fachada.py`: a leitura por escopo, a realização com o marco anterior e a data até a referência, a previsão com a cascata, o recebimento com a evidência (D5a), a importação do ERP e a ação de diligenciamento sem duplicar.
- `test_diligenciamento_rotas.py`: a tela, o formulário do marco e do recebimento, a recusa de 422 no modal, a ação criada pela rota e o 403 do Visualizador.
- `test_mas_calculos.py`: um teste por regra da situação do marco, incluindo o `na`; a LB estimada pelas proporções da emissão; a situação da linha; o avanço com a renormalização dos aplicáveis, a ponderação pelo valor e o índice.
- `test_mas_fachada.py`: a linha por pacote com os doze marcos nos dois grupos, a fabricação vinda do pedido e a estimada sem pedido, o `na` do serviço, o resumo com o avanço ponderado e os filtros (fase, tipo, LLI, comprador, fornecedor, situação, vencidos, busca e ordenação).
- `test_mas_rotas.py`: a tela (com o modo desvio e a fase), a coluna Projeto no Portfólio, o detalhe no modal com o aviso da LB estimada, o Excel com as colunas do protótipo em A3 e o imprimível A3 com as células coloridas.
- `test_painel_calculos.py`: uma fórmula por teste — aderência, ciclo médio, os dois savings, competitividade (média e fornecedor único), emergenciais, comprometido x orçado e as três curvas (contratação, saving e avanço, com o corte e a renormalização dos serviços).
- `test_painel_fachada.py`: a leitura do escopo com os indicadores e as curvas, o processo vivo na frente das colunas da carga, o adjudicado vindo do contrato, a tabela por folga (serviço fora) e as metas vindas dos parâmetros vigentes.
- `test_painel_rotas.py`: a tela com os KPIs e os quatro visuais, a coluna Projeto no Portfólio, o Excel com o Resumo e a aba Pedidos por folga e o imprimível A4 com os gráficos.
- `api/tests/plataforma/test_carga_demonstracao.py`: o oráculo da carga na âncora — as 17 qualificações do mock, o documento vencido, o histórico, as empresas sem qualificação, o desempenho, os 28 pacotes com as camadas dos marcos, os 4 processos com o PC-14 em equalização comercial, os 14 pedidos com os 84 marcos de fabricação, os 3 recebimentos do mock, o diligenciamento com 3 pedidos críticos (−20, −9 e −5) e OTD de 66,7%, o MAS do projeto com 14 linhas, 12 marcos, 3 críticos e o PC-14 com a LB de fabricação estimada, e o painel com aderência de 92,9%, saving de 5,2% sobre a estimativa e 4,7% na negociação e avanço de 90,9% x 97,3% (índice 0,93).
- `api/tests/apoio_suprimentos.py`, `api/tests/apoio_pacotes.py`, `api/tests/apoio_processos.py`, `api/tests/apoio_diligenciamento.py` e `api/tests/suprimentos/conftest.py`: os cenários e a sessão do teste.
