# Configurações

Módulo `configuracoes`. Mantém colaboradores, cadastros de apoio e parâmetros gerais versionados. A configuração específica de janelas da Programação Semanal fica no submódulo `programacao_semanal`, uma por projeto (D10).

## Telas

| Tela | Conteúdo | Issue |
|---|---|---|
| Parâmetros | Grupos por módulo com os valores vigentes, edição por grupo com justificativa, versões e histórico antes/depois (entregue) | ISSUE-076 |
| Colaboradores | Quem entra e o que faz: perfil geral, vínculo, empresa e os papéis da Programação Semanal por projeto; busca, filtros, Excel e PDF (entregue) | ISSUE-077 |
| Cadastros de apoio | Empresas, pessoas, projetos (com cliente, orçamento, padrões e notas de ponderação), sistemas, unidades, locais e disciplinas; exclusão em uso recusada com a mensagem; Excel e PDF (entregue) | ISSUE-078 |

## A tela de Parâmetros (ISSUE-076)

A tela mostra o card da versão vigente (a mais recente entre os grupos), a busca e o filtro por módulo (formulário GET que re-renderiza o fragmento; o filtro é do servidor) e os grupos por módulo (Avaliação de contratadas, Financeiro, Suprimentos, Riscos, Qualidade, HSE, Planejamento, Governança, Portfólio e Anexos) com a tabela de parâmetro × valor vigente e o botão Editar. Só Gestor e Admin alcançam a tela e gravam (`rbac.MODULE_PERMISSION`). Os metadados dos grupos e campos — o porte de `grupos(p)` e `exibir(c, v)` do protótipo, com as listas dinâmicas (critérios e classes da avaliação, alçadas e pesos dos marcos, probabilidades dos riscos, modelos de etapas da EAP, critérios do portfólio) — ficam em `forms.py` e são construídos a partir dos valores vigentes.

O **Editar** abre o modal do grupo com os campos vigentes (selects com as opções, números com min/max/passo, alçadas em reais, a nota mínima da última classe e os tipos aceitos de Anexos somente leitura) e a justificativa obrigatória (mínimo de 10 caracteres, como o protótipo). Um grupo da tela agrega um ou mais grupos de parâmetros (ex.: Planejamento = punch + produtividade + eap); a gravação cria a nova versão **só dos grupos de origem cujos valores mudaram**, com vigência de hoje e autor, e recusa com 422 "Nenhum valor foi alterado." quando nada mudou. A validação é a da ISSUE-007 (uma mensagem por campo/bloco; o erro de um campo aparece sob o campo e o de um bloco no topo do formulário). A troca da escala de riscos exige o campo `confirmar_escala`: sem ele a gravação é recusada, porque muda a contagem de riscos críticos em todo o sistema. O **Histórico de versões** mostra todas as versões de todos os grupos, da mais recente para a mais antiga, com o selo Vigente na versão vigente de cada grupo e o número de alterações; o Ver abre o antes/depois da versão contra a anterior do MESMO grupo (a primeira versão de cada grupo não tem alterações).

## A tela de Colaboradores (ISSUE-077)

A tela mostra os dois avisos do precedente (o app de Programação Semanal): "Esta tela controla quem entra no sistema" e "Fiscais e encarregados saem daqui". Só o Admin chega a ela e às gravações (`rbac.SCREEN_PERMISSION["configuracoes/colaboradores"] = Permission.ADMINISTER`; o Gestor recebe 403). A linha de KPIs conta os colaboradores de cada perfil geral sobre o **universo completo** (como o app: o filtro não muda a situação do cadastro), e a barra de filtros (busca, perfil e vínculo) é um GET que re-renderiza o fragmento — o filtro é do servidor. A busca não diferencia maiúsculas de nome, e-mail, função e empresa; o perfil e o vínculo filtram pelo valor exato. O botão **Liberar acesso** e o **Editar** de cada linha abrem o mesmo modal (`colaboradores-modal-corpo`), cujo corpo o servidor entrega por GET; a gravação (POST) devolve a tela atualizada, o modal fecha pelo `@ajax:success` e o toast diz "Acesso de Fulano liberado/atualizado.". O **Revogar** confirma por `TN.confirmarExclusao` e posta; o servidor devolve a tela com o toast "Acesso de fulano@empresa.com revogado.".

