# HSE

Módulo `hse` (saúde, segurança e meio ambiente). Registra HHT, inspeções, observações, DDS,
ocorrências com investigação, prazos legais e dado restrito (ISSUE-072 e ISSUE-073), as análises
de risco APR/JSA e HAZOP com recomendações que viram ações (ISSUE-074) e o painel com as taxas,
as pirâmides, os proativos e a nota HSE sugerida (ISSUE-075).

## Telas

| Tela | Conteúdo | Issue | Situação |
|---|---|---|---|
| Horas trabalhadas (HHT) | HHT e efetivo médio por mês e empresa, importação de planilha e histograma de mão de obra | ISSUE-072 | pronta |
| Inspeções e observações | Checklist de inspeção, observações comportamentais, DDS e consolidado mensal | ISSUE-072 | pronta |
| Ocorrências | Registro, investigação, ações corretivas na Central, tratamento, encerramento, anexos e dado restrito | ISSUE-073 | pronta |
| Análises de risco (APR/HAZOP) | Estudos APR/JSA e HAZOP, participantes e recomendações que viram ações na Central | ISSUE-074 | pronta |
| Painel HSE | Taxas reativas/proativas, pirâmides, dias sem afastamento e evolução | ISSUE-075 | pronta |

Nome e dados médicos das ocorrências ficam restritos segundo Q35: o Membro preenche no registro,
mas só Gestor e Admin leem o bloco restrito e os anexos com esses dados; o download do anexo da
ocorrência exige `Permission.VIEW_RESTRICTED`.

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
estados; o conteúdo vem do servidor em `#hse-modal-corpo` e a tela se recarrega ao fechar. O
`ocorrencias.js` faz o mesmo no alvo `ocorrencias-modal-corpo`: a ficha e os formulários do fluxo
(nova, investigar, ação, tratamento e encerrar) chegam por GET, e depois de gravar o fragmento da
lista traz o marcador oculto que reabre a ficha. O `analises_risco.js` repete o padrão no alvo
`analises-risco-modal-corpo` (ficha, novo estudo e fechamento de recomendação) e cuida das linhas
repetíveis de recomendação do formulário (acrescentar e remover, renumerando os campos
`rec_descricao_N`, `rec_responsavel_N` e `rec_prazo_N`).

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

## Rotas (ISSUE-073)

Prefixo: `/api/hse/ocorrencias`. O código nasce da série do projeto (`OCR-<padrão da ata>-NNNN`,
quatro dígitos, pelo núcleo de numeração, `numbering` kind `ocorrencia`).

| Rota | Uso |
|---|---|
| `GET ocorrencias` com `ocorrencias/excel` e `ocorrencias/imprimivel` | A tela (filtros e página na query) e as duas exportações |
| `GET ocorrencias/{codigo}/ficha` | A ficha no modal (investigação, ações, histórico e lição) |
| `GET/POST ocorrencias/nova` | Nova ocorrência, com o dado restrito na mesma transação (Q35) |
| `GET/POST ocorrencias/{codigo}/investigar` | Investigação preliminar (método, causa raiz e data) |
| `GET/POST ocorrencias/{codigo}/acoes` | Ação corretiva na Central (origem HSE) |
| `GET/POST ocorrencias/{codigo}/tratamento` | Início do tratamento (confirmação) |
| `GET/POST ocorrencias/{codigo}/encerrar` | Encerramento com a eficácia verificada (Gestor) |
| `GET ocorrencias/{codigo}/restrito` | O bloco restrito (LGPD): só Gestor e Admin; 403 aos demais |

No Portfólio a lista traz a coluna Projeto (também nas exportações) e o botão de inclusão pede o
projeto antes do formulário (`data-tn-incluir`, `ds/shell.js`).

## Rotas (ISSUE-074)

Prefixo: `/api/hse/analises-risco`. O código nasce da série do projeto e do tipo (APR/JSA ou
HAZOP): `APR-<padrão da ata>-NNNN` e `HAZOP-<padrão da ata>-NNNN`, quatro dígitos, pelo núcleo de
numeração (kinds `apr` e `hazop`).

