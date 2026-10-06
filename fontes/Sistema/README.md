# Gestão Integrada AMT (Timenow): protótipo navegável

Protótipo de apresentação do sistema **Gestão Integrada AMT**, bilíngue (português e inglês), somente HTML/CSS/JS estático, com dados fictícios. Backend, banco de dados, hub e servidor ficam para uma fase posterior; por isso toda leitura de dados passa por uma fachada (`js/services/api.js`) que hoje lê o mock (`data/mock-*.js`) e amanhã chamará a API, sem reescrever as telas.

| Etapa | Situação |
|---|---|
| 1. Fontes lidas, paleta e inventário registrados | Concluída |
| 2. Design system e `styleguide.html` | Concluída |
| 3. Aprovação da paleta aplicada e do styleguide | Concluída (aprovada em 25/09/2026; escopo ampliado em 24 e 25/09/2026: módulo 03 Gestão Financeira e exceção do vermelho, Punch list no 02, Governança, módulos 04 Suprimentos e 07 HSE, administração contratual no 03 e renumeração final dos módulos) |
| 4. Layout (header, sidebar, gaveta), Home, camada de dados (mock + `api.js`) e páginas-base de todas as telas | Concluída |
| 5. Telas completas dos módulos 01 a 08 e Configurações | Concluída em 30/09/2026: 01 Central de Ações, 02 Planejamento, 03 Gestão Financeira, 04 Suprimentos (com o MAS, Mapa de Suprimentos), 05 Gestão de Riscos (26/09/2026), 07 HSE (27/09/2026), 08 Governança (28/09/2026) e as telas Produtividade, EAP e Relato do período no 02 (28/09/2026) concluídos; em 30/09/2026 o sistema passou a **gestão de portfólio** (3 projetos, visão por projeto e Portfólio em todos os módulos, ponderação configurável, Curva S física e financeira da carteira e relatório gerencial do portfólio; ver seção 3); em 28/09/2026 a Home ganhou o **relatório gerencial** semanal e mensal, com **análise do período** por módulo (02, 03, 04, 05, 06 e 07), indicadores de produtividade, linha de tendência na Curva S financeira e folha HSE; 06 Gestão da Qualidade e Configurações > Parâmetros concluídos em 30/09/2026; em 25/09/2026 entraram o novo padrão de página (sem título no topo, abas e ações na mesma linha), o nome Gestão Integrada AMT e o seletor de idioma PT/IN |
| 6. Upload e exportação Excel/PDF em todas as tabelas e painéis | Entregue em todos os módulos (01 a 08), Configurações, Home e relatório gerencial |
| 7. Validação final (360, 768 e 1440px; cores; pílulas; links) | Não iniciada |

---

## 1. Como abrir

* Abra `index.html` com duplo clique. Funciona direto do disco (`file://`), sem servidor e sem internet. O `styleguide.html` fica no rodapé do menu.
* Todas as telas do menu já existem e navegam; as que ainda não foram construídas mostram "Tela em construção" com o conteúdo previsto (etapa 5).
* **Idioma:** o botão **PT | IN** no topo, ao lado do nome do usuário, alterna entre português e inglês (a escolha fica salva no navegador e a página recarrega no idioma novo). Ver 6.2.
* **Data de referência fixa: 25/09/2026** (`data/mock-config.js`). Status, atrasos, prazos e "dias sem acidente" são calculados nessa data, para que o protótipo mostre sempre o mesmo cenário.
* O que for gravado nas telas fica salvo na sessão do navegador (`sessionStorage`): sobrevive à navegação e ao recarregar, e some ao fechar a aba. Quando há alterações, o rodapé do menu mostra **Restaurar dados de demonstração**, que volta ao cenário fictício original. Além disso, o navegador guarda só a preferência de menu recolhido e o idioma.
* **Relatório gerencial:** no Início, botão **Relatório gerencial** (modal com tipo, período e seções) abre `relatorio.html` em nova aba, com folhas A4 na horizontal; **Imprimir / PDF** usa a impressão do navegador (Salvar como PDF). Ver "Relatório gerencial" na seção 3.
* Nenhuma tela usa `fetch()` para arquivos locais: dados mock ficam em arquivos `.js` (`window.MOCK = {...}`).
* Fontes (Montserrat e Roboto) estão embutidas em `css/fonts.css` (data URI), para que carreguem em qualquer navegador via `file://`, inclusive nas páginas de `modulos/`.

---

## 2. Paleta oficial extraída

Fonte: `Cores Padrões - MODELO BI - Rev.00.pdf` (2 páginas). A transcrição `Programação semanal\Cores_Padroes_MODELO_BI_Rev00.md` foi conferida contra o PDF; **o PDF prevalece** (divergências em 2.5).

### 2.1 Cores institucionais

| Nome (PDF) | Hex | RGB / CMYK (PDF) | Papel no PDF (pág. 2) | Token CSS |
|---|---|---|---|---|
| Verde Timenow | `#006357` | RGB 0 99 87 · CMYK 88 35 63 30 | Principais, Títulos, Fundos | `--brand-verde` |
| Cinza Timenow | `#54605e` | RGB 84 96 94 · CMYK 64 44 49 36 | Texto | `--brand-cinza` |
| Detalhe verde-água | `#00a793` | não informado | Detalhes | `--brand-detalhe` |
| Laranja | `#eb6100` | não informado | Detalhes | `--brand-laranja` |
| Branco | `#ffffff` | não informado | Institucional | `--brand-branco` |
| Preto | `#000000` | não informado | Institucional | `--brand-preto` |

### 2.2 Escalas tonais (PDF, pág. 1)

Seis famílias com nove tons cada, do mais claro (1) ao mais escuro (9). O tom 5 é a cor base da família.

| Família | 1 | 2 | 3 | 4 | **5 (base)** | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Verde-água (`--teal-N`) | `#ccede9` | `#99dcd4` | `#66cabe` | `#33b9a9` | **`#00a793`** | `#008676` | `#006458` | `#00433b` | `#00211d` |
| Roxo (`--roxo-N`) | `#e3d7ef` | `#c7afdf` | `#ac88d0` | `#9060c0` | **`#7438b0`** | `#5d2d8d` | `#46226a` | `#2e1646` | `#170b23` |
| Laranja (`--laranja-N`) | `#fbdfcc` | `#f7c099` | `#f3a066` | `#ef8133` | **`#eb6100`** | `#bc4e00` | `#8d3a00` | `#5e2700` | `#2f1300` |
| Azul-acinzentado (`--azul-N`) | `#e0e9ec` | `#c1d2d9` | `#a2bcc6` | `#83a5b3` | **`#648fa0`** | `#507280` | `#3c5660` | `#283940` | `#141d20` |
| Areia (`--areia-N`) | `#efebe3` | `#dfd6c8` | `#d0c2ac` | `#c0ad91` | **`#b09975`** | `#8d7a5e` | `#6a5c46` | `#463d2f` | `#231f17` |
| Cinza (`--cinza-N`) | `#eaeaea` | `#c4c6c6` | `#959b9a` | `#6b7775` | **`#54605e`** | `#4a5452` | `#414948` | `#343a39` | `#1f2322` |

### 2.3 Paletas auxiliares do PDF (registradas, não usadas)

O PDF traz duas amostras "2. Veja as cores" ligadas à marca **Time Connect** (outro produto). Ficam registradas para rastreabilidade, mas **não entram** no design system do Gestão Integrada AMT.

* Time Connect: `#3b464d`, `#08a494`, `#cdd1d2`, `#80888c`, `#949ca4`
* Amostra de interface Time Connect: `#cceceb`, `#09a797`, `#74d0d3`, `#c7d3a0`, `#9ed4cf`

### 2.4 Tipografia

| Uso | Fonte | Pesos embutidos |
|---|---|---|
| Títulos | Montserrat | 600, 700 |
| Texto | Roboto | 400, 500, 700 |

### 2.5 Divergências entre a transcrição `.md` e o PDF

| # | Transcrição `.md` | PDF (prevalece) | Tratamento adotado |
|---|---|---|---|
| D1 | `#eb6100` com papel "Destaques" | Pág. 2 agrupa `#00a793` **e** `#eb6100` sob "Detalhes"; não existe o papel "Destaques" | Ambos tratados como cores de detalhe. O uso do laranja como destaque/alerta (CTA, atraso, criticidade) é **decisão de design deste protótipo**, submetida à aprovação |
| D2 | Omite as 6 escalas tonais (54 tons) | Pág. 1 traz as escalas completas | Escalas incorporadas como tokens primitivos (2.2) |
| D3 | Omite RGB/CMYK | Verde e Cinza Timenow têm RGB e CMYK | Registrados em 2.1 |
| D4 | Lista `#00a793`, `#648fa0`, `#7438b0`, `#eb6100`, `#b09975` só como "complementares observadas" | São as bases (tom 5) das escalas | Tratadas como bases de família |
| D5 | Não cita as amostras Time Connect | Pág. 1 traz duas amostras auxiliares | Registradas em 2.3, fora do sistema |
| D6 | "Montserrat" | Grafado "Montsserat" (erro de digitação no PDF) | Adotado Montserrat |

**Observação sobre os logos:** os arquivos de `Sistema Gestão\Logos\` usam o verde `#376458` (medido nos pixels), que não consta da paleta. Os logos são usados **como estão**, sem recolorir; apenas foram recortadas as margens transparentes e reduzida a resolução para uso web (`assets/logos/`).

### 2.6 Regras de aplicação (contraste AA)

Medições de contraste (WCAG 2.1) que determinaram o uso de cada cor:

| Combinação | Contraste | Resultado | Decisão |
|---|---|---|---|
| Branco sobre Verde `#006357` | 7,19:1 | AA | Botão primário, sidebar, cabeçalhos de destaque |
| Cinza `#54605e` sobre branco | 6,54:1 | AA | Texto padrão |
| Branco sobre Laranja `#eb6100` | 3,36:1 | **Reprova** texto normal | Laranja base só em elementos **sem texto** (barras, indicadores, séries de gráfico, faixa de título). Botão de destaque usa `--laranja-6` `#bc4e00` (4,97:1) |
| Branco sobre Detalhe `#00a793` | 3,02:1 | **Reprova** texto normal | Detalhe só em bordas, foco, ícones e gráficos. Texto verde-água usa `--teal-7` `#006458` (7,09:1) |
| `#6b7775` sobre fundo de página | 4,26:1 | Reprova | Texto secundário usa `--text-muted` (derivado: 4,96:1 sobre o fundo e 5,45:1 sobre branco) |

**Cores derivadas** (misturas de tons oficiais com branco, declaradas só em `css/tokens.css`): fundo de página, fundos sutis de tabela e seleção, bordas e texto secundário. A paleta **não tem vermelho nem amarelo**; os estados gerais usam as famílias oficiais (a única exceção, o vermelho financeiro, está em 2.7):

| Estado | Família | Exemplo de uso |
|---|---|---|
| Sucesso | Verde-água | Concluída, Aprovado, Validada |
| Alerta / perigo | Laranja (tons 6 e 7) | Atrasada, Crítico, Revisão vencida |
| Atenção | Areia | Pendente, Em análise |
| Informação | Azul-acinzentado | Em andamento, Monitorado |
| Tipo "Informação" (ata) | Roxo | Mantém o roxo do sistema atual |
| Neutro | Cinza | Rascunho, Encerrado |

Severidade de risco (matriz 5x5): Baixo `--teal-2`, Moderado `--laranja-2`, Alto `--laranja-5`, Crítico `--laranja-7`.

**Gráficos** (conferidos com validador de paleta: faixa de luminosidade, croma, separação para daltonismo e contraste):

* Série categórica em ordem fixa: `--chart-1` teal 6, `--chart-2` laranja 5, `--chart-3` roxo 5 (aprovadas em todos os critérios); `--chart-4` azul 6 e `--chart-outros` cinza 3. A partir da 5ª série, agrupar em "Outros".
* Curva S: Baseline azul 5 (tracejada), Real Verde Timenow (contínua, com área), Tendência laranja 5 (tracejada).
* Limitação da paleta oficial: azul 6 e Verde Timenow ficam abaixo do piso de croma recomendado; compensado por legenda sempre visível, tracejado e rótulos.
* Curva S financeira: Planejado azul 5 (tracejada), Comprometido roxo 5, Realizado Verde Timenow (contínua, com área). Aprovada em separação para daltonismo e visão normal.
* Cascata de contratos: totais (valor original, valor atual, saldo a faturar) Verde Timenow; acréscimos (aditivos) laranja 5; reduções (medido) roxo 5.
* Cronograma de desembolso: Previsto azul 5, Realizado Verde Timenow.

### 2.7 Exceção aprovada: vermelho financeiro (E1)

Decisão do usuário em 24/09/2026: o mapa de controle da EAC mostra **sobrecusto em vermelho e economia em verde**. Como a paleta oficial não tem vermelho, foi criada uma escala **fora da paleta**, derivada da escala Laranja oficial (mesma luminosidade e croma de cada tom, só o matiz girado para o vermelho, OKLCH 27°), para manter a harmonia com a marca.

| Token | 1 | 2 | 3 | 4 | **5 (base)** | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Vermelho (`--vermelho-N`) | `#ffdcd7` | `#feb9b0` | `#fb968b` | `#f7756a` | **`#ef574e`** | `#c0463e` | `#90332d` | `#61221d` | `#310f0d` |

Regras de uso:

* **Somente** no domínio financeiro, para desvio desfavorável de custo (sobrecusto). Atraso, criticidade de risco e demais alertas continuam em laranja.
* Economia usa a escala Verde-água oficial; desvio neutro usa Cinza.
* Mapa de calor do desvio (projeção no término x orçado atual):

| Faixa de desvio | Fundo | Texto | Contraste |
|---|---|---|---|
| Sobrecusto acima de 10% | vermelho 6 | branco | 5,02:1 |
| Sobrecusto de 5% a 10% | vermelho 3 | cinza 9 | 7,44:1 |
| Sobrecusto de 1% a 5% | vermelho 1 | vermelho 7 | 6,11:1 |
| Neutro (menos de 1% em módulo) | cinza 1 | cinza 7 | 7,69:1 |
| Economia de 1% a 5% | teal 1 | teal 8 | 9,03:1 |
| Economia de 5% a 10% | teal 3 | cinza 9 | 8,14:1 |
| Economia acima de 10% | teal 7 | branco | 7,09:1 |

Cor nunca é o único sinal: a célula também mostra o valor com sinal (+/−) e o ícone de seta.

---

## 3. Inventário de telas por módulo

Legenda de situação: **Replicada** (conteúdo e fluxo vindos de sistema/protótipo existente, visual reescrito), **Nova** (definida pelo escopo, sem tela de referência), **Proposta** (desenho mínimo sugerido, a validar).

### Home

| Tela | Arquivo | Conteúdo | Situação |
|---|---|---|---|
| Home | `index.html` | Contexto do projeto em etiquetas na barra da página (projeto, data de referência, orçamento, término), com exportação à direita; um indicador-chave por módulo, clicável (ações atrasadas, SPI, CPI, pedidos críticos, riscos críticos, RNC abertas, dias sem afastamento, mudanças aguardando comitê); pontos de atenção calculados (ações mais atrasadas, pedidos com folga negativa, sistemas bloqueados por item A, revisão de risco vencida, claim fora do prazo, HiPo no mês); cards dos 8 módulos | Nova |
| Relatório gerencial | modal em `index.html` e página `relatorio.html` | Botão **Relatório gerencial** na barra do Início: modal com Tipo (Semanal ou Mensal), Período (padrão: semana anterior; no mensal, mês anterior), situação do relato do período e da análise do período de cada módulo (registrada, pendente ou com desvio sem comentário), com link para registrar, Conteúdo (Planejamento em 2 páginas, Financeiro, Suprimentos, Riscos, Qualidade e HSE) e Formato; o relatório abre em nova aba em folhas A4 na horizontal (uma por seção), com Imprimir / PDF, Excel e Alterar período | Nova (28/09/2026) |
| Styleguide | `styleguide.html` | Paleta aplicada e todos os componentes | Nova |

**Relatório gerencial: regras (boas práticas de relatório de desempenho, PMBOK e ISO 21502)**