O formulário tem nome, e-mail (bloqueado na edição — é por ele que o login reconhece a pessoa), função, perfil geral, vínculo, a empresa (que só aparece no vínculo Fornecedor, por `x-show`) e a situação Ativo/Suspenso. A seção **Papéis na Programação Semanal** lista os papéis atuais com remover e permite adicionar por projeto + papel; o editor do trio lê os projetos, os papéis e os rótulos de `data-*` e posta um campo repetido `papeis` por linha, com valor `"<projeto_id>:<papel>"` (a rota lê com `req.form.getlist("papeis")`). Os papéis são substituídos pelo conjunto enviado: o que sai e o que entra ficam na trilha, e a UK (colaborador + projeto + papel) não duplica.

Regras da gravação (`service.save_collaborator`): nome obrigatório; e-mail com formato (`^[^@\s]+@[^@\s]+\.[^@\s]{2,}$`), normalizado para minúsculas e único entre quem já tem acesso — o e-mail de uma pessoa **sem** acesso reusa a pessoa; perfil em `GeneralProfile` e vínculo em `Bond`; empresa obrigatória no vínculo Fornecedor (e existente no cadastro; nos demais vínculos é ignorada/limpa); papéis de projeto existente e papel em `ScheduleRole`. A recusa levanta `InvalidDataError` com uma mensagem por campo (`nome`, `email`, `perfil`, `vinculo`, `empresa`, `papeis`, `ativo`) e a rota devolve o formulário preenchido com 422. O **último Admin ativo** não pode ser desativado nem rebaixado (422 no campo `ativo`/`perfil`, com a mensagem "O último Admin não pode ser removido nem rebaixado."), e a revogação dele também é recusada (422 no aviso do topo). A revogação apaga os papéis e o colaborador com a trilha; a **pessoa permanece no cadastro** (quem dona das pessoas é o cadastro de apoio, ISSUE-078), e o gate deixa de achar o e-mail na requisição seguinte. Quem já deixou trilha de auditoria (é autor de alguma gravação) não é apagado — a trilha perde o autor — e a recusa orienta suspender o acesso (`ativo = False`); o gate nega o acesso do mesmo jeito (a pessoa passa a ver o acesso negado na requisição seguinte).

## A tela de Cadastros (ISSUE-078)

A tela mostra **sete cartões**, um por cadastro de apoio que alimenta os formulários: Empresas (Nome, Tipo), Pessoas (Nome, Função, Empresa, E-mail), Projetos (Código, Nome, Cliente, Gerente, Orçamento, Início, Término e as notas de ponderação como selos), Sistemas (Projeto, Código, Nome, Área), Unidades (Tipo, Código, Nome), Locais (Projeto, Código, Nome) e Disciplinas (Nome). Cada cartão tem a contagem, o **Incluir** e **Editar/Excluir** por linha; a barra superior tem **Excel** e **PDF** pelos mecanismos genéricos do Design System. Só Gestor e Admin alcançam a tela e as gravações (`rbac.MODULE_PERMISSION["configuracoes"] = Permission.CONFIGURE`); Membro, Visualizador e Fornecedor recebem 403. Não há filtros nem KPIs: a lista é inteira.

O corpo do modal (`cadastros-modal-corpo`) é desenhado pelo servidor por GET conforme o tipo (`/api/configuracoes/cadastros/{tipo}/novo` e `.../{id}/editar`); a gravação (POST) devolve a tela inteira (`cadastros-conteudo`) com o toast e o modal fecha pelo `@ajax:success`; a recusa volta no modal (422) com a mensagem sob cada campo, e a exclusão confirmada por `TN.confirmarExclusao` volta como a tela com o toast. Em **Sistemas** e **Locais** o projeto é campo do próprio formulário (pré-selecionado com o projeto do escopo quando a requisição está num projeto), e a lista mostra a coluna Projeto; no **Portfólio** o select oferece todos os projetos (`codigo · nome`).

