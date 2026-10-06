# Handover: protótipo Gestão Integrada AMT (Timenow)

Documento para retomar o trabalho em outro chat. Data: 01/10/2026 (atualizado após os **ajustes de 01/10/2026**: dica das siglas, referência em todos os cards, controle de contingência e remanejamento da EAC por SM; antes, em 30/09/2026, o **06 Gestão da Qualidade** e **Configurações > Parâmetros**, que encerram a etapa 5; antes, no mesmo dia, a **gestão de portfólio**: 3 projetos, visão por projeto e Portfólio em todos os módulos, ponderação da carteira e relatório gerencial do portfólio; antes, em 28/09/2026: Relato do período, relatório gerencial e análise do período). Idioma de trabalho: português do Brasil.

## 1. Onde as coisas estão

| O quê | Onde |
|---|---|
| Protótipo (fonte da verdade) | `C:\Users\leonardo.gomes\Documents\Sistema Gestão\Sistema\` |
| Documentação completa (paleta, telas, regras, API) | `README.md` na raiz |
| Este handover | `HANDOVER.md` na raiz |
| Ferramentas de desenvolvimento (gerador de páginas e testes) | `_dev/` na raiz (ver `_dev/LEIA-ME.md`) |
| Resumo de decisões no projeto do Claude (GI) | `claude/prototipo-gi-status.md` e `claude/aderencia-cipm-tartan-book.md` |

Estado da pasta: sincronizada em 30/09/2026, após o 06 Gestão da Qualidade e Configurações > Parâmetros (cópia de trabalho e pasta conferidas por soma md5).

## 2. Regras obrigatórias (vêm do prompt original; não mudar sem o usuário)

* Tudo dentro da raiz `...\Sistema Gestão\Sistema\`. **Pare e pergunte** antes de gravar fora da raiz, sobrescrever arquivo existente fora do fluxo normal ou quando uma fonte de referência estiver ausente ou ilegível (não inventar o conteúdo).
* **Nunca** ler, usar ou citar `C:\Users\leonardo.gomes\Documents\Sistema Gestão Integrada\Legado\`. As pastas de referência são somente leitura.
* **Nunca** ler, usar ou distribuir `Acesso.txt` (senha de admin do app de referência).
* Abre com duplo clique em `index.html` (`file://`), sem servidor e **sem `fetch()`** para arquivos locais. Dados mock ficam em `.js` (`window.MOCK = {...}`).
* Todos os botões em **pílula** (`border-radius: 999px`), sem exceção.
* Cores **só por variáveis CSS** de `css/tokens.css`; nenhum hexadecimal solto nas telas. A exceção E1 (vermelho) vale **só para sobrecusto financeiro**. Desvio de prazo ou físico usa laranja (`.valor--negativo`).
* Valores financeiros em **centavos inteiros** (R$ 10,50 = 1050), formatados só na exibição.
* Uma HTML por tela, com layout comum (`js/layout.js`). Breakpoints ≤480, ≤768, ≤1024 e >1024; zero rolagem horizontal da página em 360px (tabela larga rola dentro do contêiner); toque ≥44px; contraste AA.
* Toda tabela e painel com exportação Excel e PDF; Chart.js com cores dos tokens; bibliotecas locais em `assets/vendor/`.
* Depois de cada etapa: "✅ [concluído]" com a lista de arquivos.

Preferências do usuário: respostas curtas, sem preâmbulo, bullets com `*`, **nenhum travessão nem meia-risca** (caracteres U+2014 e U+2013), inclusive dentro dos arquivos. Tarefas complexas e de código terminam com "Status de Execução" (Feito, Pendente, Riscos). Aplicar sempre as boas práticas de gerenciamento de projetos (PMBOK, ISO 21502, completação e comissionamento). Apontar conflitos com decisões anteriores antes de seguir.

## 3. Estado das etapas

| Etapa | Situação |
|---|---|
| 1 a 4 (fontes, design system, aprovação, layout, Home, camada de dados, páginas-base) | Concluídas |
| 5. Telas completas | **01 Central de Ações, 02 Planejamento, 03 Gestão Financeira, 04 Suprimentos (com o MAS), 05 Gestão de Riscos, 07 HSE e 08 Governança concluídos; 02 ganhou as telas Produtividade, EAP e Relato do período (28/09/2026); relatório gerencial no Início (28/09/2026); gestão de portfólio com 3 projetos (30/09/2026); 06 Gestão da Qualidade e Configurações > Parâmetros (30/09/2026).** Etapa concluída |
| 6. Upload e exportação | Entregue em todos os módulos, Configurações, Home e relatório gerencial |
| 7. Validação final | Pendente (fazer ao fim da etapa 5) |

Módulos: 01 Central de Ações · 02 Planejamento · 03 Gestão Financeira · 04 Suprimentos · 05 Gestão de Riscos · 06 Gestão da Qualidade · 07 HSE · 08 Governança · Configurações (só Gestor e Admin).

Todas as telas estão completas (o 06 e Parâmetros deixaram de ser página-base em 30/09/2026).

## 4. Padrão atual das telas (ajustes de 25/09/2026)

* **Nome do sistema:** Gestão Integrada AMT.
* **Sem título, eyebrow nem subtítulo no topo.** O header mostra módulo e tela. Cada página tem `<h1 class="sr-only" id="titulo">` e logo abaixo a **barra da página**:
  `<div class="page-bar"><nav data-module-tabs></nav><div class="page-actions" id="acoes-pagina">...</div></div>`
  Abas do módulo à esquerda e ações à direita, na mesma linha. Tela de detalhe usa o botão Voltar no lugar das abas e chama `GI.layout.detalhe("Registro X")` para completar o contexto do header.
* **Compactação automática da barra** (`layout.js`): nível 1 reduz o respiro e esconde "Exportar" (os botões usam `<span class="btn__prefixo">Exportar </span>Excel`); nível 2 tira os ícones das abas. Se ainda não couber, as ações descem para a linha de baixo. Itens da NAV podem ter `curto` (nome menor na aba).
* **Bilíngue PT/EN:** botão "PT | IN" no header. `js/i18n.js` traduz o DOM pelo dicionário `js/i18n/en.js` (texto português exato, padrões regex e regra número + unidade). **Toda tela nova precisa das suas entradas em `en.js`.** Para padrões de um módulo, registrar com `GI.i18n.registrar(dic, padroes, true)`, que coloca os padrões na frente dos genéricos. Não traduzir dados dos usuários, o nome do sistema nem o styleguide. `data-sem-traducao` exclui um trecho.
* **Persistência:** as gravações ficam no `sessionStorage` (`gi.prototipo.alteracoes.v2`); o botão "Restaurar dados de demonstração" aparece no rodapé do menu. A data de referência é fixa: **25/09/2026**.

