# Governança

Módulo `governanca`. Controla solicitações de mudança (SM) e lições aprendidas, processos transversais aos módulos do projeto. As funcionalidades chegam nas ISSUE-023 a ISSUE-028; integrações são ativadas na issue do módulo que chega por último (D9).

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Registro e painel de mudanças | Lista, etapa, próxima decisão e indicadores | ISSUE-023, ISSUE-026 |
| Ficha da mudança | Solicitação, impacto, decisão, implementação e histórico | ISSUE-023 a ISSUE-025 |
| Acervo de lições | Busca, filtros, aplicabilidade e aplicação em projeto | ISSUE-027 (pronta) |
| Painel de lições | Lições publicadas, reuso e projetos sem registro | ISSUE-028 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Gestão de mudanças | `app/_views/governanca/mudancas.html` | `app/paginas/governanca/mudancas.css` | `app/paginas/governanca/mudancas.js` |
| Solicitação de mudança | `app/_views/governanca/mudanca.html` | `app/paginas/governanca/mudanca.css` | `app/paginas/governanca/mudanca.js` |
| Lições aprendidas | `app/_views/governanca/licoes.html` | `app/paginas/governanca/licoes.css` | `app/paginas/governanca/licoes.js` |

## Rotas previstas

Prefixo: `/api/governanca/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `mudancas` | Criar/listar e consultar SM | ISSUE-023 |
| `mudancas/{codigo}/analise` | Registrar impacto e calcular alçada | ISSUE-024 |
| `mudancas/{codigo}/decisao` e `implementacao` | Decidir, integrar ações e encerrar | ISSUE-025 |
| `painel-de-mudancas` | Consultar indicadores de mudanças | ISSUE-026 |
| `licoes` e `licoes/{codigo}/aplicacoes` | Validar/publicar/aplicar lição | ISSUE-027 |
| `painel-de-licoes` | Consultar indicadores do acervo | ISSUE-028 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Alçada mínima da mudança | Gerente se o custo cabe no limite percentual do orçamento e não afeta marco contratual; caso contrário, Comitê | `calculations.minimum_change_authority` |
| Prazo de ratificação emergencial | Data de início mais o prazo configurado para a ratificação | `calculations.emergency_ratification_due_date` |

O analista pode elevar, mas não rebaixar, a alçada calculada. A pessoa que elabora uma lição não pode validá-la.

## Fluxos

SM: Registrada → Em análise de impacto → Aguardando decisão → Aprovada/Aprovada com condições/Rejeitada/Adiada → Em implementação → Encerrada. Cancelamento antes da decisão exige justificativa. Lição: Rascunho → Em validação → Validada → Publicada; devolução retorna a Rascunho com comentário.

## Integrações

Recebe impactos de Financeiro, Planejamento, Contratos e Riscos. Aprovação cria ações na Central e fornece SM para revisões donas de EAC/EAP/contratos. Lições podem nascer de Riscos, Qualidade, HSE e demais origens; sua aplicação cria ação na Central ou risco em Riscos. Cada escrita chama a fachada dona da entidade, na transação.

## Parâmetros

Limite de alçada do Gerente (até 1% do orçamento e sem impacto contratual inicialmente), quórum de Comitê (3), prazo de análise (10 dias), prazo de ações (15), ratificação emergencial (7) e alerta de lições sem registro (90 dias). São versionados em Configurações.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` e `lessons_routes.py` |
| Transições, permissões e integrações | `service.py` e `lessons_service.py` |
| Alçada e prazos derivados | `calculations.py` e `lessons_calculations.py` |
| Validação de impacto/decisão | `validation.py` e `lessons_validation.py` |
| Exportação | `export.py` e `lessons_export.py` |
| Persistência | `models.py` e `lessons_models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` (`governanca` e `governanca-licoes`) |
| Fragmentos | `api/src/templates/governanca/` |
| Tela, estilo e comportamento | `app/_views/governanca/` e `app/paginas/governanca/` |
| Testes | `api/tests/governanca/` e `api/tests/oraculo/test_oraculo_licoes.py` |

As ISSUE-025, ISSUE-026 e ISSUE-028 completam este documento (decisão, painel de mudanças e painel de lições).

## O que a ISSUE-023 trouxe (Registro e ficha da mudança)

