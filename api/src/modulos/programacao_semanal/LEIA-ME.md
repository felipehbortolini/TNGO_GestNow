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

## Rotas (ISSUE-051 e ISSUE-052)

Prefixo `/api/programacao-semanal/`. Todas declaram `Access(module="programacao_semanal")` (o fornecedor alcança o módulo; o recorte por empresa e o papel são da fachada) e respondem fragmento com alvos de id fixo: `prog-janela`, `prog-filtros`, `prog-resumo`, `prog-tabela` e `drawer`.

| Rota | Método | O que devolve |
|---|---|---|
| `programacoes` | GET | Faixa de indicadores + matriz da semana (`semana`, `local`, `empresa`, `encarregado`, `responsavel`, `situacao`, `aprovacao`, `ppc`, `busca`, `ordena`, `ordem`) |
| `programacoes/filtros` | GET | Barra de ferramentas: semana, busca, painel de refino e a ação "Publicar as validadas" (Planejador) |
| `programacoes/janela` | GET | Faixa da janela (aberta, fechada e o motivo; no Portfólio, "só leitura") |
| `atividades/formulario` | GET | Painel de nova atividade (`semana`) ou de edição (`atividade`) |
| `atividades` | POST | Cria (sem `atividade_id`) ou salva; 422 e 409 devolvem o painel preenchido |
| `atividades/excluir` | POST | Exclui (só Admin, e só sem pedidos de alteração) e redesenha a matriz |
| `atividades/detalhe` | GET | Painel de leitura da atividade: ficha, grade dos dias e histórico |
| `validacoes/formulario` | GET | Painel de validar: o fiscal responsável e os comentários ao fornecedor |
| `validacoes` | POST | Valida a programação e define o fiscal; 422 e 409 devolvem o painel e a matriz |
| `realizados/formulario` | GET | Painel de anexar o realizado: os dois turnos e os atalhos |
| `realizados` | POST | Grava o realizado por turno/dia; o desvio acima do limite exige observação |
| `aprovacoes/formulario` | GET | Painel do fiscal: aprovar o realizado ou reabrir com motivo |
| `aprovacoes` | POST | Aprova o realizado (congela para o fornecedor) |
| `reaberturas` | POST | Reabre o realizado aprovado, com motivo |
| `publicacoes` | POST | Publica uma atividade validada e encerra a edição dela |
| `publicacoes/semana` | POST | Publica todas as validadas da semana que a pessoa vê |

Os painéis do fluxo declaram `x-target="drawer prog-resumo prog-tabela"`: no 422/409 a resposta traz o painel **e** a faixa e a matriz, porque alvo declarado que não vem na resposta é esvaziado pelo Alpine AJAX.

Previstas nas próximas issues: `pedidos-de-alteracao` e `governanca` (053), `configuracoes` (054), `importacoes` e `exportacoes` (055), `dashboard` (056).

## Estrutura portada do app

| Arquivo | O que tem | Origem no app |
|---|---|---|
| `weeks.py` | Semana `S.30/2026`, segunda a domingo, ISO (2026 tem 53), `week_dates`, `shift`, `horizon` | `core/semanas.py` |
| `calculations.py` | Os sete dias, total, PPC, faixa, aderência, PPC médio, `figures_of` | `core/calculos.py` |
| `window.py` | `decide`: extraordinária vence, depois semana liberada, depois dia e hora | `core/janela.py` |
| `permissions.py` | Quem cria, edita, valida, lança, aprova, publica e exclui (papel por projeto, D7) e `next_action`, a fila dos cinco degraus | `core/rbac.py` |
| `validation.py` | Formulário da atividade (obrigatórios, soma dos dias com tolerância de 0,51) e os painéis do fluxo (validar, realizado, aprovar/reabrir) | `blueprints/atividades.py` |
| `service.py` | Fachada: recorte por empresa, janela, Portfólio somente leitura, gravação pelo `recording`, as transições do fluxo e a regra do desvio | `core/registro.py`, `core/dados.py` |
| `repository.py`, `models.py` | Consultas e tabelas `programacao_*` (migração `m051`); a trilha de uma atividade para o painel de detalhe | `core/repositorio.py` (JSON) |
| `views.py`, `presentation.py`, `screen.py` | Linha da matriz com os textos e as ações decididos no Python, grade dos dias, pastilhas, cabeçalhos, contextos dos painéis | `templates/programacao/*` |
| `seed.py`, `demonstracao.json` | Carga: o ambiente `demo-obra` do app no projeto `TN-2026-014`, datas e semanas deslocadas | `data/demo-obra` |

Tradução de termos do app: ambiente = projeto, empresa = `company`, encarregado = `foreman`, responsável (fiscal) = `inspector`, atividade = `Activity`, `dias_previsto` = `planned_days`, `dias_realizado` = turno dia (`day_shift`), `dias_noite` = `night_shift`, `id_exclusiva` = `unique_id`, situação = `situation`, aprovação do realizado = `approval`.

