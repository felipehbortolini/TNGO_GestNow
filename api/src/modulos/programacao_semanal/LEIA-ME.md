# Programação Semanal

Módulo `programacao_semanal`. É a aplicação `Timenow - Programação Semanal` adaptada ao escopo de projeto, aos cadastros e aos perfis do GestNow (D10). Não é a tela reduzida do protótipo.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Programação | Matriz de atividades de segunda a domingo, previsto e realizado | ISSUE-051, ISSUE-052 |
| Governança da programação | Pedidos de alteração e histórico por empresa/semana | ISSUE-053 |
| Configuração da programação | Parâmetros e janelas, por projeto | ISSUE-054 |
| Importação e impressão | Conferência da planilha, exportação Excel e relatório imprimível | ISSUE-055 |
| Dashboard | Curva do avanço programado, aderência, ranking, heatmap, turnos e gargalos | ISSUE-056 |

## Rotas previstas

Prefixo: `/api/programacao-semanal/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `programacoes` e `atividades` | Consultar/editar a semana e as atividades | ISSUE-051 |
| `validacoes`, `realizados` e `publicacoes` | Fluxo de cinco passos com fiscal | ISSUE-052 |
| `pedidos-de-alteracao` e `governanca` | Solicitar, aplicar/recusar e auditar alterações | ISSUE-053 |
| `configuracoes` | Parâmetros e janelas de escrita do projeto | ISSUE-054 |
| `importacoes` e `exportacoes` | Planilha e impressão | ISSUE-055 |
| `dashboard` | Indicadores e séries da programação | ISSUE-056 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| PPC da atividade | Realizado dividido pelo previsto de uma atividade; sem previsto, zero | `calculations.activity_ppc` |
| Aderência da programação | Soma do realizado dividida pela soma do previsto no conjunto (semana, empresa ou frente); não é a média do PPC | `calculations.schedule_adherence` |
| Faixa de desempenho | Classifica PPC ou aderência com os limites configurados para o projeto | `calculations.performance_band` |

## Fluxo de estado

Fornecedor cria/edita na janela → Planejador valida e define fiscal → Fornecedor informa realizado por turno dia/noite → Fiscal aprova (o realizado congela) → Planejador publica. Situação da programação e aprovação do realizado são estados distintos. Um pedido aprovado pode reabrir uma programação publicada com trilha.

## Integrações

Projeto, empresas, colaboradores, fiscais e encarregados vêm de Configurações. A identidade e o papel da pessoa vêm da plataforma GestNow; fornecedor só acessa a própria empresa. O módulo não mantém cadastro paralelo de pessoas/empresas. A saída alimenta o dashboard da programação e os relatórios previstos.

## Parâmetros

Cada projeto tem seus parâmetros e janelas: limites de PPC/aderência, limite de desvio que exige justificativa, semanas/dias/horários liberados e liberações extraordinárias. Projeto novo recebe valores padrão. A alteração vale na hora e deixa auditoria (ISSUE-054).

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Fluxo, permissões e janela | `service.py` |
| PPC, aderência e faixas | `calculations.py` |
| Validações da atividade/planilha | `validation.py` |
| Planilha e impressão | `export.py` |
| Persistência | `models.py`; entidades na ISSUE-004 |
| Fragmentos | `api/src/templates/programacao_semanal/` |
| Tela, estilo e comportamento | `app/_views/programacao_semanal/` e `app/paginas/programacao_semanal/` |
| Testes | `api/tests/programacao_semanal/` |

O app de origem e seu glossário ficam somente para consulta em `docs/referencia/programacao-semanal/`. Multi-ambiente, seletor de clientes, área do operador, login próprio, SharePoint/JSON e API JSON de leitura permanecem fora de escopo. Os stubs Python desta issue não portam comportamento; ISSUE-051 a ISSUE-056 completam este documento e os testes.
