/* ==========================================================================
   mock-central.js | 01 Central de Ações (dados fictícios).
   atas: cabeçalho de cada revisão (linhagem = número da ata).
   acoes: anotações e ações de todas as origens. O status NÃO é gravado:
   é calculado por GI.regras.statusAcao na data de referência.
   Itens de Punch list não ficam aqui: a api gera a ação a partir do item
   (relação 1 para 1, status sincronizado).
   ========================================================================== */
window.MOCK = window.MOCK || {};

window.MOCK.atas = [
  { id: 1, escopo: "Projeto", projetoId: 1, numero: "TN-2026-0028", revisao: 0, data: "2026-06-25",
    tipoReuniao: "Coordenação de obra", diretoria: "Diretoria de Projetos", unidade: "Unidade Horizonte", elaboradoPorId: 3,
    assunto: "Coordenação quinzenal de obra: frentes civis e montagem", empresaPrincipalId: 6, empresasIds: [6, 1],
    participantesIds: [1, 2, 3, 5, 9, 10, 11] },
  { id: 2, escopo: "Projeto", projetoId: 1, numero: "TN-2026-0031", revisao: 0, data: "2026-07-03",
    tipoReuniao: "Licenciamento", diretoria: "Diretoria de Projetos", unidade: "Unidade Horizonte", elaboradoPorId: 1,
    assunto: "Licenciamento ambiental: condicionantes da licença de operação", empresaPrincipalId: 5, empresasIds: [5],
    participantesIds: [1, 2, 4, 6, 7] },
  { id: 3, escopo: "Projeto", projetoId: 1, numero: "TN-2026-0031", revisao: 1, data: "2026-08-04",
    tipoReuniao: "Licenciamento", diretoria: "Diretoria de Projetos", unidade: "Unidade Horizonte", elaboradoPorId: 1,
    assunto: "Licenciamento ambiental: condicionantes da licença de operação", empresaPrincipalId: 5, empresasIds: [5],
    participantesIds: [1, 2, 4, 6, 7] },
  { id: 4, escopo: "Projeto", projetoId: 1, numero: "TN-2026-0036", revisao: 0, data: "2026-09-10",
    tipoReuniao: "Status com o cliente", diretoria: "Diretoria de Projetos", unidade: "Unidade Horizonte", elaboradoPorId: 1,
    assunto: "Reunião mensal de status com o cliente: agosto de 2026", empresaPrincipalId: null, empresasIds: [],
    participantesIds: [1, 2, 3, 7, 13] },
  { id: 5, escopo: "Projeto", projetoId: 1, numero: "TN-2026-0038", revisao: 0, data: "2026-09-22",
    tipoReuniao: "Segurança", diretoria: "Diretoria de Projetos", unidade: "Unidade Horizonte", elaboradoPorId: 10,
    assunto: "Análise da ocorrência de alto potencial de 12/09/2026", empresaPrincipalId: 1, empresasIds: [1],
    participantesIds: [1, 2, 5, 10, 12] },
  { id: 7, escopo: "Projeto", projetoId: 1, numero: "TN-2026-0034", revisao: 0, data: "2026-09-01",
    tipoReuniao: "Planejamento", diretoria: "Diretoria de Projetos", unidade: "Unidade Horizonte", elaboradoPorId: 1,
    assunto: "Padronização do relatório gerencial do projeto", empresaPrincipalId: null, empresasIds: [],
    participantesIds: [1, 2, 3, 9, 10, 13] }
];

/* Campos: origem, origemRef (código do registro de origem), ataId e item (só origem Ata),
   grupo, assunto, descricao, tipo (Ação | Informação), solicitanteId, responsavelId,
   prevista, replanejada, conclusao, replanejamentos (justificativa obrigatória). */
