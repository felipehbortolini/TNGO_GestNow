# Central de Ações

Módulo `central_acoes`. É o ponto único para acompanhar ações originadas nos demais módulos e atas de reunião. As regras de ação chegam nas ISSUE-019 e ISSUE-020; as atas, nas ISSUE-021 e ISSUE-022.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Ações | Lista, kanban, filtros, KPIs, replanejamento justificado e origem | ISSUE-019 |
| Painel de ações | Indicadores por origem, responsável e projeto; follow-up e PDF | ISSUE-020 |
| Atas | Lista e revisão mais recente de cada ata | ISSUE-021 |
| Ficha da ata | Dados da reunião, participantes, anotações, ações e histórico | ISSUE-021, ISSUE-022 |

O status de uma ação é calculado pelo servidor. A origem registrada aponta de volta para a ficha que criou a ação.

## Rotas previstas

Prefixo: `/api/central-acoes/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `acoes` | Listar, filtrar, replanejar e consultar ações | ISSUE-019 |
| `painel` | Consultar indicadores e gerar follow-up/PDF | ISSUE-020 |
| `atas` | Listar, criar e consultar atas | ISSUE-021 |
| `atas/{codigo}` | Revisar ata e manter presença, anotações e ações | ISSUE-022 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Status da ação | Concluída se há data de conclusão; caso contrário, Atrasada se a data replanejada ou prevista passou da data de referência; nos demais casos, Em andamento | `calculations.action_status` |
| Total de ações atrasadas | Contagem de ações cujo status calculado é Atrasada no escopo consultado | `calculations.overdue_action_count` |

A data de referência é recebida pela função; o status não é persistido como resultado. As integrações mantêm sincronizados o item e seu registro de origem.

## Fluxos

Uma ação aberta pode ser replanejada com justificativa. Concluir exige data de conclusão. Atas são numeradas por projeto; uma revisão nova mantém a linhagem e o histórico. A retirada de participante é recusada enquanto houver ação aberta sob sua responsabilidade.

## Integrações

Recebe ações de Planejamento, Financeiro, Suprimentos, Riscos, Qualidade, HSE e Governança. Oferece a fachada única de criação de ação para esses módulos; cada módulo continua dono do seu registro de origem. Links de retorno são resolvidos pela plataforma.

## Parâmetros

Não há grupo de parâmetros próprio definido nesta issue. Numeração, data de referência e permissões vêm das fachadas de plataforma; filtros e ordenação não são parâmetros versionados.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Fluxo, permissões e integrações | `service.py` |
| Status e indicadores | `calculations.py` |
| Validação de formulários | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades são desenhadas nas ISSUE-003 e ISSUE-004 |
| Fragmentos | `api/src/templates/central_acoes/` |
| Tela, estilo e comportamento | `app/_views/central_acoes/` e `app/paginas/central_acoes/` |
| Testes | `api/tests/central_acoes/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-019 a ISSUE-022 completam este documento e acrescentam testes das regras.