Validações da gravação (`service.save_register`, mensagem por campo): **empresa** com `nome` obrigatório e único sem diferenciar maiúsculas e `tipo` em Contratada/Fornecedor/Gerenciadora; **pessoa** com `nome` obrigatório, `email` obrigatório, com formato, normalizado para minúsculas e único, e `empresa` existente quando informada; **projeto** com `codigo` obrigatório e único, `nome`, `cliente_nome` obrigatório, `cliente_sigla` obrigatória só quando o cliente é novo, `gerente` existente, `apetite_risco` em uma das faixas da escala de riscos vigente, datas ISO com término não anterior ao início, `orcamento` em reais (`forms.parse_money`), padrões de numeração opcionais e as notas `nota_<criterio>` inteiras na faixa `notaMinima..notaMaxima` do grupo vigente; **sistema** e **local** com `projeto` existente e `codigo` único no projeto; **unidade** com `tipo` em medida/organizacional e `codigo` único no tipo; **disciplina** com `nome` único. Toda gravação passa por `recording` (create/update) com a trilha.

O **cliente entra pelo formulário do projeto**: o servidor reusa o cliente existente pelo nome (sem diferenciar maiúsculas) ou cria um novo com a sigla; a **sigla só é obrigatória quando o cliente é novo**. O **projeto novo nasce com a configuração padrão da Programação Semanal** (`programacao_semanal.service.ensure_settings`, 60/75/15 e a regra de desvio ligada), e a edição do projeto **não** mexe nessa configuração. As **notas de ponderação** do projeto vivem na versão vigente do grupo `portfolio` (`portfolio_ponderacao`): a gravação do projeto substitui as notas dele na versão vigente, com trilha (o que sai e o que entra), e a nova versão do grupo criada pela tela de Parâmetros **copia as notas da versão anterior** (`service._copy_portfolio_weights`), senão a ponderação de todos os projetos zeraria. A ponderação da carteira, no Início (ISSUE-080), grava a versão nova pelos mesmos caminhos e substitui as notas digitadas nela (`service.replace_portfolio_grades`), também com a trilha.

A **exclusão** é recusada quando o cadastro está em uso, com a mensagem de onde ele é usado. Primeiro as referências do próprio módulo, com a contagem: empresa ← `pessoa.empresa_id` e `colaborador.empresa_id`; pessoa ← `colaborador.pessoa_id` e `projeto.gerente_id`; projeto ← `sistema`, `colaborador_papel_programacao` e `portfolio_ponderacao`. Depois, a exclusão roda num savepoint e a chave estrangeira do banco decide: a tabela bloqueadora sai do diagnóstico da violação (ou da mensagem do banco) e vira o rótulo em português ("item da EAP", "contrato", "risco", "item da punch list", "ocorrência", "inspeção", "RNC", "pedido de compra"...), no mapa `_USED_BY_LABELS`; tabela sem rótulo cai em "está em uso no sistema". O **projeto** tem um degrau a mais: a configuração da Programação Semanal sai antes, pela fachada dona (`programacao_semanal.service.remove_settings`), e o toast explica a categoria do uso. Observação: a trilha de auditoria das gravações feitas no projeto (`auditoria.projeto_id`) impede a exclusão depois da primeira gravação — a trilha é só de inclusão (D5b) e o gatilho do banco recusa apagá-la; a mensagem diz "em uso pela trilha de auditoria".

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Parâmetros do sistema | `app/_views/configuracoes/parametros.html` | `app/paginas/configuracoes/parametros.css` | `app/paginas/configuracoes/parametros.js` |
| Colaboradores | `app/_views/configuracoes/colaboradores.html` | `app/paginas/configuracoes/colaboradores.css` | `app/paginas/configuracoes/colaboradores.js` |
| Cadastros de apoio | `app/_views/configuracoes/cadastros.html` | `app/paginas/configuracoes/cadastros.css` | `app/paginas/configuracoes/cadastros.js` |

## Rotas previstas

Prefixo: `/api/configuracoes/`.