## 5. Arquitetura técnica (resumo)

Ordem dos scripts em toda tela: `js/i18n.js`, `js/i18n/en.js`, `data/mock-*.js`, `js/services/regras.js`, `js/services/api.js`, `[chart.umd.min.js]`, componentes, `[charts.js]`, extras, `js/layout.js`, `js/pages/<modulo>/<tela>.js`.

| Namespace | Arquivo | Uso |
|---|---|---|
| `GI.api` | `js/services/api.js` | Única porta de dados (Promises). CRUD genérico `listar/obter/salvar/excluir(colecao)`, `proximoCodigo`, `cadastros`, `parametros`, e um grupo por módulo (`central`, `planejamento`, `financeiro`, `suprimentos`, `riscos`, `qualidade`, `hse`, `governanca`, `resumoHome`). Cada ponto de troca está marcado com `TODO: API` e o endpoint sugerido |
| `GI.regras` | `js/services/regras.js` | Regras puras (dias entre datas, faixa de desvio, severidade, taxas HSE, avaliação de contratada) |
| `GI.util` | `js/components/comum.js` | `pronto()` (cadastros), `pessoa/empresa/projeto`, `esc`, `icone`, `badge`, `kpi({ rotulo, valor, unidade, moeda, sinal, icone, cor, rodape, href, filtro })`, `tela(modulo, tela, params)`, `opcoes`, `plural`, `mesCurto`, `contem` |
| `GI.tabela` | `js/components/tabela.js` | `criar(el, { colunas, porPagina, ordem, pilha, compacta, acoes, rodape, classeLinha, celulaVazia })`, `escolherColunas(t)`, `exportacao()` |
| `GI.form` | `js/components/formulario.js` | `abrir({ titulo, campos, validar, aoSalvar(v, modal, acao), aoMudar, extras })`; campo com `mostrarSe(v)`; `info` atualizado por `ctx.info(id, html)`; tipos `escolha` (pílulas, com número e legenda) e `radio`; `extras` = botões entre Cancelar e Salvar (ex.: Salvar e avaliar, Limpar); o modal devolvido tem `ler()`, `definir(valores)` e `erros()` |
| `GI.exportar` | `js/components/exportar.js` | `registrar(fn)` devolve `{ titulo, subtitulo, arquivo, orientacao, blocos: [kpis, grafico, tabela] }`; botões `data-exportar="excel"` e `data-exportar="pdf"` |
| `GI.importar` / `GI.upload` | `importar.js`, `upload.js` | Importação em 5 passos com modelo; upload com validação |
| `GI.charts` | `js/components/charts.js` | `line`, `bar`, `sCurve`, `sCurveFinanceira`, `waterfall`, `pyramid`; cores por nome de token (`"chart-1"`) |
| `GI.fmt` / `GI.ui` / `GI.modal` | `ui.js`, `modal.js` | Formatação no idioma ativo (`moeda`, `moedaCompacta`, `moedaPartes`, `pct`, `num`, `data`), toasts, abas, modais e `confirm` |
| `GI.fin` | `js/pages/financeiro/financeiro.js` | Apoio do 03: seletor de projeto, R$ mil, mapa de calor, árvore da EAC, selos |
| `GI.sup` | `js/pages/suprimentos/suprimentos.js` | Apoio do 04: seletor de projeto, selos de etapa, folga, situação e qualificação, célula e legenda do MAS |
| `GI.gov` | `js/pages/governanca/governanca.js` | Apoio do 08: seletor de projeto, selos (situação da SM e da lição, tipo, prioridade), custo e prazo com sinal, barra de etapas, chips e modal de filtros, botões do fluxo por situação e papel e todos os modais de mudança e de lição |
| `GI.rsk` | `js/pages/riscos/riscos.js` | Apoio do 05: seletor de projeto, contexto, selos de severidade (oportunidade com cor invertida), situação, cadência e **os modais 10 a 17** (novo, editar, avaliar, plano, aprovarPlano, novaAcao, revisar, encerrar, reabrir, excluir), usados no registro, na matriz e na ficha |

Coleções mock já prontas para o próximo módulo: `rncs`, `itps`, `inspecoesQualidade`, `auditorias` (06). A api já calcula os indicadores de suprimentos, riscos, qualidade, HSE e mudanças, usados na Home.

Números do cenário (manter coerentes): BAC R$ 44,6 mi, CPI 0,96, SPI 0,94, projeção R$ 45,26 mi, 8 ações atrasadas, 3 pedidos críticos, 2 riscos críticos, 4 RNC abertas, 263 dias sem afastamento (desde o início do projeto, nenhuma LTI), TF 0,00, TG 0, pirâmide 0/16/31/190/1240 (lesão grave zero em todos os meses), 3 SMs aguardando comitê, SM-TN-2026-0004 aprovada e ainda não incorporada ao orçamento.

## 6. Como construir uma tela nova (checklist)

1. Ler a especificação em `README.md` seção 3 e os dados/funções em `api.js`. Se a regra exigir cálculo novo, criar a função na api (com `TODO: API`), não na tela.
2. Descrever a página em `_dev/specs_0N.py` (corpo HTML, ações da barra, `graficos`, `extras`) e gerar com `python3 telas.py specs_0N.py` (dentro de `_dev/`).
3. Escrever `js/pages/<modulo>/<tela>.js`: `GI.util.pronto().then(...)`, KPIs com `U.kpi`, tabelas com `GI.tabela`, modais com `GI.form`, gráficos com `GI.charts` e `GI.exportar.registrar(...)`.
4. Incluir as traduções em `js/i18n/en.js` (bloco do módulo com `antes = true`) e checar com `_dev/coleta_en.py`.
5. Validar: `_dev/crawl.py` (erros de console, links, pílulas, overflow em 360 e 1440), fluxos com `_dev/t_pag.py` e capturas em 360, 768 e 1440, PT e EN. Conferir que não há hexadecimal solto nem travessão.
6. Atualizar o `README.md` (situação do módulo e decisões) e o `claude/prototipo-gi-status.md` do projeto.
7. Gravar na pasta do computador. Antes, comparar a soma de verificação (md5) da pasta com a da cópia de trabalho para não sobrescrever uma edição do usuário. Gravar no máximo 50 arquivos por vez e conferir as somas no fim.

