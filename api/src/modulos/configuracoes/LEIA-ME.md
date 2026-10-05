# Configurações

Módulo `configuracoes`. Mantém colaboradores, cadastros de apoio e parâmetros gerais versionados. A configuração específica de janelas da Programação Semanal fica no submódulo `programacao_semanal`, uma por projeto (D10).

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Parâmetros | Grupos, versão vigente, edição justificada e histórico antes/depois | ISSUE-076 |
| Colaboradores | Perfil geral, papéis da Programação Semanal por projeto, vínculo e empresa | ISSUE-077 |
| Cadastros de apoio | Projetos, empresas, pessoas, sistemas, unidades e locais | ISSUE-078 |

## Rotas previstas

Prefixo: `/api/configuracoes/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `parametros` e `parametros/historico` | Consultar, versionar e auditar parâmetros | ISSUE-076 |
| `colaboradores` | Administrar acesso, perfil e papéis por projeto | ISSUE-077 |
| `cadastros` | Manter entidades de apoio usadas nos formulários | ISSUE-078 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

Este módulo não calcula indicadores de negócio. A validação da edição de parâmetros é uma regra de entrada, não um KPI:

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Grupo de parâmetros válido | Verifica tipos, faixas, relações e somas exigidas antes de criar versão | `validation.validate_parameter_group` |
| Peso normalizado | Exige que os critérios de uma distribuição versionada fechem em 100% | `validation.validate_weight_total` |

As fórmulas dos domínios permanecem nas `calculations.py` dos módulos donos; Configurações não as duplica.

## Fluxos

Alterar parâmetro exige justificativa e cria nova versão com vigência, autor, antes e depois. Colaboradores são cadastrados com um perfil geral e, quando aplicável, papéis por projeto na Programação Semanal. Cadastros de apoio não são duplicados dentro dos módulos consumidores.

## Integrações

É fonte única de colaboradores, projetos, empresas, pessoas, sistemas, unidades e locais. Fachadas dos módulos consultam os parâmetros do grupo vigente. A janela semanal e liberações extraordinárias são mantidas dentro de Programação Semanal; aqui ficam parâmetros gerais versionados.

## Parâmetros

Este módulo é dono do versionamento e dos grupos gerais: financeiro, suprimentos, riscos, qualidade, HSE, planejamento, governança, avaliação de contratadas, portfólio e anexos. Os valores/limites iniciais e seus consumidores estão na spec, decisão D5a e seção 7.4 do README do protótipo.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Versionamento e cadastros | `service.py` |
| Derivação própria | Não há KPI próprio; cálculos permanecem nos módulos consumidores |
| Regras de entrada | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades na ISSUE-003 |
| Fragmentos | `api/src/templates/configuracoes/` |
| Tela, estilo e comportamento | `app/_views/configuracoes/` e `app/paginas/configuracoes/` |
| Testes | `api/tests/configuracoes/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-076 a ISSUE-078 completam este documento e acrescentam testes de validação, acesso e versionamento.
