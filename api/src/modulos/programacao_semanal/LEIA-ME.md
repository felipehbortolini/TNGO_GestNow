# Programação Semanal

Módulo `programacao_semanal`. É a aplicação `Timenow - Programação Semanal` adaptada ao escopo de projeto, aos cadastros e aos perfis do GestNow (D10). Não é a tela reduzida do protótipo.

## Telas

| Tela | Conteúdo | Issue |
|---|---|---|
| Programação | Matriz de atividades de segunda a domingo, previsto e realizado; criar, editar e excluir (051), lançar realizado e fluxo (052) | ISSUE-051, ISSUE-052 |
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

## Rotas (ISSUE-051)

Prefixo `/api/programacao-semanal/`. Todas declaram `Access(module="programacao_semanal")` (o fornecedor alcança o módulo; o recorte por empresa e o papel são da fachada) e respondem fragmento com alvos de id fixo: `prog-janela`, `prog-filtros`, `prog-resumo`, `prog-tabela` e `drawer`.

| Rota | Método | O que devolve |
|---|---|---|
| `programacoes` | GET | Faixa de indicadores + matriz da semana (`semana`, `local`, `empresa`, `encarregado`, `responsavel`, `situacao`, `aprovacao`, `ppc`, `busca`, `ordena`, `ordem`) |
| `programacoes/filtros` | GET | Barra de ferramentas: semana, busca e painel de refino |
| `programacoes/janela` | GET | Faixa da janela (aberta, fechada e o motivo; no Portfólio, "só leitura") |
| `atividades/formulario` | GET | Painel de nova atividade (`semana`) ou de edição (`atividade`) |
| `atividades` | POST | Cria (sem `atividade_id`) ou salva; 422 e 409 devolvem o painel preenchido |
| `atividades/excluir` | POST | Exclui (só Admin, e só sem pedidos de alteração) e redesenha a matriz |

### Rotas do fluxo de cinco passos (ISSUE-052)

Mesmo prefixo e mesmos alvos. Cada passo tem o painel (GET `.../formulario`, alvo `drawer`) e a gravação (POST, alvos `drawer prog-resumo prog-tabela`). O papel errado recebe 403 antes de qualquer outra checagem; passo fora do lugar no fluxo, 422 com a mensagem do app; versão velha, 409. Em 422 e 409 o painel volta preenchido.

| Rota | Método | Quem | O que faz |
|---|---|---|---|
| `validacoes/formulario`, `validacoes` | GET, POST | Planejador ou Admin | Valida a programação (elaboração para validada) e define o fiscal, com comentário ao fornecedor |
| `realizados/formulario`, `realizados` | GET, POST | Encarregado, Fornecedor ou Admin | Lança o realizado por turno (dia e noite), com "= previsto", "Copiar a semana", PPC e desvio vivos; desvio acima do limite exige justificativa |
| `aprovacoes/formulario`, `aprovacoes` | GET, POST | Fiscal da atividade ou Admin | Aprova o realizado (ele congela) |
| `reaberturas/formulario`, `reaberturas` | GET, POST | Fiscal da atividade ou Admin | Reabre o realizado aprovado, com o motivo nos comentários |
| `publicacoes` | POST | Planejador ou Admin | Publica uma atividade validada (`atividade`, `versao`) |
| `publicacoes/semana` | POST | Planejador ou Admin | Publica todas as validadas da semana (as demais ficam) |
| `atividades/detalhe` | GET | Quem vê a atividade | Painel só de leitura: dias, observações e comentários |

Previstos nas próximas issues: `pedidos-de-alteracao` e `governanca` (053), `configuracoes` (054), `importacoes` e `exportacoes` (055), `dashboard` (056).

## Estrutura portada do app

| Arquivo | O que tem | Origem no app |
|---|---|---|
| `weeks.py` | Semana `S.30/2026`, segunda a domingo, ISO (2026 tem 53), `week_dates`, `shift`, `horizon` | `core/semanas.py` |
| `calculations.py` | Os sete dias, total, PPC, faixa, aderência, PPC médio, `figures_of` | `core/calculos.py` |
| `window.py` | `decide`: extraordinária vence, depois semana liberada, depois dia e hora | `core/janela.py` |
| `permissions.py` | Quem cria, edita, valida, lança o realizado, aprova, publica e exclui (papel por projeto, D7) | `core/rbac.py` |
| `flow.py` | Regras puras do fluxo: `next_action` (o botão da linha), `menu_of`, `actions_of` e as guardas de cada passo | `core/rbac.py` (`proxima_acao`) e `core/dados.py` |
| `workflow.py` | Fachada dos passos: `validate_activity`, `report_done`, `approve_done`, `reopen_done`, `publish_activity`, `publish_week` | `core/dados.py` |
| `validation.py` | Formulário da atividade, obrigatórios, soma dos dias com tolerância de 0,51 | `blueprints/atividades.py` |
| `service.py` | Fachada: recorte por empresa, janela, Portfólio somente leitura, gravação pelo `recording` | `core/registro.py`, `core/dados.py` |
| `repository.py`, `models.py` | Consultas e tabelas `programacao_*` (migração `m051`) | `core/repositorio.py` (JSON) |
| `views.py`, `presentation.py`, `screen.py` | Linha da matriz com os textos decididos no Python, grade dos dias, pastilhas, cabeçalhos | `templates/programacao/*` |
| `seed.py`, `demonstracao.json` | Carga: o ambiente `demo-obra` do app no projeto `TN-2026-014`, datas e semanas deslocadas | `data/demo-obra` |