## 7. Módulo 04 Suprimentos (concluído em 26/09/2026)

Seis telas: Painel, Plano de compras, Processos de compra (RFx), **MAS (Mapa de Suprimentos)**, Diligenciamento e Fornecedores. Regras completas em `README.md` seção 3, "04 Suprimentos".

* **MAS:** uma linha por pacote, 12 marcos (7 de aquisição e 5 de fabricação e entrega) com LB, previsão e realizado; situação por cor, ícone e texto (no prazo, com atraso, vencido, previsão após a LB, a vencer, não se aplica); Datas ou Desvio em dias; filtros e ordenação; folga, avanço (critério de medição por pesos dos parâmetros, ponderado pelo valor) e situação. Montado pela api (`GI.api.suprimentos.mas`) a partir de plano, processos e pedidos: não tem cadastro próprio. Exporta Excel (3 colunas por marco) e PDF A3 com células coloridas (`exportar.js` ganhou `formato` e `corCelula`).
* **Processos:** fluxo completo das 9 etapas em `GI.api.suprimentos.acaoProcesso`, com mínimo de propostas, técnica antes da comercial, alçada (parâmetros), segregação de funções e limite do saldo da EAC. A emissão cria pedido (04) ou contrato (03) e compromete a EAC.
* **Diligenciamento:** folga negativa cria ação na Central e sugere o risco (05); FAT realizado grava inspeção no 06; recebimento com avarias e pendências; importação do ERP.
* **Parâmetros novos** (`MOCK.parametros.suprimentos`): `alcadas` e `pesosMarcos`, com validação em `GI.regras.validarParametros`.
* Cenário do mock mantido: 3 pedidos críticos na Home; PC-14 (SDCD) em equalização comercial, pronto para demonstrar o fluxo até o pedido.

## 7.1 Módulo 05 Gestão de Riscos (concluído em 26/09/2026)

Quatro telas (Registro, Matriz P x I, Ficha, Painel) e os modais 10 a 17 replicados dos mockups de `Sistema Gestão Integrada\Módulo de Riscos\mockups\`, no padrão atual. Regras, decisões e divergências entre mockups em `README.md` seção 3, "05 Gestão de Riscos".

* **Camada de dados:** `GI.api.riscos` com lista, resumo, matriz, painel, ficha, prévia, salvar, avaliar, plano, aprovação, nova ação, revisão, encerramento, reabertura, exclusão lógica, restauração e catálogo RBS (todos com `TODO: API`). Regras puras novas em `GI.regras`: `impactoResultante`, `vme`, `cadenciaRisco`, `ordemFaixa`. Parâmetros novos em `MOCK.parametros.riscos`: `cadenciaDias`, `probabilidades`, `impactos`, `pautaDiasAntesDoPrazo`, `revisaoAlertaDias` (validados).
* **Integrações:** ações do risco são da Central (origem Risco, item sequencial por risco, contribuição P/I); o diligenciamento (04) cria risco "Em análise" com resposta proposta que preenche o plano; encerramento cria lição em Rascunho (08) e, se materializado, ação de problema e SM Registrada (08); plano com Evitar aponta SM existente ou gera ação para registrá-la.
* **Componentes:** `GI.form` ganhou `escolha`, `radio` e `extras`; `i18n.js` passou a traduzir o placeholder das áreas de texto; corrigido no `en.js` o padrão do 04 que traduzia "há N dias" como "for N dias".
* **Cenário mantido:** 2 riscos críticos e exposição R$ 3,4 mi na Home; 8 ações atrasadas na Central.

## 7.2 Módulo 07 HSE (concluído em 27/09/2026, adiantado antes do 06)

Cinco telas: Painel HSE, Ocorrências, Inspeções e observações, Análises de risco (APR/JSA e HAZOP) e HHT. Sem fonte de referência (proposta pelas boas práticas, README seção 3, "07 HSE"). Regras, decisões e cenário do mock em `README.md` seção 3 e em `claude/prototipo-gi-status.md`.

* **Camada de dados:** `GI.api.hse` cobre painel (pirâmide, evolução mensal, taxas), ocorrências (listar, ficha, registrar, investigar, ação corretiva, iniciar tratamento, encerrar), análises de risco (listar, ficha, registrar, recomendação, fechar recomendação, criar ação) e HHT/mensal (registrar mês, upsert por mês e empresa). Regra pura nova em `GI.regras`: `faixaPotencialHSE(p, i)`.
* **Sem fichas separadas:** ocorrência e estudo abrem em modal a partir da própria lista (mesmo padrão do 05 para o risco).
* **Pirâmide de segurança:** `GI.charts.pyramid` reaproveitado do 05 sem alteração; referência configurável (Bird ou Heinrich).
* **Ciclo da ocorrência:** Registrada → Em investigação → Ações definidas → Em tratamento → Encerrada. Nível 5 (desvio) não tem registro individual, vem do consolidado mensal de Inspeções e observações.
* **Central de Ações:** `GI.util.linkOrigem` distingue prefixo `OCR-` (ocorrência) de `APR-`/`HAZOP-` (estudo) para rotear de volta à tela de origem.
* **HHT e registros mensais:** editar reabre o mesmo registro do mês (e da empresa, no HHT) com esses campos bloqueados; só os totais são editáveis.
* **i18n:** dicionário global (`js/i18n/en.js`) sem namespace por módulo; as palavras soltas "Prazo", "Desvio" e "Emissão" já tinham tradução de outros módulos (05, 05 e 04) e foram mantidas como estavam, para não quebrar essas telas; o 07 não as redefiniu (limitação conhecida, documentada também no `README.md`).
* **Cenário mantido:** 240 ocorrências (63 abertas, 9 fora do prazo), 5 estudos de risco (8 recomendações abertas, 3 atrasadas), 788.070 HHT em 32 registros de 4 empresas.

## 7.2a Painel HSE: filtro de mês/ano e pirâmide dupla (28/09/2026)

Pedido do usuário: dados do mês e acumulado, com filtro de mês e ano, pirâmide de segurança em duas (mês filtrado e acumulado) e sem meses zerados nos indicadores. Mudanças em `modulos/hse/painel.html`, `js/pages/hse/painel.js`, `js/i18n/en.js` e `data/mock-hse.js`.

* **Filtro:** selects `#f-ano` e `#f-mes` na barra de filtros, preenchidos a partir dos meses com HHT (`evolucao` do `GI.api.hse.painel`); mês padrão é o último com HHT.
* **Mês x acumulado:** "No mês selecionado" usa `{inicio: mes, fim: mes}`; "Acumulado" usa `{inicio: primeiroMesComHht, fim: mes}` (mesmo critério de acumulado até o corte usado em Financeiro e Planejamento). TF, TRIF, TG e HiPo aparecem nos dois blocos; "Dias sem afastamento" e "Ações HSE no prazo" só no Acumulado, por não variarem com o período (o primeiro usa a data do último LTI, sempre; o segundo compara com a data de referência, sempre).
* **Pirâmide dupla:** dois `<div class="pyramid">` (`#piramide-mes` e `#piramide-acum`), cada um com sua própria chamada a `GI.charts.pyramid`; a nota de referência (Bird/Heinrich) é só uma, comum às duas, porque o texto não depende dos valores.
* **Pirâmide padronizada e lesão grave zero (28/09/2026, segundo ajuste do usuário):** "muito texto e pirâmides de tamanhos diferentes" (a altura de cada faixa variava com a quebra do texto ao lado). Novo componente `GI.charts.pyramidPair` em `charts.js`: um único `<div class="pyramid-pair" id="piramides">` com grid de 3 colunas (pirâmide do mês, rótulos, pirâmide do acumulado) e linhas de altura fixa; rótulos no plural ("Lesões graves"... "Desvios", porque "Desvio" já é "Variance" no `en.js`); proporção real numa linha por pirâmide e referência numa linha no rodapé. Texto por nível ("Real 1 : X · Bird 1 : 10", "sem lesão grave no período", "Base de comparação") removido. `GI.charts.pyramid` segue o mesmo padrão visual. `specs_07.py` sincronizado com a página (gerador reproduz o `painel.html` idêntico).
* **Lesão grave = 0 em todo o HSE:** os dois acidentes com afastamento de fevereiro viraram "Trabalho restrito" (03/02) e "Tratamento médico" (25/02, HiPo mantido), gravidade real 2, sem dias perdidos. API: sem LTI, `diasSemAfastamento` conta desde `projeto.inicio` e devolve `inicioContagem`; rodapé do KPI "desde o início do projeto (05/01/2026)". Styleguide ajustado (263 dias, TF 0, pirâmide 0/16/31/190/1240). Plural corrigido no rodapé da TF ("0 acidentes com afastamento").
* **Mock (`data/mock-hse.js`):** dois registros de "Primeiros socorros" (nível 2, lesão leve) remanejados de julho para janeiro e fevereiro, que ficavam zerados no filtro por mês.
* **i18n:** corrigidos dois textos da pirâmide que nunca tinham tradução completa (não achados pelo `coleta_en.py` porque não usam palavras do heurístico de detecção): o texto "Real 1 : X" dentro do `<b>` e o texto "· Heinrich 1 : 300 (níveis 3 e 4 somados)" fora dele (são nós de texto separados, por causa da tag `<b>`); só apareciam ao alternar para a referência Heinrich, testado manualmente com `_dev/t_pag.py` (`coleta_en.py` não clica no segmentado Bird/Heinrich porque ele não abre modal).

