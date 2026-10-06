# Gestão de Riscos

Módulo `riscos`. Mantém ameaças e oportunidades, avaliações, respostas, revisões e encerramentos. Score e severidade são calculados no servidor a partir da escala vigente.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Registro de riscos | Lista, avaliação exibida, filtros e próximas revisões | ISSUE-064 |
| Matriz P x I | Contagem e navegação por probabilidade e impacto | ISSUE-066 |
| Ficha do risco | Identificação, avaliação, resposta, monitoramento e histórico | ISSUE-065 |
| Painel de riscos | Exposição, tendência residual e pauta de escalonamento | ISSUE-066 |

As integrações que chegam de Suprimentos, Contratos, Governança e Financeiro são ligadas nas ISSUE-067.

## O que a ISSUE-064 trouxe (Registro de riscos)

Tela `riscos/registro`: contexto do projeto, 5 KPIs clicáveis (faixa mais alta, segunda faixa, Em tratamento, Revisão vencida, Ativos), aviso de revisão vencida, chips, alternador Inerente/Residual, filtro completo no modal, tabela paginada e exportação Excel e PDF. Todo clique é um GET do mesmo fragmento `registro-conteudo` com os filtros na consulta. No Portfólio a tabela e as exportações trazem a coluna Projeto e "Novo risco" pede o projeto antes do formulário.

Rotas (`routes.py`, prefixo `/api/riscos/`): `registro`, `registro/excel`, `registro/imprimivel`, `novo` (GET/POST), `{codigo}/editar`, `{codigo}/avaliar`, `previa`, `{codigo}/excluir`, `{codigo}/restaurar`, `categorias/nova` e `categorias`. Templates em `api/src/templates/riscos/`; view, CSS e JS em `app/_views/riscos/registro.html` e `app/paginas/riscos/registro.{css,js}`.

Fórmulas (`calculations.py`, data de referência sempre por argumento):

| Nome no código | Definição de negócio |
|---|---|
| `risk_score` | probabilidade x impacto (1 a 25) |
| `risk_severity` | faixa da escala ativa (Timenow 4 faixas ou CIPM 3); risco à vida é sempre a faixa mais alta na CIPM |
| `resulting_impact`, `is_impact_reduced` | impacto = maior dimensão (pior caso); pode ser elevado, nunca reduzido |
| `expected_monetary_value` | VME = probabilidade média da faixa x impacto em custo, em centavos, meio para cima |
| `threat_exposure` | exposição do projeto = soma do VME só das ameaças |
| `review_cadence`, `is_review_overdue`, `is_review_due_soon` | cadência por severidade e revisão vencida/próxima |
| `next_code_number`, `format_code` | numeração `RSK-<padrão>-nnnn`, contando só sufixos numéricos |

Fluxos: score e severidade só no servidor (a prévia é `GET previa`); justificativa obrigatória quando o score muda; residual só com plano de resposta; exclusão lógica (`service.delete_risk`, Gestor) recusada com ação aberta (consulta `central_acoes.count_actions_of_origin`) e para risco encerrado, grava motivo, autor e data; só o Admin vê e restaura (`restore_risk`). A numeração é reservada na gravação (`reserve_code`). Migração `m064_registro_de_riscos`; carga em `seed.py`; oráculo em `api/tests/oraculo/test_oraculo_riscos.py` (7 ativos, 2 críticos no residual, exposição de R$ 3,4 mi no projeto 1). Onde mexer: regra em `calculations.py`/`service.py`, filtros em `validation.py` e `presentation.py`, exportação em `export.py`.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Registro de riscos | `app/_views/riscos/registro.html` | `app/paginas/riscos/registro.css` | `app/paginas/riscos/registro.js` |
| Matriz de riscos 5x5 | `app/_views/riscos/matriz.html` | `app/paginas/riscos/matriz.css` | `app/paginas/riscos/matriz.js` |
| Ficha do risco | `app/_views/riscos/ficha.html` | `app/paginas/riscos/ficha.css` | `app/paginas/riscos/ficha.js` |
| Painel de riscos | `app/_views/riscos/painel.html` | `app/paginas/riscos/painel.css` | `app/paginas/riscos/painel.js` |

## Rotas previstas

Prefixo: `/api/riscos/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `riscos` | Consultar, registrar e atualizar a ficha | ISSUE-064, ISSUE-065 |
| `riscos/{codigo}/avaliacoes` e `revisoes` | Avaliar e revisar P/I | ISSUE-064, ISSUE-065 |
| `riscos/{codigo}/plano` | Registrar/aprovar resposta | ISSUE-065 |
| `matriz` e `painel` | Consultar matriz e indicadores | ISSUE-066 |
| `integracoes` | Receber sugestões e atualizações dos módulos donos | ISSUE-067 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Score residual | Resultado de probabilidade e impacto na escala de risco ativa | `calculations.residual_score` |
| Severidade | Faixa da escala vigente atribuída ao score | `calculations.risk_severity` |
| VME | Probabilidade média da faixa multiplicada pelo impacto em custo, em centavos | `calculations.expected_monetary_value` |

## Fluxos

Identificado → Em análise → Em tratamento → Monitorado → Materializado ou Encerrado. Aprovar um plano é segregado da sua elaboração. O encerramento exige lição aprendida; materialização pode criar problema/ação e SM. Reabertura e exclusão lógica são controladas.

## Integrações

Recebe sugestões do diligenciamento (Suprimentos), claims (Financeiro), lições aplicadas (Governança) e dados de exposição usados em contingência (Financeiro). Cria ações na Central. Encerramento pode criar lição em Governança; somente a fachada dona grava em cada módulo.

## Parâmetros

Escala de severidade, probabilidades médias por faixa, cadência de revisão, limites de pauta e de alerta. A escala e os limites são configurados/versionados em Configurações; valores iniciais constam no grupo Riscos da spec e entram nas ISSUE-064 a ISSUE-067 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Fluxo, segregação e integrações | `service.py` |
| Score, severidade e VME | `calculations.py` |
| Validação de avaliação/plano | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/riscos/` |
| Tela, estilo e comportamento | `app/_views/riscos/` e `app/paginas/riscos/` |
| Testes | `api/tests/riscos/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-064 a ISSUE-067 completam este documento e acrescentam testes de fronteira.
