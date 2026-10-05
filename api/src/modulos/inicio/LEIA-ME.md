# Início

Módulo `inicio`. Reúne o resumo do projeto e da carteira de projetos. A view existente permanece vazia; os indicadores e pontos de atenção chegam nas ISSUE-079 e ISSUE-080.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Início do projeto | Um indicador-chave por módulo e pontos de atenção calculados | ISSUE-079 |
| Início do Portfólio | Carteira de projetos, indicadores consolidados e edição da ponderação com prévia | ISSUE-080 |

O protótipo chama a tela inicial de Home. No GestNow ela é o módulo Início; relatório gerencial é o módulo separado `relatorio`.

## Rotas previstas

Prefixo: `/api/inicio/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `resumo` | Consultar indicadores e pontos de atenção do projeto | ISSUE-079 |
| `carteira` | Consultar projetos, pesos e consolidados | ISSUE-080 |
| `ponderacao` | Prévia e gravação versionada dos critérios da carteira | ISSUE-080 |

São grupos de rota planejados; cada issue de comportamento fixa os métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Peso do projeto na carteira | Normalização dos critérios configurados, distribuída em 100% pelo método do maior resto | `calculations.portfolio_project_weights` |
| Avanço físico do Portfólio | Média dos avanços calculados pela EAP, ponderada pelo peso vigente de cada projeto | `calculations.portfolio_physical_progress` |
| Valor financeiro da carteira | Soma dos valores financeiros dos projetos, sem ponderação | `calculations.portfolio_financial_totals` |

As implementações e os casos de fronteira entram nas issues indicadas; pesos e avanços não são digitados como resultados.

## Fluxos

O Início é uma leitura consolidada. A ponderação é editada com prévia e justificativa e gera uma nova versão de parâmetros; a gravação/versionamento pertence à fachada de Configurações. Trocar o escopo entre projeto e Portfólio não altera registros.

## Integrações

Lê resumos das fachadas de Central de Ações, Planejamento, Financeiro, Suprimentos, Riscos, Qualidade, HSE e Governança. Lê critérios versionados de Configurações. Os botões levam à tela dona do dado; Início não lê tabelas de outros módulos diretamente.

## Parâmetros

Critérios de ponderação da carteira: valor financeiro (60%), criticidade estratégica (25%) e complexidade/exposição a risco (15%), inicialmente. São versionados; Gestor ou Admin pode alterá-los pela ação do Início.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Agregação, permissões e fluxo | `service.py` |
| Pesos e consolidados | `calculations.py` |
| Entrada e justificativa | `validation.py` |
| Exportação | `export.py` |
| Persistência, se necessária | `models.py`; modelo relacional em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/inicio/` |
| Tela, estilo e comportamento | `app/_views/inicio/` e `app/paginas/inicio/` |
| Testes | `api/tests/inicio/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. A issue de cada funcionalidade completa este documento e acrescenta os testes da regra.
