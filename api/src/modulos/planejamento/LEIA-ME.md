# Planejamento

Módulo `planejamento`. Controla escopo e avanço físico pela EAP e reúne Curva S, indicadores, relato, 6WLA, produtividade e punch list. A Programação Semanal é um módulo próprio. As funcionalidades chegam nas ISSUE-036 a ISSUE-050.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| EAP | Árvore área/subárea/pacote, dicionário e avanço por critério | ISSUE-036, ISSUE-037, ISSUE-038 |
| Curva S física | Linha de base, real e tendência, com drill por período | ISSUE-039 |
| KPIs de planejamento | Previsto x real, SPI e desvios por período e área | ISSUE-040 |
| Relato do período | Atividades feitas/próximas e pontos de atenção | ISSUE-044 |
| 6WLA | Atividades por semana, restrições e responsáveis | ISSUE-045 |
| Produtividade | Quantidades, horas efetivas, amostragem, paradas e KPIs | ISSUE-046 a ISSUE-048 |
| Punch list | Lista de itens, verificação, bloqueios e painel | ISSUE-049, ISSUE-050 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| EAP | `app/_views/planejamento/eap.html` | `app/paginas/planejamento/eap.css` | `app/paginas/planejamento/eap.js` |
| Curva S | `app/_views/planejamento/curva_s.html` | `app/paginas/planejamento/curva_s.css` | `app/paginas/planejamento/curva_s.js` |
| KPIs | `app/_views/planejamento/kpis.html` | `app/paginas/planejamento/kpis.css` | `app/paginas/planejamento/kpis.js` |
| Relato do período | `app/_views/planejamento/relato.html` | `app/paginas/planejamento/relato.css` | `app/paginas/planejamento/relato.js` |
| 6WLA | `app/_views/planejamento/6wla.html` | `app/paginas/planejamento/6wla.css` | `app/paginas/planejamento/6wla.js` |
| Produtividade | `app/_views/planejamento/produtividade.html` | `app/paginas/planejamento/produtividade.css` | `app/paginas/planejamento/produtividade.js` |
| Punch list | `app/_views/planejamento/punch_list.html` | `app/paginas/planejamento/punch_list.css` | `app/paginas/planejamento/punch_list.js` |

## Rotas previstas

Prefixo: `/api/planejamento/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `eap` | Árvore, dicionário, revisões, pacotes e medições | ISSUE-036 a ISSUE-038 |
| `curva-fisica` e `kpis` | Séries e indicadores físicos | ISSUE-039, ISSUE-040 |
| `relatos`, `6wla` | Relatos de período, lookahead e restrições | ISSUE-044, ISSUE-045 |
| `produtividade` | Plano de quantidades, horas efetivas e desempenho | ISSUE-046 a ISSUE-048 |
| `punch-list` | Itens, transições, consultas e painel | ISSUE-049, ISSUE-050 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Avanço do pacote | Progresso calculado pelas entradas do critério de medição do pacote | `calculations.package_progress` |
| Avanço da EAP | Soma ponderada do real dos pacotes pela linha de base vigente | `calculations.weighted_wbs_progress` |
| SPI físico | Avanço real dividido pelo avanço previsto no corte | `calculations.physical_schedule_index` |

O avanço físico real vem somente das medições da EAP (D6). Uma fórmula que usa data recebe o corte/data de referência como argumento.

## Fluxos

Rev 0 da EAP é a linha de base. Alterações estruturais e de peso entram em revisão ligada a SM aprovada; medição segue o critério do pacote e não permite regressão sem estorno justificado por Gestor. A punch list segue Aberto → Em tratamento → Aguardando verificação → Fechado; verificação reprovada volta a Em tratamento e Cancelado exige justificativa.

## Integrações

Lê a SM aprovada de Governança para revisões da EAP. O avanço da EAP alimenta Curva S, KPIs, Início e relatório. Itens de punch list criam ações na Central e podem bloquear marcos por item A. Referências de custo usam a EAC do Financeiro, sem leitura direta das tabelas alheias.

## Parâmetros

Incluem critérios/modelos de medição e faixas de desvio da EAP, faixas de produtividade e janelas de cálculo, e limites de aging da punch list (7 e 30 dias inicialmente). A edição versionada pertence a Configurações; os detalhes entram nas ISSUE-036 a ISSUE-050 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Fluxo, permissões e integrações | `service.py` |
| Medições, avanço e indicadores | `calculations.py` |
| Validações | `validation.py` |
| Exportação | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/planejamento/` |
| Tela, estilo e comportamento | `app/_views/planejamento/` e `app/paginas/planejamento/` |
| Testes | `api/tests/planejamento/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-036 a ISSUE-050 completam este documento e acrescentam testes das regras.