Tradução de termos do app: ambiente = projeto, empresa = `company`, encarregado = `foreman`, responsável (fiscal) = `inspector`, atividade = `Activity`, `dias_previsto` = `planned_days`, `dias_realizado` = turno dia (`day_shift`), `dias_noite` = `night_shift`, `id_exclusiva` = `unique_id`, situação = `situation`, aprovação do realizado = `approval`.

## Fórmulas do fluxo

| Termo de negócio | Nome no código | Definição |
|---|---|---|
| PPC da atividade | `calculations.activity_ppc` | Realizado (dia mais noite) sobre previsto, em %; zero sem previsto |
| Aderência ponderada do conjunto | `calculations.schedule_adherence` | Soma do realizado sobre soma do previsto, em %; atividade grande pesa mais |
| Faixa alta, média, baixa | `calculations.performance_band` | 80% ou mais, 60% a 79,99%, abaixo de 60% |
| Desvio do realizado | `calculations.deviation_percent` | Distância do realizado ao previsto, em % do previsto |
| Desvio que exige justificativa | `calculations.needs_deviation_note` | Regra ligada no projeto e desvio acima do limite (no limite exato não exige; sem previsto não exige) |
| Próxima ação da linha | `flow.next_action` | Na ordem do fluxo: validar, aprovar, lançar, publicar; sem passo, "ver" |

## Quem faz cada passo (D7, por projeto)

Planejador valida e publica; Encarregado e Fornecedor lançam o realizado (o fornecedor só da própria empresa); o Fiscal aprova ou reabre **só as atividades em que ele é o fiscal responsável**; Admin faz todos. Fiscal e Visualizador não lançam; Planejador não lança nem aprova. A linha da matriz mostra o botão da próxima ação de quem olha e um menu só com o que o perfil ainda pode fazer; no Portfólio só resta "Ver".

## Fluxo de estado

Fornecedor cria/edita na janela → Planejador valida e define fiscal → Fornecedor informa realizado por turno dia/noite → Fiscal aprova (o realizado congela) → Planejador publica. Situação da programação e aprovação do realizado são estados distintos. Um pedido aprovado pode reabrir uma programação publicada com trilha.

## Integrações

Projeto, empresas, colaboradores, fiscais e encarregados vêm de Configurações. A identidade e o papel da pessoa vêm da plataforma GestNow; fornecedor só acessa a própria empresa. Para isso as rotas declaram `Access(module="programacao_semanal")` e a fachada chama `core.rbac`: `company_scope(user)` corta a consulta pela empresa do fornecedor (e `require_company` recusa a de outra), e `has_schedule_role` / `require_schedule_role(user, project_id, *roles)` conferem o papel no projeto em que a pessoa o recebeu (Planejador, Fiscal, Encarregado, Fornecedor; o papel não vale em outro projeto). O fornecedor não tem permissão geral nenhuma: na programação ele age pelos papéis. O módulo não mantém cadastro paralelo de pessoas/empresas. A saída alimenta o dashboard da programação e os relatórios previstos.

## Parâmetros

Cada projeto tem seus parâmetros e janelas: limites de PPC/aderência, limite de desvio que exige justificativa, semanas/dias/horários liberados e liberações extraordinárias. Projeto novo recebe valores padrão. A alteração vale na hora e deixa auditoria (ISSUE-054).

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` (e `screen.py` para o que a tela imprime) |
| Fluxo, recorte por empresa e janela | `flow.py`, `workflow.py`, `service.py`, `window.py`, `permissions.py` |
| PPC, aderência e faixas | `calculations.py` |
| Validações da atividade/planilha | `validation.py` |
| Planilha e impressão | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/programacao_semanal/` (`_tabela.html` é a matriz; `formulario.html`, `validacao.html`, `realizado.html`, `aprovacao.html`, `reabertura.html` e `detalhe.html` os painéis) |
| Carga de demonstração | `seed.py` e `demonstracao.json` |
| Tela, estilo e comportamento | `app/_views/programacao_semanal/` e `app/paginas/programacao_semanal/` |
| Testes | `api/tests/programacao_semanal/` |

O app de origem e seu glossário ficam somente para consulta em `docs/referencia/programacao-semanal/`. Multi-ambiente, seletor de clientes, área do operador, login próprio, SharePoint/JSON e API JSON de leitura permanecem fora de escopo. A ISSUE-051 trouxe a matriz e a programação pelo fornecedor; a ISSUE-052 trouxe os cinco passos (validar, realizado por turno, aprovação do fiscal, reabertura e publicação); as ISSUE-053 a ISSUE-056 completam o resto.