window.MOCK.acoes = [
  /* Ata TN-2026-0028 */
  { id: 1, projetoId: 1, origem: "Ata", ataId: 1, item: "1.1", grupo: "Obras civis", tipo: "Ação",
    assunto: "Liberação da base do moinho", descricao: "Concluir a cura e liberar a base do moinho para a montagem.",
    solicitanteId: 2, responsavelId: 11, prevista: "2026-07-20", replanejada: null, conclusao: "2026-07-18" },
  { id: 2, projetoId: 1, origem: "Ata", ataId: 1, item: "1.2", grupo: "Obras civis", tipo: "Ação",
    assunto: "Drenagem provisória da área norte", descricao: "Executar drenagem provisória antes do período de chuvas.",
    solicitanteId: 3, responsavelId: 11, prevista: "2026-07-10", replanejada: "2026-08-15", conclusao: "2026-08-14",
    replanejamentos: [{ data: "2026-07-08", de: "2026-07-10", para: "2026-08-15", porId: 11, justificativa: "Equipamento de escavação deslocado para a fundação F-12." }] },
  { id: 3, projetoId: 1, origem: "Ata", ataId: 1, item: "2.1", grupo: "Montagem", tipo: "Ação",
    assunto: "Plano de rigging do moinho", descricao: "Emitir e aprovar o plano de rigging para o içamento da carcaça do moinho.",
    solicitanteId: 2, responsavelId: 5, prevista: "2026-07-30", replanejada: null, conclusao: "2026-07-29" },
  { id: 4, projetoId: 1, origem: "Ata", ataId: 1, item: "2.2", grupo: "Montagem", tipo: "Informação",
    assunto: "Guindaste de 250 t confirmado para outubro", descricao: "Locadora confirmou a janela de 05 a 30/10/2026.",
    solicitanteId: 5, responsavelId: 5, prevista: null, replanejada: null, conclusao: null },
  { id: 5, projetoId: 1, origem: "Ata", ataId: 1, item: "3.1", grupo: "HSE", tipo: "Ação",
    assunto: "Reciclagem de NR-35 da equipe de montagem", descricao: "Reciclar trabalho em altura de 42 montadores antes do início do pipe rack.",
    solicitanteId: 10, responsavelId: 10, prevista: "2026-08-30", replanejada: "2026-09-20", conclusao: null,
    replanejamentos: [{ data: "2026-08-28", de: "2026-08-30", para: "2026-09-20", porId: 10, justificativa: "Instrutor credenciado disponível só em setembro." }] },

  /* Ata TN-2026-0031 Rev 1 */
  { id: 6, projetoId: 1, origem: "Ata", ataId: 3, item: "1.1", grupo: "Licenciamento", tipo: "Ação",
    assunto: "Agendar vistoria técnica com o órgão ambiental", descricao: "Obter data de vistoria para a licença de operação.",
    solicitanteId: 2, responsavelId: 4, prevista: "2026-10-20", replanejada: null, conclusao: null },
  { id: 7, projetoId: 1, origem: "Ata", ataId: 3, item: "1.2", grupo: "Licenciamento", tipo: "Informação",
    assunto: "Fila do órgão ambiental de 120 a 150 dias", descricao: "Prazo informado pelo órgão no protocolo de 12/06/2026.",
    solicitanteId: 4, responsavelId: 4, prevista: null, replanejada: null, conclusao: null },
  { id: 8, projetoId: 1, origem: "Ata", ataId: 3, item: "2.1", grupo: "Engenharia", tipo: "Ação",
    assunto: "Revisar memorial do tratamento de efluentes", descricao: "Atender às exigências técnicas do órgão ambiental.",
    solicitanteId: 4, responsavelId: 6, prevista: "2026-08-28", replanejada: null, conclusao: "2026-08-27" },

  /* Ata TN-2026-0036 */
  { id: 9, projetoId: 1, origem: "Ata", ataId: 4, item: "1.1", grupo: "Planejamento", tipo: "Ação",
    assunto: "Plano de recuperação do atraso da montagem", descricao: "Apresentar plano de recuperação com SPI-alvo de 0,98 até dezembro.",
    solicitanteId: 2, responsavelId: 3, prevista: "2026-09-24", replanejada: null, conclusao: null },
  { id: 10, projetoId: 1, origem: "Ata", ataId: 4, item: "1.2", grupo: "Custos", tipo: "Ação",
    assunto: "Revisar a projeção no término de materiais elétricos", descricao: "Refazer a projeção do item 2.2 com as cotações de cabos de média tensão.",
    solicitanteId: 2, responsavelId: 13, prevista: "2026-09-30", replanejada: null, conclusao: null },
  { id: 11, projetoId: 1, origem: "Ata", ataId: 4, item: "2.1", grupo: "Suprimentos", tipo: "Ação",
    assunto: "Posição semanal dos pedidos críticos ao cliente", descricao: "Enviar toda sexta-feira a posição dos pedidos com folga negativa.",
    solicitanteId: 2, responsavelId: 7, prevista: "2026-10-02", replanejada: null, conclusao: null },
  { id: 12, projetoId: 1, origem: "Ata", ataId: 4, item: "2.2", grupo: "Cliente", tipo: "Informação",
    assunto: "Cliente aprovou estudar a partida parcial", descricao: "Partida parcial com licença de teste será avaliada pelo comitê de mudanças.",
    solicitanteId: 1, responsavelId: 2, prevista: null, replanejada: null, conclusao: null },

  /* Ata TN-2026-0038 */
  { id: 13, projetoId: 1, origem: "Ata", ataId: 5, item: "1.1", grupo: "HSE", tipo: "Ação",
    assunto: "Linha de vida definitiva no pipe rack PR-02", descricao: "Instalar linha de vida definitiva em todo o nível superior do PR-02.",
    solicitanteId: 10, responsavelId: 5, prevista: "2026-10-06", replanejada: null, conclusao: null },
  { id: 14, projetoId: 1, origem: "Ata", ataId: 5, item: "1.2", grupo: "HSE", tipo: "Ação",
    assunto: "Divulgar alerta de segurança da ocorrência", descricao: "Alerta de segurança em todos os DDS da semana.",
    solicitanteId: 10, responsavelId: 10, prevista: "2026-09-23", replanejada: null, conclusao: "2026-09-23" },

  /* Contrato */
  { id: 15, projetoId: 1, origem: "Contrato", origemRef: "CT-2026-014", grupo: "Avaliação da contratada", tipo: "Ação",
    assunto: "Plano de melhoria de prazo da Alfa Montagens", descricao: "Nota 2 em Prazo na avaliação de setembro exige plano de melhoria com evidências.",
    solicitanteId: 12, responsavelId: 5, prevista: "2026-10-10", replanejada: null, conclusao: null },
  { id: 16, projetoId: 1, origem: "Contrato", origemRef: "CLM-TN-2026-0001", grupo: "Claims", tipo: "Ação",
    assunto: "Parecer técnico do pleito de improdutividade", descricao: "Analisar os registros diários e o histograma de mão de obra do período pleiteado.",
    solicitanteId: 12, responsavelId: 2, prevista: "2026-09-15", replanejada: null, conclusao: null },

  /* Suprimentos */
  { id: 17, projetoId: 1, origem: "Suprimentos", origemRef: "PED-2026-0007", grupo: "Diligenciamento", tipo: "Ação",
    assunto: "Inspeção de fábrica dos transformadores", descricao: "Acompanhar o ensaio de aceitação em fábrica (FAT) dos transformadores.",
    solicitanteId: 7, responsavelId: 7, prevista: "2026-09-26", replanejada: null, conclusao: null },
  { id: 18, projetoId: 1, origem: "Suprimentos", origemRef: "PED-2026-0002", grupo: "Diligenciamento", tipo: "Ação",
    assunto: "Negociar antecipação do embarque do britador", descricao: "Folga negativa de 9 dias em relação à data necessária na obra.",
    solicitanteId: 2, responsavelId: 7, prevista: "2026-09-12", replanejada: null, conclusao: null },

  /* Risco */
  { id: 19, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0001", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: true, impacto: false },
    assunto: "Protocolar programa de monitoramento de efluentes", descricao: "Condicionante da licença de operação.",
    solicitanteId: 4, responsavelId: 4, prevista: "2026-09-05", replanejada: "2026-10-05", conclusao: null,
    replanejamentos: [{ data: "2026-09-03", de: "2026-09-05", para: "2026-10-05", porId: 4, justificativa: "Laudo do laboratório acreditado atrasou." }] },
  { id: 20, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0001", item: "2", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: true, impacto: false },
    assunto: "Contratar consultoria credenciada", descricao: "Consultoria para acompanhar o processo junto ao órgão ambiental.",
    solicitanteId: 4, responsavelId: 7, prevista: "2026-08-18", replanejada: null, conclusao: null },
  { id: 21, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0001", item: "3", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: false, impacto: true },
    assunto: "Estudar partida parcial com licença de teste", descricao: "Alternativa para não atrasar a partida.",
    solicitanteId: 4, responsavelId: 6, prevista: "2026-09-26", replanejada: null, conclusao: "2026-09-20" },
  { id: 22, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0003", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: true, impacto: false },
    assunto: "Sondagem complementar nas fundações F-20 a F-28", descricao: "Sondagem a percussão em 6 pontos adicionais da casa de bombas.",
    solicitanteId: 6, responsavelId: 11, prevista: "2026-09-10", replanejada: null, conclusao: null },
  { id: 35, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0002", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: true, impacto: false },
    assunto: "Confirmar a janela do guindaste de 250 t em contrato", descricao: "Cláusula de disponibilidade e multa por indisponibilidade.",
    solicitanteId: 5, responsavelId: 7, prevista: "2026-09-01", replanejada: null, conclusao: "2026-09-01" },
  { id: 36, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0002", item: "2", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: true, impacto: false },
    assunto: "Pré-qualificar segunda locadora de guindaste de 250 t", descricao: "Alternativa em caso de quebra ou indisponibilidade do equipamento contratado.",
    solicitanteId: 5, responsavelId: 7, prevista: "2026-10-02", replanejada: null, conclusao: null },
  { id: 37, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0004", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: true, impacto: false },
    assunto: "Preparar base e pátio para receber os transformadores", descricao: "Liberar a base da subestação unitária antes da entrega antecipada.",
    solicitanteId: 7, responsavelId: 5, prevista: "2026-09-20", replanejada: null, conclusao: "2026-09-18" },
  { id: 38, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0005", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: true, impacto: false },
    assunto: "Aprovar bônus de permanência dos técnicos-chave", descricao: "Bônus pago na partida, condicionado à permanência.",
    solicitanteId: 8, responsavelId: 2, prevista: "2026-09-15", replanejada: null, conclusao: "2026-09-14" },
  { id: 39, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0006", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: false, impacto: true },
    assunto: "Contratar hedge de 70% das parcelas em dólar", descricao: "Parcelas do moinho e do SDCD.",
    solicitanteId: 13, responsavelId: 13, prevista: "2026-09-10", replanejada: null, conclusao: "2026-09-10" },
  { id: 40, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0006", item: "2", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: false, impacto: true },
    assunto: "Contratar hedge das parcelas remanescentes", descricao: "Completar a proteção cambial dos 30% restantes.",
    solicitanteId: 13, responsavelId: 13, prevista: "2026-10-15", replanejada: null, conclusao: null },
  { id: 41, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0007", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: false, impacto: true },
    assunto: "Executar drenagem provisória e bacias de sedimentação da fase 2", descricao: "Antes do início do período chuvoso.",
    solicitanteId: 4, responsavelId: 11, prevista: "2026-09-15", replanejada: null, conclusao: "2026-09-12" },
  { id: 46, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0008", item: "1", grupo: "Plano de resposta", tipo: "Ação", contribuicao: { probabilidade: false, impacto: true },
    assunto: "Formar estoque de segurança de cimento e aço", descricao: "15 dias de consumo no canteiro.",
    solicitanteId: 7, responsavelId: 7, prevista: "2026-04-10", replanejada: null, conclusao: "2026-04-10" },
  { id: 47, projetoId: 1, origem: "Risco", origemRef: "RSK-TN-2026-0009", item: "1", grupo: "Problema", tipo: "Ação", contribuicao: { probabilidade: false, impacto: false },
    assunto: "Tratar a interferência da F-12 (reforço e reprojeto)", descricao: "Risco materializado: reforço da fundação e novo projeto.",
    solicitanteId: 2, responsavelId: 6, prevista: "2026-06-30", replanejada: null, conclusao: "2026-06-26" },

  /* RNC */
  { id: 23, projetoId: 1, origem: "RNC", origemRef: "RNC-TN-2026-0004", grupo: "Ação corretiva", tipo: "Ação",
    assunto: "Refazer soldas reprovadas na linha 310-P-014", descricao: "Reparo e novo ensaio por ultrassom das 6 juntas reprovadas.",
    solicitanteId: 9, responsavelId: 5, prevista: "2026-09-30", replanejada: null, conclusao: null },
  { id: 24, projetoId: 1, origem: "RNC", origemRef: "RNC-TN-2026-0002", grupo: "Eficácia", tipo: "Ação",
    assunto: "Verificar eficácia da ação corretiva de concretagem", descricao: "Conferir resultados de fck das últimas 10 concretagens.",
    solicitanteId: 9, responsavelId: 9, prevista: "2026-09-19", replanejada: null, conclusao: "2026-09-19" },

  /* HSE */
  { id: 25, projetoId: 1, origem: "HSE", origemRef: "OCR-TN-2026-0219", grupo: "Ação corretiva", tipo: "Ação",
    assunto: "Amarração de ferramentas em trabalho em altura", descricao: "Implantar talabartes de ferramenta e inspeção diária nas frentes de altura.",
    solicitanteId: 10, responsavelId: 5, prevista: "2026-09-26", replanejada: null, conclusao: null },
  { id: 26, projetoId: 1, origem: "HSE", origemRef: "OCR-TN-2026-0219", grupo: "Investigação", tipo: "Ação",
    assunto: "Relatório final da investigação da ocorrência HiPo", descricao: "Árvore de causas e plano de ação aprovados pela gerência.",
    solicitanteId: 2, responsavelId: 10, prevista: "2026-10-12", replanejada: null, conclusao: null },

  /* Mudança */
  { id: 27, projetoId: 1, origem: "Mudança", origemRef: "SM-TN-2026-0002", grupo: "Implementação", tipo: "Ação",
    assunto: "Atualizar linha de base do cronograma", descricao: "Incorporar os 21 dias concedidos na fundação F-12.",
    solicitanteId: 2, responsavelId: 3, prevista: "2026-08-30", replanejada: null, conclusao: "2026-09-02" },
  { id: 28, projetoId: 1, origem: "Mudança", origemRef: "SM-TN-2026-0004", grupo: "Implementação", tipo: "Ação",
    assunto: "Incorporar a SM-TN-2026-0004 na EAC", descricao: "Gerar a revisão 3 da EAC com o pipe rack PR-03.",
    solicitanteId: 2, responsavelId: 13, prevista: "2026-10-09", replanejada: null, conclusao: null },

  /* Lição */
  { id: 29, projetoId: 1, origem: "Lição", origemRef: "LA-TN-2026-0003", grupo: "Reuso", tipo: "Ação",
    assunto: "Janela de chuvas no plano da terraplenagem da fase 2", descricao: "Aplicar a lição no planejamento da próxima fase.",
    solicitanteId: 1, responsavelId: 3, prevista: "2026-11-30", replanejada: null, conclusao: null },

  /* Ata TN-2026-0034 (relatório gerencial) */
  { id: 34, projetoId: 1, origem: "Ata", ataId: 7, item: "1.1", grupo: "Relatórios", tipo: "Ação",
    assunto: "Modelo do relatório gerencial semanal e mensal", descricao: "Definir o modelo com Planejamento, Financeiro, Suprimentos e Riscos, em página horizontal.",
    solicitanteId: 1, responsavelId: 3, prevista: "2026-09-19", replanejada: null, conclusao: "2026-09-18" }
];