| Rota | Uso |
|---|---|
| `GET analises-risco` com `analises-risco/excel` e `analises-risco/imprimivel` | A tela (busca, tipo, `abertas` e `pagina` na query) e as duas exportações |
| `GET analises-risco/{codigo}/ficha` | A ficha no modal (dados, participantes, recomendações e o status da ação de cada uma) |
| `GET/POST analises-risco/nova` | Novo estudo com os participantes e as recomendações repetíveis |
| `GET/POST analises-risco/{codigo}/recomendacoes/{ordem}/fechar` | Fechamento da recomendação (data de conclusão e evidência; conclui a ação vinculada) |
| `POST analises-risco/{codigo}/recomendacoes/{ordem}/acao` | Cria a ação da recomendação na Central (origem `HSE`); a segunda recebe 422 com a mensagem do protótipo |

No Portfólio a lista traz a coluna Projeto (também nas exportações) e o botão de inclusão pede o
projeto antes do formulário (`data-tn-incluir`, `ds/shell.js`).

## Rotas (ISSUE-075)

Prefixo: `/api/hse/painel`. A tela é um fragmento (`painel-conteudo`); a barra de filtros (ano,
mês e a referência da pirâmide) é um formulário GET com `x-target` no próprio fragmento, e a
referência é a do parâmetro (`referenciaPiramide`) sobreposta pela query. No Portfólio os
indicadores são do escopo inteiro e as listas por área e por empresa são agregadas, sem a coluna
Projeto (como o protótipo); a tela é só de leitura, sem botão de inclusão.

| Rota | Uso |
|---|---|
| `GET painel` com `ano`, `mes` e `referencia` na query | A tela: os três blocos de indicadores, os dois gráficos e as listas |
| `GET painel/excel` e `painel/imprimivel` | As duas exportações, com a query da tela |

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
| Nível da pirâmide | 1 a 4 pelo tipo da ocorrência (Lesão grave, Lesão leve, Dano material, Quase acidente); o Ambiental fica fora | `calculations.pyramid_level` |
| Faixa do potencial | P x I (1 a 5 cada): Crítico de 15, Alto de 10, Moderado de 5, Baixo até 4 | `calculations.potential_band` |
| HiPo | Consequência potencial (o impacto potencial) além da gravidade real; o registro guarda a marcação | `calculations.is_high_potential` |
| Comunicação fora do prazo | Horas até a comunicação acima do prazo **gravado** na ocorrência | `calculations.communication_overdue` |
| Investigação fora do prazo | Data da investigação além do prazo preliminar gravado, contado do evento em dias (as horas arredondadas para cima, como o protótipo) | `calculations.investigation_overdue` |
| Investigação vencida | Ainda Registrada e o prazo preliminar já passou na data de hoje | `calculations.investigation_pending_overdue` |
| Relatório final | Exigido de LTI (nível 1) e de HiPo; fora do prazo quando o encerramento passou do evento + dias, ou vencido quando ainda aberto | `calculations.report_required`, `calculations.report_overdue` |
| Recomendação atrasada | Recomendação aberta com o prazo anterior à data de referência | `calculations.recommendation_overdue` |
| Recomendações fechadas ÷ emitidas | As recomendações fechadas divididas pelas emitidas (abertas + fechadas), em percentual de uma casa; sem emitidas não há indicador | `calculations.closed_recommendations_pct` |
| Taxa de frequência (TF) | (fatalidades + acidentes com afastamento) x base ÷ HHT; sem HHT não há taxa | `calculations.rate_hse` |
| Lesões registráveis (TRIF) | (fatalidades + afastamentos + trabalho restrito + tratamento médico) x base ÷ HHT | `calculations.rate_hse` |
| Taxa de gravidade (TG) | (dias perdidos + dias debitados) x base ÷ HHT, com uma casa | `calculations.rate_hse` |
| Base das taxas | 1.000.000 de HHT (NBR 14280) ou 200.000 (OSHA), do parâmetro `hse.baseTaxa` | `calculations.rate_base_name` |
| Dias sem afastamento | Dias da última LTI (ou do início do projeto/carteira, sem LTI) até a data de referência; nunca negativo | `calculations.days_without_leave` |
| Pirâmide de segurança | Contagem por nível (1 a 4 das ocorrências; o 5º, desvios, vem do consolidado mensal), do vértice à base; a referência Bird/Heinrich vem do parâmetro `hse.referenciaPiramide` | `calculations.summarize_window`, `calculations.pyramid_reference` |
| Relato de quase acidentes | Quase acidentes (nível 4) ÷ lesões registráveis, com uma casa; a referência é o quase ÷ lesões da proporção (Bird 600/11, Heinrich 300/30) | `calculations.almost_miss_report` |
| Ações HSE no prazo | Ações do escopo da origem `HSE` ou do grupo `HSE` (as da Central, nunca lidas da tabela `acao`), vencidas até a data de referência e concluídas até o próprio prazo; a meta do card é 90% | `calculations.actions_on_time`, `painel_service.ACTIONS_ON_TIME_TARGET` |
| Nota HSE sugerida da contratada | Sem HHT da empresa na janela não há sugestão; 5 se a TRIF da empresa é zero, 4 até a do projeto, 3 até o dobro, 2 até o quádruplo, 1 acima (a comparação usa as TRIF arredondadas como a tela as lê); uma LTI na janela limita a nota a 2 | `calculations.suggested_hse_note`, `painel_service.company_note_suggestion` |

