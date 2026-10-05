# Relatório Gerencial

Módulo `relatorio`. Consolida dados dos módulos em relatórios semanais ou mensais, por projeto ou Portfólio. O modal de emissão é iniciado no Início; as folhas, exportação e impressão pertencem a este módulo.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Emissão do relatório | Tipo, período, escopo, seções e estado dos relatos/análises | ISSUE-083 |
| Relatório gerencial | Folhas de Planejamento e dados do período | ISSUE-083 |
| Folhas Financeiro e Suprimentos | Indicadores, análises e projeção financeira | ISSUE-084 |
| Folhas Riscos, Qualidade, HSE e Carteira | Indicadores e consolidados por seção | ISSUE-085 |
| Excel e impressão/PDF | Exportação do relatório e alteração do período | ISSUE-086 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

O relatório gerencial é tela de detalhe do Início: abre a partir do botão e do modal de emissão que o Início guarda.

| Tela | View | CSS | JS |
|---|---|---|---|
| Relatório gerencial | `app/_views/relatorio/gerencial.html` | `app/paginas/relatorio/gerencial.css` | `app/paginas/relatorio/gerencial.js` |

## Rotas previstas

Prefixo: `/api/relatorio/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `gerencial` | Montar relatório por tipo, período, escopo e seções | ISSUE-083 a ISSUE-085 |
| `gerencial/excel` | Baixar planilha do relatório | ISSUE-086 |
| `gerencial/impressao` | Obter folha imprimível para PDF do navegador | ISSUE-086 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14. Downloads são respostas de arquivo, não fragmentos Alpine.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Corte do período | Fim do período limitado à data de referência | `calculations.report_period_cutoff` |
| Período parcial | Período selecionado ainda não terminou na data de referência | `calculations.is_partial_period` |
| Tendência financeira por desempenho | EAC calculada por CPI no mês do relatório, sem dados posteriores ao corte | Pertence a `financeiro.calculations.financial_eac_trend` |

Relatório usa dados e cálculos das fachadas donas, não mantém fórmulas duplicadas. Em inglês, o indicador é chamado Estimate at Completion na fonte; no produto o termo é **Projeção no término**, nunca EAC.

## Fluxos

Selecionar semanal/mensal, projeto/Portfólio, período e seções → consultar se relatos/análises estão registrados → montar folhas no corte → exportar Excel ou abrir a versão imprimível e acionar a impressão do navegador. Período em andamento é marcado como parcial. Análises do período são gravadas nas issues 081/082, não no gerador de relatório.

## Integrações

Lê resumos das fachadas de Planejamento, Financeiro, Suprimentos, Riscos, Qualidade, HSE e Início/Portfólio, além de relatos e análises. O módulo não lê as tabelas alheias diretamente. Exportação comum e impressão seguem a porta genérica da ISSUE-017.

## Parâmetros

Tipo e granularidade do período: semana ISO (segunda a domingo) ou mês civil; corte limitado à data de referência. A lista de seções depende do escopo selecionado. Metas exibidas pertencem aos módulos donos.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Composição, corte e permissões | `service.py` |
| Parcialidade e corte do período | `calculations.py` |
| Validação das opções | `validation.py` |
| Excel/impressão | `export.py` |
| Persistência de entidades próprias | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/relatorio/` |
| Tela, estilo e comportamento | `app/_views/relatorio/` e `app/paginas/relatorio/` |
| Testes | `api/tests/relatorio/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-083 a ISSUE-086 completam este documento e acrescentam testes de corte, parcialidade e exportação.