## 7.3 Módulo 08 Governança (concluído em 28/09/2026, adiantado antes do 06)

Três telas: Gestão de mudanças (`mudancas.html`, abas Registro e Painel), Ficha da mudança (`mudanca.html?codigo=`, 5 abas e barra de etapas) e Lições aprendidas (`licoes.html`, abas Acervo e Painel). Sem fonte de referência. Regras e decisões em `README.md` seção 3, "08 Governança".

* **Camada de dados:** `GI.api.governanca` com lista, resumo, painel, ficha, salvar, iniciar análise, análise (rascunho ou envio), decisão, reapresentação, implementação, encerramento, cancelamento e conferência; lições com lista (visibilidade pela aplicabilidade), ficha, painel, salvar, envio, validação, publicação e aplicação. Regra pura nova: `GI.regras.alcadaMudanca`. Parâmetros novos: `mudancas.prazoAnaliseDias`, `quorumComite`, `prazoAcoesDias`, `ratificacaoDias` e `licoes.alertaSemRegistroDias` (validados).
* **Alçada mínima** calculada (custo até 1% do orçamento e sem marco contratual: gerente; senão Comitê), elevável e nunca rebaixada. Decisão exige Gestor, quórum no Comitê e o gerente como decisor na alçada dele.
* **Integrações:** aprovação cria ações na Central (origem Mudança) conforme a análise; o custo aprovado aparece como SM pendente na EAC (03); encerramento recusa ação aberta e custo não incorporado (revisão da EAC com `smRef`); lição opcional em Rascunho. Aplicar lição cria ação (origem Lição) ou risco Identificado no 05. Home: KPI leva ao registro filtrado por "Aguardando comitê"; alertas de ratificação e análise vencidas.
* **Mock:** SMs ganharam `impacto.dataAnalise`, `analistaId`, `afetaMarcoContratual`, `eacItens`, `atividades`, `decisao.justificativa`, `implementacao` e `analise` (SM-0007); nenhum número do cenário mudou.
* **i18n:** bloco do 08 no `en.js` com padrões na frente; "Encerramento" passou a "Closure" (usado também no rótulo de data do 04, sem prejuízo).
* **Cenário mantido:** 3 SMs aguardando comitê, R$ 1,2 mi aprovados (2,7% do orçamento), +42 dias, 46 dias de decisão; SM-0004 aprovada e não incorporada à EAC; 8 lições (4 publicadas).

## 7.3.1 Tela Produtividade no 02 Planejamento (28/09/2026)