**Telas.** Registro de mudanças (`mudancas`): barra de ações, seis KPIs (os três primeiros filtram a lista pela situação), filtros (busca, situação, tipo, origem, prioridade, alçada) e tabela com Excel e PDF; no Portfólio a primeira coluna é Projeto e "Nova solicitação" pede o projeto antes. Ficha (`mudanca`): alertas, faixa de identificação, barra de etapas e as cinco abas em leitura (Solicitação, Análise de impacto, Decisão, Implementação, Histórico), anexos e cancelamento. O trio de cada tela está na tabela acima.

**Rotas** (prefixo `/api/`, `routes.py`):

| Rota | Método | Uso |
|---|---|---|
| `governanca/mudancas` | GET | Registro (ou só os blocos `mudancas-kpis` e `mudancas-tabela` quando o filtro pede) |
| `governanca/mudancas` | POST | Registra a SM; 302 para a ficha; 422 devolve o formulário preenchido |
| `governanca/mudancas/nova` | GET | Formulário da nova solicitação (Portfólio sem projeto: 422) |
| `governanca/mudancas/excel` e `/imprimivel` | GET | Exportação do registro com os filtros da tela |
| `governanca/mudanca?codigo=` | GET | Ficha (404 se o número não existe) |
| `governanca/mudanca/excel` e `/imprimivel` | GET | Exportação da ficha |
| `governanca/mudanca/cancelar` | GET, POST | Formulário e cancelamento com justificativa (403, 422, 409) |

**Fórmulas** (`calculations.py`, todas recebem a data de referência): `change_stage` (etapa 0 a 4), `minimum_change_authority` (limite em centavos arredondado meio para cima; valor absoluto; marco contratual vai ao Comitê), `emergency_ratification_due_date`, `is_analysis_overdue`, `is_emergency_pending`, `is_ratification_overdue`, `next_step`, `summarize_changes` (KPIs), `percent_of` (uma casa, meio para cima, nulo sem orçamento), `mean_decision_days` (média arredondada meio para cima sobre as SMs com decisão), `change_history`.

**Fluxos.** Nova SM: número `SM-<padrão do projeto>-NNNN` pela sequência do projeto (`numbering.next_number`, tipo `mudanca`), situação Registrada; prioridade Emergencial com execução antecipada grava início (`data_inicio_implementacao`) e justificativa e abre a ratificação pendente. Cancelamento: só solicitante ou Gestor, só em Registrada, Em análise, Aguardando comitê ou Adiada; SM aprovada é recusada com a orientação de registrar nova SM.

**Carga e oráculo.** `seed.py` lê `prototype_collection("mudancas")` e grava pela fachada (`load_demonstration_change`), conferindo o número do protótipo; `remanejamentos` e `eacItens` esperam o Financeiro (D9). Oráculo em `api/tests/governanca/test_oraculo_mudancas.py` (11 SMs, 5 aprovadas, R$ 1.200.000,00 = 2,7%, +42 dias, 33 dias de decisão). Migração `m023_solicitacao_de_mudanca.py`.

**Testes.** `api/tests/governanca/`: `test_calculos.py`, `test_validacao.py`, `test_fachada.py`, `test_rotas.py`, `test_oraculo_mudancas.py`; `conftest.py` e `apoio.py` dão a sessão do teste às rotas.

## O que a ISSUE-024 trouxe (Análise de impacto e alçada)

**Telas.** Na ficha (`mudanca`), a barra de ações ganha **Iniciar análise** (SM Registrada), **Concluir análise de impacto** (Em análise de impacto) e **Rever análise de impacto** (Aguardando comitê ou Adiada), cada um abrindo um modal com o formulário do servidor (`mudanca.js`, atributo `data-mudanca-modal`). A aba Análise de impacto mostra custo, prazo, marco contratual, alçada (elevada ou mínima), limite do gerente, fonte do recurso, as cinco dimensões, os itens da EAC, as transferências (Remanejamento) e a reserva liberada (Liberação de reserva).

**Rotas** (prefixo `/api/`, `routes.py`; exigem Membro):

| Rota | Método | Uso |
|---|---|---|
| `governanca/mudanca/analise/iniciar?codigo=` | GET, POST | Formulário e início: responsável e prazo (padrão: hoje mais `prazoAnaliseDias`); 422 devolve o formulário |
| `governanca/mudanca/analise?codigo=` | GET, POST | Formulário (preenchido na revisão) e conclusão da análise; 302 para a ficha; 422 por campo |

