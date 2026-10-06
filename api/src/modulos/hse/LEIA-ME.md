# HSE

Módulo `hse` (saúde, segurança e meio ambiente). Registra HHT, ocorrências, inspeções/observações, DDS e estudos APR/HAZOP. As funcionalidades entram nas ISSUE-072 a ISSUE-075 (a ISSUE-074, Análises de risco, está descrita na seção própria abaixo).

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Painel HSE | Taxas reativas/proativas, pirâmides, dias sem afastamento e evolução | ISSUE-075 |
| Ocorrências | Registro, investigação, ações, encerramento e anexos | ISSUE-073 |
| Inspeções e observações | Checklists, observações comportamentais e DDS | ISSUE-072 |
| Análises de risco | APR/JSA, HAZOP e recomendações (entregue, ver abaixo) | ISSUE-074 |
| HHT | Horas-homem trabalhadas por mês e empresa | ISSUE-072 |

Nome e dados médicos ficam restritos segundo Q35; o formulário pode coletar esses dados, mas só Gestor e Admin podem lê-los.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Painel HSE | `app/_views/hse/painel.html` | `app/paginas/hse/painel.css` | `app/paginas/hse/painel.js` |
| Ocorrências | `app/_views/hse/ocorrencias.html` | `app/paginas/hse/ocorrencias.css` | `app/paginas/hse/ocorrencias.js` |
| Inspeções e observações | `app/_views/hse/inspecoes.html` | `app/paginas/hse/inspecoes.css` | `app/paginas/hse/inspecoes.js` |
| Análises de risco (APR/HAZOP) | `app/_views/hse/analises_risco.html` | `app/paginas/hse/analises_risco.css` | `app/paginas/hse/analises_risco.js` |
| Horas trabalhadas (HHT) | `app/_views/hse/hht.html` | `app/paginas/hse/hht.css` | `app/paginas/hse/hht.js` |

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
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/hse/` |
| Tela, estilo e comportamento | `app/_views/hse/` e `app/paginas/hse/` |
| Testes | `api/tests/hse/` |

As ISSUE-073 a ISSUE-075 completam este documento (ocorrências, análises de risco e painel).

## ISSUE-072: HHT, inspeções, observações e DDS

**Telas.** HHT (`hht`): indicadores, tabela paginada, formulário mensal (mês e empresa bloqueados ao editar), importação Excel e histograma de mão de obra. Inspeções e observações (`inspecoes`): inspeção por checklist (itens conformes e não conformes), observação comportamental, DDS (tema, data, participantes) e o consolidado mensal (um por mês), com importação Excel e Excel/PDF pelos mecanismos da plataforma.

**Rotas** (`/api/hse/`): `hht`, `hht/excel`, `hht/imprimivel`, `hht/novo` e `hht/{id}/editar` (GET/POST); `histograma` (fragmento para o Cronograma de desembolso); `inspecoes`, `inspecoes/excel`, `inspecoes/imprimivel`, `inspecoes/{tipo}/novo` e `inspecoes/{tipo}/{id}/editar` (GET/POST). Importadores registrados em `importers.py`.

**Fórmulas** (`calculations.py`): `hours_per_person` (HHT ÷ efetivo médio), `expected_months` (meses esperados com registro), `summarize_hours`, `histogram_factor` (avanço previsto ÷ real do mês na Curva S física, entre 0,85 e 1,20), `labour_histogram` (HHT e efetivo do mês vezes o fator; horas em centenas, efetivo em unidades), `rate_percent` (taxa de DDS e de conformidade, 1 casa), `proactive_target` (meta por 10 mil HHT).

**Fluxos.** Gravar de novo o mesmo mês e empresa atualiza (`service.save_hours`), nunca duplica; o consolidado é um por mês (`save_closing`); a importação recusa as linhas inválidas e grava as válidas só na confirmação. Nome e dados pessoais de observações seguem a restrição de Q35.

**Integração pendente.** O histograma lê a Curva S física por `service.register_curve_reader`; enquanto o módulo dono da curva (EAP) não registra o leitor, o fator vale 1. O desembolso pede o fragmento `GET /api/hse/histograma`.

**Carga e oráculo.** `seed.py` grava `hht` e `hseMensal` do protótipo (meses deslocados pela distância em meses). O protótipo não traz inspeção, observação nem DDS individuais. Oráculo em `api/tests/oraculo/test_oraculo_hse.py`; testes puros em `api/tests/hse/`.

## Análises de risco (ISSUE-074, HU-123)

Tela `hse/analises_risco` (`app/_views/hse/analises_risco.html`, `app/paginas/hse/analises_risco.{css,js}`): quatro indicadores (estudos registrados, recomendações abertas, atrasadas e fechadas ÷ emitidas, cada um com o esperado), filtro (busca por número, título ou área; tipo; só estudos com recomendação aberta) e a tabela de estudos com a coluna Projeto no Portfólio. O estudo abre num modal com as recomendações; ali a pessoa fecha uma recomendação (data de conclusão e evidência opcional) ou cria a ação dela na Central. Excel e PDF pelos mecanismos genéricos, com o mesmo conteúdo do protótipo (indicadores e tabela de estudos, respeitando o filtro). Vinda do link de uma ação (`?busca=<código>`), a tela abre o estudo sozinha. No Portfólio o botão "Novo estudo" pede o projeto antes.

### Arquivos

| Arquivo | Papel |
|---|---|
| `models.py` | `RiskAnalysis` (`analise_risco`), `RiskAnalysisParticipant`, `RiskRecommendation` (inclui `concluida_em` e `evidencia`) |
| `analysis_service.py` | A fachada: `save_analysis`, `list_analyses`, `find_analysis`, `close_recommendation`, `create_recommendation_action`, `react_to_action` |
| `calculations.py` | `count_recommendations`, `is_recommendation_overdue`, `recommendations_closed_rate` |
| `validation.py` | `AnalysisInput`, `RecommendationInput`, `analysis_problems`, `recommendation_closing_problems` |
| `analysis_routes.py` e `analysis_export.py` | Rotas e documento de exportação |
| `origins.py` | A reação e o link da origem `HSE` na Central, compartilhados pelas partes do HSE |
| `api/src/templates/hse/` | `analises_risco.html`, `analises_risco_partes.html`, `_analises_kpis.html`, `_analises_tabela.html`, `analise_nova.html`, `analise_ver.html`, `analise_fechar.html` |

### Rotas (prefixo `/api/hse/analises-de-risco`)

`GET` tela (`busca`, `tipo`, `situacao=abertas`, `pagina`); `GET excel` e `GET imprimivel`; `GET` e `POST novo` (estudo do projeto no escopo); `GET {codigo}` (estudo e recomendações); `GET` e `POST {codigo}/recomendacoes/{ordem}/fechar`; `POST {codigo}/recomendacoes/{ordem}/acao`. Escrever exige o papel de Membro ou acima; ler, o acesso ao módulo.

### Fórmulas

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Recomendação atrasada | Situação Aberta e prazo anterior à data de referência (prazo no dia da referência não está atrasado) | `calculations.is_recommendation_overdue` |
| Recomendações emitidas, abertas, atrasadas e fechadas | Contagem das recomendações de um ou mais estudos | `calculations.count_recommendations` |
| Recomendações fechadas ÷ emitidas | Fechadas × 100 ÷ emitidas, uma casa decimal, meio para cima; vazio sem recomendação emitida. Alimenta o painel (ISSUE-075) | `calculations.recommendations_closed_rate` |

### Fluxos e integração com a Central (D9)

* Novo estudo: tipo (APR ou HAZOP), área, data (não posterior à referência), título (5 a 150 caracteres), ao menos um participante e ao menos uma recomendação (responsável e prazo obrigatórios; linhas sem descrição são ignoradas; até 10 por estudo no formulário). O código vem da numeração do projeto (`APR-<padrão>-0001`, `HAZOP-<padrão>-0001`; o próximo é o maior sufixo existente mais um).
* "Criar ação": `central_acoes.service.create_action` com origem `HSE`, referência o código do estudo e item o número da recomendação, responsável e prazo da recomendação; a ação aponta de volta ao estudo pelo link da origem (`origins.py` registra o tipo `HSE`). Uma recomendação tem no máximo uma ação.
* Sincronia, na mesma transação, nos dois sentidos: fechar a recomendação conclui a ação dela (`close_from_origin` com o item); concluir a ação na Central fecha a recomendação na data da conclusão; replanejar a ação move o prazo da recomendação (`react_to_action`, reação da origem `HSE`).
* Ocorrências (ISSUE-073) usam a mesma origem `HSE`: registram o tratador da referência em `origins.register_action_handler` e `origins.register_link_builder`, sem registrar uma segunda reação.

### Onde mexer

Nova regra de estudo: `validation.py` e `analysis_service.py`. Novo indicador: `calculations.py` e `analysis_export.py`. Aparência da tabela: `_analises_tabela.html`. Carga de demonstração: `seed.py` (lê `analisesRisco`, mantém o código do protótipo e a situação de cada recomendação).
