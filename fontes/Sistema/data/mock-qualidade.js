/* ==========================================================================
   mock-qualidade.js | 06 Gestão da Qualidade (dados fictícios, proposta).
   rncs: relatórios de não conformidade (ISO 9001 8.7 e 10.2). Situação:
     Aberta > Em análise de causa > Ação corretiva > Verificação de eficácia > Encerrada
     (Cancelada só antes da ação corretiva). Ações corretivas são registros da Central
     (origem RNC). Disposição "Reparo" ou "Usar como está" exige concessão do cliente.
   itps: planos de inspeção e testes por disciplina, com os pontos (H = espera
     obrigatória, W = testemunho, R = revisão de registro).
   inspecoesQualidade: registro de inspeção por ponto do ITP; reprovação gera RNC.
   auditorias: programa de auditorias (ISO 19011) com constatações; constatação do
     tipo Não conformidade gera RNC.
   ========================================================================== */
window.MOCK = window.MOCK || {};

window.MOCK.rncs = [
  { id: 1, projetoId: 1, codigo: "RNC-TN-2026-0001", data: "2026-05-12", origem: "Inspeção", origemRef: null, disciplina: "Civil", empresaId: 6,
    descricao: "Segregação do concreto no bloco B-07 após a desforma.", severidade: "Maior",
    contencao: "Área isolada e concretagem dos blocos seguintes suspensa até o plano de lançamento revisado.",
    responsavelId: 11, disposicao: "Reparo", concessao: { referencia: "Carta MHS-ENG-0412 (aceite do reparo com graute)", data: "2026-05-20" },
    metodo: "5 porquês", causaRaiz: "Altura de lançamento acima do especificado, sem tromba.",
    prazo: "2026-06-11", encerramento: "2026-06-30", situacao: "Encerrada", custoNaoQualidadeCentavos: 1850000, abertaPorId: 9,
    eficacia: { data: "2026-06-30", eficaz: true, texto: "Dez concretagens seguintes sem segregação; tromba e altura máxima de 2 m incorporadas ao procedimento.", porId: 9 },
    licaoRef: null },
  { id: 2, projetoId: 1, codigo: "RNC-TN-2026-0002", data: "2026-07-21", origem: "Inspeção", origemRef: null, disciplina: "Civil", empresaId: 6,
    descricao: "Resistência do concreto (fck) abaixo do especificado em 3 corpos de prova da fundação F-15.", severidade: "Maior",
    contencao: "Carregamento da fundação F-15 suspenso até a extração de testemunhos.",
    responsavelId: 11, disposicao: "Usar como está", concessao: { referencia: "Parecer estrutural MHS-EST-0088 (testemunhos aprovados)", data: "2026-08-05" },
    metodo: "Diagrama de Ishikawa", causaRaiz: "Relação água/cimento alterada na obra sem controle.",
    prazo: "2026-08-20", encerramento: null, situacao: "Verificação de eficácia", custoNaoQualidadeCentavos: 420000, abertaPorId: 9,
    verificacaoPrevista: "2026-10-05", licaoRef: null },
  { id: 3, projetoId: 1, codigo: "RNC-TN-2026-0003", data: "2026-09-10", origem: "Fornecedor", origemRef: null, disciplina: "Mecânica", empresaId: 3,
    descricao: "Certificados de material de 6 válvulas divergentes da corrida informada.", severidade: "Menor",
    contencao: "Válvulas segregadas no almoxarifado com etiqueta de bloqueio.",
    responsavelId: 7, disposicao: "Rejeitar", concessao: null,
    metodo: "5 porquês", causaRaiz: "Falha no controle de rastreabilidade do fornecedor.",
    prazo: "2026-10-25", encerramento: "2026-09-22", situacao: "Encerrada", custoNaoQualidadeCentavos: 0, abertaPorId: 9,
    eficacia: { data: "2026-09-22", eficaz: true, texto: "Lote substituto recebido com certificados conferidos contra a corrida; auditoria de rastreabilidade programada.", porId: 9 },
    licaoRef: null },
  { id: 4, projetoId: 1, codigo: "RNC-TN-2026-0004", data: "2026-08-18", origem: "Inspeção", origemRef: "INS-2026-0145", disciplina: "Tubulação", empresaId: 1,
    descricao: "Seis juntas soldadas da linha 310-P-014 reprovadas no ultrassom.", severidade: "Maior",
    contencao: "Linha 310-P-014 bloqueada para teste hidrostático; soldador afastado da frente.",
    responsavelId: 5, disposicao: "Retrabalho", concessao: null,
    metodo: "Árvore de causas", causaRaiz: "Soldador sem qualificação para o processo e a espessura.",
    prazo: "2026-09-17", encerramento: null, situacao: "Ação corretiva", custoNaoQualidadeCentavos: 3400000, abertaPorId: 9, licaoRef: null },
  { id: 5, projetoId: 1, codigo: "RNC-TN-2026-0005", data: "2026-09-19", origem: "Auditoria", origemRef: "AUD-TN-2026-02", disciplina: "Mecânica", empresaId: 1,
    descricao: "Torque dos parafusos da estrutura PR-02 fora do especificado em 12 ligações.", severidade: "Maior",
    contencao: "Montagem do nível 2 do PR-02 suspensa até o reaperto.",
    responsavelId: 5, disposicao: null, concessao: null,
    metodo: null, causaRaiz: null, prazo: "2026-10-19", encerramento: null, situacao: "Em análise de causa", custoNaoQualidadeCentavos: 0, abertaPorId: 9, licaoRef: null },
  { id: 6, projetoId: 1, codigo: "RNC-TN-2026-0006", data: "2026-09-23", origem: "Processo", origemRef: null, disciplina: "Mecânica", empresaId: 5,
    descricao: "Desenho de montagem do moinho em revisão desatualizada na frente de trabalho.", severidade: "Menor",
    contencao: "Cópias recolhidas e revisão vigente distribuída à frente.",
    responsavelId: null, disposicao: null, concessao: null,
    metodo: null, causaRaiz: null, prazo: "2026-11-07", encerramento: null, situacao: "Aberta", custoNaoQualidadeCentavos: 0, abertaPorId: 9, licaoRef: null }
];

