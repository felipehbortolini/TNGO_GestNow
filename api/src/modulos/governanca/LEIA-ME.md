# Governança

Módulo `governanca`. Controla solicitações de mudança (SM) e lições aprendidas, processos transversais aos módulos do projeto. As funcionalidades chegam nas ISSUE-023 a ISSUE-028; integrações são ativadas na issue do módulo que chega por último (D9).

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Registro e painel de mudanças | Lista, etapa, próxima decisão e indicadores | ISSUE-023, ISSUE-026 |
| Ficha da mudança | Solicitação, impacto, decisão, implementação e histórico | ISSUE-023 a ISSUE-025 |
| Acervo de lições | Busca, filtros, aplicabilidade e aplicação em projeto | ISSUE-027 |
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
| Rotas | `routes.py` |
| Transições, permissões e integrações | `service.py` |
| Alçada e prazos derivados | `calculations.py` |
| Validação de impacto/decisão | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades na ISSUE-003 |
| Fragmentos | `api/src/templates/governanca/` |
| Tela, estilo e comportamento | `app/_views/governanca/` e `app/paginas/governanca/` |
| Testes | `api/tests/governanca/` |

As ISSUE-024 a ISSUE-028 completam este documento (análise, decisão, painel e lições).

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

**Telas.** Acervo de lições (`licoes`): cartões (situação, recomendação, aplicabilidade), busca por palavras, filtros (fase, área, disciplina, tipo, origem, aplicabilidade, situação) e o checklist de kickoff (botões por fase que filtram as publicadas). Fragmentos em `api/src/templates/governanca/licao*.html`: nova lição e edição (`licao_form`), ficha (`licao_ver`), validação (`licao_validar`), aplicação em projeto (`licao_aplicar`). No Portfólio o acervo traz a coluna Projeto (também no Excel e no PDF) e **Nova lição** pede o projeto antes do formulário.

**Rotas** (prefixo `/api/`, `lessons_routes.py`): `governanca/licoes` (GET acervo, POST registra), `licoes/nova`, `licoes/ver?codigo=`, `licoes/editar`, `licoes/enviar`, `licoes/validar` (GET, POST), `licoes/publicar`, `licoes/aplicar` (GET, POST), `licoes/excel` e `licoes/imprimivel`. Escrita exige Membro; validar e publicar exigem Gestor.

**Fórmulas** (`lessons_calculations.py`): `is_lesson_visible` (o projeto vê as próprias e as Corporativas publicadas dos outros; o Portfólio vê todas), `search_matches`, `lesson_order_key`, `lesson_actions`, `is_ready_to_send` (disciplina e recomendação de 20 caracteres), `origin_of_text`, `lesson_draft_for_change` (texto da lição que nasce no encerramento da SM), `acervo_counts`, `published_by_phase`.

**Fluxo.** Rascunho, Em validação, Validada, Publicada. O validador é Gestor e não é o autor (403, `SELF_VALIDATION_MESSAGE`); a devolução volta a Rascunho com o comentário no histórico (`licao_historico`). Origem de módulo exige o número e a fachada do dono confere que existe (422); entram Ata e Mudança, mais Workshop, Encerramento e Registro direto; as demais são registradas com `register_origin` pelas issues dos módulos. `create_draft_lesson` é a fachada para os outros módulos abrirem lição em Rascunho com origem. `apply_lesson` registra o reuso e, quando pedido, cria a ação pela costura da Central (origem Lição); a opção de risco chega na ISSUE-067.

**Carga e oráculo.** `seed.py` grava as 10 lições do protótipo (`load_demonstration_lesson`, número conferido, uma aplicação por reuso contado); `api/tests/governanca/test_oraculo_licoes.py`. **Testes:** `test_licoes.py`, `apoio_licoes.py`.

**Onde mexer.** Regras em `lessons_calculations.py`, formulário em `lessons_validation.py`, fluxo em `lessons_service.py`, exportação em `lessons_export.py`, tabelas em `lessons_models.py` (migração `m027_licoes_aprendidas.py`).
