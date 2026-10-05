# Onde está o quê no Timenow GestNow

Mapa de manutenção do produto. Para a resposta direta a “quero mudar X, abro Y”, use também [MAPA-DE-MODULOS.md](MAPA-DE-MODULOS.md). A estrutura e as convenções por módulo estão em [ADR-0001](adr/0001-convencao-de-subpastas-por-modulo.md).

## Comece por aqui

| Procurando | Abra |
|---|---|
| Vocabulário de negócio e termos técnicos do produto | [`CONTEXT.md`](../CONTEXT.md) |
| Módulo dono, arquivos por camada, telas, fórmulas e fluxos | O `LEIA-ME.md` de cada módulo em `api/src/modulos/<modulo>/` |
| Mapa “quero mudar X, abro Y” | [`MAPA-DE-MODULOS.md`](MAPA-DE-MODULOS.md) |
| O que a migração pede e suas decisões | [`SPEC-MIGRACAO-GESTNOW.md`](SPEC-MIGRACAO-GESTNOW.md) |
| Fila e critérios das issues | `docs/issues/spec-migracao-gestnow/` |

## Front-end

| Procurando | Está em | Responsabilidade |
|---|---|---|
| Documento completo e shell | `app/index.html` | Carrega Design System, Alpine AJAX, views e estado inicial do Início |
| Início atualmente vazio | `app/_views/inicio/home.html` | Preserva a tela de entrada até as issues 079/080 |
| Views de um módulo | `app/_views/<modulo>/<tela>.html` | Fragmentos HTML, um por tela |
| CSS e JavaScript de página | `app/paginas/<modulo>/<tela>.css` e `.js` | Trio por tela conforme D3/ISSUE-010; CSS usa tokens |
| Design System | `app/ds/` | `tokens.css`, `shell.css`, `patterns.css`, ícones, UI e assets |
| Biblioteca de gráficos | `app/ds/graficos/` | Destino dos visuais portados nas ISSUE-014 a ISSUE-016 |
| Alpine.js e Alpine AJAX | `app/lib/` | Bibliotecas vendorizadas; não editar |

## Backend

| Procurando | Está em | Responsabilidade |
|---|---|---|
| Registro de Azure Functions | `api/function_app.py` | Registra blueprints de plataforma e dos 12 módulos |
| Rotas de plataforma | `api/src/blueprints/` | Saúde e navegação global |
| Rotas e fachada de um módulo | `api/src/modulos/<modulo>/routes.py` e `service.py` | HTTP no blueprint; fluxo, permissões e integrações na fachada |
| Fórmulas, validação e exportação | `api/src/modulos/<modulo>/calculations.py`, `validation.py`, `export.py` | Regra pura, entrada e saídas do módulo |
| Modelos do módulo | `api/src/modulos/<modulo>/models.py` | Dono das entidades; as tabelas de plataforma e dos cadastros nasceram na ISSUE-005, as de domínio em cada fatia de módulo |
| LEIA-ME do módulo | `api/src/modulos/<modulo>/LEIA-ME.md` | Referência de manutenção sem depender do código ou de IA |
| Sessão, base dos modelos e relatório do banco | `api/src/core/database.py` | `GESTNOW_DATABASE_URL`, engine SQLAlchemy, `Base` dos modelos, revisão da migração e a unidade de trabalho (`unidade_de_trabalho`) |
| Gravação segura (trilha, versão, numeração e dinheiro) | `api/src/core/recording.py`, `audit.py`, `versioning.py`, `numbering.py` e `money.py` | A forma única de gravar registro editável com trilha, o 409 de edição simultânea, a numeração por projeto e os centavos formatados só na apresentação (ISSUE-006) |
| Erros de domínio e decorador de rota | `api/src/core/errors.py` e `routing.py` | `AccessDeniedError`/`InvalidDataError`/`VersionConflictError`; `fragment_route` com gate, transação e o mapa 403/409/422 |
| Configuração local | `api/src/core/config.py` | Carrega `api/local.settings.json` (fora do git) para o ambiente |
| Modelos da plataforma | `api/src/core/models.py` | Cliente, sequência, auditoria, anexo e notificação |
| Migrações Alembic | `api/migrations/` | Uma revisão por fatia de módulo, a partir de `0001_plataforma` |
| Fragmentos de domínio | `api/src/templates/<modulo>/` | Jinja2 devolvido pelas rotas do módulo |
| Fragmento da sidebar | `api/src/templates/nav/sidebar.html` | Navegação global do shell |
| Testes | `api/tests/<modulo>/` e `api/tests/conftest.py` | Testes por módulo; o conftest recria `gestnow_teste` e isola cada teste numa transação |
| Renderização de fragmentos | `api/src/core/responses.py` | `AlpineAjaxResponse` e gate Alpine AJAX |

As pastas existem antes das funcionalidades. Rotas de módulo são blueprints sem endpoints até as respectivas issues. O Postgres nasceu na ISSUE-005: o `run.bat` prepara o banco local e as migrações por módulo são aplicadas na mesma fatia que cria as tabelas.

## Execução e qualidade

| Procurando | Está em |
|---|---|
| Executar localmente | `run.bat` e `scripts/dev_local.py` |
| Preparar o banco local (papel, bancos e migrações) | `scripts/prepare_database.py` e `GESTNOW_PG_ADMIN_URL` |
| Rodar os testes | `api/.venv/Scripts/python.exe -m pytest` (dentro de `api/`) |
| Instalar dependências | `scripts/instalar.ps1` |
| Porta de qualidade | `npm run verificar` → `scripts/verificar.mjs` |
| Verificações do Design System e estrutura | `scripts/verificar-padrao.mjs` |
| Skills de desenvolvimento | `.agents/skills/`; comece por `padrao-de-codigo` |

## Documentação e referências

| Procurando | Está em |
|---|---|
| Convenção das subpastas por módulo | `docs/adr/0001-convencao-de-subpastas-por-modulo.md` |
| Regras herdadas do Padrão | `docs/PADRAO-DE-CODIGO.md`, `docs/CONTRATO-VISUAL.md`, `docs/DESIGN-SYSTEM.md` |
| Guia das referências preservadas | `docs/referencia/LEIA-ME.md` |
| Visuais originais | `docs/referencia/graficos/` |
| Protótipo e ferramentas de consulta | `docs/referencia/prototipo/` |
| App de Programação Semanal | `docs/referencia/programacao-semanal/` |

As referências dentro de `docs/referencia/` são cópias para consulta. As pastas de origem ficam somente para leitura; nenhuma issue de implementação grava nelas.