Aba nova entre Programação Semanal e Punch list (`modulos/planejamento/produtividade.html`, `js/pages/planejamento/produtividade.js`, spec em `_dev/specs_02.py`). Regras completas em `README.md` seção 3, "Produtividade: regras".

* **Filtros globais:** Empresa e Semana de corte (semanas ISO `2026-S39`, W39 em inglês). Abas internas: Quantidades, Horas efetivas (visões Capacidade produtiva, Amostragem do trabalho, Paralisações) e KPIs de performance (geral e por empresa). `?aba=kpis&corte=2026-S38&empresa=1` abre direto.
* **Camada de dados:** `GI.api.planejamento.produtividade` (quantidades, item, salvarItem, aprovarItem, revisarItem, excluirItem, apontar, importarItens, horasEfetivas, salvarJornada, salvarAmostragem, salvarParalisacao, kpis, gerarAcao, smsRevisao), todos com `TODO: API`. Coleções novas: `produtividadeItens`, `jornadasCampo`, `amostragens`, `paralisacoes` (geradas no fim de `mock-planejamento.js` com semente fixa). Regras puras novas em `GI.regras`: semanas ISO (`semanaIso`, `inicioSemana`, `somarSemanas`, `semanasEntre`, `listaSemanas`), `distribuirQuantidade` (perfil e maior resto), `minutos`, `duracaoHoras`, `faixaIndicador`. Parâmetros novos em `MOCK.parametros.produtividade` (validados).
* **Integrações:** revisão da LB exige SM aprovada (08); paralisação de responsabilidade do cliente sinaliza pleito potencial (03); plano de ação vai para a Central com origem nova **Produtividade** (`PRD-<semana>-<empresa>`), com filtro nas telas da Central e link de volta em `GI.util.linkOrigem`.
* **Componentes:** `GI.form` ganhou o tipo `hora`; CSS novo no fim de `components.css` (jornada média, grade de semanas, grade de motivos, `cell-duo`, `kpi-grid--compacto`, `.section-title.mt-6`).
* **Cenário:** números dos outros módulos inalterados (a Central ganhou 1 ação em andamento, PRD-2026-S38-01; continuam 8 atrasadas).

## 7.3.2 Tela EAP no 02 Planejamento (28/09/2026)

Primeira aba do 02, antes da Curva S (`modulos/planejamento/eap.html`, `js/pages/planejamento/eap.js`, spec em `_dev/specs_02.py`). Espelho físico da EAC do 03. Regras completas em `README.md` seção 3, "EAP: regras".

* **Estrutura:** área > subárea > pacote (de trabalho ou de planejamento), pesos em % do projeto somando 100; árvore e recolhimento reaproveitam `GI.fin` (a página carrega `js/pages/financeiro/financeiro.js`).
* **Camada de dados:** `GI.api.planejamento.eap`, `eapRegistrarAvanco`, `eapImportarAvanco`, `eapEditarPacote`, `eapNovoPacote` (desdobramento ou revisão), `eapNovaRevisao`, `proximoCodigoEap`; coleções `eap`, `eapRevisoes`, `eapDesdobramentos`. Regras puras em `GI.regras`: `CRITERIOS_EAP`, `avancoPacoteEap`, `entradasPorPercentual`, `reescalarPesos`, `faixaDesvioFisico`. Parâmetros novos em `MOCK.parametros.eap` (faixas de desvio, pesos máximos, modelos de etapas), validados.
* **Integração 08:** SM aprovada com impacto em escopo exige revisão da EAP para encerrar (`exigeEap`, `eapRevisao` em `mudancaCalculada`); ficha e encerramento da SM mostram a pendência.
* **Atenção:** nomes de funções no `api.js` são de escopo único do arquivo (declarações de função com o mesmo nome se sobrescrevem): as da EAP têm sufixo `Eap` (houve colisão com `montarPacote` de suprimentos durante o desenvolvimento).
* **Pendente (decisão do usuário):** a Curva S e os KPIs por área seguem com lançamento próprio; a EAP só concilia.
* **Cenário:** números dos outros módulos inalterados (previsto 65,7% e real 61,8%, iguais à Curva S e ao avanço por área).

## 7.3.3 Projeto único, Relato do período e relatório gerencial (28/09/2026; a parte de projeto único foi revertida em 30/09/2026, ver 7.3.5)

Pedido do usuário: o sistema é de controle de **um projeto** ("Construção de uma nova fábrica"), não de portfólio; relatório gerencial semanal e mensal no Início; campos do relato no 02. Detalhes em `README.md` seção 3 ("Relatório gerencial: regras", "Projeto único" e "Relato do período: regras").

* **Projeto único:** `MOCK.portfolios` e o projeto 2 saíram (curva, riscos, pacotes, pedido, RFx e ações); `cadastros()` não devolve mais portfólios e `GI.util.portfolio` foi removido. Seletores `#f-projeto` saíram das specs (`SELETOR_PROJETO` removido) e das páginas; os helpers `GI.fin/sup/rsk/hse/gov.projeto()` continuam devolvendo o projeto atual (`?projeto=` ou `projetoAtualId()`), então a api segue por `projetoId`. Central sem filtros Portfólio/Projeto; atas só do projeto (a ata geral virou TN-2026-0034 "Padronização do relatório gerencial do projeto"); 05 com painel do projeto e aprovação pela "gerência do projeto"; 08 com aplicabilidade Projeto ou Corporativa e painel sem "Projetos sem registro".
* **EAP, EAC e Mapa de controle:** primeira linha = atividade resumo do projeto (código 0, nome do projeto, totais). `GI.fin.arvore(itens, { raiz })` cria a linha; `GI.fin.recolhimento` recolhe a árvore toda pela linha 0; classe `row--raiz`. Os rodapés de total saíram (EAC mantém "Total filtrado" só com filtro; `GI.tabela` aceita `rodape` devolvendo `null`).
* **Relato do período (02):** aba entre KPIs e 6WLA (`relato.html`, `js/pages/planejamento/relato.js`, spec em `specs_02.py`, NAV em `layout.js`). Coleção `relatos` (mock em `mock-planejamento.js`), api `planejamento.relatos/relato/periodosRelato/resumoRelatos/salvarRelato/excluirRelato`, regras de período em `GI.regras` (`limitesPeriodo`, `periodoDaData`, `somarPeriodos`, `listaPeriodos`, `periodoValido`). `GI.form` ganhou o tipo **`repetir`** (itens repetíveis com subcampos; erros no formato `campo.indice.subcampo`).
* **Relatório gerencial:** botão no Início (`index.html` agora carrega `formulario.js`) com modal (tipo, período com padrão na semana anterior, situação do relato, seções); `relatorio.html` (página sem menu; `css/relatorio.css`, `js/pages/relatorio.js`) com folhas A4 horizontais: Planejamento (2), Financeiro, Suprimentos e Riscos. Dados só por `GI.api.relatorioGerencial` (funções com sufixo `Rg` na api). Impressão pelo navegador; Excel pelas tabelas das folhas. `?relatorio=1&tipo=&periodo=` no Início reabre o modal.
* **Validação:** crawl sem erro em 45 páginas (360 e 1440), fluxos do relato (novo, validação, copiar, editar, excluir, abrir por URL) e do modal do relatório, PDF impresso pelo Chromium (5 páginas A4 horizontais) em PT e EN, exportações Excel e PDF das telas alteradas.
* **Pendente (decisão do usuário):** (1) no semanal, o Financeiro usa o último mês fechado (alternativa: mês corrente parcial); (2) riscos, avanço por área e EAC por pacote saem na posição atual mesmo em período passado (para histórico real, gravar fotografia semanal/mensal no backend); (3) a numeração e os textos do mock continuam de uma planta de beneficiamento (moagem e flotação) sob o nome novo; (4) relato sem fluxo de aprovação (Rascunho/Emitido), se desejar.

