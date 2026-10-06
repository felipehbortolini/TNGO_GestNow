/* ==========================================================================
   mock-governanca.js | 08 Governança (dados fictícios).
   mudancas: solicitações de mudança (SM). Situação: Registrada,
   Em análise de impacto, Aguardando comitê, Aprovada, Aprovada com condições,
   Rejeitada, Adiada, Em implementação, Encerrada, Cancelada.
   fonteRecurso: de onde sai o valor aprovado (Aditivo de orçamento do cliente
   ou Reserva de contingência). Custos em centavos; prazo em dias corridos
   no caminho crítico (negativo = antecipação).
   remanejamentos: transferências propostas entre itens da EAC (tipo Remanejamento de
     orçamento); remanejamentoAplicado: data em que a aprovação aplicou na EAC.
   impacto: análise de impacto (dataAnalise, analistaId, afetaMarcoContratual,
     eacItens = códigos nível 3 da EAC, atividades do cronograma afetadas).
   alcada: quem decide (Gerente do projeto ou Comitê); a mínima exigida é
     calculada pela api (parâmetro mudancas.alcadaGerentePctOrcamento) e o
     analista pode elevar ao Comitê, nunca rebaixar.
   analise: responsável e prazo da análise em andamento.
   emergencia: execução iniciada antes do comitê (ratificação obrigatória).
   implementacao: início; encerramentoDetalhe: conferência do encerramento.
   historico: trilha de auditoria (quando ausente, a api monta a partir das datas).
   licoes: acervo de lições aprendidas. Situação: Rascunho, Em validação,
     Validada, Publicada. aplicabilidade: Projeto ou Corporativa.
     aplicacoes: reusos registrados pelo modal Aplicar em projeto
     (reusos = contagem, inclui reusos anteriores ao registro detalhado).
   ========================================================================== */
window.MOCK = window.MOCK || {};

