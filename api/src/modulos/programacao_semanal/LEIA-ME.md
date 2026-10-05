# Programação Semanal

Módulo `programacao_semanal`. É a aplicação `Timenow - Programação Semanal` adaptada ao escopo de projeto, aos cadastros e aos perfis do GestNow (D10). Não é a tela reduzida do protótipo.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Programação | Matriz de atividades de segunda a domingo, previsto e realizado | ISSUE-051, ISSUE-052 |
| Governança da programação | Pedidos de alteração e histórico por empresa/semana | ISSUE-053 |
| Configuração da programação | Parâmetros e janelas, por projeto | ISSUE-054 |
| Importação e impressão | Conferência da planilha, exportação Excel e relatório imprimível | ISSUE-055 |
| Dashboard | Curva do avanço programado, aderência, ranking, heatmap, turnos e gargalos | ISSUE-056 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

As cinco telas aparecem como abas do grupo Programação Semanal no módulo 02 Planejamento, mas têm pasta própria (D10).

| Tela | View | CSS | JS |
|---|---|---|---|
| Programação | `app/_views/programacao_semanal/programacao.html` | `app/paginas/programacao_semanal/programacao.css` | `app/paginas/programacao_semanal/programacao.js` |
| Dashboard da programação | `app/_views/programacao_semanal/dashboard.html` | `app/paginas/programacao_semanal/dashboard.css` | `app/paginas/programacao_semanal/dashboard.js` |
| Governança da programação | `app/_views/programacao_semanal/governanca.html` | `app/paginas/programacao_semanal/governanca.css` | `app/paginas/programacao_semanal/governanca.js` |
| Importação e impressão | `app/_views/programacao_semanal/importacao.html` | `app/paginas/programacao_semanal/importacao.css` | `app/paginas/programacao_semanal/importacao.js` |
| Configuração da programação | `app/_views/programacao_semanal/configuracao.html` | `app/paginas/programacao_semanal/configuracao.css` | `app/paginas/programacao_semanal/configuracao.js` |

## Rotas previstas

Prefixo: `/api/programacao-semanal/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `programacoes` e `atividades` | Consultar/editar a semana e as atividades | ISSUE-051 |
| `validacoes`, `realizados` e `publicacoes` | Fluxo de cinco passos com fiscal | ISSUE-052 |
| `pedidos-de-alteracao` e `governanca` | Solicitar, aplicar/recusar e auditar alterações | ISSUE-053 |
| `configuracoes` | Parâmetros e janelas de escrita do projeto | ISSUE-054 |
| `importacoes` e `exportacoes` | Planilha e impressão | ISSUE-055 |
| `dashboard` | Indicadores e séries da programação | ISSUE-056 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| PPC da atividade | Realizado dividido pelo previsto de uma atividade; sem previsto, zero | `calculations.activity_ppc` |
| Aderência da programação | Soma do realizado dividida pela soma do previsto no conjunto (semana, empresa ou frente); não é a média do PPC | `calculations.schedule_adherence` |
| Faixa de desempenho | Classifica PPC ou aderência com os limites configurados para o projeto | `calculations.performance_band` |

## Fluxo de estado

Fornecedor cria/edita na janela → Planejador valida e define fiscal → Fornecedor informa realizado por turno dia/noite → Fiscal aprova (o realizado congela) → Planejador publica. Situação da programação e aprovação do realizado são estados distintos. Um pedido aprovado pode reabrir uma programação publicada com trilha.

## Integrações

Projeto, empresas, colaboradores, fiscais e encarregados vêm de Configurações. A identidade e o papel da pessoa vêm da plataforma GestNow; fornecedor só acessa a própria empresa. Para isso as rotas declaram `Access(module="programacao_semanal")` e a fachada chama `core.rbac`: `company_scope(user)` corta a consulta pela empresa do fornecedor (e `require_company` recusa a de outra), e `has_schedule_role` / `require_schedule_role(user, project_id, *roles)` conferem o papel no projeto em que a pessoa o recebeu (Planejador, Fiscal, Encarregado, Fornecedor; o papel não vale em outro projeto). O fornecedor não tem permissão geral nenhuma: na programação ele age pelos papéis. O módulo não mantém cadastro paralelo de pessoas/empresas. A saída alimenta o dashboard da programação e os relatórios previstos.

## Parâmetros

Cada projeto tem seus parâmetros e janelas: limites de PPC/aderência, limite de desvio que exige justificativa, semanas/dias/horários liberados e liberações extraordinárias. Projeto novo recebe valores padrão. A alteração vale na hora e deixa auditoria (ISSUE-054).

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Fluxo, permissões e janela | `service.py` |
| PPC, aderência e faixas | `calculations.py` |
| Validações da atividade/planilha | `validation.py` |
| Planilha e impressão | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/programacao_semanal/` |
| Tela, estilo e comportamento | `app/_views/programacao_semanal/` e `app/paginas/programacao_semanal/` |
| Testes | `api/tests/programacao_semanal/` |

O app de origem e seu glossário ficam somente para consulta em `docs/referencia/programacao-semanal/`. Multi-ambiente, seletor de clientes, área do operador, login próprio, SharePoint/JSON e API JSON de leitura permanecem fora de escopo. Os stubs Python desta issue não portam comportamento; ISSUE-051 a ISSUE-056 completam este documento e os testes.