| Grupo | Uso | Issue |
|---|---|---|
| `parametros` e `parametros/historico` | Consultar, versionar e auditar parâmetros | ISSUE-076 |
| `colaboradores` | Administrar acesso, perfil, vínculo e papéis por projeto | ISSUE-077 |
| `cadastros` | Manter empresas, pessoas, projetos, sistemas, unidades, locais e disciplinas | ISSUE-078 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

### Rotas da tela de Cadastros (ISSUE-078)

| Rota | Uso |
|---|---|
| `GET /api/configuracoes/cadastros` | A tela com os sete cartões |
| `GET /api/configuracoes/cadastros/excel` e `.../imprimivel` | Os dois exports, com as sete tabelas (D12) |
| `GET /api/configuracoes/cadastros/{tipo}/novo` | O corpo do modal de novo cadastro, conforme o tipo |
| `GET /api/configuracoes/cadastros/{tipo}/{id}/editar` | O corpo do modal de edição, com o registro carregado |
| `POST /api/configuracoes/cadastros/{tipo}` | Cria o cadastro e devolve a tela; a recusa volta no formulário (422) |
| `POST /api/configuracoes/cadastros/{tipo}/{id}` | Atualiza o cadastro e devolve a tela; a recusa volta no formulário (422) |
| `POST /api/configuracoes/cadastros/{tipo}/{id}/excluir` | Apaga o cadastro e devolve a tela com o toast; em uso, a recusa volta na própria tela (422) |

O `{tipo}` é `empresa`, `pessoa`, `projeto`, `sistema`, `unidade`, `local` ou `disciplina` (`service.REGISTER_KINDS`).

### Rotas da tela de Colaboradores (ISSUE-077)

| Rota | Uso |
|---|---|
| `GET /api/configuracoes/colaboradores` | A tela (busca, perfil e vínculo por query; o servidor filtra e re-renderiza) |
| `GET /api/configuracoes/colaboradores/excel` e `.../imprimivel` | Os dois exports, com a lista de quem tem acesso (D12) |
| `GET /api/configuracoes/colaboradores/novo` | O corpo do modal de novo acesso |
| `GET /api/configuracoes/colaboradores/{id}/editar` | O corpo do modal de edição, com os papéis atuais |
| `POST /api/configuracoes/colaboradores` | Cria o acesso e devolve a tela; a recusa volta no formulário (422) |
| `POST /api/configuracoes/colaboradores/{id}` | Atualiza o acesso e devolve a tela; a recusa volta no formulário (422) |
| `POST /api/configuracoes/colaboradores/{id}/revogar` | Apaga o acesso e os papéis e devolve a tela com o toast; a recusa do último Admin (e de quem já deixou trilha) volta na própria tela (422) |

### Rotas da tela de Parâmetros (ISSUE-076)

| Rota | Uso |
|---|---|
| `GET /api/configuracoes/parametros` | A tela (busca e módulo por query; o servidor filtra e re-renderiza) |
| `GET /api/configuracoes/parametros/excel` e `.../imprimivel` | Os dois exports, com as tabelas de parâmetros vigentes e do histórico (D12) |
| `GET /api/configuracoes/parametros/{grupo}/editar` | O corpo do modal de edição, com os campos vigentes do grupo |
| `POST /api/configuracoes/parametros/{grupo}` | Grava a nova versão (uma por grupo de origem que mudou) e devolve a tela; a recusa volta no formulário (422) |
| `GET /api/configuracoes/parametros/historico` | O corpo do modal do histórico; `grupo` e `versao` na query abrem o antes/depois da versão |

## Fórmulas e nomes no código