**Fórmulas** (`calculations.py`): `required_change_authority` (alçada exigida: o maior entre o custo absoluto e o total remanejado vai a `minimum_change_authority`; Liberação de reserva e fonte Reserva gerencial vão sempre ao Comitê), `is_authority_lowered` (só o Gerente abaixo do Comitê é rebaixar), `analysis_deadline` (início mais dias do parâmetro). A alçada é calculada no servidor, também dentro da validação (`validation.validate_impact`), para a mensagem sair no campo `alcada`.

**Regras do formulário** (`validation.py`): custo em reais (centavos no banco; negativo é redução) e prazo em dias inteiros obrigatórios; marco contratual sim ou não; escopo, qualidade, riscos, SMS e contrato com 3 a 300 caracteres ("Sem impacto" vale); custo positivo exige a fonte do recurso (sem custo positivo a fonte não é guardada); Remanejamento tem custo zero e de 1 a 5 transferências (origem, destino, valor maior que zero, itens diferentes); Liberação de reserva tem custo zero, a reserva e o valor.

**Fluxos** (`service.py`): `start_analysis` cria a análise em andamento e leva a SM a Em análise de impacto; `conclude_analysis` grava o impacto (uma linha por SM, atualizada nas revisões), troca os itens da EAC e as transferências não aplicadas, fecha a análise em andamento, grava fonte e alçada na SM e leva Em análise de impacto a Aguardando comitê (a revisão mantém a situação). A Próxima etapa diz quem decide.

**Pontos para outros módulos.** Os itens vêm do Financeiro por `eac_item_ids_by_code` e `eac_item_codes` (que o item é de custo, nível 3, é conferido na ISSUE-030); o aviso de custo acima do saldo das reservas fica para a ISSUE-041. Migração `m024_analise_de_impacto.py`. Testes: `test_analise.py`, `test_validacao_analise.py`, `test_rotas_analise.py` e as fronteiras novas de `test_calculos.py`.

## O que a ISSUE-027 trouxe (Lições aprendidas)

**Telas.** Acervo de lições (`licoes`): contagem, cartões com situação/recomendação/aplicabilidade, KPIs por escopo, checklist de kickoff (botões de fase filtram as lições publicadas da fase), filtros (busca, fase, área, disciplina, tipo, origem, aplicabilidade, situação) e Excel/PDF. No Portfólio a lista traz a coluna Projeto e "Nova lição" pede o projeto antes. O trio está na tabela acima e o `licoes.js` abre os modais (ver, editar, validar, aplicar, nova), entregues pelo servidor.

**Rotas** (prefixo `/api/`, `lessons_routes.py`):

| Rota | Método | Uso |
|---|---|---|
| `governanca/licoes` | GET | Acervo com filtros; no Portfólio, coluna Projeto |
| `governanca/licoes` | POST | Cria a lição (Rascunho; `enviar=1` já manda para validação) |
| `governanca/licoes/excel` e `/imprimivel` | GET | Exportações do acervo no filtro |
| `governanca/licoes/nova` | GET | Formulário da nova lição |
| `governanca/licoes/ver`, `/editar`, `/validar` e `/aplicar` | GET, POST | Ficha, edição do rascunho, decisão da validação e reuso |
| `governanca/licoes/enviar` e `/publicar` | POST | Rascunho → Em validação e Validada → Publicada |

**Fórmulas** (`lessons_calculations.py`): `is_lesson_visible` (o projeto vê as suas e as Corporativas publicadas de outros; o Portfólio vê todas), `acervo_counts`, `published_by_phase` (checklist de kickoff), `is_ready_to_send` (recomendação e disciplina), `lesson_order_key`, `parse_keywords` (até 8), `next_application_item` (item da ação gerada), `lesson_draft_for_change` (texto do rascunho nascido no encerramento da SM).

**Fluxos** (`lessons_service.py`): Rascunho → Em validação → Validada → Publicada; a devolução volta a Rascunho com o comentário no histórico. O validador é Gestor e não pode ser o autor (`rbac.require_segregation`, 403). A origem de módulo exige o número do registro e o confere pela fachada dona (`register_origin`; Mudança já ligada, as demais nas issues dos seus módulos); origem sem número ou número inexistente é 422. `create_draft_lesson` é o que os outros módulos chamam para abrir lição em Rascunho com origem — a primeira ligação é o encerramento da SM (ISSUE-025). Aplicar em projeto registra `licao_aplicacao` e, quando pedido, cria a ação na Central (origem `Lição`); o risco gerado fica para a ISSUE-067.

