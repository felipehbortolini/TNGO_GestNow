# HSE

Módulo `hse` (saúde, segurança e meio ambiente). Registra HHT, inspeções, observações e DDS
(ISSUE-072); ocorrências, análises de risco e painel entram nas ISSUE-073 a ISSUE-075.

## Telas

| Tela | Conteúdo | Issue | Situação |
|---|---|---|---|
| Horas trabalhadas (HHT) | HHT e efetivo médio por mês e empresa, importação de planilha e histograma de mão de obra | ISSUE-072 | pronta |
| Inspeções e observações | Checklist de inspeção, observações comportamentais, DDS e consolidado mensal | ISSUE-072 | pronta |
| Ocorrências | Registro, investigação, ações, encerramento e anexos | ISSUE-073 | prevista |
| Análises de risco (APR/HAZOP) | Estudos e recomendações | ISSUE-074 | prevista |
| Painel HSE | Taxas reativas/proativas, pirâmides, dias sem afastamento e evolução | ISSUE-075 | prevista |

Nome e dados médicos ficam restritos segundo Q35; o formulário pode coletar esses dados, mas só
Gestor e Admin podem lê-los.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a
view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view
(`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra
`TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A
verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`,
seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Horas trabalhadas (HHT) | `app/_views/hse/hht.html` | `app/paginas/hse/hht.css` | `app/paginas/hse/hht.js` |
| Inspeções e observações | `app/_views/hse/inspecoes.html` | `app/paginas/hse/inspecoes.css` | `app/paginas/hse/inspecoes.js` |
| Ocorrências | `app/_views/hse/ocorrencias.html` | `app/paginas/hse/ocorrencias.css` | `app/paginas/hse/ocorrencias.js` |
| Análises de risco (APR/HAZOP) | `app/_views/hse/analises_risco.html` | `app/paginas/hse/analises_risco.css` | `app/paginas/hse/analises_risco.js` |
| Painel HSE | `app/_views/hse/painel.html` | `app/paginas/hse/painel.css` | `app/paginas/hse/painel.js` |

O `hht.js` e o `inspecoes.js` só abrem os modais (formulário, importação) e cuidam dos cinco
estados; o conteúdo vem do servidor em `#hse-modal-corpo` e a tela se recarrega ao fechar.

## Rotas (ISSUE-072)

Prefixo: `/api/hse/`.

| Rota | Uso |
|---|---|
| `GET hht` com `hht/excel` e `hht/imprimivel` | A tela do HHT e as duas exportações |
| `GET/POST hht/novo` e `hht/{id}/editar` | Formulário mensal (mês e empresa bloqueados na edição) |
| `GET histograma` | O histograma de mão de obra, para a tela e para o desembolso (ISSUE-043) |
| `GET inspecoes` com `inspecoes/excel` e `inspecoes/imprimivel` | A tela e as exportações |
| `GET/POST inspecoes/{tipo}/novo` e `inspecoes/{tipo}/{id}/editar` | `tipo` ∈ inspecao, observacao, dds, mensal |
| `GET /api/importacao/hht` e `/api/importacao/hse-mensal` | Importação por planilha (mecanismo genérico) |

O HHT é um registro por mês e empresa: gravar de novo atualiza o mesmo registro. O fechamento
mensal é um por mês. A importação confere linha a linha e só grava na confirmação; no Portfólio a
importação é recusada (o registro pertence a um projeto).

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Horas por pessoa | HHT dividido pelo efetivo médio, meio para cima | `calculations.hours_per_person` |
| Fator do histograma | Avanço planejado sobre o realizado da Curva S física, entre 0,85 e 1,20 | `calculations.histogram_factor` |
| Histograma de mão de obra | HHT previsto por projeto e mês (registrado ajustado pelo fator, às centenas) e o realizado | `calculations.labour_histogram` |
| HHT previsto acumulado | Soma do previsto até o mês, ou só no mês | `calculations.planned_labour` |
| Aderência aos DDS | DDS realizados divididos pelos programados | `calculations.rate_percent` |
| Aderência da inspeção | Itens conformes divididos pelos inspecionados | `calculations.rate_percent` |
| Meta proativa | Ocorrências (ou desvios) esperados por 10 mil HHT, aplicado ao HHT dos meses fechados | `calculations.proactive_target` |

## Fluxos

HHT e fechamento mensal são atualizados por upsert (mês + empresa; mês). A inspeção tem checklist
com itens conformes e não conformes; a observação comportamental tem tipo e situação; o DDS tem
tema, data e participantes. O nível 5 da pirâmide (desvios) sai do consolidado mensal. Importação:
conferência (leitura, sem gravar) e confirmação (grava as linhas sem erro, tudo ou nada).

## Integrações

Empresas e pessoas vêm de Configurações. O histograma de mão de obra é calculado aqui e mostrado
na tela de HHT e no Cronograma de desembolso (ISSUE-043); a Curva S física vem do módulo dono
(`register_curve_reader`, ISSUE-039) e, sem leitor, o fator fica em 1. Ocultar nome em dado de
saúde segue Q35 (Gestor e Admin).

## Parâmetros

O grupo `seguranca` dos parâmetros traz as metas de observações e desvios por 10 mil HHT
(`metas.observacoesPor10MilHht` e `metas.desviosPor10MilHht`), com os padrões do módulo quando
ausentes; base das taxas e prazos legais entram com a ISSUE-073.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| HHT, fechamento, inspeções, observações e DDS | `service.py` |
| Fator, histograma e taxas | `calculations.py` |
| Validações e campos restritos | `validation.py` |
| Formulários e campos por tipo | `forms.py` |
| Importação por planilha | `importers.py` |
| Exportação (Excel e imprimível) | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` |
| Fragmentos | `api/src/templates/hse/` |
| Tela, estilo e comportamento | `app/_views/hse/` e `app/paginas/hse/` |
| Testes | `api/tests/hse/` e `api/tests/oraculo/test_oraculo_hse.py` |

As ISSUE-073 a ISSUE-075 completam ocorrências, análises de risco e o painel.