* **Período:** semanal = semana ISO (segunda a domingo, `2026-S38`); mensal = mês civil (`2026-08`). A lista vai do início do projeto até o período corrente; o período em andamento sai **parcial** (dados até a data de referência) e o relatório avisa. Padrão do modal: semana anterior (no mensal, mês anterior).
* **Corte** = fim do período, limitado à data de referência. Cálculo só na api (`GI.api.relatorioGerencial`).
* **Folhas (A4 horizontal, uma por seção):**
  1. **Planejamento · Curva S, KPIs e produtividade:** avanço previsto e real acumulados, SPI físico (e do período anterior), avanço no período (real x previsto, p.p.), término pela tendência x linha de base, desvio acumulado; **produtividade** (02 Produtividade, janela de 4 semanas terminando na semana do corte): SPI de quantidades, fator de produtividade (FP), aderência semanal, pessoas trabalhando, utilização da jornada e HH paralisadas, com as metas dos parâmetros e as empresas em alerta; Curva S física mensal (real até o corte e tendência só quando o corte está no mês corrente); barras do avanço por período (8 semanas ou 6 meses); avanço por área.
  2. **Planejamento · Análise e relato do período:** análise do período (texto e tabela de desvios negativos com o comentário de cada um) ao lado das atividades do período e do próximo período; abaixo, os pontos de atenção com o risco atrelado (ameaça ou oportunidade). Sem relato ou sem análise, a folha mostra o aviso e o link para registrar.
  3. **Financeiro:** BAC, realizado acumulado e do mês, valor agregado (EV e PV), CPI e SPI de custo, projeção no término e VAC (sobrecusto em vermelho, exceção E1), contingência consumida; Curva S financeira com a **linha de tendência** (ver abaixo) e valor agregado mês a mês (6 meses) à esquerda; análise do período e EAC por pacote (nível 1, R$ mil, mapa de calor) à direita.
  4. **Suprimentos:** aderência ao plano de compras, pacotes adjudicados, saving, OTD, pedidos críticos e emitidos até o corte; curva de contratação e pedidos críticos (até 4) ao lado da análise do período; marcos realizados no período e adjudicações e entregas previstas no horizonte (até 5 cada; semanal: 4 semanas seguintes, como lookahead; mensal: mês seguinte).
  5. **Riscos:** ativos (ameaças e oportunidades), faixa mais alta e segunda faixa, exposição (VME), revisão vencida, identificados e encerrados no período; matriz P x I residual (A = ameaças, O = oportunidades) e exposição mensal das ameaças; análise do período e principais riscos (até 5, maior score residual).
  6. **Qualidade:** RNC em aberto no corte (críticas e vencidas), abertas e encerradas no período, aprovação em inspeções e conformidade em auditorias do período x metas, custo da não qualidade acumulado, disciplina com mais RNC; RNC por mês (6 meses até o corte) e inspeções reprovadas no período; análise do período e pauta de tratamento (posição na data de referência).
  7. **HSE:** TF, TRIF, TG e HiPo do mês (com o acumulado no rodapé), dias sem afastamento na data de corte, HHT do mês (no semanal, ocorrências da semana); pirâmide de segurança mês x acumulado (referência Bird ou Heinrich dos parâmetros); análise do período; evolução mensal de TF e TRIF; indicadores proativos do acumulado (DDS, inspeções, observações, relato de quase acidentes, recomendações fechadas, incidentes ambientais).
* **Análise do período (todas as folhas):** texto executivo e analítico do módulo (panorama, desempenho dos períodos anteriores, causas e tendência) e a tabela **Desvio negativo x Comentário**. Desvio sem comentário aparece como "Comentário pendente" em laranja; sem análise registrada, a folha avisa e traz o link para o modal do módulo.
* **Linha de tendência da Curva S financeira:** parte do realizado no mês do relatório e chega à EAC por desempenho (EAC = BAC ÷ CPI, isto é, AC + (BAC - EV) ÷ CPI), distribuindo o custo restante pelo perfil do planejado. É calculada no próprio mês, sem usar dados posteriores ao período, e pode diferir da projeção no término da EAC (estimativa da equipe, bottom-up): a diferença é informação para a análise.
* **Granularidade das fontes:** a Curva S física é mensal: no mensal o relatório usa o ponto do mês (igual às telas e à Home); no semanal, interpola linearmente dentro do mês até o fim da semana (o real do mês corrente vale na data de referência). O custo é apurado por mês: no mensal, o próprio mês; no semanal, o **último mês fechado** até o fim da semana. Suprimentos usa as datas dos eventos. O registro de riscos não guarda fotografia por data: KPIs, matriz e principais riscos saem na data de referência (a folha informa); identificados e encerrados no período e a evolução mensal saem do histórico. Avanço por área e EAC por pacote também são posição atual.
* **Impressão:** `@page` A4 landscape sem margem (a margem está dentro da folha), cores de fundo preservadas, uma folha por página; se o texto passar da altura útil, a fonte da folha é reduzida até caber (mínimo 6,4 pt). **Excel:** indicadores e tabelas de todas as folhas, mais as abas Análises do período e Desvios negativos e comentários.

### Gestão de portfólio (decisão de 30/09/2026, substitui a de projeto único de 28/09/2026)

O sistema controla uma **carteira de 3 projetos** e todo módulo tem duas visões: **por projeto** e **Portfólio** (todos os projetos). Projetos: TN-2026-014 Construção de uma nova fábrica (R$ 44,6 mi, jan/26 a mar/27), TN-2026-021 Construção de uma nova caldeira de biomassa (R$ 18,2 mi, mar/26 a jun/27) e TN-2026-027 Construção de uma nova torre de resfriamento (R$ 7,4 mi, jun/26 a fev/27), em fases diferentes.

* **Escopo global:** seletor no cabeçalho (desktop e tablet) e no menu lateral (celular): "Portfólio (3 projetos)" ou um projeto. O escopo vai na URL (`?projeto=portfolio` ou `?projeto=<id>`) e fica gravado no navegador (`gi.escopo`); sem nada gravado, abre no Portfólio. Telas de detalhe (ata, ficha do risco, contrato, SM) voltam para a lista do módulo ao trocar o escopo. `GI.api.projetoAtualId()` devolve `null` no Portfólio.
* **Ponderação da carteira (relevância de cada projeto):** composta e configurável em `parametros.portfolio.criterios` (soma 100): valor financeiro pelo orçamento vigente da EAC (60%), criticidade estratégica (25%) e complexidade e exposição a risco (15%), com notas de 1 a 5 por projeto. Peso do projeto = soma dos critérios normalizados, fechado em 100 pelo maior resto (`GI.regras.ponderarPortfolio`). Pesos atuais: fábrica 55,36%, caldeira 29,34%, torre 15,30%. Edição na Home (botão **Ponderação**, Gestor ou Admin, com prévia e justificativa; grava nova versão dos parâmetros).
* **Curva S física do portfólio:** média ponderada pelos pesos, no calendário da união dos projetos (antes do início o projeto vale 0; depois do término, 100 na linha de base e o último real no realizado). **Curva S financeira do portfólio:** soma em R$ de planejado, comprometido, realizado e projeção. Valor agregado da carteira = soma de PV, EV e AC dos projetos (o SPI de custo pode diferir do SPI físico ponderado; os dois são mostrados com o nome).
* **EAP e EAC na visão carteira:** linha 0 = portfólio; nível 1 = projeto (código 1, 2, 3 e "código · nome"); nível 2 = pacotes principais do projeto (nível 1 da EAP ou EAC do projeto, com o código do projeto). Somente leitura: revisões, remanejamentos, desdobramentos e cadastro acontecem no projeto.
* **Cadastro no Portfólio:** todo registro pertence a um projeto. Os botões de inclusão abrem a escolha do projeto e reabrem a mesma tela no projeto com `?acao=` (a tela abre o formulário). Edição de linha usa o projeto do próprio registro.
* **Listas consolidadas:** coluna **Projeto** nas tabelas (ações, atas, relatos, punch, pacotes, processos, pedidos, riscos, ocorrências, HHT, inspeções, APR/HAZOP, mudanças) e nas exportações; subtítulo "Portfólio de projetos".
* **Home no Portfólio:** indicadores consolidados, tabela **Carteira de projetos** (peso, BAC, avanço previsto e real, SPI, CPI, projeção e VAC, término, riscos críticos, pedidos críticos, ações atrasadas, situação e Abrir) e pontos de atenção com o código do projeto.
* **Relatório gerencial:** o modal pede **Relatório de** (Portfólio ou projeto) e mostra a situação dos relatos por projeto. `relatorio.html?escopo=portfolio|<id>` (usa `escopo=` para não trocar o escopo das telas). No projeto, o formato é o mesmo. No Portfólio entra a folha **Carteira de projetos** (KPIs da carteira, tabela por projeto, Curva S física ponderada e critérios de ponderação); Planejamento mostra avanço por projeto e, na segunda folha, a análise da carteira, a situação dos relatos e os pontos de atenção de todos os projetos; Financeiro traz a EAC por projeto; Suprimentos, Riscos e HSE consolidados com o código do projeto.
* **Análise do período:** existe por projeto e para o Portfólio (registro com `projetoId` nulo), escrita pelo PMO sobre os números consolidados.

### Configurações

| Tela | Arquivo | Conteúdo | Situação |
|---|---|---|---|
| Parâmetros | `modulos/configuracoes/parametros.html` | Versão vigente (versão, vigência, autor, justificativa); grupos por módulo (Avaliação de contratadas, Financeiro, Suprimentos, Riscos, Qualidade, HSE, Planejamento, Governança, Portfólio) com os valores vigentes, busca e filtro por módulo; **Editar** por grupo em modal com justificativa obrigatória (gravação cria nova versão; troca de escala de riscos pede confirmação); **Histórico de versões** com as alterações (antes e depois) de cada versão; exportação Excel e PDF. Visível só para Gestor e Admin; outros papéis só consultam | Nova (30/09/2026) |

### 01 Central de Ações