## 7.3.4 Análise do período por módulo, produtividade, tendência financeira e folha HSE (28/09/2026)

Pedido do usuário: campo de comentários (análise do período, com desvio e tendência) em 02, 03, 04, 05 e HSE, inserido e editado em modal no módulo; todo desvio negativo com comentário (02, 03 e 04); indicadores de produtividade no Planejamento; linha de tendência na Curva S financeira do relatório; folha HSE com KPIs, pirâmide e comentário. Regras em `README.md` seção 3 ("Análise do período por módulo: regras" e "Relatório gerencial: regras").

* **Api:** coleção `analisesPeriodo` ({ modulo, tipo, periodo, analise, desvios[{ chave, indicador, comentario }] }); bloco antes de `GI.api = {` com `produtividadeRg`, `hseRg`, `desviosDe` (desvios estruturados por chave), `resumoAnalise`, `dadosModuloRg`, `analiseMontada`; fachada `GI.api.analises` (periodo, periodos, situacao, salvar, excluir, MODULOS, OBRIGATORIO, LIMITES). `kpisProdutividade` virou `kpisProdutividadeDe` (síncrona) + wrapper. `relatorioGerencial` aceita a seção `hse` e devolve `analises` por seção. `financeiroRg` devolve `curva.tendencia` e `curva.eacTendencia` (`tendenciaCustoRg`: EAC = BAC ÷ CPI pelo perfil do planejado, sem dados posteriores ao período).
* **Componente:** `js/components/analise.js` (GI.analise.abrir, textoDesvio, valor). Botão `data-analise="<modulo>"` nas specs (02 relato e kpis, 03 kpis e curva-s, 04 painel, 05 painel, 07 painel) com o script em `extras`; `?analise=1&tipo=&periodo=` abre o passo 2. `GI.form` ganhou a opção de campo `antes` (HTML entre rótulo e controle, ligado por `aria-describedby`). `GI.charts.sCurveFinanceira` aceita `rotuloProjecao`.
* **Relatório:** Planejamento 1 com a linha de KPIs de produtividade; Planejamento 2 com análise, atividades e pontos de atenção; Financeiro, Suprimentos e Riscos rearranjados com o bloco de análise; nova folha HSE (`folhaHse`, `graficosHse`, pirâmide em escala `.rel-piramide`). Excel com as abas "Análises do período" e "Desvios negativos e comentários". Modal do Início com a seção HSE e a situação das análises por módulo.
* **Mock:** análises S38 e agosto nos 5 módulos (e S37 no 02), em cada `mock-<modulo>.js` com `concat`; S39 e setembro pendentes (período em andamento).
* **Validação:** crawl sem erro em 45 páginas (360 e 1440); fluxo do modal (passo 1 e 2, validação de desvio sem comentário, gravação, reabertura por URL) nos 6 pontos de entrada; PDF de 6 páginas A4 (S38, agosto e S39 pendente) em PT e EN sem transbordo; Excel do relatório com as análises; coleta EN só com conteúdo de usuário.
* **Pendente (decisão do usuário):** (1) HSE no semanal usa as taxas do mês que contém o corte (HHT é mensal) e as ocorrências da semana; (2) tendência financeira é estatística (CPI) e difere da projeção da EAC (bottom-up); (3) 05 e 07 sem regra de "desvio negativo" (propor: risco que subiu de faixa, revisão vencida, TRIF acima da meta); (4) análise sem fluxo de aprovação; (5) o texto do usuário não é traduzido no modo IN.

## 7.3.5 Gestão de portfólio (30/09/2026)

Pedido do usuário: visão por projeto e geral (portfólio) em todos os módulos; dois projetos fictícios novos (caldeira de biomassa e torre de resfriamento); relatórios por projeto ou portfólio (inclusive o gerencial); Curva S física e financeira do portfólio com ponderação dos projetos (uma das ponderações é o valor financeiro); na EAP e na EAC da carteira, projeto e mais um nível dos pacotes principais. Escolhas do usuário: seletor global no cabeçalho, ponderação composta e configurável, projetos completos em fases diferentes, análise própria do portfólio. Regras em `README.md` seção 3 ("Gestão de portfólio").

