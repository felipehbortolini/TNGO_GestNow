# Suprimentos

Módulo `suprimentos`. Planeja compras, conduz concorrências e acompanha aquisição, fabricação e entrega. O Mapa de Suprimentos (MAS) é uma projeção dos registros do módulo, não um cadastro duplicado.

A tela **Fornecedores** (ISSUE-057) está pronta: qualificação por empresa, documentos com validade, desempenho e a ligação com a avaliação final do Financeiro. As demais telas ainda são esqueletos até as suas issues (ISSUE-058 a ISSUE-063).

## Telas

| Tela | Conteúdo | Issue |
|---|---|---|
| Fornecedores | Qualificação, documentos com validade e desempenho | ISSUE-057 (pronta) |
| Painel de suprimentos | Indicadores, curva de contratação, avanço do MAS e pedidos críticos | ISSUE-063 |
| Plano de compras | Pacotes, datas de linha de base, ROS e vínculo à EAC | ISSUE-058 |
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

### Demais telas (previstas)

| Grupo previsto | Uso | Issue |
|---|---|---|
| `plano-de-compras` | Pacotes planejados e importação | ISSUE-058 |
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
| Aderência ao plano de compras | Pacotes adjudicados até a data divididos pelos pacotes planejados até a data | `calculations.purchase_plan_adherence` (ISSUE-058) |
| Avanço de suprimentos | Pesos dos marcos realizados/aplicáveis, ponderados pelo valor do pacote; previsto usa a linha de base | `calculations.procurement_progress` (ISSUE-062) |
| Folga ROS | Dias entre a data necessária no local (ROS) e a previsão de entrega | `calculations.required_on_site_slack` (ISSUE-061) |
| OTD | Entregas até a data contratual divididas pelas entregas realizadas | `calculations.on_time_delivery` (ISSUE-061) |

## Fluxo de qualificação (ISSUE-057)

**Novo fornecedor** cria a empresa no cadastro de Configurações (a fachada `configuracoes.create_company`) e a qualificação nasce **Em qualificação**, com o histórico de abertura; o nome repetido é recusado. **Atualizar qualificação** grava situação, validade, categorias, documentos e observação: a mudança de situação exige justificativa (mínimo de 10 caracteres) e **Restrito** ou **Bloqueado** exigem o motivo (a observação ou a justificativa); **Qualificado** exige validade futura. Só a mudança de situação gera a linha de histórico — com de/para, autor e justificativa, um fato imutável —, e gravar mantendo a mesma situação não duplica histórico, como no protótipo. Os documentos são editados por linha, cada um com a própria versão; o formulário abre os três documentos iniciais em branco.

Os seis KPIs contam o universo (os filtros cortam a tabela): cadastrados, qualificados, em qualificação, restritos ou bloqueados, documentos vencidos e qualificação a vencer (vencida ou em até 90 dias). "Sem qualificação" é a situação das empresas do cadastro ainda sem cadastro de fornecedor — inclusive as que chegaram com a Programação Semanal.

**Desempenho e histórico** mostra a classe e a nota das avaliações de contrato (as do módulo 03, lidas por `financeiro.company_performance`), os contratos e o valor contratado; a lista e o valor seguem o escopo aberto — o cadastro é global, mas no Portfólio o desempenho soma os contratos dos projetos e no projeto fica só com os dele. O OTD dos pedidos entra na ISSUE-061.

**Ligação com o Financeiro (D9)**: a avaliação final de um contrato (ISSUE-034) atualiza a qualificação existente pela porta `service.apply_final_evaluation`, registrada como ouvinte em `financeiro.register_final_evaluation_listener` e chamada na mesma transação da avaliação; A e B requalificam, C restringe e D bloqueia, e cada mudança entra no histórico com justificativa automática. Quem não tem cadastro não é criado por efeito colateral: o cadastro é um ato humano ("Novo fornecedor").

## Integrações

Pacotes se vinculam à EAC do Financeiro. Pedido ou contrato emitido cria compromisso via fachada Financeira. Folga negativa gera ação na Central e risco sugerido em Riscos. FAT realizado registra inspeção em Qualidade. O cadastro de empresas e pessoas é compartilhado com Configurações; o desempenho é lido do Financeiro e a avaliação final atualiza a qualificação (D9). O arquivo do documento como anexo ainda não foi ligado: nesta fatia o documento tem nome e validade, como no protótipo.

## Parâmetros

Mínimo de propostas (3 inicialmente), dias de alerta de folga (7), alçadas de aprovação e pesos dos marcos do MAS (soma 100). Nesta fatia os alertas do cadastro (30 dias do documento e 90 da qualificação) e os três documentos iniciais estão no código (`calculations.py` e `validation.py`); os parâmetros próprios de fornecedores e compras entram nas ISSUE-058 a ISSUE-063 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Qualificação, desempenho e ligações | `service.py` |
| Fronteiras de validade e notas | `calculations.py` |
| Formulários, filtros e recusas | `validation.py` |
| Excel e PDF imprimível | `export.py` |
| Persistência | `models.py`; migração `m043_fornecedores.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` (`suprimentos-fornecedores`) |
| Fragmentos | `api/src/templates/suprimentos/` |
| Tela, estilo e comportamento | `app/_views/suprimentos/` e `app/paginas/suprimentos/` |
| Testes | `api/tests/suprimentos/` e o oráculo em `api/tests/plataforma/test_carga_demonstracao.py` |

## Testes

- `test_fornecedores_calculos.py`: as fronteiras dos documentos e da qualificação, a classe da avaliação final, a justificativa e a nota média.
- `test_fornecedores_fachada.py`: a leitura por escopo, a gravação da qualificação com versão e trilha, as recusas e a ligação com a avaliação final (D9).
- `api/tests/plataforma/test_carga_demonstracao.py`: o oráculo da carga na âncora — as 17 qualificações do mock, o documento vencido, o histórico, as empresas sem qualificação e o desempenho.
- `api/tests/apoio_suprimentos.py` e `api/tests/suprimentos/conftest.py`: o cenário e a sessão do teste.

As ISSUE-058 a ISSUE-063 completam este documento e acrescentam os testes de fronteira de cada tela.