/* Pontos do ITP: tipo H (espera: a atividade seguinte só é liberada com o registro aprovado),
   W (testemunho: notificação prévia ao cliente) ou R (revisão de registros). */
(function () {
  function pts(lista) {
    return lista.map(function (p, k) { return { id: k + 1, atividade: p[0], tipo: p[1], criterio: p[2], referencia: p[3], responsavel: p[4] || "Contratada" }; });
  }
  window.MOCK.itps = [
    { id: 1, projetoId: 1, codigo: "ITP-TN-CIV-01", disciplina: "Civil", titulo: "Concreto estrutural", revisao: 1, data: "2026-02-10", empresaId: 6,
      aprovadoCliente: true, aprovacao: { referencia: "Carta MHS-QUA-0012", data: "2026-02-18", porId: 9 }, pontos: pts([
        ["Recebimento e ensaio de materiais (cimento e agregados)", "R", "Certificados e ensaios conforme especificação", "NBR 12654"],
        ["Locação e topografia das fôrmas", "W", "Tolerância de ±10 mm em planta", "ET-CIV-001"],
        ["Liberação de armadura", "H", "Bitolas, espaçamentos e recobrimento de projeto", "NBR 14931"],
        ["Liberação de fôrmas e embutidos", "H", "Estanqueidade, prumo e embutidos conferidos", "ET-CIV-001"],
        ["Concretagem", "W", "Abatimento 100 ± 20 mm; temperatura até 32 °C", "NBR 7212"],
        ["Moldagem de corpos de prova", "W", "Um exemplar a cada caminhão", "NBR 5738", "Laboratório"],
        ["Cura", "R", "Cura úmida por 7 dias", "ET-CIV-001"],
        ["Desforma e inspeção visual", "W", "Sem segregação, ninhos ou fissuras", "NBR 14931"],
        ["Ensaios de corpo de prova", "R", "fck aos 28 dias igual ou acima do projeto", "NBR 5739", "Laboratório"],
        ["Tolerâncias dimensionais", "W", "Conforme tabela de tolerâncias do projeto", "ET-CIV-001"],
        ["Liberação para montagem", "H", "Dossiê do elemento completo", "PG-QUA-005", "Fiscalização"]
      ]) },
    { id: 2, projetoId: 1, codigo: "ITP-TN-MEC-01", disciplina: "Mecânica", titulo: "Montagem de equipamentos rotativos", revisao: 0, data: "2026-04-15", empresaId: 1,
      aprovadoCliente: true, aprovacao: { referencia: "Carta MHS-QUA-0024", data: "2026-04-22", porId: 9 }, pontos: pts([
        ["Recebimento e preservação", "R", "Equipamento sem avarias e com preservação registrada", "PG-MEC-002"],
        ["Nivelamento da base do moinho", "H", "Desvio máximo de 0,05 mm/m", "Manual do fabricante"],
        ["Grauteamento", "W", "Graute sem vazios; cura conforme fabricante", "ET-MEC-004"],
        ["Torque de ligações estruturais", "W", "Torque conforme tabela do projeto", "ET-EST-002"],
        ["Alinhamento de acoplamentos", "H", "Desalinhamento até 0,05 mm", "Manual do fabricante"],
        ["Alinhamento a laser do motor", "H", "Relatório do alinhamento a laser", "Manual do fabricante"],
        ["Lubrificação inicial", "R", "Lubrificante e volume conforme plano", "PG-MEC-002"],
        ["Teste de giro livre", "W", "Giro sem ruído ou interferência", "PG-MEC-006"],
        ["Liberação para comissionamento", "H", "Checklist de pré-comissionamento assinado", "PG-COM-001", "Fiscalização"]
      ]) },
    { id: 3, projetoId: 1, codigo: "ITP-TN-TUB-01", disciplina: "Tubulação", titulo: "Fabricação e montagem de tubulação", revisao: 2, data: "2026-03-20", empresaId: 1,
      aprovadoCliente: true, aprovacao: { referencia: "Carta MHS-QUA-0019", data: "2026-03-27", porId: 9 }, pontos: pts([
        ["Qualificação de procedimentos e soldadores (EPS e RQS)", "R", "EPS e RQS válidos para processo, posição e espessura", "ASME IX"],
        ["Recebimento de materiais e certificados", "R", "Certificado conferido com a corrida", "ASME B31.3"],
        ["Ajuste e ponteamento", "W", "Abertura de raiz e alinhamento conforme EPS", "ASME B31.3"],
        ["Ultrassom de soldas", "H", "Sem descontinuidade acima do critério de aceitação", "ASME B31.3", "Laboratório"],
        ["Líquido penetrante", "W", "Sem indicação relevante", "ASME V", "Laboratório"],
        ["Registros de soldagem", "R", "Mapa de soldas e rastreabilidade completos", "PG-TUB-003"],
        ["Teste hidrostático", "H", "1,5 vez a pressão de projeto por 30 minutos sem queda", "ASME B31.3", "Fiscalização"],
        ["Limpeza e flushing", "W", "Água limpa na saída por 15 minutos", "PG-TUB-005"],
        ["Liberação para pintura", "H", "Dossiê da linha completo", "PG-QUA-005", "Fiscalização"]
      ]) },
    { id: 4, projetoId: 1, codigo: "ITP-TN-ELE-01", disciplina: "Elétrica", titulo: "Montagem elétrica e testes", revisao: 0, data: "2026-05-05", empresaId: 1,
      aprovadoCliente: true, aprovacao: { referencia: "Carta MHS-QUA-0031", data: "2026-05-14", porId: 9 }, pontos: pts([
        ["Recebimento de painéis", "R", "Painel sem avarias e com relatório de teste de fábrica", "PG-ELE-001"],
        ["Lançamento de cabos", "W", "Raio de curvatura e identificação conforme projeto", "NBR 14039"],
        ["Resistência de isolamento dos cabos", "W", "Isolamento acima de 100 MΩ", "NBR 14039"],
        ["Continuidade de aterramento", "W", "Resistência até 10 Ω", "NBR 5419"],
        ["Torque de conexões", "W", "Torque conforme fabricante", "ET-ELE-003"],
        ["Teste funcional de painéis", "H", "Lógica e intertravamentos conforme diagrama", "ET-ELE-005", "Fiscalização"],
        ["Energização", "H", "Permissão de trabalho e checklist de energização", "PG-COM-002", "Cliente"]
      ]) },
    { id: 5, projetoId: 1, codigo: "ITP-TN-INS-01", disciplina: "Instrumentação", titulo: "Montagem e calibração de instrumentos", revisao: 0, data: "2026-09-21", empresaId: 1,
      aprovadoCliente: false, pontos: pts([
        ["Recebimento e certificado de calibração", "R", "Certificado válido e rastreável à RBC", "PG-INS-001"],
        ["Montagem e suportação", "W", "Conforme típico de montagem", "ET-INS-002"],
        ["Teste de estanqueidade das linhas de impulso", "W", "Sem queda de pressão em 15 minutos", "ET-INS-002"],
        ["Teste de malha", "H", "Sinal do campo ao supervisório com erro até 0,5%", "ET-INS-004", "Fiscalização"]
      ]) }
  ];
})();