Este módulo não calcula indicadores de negócio. A validação da edição de parâmetros é uma regra de entrada, não um KPI:

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Grupo de parâmetros válido | Roda todas as regras do grupo e devolve uma mensagem por campo (vazio quando passa) | `validation.validate_parameter_group` |
| Regra de validação | Uma função por regra da seção 7.4, com a mensagem e a fronteira do protótipo; o registro em `_RULES` liga cada regra ao campo do formulário (ex.: `contractor_weight_total_error`, `risk_review_cadence_error`, `supply_authority_limits_error`, `eap_stage_models_error`) | `validation.py` |
| Versão vigente | Versão de cada grupo cuja vigência não é posterior à data de referência | `service.current_version`, `current_versions`, `current_group`, `current_parameters` |
| Nova versão | Valida os valores, exige justificativa (mínimo de 10 caracteres) e grava a próxima versão do grupo com autor, vigência e trilha, na transação da requisição | `service.save_parameter_group` |
| Versão inicial | Semeia a versão 1 de cada grupo sem versão, com a justificativa "Versão inicial"; rodar de novo não duplica | `service.seed_initial_parameters` |
| Projetos do portfólio | Leitura dos projetos (id, código e nome) por código, para o seletor de escopo e para validar o parâmetro `projeto` da URL (ISSUE-009, D8); quem precisa dos projetos lê aqui e nunca a tabela | `service.list_projects`, `service.ProjectSummary` |
| Acesso do colaborador | O que o gate lê do cadastro (ISSUE-011, D7): quem é, perfil geral, vínculo, empresa, se está ativo e os papéis da Programação Semanal por projeto, como o cadastro guarda (textos); a plataforma (`core.auth`) converte nos tipos de `core.rbac` e recusa o valor que não conhece | `service.CollaboratorAccess` |
| Colaborador de um e-mail | O colaborador do e-mail, ativo ou não, sem diferenciar maiúsculas; `None` quando o e-mail não está no cadastro (a pessoa vê o acesso negado) | `service.find_access_by_email` |
| Colaborador de um id | O colaborador do id, ativo ou não, ou `None` | `service.find_access` |
| Colaboradores ativos | Os ativos, por id: as pessoas que o seletor de perfil da demonstração oferece | `service.list_active_access` |
| Grupo da tela | Metadados de um grupo da tela (módulo, onde, nota e campos) construídos dos valores vigentes; o caminho de um campo é o da folha no payload (`riscos.probabilidades.0.mediaPct`) e o id no formulário troca os pontos por `__` | `forms.group_forms`, `forms.ParameterGroupForm`, `forms.ParameterField` |
| Leitura de um valor | O valor de um caminho com índice (`suprimentos.alcadas.0.ate`) e a sua exibição: select pelo texto da opção, moeda por extenso, número com 0 casas quando inteiro e 2 quando não, mais a unidade, `·` para vazio | `forms.value_at`, `forms.exibir`, `forms.input_text` |
| Gravação por grupo | Lê o formulário do grupo, compara com os valores vigentes e devolve os payloads por grupo de origem, os campos que mudaram e os erros por caminho; a troca da escala de riscos exige `confirmar_escala` | `forms.parse_group_form`, `forms.ParsedGroupForm` |
| Visão da tela | Os grupos da tela com os valores vigentes (filtrados pela busca e pelo módulo), a versão mais recente entre os grupos e o total de versões | `service.parameter_overview`, `service.ParameterOverview`, `service.GroupView` |
| Histórico de versões | As versões registradas, da mais recente para a mais antiga, com autor, vigência e justificativa, e as alterações contra a versão anterior do MESMO grupo (o GestNow versiona por grupo) | `service.parameter_history`, `service.HistoryEntry`, `service.VersionChange` |
| Documento da tela | As duas tabelas do protótipo (Parâmetros vigentes: Grupo/Parâmetro/Valor/Módulo; Histórico de versões: Versão/Grupo/Vigência/Alterada por/Justificativa/Alterações), sem a coluna Projeto porque os parâmetros são globais | `export.parametros_document` |
| Linhas da tela de Colaboradores | O colaborador com a pessoa, a empresa e os papéis da Programação Semanal por projeto, filtrados pela busca e pelos filtros exatos; a contagem por perfil é a do universo completo (os KPIs) | `service.list_collaborators_overview`, `service.CollaboratorRow`, `service.ScheduleRoleLine` |
| Colaborador de um id (tela) | O colaborador com empresa e papéis, ou `None`: o que o modal de edição carrega | `service.find_collaborator` |
| Gravação do acesso | Cria (pessoa + colaborador) ou atualiza, com a trilha, e substitui os papéis pelo conjunto enviado; as regras do D7 mensagem por campo, o último Admin ativo recusado | `service.save_collaborator` |
| Revogação do acesso | Apaga os papéis e o colaborador com a trilha (a pessoa permanece); recusa o último Admin e quem já deixou trilha de auditoria | `service.revoke_collaborator` |
| Documento da tela de Colaboradores | A lista de quem tem acesso (Pessoa/E-mail/Função/Perfil/Vínculo/Empresa/Situação/Papéis na Programação Semanal), sem a coluna Projeto | `export.colaboradores_document` |
| Linhas da tela de Cadastros | Os sete cadastros com a empresa, o projeto e o gerente de cada linha e um tipo de linha por cadastro; o total fecha a barra de exportações | `service.registers_overview`, `service.RegistersOverview` |
| Registro de um cadastro (modal) | O cadastro como o formulário de edição o carrega, ou `None` fora do cadastro | `service.register_form_values` |
| Listas dos formulários | Empresas, pessoas, projetos, os dois tipos de empresa e unidade, as faixas de apetite da escala vigente e os critérios de nota da carteira | `service.register_form_options`, `service.AppetiteOption`, `service.GradeCriterion` |
| Gravação de um cadastro | Valida uma mensagem por campo (`InvalidDataError`) e grava com a trilha; o projeto novo chama `ensure_settings` e substitui as notas na versão vigente | `service.save_register` |
| Exclusão de um cadastro | Recusa em uso (contagem do próprio módulo e chave estrangeira do banco, tabela → rótulo) e grava a trilha; no projeto, `remove_settings` sai antes | `service.delete_register`, `service._USED_BY_LABELS` |
| Configuração da programação na exclusão | Apaga a linha de `programacao_configuracao` do projeto com a trilha, pela fachada dona | `programacao_semanal.service.remove_settings` |
| Versão nova do portfólio | Copia as notas dos projetos da versão anterior para a nova, senão a ponderação da carteira zeraria (correção da ISSUE-076) | `service._copy_portfolio_weights` |
| Notas na versão nova | A ponderação do Início (ISSUE-080) substitui as notas digitadas na versão recém-criada do grupo `portfolio`, por projeto e critério, com a trilha do que sai e do que entra; nota igual não gera trilha | `service.replace_portfolio_grades` |
| Documento da tela de Cadastros | As sete tabelas (empresas, pessoas, projetos, sistemas, unidades, locais e disciplinas), com as mesmas colunas da tela | `export.registers_document` |

