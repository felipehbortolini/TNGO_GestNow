# Suprimentos

Módulo `suprimentos`. Planeja compras, conduz concorrências e acompanha aquisição, fabricação e entrega. O Mapa de Suprimentos (MAS) é uma projeção dos registros do módulo, não um cadastro duplicado.

A tela **Fornecedores** (ISSUE-057) está pronta: qualificação por empresa, documentos com validade, desempenho e a ligação com a avaliação final do Financeiro. A tela **Plano de compras** (ISSUE-058) também está pronta: pacotes vinculados à EAC, datas da linha de base, ROS, folga planejada e importação. As demais telas ainda são esqueletos até as suas issues (ISSUE-059 a ISSUE-063).

## Telas

| Tela | Conteúdo | Issue |
|---|---|---|
| Fornecedores | Qualificação, documentos com validade e desempenho | ISSUE-057 (pronta) |
| Painel de suprimentos | Indicadores, curva de contratação, avanço do MAS e pedidos críticos | ISSUE-063 |
| Plano de compras | Pacotes, datas de linha de base, ROS e vínculo à EAC | ISSUE-058 (pronta) |
| Processos de compra | RFx, equalizações, ranking, alçada e emissão | ISSUE-059, ISSUE-060 |
| MAS | Doze marcos de aquisição, fabricação e entrega | ISSUE-062 |
| Diligenciamento e recebimento | Marcos, folga, riscos sugeridos, ação e recebimento | ISSUE-061 |

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

### Demais telas (previstas)

| Grupo previsto | Uso | Issue |
|---|---|---|
| `processos` | Etapas e decisões de compra | ISSUE-059, ISSUE-060 |
| `pedidos` | Marcos, recebimento e diligenciamento | ISSUE-061 |
| `mas` | Consultar mapa calculado dos doze marcos | ISSUE-062 |
| `painel` | Consultar indicadores do módulo | ISSUE-063 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

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
| Aderência ao plano de compras | Pacotes adjudicados até a data divididos pelos pacotes planejados até a data | `calculations.purchase_plan_adherence` (ISSUE-058) |
| Avanço de suprimentos | Pesos dos marcos realizados/aplicáveis, ponderados pelo valor do pacote; previsto usa a linha de base | `calculations.procurement_progress` (ISSUE-062) |
| Folga ROS | Dias entre a data necessária no local (ROS) e a previsão de entrega | `calculations.required_on_site_slack` (ISSUE-061) |
| OTD | Entregas até a data contratual divididas pelas entregas realizadas | `calculations.on_time_delivery` (ISSUE-061) |

## Fluxo de qualificação (ISSUE-057)

**Novo fornecedor** cria a empresa no cadastro de Configurações (a fachada `configuracoes.create_company`) e a qualificação nasce **Em qualificação**, com o histórico de abertura; o nome repetido é recusado. **Atualizar qualificação** grava situação, validade, categorias, documentos e observação: a mudança de situação exige justificativa (mínimo de 10 caracteres) e **Restrito** ou **Bloqueado** exigem o motivo (a observação ou a justificativa); **Qualificado** exige validade futura. Só a mudança de situação gera a linha de histórico — com de/para, autor e justificativa, um fato imutável —, e gravar mantendo a mesma situação não duplica histórico, como no protótipo. Os documentos são editados por linha, cada um com a própria versão; o formulário abre os três documentos iniciais em branco.

Os seis KPIs contam o universo (os filtros cortam a tabela): cadastrados, qualificados, em qualificação, restritos ou bloqueados, documentos vencidos e qualificação a vencer (vencida ou em até 90 dias). "Sem qualificação" é a situação das empresas do cadastro ainda sem cadastro de fornecedor — inclusive as que chegaram com a Programação Semanal.

**Desempenho e histórico** mostra a classe e a nota das avaliações de contrato (as do módulo 03, lidas por `financeiro.company_performance`), os contratos e o valor contratado; a lista e o valor seguem o escopo aberto — o cadastro é global, mas no Portfólio o desempenho soma os contratos dos projetos e no projeto fica só com os dele. O OTD dos pedidos entra na ISSUE-061.

**Ligação com o Financeiro (D9)**: a avaliação final de um contrato (ISSUE-034) atualiza a qualificação existente pela porta `service.apply_final_evaluation`, registrada como ouvinte em `financeiro.register_final_evaluation_listener` e chamada na mesma transação da avaliação; A e B requalificam, C restringe e D bloqueia, e cada mudança entra no histórico com justificativa automática. Quem não tem cadastro não é criado por efeito colateral: o cadastro é um ato humano ("Novo fornecedor").

## Fluxo do plano de compras (ISSUE-058)

**Novo pacote** nasce vinculado a um item de custo (nível 3) da EAC do projeto — sem ele, a fachada recusa; o item vem do cadastro da EAC lido na consulta (o select do formulário mostra o saldo a comprometer de cada um, calculado na hora) e o código segue a sequência do projeto (`PC-01`, `CB-PC-01`...). A fachada grava o pacote e os sete marcos de aquisição (requisição, RFx, propostas, equalização técnica, equalização comercial, adjudicação/aprovação e pedido) numa transação, com a trilha e a versão; as três datas intermediárias são derivadas do RFx e da adjudicação, como no protótipo. Regras do plano: as datas crescem (requisição ≤ RFx ≤ adjudicação ≤ pedido), o plano não nasce com folga negativa (ROS menor que o pedido é recusado), a compra emergencial é marcada e justificada (mínimo de 20 caracteres) e o LLI contratado antes do gate de investimento exige a aprovação específica (gate LLI, com a data do salvamento e a referência digitada).

