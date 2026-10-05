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
| Modelos do módulo | `api/src/modulos/<modulo>/models.py` | Dono das entidades; stubs nesta issue, modelo completo nas ISSUE-003/004 |
| LEIA-ME do módulo | `api/src/modulos/<modulo>/LEIA-ME.md` | Referência de manutenção sem depender do código ou de IA |
| Fragmentos de domínio | `api/src/templates/<modulo>/` | Jinja2 devolvido pelas rotas do módulo |
| Fragmento da sidebar | `api/src/templates/nav/sidebar.html` | Navegação global do shell |
| Testes | `api/tests/<modulo>/` | Testes de cálculo, serviço, integração e rota do módulo |
| Renderização de fragmentos | `api/src/core/responses.py` | `AlpineAjaxResponse` e gate Alpine AJAX |

As pastas existem antes das funcionalidades. Rotas de módulo são blueprints sem endpoints até as respectivas issues; não há banco nem comportamento de negócio novo nesta fundação. Postgres começa na ISSUE-005.

## Execução e qualidade

| Procurando | Está em |
|---|---|
| Executar localmente | `run.bat` e `scripts/dev_local.py` |
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