Fonte: `Sistema Gestão Integrada\Sistema\Gestão Integrada\app\` (`central.js`, `atas.js`, `status.js`, `pdf.js`) e `PARIDADE_ATA_E_CONFIGURACOES.md`.

| Tela | Arquivo | Campos e fluxos replicados | Situação |
|---|---|---|---|
| Ações (lista e kanban) | `modulos/central-acoes/acoes.html` | KPIs clicáveis (Em dia, Atrasadas, Concluídas, Total); filtros em modal (Busca, Origem, Status, Responsável) com chips; tabela Origem, Ata, Item, Assunto/Descrição, Responsável, Prevista, Replanejada, Status; Gerar PDF; Enviar follow-up. Só itens do tipo Ação (D15) | Replicada; visão **kanban** por status é nova |
| Dashboards e KPIs | `modulos/central-acoes/dashboard.html` | Indicadores do motor de status único (Concluída, Atrasada, Em andamento) por origem, responsável e projeto | Nova (a partir dos KPIs existentes) |
| Atas: lista | `modulos/central-acoes/atas.html` | Localizador das atas do projeto; só a revisão mais recente de cada linhagem; colunas Número, Rev, Data, Assunto, Empresa principal, Tipo de reunião | Replicada |
| Atas: nova ata | modal em `atas.html` | "Gerar nova ata": Data, Tipo de reunião, Diretoria, Unidade, Elaborado por, Assunto (150 caracteres com contador), todos obrigatórios; Empresas executoras opcional; numeração pelo padrão do projeto (ex.: `TN-2026-0000`) | Replicada |
| Atas: visualização | `modulos/central-acoes/ata.html` | Faixa da ata (número, revisão, contexto, ações); abas Dados da Reunião, Lista de Presença, Anotações e Ações; itens por Grupo/Área com numeração 1 / 1.1; status calculado; KPIs no rodapé | Replicada |
| Modais da ata | em `ata.html` | Gerar nova revisão (data), Empresas executoras (Principal), Buscar convidado, Retirar participante, Colunas da tabela, Nova/editar anotação/ação (Tipo, Grupo/Área, Assunto, Descrição, Solicitante, Responsável, Prevista, Replanejada, Conclusão), Registrar replanejamento (justificativa obrigatória), Justificativas, Histórico da ata | Replicada |

Origens de ação na Central: **Ata, Punch list, Contrato, Suprimentos, Risco, RNC, HSE, Mudança, Lição e Produtividade**. A origem "Pendências" do sistema atual passa a se chamar **Punch list** (decisão de 25/09/2026).

Regras de negócio preservadas: status sempre calculado (Informação; Concluída com data de conclusão; Atrasada se Replanejada ou Prevista < hoje; senão Em andamento); filtro "Em andamento" inclui atrasadas; retirada de empresa/convidado bloqueada com ação em aberto (§11.5).

### 02 Planejamento

| Tela | Arquivo | Conteúdo | Fonte | Situação |
|---|---|---|---|---|
| EAP | `modulos/planejamento/eap.html` | Árvore área, subárea e pacote (pacote de trabalho ou de planejamento) com peso (% do projeto), critério de medição, datas da linha de base, previsto x real e desvio; registro de avanço por pacote; dicionário da EAP (entregável, critério de aceitação, empresa, responsável, item da EAC); revisões (Rev 0 = linha de base) a partir de SM aprovada com impacto em escopo; desdobramento de pacote de planejamento (ondas sucessivas); importação de pacotes e do avanço; conciliação com a Curva S | Pedido de 28/09/2026 (espelho físico da EAC do 03) e boas práticas de EAP (PMBOK, 100%, dicionário, pacotes de trabalho e de planejamento) | Nova (antes da Curva S) |
| Curva S | `modulos/planejamento/curva-s.html` | Linhas Baseline, Real e Tendência/Forecast; eixo de % acumulado por período; tabela período a período | Escopo do prompt | Nova |
| KPIs | `modulos/planejamento/kpis.html` | SPI, avanço físico previsto x real, desvio (p.p.) por período e por área | Escopo do prompt | Nova |
| Relato do período | `modulos/planejamento/relato.html` | KPIs (semana anterior e mês anterior registrados ou pendentes, pontos de atenção do último semanal, relatos registrados); filtro Todos, Semanais, Mensais e busca; tabela de relatos; modais Novo, Editar (atividades do período, atividades do próximo período e pontos de atenção repetíveis, cada um com o risco atrelado: ameaça ou oportunidade e descrição), Ver, Copiar do período anterior e Excluir (Gestor) | Pedido do usuário (28/09/2026) e boas práticas de relatório de desempenho | Nova |
| 6WLA | `modulos/planejamento/6wla.html` | Grade de atividades por semana (6 semanas), restrições (tipo, situação, data de remoção) e responsáveis | Escopo do prompt | Nova |
| Programação Semanal | `modulos/planejamento/programacao-semanal.html` | Lista com grade diária 2ª a Sáb (Previsto, Dia, Noite), Situação (Em elaboração, Validada, Publicada) e Aprovação do Realizado (Pendente, Aprovado); modal Atividade (Item, Semana, ID Exclusiva, Atividade, Local, Empresa, Fiscal, Encarregado, Prod. Prevista, Unidade, Observações, Comentários; Total, PPC e Aderência automáticos); importação Excel em 5 passos; indicadores PPC por área e Aderência por contratada | `Programação semanal\` (protótipo, prompt e PDF McCain) | Replicada (Login, Cadastros, Usuários e Janela/Bloqueios ficam fora deste escopo) |
| Produtividade | `modulos/planejamento/produtividade.html` | Filtros globais Empresa e Semana de corte; abas Quantidades (plano da LB por empresa distribuído por semana, apontamento semanal, aprovação e revisão da LB com SM), Horas efetivas (capacidade produtiva por turno, amostragem do trabalho e paralisações de efetivo e de máquinas) e KPIs de performance (geral e por empresa, com plano de ação na Central) | Pedido de 28/09/2026 (painéis de fiscalização de campo do cliente como referência visual) e boas práticas de controle de produtividade | Nova (entre Programação Semanal e Punch list) |
| Punch list | `modulos/planejamento/punch-list.html` | Abas Lista e Painel; modais Novo item, Fechamento com verificação, Filtros e Importação Excel (ver detalhamento abaixo) | Boas práticas de completação e comissionamento | Nova (substitui o módulo "Pendências" do sistema atual) |

**Análise do período por módulo: regras (pedido de 28/09/2026; PMBOK, relatório de desempenho e análise de variação)**

* **Onde:** botão **Análise do período** (modal) em 02 Relato do período e KPIs, 03 KPIs de custo e Curva S financeira, 04 Painel de suprimentos, 05 Painel de riscos, 06 Painel da qualidade e 07 Painel HSE. Passo 1: tipo e período (lista com a situação: análise registrada, pendente ou em andamento; padrão: período anterior). Passo 2: resumo dos indicadores do período, texto da análise e um campo por desvio negativo. URL `?analise=1&tipo=&periodo=` abre direto no passo 2 (links do relatório e do modal do Início).
* **Registro:** um por módulo, tipo (Semanal ou Mensal) e período; semanal e mensal são distintos. Texto obrigatório de 150 a 2.500 caracteres (panorama, desempenho dos períodos anteriores, causas e tendência). Botões Trocar período, Copiar do período anterior (traz o texto para revisão) e Excluir (Gestor).
* **Desvio negativo exige comentário (02, 03 e 04), mínimo de 20 caracteres (causa, efeito e ação).** Desvios detectados pela api com os mesmos dados do relatório: 02: avanço acumulado abaixo do previsto, avanço do período abaixo do previsto, término pela tendência depois da linha de base, áreas com desvio negativo (agrupadas), produtividade fora da meta (SPI de quantidades abaixo de 1, FP acima de 1,00, aderência abaixo de 90%, pessoas trabalhando e utilização abaixo da meta; agrupados); 03: CPI abaixo de 1, SPI de custo abaixo de 1, VAC negativo, pacotes com sobrecusto projetado (agrupados); 04: aderência ao plano abaixo de 100%, OTD abaixo de 100%, pedidos críticos (folga negativa), marcos realizados com atraso no período. Em 05 e 07 só o texto é obrigatório (sem regra de desvio definida no pedido). No 06 os desvios são listados sem comentário obrigatório: RNC com prazo de tratamento vencido, aprovação em inspeções e conformidade em auditorias abaixo da meta, auditorias atrasadas.
* **Consistência:** o comentário é gravado por chave do desvio; se os dados mudarem e surgir um desvio novo, ele aparece como pendente no relatório e no modal.

**Relato do período: regras**

* Um registro por projeto, **tipo** e **período**: o semanal (semana ISO) e o mensal (mês civil) são registros distintos. Período do início do projeto até o corrente (período futuro recusado); duplicidade recusada (edite o existente); tipo e período não mudam depois de criados.
* Campos: **Atividades do período** e **Atividades do próximo período** (uma por linha, até 20 linhas de 300 caracteres; ao menos uma) e **Pontos de atenção** (até 12), cada um com o **risco atrelado**: natureza (Ameaça ou Oportunidade) e descrição (causa, evento e efeito), 10 a 400 caracteres. Esse risco é a leitura do planejamento e **não tem vínculo com o registro do 05** (o modal orienta registrar no 05 para tratamento formal).
* "Copiar do período anterior" traz o próximo período do relato anterior como atividades do período e os pontos de atenção para revisão. Gravar exige papel Membro; excluir, Gestor.
* Alimenta a página 2 do Planejamento no relatório gerencial; o modal de emissão mostra se o período tem relato e leva direto ao cadastro (`relato.html?tipo=&periodo=&abrir=1`).
* Mock: semanais S36, S37 e S38 e mensais julho e agosto de 2026; semana 39 e setembro pendentes (em andamento).

**EAP: regras (boas práticas de estrutura analítica e medição física)**

A EAP é o espelho físico da EAC (03): a EAC controla custo; a EAP controla escopo e avanço físico. Mesmo padrão de tela (árvore com recolher e expandir, revisões e movimentação da revisão vigente).

* **Linha do projeto:** a primeira linha da árvore é a atividade resumo do projeto (código 0, nome do projeto, peso 100%, avanço consolidado e datas extremas); recolhê-la esconde a árvore. O mesmo vale para a EAC e o Mapa de controle (03).
* **Estrutura:** área (nível 1) > subárea (nível 2) > pacote (nível 3). Só os pacotes têm peso, datas da linha de base, critério de medição e avanço; áreas, subáreas e o total são somados pela api (média ponderada pelo peso). **Regra dos 100%:** os pesos dos pacotes somam 100% do projeto; o peso de cada nível é a soma dos filhos. No cenário, as áreas fecham com o avanço por área dos KPIs e com a Curva S (previsto 65,7% e real 61,8% em set/26).
* **Tipos de pacote:** pacote de trabalho (mede avanço) e pacote de planejamento (peso reservado, sem medição, para escopo ainda não detalhado). O pacote de planejamento é **desdobrado** em pacotes de trabalho (planejamento em ondas sucessivas): o peso sai dele para o pacote novo, o previsto é mantido e o total do projeto não muda; com peso zero, ele é encerrado. Os desdobramentos da revisão vigente ficam listados com justificativa.
* **Critérios de medição:** Etapas (degraus com peso e % concluído por etapa; modelos nos parâmetros: engenharia, suprimentos, montagem de equipamentos, montagem de painéis, comissionamento), Unidades (executado ÷ quantidade da linha de base), Marco 0/100, Marco 50/50 e Percentual estimado (só para pacotes de até 5% de peso). Pacote novo guarda uma cópia das etapas do modelo.
* **Medição:** o real é sempre calculado a partir das entradas do critério (nunca digitado como resultado). O acumulado não regride: estorno só com justificativa e papel Gestor; o executado não passa a quantidade da linha de base (exige SM e revisão). Cada medição guarda data, de, para, autor e observação (histórico no dicionário). Importação do avanço por planilha (% acumulado ou quantidade executada), com recusa por linha (planejamento, marco fora dos degraus, regressão).
* **Revisões:** Rev 0 = linha de base. Estrutura, pesos, quantidades e términos só mudam por **nova revisão a partir de SM aprovada com impacto em escopo** ainda não incorporada (papel Gestor): o pacote afetado recebe o novo peso (e quantidade ou término), os pacotes novos entram com o peso informado e os demais pesos são reescalados pelo maior resto para fechar 100%. A importação de pacotes também gera revisão. Peso máximo por pacote: 10% (pacote grande perde controle).
* **Indicadores:** avanço real x previsto e desvio (p.p.) com faixas −2 e −5 p.p. (areia e laranja); término vencido (término da linha de base anterior à referência com real abaixo de 100%); SMs a incorporar; conciliação com a Curva S no mês de corte (diferença em p.p.).
* **Integração com 08 Governança:** SM aprovada com impacto em escopo exige a revisão da EAP para ser encerrada (como a EAC exige para custo); a ficha da SM mostra o alerta, a próxima etapa e a linha "Nova revisão da EAP (02)"; o encerramento registra "EAP Rev N" nas linhas de base conferidas.
* **Pendente (decisão do usuário):** hoje a Curva S (real do mês) e os KPIs (avanço por área) continuam com lançamento próprio; a EAP só concilia. Fazer da EAP a fonte única do avanço físico exige desativar esses lançamentos manuais.
* **Inglês:** EAP aparece como **WBS**; SM como CR.
* **Cenário do mock:** 38 pacotes (37 de trabalho e 1 de planejamento, 5.2.1 com 1,2%), Rev 2 vigente (Rev 1 pela SM-TN-2026-0001 e Rev 2 pela SM-TN-2026-0002), um desdobramento (5.2.1 > 5.2.2), dois pacotes com término vencido (2.1.1 e 3.2.1) e a SM-TN-2026-0004 (PR-03) pendente de incorporação.

**Produtividade: regras (boas práticas de controle de quantidades e de produtividade)**

Diferente da Programação Semanal (que trata atividades), a Produtividade controla o que cada empresa tem para executar em quantidades da linha de base (LB), distribuídas por semana conforme o cronograma.

* **Plano de quantidades (aba Quantidades):** item por empresa com grupo (Cabo elétrico por tipo, Concreto, Aço, Tubulação, Painel elétrico, Outros), tipo, disciplina, unidade (m, m³, t, un, m², kg), quantidade total da LB, índice orçado (HH por unidade) e semanas ISO inicial e final (`2026-S39`). O total é distribuído por semana pelo perfil (Curva S 20/60/20, linear, concentrado no início ou no fim) e pode ser ajustado semana a semana; a soma precisa fechar com o total (método do maior resto, sem sobra de arredondamento).
* **Ciclo da LB:** Em elaboração (editável, fora dos indicadores) > Aprovada (Gestor; quem elaborou não aprova). Depois de aprovada, a distribuição fica congelada; mudança só por **revisão com SM aprovada (08)** e justificativa: as semanas até a atual ficam congeladas e o saldo é redistribuído dali em diante; o novo total não pode ser menor que o realizado. Histórico de revisões na ficha do item.
* **Apontamento semanal:** a contratada informa o realizado e as HH apropriadas por item e semana (upsert). Não aponta semana futura; HH obrigatórias quando há realizado; acumulado acima do total da LB é recusado (exige SM e revisão).
* **Indicadores de quantidades:** horas ganhas (HG = realizado x índice orçado) somam unidades diferentes; avanço = HG ÷ HH orçadas; SPI de quantidades = HG ÷ horas previstas na LB; aderência semanal = realizado ÷ previsto, limitado a 100% por item e ponderado pelas HH orçadas; fator de produtividade (FP) = HH apropriadas ÷ HG (1,00 = índice da proposta); tendência de término pelo prazo agregado (earned schedule: SPI(t) = semanas da LB equivalentes ao realizado ÷ semanas decorridas); apontamento pendente = item ativo sem apontamento na semana de corte.
* **Horas efetivas (fiscalização da gerenciadora):** jornada por frente (empresa, área CWA, encarregado, efetivo) com chegada, início e término dos dois turnos; capacidade produtiva (CP) = execução da manhã + execução da tarde; utilização = CP ÷ jornada de referência (8,8 h); atraso de início, almoço, HH efetivas (CP x efetivo) e HH improdutivas ((jornada − CP) x efetivo). Um registro por frente e dia.
* **Amostragem do trabalho (work sampling):** rodadas de observação com pessoas trabalhando, em trânsito e paradas, com motivo (catálogo de 12 motivos de parada e 5 de trânsito); % por dia, Pareto de motivos e resumo por empresa e encarregado.
* **Paralisações:** efetivo (Hhora = pessoas x horas) ou máquina e equipamento (Mhora = unidades x horas), com motivo e responsabilidade (Contratada, Cliente, Gerenciadora, Clima, Terceiros). Cliente, gerenciadora e terceiros são tempo potencialmente excusável (cliente também compensável): o formulário orienta notificar dentro do prazo contratual e avaliar pleito em Contratos (03).
* **KPIs de performance:** geral e por empresa, na janela de N semanas até a semana de corte (parâmetro): avanço, SPI, aderência, FP, tendência de atraso, CP e utilização, % trabalhando, Hhora e Mhora (com % das HH disponíveis); tendência semanal por empresa (FP, aderência, % trabalhando, CP). Empresa com indicador fora da faixa pode gerar **plano de ação na Central** (origem Produtividade, referência `PRD-2026-S39-01` = semana e empresa; uma ação aberta por empresa e semana; o link da Central volta para a aba KPIs com a empresa e a semana).
* **Inglês:** semanas aparecem como W39 (S39 em português); datas curtas pelo idioma (mm/dd); textos sugeridos do plano de ação já saem no idioma da tela. SM aparece como CR, FP como PF, CP como PC.
* **Cenário do mock:** 9 itens (7 da Alfa Montagens e 2 da Zeta Civil), um em elaboração (cabo de média tensão, aguardando a SM-TN-2026-0006) e um revisado (concreto, rev 1 pela SM-TN-2026-0002); dois apontamentos pendentes em S39; 120 jornadas, 240 rodadas e 25 paralisações de S33 a S39; avanço 59,2% x 67,5% (SPI 0,88), FP 1,12 nas últimas 4 semanas, CP 6,81 h/dia, 55,3% trabalhando; uma ação aberta na Central (PRD-2026-S38-01). Nenhum número dos outros módulos mudou (o total de ações da Central ganhou 1 ação em andamento; as 8 atrasadas continuam 8).

**Punch list: regras (boas práticas de completação mecânica e comissionamento)**

* Numeração pelo padrão do projeto: `PL-TN-2026-0001` (herda o campo de numeração de pendências do cadastro de Projeto).
* Hierarquia de sistemas: Área, Sistema, Subsistema, TAG; mais Disciplina (Civil, Mecânica, Tubulação, Elétrica, Instrumentação, Automação, Arquitetura).
* Categoria:
  * **A**: impede o marco seguinte (completação mecânica, comissionamento ou partida); precisa estar fechado para liberar o sistema.
  * **B**: não impede a operação; fechamento até o aceite definitivo, com prazo acordado.
  * **C**: melhoria ou acabamento; fechamento conforme acordo com o cliente.
* Marco vinculado: Completação mecânica, Pré-comissionamento, Comissionamento, Partida, Aceite provisório, Aceite definitivo.
* Origem: Walkdown, Inspeção, Comissionamento, Cliente, Auditoria.
* Fluxo: **Aberto → Em tratamento → Aguardando verificação → Fechado**, com retorno para Em tratamento se a verificação reprovar; **Cancelado** exige justificativa.
* Campos: descrição, empresa executante, responsável, prazo, identificado por, data de abertura, foto de abertura, foto de fechamento, verificado por, data de fechamento.
* Fechamento exige evidência (foto ou documento) e verificação por pessoa diferente do executante (segregação de funções).
* Sistema com item A aberto fica bloqueado para o marco vinculado (alerta no painel).
* Cada item gera uma ação na Central de Ações com origem Punch list; o status do item e o da ação ficam sincronizados.
* Painel: abertos por categoria; curva de abertura e fechamento acumulados (burndown); tempo em aberto (aging: até 7, 8 a 30, mais de 30 dias); itens por disciplina, sistema e empresa; % de sistemas liberados por marco.

### 03 Gestão Financeira

Fonte: pedido do usuário (24/09/2026) e quadro "Tipos de Controle e Componentes Visuais Recomendados". Sem sistema de referência: **todas as telas são novas**. Valores sempre em centavos (inteiros), formatados só na exibição.

**Situação: concluído na etapa 5 (25/09/2026).** Decisões de implementação:

* Abas do módulo com nome curto (Desembolso, KPIs, Curva S); o menu lateral e o topo mantêm o nome completo.
* **Toda alteração de valor na EAC (elemento PEP) passa pela gestão de mudanças (ajuste de 01/10/2026):** remanejamento entre itens e item novo com recurso de outro item viram **SM do tipo "Remanejamento de orçamento"** (08) com as transferências propostas (origem, destino, valor). A SM segue o fluxo completo (análise de impacto com custo zero, decisão na alçada, que considera o valor remanejado) e **a aprovação aplica as transferências na EAC** (com a SM de referência; o saldo livre é conferido de novo). Até a decisão, o valor fica reservado na origem e aparece em "Remanejamentos" como pendente. Acréscimo ao total só por **nova revisão** a partir de SM aprovada com custo (a revisão exige a SM; a importação de itens também). A revisão consolida os remanejamentos na base, aplica o valor da SM e reescala a linha de base da Curva S financeira.
* **Remanejamento** só tira saldo livre da origem: orçado atual menos comprometido menos o reservado em outras SMs abertas; o valor do item novo não pode superar o custo aprovado na SM. Descrição, tipo, classificação, centro de custo e responsável do item não mudam valor: dispensam SM, mas exigem justificativa e ficam no histórico do item (`historicoCadastro`, trilha de auditoria mostrada na edição).
* **Contingência (ajuste de 01/10/2026):** tela própria `contingencia.html`. Reserva de contingência (riscos identificados, integra a linha de base de custo) e reserva gerencial (imprevistos, fora da linha de base, libera só o Comitê/patrocinador), constituídas na linha de base com a base de cálculo. Consumo só por SM aprovada com a fonte da reserva (08; a fonte "Reserva gerencial" exige alçada do Comitê). **Liberação de saldo** (risco encerrado, fase concluída, encerramento) só por SM do tipo "Liberação de reserva", decisão do Comitê, valor até o saldo menos o pedido em SMs abertas: aparece no extrato como Liberação e reduz o saldo e o orçamento do projeto. Indicadores: saldo (com o saldo previsto pelo avanço planejado), consumo x limite (avanço físico real + tolerância), valor pedido em SMs em análise e saldo se aprovadas, cobertura do saldo sobre a exposição (VME das ameaças ativas do 05; meta nos parâmetros) e reserva gerencial. Gráfico do saldo real x previsto, composição (orçado da EAC + contingência = linha de base de custo; + gerencial = orçamento do projeto), extrato de movimentos e ameaças ativas com SMs vinculadas; no Portfólio, tabela por projeto. O Mapa de controle mostra a faixa "Reservas" (o saldo cobre o desvio projetado?).
* **Mapa de controle:** grade em R$ mil (exportação em reais, valor integral); projeção no término atualizada por item com justificativa e histórico; importação dos custos do ERP (comprometido, realizado e projeção) no fechamento do mês.
* **Desembolso:** saldo a pagar = projeção no término menos realizado, distribuído nos meses após o corte pelo perfil da projeção (no backend, por marcos de pagamento e contratos); envio à tesouraria simulado.
* **KPIs de custo:** CPI, SPI, CV, VAC, contingência e comprometido; CPI e SPI mês a mês; tabela de valor agregado com EAC pelo CPI e TCPI.
* **Contratos:** visão consolidada em abas com os indicadores da administração contratual; registros novos nascem na ficha do contrato. Fluxos na ficha: medição (Em análise, Aprovada, Faturada, Paga ou Devolvida com motivo; marco vinculado acompanha faturamento e pagamento), marco (evidência obrigatória antes de aprovar; soma até 100%), claim (situações com parecer e histórico; alerta de notificação fora do prazo ao cadastrar), EOT (decisão com dias, classificação e parecer; concedida prorroga o término vigente), avaliação (pesos gravados na avaliação; nota 1 ou 2 exige evidência e cria ação de plano de melhoria na Central, origem Contrato).
* Cor: sobrecusto e economia usam as cores financeiras (vermelho E1 só para sobrecusto); desvios de prazo (atrasos de marco, notificação fora do prazo) usam laranja.
* Em inglês, a EAC aparece como **CBS** (Cost Breakdown Structure), para não confundir com Estimate at Completion.

**Terminologia:** neste sistema **EAC = Estrutura Analítica de Custos**. O indicador de valor agregado com a mesma sigla em inglês (Estimate at Completion) aparece como **"Projeção no término"**, para evitar ambiguidade.

| Tela | Arquivo | Conteúdo | Situação |
|---|---|---|---|
| EAC: cadastro e atualização | `modulos/financeiro/eac.html` | Árvore da EAC (pacote, subpacote, item) com código, descrição, tipo de custo (Material, Mão de obra, Equipamento, Serviço, Indireto, Contingência), unidade, quantidade, preço unitário, valor orçado (automático), CAPEX/OPEX, centro de custo e responsável; revisões (Rev 0 = linha de base aprovada; Rev N com justificativa); remanejamento entre itens (origem, destino, valor, justificativa); importação por planilha (componente de upload) | Nova |
| Mapa de controle da EAC | `modulos/financeiro/mapa-controle.html` | Item a item e subtotal por pacote: Orçado (linha de base), Remanejamentos, Orçado atual, Comprometido, Realizado, Saldo a comprometer, Projeção no término, Desvio (R$ e %); mapa de calor no desvio (2.7) | Nova |
| Cronograma de desembolso | `modulos/financeiro/desembolso.html` | Gerado a partir do mapa de controle: saldo a pagar de cada item distribuído por mês; histograma mensal Previsto x Realizado; tabela item x mês com totais, para alinhamento com a tesouraria | Nova |
| KPIs de custo | `modulos/financeiro/kpis.html` | Cartões de resumo: CPI, SPI, CV, VAC, % de consumo da contingência, % comprometido; variação em relação ao período anterior | Nova |
| Curva S financeira | `modulos/financeiro/curva-s.html` | CAPEX Planejado, Comprometido e Realizado acumulados por mês; tabela período a período | Nova |
| Contingência | `modulos/financeiro/contingencia.html` | Reservas de contingência e gerencial: KPIs, alertas, saldo real x previsto, composição da linha de base de custo, extrato de movimentos (constituição, consumo por SM, pedidos em análise), ameaças ativas e cobertura; por projeto no Portfólio | Nova (01/10/2026) |
| Contratos: registros | `modulos/financeiro/contratos.html` | Abas Contratos, Claims, Extensões de prazo, Marcos de pagamento e Avaliações (visão consolidada de todos os contratos, com filtros e exportação); KPIs da administração contratual | Nova |
| Contrato: ficha | `modulos/financeiro/contrato.html` | Abas Resumo (cascata: valor original, aditivos aprovados, medido, saldo a faturar; datas de término original e vigente), Medições, Aditivos, Marcos de pagamento, Claims, Extensões de prazo, Avaliação de desempenho; modais Nova medição, Novo aditivo, Novo claim, Nova extensão de prazo, Novo marco, Nova avaliação | Nova |

Regras de negócio propostas:

* Orçado atual = Orçado (linha de base) + Remanejamentos. A soma dos remanejamentos de uma revisão é zero; o total do orçamento só muda por nova revisão aprovada.
* Saldo a comprometer = Orçado atual − Comprometido.
* Desvio = Projeção no término − Orçado atual (positivo = sobrecusto; negativo = economia).
* Cronograma de desembolso: a soma dos meses futuros de cada item = Projeção no término − Realizado.
* Contrato: Valor atual = Valor original + Aditivos aprovados; Saldo a faturar = Valor atual − Medido aprovado.

#### Administração contratual (boas práticas de gestão de contratos pós-adjudicação)

Campos comuns a todos os contratos: Nº, contratada, objeto, modalidade (Preço global, Preço unitário, Administração, EPC), valor original (centavos), data de início, término original, término vigente, gestor do contrato, fiscal, retenção contratual (%), prazo contratual de notificação de claims (dias). O contrato nasce da adjudicação no módulo 04 Suprimentos.

**Medições (boletins)**

* Nº, período, itens medidos (quantidade × preço unitário, ou % do marco), valor bruto, retenção, valor líquido; situação **Em análise → Aprovada → Faturada → Paga**, ou **Devolvida** com motivo.
* Medição aprovada alimenta o Realizado da EAC e o Cronograma de desembolso.

**Claims (pleitos)**

* Numeração `CLM-TN-2026-0001`. Direção: **da contratada** (pleito contra o contratante) ou **do contratante** (back-charge contra a contratada).
* Tipo: Prazo, Custo, Prazo e custo. Causa: Liberação de área, Mudança de escopo, Informação de projeto tardia, Interferência, Suspensão, Condição climática, Força maior, Outros.
* Datas do evento e da notificação; **alerta de notificação fora do prazo contratual** (preclusão).
* Valor e dias pleiteados; valor e dias reconhecidos; fundamentação contratual (cláusula); documentos (upload).
* Fluxo: **Notificado → Em análise → Em negociação → Acordado (total ou parcial) / Rejeitado → Em disputa (jurídico) → Encerrado**.
* Claim acordado gera Solicitação de Mudança (08) para atualizar linha de base e aditivo; claim relacionado a risco é vinculado ao registro (05).

**Extensões de prazo (EOT)**

* Numeração `EOT-TN-2026-0001`. Evento causador (pode vir de um claim), dias solicitados, dias concedidos, marco contratual afetado.
* Classificação: **Justificável e compensável** (prazo e custo), **Justificável não compensável** (só prazo), **Não justificável** (atraso da contratada, sujeito a multa).
* Análise de atraso registrada: método (análise de impacto no tempo ou por janelas), atividades e caminho crítico afetados.
* Fluxo: **Solicitada → Em análise → Concedida (total ou parcial) / Negada**. Concedida atualiza o término vigente do contrato e dispara SM (08) para a linha de base do cronograma.

**Marcos de pagamento**

* Por contrato: Nº, descrição, critério de aceite (evidência exigida), % do valor, valor (centavos), data prevista, data de conclusão, retenção aplicada.
* Fluxo: **Previsto → Evidência enviada → Aprovado (fiscal e gestor) → Faturado → Pago**. Marco só é aprovado com evidência anexada.
* A soma dos % dos marcos de um contrato é 100%. Marcos previstos alimentam o Cronograma de desembolso.

**Avaliação de desempenho da contratada**

* Periodicidade: mensal durante a execução e **avaliação final** no encerramento do contrato.
* Critérios, nota de 1 a 5 e peso: HSE (25%), Qualidade (20%), Prazo (20%), Gestão contratual e comercial (15%), Recursos e mobilização (10%), Documentação e comunicação (10%).
* Nota ponderada de 0 a 100 e classe: **A** (85 ou mais, preferencial), **B** (70 a 84, aprovada), **C** (50 a 69, aprovada com plano de melhoria), **D** (abaixo de 50, não recomendada).
* Nota 1 ou 2 em qualquer critério exige evidência e plano de melhoria (ações na Central, origem Contrato).
* A avaliação final atualiza a qualificação do fornecedor (04 Suprimentos) e gera lição aprendida de fornecedor (08).

**Indicadores da administração contratual**

| Indicador | Cálculo |
|---|---|
| Exposição de claims | Soma do valor pleiteado em aberto (centavos), por direção |
| Taxa de reconhecimento | Valor reconhecido ÷ valor pleiteado (claims encerrados) |
| Tempo médio de resolução | Média de dias entre notificação e encerramento |
| Notificações fora do prazo | Nº de claims notificados após o prazo contratual |
| Extensão de prazo acumulada | Dias concedidos ÷ duração original do contrato (%) |
| Dias solicitados x concedidos | Por contrato e por causa |
| Marcos atrasados | Marcos com data prevista vencida e não aprovados |
| Aprovado não faturado | Soma dos marcos aprovados sem faturamento |
| Pago x previsto | Pago acumulado ÷ previsto acumulado até a data |
| Desempenho das contratadas | Nota média, classe e tendência por contratada; nº de contratadas C ou D |

### 04 Suprimentos

Fonte: pedido do usuário (25/09/2026 e 26/09/2026: incluir o **MAS, Mapa de Suprimentos**) e área de conhecimento "Procurement" do CIPM 2.0 (Tartan Book). Sem sistema de referência: **todas as telas são novas**; o MAS foi desenhado pelas boas práticas (sem modelo de planilha do cliente, decisão do usuário em 26/09/2026). Valores em centavos.

**Situação: concluído na etapa 5 (26/09/2026).** Seis telas, abas com nome curto (Plano, Processos, MAS); o menu lateral e o topo mantêm o nome completo.

| Tela | Arquivo | Conteúdo e entrada de dados | Situação |
|---|---|---|---|
| Painel de suprimentos | `modulos/suprimentos/painel.html` | 9 KPIs (tabela de indicadores abaixo); curva de contratação (pacotes adjudicados acumulados, plano x realizado); avanço físico de suprimentos (Curva S do MAS: LB, real e tendência); saving acumulado (sobre a estimativa e na negociação); pacotes por etapa; pedidos por folga em relação ao ROS | Nova |
| Plano de compras | `modulos/suprimentos/plano-compras.html` | Pacotes: código, escopo, tipo (Equipamento, Material, Serviço, EPC), modalidade, disciplina, LLI, item da EAC, estimativa, comprador, datas planejadas (LB) e ROS; etapa, folga e adjudicado. Entrada: modal Novo pacote (saldo a comprometer do item e folga planejada calculados na hora), edição e importação Excel | Nova |
| Processos de compra (RFx) | `modulos/suprimentos/processos.html` | Lista com a etapa (barra de 9 segmentos), propostas, melhor proposta e alçada; ficha do processo com as 9 etapas, resumo, **mapa de equalização** (nota técnica, comercial e final, ranking, desvios, anexos) e histórico. Entrada: modais Nova requisição, Emitir RFx, Registrar proposta (PDF), Encerrar recebimento, Equalização técnica, Equalização comercial (prévia do ranking), Negociação, Recomendação, Aprovação por alçada, Devolver, Emitir pedido ou contrato | Nova |
| **MAS: Mapa de Suprimentos** | `modulos/suprimentos/mas.html` | Uma linha por pacote e 12 marcos do ciclo completo em dois grupos: **Aquisição** (requisição, RFx emitida, propostas, equalização técnica, equalização comercial, aprovação, pedido/contrato) e **Fabricação e entrega** (documentos aprovados, fabricação, inspeção/FAT, embarque, entrega). Cada célula mostra LB e previsão ou realizado, com cor, ícone e texto (legenda abaixo); alternância Datas / Desvio em dias; filtro de fase (Todos, Aquisição, Fabricação); filtros por disciplina, tipo, LLI, comprador, fornecedor e situação, com ordenação; ROS, previsão de entrega, folga, avanço (real x LB) e situação; rodapé com realizados x previstos na LB por marco; clique na célula abre o detalhe do item. Exportação Excel (LB, previsão/real e situação de cada marco) e PDF A3 paisagem com as células coloridas | Nova |
| Diligenciamento e recebimento | `modulos/suprimentos/diligenciamento.html` | Pedidos com próximo marco, data contratual, previsão, ROS, folga e situação; bloco de pedidos críticos com tratamento pendente (gerar ação, registrar risco sugerido); ficha do pedido com os 6 marcos (LB contratual, previsão, realizado, desvio), recebimento, ação e risco vinculados e últimas atualizações. Entrada: modais Atualizar marco (realização ou reprogramação com efeito na folga), Registrar recebimento, Registrar risco sugerido e importação do ERP (uma linha por marco) | Nova |
| Fornecedores | `modulos/suprimentos/fornecedores.html` | Situação (Qualificado, Em qualificação, Restrito, Bloqueado), categorias, validade da qualificação, documentos com validade, desempenho (classe e nota das avaliações de contrato do 03; OTD dos pedidos), valor contratado. Entrada: Novo fornecedor, Atualizar qualificação (justificativa na mudança de situação); modal Desempenho e histórico | Nova |

**MAS (Mapa de Suprimentos): regras**

* O MAS não tem cadastro próprio: é montado pela api a partir do plano de compras (LB e marcos de aquisição), dos processos (realizado) e do diligenciamento (marcos de fabricação). Uma fonte de verdade por dado; nada é digitado duas vezes.
* Cada marco tem três camadas: **LB** (linha de base do plano; nos marcos de fabricação, o cronograma contratual do pedido), **previsão** (reprogramação) e **realizado**.
* Situação do marco (`GI.regras.situacaoMarco`): **realizado no prazo** (real até a LB, verde-água); **realizado com atraso** (real depois da LB, laranja claro); **vencido sem realização** (previsão ou LB já passou, laranja forte); **previsão após a LB** (previsão futura depois da LB, areia); **a vencer** (neutro); **não se aplica** (cinza: fabricação de pacotes de serviço e EPC). Desvio = dias em relação à LB.
* Pacote ainda sem pedido: a LB e a previsão dos marcos de fabricação são **estimadas** entre o pedido e a entrega do plano (itálico e aviso "LB estimada"), pelas mesmas proporções usadas na emissão do pedido.
* Folga = ROS menos a previsão de entrega (serviço: ROS menos o contrato). Situação da linha: Entregue ou Contratado; **Crítico** (folga negativa); **Atenção** (folga até o alerta dos parâmetros ou marco vencido); No prazo.
* **Avanço de suprimentos** pelo critério de medição dos parâmetros (pesos por marco, soma 100; serviço renormaliza só os marcos de aquisição), ponderado pelo valor do pacote (adjudicado ou estimado). Previsto = marcos com LB até a data de referência. Índice = real ÷ previsto. A mesma regra gera a Curva S de suprimentos do Painel.

**Fluxo do processo de compra (validado na api, `GI.api.suprimentos.acaoProcesso`)**

* Planejado → **Requisição** → **RFx emitida** (convidados; mínimo de propostas dos parâmetros ou fornecedor único com justificativa; fornecedor Bloqueado não é convidado) → **Propostas recebidas** (primeira proposta) → **Equalização técnica** (encerramento do recebimento; abaixo do mínimo exige justificativa) → **Equalização comercial** (notas técnicas e aprovação; técnica sempre antes da comercial) → **Negociação** (ranking: nota comercial = menor preço tecnicamente aprovado ÷ preço x 100; nota final ponderada pelos pesos) → **Recomendação de adjudicação** (só proposta aprovada tecnicamente e fornecedor cadastrado; outra que não a melhor nota, ou fornecedor não qualificado, exige justificativa) → **Aprovada** (alçada por valor; aprovador diferente do comprador e de quem recomendou; valor limitado ao saldo a comprometer do item da EAC; LLI antes do gate de investimento exige a aprovação do gate LLI) → **Pedido/contrato emitido**.
* Cada ação grava a data realizada do marco correspondente no pacote (MAS) e o histórico do processo. Devolver a recomendação volta para Negociação com motivo.
* Emissão: equipamento e material geram **pedido** (`PED-2026-0012` em diante) com cronograma de fabricação padrão a partir do prazo da proposta; serviço e EPC geram **contrato no 03** (`CT-2026-015` em diante). O valor fica **comprometido na EAC**. Pedido que já nasce com folga negativa cria a ação de diligenciamento na Central.

**Diligenciamento (regras)**

* Marco realizado exige o anterior realizado e data até a referência; previsão não pode ficar no passado. Reprogramação pode deslocar os marcos seguintes na mesma quantidade de dias.
* Folga negativa gera, sem duplicar: **ação na Central** (origem Suprimentos, grupo Diligenciamento, responsável o comprador, prazo de 7 dias) e **risco sugerido** (modal pré-preenchido; entra no registro 05 como "Em análise", categoria Suprimentos, origem "Diligenciamento PED-...").
* FAT realizado registra a **inspeção no 06 Qualidade** (`inspecoesQualidade`, origem Suprimentos); FAT reprovado não conclui o marco e exige nova previsão do reteste.
* Entrega só pelo Registrar recebimento (embarque realizado antes; conferência, avarias com descrição, pendências e anexos) ou pela importação do ERP.

Regras gerais (boas práticas de suprimentos em projetos de capital):

* Todo pacote nasce no plano de compras vinculado a um item da EAC (nível 3); compra emergencial é marcada e justificada.
* A LB do pacote fica congelada a partir da requisição: depois disso só escopo, comprador, estimativa e ROS mudam, com justificativa e histórico.
* O plano não pode nascer com folga negativa (entrega ou contrato planejado depois do ROS).
* Processo competitivo com no mínimo 3 propostas válidas; fornecedor único exige justificativa aprovada.
* Equalização técnica antes da comercial; proposta tecnicamente reprovada não segue para a comercial.
* Adjudicação aprovada por alçada (valores configuráveis); gera contrato no 03 ou pedido no 04 e compromete o valor na EAC.
* Item LLI com contratação antes do gate de investimento exige aprovação específica e análise de risco (CIPM: gate LLI).
* Folga negativa (previsão de entrega após o ROS) gera alerta, risco sugerido (05) e ação de diligenciamento na Central.

Indicadores:

| Indicador | Cálculo |
|---|---|
| Aderência ao plano de compras | Pacotes adjudicados até a data ÷ pacotes planejados até a data |
| Ciclo de compra | Média de dias entre requisição e pedido emitido |
| Saving sobre estimativa | (Soma das estimativas − soma adjudicada) ÷ soma das estimativas |
| Saving de negociação | (Primeira proposta vencedora − valor negociado) ÷ primeira proposta |
| Competitividade | Média de propostas válidas por processo; % de processos com fornecedor único |
| Entrega no prazo (OTD) | Entregas até a data contratual ÷ entregas realizadas |
| Pedidos críticos | Nº de pedidos com folga negativa em relação ao ROS; itens LLI em atraso |
| Compras emergenciais | Valor emergencial ÷ valor total contratado |
| Comprometido x orçado | Valor adjudicado ÷ orçado atual dos itens da EAC |
| Avanço de suprimentos (MAS) | Soma dos pesos dos marcos realizados ÷ soma dos pesos aplicáveis, ponderada pelo valor; previsto pela LB; índice = real ÷ previsto |
| Marcos vencidos (MAS) | Marcos sem realização com previsão (ou LB) anterior à data de referência |

Cenário do mock (coerente com a Home): 14 pacotes no projeto 1; 3 pedidos críticos (PED-2026-0001 folga −20, 0002 −9, 0004 −5), 2 deles LLI; aderência 92,9%; saving 5,2% sobre a estimativa e 4,7% na negociação; OTD 66,7%; avanço de suprimentos 90,9% x 97,3% previsto (índice 0,93); PC-14 (SDCD) em equalização comercial, pronto para percorrer o fluxo até a emissão.

### 05 Gestão de Riscos

Fonte: `Sistema Gestão Integrada\Módulo de Riscos\mockups\` (telas 01 a 04, modais 10 a 17). **Concluído em 26/09/2026.**

| Tela | Arquivo | Conteúdo | Situação |
|---|---|---|---|
| Registro | `modulos/riscos/registro.html` | Contexto do projeto (projeto, cliente, numeração, apetite); 5 KPIs clicáveis pela avaliação exibida (faixa mais alta, segunda faixa, Em tratamento, Revisão vencida, Ativos); aviso de revisão vencida; chips; alternador Inerente/Residual (troca a coluna destacada, a base dos KPIs e o filtro de severidade); colunas Nº, Risco, Dono, Inerente, Residual, Estratégia, Ações, Próx. revisão, Situação (Natureza e Projeto opcionais); ações por linha Avaliar, Nova ação e Excluir (o número abre a ficha); planilha com causa, consequência e plano | Replicada |
| Matriz P x I | `modulos/riscos/matriz.html` | Mapa 5x5 com contagem, fórmula e números por célula (célula é link para o registro filtrado; vazia esmaecida); natureza (oportunidades com escala de cor invertida em verde); legenda pelas faixas da escala ativa; movimentação inerente para residual com barras sobrepostas e destaque de "sem redução" | Replicada |
| Ficha do risco | `modulos/riscos/ficha.html?codigo=` | Faixa com inerente › residual e situação; alertas (sem avaliação, plano aguardando aprovação, gatilho, revisão vencida, pauta, encerrado ou excluído); botões Editar, Avaliar, Plano de resposta, Nova ação, Registrar revisão, Aprovar plano, Encerrar e Reabrir (o próximo passo recomendado vem em destaque); abas Identificação, Avaliação (somente leitura, dimensões, VME inerente e atual), Resposta e ações (plano, custo x benefício, aprovação, ações da Central), Monitoramento (linha do tempo das revisões e cadência) e Histórico (trilha de auditoria) | Replicada |
| Painel | `modulos/riscos/painel.html` | Painel de riscos do projeto: KPIs (faixa mais alta, segunda faixa, exposição VME, revisão vencida, redução média); exposição por categoria da RBS (barras que abrem o registro filtrado); evolução mensal do score residual das ameaças; pauta de escalonamento com envio por e-mail ao gerente do projeto (simulado) | Replicada (visão de portfólio retirada em 28/09/2026) |
| Modais 10 a 17 | `js/pages/riscos/riscos.js` | Novo risco/edição (causa, evento, consequência; cadastro rápido de categoria; ata de origem; Salvar e avaliar), Avaliação (P com faixas percentuais, 6 dimensões, impacto pelo pior caso, prévia do score), Plano de resposta (estratégias por natureza, instrumento, SM, alvo, custo x VME, aprovação, ações), Ação de mitigação (vai para a Central; Salvar e nova), Revisão periódica, Encerramento, Filtros e Excluir | Replicados |

Regras aplicadas (RG dos mockups):

* **Score e severidade só na api** (`GI.api.riscos`); a tela exibe a prévia devolvida por `previa()`. Faixas da escala ativa dos parâmetros (Timenow 4 faixas ou CIPM 3 faixas, com risco à vida sempre na mais alta na CIPM).
* **Impacto = maior dimensão** (prazo, custo, escopo e qualidade, SMS, imagem, legal e contratual); pode ser elevado, nunca reduzido.
* **VME = probabilidade média da faixa x impacto em custo**, em centavos (faixas 5, 20, 40, 60 e 85%). A ficha mostra o VME inerente e o atual; a exposição do painel e da Home soma só ameaças.
* **Ciclo de vida:** Identificado (sem avaliação) > Em análise (avaliado, sem plano ou com plano aguardando aprovação) > Em tratamento (plano aprovado e ações) > Monitorado (Aceitar, ou ações concluídas com reavaliação residual) > Materializado ou Encerrado. Concluir as ações não fecha o risco.
* **Plano de resposta:** residual só depois do plano; alvo não maior que a inerente (ameaça); prazo futuro; ação obrigatória para inerente Alto ou Crítico (exceto Aceitar, que exige justificativa de 30 caracteres); Evitar exige 80 caracteres e SM (existente ou nova, que gera ação na Central); Transferir exige instrumento (seguro, cláusula, subcontratação, hedge). Inerente na faixa mais alta exige aprovação da gerência do projeto (papel Gestor), e quem é responsável pelo plano não aprova (segregação de funções).
* **Cadência de revisão** pela severidade atual (crítico 15, alto 30, moderado 60, baixo 90 dias, parâmetro): o gestor antecipa, nunca posterga. Toda avaliação e toda revisão grava linha na linha do tempo com antes e depois; gatilho ocorrido força reavaliação e entra na pauta; "Risco materializado" e "Risco superado" abrem o encerramento.
* **Pauta de escalonamento:** acima do alvo a 30 dias (parâmetro) ou menos do prazo do alvo, sem redução após o plano, plano aguardando aprovação, revisão vencida, gatilho ocorrido, identificado sem avaliação ou risco da faixa mais alta sem plano.
* **Encerramento (Gestor):** bloqueado com ação aberta, salvo Materializado; lição aprendida sempre obrigatória (cria lição em Rascunho no acervo do 08); reabertura pelo Gestor com justificativa.
* **Exclusão lógica (Gestor):** bloqueada com ação aberta e para risco encerrado; grava motivo, autor e data; só o Admin vê e restaura. O número não é reaproveitado.
* **Numeração** reservada na gravação pelo padrão do projeto (`proximoCodigo` agora só conta sufixos numéricos: RSK-TN-2026 não soma RSK-TN-2026-SE).

**Ajuste ao mockup 15 (Encerramento), aplicado:** risco materializado vira **problema**, não pendência: a opção gera ação na Central (grupo Problema, origem Risco) e, se exigir alterar escopo, prazo ou custo, registra a **solicitação de mudança** no 08 (situação Registrada). As ações abertas continuam na Central. Para oportunidade, o motivo aparece como "Capturada" e não gera problema nem SM.

Decisões onde os mockups divergem entre si:

* **Excluir:** o mockup 01 cita Membro, mas a regra do modal 17 (RG-34) exige Gestor; seguido o RG-34.
* **Severidade padrão do filtro:** o modal 16 sugere Alto e Crítico, mas a tela 01 abre com "Severidade: Todas" e 7 riscos ativos; seguida a tela 01.
* **Revisão periódica** altera P e I da avaliação vigente (residual, ou inerente se ainda não houver plano), como mostra o modal 14; o modal 11 continua sendo o lugar da avaliação completa (dimensões e justificativa).
* **Exposição e evolução** somam só ameaças (o mockup somava a oportunidade); oportunidades seguem nos KPIs de severidade com a separação "ameaças · oportunidades".
* **Consulta ao abrir (RG-04):** no protótipo o registro carrega ao abrir, como a Central; o botão Atualizar refaz a consulta.
* Não implementados no protótipo: cadastro rápido de dono (convidados ficam em Configurações > Cadastros), confirmação ao cancelar com alterações e pendência vinculada (substituída pelo ajuste do mockup 15).

Cenário do mock (coerente com a Home): projeto 1 com 7 riscos ativos e 2 encerrados (RSK-TN-2026-0008 não se materializou; 0009 materializado, com SM-TN-2026-0002 e lição LA-TN-2026-0001); **2 críticos** no residual (0003, ameaça, e 0004, oportunidade), 1 alto, 3 em tratamento, 1 revisão vencida (0003, com plano aguardando aprovação), exposição **R$ 3,4 mi**; pauta com 0003 e 0001. Projeto 2 (subestação) com 4 riscos, entre eles RSK-TN-2026-SE-0001 vindo do diligenciamento do PED-2026-0011 e um risco à vida (descarga atmosférica).

### 06 Gestão da Qualidade

Sem fonte de referência: **todas as telas são proposta** pelas boas práticas (PMBOK: gerenciar e controlar a qualidade; ISO 9001 8.7 e 10.2 para saída não conforme e ação corretiva; ISO 19011 para auditorias; ITP com pontos de espera e testemunho, prática de completação de projetos industriais). Concluído em 30/09/2026, com visão por projeto e Portfólio.

| Tela | Arquivo | Conteúdo | Situação |
|---|---|---|---|
| Painel | `modulos/qualidade/painel.html` | KPIs (RNC em aberto com vencidas e críticas, tempo médio de tratamento e eficácia na 1ª verificação, aprovação em inspeções x meta, conformidade em auditorias x meta e aderência ao programa, custo da não qualidade); aviso de auditorias atrasadas; RNC por mês (abertas e encerradas), aprovação em inspeções por mês com a meta, Pareto de RNC por disciplina, RNC por origem; pauta de tratamento; desempenho por empresa; botão **Análise do período** | Nova (30/09/2026) |
| Não conformidades (RNC) | `modulos/qualidade/rnc.html` | Filtros (busca, situação, severidade, disciplina), KPIs, lista com próxima etapa e ações; ficha em modal com contenção, causa raiz, disposição e concessão, verificação, ações da Central e histórico; `?busca=RNC-...` abre a ficha | Nova (30/09/2026) |
| Inspeções e ITP | `modulos/qualidade/inspecoes.html` | Planos de inspeção e testes (pontos H, W e R com critério, referência e responsável; revisão e aprovação do cliente) e registros de inspeção por ponto (filtros por ITP, resultado e tipo) | Nova (30/09/2026) |
| Auditorias | `modulos/qualidade/auditorias.html` | Programa de auditorias (contratada, fornecedor, interna), atrasadas, reprogramação justificada, resultado com conformidade e constatações | Nova (30/09/2026) |

**Regras (06 Gestão da Qualidade)**

* **RNC:** Aberta → Em análise de causa → Ação corretiva → Verificação de eficácia → Encerrada; Cancelada só antes da ação corretiva (Gestor, com motivo). Abertura exige descrição (o que, onde, requisito) e **contenção imediata**; o **prazo de tratamento** vem da severidade (parâmetros: Crítica 15, Maior 30, Menor 45 dias) e vale até a ação corretiva concluída. A análise (método 5 porquês, Ishikawa ou árvore de causas, causa raiz e disposição) cria ao menos uma **ação corretiva na Central** (origem RNC). Disposição **Reparo** ou **Usar como está** exige a **concessão do cliente** (documento e data). Com as ações concluídas, a RNC vai para verificação, prevista para N dias depois (parâmetro, 30). A verificação é do **Gestor** e não pode ser feita por quem respondeu pela análise (segregação); eficaz encerra (lição opcional em Rascunho no 08, origem `RNC <código>`), ineficaz volta para Ação corretiva e conta reincidência. Custo da não qualidade (retrabalho, reparo, ensaios, perdas) atualizável com a composição.
* **ITP:** pontos H (espera: a atividade seguinte só é liberada com o registro aprovado), W (testemunho: cliente notificado com antecedência mínima, parâmetro 48 h) e R (revisão de registros). Inspeção só em ITP **aprovado pelo cliente**; nova revisão do ITP volta a pedir aprovação e não pode retirar ponto que já tem inspeção. Ressalva conta como aprovada; **reprovação abre RNC** automaticamente (severidade e contenção no próprio registro). Notificação ausente ou com antecedência menor gera aviso.
* **Auditorias:** planejadas com escopo, critérios, auditado, auditor líder e data; data vencida sem resultado = atrasada; reprogramação exige justificativa e fica registrada. O resultado registra itens verificados e conformes e as constatações (Não conformidade, Observação, Oportunidade de melhoria); **cada Não conformidade abre RNC** (origem Auditoria) e não pode haver mais NC que itens não conformes.
* **Indicadores:** aprovação em inspeções = (aprovadas + com ressalva) ÷ inspeções; conformidade = itens conformes ÷ verificados nas auditorias realizadas; aderência ao programa = realizadas ÷ previstas até a data de referência; tempo médio de tratamento = abertura até o encerramento; eficácia na 1ª verificação = encerradas sem reincidência ÷ encerradas.
* **Integrações:** ações na Central (origem RNC, link de volta); FAT do diligenciamento (04) grava inspeção; lição em Rascunho no 08; alertas no Início (RNC com prazo vencido ou crítica em aberto); folha **Qualidade** no relatório gerencial e **análise do período** do 06 (desvios: RNC com prazo vencido, aprovação ou conformidade abaixo da meta, auditorias atrasadas; comentário não obrigatório, como em 05 e 07).

### 07 HSE (Saúde, Segurança e Meio Ambiente)

Fonte: pedido do usuário (25/09/2026), área de conhecimento HSE do CIPM 2.0 e ABNT NBR 14280 (taxas de frequência e gravidade). Sem sistema de referência: **todas as telas são novas**.

**Situação: concluído na etapa 5 (27/09/2026); Painel HSE com filtro de mês/ano e pirâmide dupla desde 28/09/2026.** Decisões de implementação:

* Cinco telas, sem ficha separada (`layout.js` já previa o módulo sem array `detalhes`): Ocorrências, Análises de risco e a pirâmide usam modal para o detalhe, não página própria.
* Pirâmide de segurança: no Painel usa `GI.charts.pyramidPair` (par mês x acumulado, 28/09/2026): faixas de altura fixa (44 px; 40 px até 480 px), rótulos curtos no plural uma vez só na coluna central, proporção real numa linha abaixo de cada pirâmide ("Real 0 : 16 : 31 : 190") e a referência numa linha única no rodapé do card ("Referência Bird 1 : 10 : 30 : 600"). `GI.charts.pyramid` (pirâmide única, mesmo padrão visual) continua disponível (styleguide). Nível 5 (Desvios) não tem registro individual, vem consolidado de Inspeções e observações.
* Ocorrência com ciclo **Registrada → Em investigação → Ações definidas → Em tratamento → Encerrada**; ação corretiva nasce na Central de Ações (origem HSE) e o link de volta (`GI.util.linkOrigem`) distingue `OCR-` (ocorrência) de `APR-`/`HAZOP-` (estudo de risco).
* HHT e o registro mensal (DDS/inspeções/observações/desvios) são upsert por mês (e por empresa, no caso do HHT): editar reabre o mesmo registro com mês e empresa bloqueados.
* Tradução (inglês): seguiu o dicionário plano existente (`js/i18n/en.js`); por ser um dicionário único sem namespace por módulo, três palavras já usadas por outros módulos com outro sentido (`Prazo`, `Desvio`, `Emissão`) não foram redefinidas para não quebrar a tradução desses módulos: ficam em português nos poucos lugares em que aparecem soltas no HSE (limitação pré-existente do dicionário, mesmo padrão já visto entre os módulos 02 e 05).
* **Painel HSE (28/09/2026):** filtro de Ano e Mês na barra de filtros; KPIs reativos (TF, TRIF, TG, HiPo) em dois blocos, "No mês selecionado" e "Acumulado" (desde o primeiro mês com HHT até o mês escolhido, mesmo critério de "acumulado" usado em Financeiro e Planejamento); "Dias sem afastamento" e "Ações HSE no prazo" ficam só no bloco Acumulado por não variarem por mês. Pirâmide de segurança em duas colunas (Mês e Acumulado), mesmo componente `GI.charts.pyramid` chamado duas vezes.
* **Dados do mock (28/09/2026):** dois registros de "Primeiros socorros" gerados foram remanejados de julho para janeiro e fevereiro, para nenhum mês do ano ficar sem lesão leve no filtro por mês. **Cenário sem lesão grave (28/09/2026, pedido do usuário):** o nível 1 é zero em todos os meses; os dois acidentes com afastamento de fevereiro foram reclassificados como lesão leve (OCR de 03/02: trabalho restrito; OCR de 25/02: tratamento médico, mantido como HiPo), sem dias perdidos. Efeitos: pirâmide acumulada 0/16/31/190/1.240; TF e TG zerados; TRIF inalterada (as duas ocorrências continuam registráveis); "Dias sem afastamento" passa a contar desde o início do projeto (05/01/2026), 263 dias na data de referência.

| Tela | Arquivo | Conteúdo e entrada de dados | Situação |
|---|---|---|---|
| Painel HSE | `modulos/hse/painel.html` | Filtro de Ano e Mês; **duas pirâmides de Heinrich/Bird** (Mês e Acumulado, contagem real por nível e comparação com a proporção de referência 1 : 10 : 30 : 600 de Bird ou 1 : 29 : 300 de Heinrich); taxas reativas no mês e acumuladas, e proativas (tabela abaixo); dias sem acidente com afastamento; evolução mensal das taxas; ocorrências por empresa e por área | Nova |
| Ocorrências | `modulos/hse/ocorrencias.html` | Registro, investigação e ações. Entrada: modal Nova ocorrência (campos abaixo), Investigação, Encerramento; upload de fotos e relatório | Nova |
| Inspeções e observações | `modulos/hse/inspecoes.html` | Inspeções de segurança por checklist (itens conformes e não conformes), observações comportamentais, DDS (tema, data, participantes). Entrada: modais e importação Excel | Nova |
| Análises de risco (APR/JSA, HAZOP) | `modulos/hse/analises-risco.html` | Registro dos estudos (tipo, área, data, participantes) e das recomendações (responsável, prazo, situação); recomendação vira ação na Central | Nova |
| Horas trabalhadas (HHT) | `modulos/hse/hht.html` | Horas-homem trabalhadas e efetivo médio por mês e por empresa (base de todas as taxas). Entrada: formulário mensal e importação Excel | Nova |

**Classificação das ocorrências** (base da pirâmide)

| Nível da pirâmide | Tipos de ocorrência |
|---|---|
| 1. Lesão grave | Fatalidade; acidente com afastamento (LTI) |
| 2. Lesão leve | Trabalho restrito (RWC); tratamento médico (MTC); primeiros socorros |
| 3. Dano material | Acidente sem lesão com dano à propriedade ou equipamento |
| 4. Quase acidente | Evento sem lesão nem dano que poderia ter causado |
| 5. Desvios | Atos e condições inseguras registrados em observações e inspeções |

Ocorrências ambientais (vazamento, emissão, resíduo) são registradas no mesmo formulário com tipo Ambiental e severidade própria, fora da pirâmide.

**Nova ocorrência (campos):** data e hora, área e local, empresa (contratada), tipo, descrição, gravidade real e **potencial** (matriz 5x5), marcação de **alto potencial (HiPo)**, número de pessoas envolvidas e função (sem nome no registro geral), dias perdidos e debitados, comunicação legal (CAT) quando aplicável, causa imediata, evidências.

Fluxo: **Registrada → Em investigação → Ações definidas → Em tratamento → Encerrada (eficácia verificada)**. Prazos: comunicação em até 24 h; investigação preliminar em até 48 h; relatório final de LTI e HiPo em até 30 dias. Investigação com método registrado (5 porquês ou árvore de causas); ações corretivas vão para a Central (origem HSE).

**Privacidade (LGPD):** dados de lesão são dados pessoais sensíveis de saúde. O registro geral guarda função e empresa; nome e dados médicos ficam em campo de acesso restrito. O protótipo usa apenas dados fictícios.

Indicadores (base padrão 1.000.000 de HHT, NBR 14280; base 200.000 da OSHA configurável):

| Indicador | Tipo | Cálculo |
|---|---|---|
| Taxa de frequência com afastamento (TF, LTIF) | Reativo | (Fatalidades + acidentes com afastamento) × 1.000.000 ÷ HHT |
| Taxa de lesões registráveis (TRIF) | Reativo | (Fatalidades + afastamento + trabalho restrito + tratamento médico) × 1.000.000 ÷ HHT |
| Taxa de gravidade (TG) | Reativo | (Dias perdidos + dias debitados) × 1.000.000 ÷ HHT |
| Dias sem acidente com afastamento | Reativo | Dias desde a última LTI; sem LTI registrada, desde o início do projeto |
| Ocorrências de alto potencial (HiPo) | Reativo | Nº no período |
| Incidentes ambientais | Reativo | Nº por severidade |
| Relato de quase acidentes | Proativo | Quase acidentes ÷ lesões registráveis (comparado à proporção da pirâmide; valor baixo indica subnotificação) |
| DDS realizados | Proativo | DDS realizados ÷ programados |
| Observações comportamentais | Proativo | Nº por 10.000 HHT |
| Conformidade em inspeções | Proativo | Itens conformes ÷ itens inspecionados |
| Ações HSE no prazo | Proativo | Ações concluídas no prazo ÷ ações vencidas no período |
| Recomendações de APR/HAZOP fechadas | Proativo | Fechadas ÷ emitidas |

### 08 Governança

Módulo transversal (decisão de 25/09/2026): processos que atravessam todos os módulos. Sem sistema de referência: **todas as telas são novas**, desenhadas pelas boas práticas de controle integrado de mudanças e de gestão do conhecimento (PMBOK e ISO 21502).

**Situação: concluído na etapa 5 (28/09/2026), adiantado antes do 06 a pedido do usuário.** Decisões de implementação:

* Três telas: `mudancas.html` (abas Registro e Painel), `mudanca.html?codigo=` (ficha com abas Solicitação, Análise de impacto, Decisão, Implementação e Histórico, com a barra de etapas do fluxo) e `licoes.html` (abas Acervo e Painel). Modais em `GI.gov` (`js/pages/governanca/governanca.js`); regras, alçada, prazos e integrações só em `GI.api.governanca`.
* **Alçada:** a api calcula a alçada mínima (`GI.regras.alcadaMudanca`): Gerente do projeto quando o custo (em módulo) cabe em `mudancas.alcadaGerentePctOrcamento` do orçamento **e** a mudança não afeta marco contratual; senão, Comitê. O analista pode elevar ao Comitê, nunca rebaixar (no mock, SM-0004 e SM-0006 foram elevadas). Comitê exige quórum (`quorumComite`, 3); alçada do gerente exige o gerente do projeto como decisor. Registrar a decisão exige papel Gestor.
* **Status "Aguardando comitê"** vale para as duas alçadas (lista fixa da especificação); a coluna Próxima etapa diz quem decide.
* **Emergencial:** a execução antecipada é marcada no registro (início e justificativa); a decisão seguinte é a ratificação, com prazo `ratificacaoDias` (7) a partir do início; vencido, vira alerta na Home e na ficha.
* **Análise de impacto** obrigatória: custo (centavos, negativo para redução), prazo (dias no caminho crítico, negativo para antecipação), marco contratual, escopo, qualidade, riscos, SMS, contrato (texto, "Sem impacto" quando não afeta), itens da EAC validados contra a EAC (nível 3) e atividades do cronograma. Fonte do recurso (aditivo de orçamento ou reserva de contingência) obrigatória com custo positivo; a decisão recusa aprovação acima do saldo da reserva.
* **Aprovação gera** ações de implementação na Central (origem Mudança), sugeridas pela análise (EAC, linha de base e Curva S, aditivo, riscos, SMS, qualidade) com responsável pela função e prazo `prazoAcoesDias` (15); o custo aprovado aparece como SM pendente na EAC (03), que já gerava a nova revisão a partir de SM aprovada.
* **Encerramento** (Gestor) recusa enquanto houver ação de implementação aberta ou custo não incorporado à EAC (conferido pela revisão com a SM); cronograma e Curva S, aditivo e riscos são confirmações obrigatórias quando a análise apontou impacto. Lição aprendida opcional, criada em Rascunho com origem na SM.
* Adiada volta à pauta por "Reapresentar" (a decisão anterior fica em `decisoesAnteriores`); Rejeitada e Cancelada são terminais; cancelamento só pelo solicitante ou Gestor, antes da decisão. Mudança já aprovada não se cancela: registra-se nova SM para reverter.
* **Lições:** fluxo Rascunho → Em validação → Validada → Publicada; validador é Gestor e não pode ser o autor (segregação de funções); devolução volta a Rascunho com comentário. **Aplicabilidade** Projeto ou Corporativa (a lição de Projeto aparece no projeto e no Portfólio; a Corporativa marca a lição para o acervo da organização). Painel com "Dias desde a última lição" (alerta pelo parâmetro de 90 dias) e "Lições por situação".
* **Origem rastreável:** o tipo de origem (Ata, Punch list, Contrato ou claim, Suprimentos, Risco, RNC, Ocorrência HSE, Mudança, Workshop, Encerramento do projeto, Registro direto) exige o número do registro quando é de módulo, e a api confere que ele existe; o cartão e a ficha levam ao registro de origem. "Avaliação de fornecedor (03)" da especificação foi generalizada para "Contrato ou claim (03)", porque o acervo já tinha lição de claim.
* **Aplicar em projeto:** registra o reuso (projeto, data, como) e pode criar ação na Central (origem Lição) ou risco Identificado no 05 (ameaça para "A evitar", oportunidade para "A repetir", origem Lições aprendidas). Checklist de kickoff no Acervo: botões por fase filtram as lições publicadas daquela fase.
* Painel de mudanças: situação, Pareto por origem (tabela com percentual acumulado), valor e prazo aprovados acumulados por mês (linhas sem suavização), tipo, taxa de aprovação (sem as adiadas), tempo médio de decisão e consumo da reserva de contingência. Painel de lições: por fase e área (a repetir e a evitar), publicadas nos últimos `licoes.alertaSemRegistroDias` (90), taxa de reuso, projetos sem registro no período e lições mais reusadas.
* Tabela do registro cabe em 1440px sem rolagem: Tipo e origem numa coluna; custo e prazo com o título curto e a explicação no subtítulo do cartão.
* Tradução: bloco próprio no `en.js` (padrões na frente). "Encerramento" passou a "Closure" (antes "Closing date", só usado no rótulo de data do 04, que continua correto); SM aparece como "CR" nos textos em inglês (os códigos SM-TN-... são dados).

#### Gestão de Mudanças (controle de mudanças do projeto)

Escopo: mudanças de escopo, prazo, custo, qualidade/especificação e contrato. **Não inclui** o MOC de segurança de processo (SMS).

| Tela | Arquivo | Conteúdo | Situação |
|---|---|---|---|
| Registro de mudanças | `modulos/governanca/mudancas.html` | Abas Registro e Painel; KPIs (em análise, aguardando comitê, aprovadas no período, valor aprovado acumulado e % do orçamento, impacto de prazo acumulado, tempo médio de decisão); colunas Nº, Título, Tipo, Origem, Impacto em custo, Impacto em prazo, Situação, Próxima etapa | Nova |
| Ficha da mudança | `modulos/governanca/mudanca.html` | Abas Solicitação, Análise de impacto, Decisão, Implementação, Histórico | Nova |
| Modais | nas telas acima | Nova solicitação, Análise de impacto, Decisão do comitê, Encerramento, Filtros | Nova |

Regras (controle integrado de mudanças):

* Numeração `SM-TN-2026-0001`. Toda mudança nasce como solicitação formal; nada altera linha de base sem SM aprovada.
* **Remanejamento de orçamento (01/10/2026):** tipo próprio de SM com as transferências entre itens da EAC (repetíveis no formulário; abertas também pelo 03). Impacto em custo zero; alçada pelo valor remanejado; aprovação aplica na EAC; ficha mostra origem, destino, valor e saldo livre.
* Fontes do recurso: aditivo de orçamento, reserva de contingência e reserva gerencial (só Comitê); saldo da reserva conferido na análise e na decisão.
* **Liberação de reserva (01/10/2026):** tipo de SM com a reserva (contingência ou gerencial) e o valor; impacto em custo zero; alçada sempre Comitê; a aprovação registra a liberação na reserva (03 Contingência).
* Classificação: tipo (Escopo, Prazo, Custo, Qualidade/Especificação, Contratual, Remanejamento de orçamento, Liberação de reserva); origem (Cliente, Contratada, Engenharia, Interna, Legal/regulatória); prioridade (Normal, Urgente, Emergencial).
* Fluxo: **Registrada → Em análise de impacto → Aguardando comitê → Aprovada / Aprovada com condições / Rejeitada / Adiada → Em implementação → Encerrada**. Cancelamento a pedido do solicitante com justificativa.
* Análise de impacto obrigatória antes do comitê: escopo, prazo (dias no caminho crítico), custo (centavos), qualidade, riscos novos ou alterados, SMS e contrato; itens da EAC e atividades do cronograma afetados.
* Alçada de aprovação por impacto (valores de exemplo, configuráveis): custo até 1% do orçamento ou prazo sem impacto em marco contratual, Gerente do projeto; acima disso, Comitê de Controle de Mudanças (patrocinador, cliente, planejamento, custos).
* Mudança emergencial pode ser executada antes do comitê, com registro imediato e ratificação obrigatória na reunião seguinte.
* Decisão registra participantes, data, justificativa e condições (ata do comitê opcional, vinculada ao módulo 01).
* Aprovada gera: nova revisão da EAC (03), nova linha de base do cronograma e Curva S (02), aditivo de contrato quando houver (03), revisão dos riscos afetados (05) e ações de implementação na Central (origem Mudança).
* Encerramento exige confirmação de que as linhas de base foram atualizadas e o registro da lição aprendida quando houver.
* Painel: mudanças por situação e por origem (Pareto), valor aprovado acumulado por mês, impacto de prazo acumulado, tempo médio de decisão, taxa de aprovação.

#### Lições Aprendidas

| Tela | Arquivo | Conteúdo | Situação |
|---|---|---|---|
| Acervo de lições | `modulos/governanca/licoes.html` | Abas Acervo e Painel; busca por palavra-chave e filtros (fase, área de conhecimento, disciplina, tipo, origem, aplicabilidade); cartões com situação, recomendação e aplicabilidade | Nova |
| Modais | na tela acima | Nova lição, Validação, Aplicar em projeto, Filtros | Nova |

Regras (gestão do conhecimento):

* Numeração `LA-TN-2026-0001`. Registro contínuo durante todo o ciclo de vida, não só no encerramento.
* Campos: título, tipo (**A repetir**: boa prática; **A evitar**: problema), fase (Iniciação, Engenharia, Suprimentos, Construção, Comissionamento, Encerramento), área de conhecimento (Escopo, Cronograma, Custos, Qualidade, Recursos, Comunicações, Riscos, Aquisições, Partes interessadas, SMS), disciplina, o que aconteceu, causa, impacto (prazo em dias e custo em centavos), recomendação, palavras-chave, autor.
* Origem rastreável: Risco encerrado (05), RNC (06), Ocorrência HSE (07), Mudança (08), Avaliação de fornecedor (03), Ata (01), Punch list (02), Workshop de lições, Encerramento do projeto; com vínculo ao registro de origem.
* Fluxo: **Rascunho → Em validação → Validada → Publicada no acervo**; validação pelo PMO ou pela gerência do projeto. Lição rejeitada volta ao autor com comentário.
* Aplicabilidade: Projeto (restrita ao projeto) ou Corporativa (compartilhada com a organização para os próximos projetos).
* "Aplicar em projeto" registra o reuso (qual projeto, quando, como) e pode gerar ação na Central (origem Lição) ou risco no registro (05).
* Consulta ao acervo recomendada no início de cada projeto e de cada fase (checklist de kickoff).
* Painel: lições por fase, área e tipo; publicadas no período; taxa de reuso; projetos sem registro nos últimos 90 dias.

---

## 4. Fontes de referência consultadas

| Fonte | Uso |
|---|---|
| `Sistema Gestão\Cores Padrões - MODELO BI - Rev.00.pdf` | Paleta e tipografia (prevalece) |
| `Sistema Gestão\Programação semanal\Cores_Padroes_MODELO_BI_Rev00.md` | Conferência (divergências em 2.5) |
| `Sistema Gestão\Logos\` | Logos horizontal, ícone e vertical |
| `Sistema Gestão Integrada\Sistema\Gestão Integrada\` (`app\`, `GI_README.md`, `PARIDADE_ATA_E_CONFIGURACOES.md`, `handover.md`) | Campos, fluxos e regras da Central de Ações e Atas |
| `Sistema Gestão\Programação semanal\` (`prototipo_programacao_semanal.html`, `PROMPT_...md`, `App_McCain_Programação_Semanal.pdf`) | Programação Semanal |
| `Sistema Gestão Integrada\Módulo de Riscos\mockups\` | Gestão de Riscos |

A pasta `Legado\` **não** foi lida nem referenciada. Nenhum arquivo fora desta pasta (`Sistema\`) foi alterado.

---

## 5. Bibliotecas (cópias locais em `assets/vendor/`)

| Biblioteca | Versão | Arquivo | Uso |
|---|---|---|---|
| Chart.js | 4.5.1 | `chart.umd.min.js` | Gráficos, cores lidas das variáveis CSS |
| SheetJS (xlsx) | 0.18.5 | `xlsx.full.min.js` | Exportar `.xlsx` e pré-visualizar planilhas |
| jsPDF | 4.2.1 | `jspdf.umd.min.js` | Exportar PDF |
| jsPDF-AutoTable | 5.0.8 | `jspdf.plugin.autotable.min.js` | Tabelas no PDF |
| Montserrat, Roboto (Fontsource, OFL) | 5.3.0 | `fonts/*.woff2` e `css/fonts.css` | Tipografia offline |

**Risco registrado (SheetJS):** a versão publicada no npm (0.18.5) tem vulnerabilidades conhecidas na **leitura** de arquivos maliciosos (CVE-2023-30533, poluição de protótipo; CVE-2024-22363, ReDoS). A versão corrigida (0.20.3) só é distribuída por `cdn.sheetjs.com`, bloqueado na rede desta sessão. No protótipo o risco é baixo (arquivos lidos só em memória, na máquina do próprio usuário, sem envio), mas **antes de produção** substituir por `https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js`.

---

## 6. Design system

| Arquivo | Conteúdo |
|---|---|
| `css/fonts.css` | `@font-face` com as fontes embutidas |
| `css/tokens.css` | Única origem de cor: paleta oficial, derivadas, semânticas; tipografia, espaçamentos, raios, sombras, camadas |
| `css/components.css` | Botões pílula, cards, KPI tiles, tabelas, badges, formulários, modais, abas, upload, alertas, toasts, progresso, etapas, kanban, matriz, mapa de calor financeiro |
| `css/layout.css` | Grade, header, sidebar, gaveta mobile, breakpoints (≤480, ≤768, ≤1024, >1024) |
| `js/components/icons.js` | Ícones SVG em linha (`stroke: currentColor`, sem cor própria) |
| `js/components/modal.js` | Abrir/fechar modal (ESC, fundo, foco preso) |
| `js/components/charts.js` | Chart.js com cores lidas de `tokens.css` (linhas, barras, Curva S física e financeira, cascata, pirâmide) |
| `js/components/ui.js` | Abas, controle segmentado, contador de caracteres, avisos (toast) e formatação no idioma ativo (`GI.fmt`: moeda, moeda compacta, índice, %, número, data; pt-BR ou en-US) |
| `js/components/comum.js` | Utilitários das telas (`GI.util`): nomes a partir dos cadastros, badges, KPIs, links entre módulos, busca sem acento |
| `js/components/tabela.js` | Tabela com ordenação, paginação, colunas configuráveis, rodapé de totais e modo empilhado no mobile |
| `js/components/exportar.js` | Exportação Excel (SheetJS) e PDF (jsPDF + AutoTable) de toda tabela e painel, com logo, contexto e cores dos tokens; bibliotecas carregadas só no primeiro uso. Opções: `formato: "a3"` e, por tabela, `corCelula(linha, coluna)` (fundo e texto por token) e `fonte` (usadas no PDF do MAS) |
| `js/components/formulario.js` | Formulários em modal (texto, lista, data, hora, número, moeda em centavos, múltipla escolha, arquivo, grupo repetível `repetir`, HTML `antes` entre o rótulo e o controle) com validação, campos condicionais (`mostrarSe`) e campos calculados (`aoMudar`) |
| `js/pages/financeiro/financeiro.js` | Apoio do módulo 03 (`GI.fin`): projeto da tela, valores em R$ mil, mapa de calor, árvore da EAC e da EAP (com a linha resumo do projeto, código 0), selos de situação e classe |
| `js/pages/suprimentos/suprimentos.js` | Apoio do módulo 04 (`GI.sup`): projeto da tela, selos de etapa, folga, situação e qualificação, célula e legenda do MAS, data curta, links entre telas |
| `js/pages/riscos/riscos.js` | Apoio do módulo 05 (`GI.rsk`): projeto da tela, contexto, selos de severidade e situação, cadência e os modais 10 a 17 (novo, avaliação, plano, aprovação, ação, revisão, encerramento, reabertura e exclusão) |
| `js/components/upload.js` e `importar.js` | Upload de anexos e importação de planilha em 5 passos (upload, validação, pré-visualização, confirmação, inserção) com modelo para baixar |
| `relatorio.html`, `css/relatorio.css` e `js/pages/relatorio.js` | Relatório gerencial: página própria (sem menu) com folhas A4 na horizontal, impressão (`@page`), encaixe da fonte e exportação Excel |
| `js/components/analise.js` | Análise do período (GI.analise): modal em dois passos (período; texto e comentário de cada desvio negativo), ligação automática dos botões `data-analise`, abertura por `?analise=1` e texto dos desvios no idioma ativo (usado também no relatório) |
| `js/pages/planejamento/relato.js` | Relato do período (02): tabela, KPIs e modais novo, editar, ver e excluir |
| `js/i18n.js` e `js/i18n/en.js` | Idiomas: motor de tradução e dicionário inglês (ver 6.2) |
| `js/siglas.js` | Dica das siglas ao parar o mouse (glossário bilíngue) |
| `js/layout.js` | Header (com seletor PT/IN), sidebar, gaveta mobile, abas do módulo e ajuste da barra da página, montados a partir de uma única lista de navegação |

**Siglas (01/10/2026):** `js/siglas.js` (carregado em todas as páginas logo após o dicionário) mostra uma janela com o significado e a função de cada sigla ao parar o mouse sobre ela (SPI, CPI, FP, CP, HH, EAC, VME, RNC, TF, S39 e outras) e esconde ao tirar o mouse; no celular, um toque abre e outro fecha. Não altera o DOM das telas: localiza a palavra sob o ponteiro (`caretRangeFromPoint`) e sublinha as siglas do conteúdo com a Highlight API do CSS. Glossário bilíngue (forma PT e EN de cada sigla) e padrões para semana ISO, níveis P/I da matriz e níveis N da pirâmide. Nova sigla: uma linha na lista `LISTA`. Limitação: textos dentro de gráficos (canvas) e de listas de seleção não têm a dica.

**Cards com referência (01/10/2026):** todo card com valor mostra, logo abaixo do valor, a referência de gestão (`esperado` em `GI.util.kpi`, no relatório e na Home): Previsto, Meta, Linha de base, Orçado, Limite, Esperado (ex.: zero para atrasos e lesões), Mês anterior ou Referência. A exportação Excel e PDF leva a referência.

Regras: botões e controles de ação sempre pílula (`border-radius: 999px`); nenhuma cor hexadecimal fora de `tokens.css`; alvo de toque mínimo de 44px em dispositivos de toque (`pointer: coarse`); no mouse, botões pequenos têm 36px.

### 6.1 Estrutura de páginas e pastas

```
Sistema/
├── index.html                 Home
├── styleguide.html            Design system
├── README.md
├── HANDOVER.md                Resumo para retomar o trabalho em outro chat
├── _dev/                      Gerador de páginas e scripts de teste (não carregados pelas telas)
├── assets/logos/              Logos oficiais (horizontal, ícone, vertical)
├── assets/vendor/             Chart.js, SheetJS, jsPDF, AutoTable e fontes (cópias locais)
├── css/                       fonts, tokens, layout, components
├── data/                      mock-config (parâmetros e data de referência), mock-base (cadastros) e um mock por módulo
├── js/layout.js               Estrutura comum de todas as páginas
├── js/services/regras.js      Regras de negócio puras
├── js/services/api.js         Fachada de dados (única porta de acesso aos dados)
├── js/i18n.js, js/i18n/en.js   Idiomas (motor e dicionário inglês)
├── js/components/             icons, ui, modal, comum, tabela, exportar, formulario, upload, importar, charts, logo-pdf
├── js/pages/                  Script de cada tela (home.js e uma pasta por módulo)
└── modulos/<módulo>/<tela>.html
```

Contrato de cada página: `<body data-root="../../" data-page="modulo/tela">` e `<div class="app"><main class="app-main" id="conteudo"><div class="container">...</div></main></div>`. Dentro do container, **sem título visível no topo** (o header já mostra módulo e tela): `<h1 class="sr-only">` para leitores de tela e, em seguida, a **barra da página** `<div class="page-bar">` com as abas do módulo (`<nav data-module-tabs>`) ou o botão Voltar à esquerda e as ações da página (`<div class="page-actions">`) à direita, na mesma linha. Quando não cabem, a barra entra em modo compacto (menos respiro e a palavra "Exportar" oculta nos botões de exportação); se ainda assim não couber, as ações descem para a linha de baixo, alinhadas à direita. Até 768px, abas e ações ficam empilhadas em largura total. Telas de detalhe acrescentam o registro ao contexto do header com `GI.layout.detalhe("Ata TN-2026-0028 Rev 0")`. O `layout.js` insere header, sidebar, fundo da gaveta e link "Pular para o conteúdo", destaca o item ativo e preenche `<nav data-module-tabs>` com as telas do módulo. Comportamento: acima de 1024px a sidebar pode recolher para um trilho de ícones (preferência salva); de 769 a 1024px fica em trilho e abre sobreposta (fecha com ESC ou clique fora); até 768px vira gaveta com fundo escurecido e foco preso.

### 6.2 Idiomas (português e inglês)

* **Seletor:** botão segmentado **PT | IN** no header, ao lado do usuário (rótulo "IN" conforme pedido; o código ISO do inglês é EN, troca de uma linha em `layout.js`). A escolha fica em `localStorage` (`gi.idioma`) e a página recarrega no idioma novo.
* **Como funciona:** o português é o texto-fonte das telas. `js/i18n.js` percorre a página (textos e atributos `aria-label`, `title`, `placeholder`, `data-label`, `alt`) e observa o que as telas montam depois (tabelas, modais, avisos), trocando cada texto pelo equivalente do dicionário `js/i18n/en.js`: entradas exatas, padrões para textos montados ("Mostrando 1 a 10 de 32", "8 dias de atraso") e regra de número + unidade. Gráficos, Excel e PDF usam o mesmo dicionário (`GI.t`). Datas, números e moeda seguem o idioma (pt-BR ou en-US; a moeda continua R$).
* **O que não é traduzido:** dados cadastrados pelos usuários (títulos de ações, nomes, descrições, empresas), o nome do sistema e o `styleguide.html` (referência técnica do design system, só em português). Telas ainda em construção (etapa 5) mostram o conteúdo previsto em português até serem construídas.
* **Para uma nova tela:** escrever os textos em português normalmente e acrescentar as traduções em `js/i18n/en.js`. Trechos que não devem ser traduzidos levam `data-sem-traducao`.
* **No backend:** o mesmo dicionário vira arquivo de recursos (ex.: `pt-BR.json`, `en-US.json`) e os textos passam a sair por chave; os dados dos usuários continuam no idioma em que foram cadastrados.

---

## 7. Camada de dados e integração futura com o backend

### 7.1 Como os dados fluem

* Tela → `GI.api` (`js/services/api.js`) → hoje `window.MOCK` (`data/mock-*.js`); na fase com backend, endpoints REST. **Nenhuma tela lê `window.MOCK` diretamente**; trocar o mock pela API altera só `api.js`.
* Regras de negócio puras em `js/services/regras.js` (status da ação, severidade do risco, faixa de desvio de custo, taxas de HSE, nível da pirâmide, avaliação da contratada, validação de parâmetros). No backend, as mesmas regras rodam também no servidor.
* Métodos de dados devolvem `Promise` com cópias; erro de validação volta como `{ erros: [...] }`. Síncronos só `sessaoAtual()`, `referencia()` e `projetoAtualId()` (virão do token da sessão).
* Valores financeiros em centavos (inteiros); datas em ISO (AAAA-MM-DD). Nada é formatado na camada de dados.
* Cada ponto de troca está marcado no código com `TODO: API` e o endpoint sugerido.

### 7.2 Métodos da fachada e endpoints sugeridos

| Método (`GI.api`) | Endpoint sugerido | Observação |
|---|---|---|
| `sessaoAtual()`, `projetoAtualId()`, `referencia()` | token e bootstrap da sessão | Nome, papel, projeto e data do servidor |
| `listar`, `obter`, `salvar`, `excluir` (coleção) | `GET/POST/PUT/DELETE /{colecao}` | CRUD genérico; exclusão lógica no backend |
| `proximoCodigo(colecao, prefixo)` | numeração no servidor | Evita código duplicado entre usuários |
| `cadastros()` | `GET /cadastros` | Clientes, projeto, empresas, pessoas, sistemas |
| `parametros()`, `salvarParametros()`, `historicoParametros()` | `GET/PUT /parametros`, `GET /parametros/historico` | Só Gestor e Admin gravam (7.4) |
| `central.acoes()`, `central.resumo()` | `GET /acoes` | Status calculado; inclui as ações geradas pela Punch list |
| `planejamento.eap()`, `eapRegistrarAvanco()`, `eapImportarAvanco()`, `eapEditarPacote()`, `eapNovoPacote()`, `eapNovaRevisao()`, `proximoCodigoEap()` | `GET /projetos/{id}/eap`, `POST /eap/{codigo}/medicoes`, `POST /eap/medicoes/lote`, `PUT /eap/{codigo}`, `POST /eap/pacotes`, `POST /eap/revisoes` | Árvore somada pela api (peso, previsto, real, desvio e faixa), revisões, desdobramentos, SMs pendentes com impacto em escopo e conciliação com a Curva S; real sempre calculado pelo critério (`GI.regras.avancoPacoteEap`) |
| `planejamento.relatos()`, `relato()`, `periodosRelato()`, `resumoRelatos()`, `salvarRelato()`, `excluirRelato()` | `GET /projetos/{id}/relatos?tipo`, `GET /relatos/{tipo}/{periodo}`, `GET /relatos/periodos?tipo`, `PUT /projetos/{id}/relatos/{tipo}/{periodo}`, `DELETE /relatos/{id}` | Um por tipo e período; pontos de atenção com risco atrelado sem vínculo com o 05 |
| `planejamento.curvaFisica()`, `punch()`, `resumoPunch()` | `GET /projetos/{id}/curva-fisica`, `/punch` | SPI, aging, sistemas bloqueados |
| `planejamento.produtividade.quantidades()`, `item()`, `salvarItem()`, `aprovarItem()`, `revisarItem()`, `excluirItem()`, `apontar()`, `importarItens()` | `GET /projetos/{id}/produtividade/quantidades?corte&empresa&grupo`, `POST/PUT /produtividade/itens`, `POST /produtividade/itens/{id}/aprovacao`, `/revisoes`, `PUT /produtividade/apontamentos/{semana}` | Distribuição semanal da LB, horas ganhas, SPI, aderência, FP, tendência (earned schedule); revisão só com SM aprovada |
| `planejamento.produtividade.horasEfetivas()`, `salvarJornada()`, `salvarAmostragem()`, `salvarParalisacao()` | `GET /projetos/{id}/produtividade/horas-efetivas?de&ate&empresa&area&encarregado`, `POST/PUT /produtividade/jornadas`, `/amostragens`, `/paralisacoes` | Capacidade produtiva, amostragem do trabalho, Hhora e Mhora |
| `planejamento.produtividade.kpis()`, `gerarAcao()` | `GET /projetos/{id}/produtividade/kpis?corte`, `POST /produtividade/acoes` | Geral e por empresa na janela de N semanas; ação na Central com origem Produtividade |
| `financeiro.mapaControle()`, `curvaFinanceira()`, `indicadores()`, `historicoIndices()` | `GET /projetos/{id}/eac/mapa-controle`, `/curva-financeira`, `/indicadores-custo`, `/valor-agregado` | Totais por pacote, faixa do mapa de calor, valor agregado mês a mês |
| `financeiro.eac()`, `remanejar()`, `novaRevisao()`, `novoItemEac()`, `proximoCodigoEac()` | `GET /projetos/{id}/eac`, `POST /eac/remanejamentos`, `POST /eac/revisoes`, `POST /eac/itens` | Remanejamento de soma zero limitado ao saldo não comprometido; revisão só a partir de SM aprovada |
| `financeiro.importarCustos()`, `atualizarProjecao()` | `POST /projetos/{id}/eac/custos` (ERP), `PUT /eac/itens/{codigo}/projecao` | Fechamento do mês; projeção com justificativa e histórico |
| `financeiro.desembolso()` | `GET /projetos/{id}/desembolso` | Mensal previsto, realizado e projetado; saldo a pagar por item e mês |
| `financeiro.contratos()`, `claims()`, `resumoContratos()`, `consolidadoContratos()`, `contrato(numero)`, `avaliacao()` | `GET /projetos/{id}/contratos`, `/claims`, `/contratos/consolidado`, `GET /contratos/{numero}` | Valor atual, medido, saldo, exposição, fora do prazo, indicadores da administração contratual |
| `financeiro.salvarAditivo()`, `decidirEot()` | `POST /contratos/{id}/aditivos`, `PUT /extensoes-prazo/{id}/decisao` | Aditivo e EOT concedida prorrogam o término vigente |
| `suprimentos.pedidos()`, `indicadores()` | `GET /projetos/{id}/pedidos`, `/indicadores-suprimentos` | Folga em relação ao ROS, situação dos marcos, ação e risco vinculados; OTD, saving, curva de contratação |
| `suprimentos.mas()` | `GET /projetos/{id}/mas` | Mapa de Suprimentos: linhas, marcos com LB, previsão, real e situação, resumo e Curva S de suprimentos |
| `suprimentos.pacotes()`, `salvarPacote()`, `importarPacotes()` | `GET/POST /projetos/{id}/pacotes`, `PUT /pacotes/{id}`, `POST /pacotes/importacao` | LB congelada após a requisição; validação de datas, EAC, ROS e gate LLI |
| `suprimentos.processos()`, `acaoProcesso(pacoteId, acao, dados)` | `GET /projetos/{id}/processos`, `POST /pacotes/{id}/processo/{acao}` | Fluxo da RFx com as regras (mínimo, técnica antes, alçada, saldo da EAC); emissão cria pedido ou contrato e compromete a EAC |
| `suprimentos.atualizarMarco()`, `registrarRecebimento()`, `gerarAcao()`, `registrarRisco()`, `importarPedidos()` | `PUT /pedidos/{id}/marcos/{i}`, `POST /pedidos/{id}/recebimento`, `/acao-central`, `POST /riscos`, `POST /pedidos/importacao` | Folga negativa cria ação na Central; FAT gera inspeção no 06 |
| `suprimentos.fornecedores()`, `salvarQualificacao()`, `novoFornecedor()` | `GET /fornecedores`, `PUT /fornecedores/{id}/qualificacao`, `POST /empresas` | Documentos com validade; desempenho das avaliações do 03 e OTD |
| `riscos.lista(filtro)`, `resumo(filtro)` | `GET /projetos/{id}/riscos`, `/riscos/resumo` | Score, severidade pela escala ativa, VME pela faixa, revisão vencida, pauta de escalonamento; excluídos só para Admin |
| `riscos.matriz(opcoes)`, `painel(filtro)`, `risco(codigo)`, `previa(dados)` | `GET /projetos/{id}/riscos/matriz`, `/projetos/{id}/riscos/painel`, `GET /riscos/{codigo}`, `POST /riscos/score` | Contagem por célula e movimentação; painel do projeto com evolução mensal; ficha com ações, revisões e histórico |
| `riscos.salvar()`, `avaliar()`, `plano()`, `aprovarPlano()`, `novaAcao()` | `POST /projetos/{id}/riscos`, `PUT /riscos/{codigo}`, `PUT /riscos/{codigo}/avaliacao`, `PUT /riscos/{codigo}/plano`, `PUT /riscos/{codigo}/plano/aprovacao`, `POST /riscos/{codigo}/acoes` | Numeração em transação; justificativa quando a severidade muda; regras do plano e da aprovação; ação na Central com origem Risco |
| `riscos.revisar()`, `encerrar()`, `reabrir()`, `excluir()`, `restaurar()`, `categorias()`, `novaCategoria()` | `POST /riscos/{codigo}/revisoes`, `/encerramento`, `/reabertura`, `DELETE /riscos/{codigo}`, `POST /riscos/{codigo}/restauracao`, `GET/POST /cadastros/risco-categorias` | Cadência; encerramento com lição (08), ação e SM quando materializado; exclusão lógica |
| `qualidade.indicadores()` | `GET /projetos/{id}/indicadores-qualidade` | RNC, inspeções, auditorias |
| `hse.indicadores(id, periodo)` | `GET /projetos/{id}/indicadores-hse?inicio&fim` | TF, TRIF, TG, pirâmide, proativos |
| `governanca.resumoMudancas()`, `mudancas(filtro)`, `painelMudancas()`, `mudanca(codigo)` | `GET /projetos/{id}/mudancas/resumo`, `/mudancas`, `/mudancas/painel`, `GET /mudancas/{codigo}` | Etapa, próxima etapa, alçada mínima, prazos, ações, revisão da EAC e aditivos vinculados |
| `governanca.salvarMudanca()`, `iniciarAnalise()`, `salvarAnalise()`, `decidir()`, `reapresentar()`, `iniciarImplementacao()`, `encerrar()`, `cancelar()`, `conferencia()` | `POST /projetos/{id}/mudancas`, `PUT /mudancas/{codigo}`, `POST /mudancas/{codigo}/analise/inicio`, `PUT /mudancas/{codigo}/analise`, `POST /mudancas/{codigo}/decisao`, `/reapresentacao`, `/implementacao`, `/encerramento`, `/cancelamento` | Alçada nunca rebaixada; quórum; saldo da reserva; aprovação cria ações na Central; encerramento confere EAC e ações |
| `governanca.licoes(filtro)`, `licao()`, `painelLicoes()`, `disciplinas()` | `GET /licoes?contexto&...`, `GET /licoes/{codigo}`, `GET /licoes/painel` | Visibilidade pela aplicabilidade; origem e referência calculadas |
| `governanca.salvarLicao()`, `enviarValidacao()`, `validarLicao()`, `publicarLicao()`, `aplicarLicao()` | `POST /licoes`, `PUT /licoes/{codigo}`, `POST /licoes/{codigo}/envio`, `/validacao`, `/publicacao`, `/aplicacoes` | Segregação autor e validador; aplicação cria ação (origem Lição) ou risco no 05 |
| `resumoHome()` | `GET /projetos/{id}/resumo` | Indicadores e pontos de atenção da Home |
| `relatorioGerencial(id, { tipo, periodo, secoes })`, `periodoPadraoRelatorio(tipo)` | `GET /projetos/{id}/relatorio-gerencial?tipo&periodo&secoes` | Consolidado do período (Planejamento com produtividade, relato, Financeiro com tendência, Suprimentos, Riscos, HSE e as análises com os desvios) com as regras de corte da seção 3; no backend, gerar também o PDF no servidor para arquivo |
| `analises.periodo(id, modulo, tipo, periodo)`, `analises.periodos(id, modulo, tipo)`, `analises.situacao(id, tipo, periodo)`, `analises.salvar(id, modulo, { tipo, periodo, analise, desvios })`, `analises.excluir(idAnalise)` | `GET/PUT/DELETE /projetos/{id}/analises/{modulo}/{tipo}/{periodo}` | Análise do período por módulo: desvios negativos calculados no servidor; validação do texto e do comentário de cada desvio (02, 03 e 04) |

### 7.3 Arquivos de dados fictícios

| Arquivo | Conteúdo |
|---|---|
| `data/mock-config.js` | Data de referência e parâmetros configuráveis (versão 1) |
| `data/mock-base.js` | Sessão, cliente, projetos (TN-2026-014 fábrica, TN-2026-021 caldeira de biomassa, TN-2026-027 torre de resfriamento, com notas de ponderação), empresas e pessoas |
| `data/mock-portfolio.js` | Dados dos projetos TN-2026-021 e TN-2026-027 em todos os módulos (Curva S, EAP, EAC, contratos, pacotes, pedidos, riscos, HSE, mudanças, lições, relatos) e análises do período do Portfólio (S38 e agosto) |
| `data/mock-central.js` | Atas e ações de todas as origens |
| `data/mock-planejamento.js` | Curva S física, avanço por área, EAP (38 pacotes, revisões e desdobramentos), sistemas, Punch list, 6WLA, Programação Semanal, Relato do período (3 semanais e 2 mensais), análises do período do 02 (S37, S38 e agosto) e Produtividade (plano de quantidades com distribuição semanal e apontamentos, jornadas, amostragens e paralisações geradas com semente fixa) |
| `data/mock-financeiro.js` | EAC (3 níveis), revisões, remanejamentos (com a SM de referência), reservas de contingência e gerencial (constituição e base de cálculo), Curva S financeira, contratos, aditivos, medições, marcos, claims, extensões de prazo e avaliações; análises do período do módulo (S38 e agosto) |
| `data/mock-suprimentos.js` | Plano de compras (LB, previsão e real dos 7 marcos de aquisição), pedidos com marcos de fabricação (LB contratual, previsão e realizado), processos de RFx (PC-14 em equalização comercial, PC-SE-02 com RFx emitida, PC-12 encerrado com mapa completo) e qualificação de fornecedores com documentos; análises do período do módulo (S38 e agosto) |
| `data/mock-riscos.js` | Catálogo RBS (`riscoCategorias`); riscos RSK-TN-2026-0001 a 0009 (7 ativos e 2 encerrados) e RSK-TN-2026-SE-0001 a 0004, com dimensões, plano, aprovação, revisões e histórico; evolução mensal do score residual das ameaças; análises do período do módulo (S38 e agosto) |
| `data/mock-qualidade.js` | RNC (com contenção, responsável, disposição, concessão e eficácia), ITP com pontos H, W e R (TN-CIV, MEC, TUB, ELE aprovados; INS em aprovação), 20 inspeções (série de junho a setembro), programa de auditorias com constatações e análises do período do 06 (S38 e agosto) |
| `data/mock-hse.js` | HHT por mês e empresa (o histograma de mão de obra previsto, `histogramaMaoDeObra`, é gerado no fim de `mock-portfolio.js` a partir do HHT e da Curva S física, como linha de base de recursos), ocorrências (geradas com semente fixa), consolidado mensal e APR/HAZOP; análises do período do módulo (S38 e agosto) |
| `data/mock-governanca.js` | Solicitações de mudança SM-TN-2026-0001 a 0011 (4 encerradas, das quais 0009 e 0010 são remanejamentos aplicados na EAC; 1 em implementação, 3 aguardando comitê, 2 em análise, entre elas o remanejamento 0011 de R$ 250 mil da montagem mecânica para as fundações; 1 rejeitada) com análise de impacto e decisão; lições LA-TN-2026-0001 a 0008 (4 publicadas, 1 validada, 1 em validação, 2 rascunhos) |

Os números fecham entre si: orçado atual da EAC = orçamento do projeto (R$ 44,6 mi); comprometido e realizado dos contratos = colunas da EAC dos itens contratados; CPI 0,96 e SPI 0,94 saem da Curva S física e do realizado financeiro; a pirâmide HSE soma 0, 16, 31, 190 e 1.240 ocorrências por nível (nenhuma lesão grave no cenário).

### 7.4 Parâmetros configuráveis (avaliação de 25/09/2026)

Pedido: usar os valores propostos para os pesos da avaliação de contratadas e os prazos de investigação de HSE, avaliando um campo de configuração para alterá-los.

**Conclusão: viável e recomendado.** Os valores deixam de ficar fixos no código e passam a ser parâmetros com versão. Já está pronto na etapa 4: a estrutura (`MOCK.parametros`), a validação (`GI.regras.validarParametros`) e a gravação com versão (`GI.api.salvarParametros`); a tela `Configurações > Parâmetros` entra na etapa 5, depois do módulo 08.

| Grupo | Parâmetro | Valor inicial | Onde é usado |
|---|---|---|---|
| Avaliação de contratadas | Pesos: HSE, Qualidade, Prazo, Gestão, Recursos, Documentação | 25, 20, 20, 15, 10, 10 (soma 100) | 03 Contratos |
| Avaliação de contratadas | Nota mínima das classes A, B, C, D | 85, 70, 50, 0 | 03 Contratos, 04 Fornecedores |
| Avaliação de contratadas | Nota que exige plano de melhoria | 2 ou menos | 03 Contratos, 01 Central |
| HSE | Prazos de comunicação, investigação preliminar e relatório final | 24 h, 48 h, 30 dias | 07 Ocorrências |
| HSE | Base das taxas | 1.000.000 HHT (NBR 14280); opção 200.000 (OSHA) | 07 Painel |
| HSE | Proporção de referência da pirâmide | Bird (opção Heinrich) | 07 Painel |
| Riscos | Escala de severidade ativa | Timenow 4 faixas (opção CIPM 3 faixas) | 05 Riscos, Home |
| Riscos | Cadência máxima de revisão por faixa | Crítico 15, alto 30, moderado 60, baixo 90 dias | 05 Revisão periódica e pauta |
| Riscos | Probabilidade média por faixa (base do VME) | 5, 20, 40, 60 e 85% | 05 Avaliação, Painel, Home |
| Riscos | Pauta: dias antes do prazo do alvo; alerta de revisão | 30 dias; 15 dias | 05 Painel e Registro |
| Financeiro | Faixas do mapa de calor do desvio | 1%, 5%, 10% | 03 Mapa de controle |
| Financeiro | Contingência: tolerância do consumo acima do avanço físico; cobertura mínima da exposição a riscos | 10 p.p.; 100% | 03 Contingência, Mapa de controle, relatório gerencial |
| Suprimentos | Propostas mínimas; folga de alerta | 3; 7 dias | 04 Processos, Diligenciamento, MAS |
| Suprimentos | Alçadas de aprovação da adjudicação | até R$ 500 mil Gerente de suprimentos; até R$ 5 mi Gerente do projeto; acima, Comitê de investimentos | 04 Processos |
| Suprimentos | Pesos dos marcos do MAS (critério de medição) | Requisição, RFx, propostas, equalização técnica e comercial, aprovação 5 cada; pedido 10; documentos 10; fabricação 30; inspeção/FAT 10; embarque 5; entrega 5 (soma 100) | 04 MAS e Painel |
| Punch list | Faixas de tempo em aberto | 7 e 30 dias | 02 Punch list |
| Produtividade | Jornada diária de referência; metas de % trabalhando e de utilização da jornada | 8,8 h (44 h em 5 dias); 60%; 75% | 02 Produtividade (horas efetivas e KPIs) |
| Produtividade | Faixas da aderência semanal; faixas do fator de produtividade; janela da média móvel | 75% e 90%; 1,00 e 1,10; 4 semanas | 02 Produtividade (quantidades e KPIs) |
| Produtividade | Faixas do SPI de quantidades; faixas do atraso médio de início (01/10/2026) | 0,85 e 0,95; 15 e 30 min | 02 Produtividade (cores e referência dos cards) |
| HSE | Metas proativas por 10 mil HHT: observações comportamentais; relato de desvios (01/10/2026) | 40; 12 | 07 Inspeções e observações, Painel HSE, relatório gerencial |
| Mudanças | Alçada do gerente do projeto | até 1% do orçamento e sem impacto em marco contratual | 08 Mudanças (análise e decisão) |
| Mudanças | Prazo padrão da análise; quórum do Comitê; prazo das ações de implementação; ratificação da emergencial | 10 dias; 3 participantes; 15 dias; 7 dias | 08 Mudanças |
| Lições | Alerta de projeto sem lição registrada | 90 dias | 08 Lições (Painel) |
| EAP | Faixas de desvio físico; peso máximo por pacote; peso máximo com percentual estimado | −2 e −5 p.p.; 10%; 5% | 02 EAP |
| EAP | Modelos de etapas do critério de medição (cada modelo soma 100) | Engenharia, Suprimentos, Montagem de equipamentos, Montagem de painéis, Comissionamento | 02 EAP (pacote novo copia as etapas) |
| Qualidade | Prazo de tratamento da RNC por severidade; espera da verificação de eficácia | Crítica 15, Maior 30, Menor 45 dias; 30 dias | 06 RNC |
| Qualidade | Metas de aprovação em inspeções e de conformidade em auditorias; antecedência da notificação ao cliente (H e W) | 95%; 90%; 48 horas | 06 Painel, Inspeções e Auditorias, relatório gerencial |
| Portfólio | Critérios de ponderação da carteira (soma 100) | Valor financeiro 60, criticidade estratégica 25, complexidade e exposição a risco 15 | Início, Curvas S e índices da carteira |

Regras propostas (boas práticas de governança de dados):

* Acesso: só Gestor e Admin veem o item no menu, e a gravação é recusada para os demais papéis (no backend, a mesma checagem no servidor).
* Cada gravação cria **nova versão** com início de vigência, autor e justificativa obrigatória; o histórico fica consultável.
* **Efeito daqui em diante:** pesos e prazos valem para registros novos. Avaliações já feitas guardam os pesos usados (a nota não muda); ocorrências guardam o prazo vigente no registro. Base das taxas, referência da pirâmide, escala de severidade e faixas do mapa de calor são critérios de exibição e recalculam as telas na hora; a troca de escala de riscos pede confirmação, porque muda a contagem de críticos em todo o sistema.
* Validações antes de gravar: cadência de revisão crescente da faixa mais grave para a mais leve; probabilidades médias crescentes entre 0 e 100%; pesos somam 100%; notas mínimas decrescentes de A para D; investigação preliminar não vence antes da comunicação; base das taxas 1.000.000 ou 200.000; pesos do MAS somam 100; alçadas de suprimentos com tetos crescentes e a última sem teto; alçada do gerente entre 0 e 10% do orçamento; quórum do Comitê de 2 ou mais; prazos de mudanças entre 1 e 90 dias; alerta de lições entre 30 e 365 dias; jornada de referência entre 4 e 12 h; metas de produtividade entre 0 e 100%; faixas de aderência e do fator de produtividade crescentes; janela da média entre 1 e 12 semanas; prazos de tratamento da RNC crescentes de Crítica para Menor (1 a 180 dias); espera da verificação entre 0 e 180 dias; metas da qualidade entre 0 e 100%; antecedência da notificação entre 0 e 240 horas; critérios do portfólio somando 100.

## 8. Telas propostas

Etapa 5 concluída em 30/09/2026. Os módulos 03 Gestão Financeira, 04 Suprimentos (inclusive o MAS), 06 Gestão da Qualidade, 07 HSE e 08 Governança, o Punch list e Configurações > Parâmetros são telas **novas**, definidas pelas boas práticas descritas no inventário (seção 3).

### Integração entre módulos (fluxos previstos)

| De | Evento | Para |
|---|---|---|
| 02 Punch list | Item aberto | 01 Central (ação, origem Punch list) |
| 02 Cronograma | Data necessária na obra (ROS) | 04 Diligenciamento (folga do pedido) |
| 04 Suprimentos | Pacote adjudicado | 03 Contratos (novo contrato) e 03 EAC (comprometido) |
| 04 Suprimentos | Pedido com folga negativa ou item LLI | 05 Riscos (risco de suprimento) e 01 Central (ação, origem Suprimentos) |
| 04 Suprimentos | Inspeção em fábrica (FAT) | 06 Qualidade (inspeção) |
| 04 Suprimentos | Processo, plano e diligenciamento | 04 MAS (montado, sem digitação própria) |
| 03 Contratos | Medição aprovada | 03 EAC (realizado) e Cronograma de desembolso |
| 03 Contratos | Claim acordado ou EOT concedida | 08 Mudanças (SM para linha de base e aditivo) |
| 03 Contratos | Avaliação final da contratada | 04 Fornecedores (qualificação) e 08 Lições (lição de fornecedor) |
| 05 Riscos | Risco materializado | 01 Central (ações) e 08 Mudanças (se exigir alterar linha de base) |
| 05 Riscos | Risco encerrado | 08 Lições (lição obrigatória) |
| 06 Qualidade | RNC encerrada | 08 Lições |
| 07 HSE | Ocorrência ou recomendação de APR/HAZOP | 01 Central (ação corretiva, origem HSE) |
| 07 HSE | Ocorrência de alto potencial encerrada | 08 Lições (lição obrigatória) |
| 07 HSE | Nota HSE da contratada | 03 Avaliação de desempenho (critério HSE) |
| 08 Mudanças | SM aprovada | 03 EAC (nova revisão), 03 Contratos (aditivo), 02 Linha de base e Curva S, 05 Riscos, 01 Central (ações de implementação) |
| 08 Lições | Aplicar em projeto | 01 Central (ação, origem Lição) ou 05 Riscos (novo risco) |