**Depois da requisição** (o marco com data real), a LB fica congelada: o formulário abre só com escopo, comprador, estimativa e ROS, e qualquer campo da linha de base no POST é recusado com 422. As mudanças permitidas exigem justificativa (mínimo de 10 caracteres) e ficam na trilha; nada mudando, nada é gravado. Cada marco é uma linha com as três camadas (plano/LB, previsão e real), com versão própria e o antes/depois na auditoria (decisão da ISSUE-004). O histórico do pacote (campos alterados e justificativa) vive na auditoria, na entidade `pacote_compra.historico` — o protótipo o guardava no registro, e o modelo o mandou para a trilha; a justificativa da emergência, que não tem coluna, viaja na mesma linha. A etapa, a folga e o desvio da adjudicação são calculados na leitura; adjudicado, fornecedor, saving, primeira proposta, propostas válidas e fornecedor único dependem do processo (ISSUE-059) e do pedido (ISSUE-061) e saem vazios/— até lá (decisão registrada).

**Importar Excel** usa o importador genérico (`/api/importacao/plano-de-compras`): o modelo traz as colunas do protótipo — sem a coluna do prazo de entrega, que o modelo não tem — e a conferência valida linha a linha (item de nível 3, comprador e disciplina dos cadastros, datas crescentes e folga não negativa); a gravação passa pela mesma fachada, com a nota "Importado do plano de compras (planilha)" no histórico. O modal da importação abre pelo `data-tn-incluir="importar"` (no Portfólio o projeto é pedido antes) e a tela se refaz quando ele fecha.

## Integrações

Pacotes se vinculam à EAC do Financeiro; o saldo a comprometer do item é lido na consulta pela porta `financeiro.service.cost_item_balances` e o vínculo do pacote é resolvido pelos itens de custo lidos por `financeiro.service.eac_item_labels`/`eac_item_ids_by_code` — o plano só lê a EAC, nunca a tabela (D9). Pedido ou contrato emitido cria compromisso via fachada Financeira (ISSUE-059/061). Folga negativa gera ação na Central e risco sugerido em Riscos (ISSUE-061). FAT realizado registra inspeção em Qualidade. O cadastro de empresas e pessoas é compartilhado com Configurações; o desempenho é lido do Financeiro e a avaliação final atualiza a qualificação (D9). O arquivo do documento como anexo ainda não foi ligado: nesta fatia o documento tem nome e validade, como no protótipo.

## Parâmetros

Mínimo de propostas (3 inicialmente), dias de alerta de folga (7), alçadas de aprovação e pesos dos marcos do MAS (soma 100). Nesta fatia os alertas do cadastro (30 dias do documento e 90 da qualificação), os três documentos iniciais e o alerta da folga (7 dias, `calculations.SLACK_ALERT_DAYS`) estão no código (`calculations.py` e `validation.py`); os parâmetros próprios de fornecedores e compras entram nas ISSUE-059 a ISSUE-063 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Qualificação, desempenho, plano de compras e ligações | `service.py` |
| Fronteiras de validade, folga, etapa e datas do plano | `calculations.py` |
| Formulários, filtros e recusas | `validation.py` |
| Importação Excel | `importers.py` (registrado em `routes.py`) |
| Excel e PDF imprimível | `export.py` |
| Persistência | `models.py`; migrações `m043_fornecedores.py` e `m046_pacotes_de_compra.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` (`suprimentos-fornecedores` e `suprimentos-pacotes`) |
| Fragmentos | `api/src/templates/suprimentos/` |
| Tela, estilo e comportamento | `app/_views/suprimentos/` e `app/paginas/suprimentos/` |
| Testes | `api/tests/suprimentos/` e o oráculo em `api/tests/plataforma/test_carga_demonstracao.py` |

## Testes

- `test_fornecedores_calculos.py`: as fronteiras dos documentos e da qualificação, a classe da avaliação final, a justificativa e a nota média.
- `test_fornecedores_fachada.py`: a leitura por escopo, a gravação da qualificação com versão e trilha, as recusas e a ligação com a avaliação final (D9).
- `test_pacotes_calculos.py`: as fronteiras da etapa, da ordem e da folga, a derivação das datas intermediárias, o desvio e a atrasada da adjudicação e o código a partir do 100º pacote.
- `test_pacotes_fachada.py`: a leitura do plano, o saldo a comprometer lido da EAC (D9), o vínculo de nível 3, a folga negativa, o congelamento com justificativa e a trilha do histórico.
- `test_pacotes_importacao.py`: o importador registrado, a linha válida gravando com a nota de importação e as recusas do item de nível 2, da disciplina desconhecida e da folga negativa.
- `test_pacotes_rotas.py`: a tela, o formulário com o saldo, a recusa de 422 no modal, o campo da LB no pacote congelado e o 403 do Visualizador.
- `api/tests/plataforma/test_carga_demonstracao.py`: o oráculo da carga na âncora — as 17 qualificações do mock, o documento vencido, o histórico, as empresas sem qualificação, o desempenho e os 28 pacotes com as camadas dos marcos.
- `api/tests/apoio_suprimentos.py`, `api/tests/apoio_pacotes.py` e `api/tests/suprimentos/conftest.py`: os cenários e a sessão do teste.

As ISSUE-059 a ISSUE-063 completam este documento e acrescentam os testes de fronteira de cada tela.
