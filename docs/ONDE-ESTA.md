# Onde está o quê no Timenow GestNow

Mapa do repositório nesta etapa inicial. Os módulos de domínio e o mapa "quero mudar X, abro Y" serão acrescentados na ISSUE-002.

## Aplicação

| Procurando | Está em | Estado atual |
|---|---|---|
| Documento completo e shell | `app/index.html` | Carrega o Design System, Alpine AJAX e Alpine.js |
| Tela inicial | `app/_views/home.html` | Estado vazio, sem tela de domínio |
| Tokens e componentes visuais | `app/ds/tokens.css` | Fonte dos tokens e componentes atômicos |
| Estrutura de página e sidebar | `app/ds/shell.css` | Layout do Padrão Timenow |
| Padrões reutilizáveis | `app/ds/patterns.css` | Composições de interface |
| Ícones e utilitários de interface | `app/ds/icons.js`, `app/ds/ui.js` | Biblioteca do Design System |
| Bibliotecas vendorizadas | `app/lib/` | Alpine AJAX e Alpine.js; não editar |
| Acesso local de demonstração | `app/login.html`, `scripts/dev_local.py` | Simulado localmente; SSO será ligado em issue futura |

## Backend e execução local

| Procurando | Está em | Estado atual |
|---|---|---|
| Registro de Functions | `api/function_app.py` | Registra saúde e navegação |
| Rota de saúde | `api/src/blueprints/health.py` | `GET /api/health` |
| Rota da sidebar | `api/src/blueprints/nav.py` | `GET /api/nav`, com Início |
| Fragmento da sidebar | `api/src/templates/nav/sidebar.html` | Servido pelo blueprint de navegação |
| Renderização de fragmentos | `api/src/core/responses.py` | `AlpineAjaxResponse` e gate Alpine AJAX |
| Preparação local | `run.bat` | Cria `api/.venv` e sobe o servidor Python sem `func` |
| Servidor de desenvolvimento | `scripts/dev_local.py` | Serve os arquivos e encaminha as duas rotas de plataforma |
| Porta de qualidade | `scripts/verificar.mjs` | Ruff, ty, ESLint e verificações Timenow |

Não há banco, fachada de domínio ou rota de módulo nesta issue. O banco Postgres começa na ISSUE-005.

## Documentação e referências

| Procurando | Está em |
|---|---|
| Fonte da migração | `docs/SPEC-MIGRACAO-GESTNOW.md` |
| Issues e fila de execução | `docs/issues/spec-migracao-gestnow/` |
| Regras herdadas do Padrão | `docs/PADRAO-DE-CODIGO.md`, `docs/CONTRATO-VISUAL.md`, `docs/DESIGN-SYSTEM.md` |
| Guia de operação das referências | `docs/referencia/LEIA-ME.md` |
| Visuais originais | `docs/referencia/graficos/` |
| Protótipo e ferramentas de consulta | `docs/referencia/prototipo/` |
| App de Programação Semanal | `docs/referencia/programacao-semanal/` |
| Skills de agente | `.agents/skills/` e `.claude/skills/` |

## Estrutura copiada do Padrão

```text
Timenow - GestNow/
  app/                 shell, Design System, bibliotecas e views
  api/                 Azure Functions, blueprints e templates Jinja2
  docs/                especificação, issues, padrão e referências
  scripts/             instalação, execução local e porta de qualidade
  .agents/skills/      skills de desenvolvimento
  .claude/              configuração e skills do Claude
  run.bat               execução local por duplo clique
```

As pastas de origem são somente leitura durante esta execução. Os arquivos de `docs/referencia/` são cópias preservadas para consulta.