**Carga e oráculo.** `seed.py` ganhou a parte `governanca-licoes`: lê `prototype_collection("licoes")`, converte a origem em texto do protótipo ("Claim CLM-..." → `Contrato` + `CLM-...`) e grava pela fachada (`load_demonstration_lesson`), conferindo o código do protótipo. Oráculo em `api/tests/oraculo/test_oraculo_licoes.py` (10 lições, 4 publicadas, 9 corporativas, 6 reusos). Migração `m027_licoes_aprendidas.py`; a tabela `licao_historico` entrou no `docs/MODELO-DE-DADOS.md` nesta entrega.

**Testes.** `api/tests/governanca/test_licoes_fachada.py`: segregação do validador, devolução com comentário, origem de módulo, rascunho com origem, aplicação com ação na Central e visibilidade no acervo.

## O que a ISSUE-025 trouxe

**Telas.** Na ficha da mudança, a barra de ações ganha **Registrar decisão** (Aguardando comitê, Gestor), **Reapresentar** (Adiada) e **Encerrar** (Em implementação, Gestor), e o alerta de **ratificação** da emergencial (pendente ou vencida, pelo prazo do parâmetro). O modal **Decisão** mostra o resumo (alçada, impacto em custo e prazo, fonte do recurso), o resultado (Aprovada, Aprovada com condições, Rejeitada ou Adiada), a data, a ata opcional do comitê, os participantes (quórum ou o gerente do projeto, conforme a alçada), a justificativa, as condições, o "reapresentar em" e as **ações de implementação** que a aprovação cria na Central. O modal **Encerrar** faz a conferência das ações em aberto e das linhas de base que a análise exige confirmar, com a data, as observações e a lição opcional.

**Rotas** (`/api/governanca/mudanca/...`, `routes.py`):

| Rota | Uso |
|---|---|
| `GET/POST decisao` | Formulário e gravação da decisão; a aprovação cria as ações e leva a SM a Em implementação |
| `GET/POST reapresentar` | A adiada volta à pauta; a decisão anterior fica no histórico |
| `GET/POST encerrar` | Encerramento com as confirmações do impacto e a lição opcional em Rascunho |

**Fórmulas** (`calculations.py`): `suggested_change_actions` (as ações que a aprovação cria, pelo que a análise apontou: custo → EAC, prazo → cronograma e Curva S, contrato → aditivo, riscos, SMS e qualidade, com o responsável pela função e o gerente como fallback), `has_impact` (texto preenchido e diferente de "sem impacto") e `person_for_role`. A Central expõe `next_origin_item` para a numeração das ações de um registro de origem.

**Fluxos** (`service.py`): a decisão exige Gestor, a SM Aguardando comitê e a análise de impacto; na alçada do gerente do projeto ele precisa constar entre os participantes; no Comitê, o quórum do parâmetro. A **aprovação** registra a decisão e os participantes, cria as ações de implementação pela costura da Central (origem `Mudança`, grupo `Implementação`, item sequencial, prazo do parâmetro) e leva a SM a Em implementação — tudo na mesma transação, de modo que uma falha no meio desfaz a decisão e as ações. **Rejeitada** é terminal e grava a data de encerramento; **Adiada** guarda o "reapresentar em" e volta à pauta por `resubmit_change`. O **encerramento** é recusado enquanto houver ação de implementação aberta e exige as confirmações que o impacto apontar (cronograma e Curva S, aditivo, riscos); a lição opcional nasce em Rascunho com origem na SM (`lessons_service.create_draft_lesson`).

**Integrações.** Central de Ações (criação das ações, contagem das abertas e numeração por origem), Atas (a ata do comitê, da Central), Lições (o rascunho do encerramento) e o link de origem `Mudança` registrado em `origin_links` (a ação de implementação abre a ficha da SM).

**Migração e modelo.** `m025_decisao_da_mudanca.py` acrescenta `ata_id` (FK para `ata`) e `reapresentar_em` a `mudanca_decisao`, que o modelo aceito não previa; o `docs/MODELO-DE-DADOS.md` mudou na mesma entrega. As conferências de incorporação na EAC e na EAP ficam com as ISSUE-030 e ISSUE-038.

**Testes.** `api/tests/governanca/test_decisao.py`: quórum e decisor, aprovação com ações e link de volta, atomicidade (falha no meio desfaz tudo), adiada e reapresentação, ratificação vencida, encerramento com ação aberta, confirmações do impacto e lição em Rascunho, além das rotas (403 para Membro e a ficha de volta para o Gestor).