## Fluxo de estado (ISSUE-052)

Fornecedor cria/edita na janela → **Planejador valida e define o fiscal** → Encarregado/Fornecedor informa o realizado por turno dia/noite → **Fiscal aprova (o realizado congela) ou reabre com motivo** → **Planejador publica** (a edição da semana encerra). Situação da programação (`em_elaboracao`, `validada`, `publicada`) e aprovação do realizado (`pendente`, `aprovado`) são estados distintos: uma atividade publicada pode ter realizado pendente.

Cada transição só é aceita do papel certo no projeto (D7) — validar e publicar do Planejador, lançar do Encarregado ou Fornecedor, aprovar/reabrir do Fiscal, e o Admin faz tudo; os demais recebem 403. Só se lança sobre programação validada, e o realizado aprovado não muda mais.

O realizado entra por turno, dia a dia, com os atalhos **"= previsto"** e **"copiar a semana"** na tela. Quando o desvio do total passa do parâmetro `limite_desvio_justificativa` e `exige_justificativa_desvio` está ligado, a **observação é obrigatória**; a conta é `abs(total − previsto) / previsto × 100`, a mesma do app (`calculations.deviation_percent`). A matriz mostra, em cada linha, o **botão da próxima ação** de quem está olhando e o menu só com o que o perfil pode fazer: a regra é `permissions.next_action`, a fila validar → lançar → aprovar → publicar → ver. "Publicar as validadas" publica a semana inteira de uma vez.

Um pedido aprovado pode reabrir uma programação publicada com trilha (ISSUE-053).

## Integrações

Projeto, empresas, colaboradores, fiscais e encarregados vêm de Configurações. A identidade e o papel da pessoa vêm da plataforma GestNow; fornecedor só acessa a própria empresa. Para isso as rotas declaram `Access(module="programacao_semanal")` e a fachada chama `core.rbac`: `company_scope(user)` corta a consulta pela empresa do fornecedor (e `require_company` recusa a de outra), e `has_schedule_role` / `require_schedule_role(user, project_id, *roles)` conferem o papel no projeto em que a pessoa o recebeu (Planejador, Fiscal, Encarregado, Fornecedor; o papel não vale em outro projeto). O fornecedor não tem permissão geral nenhuma: na programação ele age pelos papéis. O módulo não mantém cadastro paralelo de pessoas/empresas. A saída alimenta o dashboard da programação e os relatórios previstos.

## Parâmetros

Cada projeto tem seus parâmetros e janelas: limites de PPC/aderência, limite de desvio que exige justificativa, semanas/dias/horários liberados e liberações extraordinárias. Projeto novo recebe valores padrão. A alteração vale na hora e deixa auditoria (ISSUE-054).

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` (e `screen.py` para o que a tela imprime) |
| Fluxo, recorte por empresa e janela | `service.py`, `window.py`, `permissions.py` |
| PPC, aderência e faixas | `calculations.py` |
| Validações da atividade/planilha | `validation.py` |
| Planilha e impressão | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/programacao_semanal/` (`_tabela.html` é a matriz; `formulario.html` o painel da atividade; `_validar.html`, `_realizado.html`, `_aprovacao.html` e `_detalhe.html` os painéis do fluxo) |
| Carga de demonstração | `seed.py` e `demonstracao.json` |
| Tela, estilo e comportamento | `app/_views/programacao_semanal/` e `app/paginas/programacao_semanal/` |
| Testes | `api/tests/programacao_semanal/` |

O app de origem e seu glossário ficam somente para consulta em `docs/referencia/programacao-semanal/`. Multi-ambiente, seletor de clientes, área do operador, login próprio, SharePoint/JSON e API JSON de leitura permanecem fora de escopo. A ISSUE-051 trouxe a matriz e a programação pelo fornecedor; a ISSUE-052, o fluxo de cinco passos; as ISSUE-053 a ISSUE-056 completam o resto do módulo.

## Testes

- `test_programacao_dominio.py`: semanas, cálculos (incluindo o oráculo de PPC e aderência com a semana S.34/2026 da demonstração) e janela.
- `test_programacao_fachada.py`: recorte por empresa, janela, Portfólio e gravação.
- `test_programacao_rotas.py`: o HTTP da matriz e do formulário, e o `Access` de toda rota.
- `test_programacao_fluxo.py`: a fila da próxima ação por perfil (portada do app), as transições, a regra do desvio e a trilha.
- `test_programacao_fluxo_rotas.py`: os 403 de cada papel, o fornecedor só da própria empresa, 422/409 e o botão/menu por perfil na matriz.
- `api/tests/plataforma/test_carga_demonstracao.py`: o oráculo do fluxo na carga (estados e próximas ações).