## Fluxos

HHT e fechamento mensal são atualizados por upsert (mês + empresa; mês). A inspeção tem checklist
com itens conformes e não conformes; a observação comportamental tem tipo e situação; o DDS tem
tema, data e participantes. O nível 5 da pirâmide (desvios) sai do consolidado mensal. Importação:
conferência (leitura, sem gravar) e confirmação (grava as linhas sem erro, tudo ou nada).

A ocorrência percorre **Registrada → Em investigação → Ações definidas → Em tratamento →
Encerrada**: a nova ocorrência grava o prazo vigente do grupo `hse` (`prazos`) **na própria linha**
(D5b; mudar o parâmetro depois muda o próximo registro, nunca o gravado); investigar grava o fato
`ocorrencia_investigacao` e move; definir ações cria as ações corretivas na Central (origem `HSE`,
`origem_ref` o código) e move; iniciar o tratamento confirma; encerrar exige Gestor, as ações
concluídas e a eficácia verificada, e um **HiPo encerrado exige a lição**, que nasce em Rascunho na
Governança (origem `HSE`, D9) na mesma transação. O tipo Ambiental não tem gravidade real,
potencial nem HiPo: tem subtipo e severidade próprios.

O estudo de risco é registrado de uma vez (tipo, área, título, data, participantes e
recomendações, todas Aberta); cada recomendação pode virar **uma** ação na Central (origem `HSE`,
`origem_ref` o código do estudo, `item` a ordem da recomendação, grupo `<TIPO> · Recomendação`).
Recomendação e ação ficam sincronizadas nas duas direções (D9, padrão da ISSUE-049): concluir ou
replanejar a ação na Central fecha a recomendação (na data da conclusão) ou move o prazo; fechar a
recomendação na tela do estudo conclui a ação vinculada, na mesma transação. Uma ação de
ocorrência (`OCR-`), que divide a origem `HSE`, não reage nos estudos.

