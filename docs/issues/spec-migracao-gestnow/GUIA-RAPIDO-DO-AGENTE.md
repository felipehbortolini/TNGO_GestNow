# Guia rápido do agente: a plataforma já pronta

> Leia isto em vez de explorar o repositório. As assinaturas atuais de tudo que
> existe em `api/src/core`, `api/src/blueprints` e `api/src/carga` saem de
> `python scripts/execucao/gerar_api_sheet.py`.

## Mapa

- Backend: `api/src/core/` (plataforma), `api/src/modulos/<modulo>/{routes,service,calculations,validation,export,models}.py`
  e `LEIA-ME.md`, `api/src/templates/<modulo>/` (fragmentos Jinja),
  `api/src/blueprints/` (shell: health, nav), `api/migrations/versions/`,
  `api/tests/<modulo>/`.
- Front: `app/index.html` (shell), `app/ds/` (tokens.css, shell.css,
  patterns.css, ui.js, icons.js, shell.js, dica.js), `app/_views/<modulo>/<tela>.html`
  (view), `app/paginas/<modulo>/<tela>.{css,js}` (o trio da tela), `app/lib/`
  (Alpine e Alpine AJAX).
- Lista única de telas e navegação: `api/src/core/navegacao.json` (lida por
  `api/src/core/navigation.py`).

## Receita de uma fatia vertical

1. **Modelo:** `api/src/modulos/<m>/models.py` (SQLAlchemy 2; nomes de tabela e
   coluna em português snake_case como em `docs/MODELO-DE-DADOS.md`; modelos em
   inglês) e **uma** migração Alembic nova em `api/migrations/versions/`, no
   formato das anteriores. Detalhe de uma tabela:
   `grep -n -A12 '`nome_da_tabela`' docs/MODELO-DE-DADOS.md` (não leia inteiro).
2. **Fachada** `service.py` do módulo dono: funções com a sessão, o usuário, o
   escopo e a data de referência como argumentos. Grava só por
   `src.core.recording` (`create`, `update`, `delete`: trilha, versão e
   transação juntas); numeração por projeto em `src.core.numbering`; dinheiro em
   centavos (`Centavos`); "hoje" só de `src.core.calendario.today()` e só nas
   bordas (a fórmula recebe a data). Um módulo nunca lê nem grava tabela de
   outro: usa a fachada do dono.
3. **Cálculos puros** em `calculations.py`, uma função por regra, com o nome de
   negócio no `LEIA-ME.md` e teste com o caso de fronteira.
4. **Rota** em `routes.py` do módulo: `bp = func.Blueprint()` (já registrado em
   `api/function_app.py`), `@bp.route(route="<modulo>/<tela>", methods=[...])` e
   `@fragment_route` (de `src.core.routing`: gate do Alpine, transação e mapa de
   erros). O handler recebe `(req, session)` e devolve
   `AlpineAjaxResponse(template_name="<modulo>/<fragmento>.html", context={...}, request=req, ...)`
   (de `src.core.responses`; aceita toast e multi-alvo). Erros de domínio de
   `src.core.errors`: `InvalidDataError` (422, formulário preenchido via
   `on_error`), `AccessDeniedError` (403), `VersionConflictError` (409). Exemplo
   vivo: `api/src/blueprints/nav.py`.
5. **Template Jinja** em `api/src/templates/<modulo>/` (parta de
   `api/src/templates/base_fragment.html`); fragmento sem `<link>`, `<style>` nem
   `<script>`; dados de gráfico em `data-*`.
6. **Tela:** a view em `app/_views/<modulo>/<tela>.html` e o CSS e o JS da página
   em `app/paginas/<modulo>/<tela>.{css,js}` (o shell vincula todos; CSS
   escopado por `.pagina--<modulo>-<tela>` e só com tokens; JS registra
   `TN.paginas["<modulo>/<tela>"]` com `iniciar(raiz)`). Cinco estados:
   carregando, vazio de origem, vazio por filtro, erro e sem permissão.
7. **Carga de demonstração:** `api/src/modulos/<m>/seed.py` com
   `register("<m>", load)` (veja `api/src/carga/LEIA-ME.md`). Sem os mocks do
   protótipo, o critério de carga e o de oráculo ficam pendentes
   (`PENDENCIAS-DE-FONTE.md`).
8. **Testes** em `api/tests/<modulo>/test_*.py`: fixture `db_session`
   (transação desfeita) em `api/tests/conftest.py`; para rota, monte um
   `func.HttpRequest` com o cabeçalho de Alpine e chame o handler (veja
   `api/tests/plataforma/test_rota_conflito.py` e `test_navegacao.py`); cálculo
   com tabela de casos e fronteiras.

## O que mais derruba a porta de qualidade

- Python (arquivos, funções, classes, docstrings, comentários) em inglês;
  interface, CSS, JS, rotas, HTML e tabelas em português com acento correto.
- Ruff rígido (`api/pyproject.toml`): complexidade ≤ 10, no máximo 5 argumentos
  posicionais (use keyword-only depois de `*`), sem booleano posicional, sem
  `print`, sem código comentado, `pathlib` em vez de `os.path`, datas com fuso.
  Rode `ruff format` antes de entregar.
- JS, CSS e HTML passam no ESLint e no `scripts/verificar-padrao.mjs`: só tokens
  (sem hexadecimal solto), BEM, namespace `TN`, sem recurso externo.
- Fórmula nova: nome, teste de fronteira, data por argumento. Gravação: sempre
  pela fachada com `recording`.

## Decisões que valem para todas as issues

Q30 modelo aceito; Q31 divergência do protótipo vai para
`docs/DIVERGENCIAS-DO-PROTOTIPO.md` como "pendente de aceite"; Q35 nome e dados
médicos do HSE só Gestor e Admin leem; a spec vence a issue; nenhuma regra de
lint desligada.
