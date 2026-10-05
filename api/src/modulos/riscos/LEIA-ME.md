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
| Persistência | `models.py`; entidades na ISSUE-004 |
| Fragmentos | `api/src/templates/riscos/` |
| Tela, estilo e comportamento | `app/_views/riscos/` e `app/paginas/riscos/` |
| Testes | `api/tests/riscos/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-064 a ISSUE-067 completam este documento e acrescentam testes de fronteira.
