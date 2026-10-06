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
