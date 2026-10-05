# HSE

Módulo `hse` (saúde, segurança e meio ambiente). Registra HHT, ocorrências, inspeções/observações, DDS e estudos APR/HAZOP. As funcionalidades entram nas ISSUE-072 a ISSUE-075.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Painel HSE | Taxas reativas/proativas, pirâmides, dias sem afastamento e evolução | ISSUE-075 |
| Ocorrências | Registro, investigação, ações, encerramento e anexos | ISSUE-073 |
| Inspeções e observações | Checklists, observações comportamentais e DDS | ISSUE-072 |
| Análises de risco | APR/JSA, HAZOP e recomendações | ISSUE-074 |
| HHT | Horas-homem trabalhadas por mês e empresa | ISSUE-072 |

Nome e dados médicos ficam restritos segundo Q35; o formulário pode coletar esses dados, mas só Gestor e Admin podem lê-los.

## Rotas previstas

Prefixo: `/api/hse/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `hht` | Registrar e consultar horas trabalhadas | ISSUE-072 |
| `inspecoes` e `observacoes` | Inspeções de segurança, observações e DDS | ISSUE-072 |
| `ocorrencias` | Registrar, investigar e encerrar ocorrências | ISSUE-073 |
| `analises-de-risco` | Estudos e recomendações APR/HAZOP | ISSUE-074 |
| `painel` | Consultar taxas e indicadores | ISSUE-075 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| TF | (fatalidades + acidentes com afastamento) × base da taxa ÷ HHT | `calculations.frequency_rate` |
| TRIF | (fatalidades + afastamento + trabalho restrito + tratamento médico) × base ÷ HHT | `calculations.recordable_injury_rate` |
| TG | (dias perdidos + dias debitados) × base ÷ HHT | `calculations.severity_rate` |
| Dias sem acidente com afastamento | Dias desde a última LTI ou, sem LTI, desde o início do projeto | `calculations.days_without_lost_time_injury` |

A base da taxa é parâmetro (1.000.000 HHT como padrão Timenow; 200.000 é a opção OSHA). As fórmulas recebem a data de referência e o período; eventos pessoais não são lidos por perfis sem permissão.

## Fluxos

Ocorrência: Registrada → Em investigação → Ações definidas → Em tratamento → Encerrada. Investigação registra causa e ações; o fechamento confere prazos e eficácia. HHT e consolidados mensais são atualizados por mês e empresa. Recomendações de APR/HAZOP podem ser concluídas ou encaminhadas como ação.

## Integrações

Cria ações na Central. Envia indicadores ao Início, análise de período e relatório gerencial. Colaboradores/empresas vêm de Configurações; a fonte de HHT previsto é o cálculo comum com Planejamento, conforme ISSUE-047/075. Dados pessoais sensíveis e anexos seguem a mesma permissão do registro.

## Parâmetros

Prazo de comunicação (24h), investigação preliminar (48h), relatório final (30 dias), base das taxas e referência da pirâmide Bird/Heinrich; metas proativas também são configuradas. Valores iniciais constam na spec e são versionados em Configurações.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Ciclo, permissões LGPD e integrações | `service.py` |
| Taxas e séries | `calculations.py` |
| Validações e campos restritos | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades na ISSUE-004 |
| Fragmentos | `api/src/templates/hse/` |
| Tela, estilo e comportamento | `app/_views/hse/` e `app/paginas/hse/` |
| Testes | `api/tests/hse/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-072 a ISSUE-075 completam este documento e acrescentam testes de fronteira e autorização.