* **Escopo:** `GI.api.projetoAtualId()` lê `?projeto=portfolio|<id>`, depois `localStorage gi.escopo`; padrão `MOCK.projetoAtualId = null` (Portfólio). `definirEscopo`, `emPortfolio`; `U.tela(..., { projeto: null })` gera `projeto=portfolio`. Chave de alterações da sessão passou a `gi.prototipo.alteracoes.v2`. Seletor em `layout.js` (`seletorEscopo`, `trocarEscopo`: tela de detalhe volta para a lista).
* **Dados:** `data/mock-portfolio.js` (carregado em todas as páginas; `DADOS` em `telas.py`) com P2 e P3 em todos os módulos e análises do Portfólio (`projetoId: null`, S38 e agosto; setembro e S39 pendentes; P3 sem análise de agosto de propósito). `mock-base.js`: projetos 2 e 3, empresas 14 a 18, pessoas 14 a 18, `ponderacao` por projeto. `mock-config.js`: `portfolio.criterios`.
* **Api:** bloco de carteira antes de `GI.api = {` (`pesosCarteira`, `curvaFisicaCarteira`, `curvaFinanceiraCarteira`, `vaCarteiraNoMes`, `mapaCarteira`, `indicesCustoCarteira`, `desembolsoCarteira`, `eapCarteira`, `resumoCarteiraDe`, `salvarPonderacao`); funções de projeto renomeadas com sufixo `Projeto` e despachadas por `projetoId == null`; fachada `GI.api.portfolio` (resumo, pesos, salvarPonderacao, projetos, criterios, projeto). `relatorioGerencial(null)` devolve `portfolio: true` e `carteira`.
* **Componentes:** `comum.js` ganhou `escopo`, `listaProjetos`, `codigoProjeto`, `colunaProjeto`, `selosProjeto`, `noProjeto` (modal que escolhe o projeto e reabre a tela com `?acao=`) e `acaoPendente`. `exportar.js` usa "Portfólio de projetos" no contexto (e respeita `?escopo=` do relatório).
* **Telas:** Home com "Carteira de projetos" e modal "Ponderação"; 01 a 08 com coluna Projeto, contexto e cadastro roteado para o projeto; EAP, EAC e Mapa de controle com projeto e pacotes principais; Curva S e KPIs de 02 e 03 com seções da carteira; relatório com folha "Carteira de projetos" e demais folhas consolidadas.
* **Pendente (decisão do usuário):** (1) SPI físico da carteira é ponderado pelos pesos e SPI de custo é EV/PV em R$ (diferem; ambos rotulados); (2) Curva S física da carteira usa calendário mensal da união dos projetos; (3) a folha Carteira do relatório está na data de referência e a de Planejamento no corte do período (mesma regra do avanço por área); (4) ponderação por notas é manual (sem histórico por período; com backend, versionar por data).

## 7.3.6 Módulo 06 Gestão da Qualidade e Configurações > Parâmetros (30/09/2026)

Pedido do usuário: elaborar o módulo de Gestão da Qualidade e Configurações. Regras em `README.md` seção 3 ("06 Gestão da Qualidade" e "Configurações") e 7.4.

* **06, telas:** Painel, Não conformidades, Inspeções e ITP e Auditorias (`_dev/specs_06.py`, `js/pages/qualidade/`); modais e selos em `GI.qld` (`qualidade.js`). Visão por projeto e Portfólio (coluna Projeto, cadastro roteado com `?acao=`).
* **06, api (`GI.api.qualidade`):** painel, rncs, rnc, salvarRnc, iniciarAnalise, registrarAnalise (cria ações na Central), definirAcoes, enviarVerificacao, verificarEficacia (lição opcional), cancelarRnc, atualizarCusto, itps, itp, salvarItp (revisão), aprovarItp, inspecoes, registrarInspecao (reprovação abre RNC), auditorias, auditoria, salvarAuditoria (planejar ou reprogramar), registrarResultado (NC abre RNC). Funções novas: `rncCalculada`, `abrirRncDe`, `itpCalculado`, `inspecaoCalculada`, `auditoriaCalculada`, `painelQualidadeDe`, `serieQualidade`, `qualidadeRg`.
* **06, integrações:** Início com alertas de RNC vencida ou crítica; relatório gerencial com a folha Qualidade (seção `qualidade`); análise do período do 06 (`MODULOS_ANALISE.qualidade`, desvios sem comentário obrigatório); lição em Rascunho no 08; FAT do 04 continua gravando inspeção.
* **06, dados:** `mock-qualidade.js` reescrito (RNC com contenção, responsável, disposição, concessão e eficácia; ITP com pontos; 20 inspeções; auditorias com constatações; análises S38 e agosto); P2 e P3 em `mock-portfolio.js` (RNC-CB-2026-0003 nova, ligada à reprovação da topografia da BS-610-02). Na carteira são 7 RNC em aberto (era 6).
* **Parâmetros:** `modulos/configuracoes/parametros.html` (spec `_dev/specs_config.py`, `js/pages/configuracoes/parametros.js`): grupos por módulo com valores vigentes, edição por grupo com justificativa (nova versão via `GI.api.salvarParametros`), histórico com diferenças entre versões. Parâmetros novos `qualidade` (prazos por severidade, verificação, metas, notificação), validados em `GI.regras.validarParametros`.
* **Correção:** mensagem "1 Existe 1 ação corretiva em aberto" (HSE) corrigida.
* **Pendente (decisão do usuário):** (1) a pauta, as vencidas e as auditorias atrasadas do relatório estão na data de referência (sem fotografia histórica); (2) comentário de desvio não obrigatório no 06; (3) verificação de eficácia exige Gestor (o protótipo loga sempre como Gestor); (4) dossiê da qualidade (data book) e calibração de instrumentos de medição ficam como evolução.

## 7.3.7 Ajustes de 01/10/2026 (apresentação do usuário com 4 pedidos)

