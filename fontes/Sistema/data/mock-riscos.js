/* ==========================================================================
   mock-riscos.js | 05 Gestão de Riscos (dados fictícios, a partir dos
   mockups 01 a 04 e 10 a 17). Datas ajustadas à data de referência do
   protótipo (25/09/2026). Score, severidade, VME e situação da revisão são
   calculados pela api (nunca gravados).

   riscos:
     categoria / subcategoria: RBS (catálogo riscoCategorias).
     natureza: Ameaça | Oportunidade (oportunidade: impacto é benefício e
       não soma na exposição).
     origemTipo: Manual, Ata de reunião, Workshop de riscos, Lições aprendidas,
       Auditoria (manuais) ou Diligenciamento, Claim, Plano de compras
       (gerados pelos módulos 03 e 04). origem: texto exibido.
     inerente / residual: { p, i, dimensoes: { prazo, custo, escopo, sms,
       imagem, legal } } de 1 a 5; i >= maior dimensão (pior caso).
       residual null = ainda não avaliado (exige plano de resposta).
     impactoCustoCentavos: impacto em custo se o evento ocorrer (centavos).
     plano: estrategia, plano, severidadeAlvo, prazoAlvo, custoRespostaCentavos,
       responsavelPlanoId, instrumento (Transferir), smRef (Evitar),
       aprovacao { exigida, situacao: Pendente | Aprovado | Devolvido }.
     situacao: Identificado, Em análise, Em tratamento, Monitorado,
       Materializado, Encerrado.
     cadenciaDias: intervalo de revisão (até o máximo da faixa nos parâmetros).
     revisoes: linha do tempo (tabela RiscoRevisao), mais recente primeiro.
     historico: trilha de auditoria (quando ausente, a api monta a partir
       da criação, das revisões e da aprovação).
     oculto / exclusao: exclusão lógica (só Admin vê e restaura).
   riscoCategorias: catálogo RBS (Configurações > Cadastros).
   riscosEvolucao: fotografia mensal do score residual somado das ameaças
     ativas (o mês corrente é recalculado pela api).
   ========================================================================== */
window.MOCK = window.MOCK || {};

window.MOCK.riscoCategorias = [
  { id: 1, grupo: "Regulatório", nome: "Licenciamento" },
  { id: 2, grupo: "Regulatório", nome: "Acesso à rede" },
  { id: 3, grupo: "Técnico", nome: "Fundações" },
  { id: 4, grupo: "Técnico", nome: "Interfaces" },
  { id: 5, grupo: "Custo", nome: "Câmbio" },
  { id: 6, grupo: "Custo", nome: "Estimativa" },
  { id: 7, grupo: "Recursos", nome: "Equipamentos" },
  { id: 8, grupo: "Recursos", nome: "Equipe" },
  { id: 9, grupo: "Suprimentos", nome: "Fornecedores" },
  { id: 10, grupo: "Suprimentos", nome: "Logística" },
  { id: 11, grupo: "Ambiental", nome: "Clima" },
  { id: 12, grupo: "SMS", nome: "Segurança do trabalho" }
];