window.MOCK.mudancas = [
  { id: 1, projetoId: 1, codigo: "SM-TN-2026-0001", titulo: "Inclusão do sistema de tratamento de efluentes",
    tipo: "Escopo", origem: "Legal/regulatória", prioridade: "Normal", solicitanteId: 4, dataSolicitacao: "2026-03-18",
    descricao: "Exigência do órgão ambiental para a licença de operação.",
    impacto: { custoCentavos: 40000000, prazoDias: 21, escopo: "Nova unidade de tratamento", qualidade: "Sem impacto", riscos: "RSK-TN-2026-0001", sms: "APR específica", contrato: "Aditivo CT-2026-011",
      afetaMarcoContratual: true, eacItens: ["1.1.1"], atividades: "Engenharia e montagem da ETE", dataAnalise: "2026-04-20", analistaId: 13 },
    fonteRecurso: "Aditivo de orçamento", alcada: "Comitê", decisao: { data: "2026-05-18", resultado: "Aprovada", participantesIds: [2, 1, 3, 13], condicoes: "", justificativa: "Condicionante da licença de operação." },
    implementacao: { inicio: "2026-05-20" },
    situacao: "Encerrada", encerramento: "2026-06-30" },
  { id: 2, projetoId: 1, codigo: "SM-TN-2026-0002", titulo: "Reforço das fundações por interferência no subsolo",
    tipo: "Custo", origem: "Contratada", prioridade: "Urgente", solicitanteId: 11, dataSolicitacao: "2026-04-22",
    descricao: "Decorrente do claim CLM-TN-2026-0004 (fundação F-12).",
    impacto: { custoCentavos: 40000000, prazoDias: 21, escopo: "Reforço da F-12", qualidade: "Novo projeto de fundação", riscos: "RSK-TN-2026-0003", sms: "Sem impacto", contrato: "Aditivo CT-2026-012",
      afetaMarcoContratual: true, eacItens: ["1.2.1"], atividades: "Fundações da área de moagem (F-12)", dataAnalise: "2026-06-05", analistaId: 13 },
    fonteRecurso: "Aditivo de orçamento", alcada: "Comitê", decisao: { data: "2026-07-10", resultado: "Aprovada", participantesIds: [2, 1, 3, 13], condicoes: "", justificativa: "Interferência comprovada por sondagem; claim acordado." },
    implementacao: { inicio: "2026-07-13" },
    situacao: "Encerrada", encerramento: "2026-09-02" },
  { id: 3, projetoId: 1, codigo: "SM-TN-2026-0003", titulo: "Partida parcial com licença de teste",
    tipo: "Prazo", origem: "Interna", prioridade: "Urgente", solicitanteId: 2, dataSolicitacao: "2026-09-11",
    descricao: "Alternativa ao atraso da licença de operação (RSK-TN-2026-0001).",
    impacto: { custoCentavos: 12000000, prazoDias: -15, escopo: "Partida da moagem antes da flotação", qualidade: "Sem impacto", riscos: "Reduz RSK-TN-2026-0001", sms: "Nova APR de partida", contrato: "Sem impacto",
      afetaMarcoContratual: true, eacItens: [], atividades: "Comissionamento e partida da moagem", dataAnalise: "2026-09-16", analistaId: 3 },
    fonteRecurso: "Reserva de contingência", alcada: "Comitê", decisao: null, situacao: "Aguardando comitê", encerramento: null },
  { id: 4, projetoId: 1, codigo: "SM-TN-2026-0004", titulo: "Montagem das estruturas do pipe rack PR-03",
    tipo: "Escopo", origem: "Cliente", prioridade: "Normal", solicitanteId: 2, dataSolicitacao: "2026-07-28",
    descricao: "Cliente incluiu o PR-03 para a futura expansão da flotação.",
    impacto: { custoCentavos: 40000000, prazoDias: 0, escopo: "120 t de estruturas", qualidade: "Sem impacto", riscos: "Sem impacto", sms: "APR de trabalho em altura", contrato: "Aditivo CT-2026-014",
      afetaMarcoContratual: false, eacItens: [], atividades: "Montagem eletromecânica do PR-03", dataAnalise: "2026-08-07", analistaId: 13 },
    fonteRecurso: "Reserva de contingência", alcada: "Comitê", decisao: { data: "2026-08-18", resultado: "Aprovada", participantesIds: [2, 1, 13], condicoes: "", justificativa: "Escopo solicitado pelo cliente, coberto pela reserva de contingência." },
    implementacao: { inicio: "2026-08-20" },
    situacao: "Em implementação", encerramento: null },
  { id: 5, projetoId: 1, codigo: "SM-TN-2026-0005", titulo: "Ampliação das obras civis da casa de bombas",
    tipo: "Escopo", origem: "Cliente", prioridade: "Normal", solicitanteId: 2, dataSolicitacao: "2026-09-02",
    descricao: "Nova bomba reserva e ampliação da laje.",
    impacto: { custoCentavos: 28000000, prazoDias: 10, escopo: "Laje e base adicional", qualidade: "Sem impacto", riscos: "RSK-TN-2026-0003", sms: "Sem impacto", contrato: "Aditivo CT-2026-012",
      afetaMarcoContratual: true, eacItens: ["1.2.1"], atividades: "Obras civis da casa de bombas", dataAnalise: "2026-09-15", analistaId: 13 },
    fonteRecurso: "Aditivo de orçamento", alcada: "Comitê", decisao: null, situacao: "Aguardando comitê", encerramento: null },
  { id: 6, projetoId: 1, codigo: "SM-TN-2026-0006", titulo: "Troca da especificação dos cabos de média tensão",
    tipo: "Qualidade/Especificação", origem: "Engenharia", prioridade: "Normal", solicitanteId: 6, dataSolicitacao: "2026-09-08",
    descricao: "Isolação de 15 kV para 20 kV por exigência da concessionária.",
    impacto: { custoCentavos: 36000000, prazoDias: 0, escopo: "Sem impacto", qualidade: "Nova especificação", riscos: "Sem impacto", sms: "Sem impacto", contrato: "Aditivo do pedido PED-2026-0009",
      afetaMarcoContratual: false, eacItens: [], atividades: "Lançamento de cabos de média tensão", dataAnalise: "2026-09-18", analistaId: 6 },
    fonteRecurso: "Reserva de contingência", alcada: "Comitê", decisao: null, situacao: "Aguardando comitê", encerramento: null },
  { id: 7, projetoId: 1, codigo: "SM-TN-2026-0007", titulo: "Revisão do plano de comissionamento por sistemas",
    tipo: "Prazo", origem: "Interna", prioridade: "Normal", solicitanteId: 8, dataSolicitacao: "2026-09-21",
    descricao: "Resequenciar os sistemas 310 e 510 em função da entrega das bombas.",
    impacto: null, fonteRecurso: null, alcada: null, decisao: null, analise: { responsavelId: 8, prazo: "2026-10-05" },
    situacao: "Em análise de impacto", encerramento: null },
  { id: 8, projetoId: 1, codigo: "SM-TN-2026-0008", titulo: "Pintura anticorrosiva adicional nas estruturas externas",
    tipo: "Escopo", origem: "Cliente", prioridade: "Normal", solicitanteId: 2, dataSolicitacao: "2026-08-10",
    descricao: "Terceira demão em estruturas expostas.",
    impacto: { custoCentavos: 9000000, prazoDias: 5, escopo: "Pintura adicional", qualidade: "Sem impacto", riscos: "Sem impacto", sms: "Sem impacto", contrato: "Aditivo CT-2026-014",
      afetaMarcoContratual: false, eacItens: [], atividades: "Pintura das estruturas externas", dataAnalise: "2026-08-24", analistaId: 13 },
    fonteRecurso: "Aditivo de orçamento", alcada: "Gerente do projeto",
    decisao: { data: "2026-09-01", resultado: "Rejeitada", participantesIds: [2], condicoes: "", justificativa: "Especificação atual atende à norma; tratar na fase de operação." },
    situacao: "Rejeitada", encerramento: "2026-09-01" },
  /* Remanejamentos de orçamento (03): transferência entre itens da EAC só por SM; a aprovação aplica na EAC */
  { id: 9, projetoId: 1, codigo: "SM-TN-2026-0009", titulo: "Remanejamento de R$ 150.000,00 dos transportadores para a engenharia mecânica",
    tipo: "Remanejamento de orçamento", origem: "Interna", prioridade: "Normal", solicitanteId: 13, dataSolicitacao: "2026-08-05",
    descricao: "Economia na compra dos transportadores cobre a engenharia mecânica adicional.",
    remanejamentos: [{ origem: "2.1.3", destino: "1.2.2", valorCentavos: 15000000, aplicado: true }],
    impacto: { custoCentavos: 0, prazoDias: 0, escopo: "Sem impacto", qualidade: "Sem impacto", riscos: "Sem impacto", sms: "Sem impacto", contrato: "Sem impacto",
      afetaMarcoContratual: false, eacItens: ["2.1.3", "1.2.2"], atividades: "", dataAnalise: "2026-08-10", analistaId: 13 },
    fonteRecurso: null, alcada: "Gerente do projeto", decisao: { data: "2026-08-12", resultado: "Aprovada", participantesIds: [2], condicoes: "", justificativa: "Saldo livre confirmado no item de origem; total do orçamento inalterado." },
    remanejamentoAplicado: { data: "2026-08-12", porId: 2, revisao: 2 }, implementacao: { inicio: "2026-08-12" },
    encerramentoDetalhe: { data: "2026-08-14", porId: 2, cronograma: false, contrato: false, riscos: false, eacRevisao: null, eapRevisao: null, observacao: "", licaoRef: null },
    situacao: "Encerrada", encerramento: "2026-08-14" },
  { id: 10, projetoId: 1, codigo: "SM-TN-2026-0010", titulo: "Remanejamento de R$ 200.000,00 do SDCD para as fundações",
    tipo: "Remanejamento de orçamento", origem: "Interna", prioridade: "Normal", solicitanteId: 13, dataSolicitacao: "2026-08-26",
    descricao: "Estimativa do SDCD reduzida após as propostas; saldo cobre fundações adicionais.",
    remanejamentos: [{ origem: "2.2.5", destino: "3.1.2", valorCentavos: 20000000, aplicado: true }],
    impacto: { custoCentavos: 0, prazoDias: 0, escopo: "Sem impacto", qualidade: "Sem impacto", riscos: "Sem impacto", sms: "Sem impacto", contrato: "Sem impacto",
      afetaMarcoContratual: false, eacItens: ["2.2.5", "3.1.2"], atividades: "", dataAnalise: "2026-08-31", analistaId: 13 },
    fonteRecurso: null, alcada: "Gerente do projeto", decisao: { data: "2026-09-02", resultado: "Aprovada", participantesIds: [2], condicoes: "", justificativa: "Propostas do SDCD abaixo da estimativa; transferência dentro da alçada." },
    remanejamentoAplicado: { data: "2026-09-02", porId: 2, revisao: 2 }, implementacao: { inicio: "2026-09-02" },
    encerramentoDetalhe: { data: "2026-09-04", porId: 2, cronograma: false, contrato: false, riscos: false, eacRevisao: null, eapRevisao: null, observacao: "", licaoRef: null },
    situacao: "Encerrada", encerramento: "2026-09-04" },
  { id: 11, projetoId: 1, codigo: "SM-TN-2026-0011", titulo: "Remanejamento de R$ 250.000,00 da montagem mecânica para as fundações",
    tipo: "Remanejamento de orçamento", origem: "Interna", prioridade: "Normal", solicitanteId: 13, dataSolicitacao: "2026-09-22",
    descricao: "Fundações com comprometido acima do orçado atual (reforço da F-12 e bases adicionais); a montagem mecânica tem saldo livre após a contratação.",
    remanejamentos: [{ origem: "3.2.1", destino: "3.1.2", valorCentavos: 25000000 }],
    impacto: null, fonteRecurso: null, alcada: null, decisao: null, analise: { responsavelId: 13, prazo: "2026-10-02" },
    situacao: "Em análise de impacto", encerramento: null }
];