* **Siglas:** `js/siglas.js` em todas as páginas (incluído pelo gerador `_dev/telas.py`, lista I18N, e à mão em `index.html`, `relatorio.html` e `styleguide.html`). Dica ao parar o mouse, some ao tirar; toque no celular. Glossário bilíngue em `LISTA` (sigla PT, sigla EN, nome e descrição nos dois idiomas) mais padrões S/W semana ISO, P1 a P5, I1 a I5, N1 a N5. Sem alterar o DOM (caretRangeFromPoint) e sublinhado pela Highlight API. Não cobre canvas de gráficos nem opções de select.
* **Cards:** `esperado: { rotulo, valor }` em `GI.util.kpi` (também `GI.util.kpiEsperado`, Home e `kpi()` do relatório); todas as telas, Home e relatório preenchidas (rótulos Previsto, Meta, Linha de base, Orçado, Limite, Esperado, Mês anterior, Referência); exportação Excel ganha coluna Referência e o PDF a linha. Verificação automática: `/tmp` não persiste; o script de conferência lista `.kpi` sem `.kpi__esperado` (refazer com Playwright se preciso).
* **Contingência (03):** tela `contingencia.html` (spec em `specs_03.py`, `js/pages/financeiro/contingencia.js`, `GI.api.financeiro.contingencia`); reservas com `gerencialCentavos`, `constituidaEm` e `base`; fonte de SM "Reserva gerencial" (só Comitê); parâmetros `financeiro.contingencia` (tolerância 10 p.p., cobertura mínima 100%); faixa "Reservas" no Mapa de controle. Números: projeto 1 com saldo R$ 1,6 mi (20% consumido, limite 71,8%), R$ 480 mil em SMs em análise, cobertura 47% da exposição (alerta), gerencial R$ 900 mil; carteira com saldo R$ 2,69 mi e cobertura 55%.
* **Remanejamento por SM:** tipo de SM "Remanejamento de orçamento" com `remanejamentos` [{origem, destino, valorCentavos, novoItem?}]; `GI.api.financeiro.remanejar` e o item novo por remanejamento criam a SM (`solicitarRemanejamento`); a aprovação aplica (`aplicarRemanejamentosSm`, grava `smRef`); saldo livre desconta o reservado em SMs abertas (`saldoLivreEac`); análise exige custo zero; alçada pelo valor remanejado; `novaRevisao` exige SM aprovada pendente (a importação perdeu a opção sem SM). Mock: SM-TN-2026-0009 e 0010 (remanejamentos antigos, agora com SM) e 0011 (R$ 250 mil em análise).
* **Pendências concluídas (01/10/2026, pedido "conclua as pendências"):** (1) edição cadastral do item da EAC exige justificativa e grava `historicoCadastro` (`GI.api.financeiro.editarItem`); (2) SM "Liberação de reserva" (contingência ou gerencial, Comitê) com movimento Liberação no extrato e saldo reduzido; (3) histograma de mão de obra previsto (`MOCK.histogramaMaoDeObra`, `GI.api.hse.histograma` e `hhtPrevisto`) dá o Previsto dos cards de HHT e efetivo (07 HHT e relatório); metas `hse.metas` (observações 40 e desvios 12 por 10 mil HHT) nos cards de Inspeções e observações, Painel HSE e relatório; Curva S física: card Previsto acumulado com referência "100% em <término LB>"; (4) `produtividade.spiFaixas` [0,85; 0,95] e `atrasoInicioFaixasMin` [15; 30] nos parâmetros (tela, validação, api e Produtividade). Restam como referência sem meta natural: clima (Esperado 0) e rodadas de observação (Referência: jornadas registradas).

## 7.4 Próximo passo: etapa 7, validação final

Etapa 5 e 6 concluídas. Próximo: validação final (360, 768 e 1440 px; cores; pílulas; links; PT e EN em todas as telas e modais; impressão do relatório), revisão de pendências registradas nas seções 7.3.3 a 7.3.6 e decisão do usuário sobre a fase com backend (README seção 7).

## 8. Pontos de atenção

* SheetJS 0.18.5 tem CVEs de leitura; trocar pela 0.20.3 antes de produção (README seção 5).
* Validação feita em Chromium; Firefox e Edge não foram testados.
* A escala de risco atual diverge da escala da ArcelorMittal (ver `aderencia-cipm-tartan-book.md`); a escala CIPM já existe como opção nos parâmetros e o 05 funciona com as duas (nomes e quantidade de faixas vêm dos parâmetros).
* No 05, a matriz usa células como links (não botões) para seguir a regra das pílulas; a tabela do registro cabe em 1440px sem rolagem com o número do risco como link da ficha.
* Em inglês, a EAC aparece como CBS (Cost Breakdown Structure) e o rótulo do botão de idioma é "IN", como o usuário pediu. No 04, LB aparece como BL (baseline).
* O MAS usa células em pílula (regra dos botões) e rola na horizontal dentro do contêiner, com a coluna do pacote fixa; em 360px a página não rola.
* No 07, "Status: todas" e "Ocorrência registrada." são entradas próprias no `en.js` (string composta e string estática coincidente com um padrão de outra tela); ao criar nova tela, checar sempre com `_dev/coleta_en.py` e revisão visual, o automático tem falsos positivos e negativos.
* No 08, datas dentro de frases montadas pela api (próxima etapa, histórico, mensagens) saem em dd/mm/aaaa também em inglês, como nos módulos 05 e 07; datas das telas seguem o idioma.
* Na Produtividade, o protótipo loga sempre como Leonardo (Gestor): item criado por ele não pode ser aprovado por ele (segregação); para demonstrar a aprovação, use o QTD-06 do mock.
* Relatório gerencial: o SPI do semanal (avanço interpolado no fim da semana) pode diferir do SPI mensal da Home e da tela de KPIs (ponto do mês); é regra documentada, não erro.
* Relatório gerencial: a EAC por CPI (fim da linha de tendência) pode diferir da projeção no término da EAC; é intencional (estatística x bottom-up) e deve ser comentada na análise.
* O acervo de lições mostra no máximo 24 cartões e o botão "Mostrar mais"; com backend, paginar no servidor.
* `_dev/coleta_en.py` só reabre `.modal:not([hidden])` depois de clicar um botão; um controle `segmented` (como Bird/Heinrich no Painel HSE) troca conteúdo na própria página sem abrir modal, então o clique acontece mas o texto novo não é coletado. Alternar manualmente esses controles com `_dev/t_pag.py` (`click=` no botão do segmentado) e conferir com `eval=` antes de dar como concluída a tradução de uma tela com esse tipo de controle.

## 9. Prompt para abrir o novo chat

> Vamos continuar o protótipo Gestão Integrada AMT. Leia primeiro `HANDOVER.md` e `README.md` na pasta `C:\Users\leonardo.gomes\Documents\Sistema Gestão\Sistema\` e o documento `claude/prototipo-gi-status.md` do projeto. Siga todas as regras do handover. Próxima tarefa: etapa 7, validação final do protótipo (360, 768 e 1440 nos dois escopos, PT e IN, modais, exportações e relatório), corrigindo o que aparecer e gravando na pasta ao final.