window.MOCK.riscos = [
  { id: 1, projetoId: 1, codigo: "RSK-TN-2026-0001", titulo: "Atraso na licença de operação junto ao órgão ambiental",
    categoria: "Regulatório", subcategoria: "Licenciamento", natureza: "Ameaça", donoId: 4, identificadoPorId: 1, identificadoEm: "2026-07-03",
    origemTipo: "Ata de reunião", ataId: 2, origem: "Ata TN-2026-0031",
    causa: "Fila de análise do órgão ambiental acima de 120 dias no estado",
    consequencia: "Impedimento de partida da planta e postergação do faturamento do marco M5",
    descricao: "A LO depende de vistoria presencial e do protocolo do programa de monitoramento de efluentes. O protocolo foi feito em 12/06/2026 e a fila média informada pelo órgão é de 120 a 150 dias, o que ultrapassa a data prevista de partida (10/11/2026).",
    gatilho: "Vistoria não agendada até 10/10/2026 (30 dias antes da partida)",
    inerente: { p: 4, i: 5, dimensoes: { prazo: 5, custo: 4, escopo: 1, sms: 1, imagem: 3, legal: 4 } },
    residual: { p: 3, i: 4, dimensoes: { prazo: 4, custo: 3, escopo: 1, sms: 1, imagem: 2, legal: 3 } }, riscoVida: false,
    dimensao: "Prazo", impactoPrazoDias: 45, impactoCustoCentavos: 185000000,
    estrategia: "Mitigar", plano: "Antecipar as entregas condicionantes da LO e negociar prioridade de vistoria via consultoria ambiental credenciada, mantendo plano B de partida parcial com licença de teste.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-10-25", custoRespostaCentavos: 24000000, responsavelPlanoId: 4,
    aprovacao: { exigida: true, situacao: "Aprovado", porId: 2, data: "2026-07-10" },
    cadenciaDias: 15, ultimaRevisao: "2026-09-23", proximaRevisao: "2026-10-07", situacao: "Em tratamento",
    revisoes: [
      { data: "2026-09-23", porId: 1, tipo: "revisao", situacaoApurada: "Sem mudança", de: 12, para: 12, p: 3, i: 4, gatilho: false, texto: "Laudo de efluentes atrasou; protocolo do programa replanejado para 05/10. Vistoria ainda não agendada." },
      { data: "2026-09-15", porId: 4, tipo: "revisao", situacaoApurada: "Sem mudança", de: 12, para: 12, p: 3, i: 4, gatilho: false, texto: "Órgão confirmou fila de 130 dias; consultoria cobrou prioridade por ofício." },
      { data: "2026-09-01", porId: 4, tipo: "revisao", situacaoApurada: "Sem mudança", de: 12, para: 12, p: 3, i: 4, gatilho: false, texto: "Estudo de partida parcial com licença de teste em andamento." },
      { data: "2026-08-18", porId: 1, tipo: "revisao", situacaoApurada: "Sem mudança", de: 12, para: 12, p: 3, i: 4, gatilho: false, texto: "Vistoria ainda não agendada; gatilho monitorado." },
      { data: "2026-08-04", porId: 4, tipo: "residual", situacaoApurada: "Risco reduzido", de: 20, para: 12, p: 3, i: 4, gatilho: false, texto: "Protocolo aceito pelo órgão e plano de resposta em execução. Probabilidade caiu de 4 para 3." },
      { data: "2026-07-03", porId: 1, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 20, p: 4, i: 5, gatilho: false, texto: "Risco identificado na reunião de licenciamento." }
    ],
    historico: [
      { quando: "2026-09-23T09:12", porId: 1, texto: "Revisão registrada, sem mudança de severidade." },
      { quando: "2026-09-15T10:05", porId: 4, texto: "Revisão registrada, sem mudança de severidade." },
      { quando: "2026-09-03T17:20", porId: 4, texto: "Ação 1 replanejada de 05/09/2026 para 05/10/2026 na Central de Ações." },
      { quando: "2026-09-01T08:40", porId: 4, texto: "Revisão registrada, sem mudança de severidade." },
      { quando: "2026-08-18T09:12", porId: 1, texto: "Revisão registrada, sem mudança de severidade." },
      { quando: "2026-08-04T16:40", porId: 4, texto: "Avaliação residual alterada de 20 para 12. Justificativa registrada." },
      { quando: "2026-07-21T11:05", porId: 4, texto: "Ação 2 criada (consultoria credenciada)." },
      { quando: "2026-07-10T15:30", porId: 2, texto: "Plano de resposta aprovado pela gerência do projeto (Mitigar)." },
      { quando: "2026-07-08T10:15", porId: 4, texto: "Plano de resposta registrado: Mitigar, alvo Moderado até 25/10/2026." },
      { quando: "2026-07-03T14:22", porId: 1, texto: "Risco criado a partir da ata TN-2026-0031. Avaliação inerente 20 (P4 x I5)." }
    ] },

  { id: 2, projetoId: 1, codigo: "RSK-TN-2026-0002", titulo: "Indisponibilidade de guindaste de 250 t na janela de montagem",
    categoria: "Recursos", subcategoria: "Equipamentos", natureza: "Ameaça", donoId: 5, identificadoPorId: 5, identificadoEm: "2026-06-25",
    origemTipo: "Ata de reunião", ataId: 1, origem: "Ata TN-2026-0028",
    causa: "Poucas unidades de 250 t na região e alta demanda no segundo semestre",
    consequencia: "Atraso no içamento da carcaça do moinho e do britador",
    descricao: "A janela de içamento depende de um único guindaste locado; indisponibilidade desloca a montagem mecânica.",
    gatilho: "Locadora sem confirmação da janela até 30 dias antes do içamento",
    inerente: { p: 3, i: 4, dimensoes: { prazo: 4, custo: 3, escopo: 1, sms: 2, imagem: 1, legal: 1 } },
    residual: { p: 2, i: 4, dimensoes: { prazo: 4, custo: 2, escopo: 1, sms: 2, imagem: 1, legal: 1 } }, riscoVida: false,
    dimensao: "Prazo", impactoPrazoDias: 20, impactoCustoCentavos: 120000000,
    estrategia: "Transferir", instrumento: "Cláusula contratual",
    plano: "Contrato de locação com cláusula de disponibilidade e multa por indisponibilidade; segundo fornecedor pré-qualificado.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-10-05", custoRespostaCentavos: 3500000, responsavelPlanoId: 5,
    aprovacao: { exigida: false },
    cadenciaDias: 30, ultimaRevisao: "2026-09-01", proximaRevisao: "2026-09-30", situacao: "Em tratamento",
    revisoes: [
      { data: "2026-09-01", porId: 5, tipo: "residual", situacaoApurada: "Risco reduzido", de: 12, para: 8, p: 2, i: 4, gatilho: false, texto: "Janela de 05 a 30/10 confirmada em contrato com cláusula de multa." },
      { data: "2026-06-25", porId: 5, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 12, p: 3, i: 4, gatilho: false, texto: "Avaliação inicial na coordenação de obra." }
    ] },

  { id: 3, projetoId: 1, codigo: "RSK-TN-2026-0003", titulo: "Interferência não mapeada no subsolo das fundações remanescentes",
    categoria: "Técnico", subcategoria: "Fundações", natureza: "Ameaça", donoId: 6, identificadoPorId: 11, identificadoEm: "2026-04-15",
    origemTipo: "Claim", origem: "Claim CLM-TN-2026-0004",
    causa: "Cadastro de interferências incompleto na área da casa de bombas",
    consequencia: "Reprojeto e reforço das fundações F-20 a F-28, com novo pleito da contratada",
    descricao: "Após a interferência na F-12 (risco RSK-TN-2026-0009, materializado), as fundações remanescentes podem encontrar tubulações e bases antigas não cadastradas.",
    gatilho: "Resultado da sondagem complementar com anomalias",
    inerente: { p: 3, i: 5, dimensoes: { prazo: 4, custo: 5, escopo: 3, sms: 2, imagem: 1, legal: 2 } },
    residual: { p: 3, i: 5, dimensoes: { prazo: 4, custo: 5, escopo: 3, sms: 2, imagem: 1, legal: 2 } }, riscoVida: false,
    dimensao: "Custo", impactoPrazoDias: 30, impactoCustoCentavos: 280000000,
    estrategia: "Evitar", smRef: "SM-TN-2026-0005",
    plano: "Sondagem complementar antes de liberar as frentes F-20 a F-28 e reprojeto preventivo das fundações críticas, com a mudança de solução registrada na SM da casa de bombas.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-10-15", custoRespostaCentavos: 18000000, responsavelPlanoId: 6,
    aprovacao: { exigida: true, situacao: "Pendente", solicitadaEm: "2026-09-04" },
    cadenciaDias: 15, ultimaRevisao: "2026-09-04", proximaRevisao: "2026-09-18", situacao: "Em análise",
    revisoes: [
      { data: "2026-09-04", porId: 6, tipo: "residual", situacaoApurada: "Sem mudança", de: 15, para: 15, p: 3, i: 5, gatilho: false, texto: "Plano de resposta registrado; sem redução esperada até o resultado da sondagem. Plano aguardando aprovação da gerência do projeto." },
      { data: "2026-08-20", porId: 6, tipo: "revisao", situacaoApurada: "Sem mudança", de: 15, para: 15, p: 3, i: 5, gatilho: false, texto: "Sondagem adiada pela liberação de área da casa de bombas." },
      { data: "2026-07-29", porId: 11, tipo: "revisao", situacaoApurada: "Sem mudança", de: 15, para: 15, p: 3, i: 5, gatilho: false, texto: "Sondagem complementar contratada junto com o reforço da F-12." },
      { data: "2026-04-15", porId: 11, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 15, p: 3, i: 5, gatilho: false, texto: "Avaliação inicial após o evento da F-12." }
    ] },

  { id: 4, projetoId: 1, codigo: "RSK-TN-2026-0004", titulo: "Antecipação da entrega dos transformadores pelo fornecedor",
    categoria: "Suprimentos", subcategoria: "Fornecedores", natureza: "Oportunidade", donoId: 7, identificadoPorId: 7, identificadoEm: "2026-08-21",
    origemTipo: "Diligenciamento", origem: "Diligenciamento PED-2026-0007",
    causa: "Fabricação concluída antes do previsto",
    consequencia: "Energização antecipada da subestação unitária e ganho no comissionamento elétrico",
    descricao: "O fornecedor informou possibilidade de entrega 9 dias antes da data contratual.",
    gatilho: "FAT aprovado até 26/09/2026",
    inerente: { p: 3, i: 4, dimensoes: { prazo: 4, custo: 2, escopo: 1, sms: 1, imagem: 1, legal: 1 } },
    residual: { p: 4, i: 4, dimensoes: { prazo: 4, custo: 2, escopo: 1, sms: 1, imagem: 1, legal: 1 } }, riscoVida: false,
    dimensao: "Prazo", impactoPrazoDias: 9, impactoCustoCentavos: 30000000,
    estrategia: "Explorar", plano: "Antecipar a inspeção de fábrica e preparar a base e o pátio para receber os transformadores.",
    severidadeAlvo: "alto", prazoAlvo: "2026-10-01", custoRespostaCentavos: 1500000, responsavelPlanoId: 7,
    aprovacao: { exigida: false },
    cadenciaDias: 15, ultimaRevisao: "2026-09-21", proximaRevisao: "2026-10-06", situacao: "Monitorado",
    revisoes: [
      { data: "2026-09-21", porId: 7, tipo: "revisao", situacaoApurada: "Sem mudança", de: 16, para: 16, p: 4, i: 4, gatilho: false, texto: "FAT agendado para 26/09 e base liberada para receber os transformadores." },
      { data: "2026-09-05", porId: 7, tipo: "residual", situacaoApurada: "Risco agravado", de: 12, para: 16, p: 4, i: 4, gatilho: false, texto: "Fornecedor confirmou fabricação concluída; probabilidade de captura subiu para 4." },
      { data: "2026-08-21", porId: 7, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 12, p: 3, i: 4, gatilho: false, texto: "Avaliação inicial no diligenciamento." }
    ] },

  { id: 5, projetoId: 1, codigo: "RSK-TN-2026-0005", titulo: "Rotatividade da equipe de comissionamento",
    categoria: "Recursos", subcategoria: "Equipe", natureza: "Ameaça", donoId: 8, identificadoPorId: 8, identificadoEm: "2026-07-20",
    origemTipo: "Workshop de riscos", origem: "Workshop de riscos",
    causa: "Mercado aquecido para técnicos de comissionamento",
    consequencia: "Perda de conhecimento dos sistemas e atraso nos testes",
    descricao: "Saída de técnicos-chave durante o comissionamento compromete a sequência de testes por sistema.",
    gatilho: "Duas saídas no mesmo mês",
    inerente: { p: 3, i: 3, dimensoes: { prazo: 3, custo: 2, escopo: 1, sms: 1, imagem: 1, legal: 1 } },
    residual: { p: 2, i: 3, dimensoes: { prazo: 3, custo: 2, escopo: 1, sms: 1, imagem: 1, legal: 1 } }, riscoVida: false,
    dimensao: "Prazo", impactoPrazoDias: 10, impactoCustoCentavos: 60000000,
    estrategia: "Mitigar", plano: "Bônus de permanência até a partida e documentação dos procedimentos de teste por sistema.",
    severidadeAlvo: "baixo", prazoAlvo: "2026-12-15", custoRespostaCentavos: 18000000, responsavelPlanoId: 8,
    aprovacao: { exigida: false },
    cadenciaDias: 30, ultimaRevisao: "2026-09-14", proximaRevisao: "2026-10-14", situacao: "Monitorado",
    revisoes: [
      { data: "2026-09-14", porId: 8, tipo: "residual", situacaoApurada: "Risco reduzido", de: 9, para: 6, p: 2, i: 3, gatilho: false, texto: "Bônus de permanência aprovado pela gerência." },
      { data: "2026-07-20", porId: 8, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 9, p: 3, i: 3, gatilho: false, texto: "Avaliação inicial no workshop de riscos." }
    ] },

  { id: 6, projetoId: 1, codigo: "RSK-TN-2026-0006", titulo: "Variação cambial no pacote de equipamentos importados",
    categoria: "Custo", subcategoria: "Câmbio", natureza: "Ameaça", donoId: 13, identificadoPorId: 7, identificadoEm: "2026-02-10",
    origemTipo: "Plano de compras", origem: "Plano de compras",
    causa: "Componentes importados do moinho e do SDCD cotados em dólar",
    consequencia: "Aumento do custo dos equipamentos mecânicos e de automação",
    descricao: "Parcelas finais dos pedidos em moeda estrangeira expostas à variação cambial.",
    gatilho: "Dólar acima da taxa do orçamento por 2 semanas",
    inerente: { p: 4, i: 4, dimensoes: { prazo: 1, custo: 4, escopo: 1, sms: 1, imagem: 1, legal: 1 } },
    residual: { p: 3, i: 3, dimensoes: { prazo: 1, custo: 3, escopo: 1, sms: 1, imagem: 1, legal: 1 } }, riscoVida: false,
    dimensao: "Custo", impactoPrazoDias: 0, impactoCustoCentavos: 250000000,
    estrategia: "Transferir", instrumento: "Hedge financeiro",
    plano: "Contratação de hedge cambial (instrumento financeiro) para as parcelas remanescentes em moeda estrangeira.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-11-30", custoRespostaCentavos: 9500000, responsavelPlanoId: 13,
    aprovacao: { exigida: true, situacao: "Aprovado", porId: 2, data: "2026-02-20" },
    cadenciaDias: 60, ultimaRevisao: "2026-09-10", proximaRevisao: "2026-11-09", situacao: "Em tratamento",
    revisoes: [
      { data: "2026-09-10", porId: 13, tipo: "residual", situacaoApurada: "Risco reduzido", de: 12, para: 9, p: 3, i: 3, gatilho: false, texto: "Hedge de 70% das parcelas contratado; impacto em custo caiu para 3." },
      { data: "2026-03-02", porId: 13, tipo: "residual", situacaoApurada: "Risco reduzido", de: 16, para: 12, p: 3, i: 4, gatilho: false, texto: "Plano de hedge aprovado; primeiras parcelas protegidas." },
      { data: "2026-02-10", porId: 7, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 16, p: 4, i: 4, gatilho: false, texto: "Avaliação inicial no plano de compras." }
    ] },

  { id: 7, projetoId: 1, codigo: "RSK-TN-2026-0007", titulo: "Chuvas acima da média histórica durante a terraplenagem",
    categoria: "Ambiental", subcategoria: "Clima", natureza: "Ameaça", donoId: 4, identificadoPorId: 3, identificadoEm: "2026-01-20",
    origemTipo: "Workshop de riscos", origem: "Workshop de riscos",
    causa: "Previsão de chuvas intensas no último trimestre",
    consequencia: "Paralisação da terraplenagem da fase 2 e carreamento de sedimentos",
    descricao: "Frentes de terraplenagem expostas no período chuvoso.",
    gatilho: "Previsão de mais de 60 mm em 24 h",
    inerente: { p: 4, i: 3, dimensoes: { prazo: 3, custo: 2, escopo: 1, sms: 2, imagem: 2, legal: 2 } },
    residual: { p: 3, i: 2, dimensoes: { prazo: 2, custo: 2, escopo: 1, sms: 1, imagem: 1, legal: 1 } }, riscoVida: false,
    dimensao: "Prazo", impactoPrazoDias: 12, impactoCustoCentavos: 45000000,
    estrategia: "Mitigar", plano: "Drenagem provisória, bacias de sedimentação e reprogramação das frentes críticas.",
    severidadeAlvo: "baixo", prazoAlvo: "2026-12-20", custoRespostaCentavos: 22000000, responsavelPlanoId: 3,
    aprovacao: { exigida: false },
    cadenciaDias: 30, ultimaRevisao: "2026-09-12", proximaRevisao: "2026-10-12", situacao: "Monitorado",
    revisoes: [
      { data: "2026-09-12", porId: 4, tipo: "residual", situacaoApurada: "Risco reduzido", de: 12, para: 6, p: 3, i: 2, gatilho: false, texto: "Drenagem provisória concluída." },
      { data: "2026-01-20", porId: 3, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 12, p: 4, i: 3, gatilho: false, texto: "Avaliação inicial no workshop de riscos." }
    ] },

  /* Encerrados (fora da carteira ativa) */
  { id: 8, projetoId: 1, codigo: "RSK-TN-2026-0008", titulo: "Paralisação do transporte de cimento e aço por greve",
    categoria: "Suprimentos", subcategoria: "Logística", natureza: "Ameaça", donoId: 7, identificadoPorId: 7, identificadoEm: "2026-03-10",
    origemTipo: "Workshop de riscos", origem: "Workshop de riscos",
    causa: "Mobilização nacional dos transportadores anunciada para o segundo trimestre",
    consequencia: "Interrupção das concretagens e da montagem de armaduras",
    descricao: "Canteiro sem estoque de segurança de cimento e aço.", gatilho: "Assembleia da categoria marcar data de paralisação",
    inerente: { p: 2, i: 4, dimensoes: { prazo: 4, custo: 2, escopo: 1, sms: 1, imagem: 1, legal: 1 } },
    residual: { p: 2, i: 3, dimensoes: { prazo: 3, custo: 2, escopo: 1, sms: 1, imagem: 1, legal: 1 } }, riscoVida: false,
    dimensao: "Prazo", impactoPrazoDias: 15, impactoCustoCentavos: 35000000,
    estrategia: "Mitigar", plano: "Estoque de segurança de 15 dias de cimento e aço no canteiro.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-05-30", custoRespostaCentavos: 4000000, responsavelPlanoId: 7,
    aprovacao: { exigida: false },
    cadenciaDias: 60, ultimaRevisao: "2026-07-31", proximaRevisao: null, situacao: "Encerrado",
    encerramento: { motivo: "Não se materializou", data: "2026-07-31", porId: 2, licao: "Estoque de segurança de insumos críticos no canteiro reduziu a exposição a paralisações logísticas.", licaoRef: "LA-TN-2026-0008" },
    revisoes: [
      { data: "2026-07-31", porId: 7, tipo: "revisao", situacaoApurada: "Risco superado", de: 6, para: 6, p: 2, i: 3, gatilho: false, texto: "Janela de exposição encerrada sem paralisação." },
      { data: "2026-04-12", porId: 7, tipo: "residual", situacaoApurada: "Risco reduzido", de: 8, para: 6, p: 2, i: 3, gatilho: false, texto: "Estoque de segurança formado." },
      { data: "2026-03-10", porId: 7, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 8, p: 2, i: 4, gatilho: false, texto: "Avaliação inicial." }
    ] },
  { id: 9, projetoId: 1, codigo: "RSK-TN-2026-0009", titulo: "Interferência não mapeada no subsolo da fundação F-12",
    categoria: "Técnico", subcategoria: "Fundações", natureza: "Ameaça", donoId: 6, identificadoPorId: 11, identificadoEm: "2026-02-02",
    origemTipo: "Workshop de riscos", origem: "Workshop de riscos",
    causa: "Área industrial existente com cadastro de interferências antigo",
    consequencia: "Paralisação da escavação e reprojeto da fundação F-12",
    descricao: "Escavação da F-12 próxima a linhas antigas de água de processo.", gatilho: "Escavação encontrar material não previsto",
    inerente: { p: 2, i: 4, dimensoes: { prazo: 4, custo: 4, escopo: 2, sms: 2, imagem: 1, legal: 1 } },
    residual: { p: 2, i: 4, dimensoes: { prazo: 4, custo: 4, escopo: 2, sms: 2, imagem: 1, legal: 1 } }, riscoVida: false,
    dimensao: "Custo", impactoPrazoDias: 20, impactoCustoCentavos: 45000000,
    estrategia: "Aceitar", plano: "Aceito com base no cadastro de interferências do cliente; custo de varredura com georradar não justificado na época. Contingência reservada no orçamento.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-04-30", custoRespostaCentavos: 0, responsavelPlanoId: 6,
    aprovacao: { exigida: false },
    cadenciaDias: 60, ultimaRevisao: "2026-04-12", proximaRevisao: null, situacao: "Materializado",
    encerramento: { motivo: "Materializado", data: "2026-04-15", porId: 2, impactoRealPrazoDias: 21, impactoRealCustoCentavos: 40000000,
      smRef: "SM-TN-2026-0002", licao: "Exigir varredura com georradar e sondagens antes de liberar fundações em área industrial existente.", licaoRef: "LA-TN-2026-0001" },
    revisoes: [
      { data: "2026-04-12", porId: 11, tipo: "revisao", situacaoApurada: "Risco materializado", de: 8, para: 8, p: 2, i: 4, gatilho: true, texto: "Escavação encontrou tubulação antiga não cadastrada na F-12." },
      { data: "2026-02-02", porId: 11, tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: 8, p: 2, i: 4, gatilho: false, texto: "Avaliação inicial." }
    ] }
];