window.MOCK.inspecoesQualidade = [
  { id: 1, projetoId: 1, codigo: "INS-2026-0141", itpId: 1, pontoId: 3, ponto: "Liberação de armadura", tipoPonto: "H", data: "2026-09-02", empresaId: 6, inspetorId: 9, resultado: "Aprovado" },
  { id: 2, projetoId: 1, codigo: "INS-2026-0142", itpId: 1, pontoId: 5, ponto: "Concretagem", tipoPonto: "W", data: "2026-09-03", empresaId: 6, inspetorId: 9, resultado: "Aprovado" },
  { id: 3, projetoId: 1, codigo: "INS-2026-0145", itpId: 3, pontoId: 4, ponto: "Ultrassom de soldas", tipoPonto: "H", data: "2026-08-18", empresaId: 1, inspetorId: 9, resultado: "Reprovado", rncRef: "RNC-TN-2026-0004",
    observacao: "Seis juntas com falta de fusão na raiz." },
  { id: 4, projetoId: 1, codigo: "INS-2026-0147", itpId: 2, pontoId: 2, ponto: "Nivelamento da base do moinho", tipoPonto: "H", data: "2026-09-05", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 5, projetoId: 1, codigo: "INS-2026-0150", itpId: 4, pontoId: 3, ponto: "Resistência de isolamento dos cabos", tipoPonto: "W", data: "2026-09-08", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 6, projetoId: 1, codigo: "INS-2026-0152", itpId: 3, pontoId: 7, ponto: "Teste hidrostático", tipoPonto: "H", data: "2026-09-11", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 7, projetoId: 1, codigo: "INS-2026-0155", itpId: 2, pontoId: 4, ponto: "Torque de ligações estruturais", tipoPonto: "W", data: "2026-09-18", empresaId: 1, inspetorId: 9, resultado: "Reprovado", rncRef: "RNC-TN-2026-0005",
    observacao: "Doze ligações do PR-02 abaixo do torque; constatação confirmada na auditoria AUD-TN-2026-02." },
  { id: 8, projetoId: 1, codigo: "INS-2026-0157", itpId: 1, pontoId: 3, ponto: "Liberação de armadura", tipoPonto: "H", data: "2026-09-16", empresaId: 6, inspetorId: 9, resultado: "Aprovado" },
  { id: 9, projetoId: 1, codigo: "INS-2026-0160", itpId: 4, pontoId: 4, ponto: "Continuidade de aterramento", tipoPonto: "W", data: "2026-09-19", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 10, projetoId: 1, codigo: "INS-2026-0162", itpId: 3, pontoId: 6, ponto: "Registros de soldagem", tipoPonto: "R", data: "2026-09-22", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 11, projetoId: 1, codigo: "INS-2026-0163", itpId: 2, pontoId: 5, ponto: "Alinhamento de acoplamentos", tipoPonto: "H", data: "2026-09-23", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 12, projetoId: 1, codigo: "INS-2026-0164", itpId: 1, pontoId: 9, ponto: "Ensaios de corpo de prova", tipoPonto: "R", data: "2026-09-24", empresaId: 6, inspetorId: 9, resultado: "Aprovado" },
  /* Meses anteriores (série do painel) */
  { id: 13, projetoId: 1, codigo: "INS-2026-0098", itpId: 1, pontoId: 3, ponto: "Liberação de armadura", tipoPonto: "H", data: "2026-06-04", empresaId: 6, inspetorId: 9, resultado: "Aprovado" },
  { id: 14, projetoId: 1, codigo: "INS-2026-0102", itpId: 1, pontoId: 5, ponto: "Concretagem", tipoPonto: "W", data: "2026-06-12", empresaId: 6, inspetorId: 9, resultado: "Aprovado com ressalva",
    observacao: "Abatimento no limite superior em um caminhão; caminhão seguinte aprovado." },
  { id: 15, projetoId: 1, codigo: "INS-2026-0110", itpId: 3, pontoId: 3, ponto: "Ajuste e ponteamento", tipoPonto: "W", data: "2026-06-25", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 16, projetoId: 1, codigo: "INS-2026-0117", itpId: 1, pontoId: 9, ponto: "Ensaios de corpo de prova", tipoPonto: "R", data: "2026-07-20", empresaId: 6, inspetorId: 9, resultado: "Reprovado", rncRef: "RNC-TN-2026-0002",
    observacao: "Três corpos de prova da F-15 abaixo do fck." },
  { id: 17, projetoId: 1, codigo: "INS-2026-0121", itpId: 3, pontoId: 4, ponto: "Ultrassom de soldas", tipoPonto: "H", data: "2026-07-28", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 18, projetoId: 1, codigo: "INS-2026-0126", itpId: 2, pontoId: 1, ponto: "Recebimento e preservação", tipoPonto: "R", data: "2026-08-04", empresaId: 1, inspetorId: 9, resultado: "Aprovado" },
  { id: 19, projetoId: 1, codigo: "INS-2026-0131", itpId: 1, pontoId: 4, ponto: "Liberação de fôrmas e embutidos", tipoPonto: "H", data: "2026-08-12", empresaId: 6, inspetorId: 9, resultado: "Aprovado" },
  { id: 20, projetoId: 1, codigo: "INS-2026-0136", itpId: 4, pontoId: 2, ponto: "Lançamento de cabos", tipoPonto: "W", data: "2026-08-26", empresaId: 1, inspetorId: 9, resultado: "Aprovado com ressalva",
    observacao: "Identificação de 4 cabos faltante; corrigida na própria inspeção." }
];

