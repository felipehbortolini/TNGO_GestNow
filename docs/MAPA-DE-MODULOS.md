# Mapa de módulos

Use este mapa para localizar a alteração sem conhecer o código. Abra primeiro o `LEIA-ME.md` do módulo; ele registra telas, rotas previstas, fórmulas, estados, integrações e parâmetros, e é atualizado pela issue que implementa cada comportamento.

## Quero mudar...

| Quero mudar... | Abra... |
|---|---|
| Texto que aparece numa tela | O fragmento em `api/src/templates/<modulo>/<fragmento>.html`; para texto estático/estrutura, `app/_views/<modulo>/<tela>.html` |
| Layout de uma página | `app/_views/<modulo>/<tela>.html`; se a composição é comum ao shell, `app/ds/shell.css` |
| Estilo de uma tela | `app/paginas/<modulo>/<tela>.css`; regra comum do Design System fica em `app/ds/tokens.css`, `shell.css` ou `patterns.css`, conforme `docs/ONDE-ESTA.md` |
| Gráfico | `app/ds/graficos/<visual>.js` (biblioteca compartilhada, nas ISSUE-014 a ISSUE-016); aplicação e dados no `<tela>.js` do módulo; original de referência em `docs/referencia/graficos/` |
| Fórmula ou cálculo | `api/src/modulos/<modulo>/calculations.py`; teste de fronteira em `api/tests/<modulo>/` |
| Regra de fluxo | `api/src/modulos/<modulo>/service.py` e o teste correspondente em `api/tests/<modulo>/` |
| Banco, sessão e URL de conexão | `api/src/core/database.py` (`GESTNOW_DATABASE_URL`) e `api/src/core/config.py` |
| Transação da requisição, trilha, versão, numeração e dinheiro | `api/src/core/database.py` (`unidade_de_trabalho`), `recording.py`, `audit.py`, `versioning.py`, `numbering.py` e `money.py` |
| Erros de domínio e resposta de erro de rota | `api/src/core/errors.py`, `api/src/core/routing.py` e `api/src/templates/comum/erro.html` |
| Tabela ou migração | `api/src/modulos/<modulo>/models.py` (tabelas de domínio), `api/src/core/models.py` e `api/src/modulos/configuracoes/models.py` (plataforma e cadastros); revisão nova em `api/migrations/versions/` |
| Permissão | `api/src/modulos/<modulo>/service.py` e `api/src/core/rbac.py` (plataforma a chegar na ISSUE-011). A tela nunca é a autoridade de acesso |
| Parâmetro | `api/src/modulos/configuracoes/` e a validação/consumo em `api/src/modulos/<modulo>/validation.py`; Configurações versiona o valor, o módulo consumidor valida seu domínio |
| Exportação | `api/src/modulos/<modulo>/export.py`; exportador comum e impressão são introduzidos na ISSUE-017 |
| Importação | `api/src/modulos/<modulo>/validation.py` para regras de linha e o fluxo comum descrito na ISSUE-018; nada grava antes da confirmação |
| Integração entre módulos | `service.py` de quem inicia e fachada do módulo dono em `api/src/modulos/<modulo-dono>/service.py`; veja também a issue de integração ligada por último conforme D9 |
| Tradução PT/EN | Catálogo futuro `api/src/core/translations.py` (ISSUE-087/088) e texto-fonte nos fragmentos `api/src/templates/<modulo>/`; não coloque tradução de interface em JavaScript de página |

`<modulo>` usa o identificador em snake_case abaixo. Rotas públicas usam português minúsculo com hífen, sob `/api/` (ex.: `central_acoes` → `/api/central-acoes/`).

## Índice dos módulos

| Módulo | LEIA-ME.md | Telas/rotas começam em |
|---|---|---|
| `inicio` | [Início](../api/src/modulos/inicio/LEIA-ME.md) | `app/_views/inicio/`, `/api/inicio/` |
| `central_acoes` | [Central de Ações](../api/src/modulos/central_acoes/LEIA-ME.md) | `app/_views/central_acoes/`, `/api/central-acoes/` |
| `planejamento` | [Planejamento](../api/src/modulos/planejamento/LEIA-ME.md) | `app/_views/planejamento/`, `/api/planejamento/` |
| `programacao_semanal` | [Programação Semanal](../api/src/modulos/programacao_semanal/LEIA-ME.md) | `app/_views/programacao_semanal/`, `/api/programacao-semanal/` |
| `financeiro` | [Financeiro](../api/src/modulos/financeiro/LEIA-ME.md) | `app/_views/financeiro/`, `/api/financeiro/` |
| `suprimentos` | [Suprimentos](../api/src/modulos/suprimentos/LEIA-ME.md) | `app/_views/suprimentos/`, `/api/suprimentos/` |
| `riscos` | [Gestão de Riscos](../api/src/modulos/riscos/LEIA-ME.md) | `app/_views/riscos/`, `/api/riscos/` |
| `qualidade` | [Gestão da Qualidade](../api/src/modulos/qualidade/LEIA-ME.md) | `app/_views/qualidade/`, `/api/qualidade/` |
| `hse` | [HSE](../api/src/modulos/hse/LEIA-ME.md) | `app/_views/hse/`, `/api/hse/` |
| `governanca` | [Governança](../api/src/modulos/governanca/LEIA-ME.md) | `app/_views/governanca/`, `/api/governanca/` |
| `configuracoes` | [Configurações](../api/src/modulos/configuracoes/LEIA-ME.md) | `app/_views/configuracoes/`, `/api/configuracoes/` |
| `relatorio` | [Relatório Gerencial](../api/src/modulos/relatorio/LEIA-ME.md) | `app/_views/relatorio/`, `/api/relatorio/` |

## Fronteiras que preservam a localização

- Uma tela segue o mesmo identificador nas camadas: fragmento em `app/_views/<modulo>/<tela>.html`, CSS/JS em `app/paginas/<modulo>/<tela>.css` e `.js`, e fragmentos Jinja em `api/src/templates/<modulo>/`.
- Rotas e fachadas ficam em `api/src/modulos/<modulo>/`; um módulo lê ou grava dados de outro somente pela fachada dona, nunca por acesso direto ao modelo.
- O escopo dos dados é um projeto ou o Portfólio. “Ambiente” técnico significa implantação; o seletor multi-ambiente do app de origem não é portado.
- A persistência nasceu na ISSUE-005: Postgres com SQLAlchemy 2, migrações Alembic por fatia de módulo e testes isolados no banco `gestnow_teste`. Cada módulo é dono das próprias tabelas e um módulo só lê ou grava tabela de outro pela fachada do dono (D5).
