# Governança

Módulo `governanca`. Controla solicitações de mudança (SM) e lições aprendidas, processos transversais aos módulos do projeto. As funcionalidades chegam nas ISSUE-023 a ISSUE-028; integrações são ativadas na issue do módulo que chega por último (D9).

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Registro e painel de mudanças | Lista, etapa, próxima decisão e indicadores | ISSUE-023, ISSUE-026 |
| Ficha da mudança | Solicitação, impacto, decisão, implementação e histórico | ISSUE-023 a ISSUE-025 |
| Acervo de lições | Busca, filtros, aplicabilidade e aplicação em projeto | ISSUE-027 |
| Painel de lições | Lições publicadas, reuso e projetos sem registro | ISSUE-028 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Gestão de mudanças | `app/_views/governanca/mudancas.html` | `app/paginas/governanca/mudancas.css` | `app/paginas/governanca/mudancas.js` |
| Solicitação de mudança | `app/_views/governanca/mudanca.html` | `app/paginas/governanca/mudanca.css` | `app/paginas/governanca/mudanca.js` |
| Lições aprendidas | `app/_views/governanca/licoes.html` | `app/paginas/governanca/licoes.css` | `app/paginas/governanca/licoes.js` |

## Rotas previstas

Prefixo: `/api/governanca/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `mudancas` | Criar/listar e consultar SM | ISSUE-023 |
| `mudancas/{codigo}/analise` | Registrar impacto e calcular alçada | ISSUE-024 |
| `mudancas/{codigo}/decisao` e `implementacao` | Decidir, integrar ações e encerrar | ISSUE-025 |
| `painel-de-mudancas` | Consultar indicadores de mudanças | ISSUE-026 |
| `licoes` e `licoes/{codigo}/aplicacoes` | Validar/publicar/aplicar lição | ISSUE-027 |
| `painel-de-licoes` | Consultar indicadores do acervo | ISSUE-028 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Alçada mínima da mudança | Gerente se o custo cabe no limite percentual do orçamento e não afeta marco contratual; caso contrário, Comitê | `calculations.minimum_change_authority` |
| Prazo de ratificação emergencial | Data de início mais o prazo configurado para a ratificação | `calculations.emergency_ratification_due_date` |

O analista pode elevar, mas não rebaixar, a alçada calculada. A pessoa que elabora uma lição não pode validá-la.

## Fluxos

SM: Registrada → Em análise de impacto → Aguardando decisão → Aprovada/Aprovada com condições/Rejeitada/Adiada → Em implementação → Encerrada. Cancelamento antes da decisão exige justificativa. Lição: Rascunho → Em validação → Validada → Publicada; devolução retorna a Rascunho com comentário.

## Integrações

Recebe impactos de Financeiro, Planejamento, Contratos e Riscos. Aprovação cria ações na Central e fornece SM para revisões donas de EAC/EAP/contratos. Lições podem nascer de Riscos, Qualidade, HSE e demais origens; sua aplicação cria ação na Central ou risco em Riscos. Cada escrita chama a fachada dona da entidade, na transação.

## Parâmetros

Limite de alçada do Gerente (até 1% do orçamento e sem impacto contratual inicialmente), quórum de Comitê (3), prazo de análise (10 dias), prazo de ações (15), ratificação emergencial (7) e alerta de lições sem registro (90 dias). São versionados em Configurações.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Transições, permissões e integrações | `service.py` |
| Alçada e prazos derivados | `calculations.py` |
| Validação de impacto/decisão | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades na ISSUE-003 |
| Fragmentos | `api/src/templates/governanca/` |
| Tela, estilo e comportamento | `app/_views/governanca/` e `app/paginas/governanca/` |
| Testes | `api/tests/governanca/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-023 a ISSUE-028 completam este documento e acrescentam testes de fronteira/segregação.