window.MOCK.auditorias = [
  { id: 1, projetoId: 1, codigo: "AUD-TN-2026-01", tipo: "Contratada", auditadoId: 6, escopo: "Controle tecnológico do concreto", data: "2026-06-10",
    situacao: "Realizada", realizadaEm: "2026-06-10", itensVerificados: 40, itensConformes: 36, auditorId: 9, criterio: "ET-CIV-001 e NBR 12655",
    constatacoes: [
      { tipo: "Não conformidade", descricao: "Ensaios de abatimento sem registro em 3 caminhões.", requisito: "NBR 12655, 6.2", rncRef: "RNC-TN-2026-0001" },
      { tipo: "Observação", descricao: "Laboratório sem controle de temperatura da câmara úmida.", requisito: "NBR 5738" },
      { tipo: "Observação", descricao: "Rastreabilidade do lote de cimento por nota fiscal, sem número do lote.", requisito: "ET-CIV-001" },
      { tipo: "Oportunidade de melhoria", descricao: "Painel diário de resultados de fck na frente de obra.", requisito: "" }
    ] },
  { id: 2, projetoId: 1, codigo: "AUD-TN-2026-02", tipo: "Contratada", auditadoId: 1, escopo: "Qualificação de soldadores e procedimentos", data: "2026-09-17",
    situacao: "Realizada", realizadaEm: "2026-09-17", itensVerificados: 35, itensConformes: 29, auditorId: 9, criterio: "ASME IX e PG-TUB-003",
    constatacoes: [
      { tipo: "Não conformidade", descricao: "Torque das ligações do PR-02 sem registro e abaixo do especificado.", requisito: "ET-EST-002", rncRef: "RNC-TN-2026-0005" },
      { tipo: "Observação", descricao: "Dois RQS vencem em outubro sem plano de requalificação.", requisito: "ASME IX, QW-322" },
      { tipo: "Observação", descricao: "Controle de estufas de eletrodos sem registro no turno da noite.", requisito: "PG-TUB-003" },
      { tipo: "Observação", descricao: "Mapa de soldas da linha 310-P-022 incompleto.", requisito: "PG-TUB-003" },
      { tipo: "Oportunidade de melhoria", descricao: "Liberar o soldador por processo no crachá de campo.", requisito: "" },
      { tipo: "Oportunidade de melhoria", descricao: "Indicador semanal de reparo de soldas por soldador.", requisito: "" }
    ] },
  { id: 3, projetoId: 1, codigo: "AUD-TN-2026-03", tipo: "Fornecedor", auditadoId: 3, escopo: "Rastreabilidade de materiais", data: "2026-10-14",
    situacao: "Planejada", auditorId: 9, criterio: "PG-SUP-004" },
  { id: 4, projetoId: 1, codigo: "AUD-TN-2026-04", tipo: "Interna", auditadoId: 13, escopo: "Controle de documentos de engenharia em campo", data: "2026-10-28",
    situacao: "Planejada", auditorId: 9, criterio: "PG-DOC-001" },
  { id: 5, projetoId: 1, codigo: "AUD-TN-2026-05", tipo: "Contratada", auditadoId: 5, escopo: "Gestão de mudanças de engenharia e revisões de desenho", data: "2026-09-15",
    situacao: "Planejada", auditorId: 9, criterio: "PG-DOC-001 e PG-ENG-002" }
];