window.MOCK.licoes = [
  { id: 1, projetoId: 1, codigo: "LA-TN-2026-0001", titulo: "Cadastro de interferências antes da escavação", tipo: "A evitar",
    fase: "Construção", area: "Riscos", disciplina: "Civil", origem: "Claim CLM-TN-2026-0004",
    aconteceu: "Interferência não mapeada na F-12 gerou 21 dias de atraso e aditivo.", causa: "Cadastro de interferências incompleto na área existente.",
    impactoPrazoDias: 21, impactoCustoCentavos: 40000000, recomendacao: "Exigir varredura com georradar e sondagens antes de liberar fundações em área industrial existente.",
    palavrasChave: ["interferência", "fundação", "sondagem"], autorId: 11, aplicabilidade: "Corporativa", situacao: "Publicada", data: "2026-07-15", reusos: 2 },
  { id: 2, projetoId: 1, codigo: "LA-TN-2026-0002", titulo: "Equalização técnica antes da comercial", tipo: "A repetir",
    fase: "Suprimentos", area: "Aquisições", disciplina: "Mecânica", origem: "Processo PC-03",
    aconteceu: "Equalização técnica prévia eliminou proposta que não atendia e evitou aditivo.", causa: "Procedimento seguido.",
    impactoPrazoDias: 0, impactoCustoCentavos: 0, recomendacao: "Manter equalização técnica fechada antes de abrir preços.",
    palavrasChave: ["equalização", "RFx"], autorId: 7, aplicabilidade: "Corporativa", situacao: "Publicada", data: "2026-03-05", reusos: 3 },
  { id: 3, projetoId: 1, codigo: "LA-TN-2026-0003", titulo: "Janela de chuvas no plano de terraplenagem", tipo: "A evitar",
    fase: "Construção", area: "Cronograma", disciplina: "Civil", origem: "Risco RSK-TN-2026-0007",
    aconteceu: "Frentes abertas no início das chuvas reduziram a produtividade em 30%.", causa: "Sequência da terraplenagem sem considerar o regime de chuvas.",
    impactoPrazoDias: 8, impactoCustoCentavos: 6000000, recomendacao: "Planejar cortes e aterros fora do período chuvoso e prever drenagem provisória.",
    palavrasChave: ["chuva", "terraplenagem", "drenagem"], autorId: 3, aplicabilidade: "Corporativa", situacao: "Publicada", data: "2026-08-20", reusos: 1 },
  { id: 4, projetoId: 1, codigo: "LA-TN-2026-0004", titulo: "Qualificação de soldadores por processo e espessura", tipo: "A evitar",
    fase: "Construção", area: "Qualidade", disciplina: "Tubulação", origem: "RNC RNC-TN-2026-0004",
    aconteceu: "Juntas reprovadas por soldador sem qualificação para a espessura.", causa: "Controle de qualificação só por nome, sem processo e faixa.",
    impactoPrazoDias: 6, impactoCustoCentavos: 3400000, recomendacao: "Liberar soldador por processo, posição e faixa de espessura no controle de campo.",
    palavrasChave: ["solda", "qualificação"], autorId: 9, aplicabilidade: "Corporativa", situacao: "Em validação", data: "2026-09-12", reusos: 0 },
  { id: 5, projetoId: 1, codigo: "LA-TN-2026-0005", titulo: "Amarração de ferramentas em trabalho em altura", tipo: "A evitar",
    fase: "Construção", area: "SMS", disciplina: "Mecânica", origem: "Ocorrência OCR-TN-2026-0219",
    aconteceu: "Queda de ferramenta de 14 m em área parcialmente isolada (HiPo).", causa: "Ferramentas sem talabarte; isolamento incompleto.",
    impactoPrazoDias: 0, impactoCustoCentavos: 0, recomendacao: "Talabarte de ferramenta obrigatório acima de 2 m e isolamento pelo raio de queda.",
    palavrasChave: ["altura", "queda de objeto", "HiPo"], autorId: 10, aplicabilidade: "Corporativa", situacao: "Rascunho", data: "2026-09-23", reusos: 0 },
  { id: 6, projetoId: 1, codigo: "LA-TN-2026-0006", titulo: "Hedge cambial no momento do pedido", tipo: "A repetir",
    fase: "Suprimentos", area: "Custos", disciplina: "Mecânica", origem: "Risco RSK-TN-2026-0006",
    aconteceu: "Hedge das parcelas do moinho protegeu o orçamento da alta do dólar.", causa: "Resposta ao risco definida no plano de compras.",
    impactoPrazoDias: 0, impactoCustoCentavos: 0, recomendacao: "Contratar hedge na emissão de pedidos com parcelas em moeda estrangeira acima de R$ 1 milhão.",
    palavrasChave: ["câmbio", "hedge", "importados"], autorId: 13, aplicabilidade: "Corporativa", situacao: "Validada", data: "2026-09-15", reusos: 0 },
  { id: 7, projetoId: 1, codigo: "LA-TN-2026-0007", titulo: "Controle de revisão de desenhos em campo", tipo: "A evitar",
    fase: "Engenharia", area: "Comunicações", disciplina: "Mecânica", origem: "RNC RNC-TN-2026-0006",
    aconteceu: "Montagem com desenho desatualizado gerou retrabalho e claim.", causa: "Distribuição de revisões sem recolhimento das cópias antigas.",
    impactoPrazoDias: 0, impactoCustoCentavos: 0, recomendacao: "Distribuir desenhos só por meio digital controlado nas frentes de montagem.",
    palavrasChave: ["documentos", "revisão", "campo"], autorId: 6, aplicabilidade: "Projeto", situacao: "Rascunho", data: "2026-09-24", reusos: 0 },
  { id: 8, projetoId: 1, codigo: "LA-TN-2026-0008", titulo: "Estoque de segurança de insumos críticos no canteiro", tipo: "A repetir",
    fase: "Construção", area: "Riscos", disciplina: "Civil", origem: "Risco RSK-TN-2026-0008",
    aconteceu: "Paralisação anunciada dos transportadores não afetou as concretagens.", causa: "Estoque de 15 dias de cimento e aço formado como resposta ao risco.",
    impactoPrazoDias: 0, impactoCustoCentavos: 0, recomendacao: "Manter estoque de segurança de insumos críticos quando houver risco logístico identificado.",
    palavrasChave: ["logística", "estoque", "greve"], autorId: 7, aplicabilidade: "Corporativa", situacao: "Publicada", data: "2026-07-31", reusos: 0 }
];
