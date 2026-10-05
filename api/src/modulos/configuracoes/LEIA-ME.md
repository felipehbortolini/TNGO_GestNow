# Configurações

Módulo `configuracoes`. Mantém colaboradores, cadastros de apoio e parâmetros gerais versionados. A configuração específica de janelas da Programação Semanal fica no submódulo `programacao_semanal`, uma por projeto (D10).

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Parâmetros | Grupos, versão vigente, edição justificada e histórico antes/depois | ISSUE-076 |
| Colaboradores | Perfil geral, papéis da Programação Semanal por projeto, vínculo e empresa | ISSUE-077 |
| Cadastros de apoio | Projetos, empresas, pessoas, sistemas, unidades e locais | ISSUE-078 |

## Rotas previstas

Prefixo: `/api/configuracoes/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `parametros` e `parametros/historico` | Consultar, versionar e auditar parâmetros | ISSUE-076 |
| `colaboradores` | Administrar acesso, perfil e papéis por projeto | ISSUE-077 |
| `cadastros` | Manter entidades de apoio usadas nos formulários | ISSUE-078 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

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

O calendário da plataforma (data de hoje, semana ISO, períodos, parcial e corte) fica em `src/core/calendario.py` e é o único leitor do relógio; toda fórmula recebe a data de referência como argumento (D6).

As fórmulas dos domínios permanecem nas `calculations.py` dos módulos donos; Configurações não as duplica.

## Fluxos

Alterar parâmetro exige justificativa e cria nova versão com vigência, autor, antes e depois. Colaboradores são cadastrados com um perfil geral e, quando aplicável, papéis por projeto na Programação Semanal. Cadastros de apoio não são duplicados dentro dos módulos consumidores.

## Integrações

É fonte única de colaboradores, projetos, empresas, pessoas, sistemas, unidades e locais. Fachadas dos módulos consultam os parâmetros do grupo vigente com `service.current_group(session, group=..., reference_date=core.calendario.today())`. A janela semanal e liberações extraordinárias são mantidas dentro de Programação Semanal; aqui ficam parâmetros gerais versionados. A carga de demonstração (`api/src/carga/`) grava estes cadastros e chama `seed_initial_parameters`; o preparo de produção grava só o primeiro Admin e a versão 1.

## Parâmetros

Este módulo é dono do versionamento e dos 14 grupos gerais: `avaliacaoContratada`, `claims`, `hse`, `riscos`, `financeiro`, `suprimentos`, `punch`, `mudancas`, `licoes`, `produtividade`, `eap`, `qualidade`, `portfolio` (os 13 do protótipo) e `anexos` (D5a). Os valores iniciais ficam em `service.INITIAL_PARAMETERS`, com as mesmas chaves do `MOCK.parametros` do protótipo; a versão 1 é semeada por `service.seed_initial_parameters`.

Cada folha do payload vira uma linha de `parametro_valor`: a `chave` é o caminho com o índice das listas (`riscos.probabilidades.0.mediaPct`), o `tipo` é `texto`, `inteiro`, `decimal`, `booleano` ou `nulo`, o `valor` é o texto canônico e a `ordem` é a posição da folha na travessia. `parametro_versao` guarda uma linha por grupo e versão, com autor e justificativa; nada é editado.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Versionamento e cadastros | `service.py` (parâmetros: leitura por data, gravação validada e semeadura) |
| Calendário da plataforma | `src/core/calendario.py` (data de hoje, semana ISO, períodos, parcial e corte) |
| Derivação própria | Não há KPI próprio; cálculos permanecem nos módulos consumidores |
| Regras de entrada | `validation.py` (uma função por regra; o registro `_RULES` liga a regra ao campo) |
| Exportação | `export.py` |
| Persistência | `models.py`; projeto e cadastros de apoio criados pela revisão `0001_plataforma` (ISSUE-005); plataforma em `src/core/models.py` |
| Fragmentos | `api/src/templates/configuracoes/` |
| Tela, estilo e comportamento | `app/_views/configuracoes/` e `app/paginas/configuracoes/` |
| Testes | `api/tests/configuracoes/` (fachada e regras) e `api/tests/plataforma/test_calendario.py` |

As tabelas de projeto e cadastros de apoio nasceram na ISSUE-005 (`models.py`), junto da camada de banco. A ISSUE-007 versionou os parâmetros gerais e centralizou o calendário. A ISSUE-008 criou a carga de demonstração e o início de produção (`api/src/carga/LEIA-ME.md`) sobre estes cadastros. As ISSUE-076 a ISSUE-078 completam este documento com rotas, telas e os testes de acesso.