O calendário da plataforma (data de hoje, semana ISO, períodos, parcial e corte) fica em `src/core/calendario.py` e é o único leitor do relógio; toda fórmula recebe a data de referência como argumento (D6).

As fórmulas dos domínios permanecem nas `calculations.py` dos módulos donos; Configurações não as duplica.

## Fluxos

Alterar parâmetro exige justificativa e cria nova versão com vigência, autor, antes e depois. Colaboradores são cadastrados com um perfil geral e, quando aplicável, papéis por projeto na Programação Semanal. Cadastros de apoio não são duplicados dentro dos módulos consumidores.

Na tela Parâmetros, o Editar abre o modal do grupo; a gravação cria a nova versão com vigência de hoje e autor **só para os grupos de origem cujos valores mudaram** (um grupo da tela agrega um ou mais grupos de parâmetros), e nenhum valor alterado é recusado com 422. A troca da escala de riscos pede a confirmação `confirmar_escala`, porque muda a contagem de riscos críticos em todo o sistema. O Histórico mostra todas as versões, com o selo Vigente na vigente de cada grupo, e o Ver abre o antes/depois da versão contra a anterior do mesmo grupo.

Na tela Colaboradores, o **Liberar acesso** e o **Editar** abrem o mesmo modal; a gravação cria ou atualiza a pessoa e o acesso numa transação só e substitui os papéis da Programação Semanal pelo conjunto enviado (o que sai e o que entra ficam na trilha). Fornecedor sem empresa é recusado no campo `empresa`; o último Admin ativo não pode ser desativado nem rebaixado; a revogação apaga os papéis e o acesso com a trilha, mas recusa quem já deixou trilha de auditoria (a trilha perde o autor — a orientação é suspender).

