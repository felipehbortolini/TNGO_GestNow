/* ==========================================================================
   siglas.js | Dica das siglas em todas as telas (GI.siglas).

   Ao parar o mouse sobre uma sigla (SPI, FP, CP, HH...), abre uma janela
   com o significado e para que serve; ao tirar o mouse, a janela some.
   No toque (celular), um toque na sigla abre a dica e outro toque fecha.
   Não altera o DOM das telas (o tradutor de DOM do i18n continua igual):
   a palavra sob o ponteiro é localizada por caretRangeFromPoint. As siglas
   no conteúdo ganham sublinhado pontilhado pela Highlight API do CSS
   (sem envolver o texto em elementos).
   Glossário bilíngue: cada sigla tem a forma em português e em inglês; a
   dica sai no idioma da tela, qualquer que seja a forma exibida.
   Regras por padrão: semana ISO (S39 ou W39), níveis P1 a P5 e I1 a I5 da
   matriz de riscos, níveis N1 a N5 da pirâmide de segurança.
   Para acrescentar uma sigla, inclua uma linha em LISTA (pt, en, nome e
   descrição nos dois idiomas). Carregar depois de js/i18n.js.
   ========================================================================== */
(function (GI) {
  "use strict";

  /* [sigla PT, sigla EN, nome PT, nome EN, descrição PT, descrição EN] */
  var LISTA = [
    /* Valor agregado e custos */
    ["SPI", "SPI", "Índice de desempenho de prazo", "Schedule Performance Index",
      "Valor agregado dividido pelo valor planejado (EV ÷ PV). Abaixo de 1,00 o projeto avança menos que o previsto; acima de 1,00, adiantado.",
      "Earned value divided by planned value (EV ÷ PV). Below 1.00 the project is progressing less than planned; above 1.00, ahead."],
    ["CPI", "CPI", "Índice de desempenho de custo", "Cost Performance Index",
      "Valor agregado dividido pelo custo real (EV ÷ AC). Abaixo de 1,00 cada real gasto entrega menos que o orçado (sobrecusto).",
      "Earned value divided by actual cost (EV ÷ AC). Below 1.00 each unit spent delivers less than budgeted (cost overrun)."],
    ["TCPI", "TCPI", "Índice de desempenho para terminar", "To-Complete Performance Index",
      "Eficiência de custo necessária no trabalho restante para terminar dentro do orçamento: (BAC − EV) ÷ (BAC − AC).",
      "Cost efficiency required on the remaining work to finish within budget: (BAC − EV) ÷ (BAC − AC)."],
    ["EV", "EV", "Valor agregado", "Earned Value",
      "Quanto do orçamento corresponde ao trabalho já executado (% de avanço físico x BAC). Base para SPI e CPI.",
      "Budget value of the work actually performed (physical progress % x BAC). Basis for SPI and CPI."],
    ["PV", "PV", "Valor planejado", "Planned Value",
      "Quanto do orçamento deveria estar executado até a data, pela linha de base.",
      "Budget value of the work scheduled to be done by the date, per the baseline."],
    ["AC", "AC", "Custo real", "Actual Cost",
      "Custo efetivamente realizado até a data (lançado no ERP).",
      "Cost actually incurred to date (posted in the ERP)."],
    ["CV", "CV", "Variação de custo", "Cost Variance",
      "Valor agregado menos custo real (EV − AC). Negativo indica sobrecusto.",
      "Earned value minus actual cost (EV − AC). Negative means cost overrun."],
    ["SV", "SV", "Variação de prazo", "Schedule Variance",
      "Valor agregado menos valor planejado (EV − PV). Negativo indica atraso em valor.",
      "Earned value minus planned value (EV − PV). Negative means behind schedule in value terms."],
    ["BAC", "BAC", "Orçamento no término", "Budget at Completion",
      "Orçamento total aprovado do trabalho (orçado atual da EAC). Referência do valor agregado.",
      "Total approved budget of the work (current CBS budget). Reference for earned value."],
    ["VAC", "VAC", "Variação no término", "Variance at Completion",
      "Orçamento menos projeção no término. Negativo indica que o projeto deve terminar acima do orçamento.",
      "Budget minus estimate at completion. Negative means the project is expected to finish over budget."],
    ["EAC", "CBS", "Estrutura analítica de custos", "Cost Breakdown Structure",
      "Árvore de pacotes e itens de custo (elementos PEP) com o orçado, o comprometido, o realizado e a projeção. O valor só muda por SM aprovada.",
      "Tree of cost packages and items (WBS elements) with budget, committed, actual and forecast. Values change only through an approved CR."],
    ["PEP", "PEP", "Elemento PEP (estrutura do projeto)", "WBS element",
      "Elemento da estrutura do projeto no ERP que recebe orçamento e custos. Toda alteração de valor exige SM aprovada.",
      "Project structure element in the ERP that holds budget and costs. Any change in value requires an approved CR."],
    ["CAPEX", "CAPEX", "Despesa de capital", "Capital expenditure",
      "Investimento que vira ativo (equipamentos, obras). A Curva S financeira acompanha o CAPEX.",
      "Investment that becomes an asset (equipment, construction). The financial S-curve tracks CAPEX."],
    ["OPEX", "OPEX", "Despesa operacional", "Operating expenditure",
      "Gasto de custeio que não vira ativo.", "Running cost that does not become an asset."],
    ["ERP", "ERP", "Sistema de gestão empresarial", "Enterprise Resource Planning",
      "Sistema corporativo de onde vêm custos, pedidos e pagamentos (importação de custos e pedidos).",
      "Corporate system that provides costs, purchase orders and payments (cost and order import)."],
    ["VME", "EMV", "Valor monetário esperado", "Expected Monetary Value",
      "Probabilidade média da faixa x impacto em custo do risco. A soma das ameaças ativas é a exposição, comparada à reserva de contingência.",
      "Average probability of the band x cost impact of the risk. The sum of active threats is the exposure, compared with the contingency reserve."],
    ["P80", "P80", "Percentil 80", "80th percentile",
      "Valor com 80% de chance de não ser ultrapassado na análise quantitativa de riscos; usado para dimensionar a contingência.",
      "Value with an 80% chance of not being exceeded in the quantitative risk analysis; used to size the contingency."],
    /* Planejamento */
    ["EAP", "WBS", "Estrutura analítica do projeto", "Work Breakdown Structure",
      "Decomposição do escopo em áreas, subáreas e pacotes com pesos que somam 100%. Base do avanço físico e da Curva S.",
      "Breakdown of the scope into areas, sub-areas and packages with weights adding up to 100%. Basis for physical progress and the S-curve."],
    ["LB", "BL", "Linha de base", "Baseline",
      "Plano aprovado (escopo, prazo, custo ou quantidades) usado como referência. Só muda por revisão a partir de SM aprovada.",
      "Approved plan (scope, schedule, cost or quantities) used as reference. Changes only by revision from an approved CR."],
    ["KPI", "KPI", "Indicador-chave de desempenho", "Key Performance Indicator",
      "Indicador que mostra se a gestão está atingindo o resultado esperado; cada card mostra o valor e a referência (previsto, meta ou limite).",
      "Indicator showing whether management is achieving the expected result; each card shows the value and its reference (planned, target or limit)."],
    ["6WLA", "6WLA", "Janela de 6 semanas", "Six-week look-ahead",
      "Programação das próximas 6 semanas com restrições a remover (materiais, projetos, liberações) antes da execução.",
      "Schedule of the next 6 weeks with constraints to remove (materials, drawings, permits) before execution."],
    ["PPC", "PPC", "Percentual do planejado concluído", "Percent Plan Complete",
      "Atividades concluídas na semana dividido pelas programadas. Mede a confiabilidade da programação semanal.",
      "Activities completed in the week divided by those scheduled. Measures weekly schedule reliability."],
    ["HH", "MH", "Homem-hora", "Man-hour",
      "Uma pessoa trabalhando uma hora. Unidade de esforço da mão de obra e base do índice de produtividade.",
      "One person working one hour. Unit of labor effort and basis for the productivity rate."],
    ["Hh", "Mh", "Homem-hora", "Man-hour", "Uma pessoa trabalhando uma hora.", "One person working one hour."],
    ["HG", "EH", "Horas ganhas", "Earned hours",
      "Quantidade executada x índice orçado (HH por unidade). Permite somar unidades diferentes (m, t, m³) num só avanço.",
      "Quantity performed x budgeted rate (man-hours per unit). Allows adding different units (m, t, m³) into one progress figure."],
    ["FP", "PF", "Fator de produtividade", "Productivity factor",
      "HH apropriadas divididas pelas horas ganhas. Até 1,00 a equipe produz dentro do orçado; acima, gasta mais horas que o previsto.",
      "Man-hours spent divided by earned hours. Up to 1.00 the crew performs within budget; above, it spends more hours than planned."],
    ["CP", "PC", "Capacidade produtiva", "Productive capacity",
      "Horas por dia efetivamente disponíveis para produzir na frente de trabalho (jornada menos atrasos, deslocamentos e paradas).",
      "Hours per day actually available to produce at the work front (shift minus delays, travel and stoppages)."],
    ["Hhora", "MHour", "Homem-hora parado", "Idle man-hour",
      "Horas de efetivo paralisado por motivo registrado (clima, liberação, material). Mede perda de produção.",
      "Workforce hours stopped for a recorded reason (weather, permit, material). Measures production loss."],
    ["Mhora", "EqHour", "Máquina-hora parada", "Idle equipment-hour",
      "Horas de máquinas e equipamentos parados por motivo registrado.", "Hours of machinery and equipment stopped for a recorded reason."],
    ["CWA", "CWA", "Área de trabalho de construção", "Construction Work Area",
      "Divisão física do canteiro usada para planejar e medir a construção.", "Physical division of the site used to plan and measure construction."],
    ["TAG", "TAG", "Identificação do equipamento", "Equipment tag",
      "Código único do equipamento ou instrumento na planta.", "Unique code of the equipment or instrument in the plant."],
    /* Suprimentos */
    ["MAS", "MAS", "Mapa de Suprimentos", "Supply Map",
      "Painel de marcos de aquisição e fabricação por pacote, com linha de base, previsão e realizado.",
      "Board of procurement and fabrication milestones per package, with baseline, forecast and actual."],
    ["ROS", "ROS", "Data requerida no canteiro", "Required On Site",
      "Data em que o material precisa estar na obra. A folga é a ROS menos a previsão de entrega.",
      "Date the material must be on site. Float is ROS minus the forecast delivery."],
    ["OTD", "OTD", "Entrega no prazo", "On-Time Delivery",
      "Percentual de pedidos entregues até a data contratada.", "Percentage of orders delivered by the contracted date."],
    ["LLI", "LLI", "Item de longo prazo de entrega", "Long Lead Item",
      "Equipamento com prazo de fabricação longo, comprado antecipadamente para não atrasar o caminho crítico.",
      "Equipment with long fabrication time, bought early so it does not delay the critical path."],
    ["FAT", "FAT", "Teste de aceitação em fábrica", "Factory Acceptance Test",
      "Teste do equipamento na fábrica do fornecedor antes do embarque, testemunhado pelo cliente.",
      "Test of the equipment at the supplier's plant before shipment, witnessed by the client."],
    ["RFQ", "RFQ", "Pedido de cotação", "Request for Quotation",
      "Consulta formal de preço aos fornecedores.", "Formal price request to suppliers."],
    ["RFx", "RFx", "Consulta ao mercado", "Request for (information, proposal or quotation)",
      "Processo de compra com pedido de informação, proposta ou cotação aos fornecedores.",
      "Purchasing process requesting information, proposals or quotations from suppliers."],
    ["PO", "PO", "Pedido de compra", "Purchase Order", "Documento que formaliza a compra com o fornecedor.", "Document that formalizes the purchase with the supplier."],
    ["EPC", "EPC", "Engenharia, suprimento e construção", "Engineering, Procurement and Construction",
      "Contrato em que a contratada responde por projeto, compras e obra.", "Contract where the contractor is responsible for design, procurement and construction."],
    ["LS", "LS", "Verba global", "Lump sum", "Unidade de preço global (vb).", "Lump-sum pricing unit."],
    /* Riscos */
    ["RBS", "RBS", "Estrutura analítica de riscos", "Risk Breakdown Structure",
      "Categorias de origem dos riscos (técnico, externo, organizacional, gerencial).", "Risk source categories (technical, external, organizational, management)."],
    /* Qualidade */
    ["RNC", "NCR", "Relatório de não conformidade", "Nonconformance Report",
      "Registro de produto ou serviço fora do requisito, com contenção, causa raiz, ações corretivas e verificação de eficácia.",
      "Record of a product or service outside the requirement, with containment, root cause, corrective actions and effectiveness check."],
    ["ITP", "ITP", "Plano de inspeção e testes", "Inspection and Test Plan",
      "Lista de pontos de inspeção (H espera, W testemunho, R revisão de registro) com critério de aceitação, aprovada pelo cliente.",
      "List of inspection points (H hold, W witness, R record review) with acceptance criteria, approved by the client."],
    ["NC", "NC", "Não conformidade", "Nonconformity",
      "Constatação de auditoria em que um requisito não foi atendido; abre RNC.", "Audit finding where a requirement was not met; opens an NCR."],
    ["OM", "IO", "Oportunidade de melhoria", "Improvement opportunity",
      "Constatação de auditoria que sugere melhoria sem descumprimento de requisito.", "Audit finding suggesting an improvement with no requirement breach."],
    ["ISO", "ISO", "Organização Internacional de Normalização", "International Organization for Standardization",
      "Normas internacionais (ex.: ISO 19011 auditorias, ISO 21502 gestão de projetos).", "International standards (e.g. ISO 19011 audits, ISO 21502 project management)."],
    ["NBR", "NBR", "Norma brasileira", "Brazilian standard",
      "Norma da ABNT (ex.: NBR 14280, cálculo das taxas de acidentes).", "ABNT standard (e.g. NBR 14280, accident rate calculation)."],
    /* HSE */
    ["HSE", "HSE", "Saúde, segurança e meio ambiente", "Health, Safety and Environment",
      "Gestão de ocorrências, inspeções, análises de risco e indicadores de segurança.", "Management of incidents, inspections, risk analyses and safety indicators."],
    ["SMS", "HSE", "Segurança, meio ambiente e saúde", "Health, Safety and Environment",
      "Dimensão de segurança, meio ambiente e saúde (usada na análise de impacto das mudanças).", "Safety, environment and health dimension (used in change impact analysis)."],
    ["HHT", "HHT", "Horas-homem trabalhadas", "Man-hours worked",
      "Total de horas trabalhadas no mês por empresa. Base de cálculo das taxas de acidentes.", "Total hours worked in the month per company. Basis for accident rates."],
    ["TF", "LTIF", "Taxa de frequência de acidentes com afastamento", "Lost Time Injury Frequency",
      "Acidentes com afastamento por 1.000.000 de HHT (NBR 14280). Meta: zero.", "Lost-time injuries per 1,000,000 man-hours worked (NBR 14280). Target: zero."],
    ["LTIF", "LTIF", "Taxa de frequência de acidentes com afastamento", "Lost Time Injury Frequency",
      "Acidentes com afastamento por 1.000.000 de HHT. Meta: zero.", "Lost-time injuries per 1,000,000 man-hours worked. Target: zero."],
    ["TRIF", "TRIF", "Taxa de frequência de lesões registráveis", "Total Recordable Injury Frequency",
      "Lesões registráveis (com e sem afastamento e tratamento médico) por 1.000.000 de HHT.", "Recordable injuries (lost time, restricted work and medical treatment) per 1,000,000 man-hours."],
    ["TG", "SR", "Taxa de gravidade", "Severity rate",
      "Dias perdidos e debitados por 1.000.000 de HHT (NBR 14280).", "Days lost and charged per 1,000,000 man-hours (NBR 14280)."],
    ["LTI", "LTI", "Acidente com afastamento", "Lost Time Injury", "Lesão que afasta o trabalhador por um dia ou mais.", "Injury that keeps the worker away for one day or more."],
    ["HiPo", "HiPo", "Alto potencial", "High potential",
      "Ocorrência que poderia ter causado lesão grave ou fatal; exige investigação e relatório final no prazo.", "Event that could have caused a serious or fatal injury; requires investigation and final report on time."],
    ["DDS", "DDS", "Diálogo diário de segurança", "Daily safety talk",
      "Conversa curta antes do início da jornada sobre os riscos do dia.", "Short talk before the shift about the day's risks."],
    ["APR", "JSA", "Análise preliminar de riscos", "Job Safety Analysis",
      "Estudo dos perigos de uma tarefa e das medidas de controle antes da execução.", "Study of the hazards of a task and the controls before execution."],
    ["JSA", "JSA", "Análise de segurança da tarefa", "Job Safety Analysis",
      "Estudo dos perigos de uma tarefa e das medidas de controle antes da execução.", "Study of the hazards of a task and the controls before execution."],
    ["HAZOP", "HAZOP", "Estudo de perigos e operabilidade", "Hazard and Operability study",
      "Análise sistemática de desvios de processo por palavras-guia, com recomendações.", "Systematic analysis of process deviations using guide words, with recommendations."],
    ["LO", "OL", "Licença de operação", "Operating license", "Licença ambiental que autoriza a planta a operar.", "Environmental license that authorizes the plant to operate."],
    ["MOC", "MOC", "Gestão de mudanças de processo", "Management of Change",
      "Controle de mudanças na segurança de processo (fora do escopo das SMs do projeto).", "Process safety change control (outside the scope of project CRs)."],
    ["LGPD", "LGPD", "Lei Geral de Proteção de Dados", "Brazilian General Data Protection Law",
      "Lei 13.709/2018; dados pessoais das ocorrências seguem acesso restrito.", "Law 13.709/2018; personal data in incidents has restricted access."],
    /* Governança */
    ["SM", "CR", "Solicitação de mudança", "Change Request",
      "Pedido formal de mudança em escopo, prazo, custo, qualidade, contrato ou orçamento; passa por análise de impacto e decisão na alçada antes de alterar linha de base.",
      "Formal request to change scope, schedule, cost, quality, contract or budget; goes through impact analysis and decision at the right authority before any baseline changes."],
    ["CR", "CR", "Solicitação de mudança", "Change Request",
      "Pedido formal de mudança; nada altera linha de base sem CR aprovada.", "Formal change request; nothing changes a baseline without an approved CR."],
    ["PMO", "PMO", "Escritório de gerenciamento de projetos", "Project Management Office",
      "Área que define padrões, consolida a carteira e apoia a governança dos projetos.", "Area that sets standards, consolidates the portfolio and supports project governance."],
    ["EOT", "EOT", "Extensão de prazo", "Extension of Time", "Pedido de prorrogação do prazo contratual.", "Request to extend the contractual deadline."],
    ["CTI", "CTI", "Cooling Technology Institute", "Cooling Technology Institute",
      "Entidade que certifica o desempenho térmico de torres de resfriamento.", "Body that certifies the thermal performance of cooling towers."],
    ["SDCD", "DCS", "Sistema digital de controle distribuído", "Distributed Control System",
      "Sistema de automação que controla o processo da planta.", "Automation system that controls the plant process."],
    ["DCS", "DCS", "Sistema digital de controle distribuído", "Distributed Control System", "Sistema de automação que controla o processo da planta.", "Automation system that controls the plant process."],
    ["BT", "LV", "Baixa tensão", "Low voltage", "Tensão até 1 kV.", "Voltage up to 1 kV."],
    ["MT", "MV", "Média tensão", "Medium voltage", "Tensão acima de 1 kV até 36,2 kV.", "Voltage above 1 kV up to 36.2 kV."],
    ["p.p.", "p.p.", "Pontos percentuais", "Percentage points",
      "Diferença entre dois percentuais, em pontos. Ex.: real 61,8% e previsto 65,7% dão desvio de -3,9 p.p. (não é -3,9%). Negativo indica atraso em relação ao previsto.",
      "Difference between two percentages, in points. E.g. actual 61.8% and planned 65.7% give a variance of -3.9 p.p. (not -3.9%). Negative means behind plan."],
    ["PRFV", "FRP", "Plástico reforçado com fibra de vidro", "Fiber-reinforced plastic",
      "Material das estruturas e perfis de torres de resfriamento.", "Material of cooling tower structures and profiles."]
  ];

  var idioma = GI.i18n && GI.i18n.idioma === "en" ? "en" : "pt";
  var MAPA = {};
  LISTA.forEach(function (l) {
    var e = { pt: l[0], en: l[1], nome: { pt: l[2], en: l[3] }, desc: { pt: l[4], en: l[5] } };
    /* a forma do idioma atual tem prioridade quando a mesma sigla existe nos dois */
    var a = idioma === "en" ? [l[1], l[0]] : [l[0], l[1]];
    a.forEach(function (k) { if (!MAPA[k]) MAPA[k] = e; });
  });

  var T = {
    pt: { semana: "Semana ISO", semanaD: "Semana {n} do ano pelo calendário ISO 8601 (segunda a domingo); base da programação semanal e da produtividade.",
      p: "Probabilidade", pD: "Nível {n} de 5 da escala de probabilidade da matriz P x I (05 Riscos).",
      i: "Impacto", iD: "Nível {n} de 5 da escala de impacto da matriz P x I (05 Riscos).",
      n: "Nível da pirâmide", nD: "Nível {n} de 5 da pirâmide de segurança (1 lesão grave, 2 lesão leve, 3 dano material, 4 quase acidente, 5 desvio)." },
    en: { semana: "ISO week", semanaD: "Week {n} of the year per ISO 8601 (Monday to Sunday); basis for the weekly schedule and productivity.",
      p: "Probability", pD: "Level {n} of 5 of the probability scale of the P x I matrix (05 Risks).",
      i: "Impact", iD: "Level {n} of 5 of the impact scale of the P x I matrix (05 Risks).",
      n: "Pyramid level", nD: "Level {n} of 5 of the safety pyramid (1 serious injury, 2 minor injury, 3 property damage, 4 near miss, 5 deviation)." }
  }[idioma];

  function buscar(palavra) {
    if (!palavra || palavra.length < 2 || palavra.length > 7) return null;
    var e = MAPA[palavra];
    if (!e && /^[A-Z][A-Za-z0-9]+s$/.test(palavra)) e = MAPA[palavra.slice(0, -1)];   /* plural: KPIs, SMs, RNCs */
    if (e) return { sigla: palavra, nome: e.nome[idioma], desc: e.desc[idioma] };
    var m;
    if ((m = /^[SW](\d{2})$/.exec(palavra)) && Number(m[1]) >= 1 && Number(m[1]) <= 53) return { sigla: palavra, nome: T.semana + " " + Number(m[1]), desc: T.semanaD.replace("{n}", Number(m[1])) };
    if ((m = /^P([1-5])$/.exec(palavra))) return { sigla: palavra, nome: T.p + " " + m[1], desc: T.pD.replace("{n}", m[1]) };
    if ((m = /^I([1-5])$/.exec(palavra))) return { sigla: palavra, nome: T.i + " " + m[1], desc: T.iD.replace("{n}", m[1]) };
    if ((m = /^N([1-5])$/.exec(palavra))) return { sigla: palavra, nome: T.n + " " + m[1], desc: T.nD.replace("{n}", m[1]) };
    return null;
  }

  /* ---------------- Palavra sob o ponteiro ---------------- */
  var LETRA = /[A-Za-z0-9]/;
  var IGNORAR = "input, textarea, select, option, script, style, canvas, svg, [data-sem-siglas], .sigla-dica";
  function caretEm(x, y) {
    if (document.caretRangeFromPoint) return document.caretRangeFromPoint(x, y);
    if (document.caretPositionFromPoint) {
      var p = document.caretPositionFromPoint(x, y);
      if (!p) return null;
      var r = document.createRange(); r.setStart(p.offsetNode, p.offset); r.collapse(true); return r;
    }
    return null;
  }
  function palavraEm(x, y) {
    var c = caretEm(x, y);
    if (!c || !c.startContainer || c.startContainer.nodeType !== 3) return null;
    var no = c.startContainer, txt = no.nodeValue, i = c.startOffset;
    var pai = no.parentElement;
    if (!pai || pai.closest(IGNORAR)) return null;
    /* Siglas com pontos (p.p. = pontos percentuais) */
    var rp = /(^|[^A-Za-z])(p\.p\.)/g, mp;
    while ((mp = rp.exec(txt))) {
      var a = mp.index + mp[1].length, b = a + mp[2].length;
      if (i >= a && i <= b) {
        var rr = document.createRange(); rr.setStart(no, a); rr.setEnd(no, b);
        var qs = rr.getClientRects();
        for (var z = 0; z < qs.length; z++) { var qq = qs[z]; if (x >= qq.left - 1 && x <= qq.right + 1 && y >= qq.top - 1 && y <= qq.bottom + 1) return { texto: "p.p.", rect: qq, elemento: pai }; }
      }
    }
    var ini = i, fim = i;
    while (ini > 0 && LETRA.test(txt.charAt(ini - 1))) ini--;
    while (fim < txt.length && LETRA.test(txt.charAt(fim))) fim++;
    if (fim <= ini) return null;
    /* parte de código (TN-2026-014, PL-TN-..., CT/2026): não é sigla */
    var antes = txt.charAt(ini - 1), depois = txt.charAt(fim);
    if (/[-\/_.]/.test(antes) && LETRA.test(txt.charAt(ini - 2) || "") || /[-\/_]/.test(depois) && LETRA.test(txt.charAt(fim + 1) || "")) return null;
    var r = document.createRange(); r.setStart(no, ini); r.setEnd(no, fim);
    var rects = r.getClientRects(), dentro = null;
    for (var k = 0; k < rects.length; k++) {
      var q = rects[k];
      if (x >= q.left - 1 && x <= q.right + 1 && y >= q.top - 1 && y <= q.bottom + 1) { dentro = q; break; }
    }
    if (!dentro) return null;
    return { texto: txt.slice(ini, fim), rect: dentro, elemento: pai };
  }

  /* ---------------- Janela da dica ---------------- */
  var dica = null, atual = null, cursorEl = null;
  function criar() {
    dica = document.createElement("div");
    dica.className = "sigla-dica";
    dica.setAttribute("role", "tooltip");
    dica.setAttribute("data-sem-traducao", "");
    dica.id = "sigla-dica";
    dica.hidden = true;
    document.body.appendChild(dica);
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function mostrar(info, rect, el) {
    if (!dica) criar();
    var chave = info.sigla + "|" + Math.round(rect.left) + "|" + Math.round(rect.top);
    if (atual !== chave) {
      dica.innerHTML = '<span class="sigla-dica__topo"><b class="sigla-dica__sigla">' + esc(info.sigla) + '</b><span class="sigla-dica__nome">' + esc(info.nome) + "</span></span>" +
        '<span class="sigla-dica__desc">' + esc(info.desc) + "</span>";
      dica.hidden = false;
      var w = dica.offsetWidth, h = dica.offsetHeight, vw = document.documentElement.clientWidth, vh = window.innerHeight;
      var left = Math.max(8, Math.min(rect.left + rect.width / 2 - w / 2, vw - w - 8));
      var top = rect.bottom + 8;
      if (top + h > vh - 8) top = Math.max(8, rect.top - h - 8);
      dica.style.left = left + "px"; dica.style.top = top + "px";
      atual = chave;
    }
    if (cursorEl !== el) { limparCursor(); if (!el.closest("a, button, [role=tab], label")) { el.classList.add("sigla-alvo"); cursorEl = el; } }
  }
  function limparCursor() { if (cursorEl) cursorEl.classList.remove("sigla-alvo"); cursorEl = null; }
  function esconder() {
    if (dica && !dica.hidden) dica.hidden = true;
    atual = null; limparCursor();
  }

  var pendente = null, ultimo = null;
  function avaliar() {
    pendente = null;
    if (!ultimo) return;
    var p = palavraEm(ultimo.x, ultimo.y);
    var info = p ? buscar(p.texto) : null;
    if (info) mostrar(info, p.rect, p.elemento); else esconder();
  }
  document.addEventListener("mousemove", function (ev) {
    ultimo = { x: ev.clientX, y: ev.clientY };
    if (!pendente) pendente = window.requestAnimationFrame(avaliar);
  }, { passive: true });
  document.addEventListener("mouseleave", esconder);
  window.addEventListener("blur", esconder);
  window.addEventListener("scroll", esconder, { passive: true, capture: true });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") esconder(); });
  /* Toque: um toque na sigla abre; tocar fora (ou de novo) fecha */
  document.addEventListener("pointerdown", function (ev) {
    if (ev.pointerType !== "touch") return;
    var p = palavraEm(ev.clientX, ev.clientY);
    var info = p ? buscar(p.texto) : null;
    if (info && !p.elemento.closest("a, button, [role=tab]")) {
      var chave = info.sigla + "|" + Math.round(p.rect.left) + "|" + Math.round(p.rect.top);
      if (atual === chave) esconder(); else mostrar(info, p.rect, p.elemento);
    } else esconder();
  }, { passive: true });

  /* ---------------- Sublinhado pontilhado (Highlight API, sem mexer no DOM) ---------------- */
  var RX = /(^|[^A-Za-z0-9\-\/_])([A-Z][A-Za-z0-9]{1,6})(?=$|[^A-Za-z0-9\-\/_])/g;
  var agendado = null;
  function marcar() {
    agendado = null;
    if (!(window.CSS && CSS.highlights && window.Highlight)) return;
    var raiz = document.querySelector("main") || document.body;
    var hl = new Highlight();
    var w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT), n, total = 0;
    while ((n = w.nextNode()) && total < 4000) {
      var pai = n.parentElement;
      if (!pai || pai.closest(IGNORAR + ", a:not(.kpi), button, [role=tab], .btn, .badge, .kpi__value") || !pai.offsetParent) continue;
      var t = n.nodeValue, m;
      RX.lastIndex = 0;
      while ((m = RX.exec(t))) {
        if (!buscar(m[2])) continue;
        var ini = m.index + m[1].length, r = new Range();
        r.setStart(n, ini); r.setEnd(n, ini + m[2].length); hl.add(r); total++;
      }
      var rpp = /(^|[^A-Za-z])(p\.p\.)/g, mpp;
      while ((mpp = rpp.exec(t))) { var ip = mpp.index + mpp[1].length, rg = new Range(); rg.setStart(n, ip); rg.setEnd(n, ip + 4); hl.add(rg); total++; }
    }
    CSS.highlights.set("gi-sigla", hl);
  }
  function agendar() { if (!agendado) agendado = setTimeout(marcar, 250); }
  function iniciar() {
    marcar();
    new MutationObserver(function (lista) {
      for (var i = 0; i < lista.length; i++) { if (!dica || !dica.contains(lista[i].target)) { agendar(); return; } }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();

  GI.siglas = { buscar: buscar, lista: function () { return LISTA.slice(); } };
})(window.GI = window.GI || {});
