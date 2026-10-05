# Gestão da Qualidade

Módulo `qualidade`. Registra não conformidades, inspeções/ITP e auditorias, com controle de tratamento e eficácia. As telas são propostas pela spec e pelo inventário; entram nas ISSUE-068 a ISSUE-071.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Painel da qualidade | RNC, inspeções, auditorias, Pareto, custo e pauta | ISSUE-071 |
| Não conformidades | Registro/ficha, contenção, causa, disposição, ações e eficácia | ISSUE-068 |
| Inspeções e ITP | Planos com pontos H/W/R e registros por ponto | ISSUE-069 |
| Auditorias | Programa, resultado, constatações e reprogramação | ISSUE-070 |

## Rotas previstas

Prefixo: `/api/qualidade/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `rncs` | Abrir, tratar, verificar e consultar RNC | ISSUE-068 |
| `itps` e `inspecoes` | Planos, revisões e registros de inspeção | ISSUE-069 |
| `auditorias` | Planejar, reprogramar e registrar resultado | ISSUE-070 |
| `painel` | Consultar indicadores de qualidade | ISSUE-071 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Aprovação em inspeções | Inspeções aprovadas ou com ressalva divididas pelo total de inspeções | `calculations.inspection_approval_rate` |
| Conformidade em auditorias | Itens conformes divididos pelos itens verificados | `calculations.audit_conformity_rate` |
| Aderência ao programa de auditorias | Auditorias realizadas divididas pelas previstas até a data de referência | `calculations.audit_program_adherence` |
| Eficácia na primeira verificação | RNC encerradas sem reincidência divididas pelas encerradas | `calculations.first_check_effectiveness` |

## Fluxos

RNC: Aberta → Em análise de causa → Ação corretiva → Verificação de eficácia → Encerrada. Reprovação na eficácia volta à ação corretiva; cancelamento é limitado e justificado. Inspeção reprovada abre RNC. Uma revisão do ITP requer aprovação do cliente; auditoria reprogramada exige justificativa.

## Integrações

FAT de Suprimentos pode registrar inspeção. RNC cria ações na Central; a eficácia pode criar lição em Governança. A Home e o relatório leem KPIs e alertas de qualidade. As gravações cruzadas usam as fachadas donas e a transação da requisição.

## Parâmetros

Prazos de tratamento de RNC por severidade (Crítica 15, Maior 30, Menor 45 dias inicialmente), prazo até a verificação (30 dias), metas de inspeção/conformidade e antecedência para notificação ao cliente em ponto W (48 horas inicialmente). Valores versionados em Configurações.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Transições, permissão e integrações | `service.py` |
| Indicadores de qualidade | `calculations.py` |
| Validações de RNC, ITP e auditoria | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades na ISSUE-004 |
| Fragmentos | `api/src/templates/qualidade/` |
| Tela, estilo e comportamento | `app/_views/qualidade/` e `app/paginas/qualidade/` |
| Testes | `api/tests/qualidade/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-068 a ISSUE-071 completam este documento e acrescentam testes de fronteira.