O **cadastro de Colaboradores é a fonte de verdade do acesso** (D7): a cada requisição o gate (`core.auth`) procura o e-mail do principal do Static Web Apps aqui, e e-mail fora do cadastro ou de colaborador desativado vê o acesso negado. Uma mudança no cadastro vale na requisição seguinte da pessoa, porque nada do acesso fica guardado fora dele. Configurações só aparece para Gestor e Admin e a tela Colaboradores é só do Admin (`rbac.MODULE_PERMISSION` e `rbac.SCREEN_PERMISSION`).

Na tela Cadastros, cada cartão inclui e edita pelo mesmo modal, cujo corpo o servidor desenha por tipo; o projeto grava cliente, orçamento, padrões, apetite e notas numa transação só, e nasce com a configuração padrão da Programação Semanal. Excluir um cadastro em uso é recusado com a mensagem de onde ele é usado; um projeto que já gravou (deixou trilha) não sai do cadastro, porque a trilha é só de inclusão e aponta para ele.

## Integrações

É fonte única de colaboradores, projetos, empresas, pessoas, sistemas, unidades e locais. Fachadas dos módulos consultam os parâmetros do grupo vigente com `service.current_group(session, group=..., reference_date=core.calendario.today())`: pesos e prazos valem para registros novos e critérios de exibição (base das taxas, referência da pirâmide, escala de severidade, faixas do mapa de calor) recalculam as telas na hora. O gate do acesso (`core.auth`) lê o cadastro de Colaboradores pela fachada (`service.find_access_by_email`, `service.find_access`, `service.list_active_access`), e a Programação Semanal lê os papéis por projeto em `registers.list_people_with_role` para os campos de Fiscal responsável e Encarregado — é a mesma tabela que a tela de Colaboradores grava. O **projeto** se integra com a Programação Semanal pelas fachadas donas: nasce com `ensure_settings` (os padrões do app) e, na exclusão, a linha de configuração sai por `remove_settings` antes do delete — o cadastro nunca escreve nas tabelas do outro módulo. A janela semanal e liberações extraordinárias são mantidas dentro de Programação Semanal; aqui ficam parâmetros gerais versionados. A carga de demonstração (`api/src/carga/`) grava estes cadastros e chama `seed_initial_parameters`; o preparo de produção grava só o primeiro Admin e a versão 1.

## Parâmetros

Este módulo é dono do versionamento e dos 14 grupos gerais: `avaliacaoContratada`, `claims`, `hse`, `riscos`, `financeiro`, `suprimentos`, `punch`, `mudancas`, `licoes`, `produtividade`, `eap`, `qualidade`, `portfolio` (os 13 do protótipo) e `anexos` (D5a, lido por `core.attachments`: `tamanhoMaximoMb` e `tiposAceitos` são o limite e a lista de tipos do próximo envio). Os valores iniciais ficam em `service.INITIAL_PARAMETERS`, com as mesmas chaves do `MOCK.parametros` do protótipo; a versão 1 é semeada por `service.seed_initial_parameters`.