/* Fotografia mensal do score residual somado das ameaças ativas (tabela RiscoRevisao).
   O mês da data de referência é recalculado pela api a partir do registro atual. */
window.MOCK.riscosEvolucao = [
  { projetoId: 1, mes: "2026-04", scoreResidual: 38 },
  { projetoId: 1, mes: "2026-05", scoreResidual: 41 },
  { projetoId: 1, mes: "2026-06", scoreResidual: 47 },
  { projetoId: 1, mes: "2026-07", scoreResidual: 67 },
  { projetoId: 1, mes: "2026-08", scoreResidual: 62 },
  { projetoId: 1, mes: "2026-09", scoreResidual: 56 }
];

/* Análise do período (05): comentário executivo e analítico por tipo (Semanal ou Mensal) e período,
   inserido e editado em modal no módulo. desvios: comentário por desvio negativo detectado (chave
   calculada pela api com os dados do período). Semana 39 e setembro sem análise (em andamento). */
window.MOCK.analisesPeriodo = (window.MOCK.analisesPeriodo || []).concat([
  { id: 31, projetoId: 1, modulo: "riscos", tipo: "Semanal", periodo: "2026-S38", criadoPorId: 2, criadoEm: "2026-09-21T16:00", atualizadoPorId: 2, atualizadoEm: "2026-09-21T16:00",
    analise: "O projeto mantém 7 riscos ativos, dois de nível crítico (uma ameaça e uma oportunidade), com exposição de R$ 3,4 milhões. O score residual consolidado caiu de 67 em julho para 56 em setembro, efeito dos planos de resposta da licença de operação e do subsolo das fundações. Uma revisão está vencida e deve ser feita na S39. Tendência: redução moderada da exposição até outubro, condicionada à obtenção da licença de operação e à confirmação da antecipação dos transformadores (oportunidade)." },
  { id: 32, projetoId: 1, modulo: "riscos", tipo: "Mensal", periodo: "2026-08", criadoPorId: 2, criadoEm: "2026-09-03T15:10", atualizadoPorId: 2, atualizadoEm: "2026-09-03T15:10",
    analise: "Agosto registra um novo risco identificado e redução do score residual de 67 para 62 após a aprovação dos planos de resposta. A exposição de R$ 3,4 milhões está concentrada na licença de operação e na variação cambial dos equipamentos importados. A série de abril a julho mostrou crescimento contínuo do score; agosto marca a inversão da curva. Tendência: queda gradual se o protocolo complementar da licença for aceito pelo órgão ambiental em setembro." }
]);