/* Análise do período do 06 (S38 e agosto); setembro e S39 pendentes (período em andamento) */
window.MOCK.analisesPeriodo = (window.MOCK.analisesPeriodo || []).concat([
  { id: 51, projetoId: 1, modulo: "qualidade", tipo: "Semanal", periodo: "2026-S38", criadoPorId: 9, criadoEm: "2026-09-21T09:00", atualizadoPorId: 9, atualizadoEm: "2026-09-21T09:00",
    analise: "Semana com 3 inspeções e 1 reprovação (torque das ligações do PR-02), que abriu a RNC-TN-2026-0005 e confirmou a constatação da auditoria AUD-TN-2026-02 (82,9% de conformidade, abaixo da meta de 90%). O projeto fecha a semana com 4 RNC em aberto e a RNC-TN-2026-0004 (soldas da linha 310-P-014) com prazo de tratamento vencido: o reparo depende da requalificação do soldador. A auditoria de mudanças de engenharia (AUD-TN-2026-05) está atrasada, com reprogramação em negociação com a Épsilon. Tendência: aprovação em inspeções abaixo da meta enquanto a montagem mecânica não estabilizar o controle de torque." },
  { id: 52, projetoId: 1, modulo: "qualidade", tipo: "Mensal", periodo: "2026-08", criadoPorId: 9, criadoEm: "2026-09-02T09:00", atualizadoPorId: 9, atualizadoEm: "2026-09-02T09:00",
    analise: "Agosto teve 4 inspeções com 75% de aprovação: a reprovação do ultrassom da linha 310-P-014 abriu a RNC-TN-2026-0004 (R$ 34 mil de custo da não qualidade com o reparo das 6 juntas). O mês fecha com 2 RNC em aberto; a RNC-TN-2026-0002 (fck da F-15) segue para verificação de eficácia após a concessão do cliente. Tendência: a qualificação de soldadores passa a ser auditada em setembro e o controle de relação água/cimento já mostra resultados nas concretagens." }
]);