Cada folha do payload vira uma linha de `parametro_valor`: a `chave` é o caminho com o índice das listas (`riscos.probabilidades.0.mediaPct`), o `tipo` é `texto`, `inteiro`, `decimal`, `booleano` ou `nulo`, o `valor` é o texto canônico e a `ordem` é a posição da folha na travessia. `parametro_versao` guarda uma linha por grupo e versão, com autor e justificativa; nada é editado.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` (tela, modal, gravação, histórico e exports de parâmetros; tela, filtros, modal, gravação, revogação e exports de colaboradores; tela, modais por tipo, gravação, exclusão e exports de cadastros) |
| Metadados dos grupos e campos da tela | `forms.py` (porte de `grupos(p)`, `exibir(c, v)` e do diff por caminho) |
| Versionamento e cadastros | `service.py` (parâmetros: leitura por data, visão da tela, histórico de versões, gravação validada e semeadura; colaboradores: visão da tela, modal, gravação e revogação; cadastros: linhas, formulários, gravação, exclusão e notas do portfólio) |
| Acesso do colaborador lido pelo gate | `service.py` (`find_access_by_email`, `find_access`, `list_active_access`); quem decide e o que cada perfil pode: `src/core/auth.py` e `src/core/rbac.py` |
| Calendário da plataforma | `src/core/calendario.py` (data de hoje, semana ISO, períodos, parcial e corte) |
| Derivação própria | Não há KPI próprio; a contagem por perfil da tela de Colaboradores é contagem do cadastro, e os cálculos de negócio permanecem nos módulos consumidores |
| Regras de entrada | `validation.py` (uma função por regra; o registro `_RULES` liga a regra ao campo); a validação de Colaboradores e de Cadastros mora em `service.py` |
| Exportação | `export.py` (`parametros_document`, `colaboradores_document` e `registers_document`) |
| Persistência | `models.py`; projeto e cadastros de apoio criados pela revisão `0001_plataforma` (ISSUE-005); plataforma em `src/core/models.py` |
| Configuração da programação | `src/modulos/programacao_semanal/service.py` (`ensure_settings` no projeto novo e `remove_settings` na exclusão, como fachadas donas) |
| Fragmentos | `api/src/templates/configuracoes/` (`parametros.html`, `parametros_form.html`, `parametros_historico.html`, `colaboradores.html`, `colaboradores_form.html`, `cadastros.html` e `cadastros_form.html`) |
| Tela, estilo e comportamento | `app/_views/configuracoes/` e `app/paginas/configuracoes/` |
| Testes | `api/tests/configuracoes/` (fachada e regras; `test_parametros_rotas.py` para a tela de Parâmetros, `test_colaboradores_rotas.py` para a de Colaboradores, `test_cadastros_rotas.py` para a de Cadastros e `test_acesso_colaborador.py` para a leitura do acesso) e `api/tests/plataforma/test_calendario.py` |

As tabelas de projeto e cadastros de apoio nasceram na ISSUE-005 (`models.py`), junto da camada de banco. A ISSUE-007 versionou os parâmetros gerais e centralizou o calendário. A ISSUE-008 criou a carga de demonstração e o início de produção (`api/src/carga/LEIA-ME.md`) sobre estes cadastros. A ISSUE-076 entregou a tela de Parâmetros e a ISSUE-077, a de Colaboradores; a ISSUE-078 completa este documento com a tela de Cadastros de apoio.

## Idioma (ISSUE-088)

A parte 2 do inglês (D13) completa o catálogo: o namespace `configuracoes` vive em
`api/src/core/translations.py`, alimentado pelo `en.js` do protótipo (e, na Programação
Semanal, por chaves novas escritas com o inglês da casa). O idioma vem do cookie
`gestnow_idioma`, gravado pela rota `POST /api/idioma`, e o seletor PT | EN fica na barra
lateral. O bloco de Configurações do `en.js` é a fonte; o cadastro de colaboradores, os parâmetros versionados e os cadastros de apoio são telas de Gestor/Admin, com os avisos traduzidos no render (`_aviso`, porque `_notice` já nomeia o aviso de versões).
Os templates chamam `{{ t('configuracoes', 'Texto') }}`; as views e o JS estáticos usam
`data-i18n`/`TN.t`; as datas saem do `data()`/`data_hora()` do contexto e do
`translations.format_date`/`mes_curto`/`semana_label` (a semana ISO é `S38` em português e
`W38` em inglês). As rotas traduzem avisos, recusas e erros por campo no idioma do request,
e os gráficos passam por `_chart_data`, que traduz os textos do `data-dados` e acrescenta os
`rotulos` do motor de gráficos. Títulos e colunas das planilhas e da folha imprimível são
traduzidos pelo namespace do documento (`Document.namespace`/`Document.idioma`) em
`core/export_document`; o `RequestContext.idioma` leva o idioma resolvido às costuras das
rotas. Para acrescentar tradução, some a chave ao namespace `configuracoes`; a cobertura em
`api/tests/plataforma/test_traducoes.py` e a revisão de tela em
`api/tests/plataforma/test_idioma_nas_areas_2.py` reprovam chave marcada sem tradução.