O **painel** (ISSUE-075) é calculado a cada leitura, sem nada gravado (D5b): o mês padrão é o
último com HHT e o acumulado vai do primeiro mês com HHT até ele; o bloco "No mês selecionado"
mostra a TF, a TRIF, a TG e o HiPo do mês, o "Acumulado" os mesmos mais os dias sem afastamento e
as ações HSE no prazo, e os proativos (DDS, conformidade, observações por 10 mil HHT, relato de
quase acidentes, recomendações fechadas e incidentes ambientais) saem do acumulado. A pirâmide
dupla (mês e acumulado) e a evolução mensal de TF e TRIF usam os visuais `piramide-seguranca` e
`linhas-multiplas` da biblioteca de gráficos (D11). Trocar a base ou a referência no parâmetro
recalcula na hora; trocar a referência na tela recarrega o fragmento pela query (divergência
registrada em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`).

## Integrações

Empresas e pessoas vêm de Configurações. O histograma de mão de obra é calculado aqui e mostrado
na tela de HHT e no Cronograma de desembolso (ISSUE-043); a Curva S física vem do módulo dono
(`register_curve_reader`, ISSUE-039) e, sem leitor, o fator fica em 1. Ocultar nome em dado de
saúde segue Q35 (Gestor e Admin).

As ocorrências se ligam por fachada (D9): as ações corretivas nascem na Central
(`central_acoes.service.create_action`) na mesma transação e o link de volta é o tipo de origem
`HSE` (`origin_links`, resolvido para `hse/ocorrencias` com `busca=<código>`); a lição do HiPo
nasce pela Governança (`lessons_service.create_draft_lesson`) e o vínculo de volta é lido por
`lessons_service.code_of_origin`; os anexos usam a porta genérica com o tipo de origem
`ocorrencia`, **restrito** (Q35): o Membro envia e só Gestor e Admin listam e baixam.

As análises de risco compartilham a origem `HSE` (D9): o construtor do link de volta roteia pelo
prefixo do código — `APR-`/`HAZOP-` para `hse/analises_risco`, `OCR-` para `hse/ocorrencias`,
sempre com `busca=`; a reação da origem (`central_acoes.origins.register_reaction("HSE", ...)`,
registrada em `service.py`) espelha a conclusão e o replanejamento nos dois sentidos. A ficha lê
as ações de cada recomendação por `central_acoes.service.actions_of_origin` (nunca lê `acao`). A
fatia não registrou tipo de origem de anexo para o estudo (não há tela de anexos nas análises).

O painel lê as ações de HSE pela fachada da Central
(`central_acoes.service.actions_of_origin_or_group`, origem `HSE` ou grupo `HSE`, no escopo) —
nunca a tabela `acao` (D9). A **nota HSE sugerida** de uma empresa é calculada pelo painel
(`painel_service.company_note_suggestion`) e o Financeiro (03) a consome no formulário da
avaliação de desempenho (`financeiro/routes.py`, `_contrato_avaliacao_form_context`): o critério
HSE mostra o hint e pré-seleciona a nota, e o avaliador pode trocá-la — a nota gravada é a que
ele confirmar. Não há ciclo: o HSE não importa o Financeiro.

## Parâmetros

O grupo `hse` dos parâmetros traz as metas de observações e desvios por 10 mil HHT
(`metas.observacoesPor10MilHht` e `metas.desviosPor10MilHht`) e os prazos legais da ocorrência
(`prazos.comunicacaoHoras`, `prazos.investigacaoPreliminarHoras` e `prazos.relatorioFinalDias`,
padrões 24, 48 e 30 quando ausentes); os prazos **vigentes no registro ficam gravados na
ocorrência** (D5b). A base das taxas (`baseTaxa`, 1.000.000 ou 200.000) e a referência da
pirâmide (`referenciaPiramide`, `bird` ou `heinrich`) entram com a ISSUE-075 e o painel as lê a
cada leitura — trocar o parâmetro recalcula na hora.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas de HHT e da segurança proativa | `routes.py` |
| Rotas das ocorrências | `ocorrencias_routes.py` |
| Rotas das análises de risco | `analises_risco_routes.py` |
| Rotas do painel | `painel_routes.py` |
| HHT, fechamento, inspeções, observações, DDS, a fachada das ocorrências e a das análises | `service.py` |
| Painel: as janelas, os indicadores, os gráficos e a nota sugerida | `painel_service.py` |
| Fator, histograma, taxas, pirâmide, potencial, HiPo, prazos, o indicador de fechamento e os cálculos do painel | `calculations.py` |
| Validações e campos restritos | `validation.py` |
| Formulários e campos por tipo | `forms.py` |
| Importação por planilha | `importers.py` |
| Exportação (Excel e imprimível) | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` §12 |
| Carga de demonstração | `seed.py` (partes `hse`, `hse-ocorrencias` e `hse-analises-risco`) |
| Fragmentos | `api/src/templates/hse/` |
| Tela, estilo e comportamento | `app/_views/hse/` e `app/paginas/hse/` |
| Testes | `api/tests/hse/` e `api/tests/oraculo/test_oraculo_hse.py` |

O painel consome o indicador de recomendações fechadas ÷ emitidas por
`service.recommendation_share` e as ações de HSE pela fachada da Central; a nota sugerida é lida
pelo formulário da avaliação de desempenho do Financeiro (03). O botão "Análise do período"
abriu na ISSUE-082: ele abre o modal do módulo `relatorio` (`/api/relatorio/analise/...`), com o
resumo do mês e do acumulado, as ocorrências do período e a análise do Portfólio; só o texto é
obrigatório, sem desvios detectados.
