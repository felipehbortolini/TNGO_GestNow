/* ==========================================================================
   api.js | Fachada única de dados. As telas NUNCA leem window.MOCK direto:
   chamam GI.api, que hoje lê os mocks em memória e amanhã chama o backend.

   Contrato:
   * Métodos de dados devolvem Promise com CÓPIAS (alterar o retorno não
     altera a base). Erros de validação: Promise rejeitada com { erros: [] }.
   * Valores financeiros em centavos (inteiros). Datas em ISO (AAAA-MM-DD).
   * Síncronos só: sessaoAtual(), referencia(), projetoAtualId() (vêm do
     token/bootstrap da sessão na fase com backend).
   * Portfólio: projetoId null (ou ausente) = visão consolidada dos projetos
     (Portfólio). As funções de leitura aceitam null e devolvem o consolidado;
     gravações sempre exigem um projeto.
   * Gravações ficam na sessão do navegador (sessionStorage) para sobreviver
     à navegação entre telas; fechar a aba ou "Restaurar dados" volta ao mock.
   Cada ponto de troca está marcado com "TODO: API" e o endpoint sugerido.
   ========================================================================== */
(function (GI) {
  "use strict";

  var M = window.MOCK || {};
  var R = GI.regras;
  var LATENCIA_MS = 0;   /* simulação de rede; manter 0 no protótipo */

  /* ---------------- Utilitários ---------------- */
  function copia(v) { return v == null ? v : JSON.parse(JSON.stringify(v)); }
  function responder(valor) {
    return new Promise(function (ok) { setTimeout(function () { ok(copia(valor)); }, LATENCIA_MS); });
  }
  function rejeitar(erros) { return Promise.reject({ erros: [].concat(erros) }); }
  function soma(lista, campo) {
    return lista.reduce(function (s, x) { return s + (Number(typeof campo === "function" ? campo(x) : x[campo]) || 0); }, 0);
  }
  function porId(lista) { var m = {}; (lista || []).forEach(function (x) { m[x.id] = x; }); return m; }
  function arred(v, casas) { var f = Math.pow(10, casas || 0); return v == null || isNaN(v) ? null : Math.round(v * f) / f; }
  function divide(a, b) { return b ? a / b : null; }
  function mesDe(iso) { return String(iso).slice(0, 7); }
  /* Carimbo de auditoria: data de referência do protótipo com a hora atual. TODO: API data e hora do servidor */
  function agoraIso() { var d = new Date(); return (M.referencia || d.toISOString().slice(0, 10)) + "T" + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); }
  function doProjeto(lista, projetoId) {
    return (lista || []).filter(function (x) { return projetoId == null || x.projetoId === projetoId; });
  }
  /* Registros próprios do escopo: com projetoId null, só os do portfólio (projetoId null), não os de todos os projetos */
  function doEscopo(lista, projetoId) {
    return (lista || []).filter(function (x) { return projetoId == null ? x.projetoId == null : x.projetoId === projetoId; });
  }

  var REF = M.referencia || new Date().toISOString().slice(0, 10);
  var P = function () { return M.parametros; };

  /* ---------------- Persistência da sessão (só no protótipo) ----------------
     Cada coleção alterada é guardada inteira no sessionStorage e reaplicada ao
     abrir qualquer tela. TODO: API remover; o backend passa a ser a fonte. */
  var CHAVE_SESSAO = "gi.prototipo.alteracoes.v2";   /* v2: portfólio (30/09/2026); alterações da versão de projeto único são descartadas */
  var alteradas = {};
  (function restaurar() {
    try {
      var bruto = window.sessionStorage.getItem(CHAVE_SESSAO);
      if (!bruto) return;
      alteradas = JSON.parse(bruto) || {};
      Object.keys(alteradas).forEach(function (k) { M[k] = alteradas[k]; });
    } catch (e) { alteradas = {}; }
  })();
  function persistir(nome) {
    alteradas[nome] = M[nome];
    try { window.sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(alteradas)); } catch (e) { /* sem armazenamento: segue só em memória */ }
  }
  function restaurarDados() {
    try { window.sessionStorage.removeItem(CHAVE_SESSAO); } catch (e) { /* nada a limpar */ }
  }
  function haAlteracoes() { return Object.keys(alteradas).length > 0; }

  /* Coleções expostas pelo CRUD genérico (nome público: array no mock) */
  var COLECOES = [
    "clientes", "projetos", "empresas", "pessoas", "parametrosHistorico",
    "atas", "acoes",
    "sistemas", "punch", "avancoAreas", "curvaFisica", "lookahead", "programacoes", "eap", "eapRevisoes", "eapDesdobramentos", "relatos", "analisesPeriodo",
    "produtividadeItens", "jornadasCampo", "amostragens", "paralisacoes",
    "eac", "curvaFinanceira", "reservas", "eacRevisoes", "eacRemanejamentos", "contratos", "aditivos", "medicoes", "marcosPagamento", "claims", "extensoesPrazo", "avaliacoes",
    "pacotes", "pedidos", "processos", "fornecedores",
    "riscos", "riscosEvolucao", "riscoCategorias",
    "rncs", "itps", "inspecoesQualidade", "auditorias",
    "hht", "ocorrencias", "hseMensal", "analisesRisco",
    "mudancas", "licoes"
  ];
  function colecao(nome) {
    if (COLECOES.indexOf(nome) < 0) throw new Error("Coleção desconhecida: " + nome);
    if (!M[nome]) M[nome] = [];
    return M[nome];
  }
  function filtrar(lista, filtro) {
    if (!filtro) return lista.slice();
    if (typeof filtro === "function") return lista.filter(filtro);
    return lista.filter(function (x) {
      return Object.keys(filtro).every(function (k) { return filtro[k] == null || x[k] === filtro[k]; });
    });
  }

  /* ---------------- Sessão e referência ---------------- */
  function sessaoAtual() { return copia(M.sessao || { nome: "Usuário", iniciais: "U", papel: "", papelCodigo: "" }); }
  function referencia() { return REF; }
  /* Escopo da navegação: Portfólio (null) ou um projeto. Ordem: ?projeto= na URL ("portfolio" ou o id),
     depois a última escolha do navegador (localStorage gi.escopo), depois o padrão do mock (Portfólio).
     A URL grava a escolha para as próximas telas. TODO: API preferência do usuário no servidor. */
  var CHAVE_ESCOPO = "gi.escopo";
  function lerEscopo() {
    var v = null;
    try { v = new URLSearchParams(window.location.search).get("projeto"); } catch (e) { v = null; }
    if (v != null && v !== "") gravarEscopo(v);
    else { try { v = window.localStorage.getItem(CHAVE_ESCOPO); } catch (e) { v = null; } }
    if (v == null || v === "") return M.projetoAtualId == null ? null : M.projetoAtualId;
    if (v === "portfolio") return null;
    var id = Number(v);
    return (M.projetos || []).some(function (p) { return p.id === id; }) ? id : null;
  }
  function gravarEscopo(v) { try { window.localStorage.setItem(CHAVE_ESCOPO, v == null || v === "" ? "portfolio" : String(v)); } catch (e) { /* sem armazenamento: vale só a URL */ } }
  var ESCOPO = lerEscopo();
  function projetoAtualId() { return ESCOPO; }
  function emPortfolio() { return ESCOPO == null; }
  /* Troca o escopo (grava; a tela recarrega com ?projeto=) */
  function definirEscopo(projetoId) { ESCOPO = projetoId == null ? null : Number(projetoId); gravarEscopo(ESCOPO == null ? "portfolio" : ESCOPO); return ESCOPO; }
  /* Gravações pertencem a um projeto: recusa no escopo Portfólio */
  function semProjeto(projetoId) { return projetoId == null || projetoId === "" || !(M.projetos || []).some(function (p) { return p.id === Number(projetoId); }); }

  /* ---------------- CRUD genérico ---------------- */
  /* TODO: API GET /{colecao}?filtros */
  function listar(nome, filtro) { return responder(filtrar(colecao(nome), filtro)); }
  /* TODO: API GET /{colecao}/{id} */
  function obter(nome, id) {
    var item = colecao(nome).filter(function (x) { return String(x.id) === String(id); })[0];
    return responder(item || null);
  }
  /* TODO: API POST /{colecao} (novo) ou PUT /{colecao}/{id} (existente) */
  function salvar(nome, registro) {
    var lista = colecao(nome);
    var copiaReg = copia(registro);
    if (copiaReg.id == null) {
      copiaReg.id = lista.reduce(function (m, x) { return Math.max(m, Number(x.id) || 0); }, 0) + 1;
      lista.push(copiaReg);
    } else {
      var i = lista.findIndex(function (x) { return String(x.id) === String(copiaReg.id); });
      if (i < 0) lista.push(copiaReg); else lista[i] = copiaReg;
    }
    persistir(nome);
    return responder(copiaReg);
  }
  /* TODO: API DELETE /{colecao}/{id} (exclusão lógica no backend) */
  function excluir(nome, id) {
    var lista = colecao(nome);
    var i = lista.findIndex(function (x) { return String(x.id) === String(id); });
    if (i >= 0) { lista.splice(i, 1); persistir(nome); }
    return responder(i >= 0);
  }
  /* Próximo código sequencial no padrão do projeto (ex.: PL-TN-2026-0017).
     TODO: API numeração gerada no servidor (evita duplicidade entre usuários). */
  function proximoCodigo(nome, prefixo) {
    var maior = colecao(nome).reduce(function (m, x) {
      var c = String(x.codigo || x.numero || "");
      if (c.indexOf(prefixo) !== 0) return m;
      var resto = c.slice(prefixo.length);
      if (!/^\d+$/.test(resto)) return m;   /* RSK-TN-2026- não conta RSK-TN-2026-SE-0001 */
      var n = parseInt(resto, 10);
      return isNaN(n) ? m : Math.max(m, n);
    }, 0);
    return prefixo + ("000" + (maior + 1)).slice(-4);
  }

  /* Cadastros de apoio (nomes por Id). TODO: API GET /cadastros (cache na sessão) */
  function cadastros() {
    return responder({
      clientes: M.clientes, projetos: M.projetos,
      empresas: M.empresas, pessoas: M.pessoas, sistemas: M.sistemas
    });
  }

  /* ---------------- Parâmetros configuráveis ---------------- */
  /* TODO: API GET /parametros (versão vigente) */
  function parametros() { return responder(M.parametros); }
  /* TODO: API GET /parametros/historico */
  function historicoParametros() { return responder(M.parametrosHistorico || []); }
  /* TODO: API PUT /parametros (só Gestor e Admin; cria nova versão com vigência) */
  function salvarParametros(novos, justificativa) {
    var sessao = M.sessao || {};
    if (["Gestor", "Admin"].indexOf(sessao.papelCodigo) < 0) return rejeitar("Somente Gestor ou Admin altera parâmetros.");
    if (!justificativa || String(justificativa).trim().length < 10) return rejeitar("Informe a justificativa da alteração (mínimo de 10 caracteres).");
    var erros = R.validarParametros(novos);
    if (erros.length) return rejeitar(erros);
    var anterior = copia(M.parametros);
    anterior.vigenciaFim = REF;
    M.parametrosHistorico = (M.parametrosHistorico || []).concat([anterior]);
    var nova = copia(novos);
    nova.versao = anterior.versao + 1;
    nova.vigenciaInicio = REF;
    nova.alteradoPor = sessao.nome;
    nova.justificativa = justificativa;
    M.parametros = nova;
    persistir("parametrosHistorico");
    persistir("parametros");
    return responder(nova);
  }

  /* ======================================================================
     01 Central de Ações
     ====================================================================== */
  /* Ação derivada de item da Punch list (relação 1 para 1, status sincronizado) */
  function acaoDoPunch(item) {
    var sis = porId(M.sistemas)[item.sistemaId];
    return {
      id: "PL-" + item.id, projetoId: item.projetoId, origem: "Punch list", origemRef: item.codigo, origemId: item.id,
      grupo: sis ? sis.codigo + " " + sis.nome : "", tipo: "Ação", assunto: item.descricao,
      descricao: "Sistema " + (sis ? sis.codigo + " " + sis.nome : "") + (item.tag ? " · " + item.tag : "") + " · categoria " + item.categoria + " · " + item.situacao,
      solicitanteId: item.identificadoPorId, responsavelId: item.responsavelId,
      prevista: item.prazo, replanejada: null, conclusao: item.situacao === "Fechado" ? item.fechamento : null
    };
  }
  /* Revisão vigente de cada ata (a de maior número na mesma linhagem) */
  function revisoesVigentes() {
    var maior = {};
    (M.atas || []).forEach(function (a) { if (!maior[a.numero] || a.revisao > maior[a.numero].revisao) maior[a.numero] = a; });
    var ids = {};
    Object.keys(maior).forEach(function (k) { ids[maior[k].id] = true; });
    return ids;
  }
  function acoesComStatus(filtro) {
    var atas = porId(M.atas);
    var vigentes = revisoesVigentes();
    var punch = (M.punch || []).filter(function (p) { return p.situacao !== "Cancelado"; }).map(acaoDoPunch);
    var nativas = (M.acoes || []).filter(function (a) { return !a.ataId || vigentes[a.ataId]; });
    var todas = nativas.concat(punch).map(function (a) {
      var st = R.statusAcao(a, REF);
      var x = copia(a);
      x.status = st.chave; x.statusRotulo = st.rotulo; x.ehAcao = st.ehAcao;
      if (a.ataId && atas[a.ataId]) { x.origemRef = atas[a.ataId].numero; x.ataRevisao = atas[a.ataId].revisao; }
      x.diasAtraso = st.chave === "atrasada" ? R.diasEntre(a.replanejada || a.prevista, REF) : 0;
      return x;
    });
    return filtrar(todas, filtro);
  }
  /* TODO: API GET /acoes?projetoId&origem&status (status calculado no servidor) */
  function listarAcoes(filtro) { return responder(acoesComStatus(filtro)); }
  function resumoAcoes(projetoId) {
    var lista = acoesComStatus(function (a) { return a.ehAcao && (projetoId == null || a.projetoId === projetoId); });
    var n = function (st) { return lista.filter(function (a) { return a.status === st; }).length; };
    return { total: lista.length, atrasadas: n("atrasada"), emAndamento: n("andamento") + n("atrasada"), emDia: n("andamento"), concluidas: n("concluida") };
  }

  /* ======================================================================
     02 Planejamento
     ====================================================================== */
  function curvaFisicaProjeto(projetoId) {
    return (M.curvaFisica || []).filter(function (c) { return c.projetoId === projetoId; })[0] || null;
  }
  function indicesFisicos(projetoId) {
    var c = curvaFisicaDe(projetoId);
    if (!c) return null;
    var i = c.meses.indexOf(c.corte);
    var prev = c.baseline[i], real = c.real[i];
    var ant = i > 0 ? { previsto: c.baseline[i - 1], real: c.real[i - 1], spi: arred(divide(c.real[i - 1], c.baseline[i - 1]), 2) } : null;
    var fim = c.tendencia.reduce(function (m, v, k) { return v != null && v >= 100 && m == null ? c.meses[k] : m; }, null);
    var fimBase = c.baseline.reduce(function (m, v, k) { return v >= 100 && m == null ? c.meses[k] : m; }, null);
    return { corte: c.corte, previsto: prev, real: real, desvioPP: arred(real - prev, 1), spi: arred(divide(real, prev), 2), anterior: ant,
      terminoTendencia: fim, terminoBaseline: fimBase };
  }
  /* TODO: API GET /projetos/{id}/curva-fisica */
  function curvaFisica(projetoId) { return responder({ curva: curvaFisicaDe(projetoId), indices: indicesFisicos(projetoId) }); }

  /* ---------------- EAP: estrutura analítica do projeto (avanço físico) ----------------
     Árvore área > subárea > pacote. Pesos em % do projeto (pacotes somam 100); previsto e
     real das áreas e subáreas = média ponderada pelos pesos. Estrutura e pesos só mudam por
     revisão a partir de SM aprovada com impacto em escopo; pacote de planejamento pode ser
     desdobrado em pacotes de trabalho sem mudar o total (ondas sucessivas). */
  function parEap() { return P().eap || { faixasDesvioPP: [2, 5], pesoMaximoPacotePct: 10, estimadoMaximoPct: 5, modelosEtapas: [] }; }
  function ordemCodigoEap(a, b) {
    var pa = a.codigo.split(".").map(Number), pb = b.codigo.split(".").map(Number);
    for (var k = 0; k < Math.max(pa.length, pb.length); k++) {
      if (pa[k] == null) return -1; if (pb[k] == null) return 1;
      if (pa[k] !== pb[k]) return pa[k] - pb[k];
    }
    return 0;
  }
  function pacoteEap(projetoId, codigo) {
    return doProjeto(M.eap, projetoId).filter(function (x) { return x.codigo === codigo && x.nivel === 3; })[0] || null;
  }
  function eapArvoreDe(projetoId) {
    var faixas = parEap().faixasDesvioPP;
    var itens = doProjeto(M.eap, projetoId).map(copia).sort(ordemCodigoEap);
    var porCod = {};
    itens.forEach(function (x) { porCod[x.codigo] = x; });
    function filhos(codigo) {
      return itens.filter(function (x) { return x.codigo.indexOf(codigo + ".") === 0 && x.codigo.split(".").length === codigo.split(".").length + 1; });
    }
    function totalizar(no) {
      if (no.nivel === 3) {
        no.trabalho = no.tipo !== "Planejamento";
        no.real = R.avancoPacoteEap(no);
        no.pacotes = no.trabalho ? 1 : 0; no.planejamento = no.trabalho ? 0 : 1;
        no.vencido = no.trabalho && no.termino < REF && no.real < 100;
        no.naoIniciado = no.trabalho && no.inicio <= REF && no.real === 0;
        return no;
      }
      var f = filhos(no.codigo).map(totalizar);
      no.peso = arred(soma(f, "peso"), 2);
      no.previsto = no.peso ? arred(soma(f, function (x) { return x.peso * x.previsto; }) / no.peso, 2) : 0;
      no.real = no.peso ? arred(soma(f, function (x) { return x.peso * x.real; }) / no.peso, 2) : 0;
      no.inicio = f.reduce(function (m, x) { return x.inicio && (!m || x.inicio < m) ? x.inicio : m; }, null);
      no.termino = f.reduce(function (m, x) { return x.termino && (!m || x.termino > m) ? x.termino : m; }, null);
      no.pacotes = soma(f, "pacotes"); no.planejamento = soma(f, "planejamento");
      no.vencido = f.some(function (x) { return x.vencido; });
      return no;
    }
    itens.filter(function (x) { return x.nivel === 1; }).forEach(totalizar);
    itens.forEach(function (x) {
      var pai = porCod[x.codigo.split(".").slice(0, -1).join(".")];
      x.pesoNoPai = pai && pai.peso ? arred(x.peso / pai.peso * 100, 1) : null;
      x.desvioPP = arred(x.real - x.previsto, 1);
      x.faixa = R.faixaDesvioFisico(x.desvioPP, faixas);
      x.folha = x.nivel === 3;
    });
    var raiz = itens.filter(function (x) { return x.nivel === 1; });
    var total = { codigo: "", descricao: "Total do projeto", nivel: 0, peso: arred(soma(raiz, "peso"), 2) };
    total.previsto = total.peso ? arred(soma(raiz, function (x) { return x.peso * x.previsto; }) / total.peso, 2) : 0;
    total.real = total.peso ? arred(soma(raiz, function (x) { return x.peso * x.real; }) / total.peso, 2) : 0;
    total.desvioPP = arred(total.real - total.previsto, 1);
    total.faixa = R.faixaDesvioFisico(total.desvioPP, faixas);
    return { itens: itens, total: total };
  }
  function revisoesEapDe(projetoId) {
    return doProjeto(M.eapRevisoes, projetoId).slice().sort(function (a, b) { return a.revisao - b.revisao; });
  }
  function revisaoEapVigente(projetoId) { var r = revisoesEapDe(projetoId); return r.length ? r[r.length - 1] : null; }
  /* SMs aprovadas com impacto em escopo ainda não incorporadas à EAP */
  function smsPendentesEapDe(projetoId) {
    var usadas = revisoesEapDe(projetoId).map(function (r) { return r.smRef; });
    return doProjeto(M.mudancas, projetoId).filter(function (s) {
      return SM_APROVADA.indexOf(s.situacao) >= 0 && s.impacto && temImpacto(s.impacto.escopo) && usadas.indexOf(s.codigo) < 0;
    }).map(copia);
  }
  function temEap(projetoId) { return doProjeto(M.eap, projetoId).length > 0; }
  /* TODO: API GET /projetos/{id}/eap (árvore, revisões, desdobramentos, SMs pendentes e conciliação com a Curva S) */
  function eapDe(projetoId) { return responder(projetoId == null ? eapCarteira() : eapDadosDe(projetoId)); }
  function eapDadosDe(projetoId) {
    var arv = eapArvoreDe(projetoId), vig = revisaoEapVigente(projetoId);
    var folhas = arv.itens.filter(function (x) { return x.nivel === 3; });
    var trabalho = folhas.filter(function (x) { return x.trabalho; }), plan = folhas.filter(function (x) { return !x.trabalho; });
    var c = curvaFisicaDe(projetoId), i = c ? c.meses.indexOf(c.corte) : -1;
    var curva = c && i >= 0 ? { corte: c.corte, previsto: c.baseline[i], real: c.real[i] } : null;
    if (curva) curva.diferencaPP = arred(arv.total.real - curva.real, 1);
    return ({
      arvore: arv, revisoes: revisoesEapDe(projetoId), vigente: vig,
      desdobramentos: doProjeto(M.eapDesdobramentos, projetoId).filter(function (d) { return vig && d.revisao === vig.revisao; }),
      smsPendentes: smsPendentesEapDe(projetoId), curva: curva, referencia: REF,
      indicadores: {
        previsto: arv.total.previsto, real: arv.total.real, desvioPP: arv.total.desvioPP, spi: arred(divide(arv.total.real, arv.total.previsto), 2),
        pacotes: trabalho.length, planejamento: plan.length, pesoPlanejamento: arred(soma(plan, "peso"), 2),
        areas: arv.itens.filter(function (x) { return x.nivel === 1; }).length, subareas: arv.itens.filter(function (x) { return x.nivel === 2; }).length,
        vencidos: trabalho.filter(function (x) { return x.vencido; }).length, naoIniciados: trabalho.filter(function (x) { return x.naoIniciado; }).length,
        atrasados: trabalho.filter(function (x) { return x.faixa === "danger"; }).length
      },
      parametros: copia(parEap())
    });
  }
  function proximoCodigoEap(projetoId, pai) {
    var n = doProjeto(M.eap, projetoId).concat(doProjeto(M.eapDesdobramentos, projetoId).map(function (d) { return { codigo: d.origem }; }))
      .filter(function (x) { return x.codigo.indexOf(pai + ".") === 0 && x.codigo.split(".").length === pai.split(".").length + 1; })
      .reduce(function (m, x) { return Math.max(m, Number(x.codigo.split(".").pop())); }, 0);
    return pai + "." + (n + 1);
  }
  /* Entradas do critério: valida e devolve os campos a gravar (sem alterar o pacote) */
  function entradasCriterioEap(p, d) {
    var e = [], r = {};
    switch (p.criterio) {
      case "Etapas":
        var pcts = d.etapas || [];
        r.etapas = (p.etapas || []).map(function (et, k) {
          var v = pcts[k] == null ? et.pct : Number(pcts[k]);
          if (isNaN(v) || v < 0 || v > 100) e.push({ campo: "etapa" + k, msg: "Use um valor entre 0 e 100%." });
          return { nome: et.nome, peso: et.peso, pct: v };
        });
        break;
      case "Unidades":
        var ex = Number(d.executado);
        if (d.executado == null || isNaN(ex) || ex < 0) e.push({ campo: "executado", msg: "Informe a quantidade executada acumulada." });
        else if (ex > p.quantidade) e.push({ campo: "executado", msg: "O executado passa a quantidade da linha de base (" + p.quantidade + " " + p.unidade + "). Registre uma SM (08) para revisar a EAP." });
        r.executado = ex;
        break;
      case "Marco 0/100": case "Marco 50/50":
        var ok = p.criterio === "Marco 0/100" ? ["Não iniciado", "Concluído"] : ["Não iniciado", "Iniciado", "Concluído"];
        if (ok.indexOf(d.estado) < 0) e.push({ campo: "estado", msg: "Escolha a situação do marco." });
        r.estado = d.estado;
        break;
      case "Percentual estimado":
        var v = Number(d.estimadoPct);
        if (d.estimadoPct == null || isNaN(v) || v < 0 || v > 100) e.push({ campo: "estimadoPct", msg: "Informe um avanço entre 0 e 100%." });
        r.estimadoPct = v;
        break;
      default: e.push("Pacote sem critério de medição.");
    }
    return { erros: e, campos: r };
  }
  /* Medição do avanço de um pacote de trabalho. O acumulado não regride, salvo estorno
     justificado por Gestor. TODO: API POST /projetos/{id}/eap/{codigo}/medicoes */
  function eapRegistrarAvanco(projetoId, codigo, d) {
    var p = pacoteEap(projetoId, codigo);
    if (!p) return rejeitar("Pacote " + codigo + " não encontrado.");
    if (p.tipo === "Planejamento") return rejeitar("Pacote de planejamento não recebe medição: desdobre-o em pacotes de trabalho antes.");
    var r = entradasCriterioEap(p, d), e = r.erros;
    if (!d.data) e.push({ campo: "data", msg: "Informe a data da medição." });
    else if (d.data > REF) e.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    var antes = R.avancoPacoteEap(p);
    var depois = R.avancoPacoteEap(Object.assign({}, p, r.campos));
    if (!e.length && depois < antes) {
      if (!temPapel("Gestor")) e.push("Estorno de avanço exige papel Gestor.");
      else if (!d.justificativa || String(d.justificativa).trim().length < 10) e.push({ campo: "justificativa", msg: "Estorno de avanço (de " + antes + "% para " + depois + "%) exige justificativa." });
    }
    if (e.length) return rejeitar(e);
    Object.keys(r.campos).forEach(function (k) { p[k] = r.campos[k]; });
    p.medicoes = (p.medicoes || []).concat([{ data: d.data, de: antes, para: depois, porId: sessaoPessoa(), obs: (d.obs || d.justificativa || "").trim(), estorno: depois < antes }]);
    persistir("eap");
    return responder({ codigo: codigo, de: antes, para: depois });
  }
  /* Importação do avanço (boletim de medição física ou cronograma): % acumulado por pacote.
     TODO: API POST /projetos/{id}/eap/medicoes/lote */
  function eapImportarAvanco(projetoId, linhas, dataMedicao) {
    var ok = 0, erros = [];
    linhas.forEach(function (l, k) {
      var p = pacoteEap(projetoId, l.codigo);
      var ref = l.codigo + ": ";
      if (!p) { erros.push(ref + "pacote não encontrado."); return; }
      if (p.tipo === "Planejamento") { erros.push(ref + "pacote de planejamento não recebe medição."); return; }
      var conv = p.criterio === "Unidades" && l.executado != null ? { ok: true, entradas: { executado: l.executado } } : R.entradasPorPercentual(p, l.pct);
      if (!conv.ok) { erros.push(ref + conv.msg); return; }
      var r = entradasCriterioEap(p, conv.entradas.etapas ? { etapas: conv.entradas.etapas.map(function (x) { return x.pct; }) } : conv.entradas);
      if (r.erros.length) { erros.push(ref + r.erros.map(function (x) { return x.msg || x; }).join(" ")); return; }
      var antes = R.avancoPacoteEap(p), depois = R.avancoPacoteEap(Object.assign({}, p, r.campos));
      if (depois < antes) { erros.push(ref + "o avanço não pode regredir (de " + antes + "% para " + depois + "%); estorno só pela tela, com justificativa."); return; }
      if (depois === antes) return;
      Object.keys(r.campos).forEach(function (c) { p[c] = r.campos[c]; });
      p.medicoes = (p.medicoes || []).concat([{ data: dataMedicao || REF, de: antes, para: depois, porId: sessaoPessoa(), obs: "Importação do avanço." }]);
      ok++;
    });
    if (ok) persistir("eap");
    return responder({ aplicados: ok, erros: erros });
  }
  /* Dicionário da EAP: campos descritivos do pacote (não mexem na linha de base).
     TODO: API PUT /projetos/{id}/eap/{codigo} */
  function eapEditarPacote(projetoId, codigo, d) {
    var p = pacoteEap(projetoId, codigo);
    if (!p) return rejeitar("Pacote " + codigo + " não encontrado.");
    var e = [];
    if (!d.descricao || String(d.descricao).trim().length < 3) e.push({ campo: "descricao", msg: "Descreva o pacote (mínimo de 3 caracteres)." });
    if (!d.responsavelId) e.push({ campo: "responsavel", msg: "Escolha o responsável." });
    if (e.length) return rejeitar(e);
    ["descricao", "entregavel", "aceitacao"].forEach(function (k) { p[k] = String(d[k] || "").trim(); });
    p.responsavelId = Number(d.responsavelId); p.empresaId = d.empresaId ? Number(d.empresaId) : null; p.eacCodigo = d.eacCodigo || null;
    persistir("eap");
    return responder(copia(p));
  }
  /* Validação comum de um pacote novo (dados da linha de base) */
  function validarPacoteNovoEap(projetoId, n) {
    var par = parEap(), e = [];
    var pai = doProjeto(M.eap, projetoId).filter(function (x) { return x.codigo === n.pai && x.nivel === 2; })[0];
    if (!pai) e.push({ campo: "pai", msg: "Escolha a subárea do pacote." });
    if (!n.descricao || String(n.descricao).trim().length < 3) e.push({ campo: "descricao", msg: "Descreva o pacote (mínimo de 3 caracteres)." });
    if (!(n.peso > 0)) e.push({ campo: "peso", msg: "Informe um peso maior que zero." });
    else if (n.peso > par.pesoMaximoPacotePct) e.push({ campo: "peso", msg: "O peso passa o máximo de " + par.pesoMaximoPacotePct + "% por pacote: decomponha em pacotes menores." });
    if (n.tipo !== "Planejamento") {
      if (R.CRITERIOS_EAP.indexOf(n.criterio) < 0) e.push({ campo: "criterio", msg: "Escolha o critério de medição." });
      if (n.criterio === "Etapas" && !(n.etapas && n.etapas.length)) e.push({ campo: "modelo", msg: "Escolha o modelo de etapas." });
      if (n.criterio === "Unidades") {
        if (!n.unidade) e.push({ campo: "unidade", msg: "Escolha a unidade." });
        if (!(n.quantidade > 0)) e.push({ campo: "quantidade", msg: "Informe a quantidade da linha de base." });
      }
      if (n.criterio === "Percentual estimado" && n.peso > par.estimadoMaximoPct) e.push({ campo: "criterio", msg: "Percentual estimado só vale para pacotes de até " + par.estimadoMaximoPct + "% de peso; use etapas ou unidades." });
    }
    if (!n.inicio) e.push({ campo: "inicio", msg: "Informe o início da linha de base." });
    if (!n.termino) e.push({ campo: "termino", msg: "Informe o término da linha de base." });
    else if (n.inicio && n.termino < n.inicio) e.push({ campo: "termino", msg: "O término não pode ser anterior ao início." });
    if (!n.responsavelId) e.push({ campo: "responsavel", msg: "Escolha o responsável." });
    return e;
  }
  function montarPacoteEap(projetoId, n, id) {
    var t = n.tipo === "Planejamento";
    return { id: id, projetoId: projetoId, codigo: n.codigo, descricao: String(n.descricao).trim(), nivel: 3, tipo: t ? "Planejamento" : "Trabalho",
      criterio: t ? null : n.criterio, modelo: !t && n.criterio === "Etapas" ? n.modelo || null : null,
      etapas: !t && n.criterio === "Etapas" ? n.etapas.map(function (x) { return { nome: x.nome, peso: x.peso, pct: 0 }; }) : null,
      unidade: !t && n.criterio === "Unidades" ? n.unidade : null, quantidade: !t && n.criterio === "Unidades" ? n.quantidade : null, executado: !t && n.criterio === "Unidades" ? 0 : null,
      estado: !t && /^Marco/.test(n.criterio) ? "Não iniciado" : null, estimadoPct: !t && n.criterio === "Percentual estimado" ? 0 : null,
      peso: n.peso, previsto: n.previsto == null ? previstoLinearEap(n.inicio, n.termino) : n.previsto, inicio: n.inicio, termino: n.termino,
      empresaId: n.empresaId ? Number(n.empresaId) : null, responsavelId: Number(n.responsavelId), eacCodigo: n.eacCodigo || null,
      entregavel: String(n.entregavel || "").trim(), aceitacao: String(n.aceitacao || "").trim(), medicoes: [] };
  }
  /* Previsto na data de referência pela distribuição linear entre as datas da linha de base
     (pacote novo, até a próxima emissão do cronograma). TODO: API previsto vem do cronograma (P6/MSP) */
  function previstoLinearEap(inicio, termino) {
    if (!inicio || !termino || REF <= inicio) return 0;
    if (REF >= termino) return 100;
    var tot = R.diasEntre(inicio, termino);
    return tot > 0 ? arred(R.diasEntre(inicio, REF) / tot * 100, 1) : 0;
  }
  /* Pacote novo por desdobramento de pacote de planejamento (o total não muda) ou por nova revisão
     (SM aprovada com impacto em escopo). TODO: API POST /projetos/{id}/eap/pacotes */
  function eapNovoPacote(projetoId, n, recurso) {
    n = copia(n);
    n.codigo = proximoCodigoEap(projetoId, n.pai);
    if (recurso.tipo === "revisao") {
      var e0 = validarPacoteNovoEap(projetoId, n);
      if (e0.length) return rejeitar(e0);
      return eapNovaRevisao(projetoId, { smRef: recurso.smRef, justificativa: recurso.justificativa, novos: [n] })
        .then(function (r) { r.codigo = n.codigo; return r; });
    }
    var e = validarPacoteNovoEap(projetoId, Object.assign({}, n, { tipo: "Trabalho" }));
    var o = pacoteEap(projetoId, recurso.origem), vig = revisaoEapVigente(projetoId);
    if (!o || o.tipo !== "Planejamento") e.push({ campo: "origem", msg: "Escolha o pacote de planejamento de origem." });
    else if (n.peso > o.peso + 1e-9) e.push({ campo: "peso", msg: "O pacote de planejamento " + o.codigo + " só tem " + o.peso + "% de peso a desdobrar." });
    if (!recurso.justificativa || String(recurso.justificativa).trim().length < 10) e.push({ campo: "justificativa", msg: "Justifique o desdobramento (mínimo de 10 caracteres)." });
    if (e.length) return rejeitar(e);
    n.tipo = "Trabalho"; n.previsto = o.previsto; /* mantém o previsto consolidado do projeto */
    var eap = colecao("eap");
    eap.push(montarPacoteEap(projetoId, n, proximoId("eap")));
    o.peso = arred(o.peso - n.peso, 2);
    var encerrado = o.peso <= 0;
    if (encerrado) M.eap = eap.filter(function (x) { return x !== o; });
    colecao("eapDesdobramentos").push({ id: proximoId("eapDesdobramentos"), projetoId: projetoId, revisao: vig ? vig.revisao : 0, data: REF,
      origem: o.codigo, origemDescricao: o.descricao, origemEncerrada: encerrado, destino: n.codigo, peso: n.peso, porId: sessaoPessoa(),
      justificativa: String(recurso.justificativa).trim() });
    persistir("eap"); persistir("eapDesdobramentos");
    return responder({ codigo: n.codigo, origemEncerrada: encerrado });
  }
  /* Nova revisão da EAP a partir de SM aprovada com impacto em escopo: ajusta pesos, quantidades
     e términos dos pacotes afetados, inclui pacotes novos e reescala os demais pesos para fechar
     100%. Exige papel Gestor. TODO: API POST /projetos/{id}/eap/revisoes */
  function eapNovaRevisao(projetoId, d) {
    if (!temPapel("Gestor")) return rejeitar("Nova revisão da EAP exige papel Gestor.");
    var par = parEap(), e = [], vig = revisaoEapVigente(projetoId);
    var sm = smsPendentesEapDe(projetoId).filter(function (s) { return s.codigo === d.smRef; })[0];
    if (!sm) e.push({ campo: "sm", msg: "Escolha uma SM aprovada com impacto em escopo ainda não incorporada à EAP." });
    if (!d.justificativa || String(d.justificativa).trim().length < 10) e.push({ campo: "justificativa", msg: "Justifique a revisão (mínimo de 10 caracteres)." });
    var ajustes = d.ajustes || [], novos = d.novos || [];
    if (!ajustes.length && !novos.length) e.push("A revisão precisa alterar ao menos um pacote.");
    var fixos = {};
    ajustes.forEach(function (a) {
      var p = pacoteEap(projetoId, a.codigo);
      if (!p) { e.push({ campo: "pacote", msg: "Pacote " + a.codigo + " não encontrado." }); return; }
      var peso = a.peso == null ? p.peso : Number(a.peso);
      if (!(peso > 0)) e.push({ campo: "peso", msg: "Informe um peso maior que zero." });
      else if (peso > par.pesoMaximoPacotePct) e.push({ campo: "peso", msg: "O peso passa o máximo de " + par.pesoMaximoPacotePct + "% por pacote." });
      if (a.quantidade != null && p.criterio === "Unidades" && a.quantidade < (p.executado || 0)) e.push({ campo: "quantidade", msg: "A nova quantidade não pode ser menor que o executado (" + p.executado + " " + p.unidade + ")." });
      if (a.termino && a.termino < p.inicio) e.push({ campo: "termino", msg: "O término não pode ser anterior ao início (" + dataBr(p.inicio) + ")." });
      fixos[a.codigo] = peso;
    });
    novos.forEach(function (n) { fixos[n.codigo] = n.peso; });
    var somaFixos = Object.keys(fixos).reduce(function (s, k) { return s + (Number(fixos[k]) || 0); }, 0);
    if (somaFixos >= 100) e.push({ campo: "peso", msg: "Os pesos alterados somam 100% ou mais; os demais pacotes ficariam sem peso." });
    if (e.length) return rejeitar(e);
    var eap = colecao("eap");
    ajustes.forEach(function (a) {
      var p = pacoteEap(projetoId, a.codigo);
      if (a.quantidade != null && p.criterio === "Unidades") p.quantidade = a.quantidade;
      if (a.termino) p.termino = a.termino;
    });
    novos.forEach(function (n) { eap.push(montarPacoteEap(projetoId, n, proximoId("eap"))); });
    var livres = doProjeto(eap, projetoId).filter(function (x) { return x.nivel === 3 && fixos[x.codigo] == null; });
    var novosPesos = R.reescalarPesos(livres.map(function (x) { return { chave: x.codigo, peso: x.peso }; }), 100 - somaFixos);
    doProjeto(eap, projetoId).forEach(function (x) {
      if (x.nivel !== 3) return;
      x.peso = fixos[x.codigo] != null ? Number(fixos[x.codigo]) : novosPesos[x.codigo];
    });
    var partes = [];
    if (novos.length) partes.push((novos.length === 1 ? "Pacote " : "Pacotes ") + novos.map(function (n) { return n.codigo; }).join(", ") + (novos.length === 1 ? " incluído" : " incluídos"));
    if (ajustes.length) partes.push((ajustes.length === 1 ? "Pacote " : "Pacotes ") + ajustes.map(function (a) { return a.codigo; }).join(", ") + (ajustes.length === 1 ? " ajustado" : " ajustados"));
    var rev = { id: proximoId("eapRevisoes"), projetoId: projetoId, revisao: vig ? vig.revisao + 1 : 0, data: REF,
      pacotes: doProjeto(eap, projetoId).filter(function (x) { return x.nivel === 3; }).length, smRef: d.smRef, aprovadoPorId: sessaoPessoa(),
      alteracao: partes.join("; ") + "; demais pesos reescalados", justificativa: String(d.justificativa).trim() };
    colecao("eapRevisoes").push(rev);
    persistir("eap"); persistir("eapRevisoes");
    return responder(copia(rev));
  }

  function punchComCalculos(projetoId) {
    var sistemas = porId(M.sistemas);
    var faixas = P().punch.agingFaixas;
    return doProjeto(M.punch, projetoId).map(function (p) {
      var x = copia(p);
      var aberto = ["Fechado", "Cancelado"].indexOf(p.situacao) < 0;
      x.aberto = aberto;
      x.sistema = sistemas[p.sistemaId] || null;
      x.idadeDias = R.diasEntre(p.abertura, aberto ? REF : p.fechamento || REF);
      x.faixaAging = x.idadeDias <= faixas[0] ? "ate-" + faixas[0] : x.idadeDias <= faixas[1] ? "ate-" + faixas[1] : "acima-" + faixas[1];
      x.vencido = aberto && p.prazo < REF;
      return x;
    });
  }
  /* TODO: API GET /projetos/{id}/punch */
  function listarPunch(projetoId) { return responder(punchComCalculos(projetoId)); }
  function resumoPunch(projetoId) {
    var lista = punchComCalculos(projetoId);
    var abertos = lista.filter(function (p) { return p.aberto; });
    var abertosA = abertos.filter(function (p) { return p.categoria === "A"; });
    var bloqueados = {};
    abertosA.forEach(function (p) { if (p.sistema) bloqueados[p.sistema.codigo] = p.sistema; });
    return { total: lista.length, abertos: abertos.length, abertosA: abertosA.length, vencidos: abertos.filter(function (p) { return p.vencido; }).length,
      sistemasBloqueados: Object.keys(bloqueados).map(function (k) { return bloqueados[k]; }) };
  }

  /* 6WLA: restrições abertas, vencidas e atividades prontas para programar */
  function lookaheadDe(projetoId) {
    return doProjeto(M.lookahead, projetoId).map(function (a) {
      var x = copia(a);
      x.restricoes.forEach(function (r) {
        r.aberta = !r.remocao;
        r.vencida = r.aberta && r.necessaria < REF;
      });
      x.abertas = x.restricoes.filter(function (r) { return r.aberta; }).length;
      x.vencidas = x.restricoes.filter(function (r) { return r.vencida; }).length;
      x.pronta = x.abertas === 0;
      x.proximaSemana = x.semanas.indexOf(1);
      return x;
    });
  }
  /* TODO: API GET /projetos/{id}/lookahead */
  function listarLookahead(projetoId) { return responder({ inicio: M.lookaheadInicio, atividades: lookaheadDe(projetoId) }); }

  /* Programação semanal: total realizado, aderência (limitada a 100%) e PPC */
  var DIAS = ["seg", "ter", "qua", "qui", "sex", "sab"];
  function calcularProgramacao(p) {
    var x = copia(p);
    x.atividades.forEach(function (a) {
      a.previsto = soma(DIAS.map(function (d) { return a.dias[d]; }), "prev");
      a.realizado = soma(DIAS.map(function (d) { return a.dias[d]; }), function (d) { return (d.dia || 0) + (d.noite || 0); });
      a.aderencia = a.previsto ? Math.min(100, a.realizado / a.previsto * 100) : null;
      a.cumprida = a.previsto > 0 && a.realizado >= a.previsto;
    });
    var comPrevisto = x.atividades.filter(function (a) { return a.previsto > 0; });
    x.apurada = x.atividades.some(function (a) { return a.realizado > 0; });
    if (!x.apurada) {
      x.atividades.forEach(function (a) { a.aderencia = null; });
      x.ppc = null; x.aderencia = null; x.porArea = []; x.porEmpresa = []; return x;
    }
    x.ppc = comPrevisto.length ? arred(comPrevisto.filter(function (a) { return a.cumprida; }).length / comPrevisto.length * 100, 1) : null;
    x.aderencia = comPrevisto.length ? arred(soma(comPrevisto, "aderencia") / comPrevisto.length, 1) : null;
    function agrupar(chave) {
      var g = {};
      comPrevisto.forEach(function (a) {
        var k = a[chave];
        g[k] = g[k] || { chave: k, atividades: 0, cumpridas: 0, somaAderencia: 0 };
        g[k].atividades++; if (a.cumprida) g[k].cumpridas++; g[k].somaAderencia += a.aderencia;
      });
      return Object.keys(g).map(function (k) {
        var y = g[k];
        return { chave: y.chave, atividades: y.atividades, cumpridas: y.cumpridas, ppc: arred(y.cumpridas / y.atividades * 100, 1), aderencia: arred(y.somaAderencia / y.atividades, 1) };
      });
    }
    x.porArea = agrupar("local");
    x.porEmpresa = agrupar("empresaId");
    return x;
  }
  /* TODO: API GET /projetos/{id}/programacoes */
  function listarProgramacoes(projetoId) {
    return responder(doProjeto(M.programacoes, projetoId).map(calcularProgramacao).sort(function (a, b) { return a.semana < b.semana ? -1 : 1; }));
  }

  /* ======================================================================
     03 Gestão Financeira
     ====================================================================== */
  var CAMPOS_EAC = ["base", "remanejamento", "comprometido", "realizado", "projecao"];

  function mapaControleProjeto(projetoId) {
    var limites = P().financeiro.faixasDesvio;
    var itens = doProjeto(M.eac, projetoId).map(copia);
    function filhos(codigo) {
      return itens.filter(function (x) { return x.codigo.indexOf(codigo + ".") === 0 && x.codigo.split(".").length === codigo.split(".").length + 1; });
    }
    function totalizar(no) {
      if (no.nivel === 3 || no.base != null) return no;
      var f = filhos(no.codigo).map(totalizar);
      CAMPOS_EAC.forEach(function (c) { no[c] = soma(f, c); });
      return no;
    }
    itens.filter(function (x) { return x.nivel === 1; }).forEach(totalizar);
    itens.forEach(function (x) {
      x.atual = x.base + x.remanejamento;
      x.saldoAComprometer = x.atual - x.comprometido;
      x.desvio = x.projecao - x.atual;
      x.desvioPct = x.atual ? arred(x.desvio / x.atual * 100, 1) : null;
      x.faixa = x.desvioPct == null ? "neutro" : R.faixaDesvio(x.desvioPct, limites);
      x.folha = x.nivel === 3;
    });
    itens.sort(function (a, b) {
      var pa = a.codigo.split(".").map(Number), pb = b.codigo.split(".").map(Number);
      for (var k = 0; k < Math.max(pa.length, pb.length); k++) {
        if (pa[k] == null) return -1; if (pb[k] == null) return 1;
        if (pa[k] !== pb[k]) return pa[k] - pb[k];
      }
      return 0;
    });
    var raiz = itens.filter(function (x) { return x.nivel === 1; });
    var total = { codigo: "", descricao: "Total do projeto", nivel: 0 };
    CAMPOS_EAC.concat(["atual", "saldoAComprometer", "desvio"]).forEach(function (c) { total[c] = soma(raiz, c); });
    total.desvioPct = total.atual ? arred(total.desvio / total.atual * 100, 1) : null;
    total.faixa = total.desvioPct == null ? "neutro" : R.faixaDesvio(total.desvioPct, limites);
    return { itens: itens, total: total };
  }
  /* TODO: API GET /projetos/{id}/eac/mapa-controle */
  function mapaControle(projetoId) { return responder(mapaControleDe(projetoId)); }

  function curvaFinanceiraProjeto(projetoId) {
    return (M.curvaFinanceira || []).filter(function (c) { return c.projetoId === projetoId; })[0] || null;
  }
  /* TODO: API GET /projetos/{id}/curva-financeira */
  function curvaFinanceira(projetoId) { return responder(curvaFinanceiraDe(projetoId)); }

  /* Valor agregado na data de corte e no mês anterior (EV = % físico real x BAC) */
  function valorAgregadoNoMes(fis, fin, bac, mes) {
    var i = fis.meses.indexOf(mes), j = fin.meses.indexOf(mes);
    if (i < 0 || j < 0 || fis.real[i] == null || fin.realizado[j] == null) return null;
    var ev = Math.round(bac * fis.real[i] / 100), pv = Math.round(bac * fis.baseline[i] / 100), ac = fin.realizado[j];
    var cpi = divide(ev, ac), spi = divide(ev, pv);
    return { mes: mes, ev: ev, pv: pv, ac: ac, cv: ev - ac, sv: ev - pv, cpi: arred(cpi, 2), spi: arred(spi, 2) };
  }
  function indicesCustoProjeto(projetoId) {
    var fis = curvaFisicaDe(projetoId), fin = curvaFinanceiraDe(projetoId);
    if (!fis || !fin) return null;
    var mapa = mapaControleDe(projetoId);
    var bac = mapa.total.atual, eacBU = mapa.total.projecao;
    function noMes(mes) { return valorAgregadoNoMes(fis, fin, bac, mes); }
    var atual = noMes(fin.corte);
    var k = fis.meses.indexOf(fin.corte);
    var anterior = k > 0 ? noMes(fis.meses[k - 1]) : null;
    var reserva = (M.reservas || []).filter(function (r) { return r.projetoId === projetoId; })[0] || { contingenciaCentavos: 0 };
    var consumo = soma((M.mudancas || []).filter(function (s) {
      return s.projetoId === projetoId && s.fonteRecurso === "Reserva de contingência" &&
        ["Aprovada", "Aprovada com condições", "Em implementação", "Encerrada"].indexOf(s.situacao) >= 0;
    }), function (s) { return s.impacto ? s.impacto.custoCentavos : 0; });
    return {
      corte: fin.corte, bac: bac, projecaoTermino: eacBU, vac: bac - eacBU,
      eacPorCpi: atual && atual.cpi ? Math.round(bac / divide(atual.ev, atual.ac)) : null,
      tcpi: atual ? arred(divide(bac - atual.ev, bac - atual.ac), 2) : null,
      atual: atual, anterior: anterior,
      comprometido: mapa.total.comprometido, comprometidoPct: arred(mapa.total.comprometido / bac * 100, 1),
      contingencia: reserva.contingenciaCentavos, contingenciaConsumida: consumo,
      contingenciaPct: reserva.contingenciaCentavos ? arred(consumo / reserva.contingenciaCentavos * 100, 1) : null
    };
  }
  /* ---------------- 03 Reservas: contingência e gerencial ----------------
     PMBOK/ISO 21502: a reserva de contingência cobre riscos identificados (05) e integra a linha de
     base de custo; a reserva gerencial cobre o imprevisto e fica fora dela (libera só o Comitê, com o
     patrocinador). Constituição na linha de base; consumo só por SM aprovada (08) com a fonte da
     reserva. Controles: consumo x avanço físico, cobertura da exposição (VME das ameaças ativas) e
     valor comprometido em SMs ainda em análise. TODO: API GET /projetos/{id}/reservas */
  var FONTE_CONTINGENCIA = "Reserva de contingência", FONTE_GERENCIAL = "Reserva gerencial";
  function parContingencia() { var f = P().financeiro || {}; return f.contingencia || { toleranciaConsumoPP: 10, coberturaMinimaPct: 100 }; }
  function reservaDoProjeto(projetoId) { return (M.reservas || []).filter(function (r) { return r.projetoId === projetoId; })[0] || null; }
  function fimMesIso(mes) { return mes + "-31"; }
  function movimentosReserva(projetoId, fonte, total, rotulo, res) {
    var l = [{ data: res.constituidaEm || null, tipo: "Constituição", reserva: rotulo, valorCentavos: total, smRef: null, situacao: "Efetivado",
      descricao: res.base || "Constituída na linha de base do projeto", projetoId: projetoId }];
    doProjeto(M.mudancas, projetoId).forEach(function (s) {
      if (s.fonteRecurso !== fonte || !s.impacto || !(s.impacto.custoCentavos > 0)) return;
      var aprov = SM_APROVADA.indexOf(s.situacao) >= 0, aberta = SM_TERMINAL.indexOf(s.situacao) < 0 && !aprov;
      if (!aprov && !aberta) return;
      l.push({ data: aprov && s.decisao ? s.decisao.data : s.dataSolicitacao, tipo: aprov ? "Consumo" : "Em análise", reserva: rotulo, valorCentavos: -s.impacto.custoCentavos,
        smRef: s.codigo, situacao: aprov ? "Efetivado" : s.situacao, descricao: s.titulo, riscos: s.impacto.riscos || "", projetoId: projetoId });
    });
    /* Liberação de saldo (SM "Liberação de reserva", decisão do Comitê): reduz o saldo e o orçamento do projeto */
    doProjeto(M.mudancas, projetoId).forEach(function (s) {
      if (!s.liberacao || s.liberacao.reserva !== rotulo) return;
      var aprov = SM_APROVADA.indexOf(s.situacao) >= 0, aberta = SM_TERMINAL.indexOf(s.situacao) < 0 && !aprov;
      if (!aprov && !aberta) return;
      l.push({ data: aprov && s.decisao ? s.decisao.data : s.dataSolicitacao, tipo: aprov ? "Liberação" : "Em análise", reserva: rotulo, valorCentavos: -s.liberacao.valorCentavos,
        smRef: s.codigo, situacao: aprov ? "Efetivado" : s.situacao, descricao: s.titulo, riscos: "", projetoId: projetoId });
    });
    l.sort(function (a, b) { return (a.data || "") < (b.data || "") ? -1 : (a.data || "") > (b.data || "") ? 1 : 0; });
    var saldo = 0;
    l.forEach(function (m) { if (m.situacao === "Efetivado") saldo += m.valorCentavos; m.saldoCentavos = m.situacao === "Efetivado" ? saldo : null; });
    return l;
  }
  function contingenciaProjeto(projetoId) {
    var res = reservaDoProjeto(projetoId);
    if (!res) return null;
    var par = parContingencia();
    var total = res.contingenciaCentavos || 0, totalG = res.gerencialCentavos || 0;
    var movC = movimentosReserva(projetoId, FONTE_CONTINGENCIA, total, "Contingência", res);
    var movG = movimentosReserva(projetoId, FONTE_GERENCIAL, totalG, "Gerencial", res);
    function somaTipo(l, tipo) { return -soma(l.filter(function (m) { return m.tipo === tipo; }), "valorCentavos"); }
    var consumo = somaTipo(movC, "Consumo"), emAnalise = somaTipo(movC, "Em análise"), liberado = somaTipo(movC, "Liberação");
    var consumoG = somaTipo(movG, "Consumo"), emAnaliseG = somaTipo(movG, "Em análise"), liberadoG = somaTipo(movG, "Liberação");
    var fis = indicesFisicos(projetoId) || {};
    var consumoPct = total ? arred(consumo / total * 100, 1) : null;
    var ameacas = riscosDe(projetoId).filter(function (r) { return r.ativo && r.natureza === "Ameaça"; });
    var exposicao = soma(ameacas, "vmeCentavos");
    var saldo = total - consumo - liberado;
    var cobertura = exposicao ? arred(saldo / exposicao * 100, 1) : null;
    var limiteConsumo = fis.real != null ? arred(Math.min(100, fis.real + par.toleranciaConsumoPP), 1) : null;
    var mapa = mapaControleDe(projetoId);
    var c = curvaFisicaDe(projetoId);
    var burn = c ? c.meses.map(function (m, k) {
      var fim = fimMesIso(m);
      var ate = movC.filter(function (x) { return x.data && x.data <= fim; });
      var real = m <= c.corte ? total - somaTipo(ate, "Consumo") - somaTipo(ate, "Liberação") : null;
      return { mes: m, esperado: Math.round(total * (1 - (c.baseline[k] || 0) / 100)), real: real };
    }) : [];
    var smsAnalise = movC.filter(function (m) { return m.tipo === "Em análise"; });
    var alertas = [];
    if (consumoPct != null && limiteConsumo != null && consumoPct > limiteConsumo) alertas.push({ tipo: "consumo", texto: "Consumo da contingência (" + String(consumoPct).replace(".", ",") + "%) acima do avanço físico real mais a tolerância (" + String(limiteConsumo).replace(".", ",") + "%)." });
    if (cobertura != null && cobertura < par.coberturaMinimaPct) alertas.push({ tipo: "cobertura", texto: "Saldo cobre " + String(cobertura).replace(".", ",") + "% da exposição das ameaças ativas (meta " + par.coberturaMinimaPct + "%)." });
    if (emAnalise > saldo) alertas.push({ tipo: "analise", texto: "SMs em análise pedem " + moedaBr(emAnalise) + " da contingência, acima do saldo (" + moedaBr(saldo) + ")." });
    return {
      projetoId: projetoId, constituidaEm: res.constituidaEm || null, base: res.base || "",
      contingencia: { total: total, consumido: consumo, liberado: liberado, emAnalise: emAnalise, saldo: saldo, saldoAposAnalise: saldo - emAnalise, consumoPct: consumoPct },
      gerencial: { total: totalG, consumido: consumoG, liberado: liberadoG, emAnalise: emAnaliseG, saldo: totalG - consumoG - liberadoG },
      avancoReal: fis.real != null ? fis.real : null, avancoPrevisto: fis.previsto != null ? fis.previsto : null, limiteConsumoPct: limiteConsumo,
      exposicaoCentavos: exposicao, coberturaPct: cobertura, coberturaMinimaPct: par.coberturaMinimaPct, toleranciaConsumoPP: par.toleranciaConsumoPP,
      pmbCentavos: mapa.total.atual, linhaBaseCustoCentavos: mapa.total.atual + saldo, orcamentoProjetoCentavos: mapa.total.atual + saldo + (totalG - consumoG - liberadoG),
      movimentos: movC.concat(movG), burn: burn, smsEmAnalise: smsAnalise.length,
      riscos: ameacas.sort(function (a, b) { return (b.vmeCentavos || 0) - (a.vmeCentavos || 0); }).map(function (r) {
        var sms = movC.concat(movG).filter(function (m) { return m.smRef && m.riscos && m.riscos.indexOf(r.codigo) >= 0; }).map(function (m) { return m.smRef; });
        return { projetoId: projetoId, codigo: r.codigo, titulo: r.titulo, severidade: r.sevAtual ? r.sevAtual.nome : "", situacao: r.situacao, vmeCentavos: r.vmeCentavos || 0, sms: sms };
      }),
      alertas: alertas
    };
  }
  function contingenciaCarteira() {
    var partes = projetosCarteira().map(function (p) { var x = contingenciaProjeto(p.id); if (x) { x.projetoCodigo = p.codigo; x.projetoNome = p.nome; } return x; }).filter(Boolean);
    if (!partes.length) return null;
    var par = parContingencia();
    function s(k, f) { return soma(partes, function (x) { return x[k][f]; }); }
    var total = s("contingencia", "total"), consumo = s("contingencia", "consumido"), emAnalise = s("contingencia", "emAnalise"), saldo = s("contingencia", "saldo");
    var exposicao = soma(partes, "exposicaoCentavos");
    var pesos = soma(partes, function (x) { return x.contingencia.total; });
    var avanco = pesos ? arred(soma(partes, function (x) { return (x.avancoReal || 0) * x.contingencia.total; }) / pesos, 1) : null;
    var meses = [];
    partes.forEach(function (x) { x.burn.forEach(function (b) { if (meses.indexOf(b.mes) < 0) meses.push(b.mes); }); });
    meses.sort();
    var corteMax = partes.reduce(function (m, x) { var c = curvaFisicaDe(x.projetoId); return c && c.corte > m ? c.corte : m; }, "");
    var burn = meses.map(function (m) {
      var esp = 0, real = 0;
      partes.forEach(function (x) {
        var b = x.burn.filter(function (y) { return y.mes === m; })[0];
        var antes = x.burn.length && m < x.burn[0].mes, ult = x.burn.filter(function (y) { return y.real != null; }).slice(-1)[0];
        esp += b ? b.esperado : antes ? x.contingencia.total : 0;
        real += b && b.real != null ? b.real : antes ? x.contingencia.total : ult ? ult.real : x.contingencia.total;
      });
      return { mes: m, esperado: esp, real: m <= corteMax ? real : null };
    });
    var consumoPct = total ? arred(consumo / total * 100, 1) : null;
    var cobertura = exposicao ? arred(saldo / exposicao * 100, 1) : null;
    var alertas = [];
    partes.forEach(function (x) { x.alertas.forEach(function (a) { alertas.push({ tipo: a.tipo, texto: x.projetoCodigo + ": " + a.texto }); }); });
    return {
      portfolio: true, projetos: partes.map(function (x) {
        return { projetoId: x.projetoId, projetoCodigo: x.projetoCodigo, projetoNome: x.projetoNome, total: x.contingencia.total, consumido: x.contingencia.consumido, emAnalise: x.contingencia.emAnalise,
          saldo: x.contingencia.saldo, consumoPct: x.contingencia.consumoPct, avancoReal: x.avancoReal, limiteConsumoPct: x.limiteConsumoPct, exposicaoCentavos: x.exposicaoCentavos,
          coberturaPct: x.coberturaPct, gerencial: x.gerencial.saldo, alertas: x.alertas.length };
      }),
      contingencia: { total: total, consumido: consumo, liberado: s("contingencia", "liberado"), emAnalise: emAnalise, saldo: saldo, saldoAposAnalise: saldo - emAnalise, consumoPct: consumoPct },
      gerencial: { total: s("gerencial", "total"), consumido: s("gerencial", "consumido"), liberado: s("gerencial", "liberado"), emAnalise: s("gerencial", "emAnalise"), saldo: s("gerencial", "saldo") },
      avancoReal: avanco, limiteConsumoPct: avanco != null ? arred(Math.min(100, avanco + par.toleranciaConsumoPP), 1) : null,
      exposicaoCentavos: exposicao, coberturaPct: cobertura, coberturaMinimaPct: par.coberturaMinimaPct, toleranciaConsumoPP: par.toleranciaConsumoPP,
      pmbCentavos: soma(partes, "pmbCentavos"), linhaBaseCustoCentavos: soma(partes, "linhaBaseCustoCentavos"), orcamentoProjetoCentavos: soma(partes, "orcamentoProjetoCentavos"),
      movimentos: partes.reduce(function (l, x) { return l.concat(x.movimentos.map(function (m) { m.projetoCodigo = x.projetoCodigo; return m; })); }, []),
      riscos: partes.reduce(function (l, x) { return l.concat(x.riscos.map(function (r) { r.projetoCodigo = x.projetoCodigo; return r; })); }, []).sort(function (a, b) { return b.vmeCentavos - a.vmeCentavos; }),
      burn: burn, smsEmAnalise: soma(partes, "smsEmAnalise"), alertas: alertas
    };
  }
  function contingenciaDe(projetoId) { return projetoId == null ? contingenciaCarteira() : contingenciaProjeto(projetoId); }
  /* TODO: API GET /projetos/{id}/reservas */
  function contingencia(projetoId) { return responder(contingenciaDe(projetoId)); }

  /* TODO: API GET /projetos/{id}/indicadores-custo */
  function indicadoresCusto(projetoId) { return responder(indicesCustoDe(projetoId)); }

  /* Contratos com valores consolidados */
  var MEDICAO_VALIDA = ["Aprovada", "Faturada", "Paga"];
  var CLAIM_ABERTO = ["Notificado", "Em análise", "Em negociação", "Em disputa"];
  function contratosDe(projetoId) {
    var empresas = porId(M.empresas);
    return doProjeto(M.contratos, projetoId).map(function (c) {
      var x = copia(c);
      var ad = (M.aditivos || []).filter(function (a) { return a.contratoId === c.id; });
      var med = (M.medicoes || []).filter(function (m) { return m.contratoId === c.id; });
      var cl = (M.claims || []).filter(function (m) { return m.contratoId === c.id; });
      x.empresa = empresas[c.empresaId] ? empresas[c.empresaId].nome : "";
      x.aditivosCentavos = soma(ad, "valorCentavos");
      x.valorAtualCentavos = c.valorOriginalCentavos + x.aditivosCentavos;
      x.medidoCentavos = soma(med.filter(function (m) { return MEDICAO_VALIDA.indexOf(m.situacao) >= 0; }), "brutoCentavos");
      x.saldoCentavos = x.valorAtualCentavos - x.medidoCentavos;
      x.medidoPct = arred(x.medidoCentavos / x.valorAtualCentavos * 100, 1);
      x.claimsAbertos = cl.filter(function (m) { return CLAIM_ABERTO.indexOf(m.situacao) >= 0; }).length;
      x.exposicaoCentavos = soma(cl.filter(function (m) { return m.direcao === "Da contratada" && CLAIM_ABERTO.indexOf(m.situacao) >= 0; }), "pleiteadoCentavos");
      x.diasAditados = R.diasEntre(c.terminoOriginal, c.terminoVigente);
      var aval = (M.avaliacoes || []).filter(function (a) { return a.contratoId === c.id; }).sort(function (a, b) { return a.periodo < b.periodo ? 1 : -1; })[0];
      x.ultimaAvaliacao = aval ? avaliacaoCalculada(aval) : null;
      return x;
    });
  }
  /* Avaliação usa os pesos gravados nela (snapshot), não os parâmetros atuais */
  function avaliacaoCalculada(a) {
    var param = copia(P().avaliacaoContratada);
    param.criterios = param.criterios.map(function (c) { return { id: c.id, nome: c.nome, peso: a.pesos && a.pesos[c.id] != null ? a.pesos[c.id] : c.peso }; });
    var r = R.avaliarContratada(a.notas, param);
    var x = copia(a);
    x.nota = r.nota; x.classe = r.classe ? r.classe.classe : null; x.classeDescricao = r.classe ? r.classe.descricao : ""; x.exigePlano = r.exigePlano;
    return x;
  }
  /* TODO: API GET /projetos/{id}/contratos */
  function listarContratos(projetoId) { return responder(contratosDe(projetoId)); }
  function claimsDe(projetoId) {
    var contratos = porId(doProjeto(M.contratos, projetoId));
    return (M.claims || []).filter(function (c) { return contratos[c.contratoId]; }).map(function (c) {
      var x = copia(c);
      var ct = contratos[c.contratoId];
      x.contrato = ct.numero;
      x.diasParaNotificar = R.diasEntre(c.evento, c.notificacao);
      x.foraDoPrazo = x.diasParaNotificar > ct.prazoNotificacaoClaimDias;
      x.aberto = CLAIM_ABERTO.indexOf(c.situacao) >= 0;
      return x;
    });
  }
  /* TODO: API GET /projetos/{id}/claims */
  function listarClaims(projetoId) { return responder(claimsDe(projetoId)); }
  function resumoContratos(projetoId) {
    var cts = contratosDe(projetoId), cls = claimsDe(projetoId);
    var ids = cts.map(function (c) { return c.id; });
    var marcos = (M.marcosPagamento || []).filter(function (m) { return ids.indexOf(m.contratoId) >= 0; });
    return {
      contratos: cts.length,
      exposicaoCentavos: soma(cts, "exposicaoCentavos"),
      claimsAbertos: cls.filter(function (c) { return c.aberto; }).length,
      notificacoesForaDoPrazo: cls.filter(function (c) { return c.foraDoPrazo; }).length,
      marcosAtrasados: marcos.filter(function (m) { return m.prevista < REF && ["Previsto", "Evidência enviada"].indexOf(m.situacao) >= 0; }).length,
      contratadasCouD: cts.filter(function (c) { return c.ultimaAvaliacao && ["C", "D"].indexOf(c.ultimaAvaliacao.classe) >= 0; }).length
    };
  }

  /* Valor agregado mês a mês até o corte (CPI e SPI históricos) */
  /* TODO: API GET /projetos/{id}/valor-agregado */
  function historicoIndices(projetoId) {
    if (projetoId == null) {
      var finC = curvaFinanceiraCarteira();
      return responder(finC ? finC.meses.filter(function (m) { return m <= finC.corte; }).map(vaCarteiraNoMes).filter(Boolean) : []);
    }
    var fis = curvaFisicaDe(projetoId), fin = curvaFinanceiraDe(projetoId);
    if (!fis || !fin) return responder([]);
    var bac = mapaControleDe(projetoId).total.atual;
    return responder(fin.meses.map(function (m) { return valorAgregadoNoMes(fis, fin, bac, m); }).filter(Boolean));
  }

  /* Cronograma de desembolso: mensal da curva financeira e saldo a pagar de cada
     item (projeção no término menos realizado) distribuído nos meses após o corte,
     proporcional ao perfil da projeção. TODO: API GET /projetos/{id}/desembolso
     (no backend, a distribuição vem dos marcos de pagamento e dos contratos). */
  function desembolsoProjeto(projetoId) {
    var fin = curvaFinanceiraDe(projetoId);
    if (!fin) return null;
    var k = fin.meses.indexOf(fin.corte);
    function mensal(serie) {
      return serie.map(function (v, i) {
        if (v == null) return null;
        var ant = i > 0 ? serie[i - 1] : 0;
        return ant == null ? null : v - ant;
      });
    }
    var planejado = mensal(fin.planejado), realizado = mensal(fin.realizado);
    var projetado = fin.projecao.map(function (v, i) { return i <= k || v == null || fin.projecao[i - 1] == null ? null : v - fin.projecao[i - 1]; });
    var futuros = fin.meses.slice(k + 1);
    var pesos = futuros.map(function (m) { return projetado[fin.meses.indexOf(m)] || 0; });
    var somaPesos = pesos.reduce(function (a, b) { return a + b; }, 0);
    var mapa = mapaControleDe(projetoId);
    var itens = mapa.itens.map(function (x) {
      var saldo = Math.max(0, x.projecao - x.realizado);
      var dist = {}, acum = 0;
      futuros.forEach(function (m, j) {
        var v = j === futuros.length - 1 ? saldo - acum : (somaPesos ? Math.round(saldo * pesos[j] / somaPesos) : 0);
        dist[m] = v; acum += v;
      });
      return { codigo: x.codigo, descricao: x.descricao, nivel: x.nivel, folha: x.folha, projecao: x.projecao, realizado: x.realizado, saldo: saldo, meses: dist };
    });
    var totalMeses = {};
    futuros.forEach(function (m) { totalMeses[m] = soma(itens.filter(function (x) { return x.nivel === 1; }), function (x) { return x.meses[m]; }); });
    return {
      corte: fin.corte, meses: fin.meses, futuros: futuros,
      planejado: planejado, realizado: realizado, projetado: projetado,
      itens: itens, totalMeses: totalMeses,
      saldo: soma(itens.filter(function (x) { return x.nivel === 1; }), "saldo"),
      realizadoAcumulado: fin.realizado[k], projecaoTermino: mapa.total.projecao
    };
  }
  function desembolso(projetoId) { return responder(desembolsoDe(projetoId)); }

  /* ---------------- EAC: revisões, remanejamentos, itens e custos ---------------- */
  var SM_APROVADA = ["Aprovada", "Aprovada com condições", "Em implementação", "Encerrada"];
  function revisoesEacDe(projetoId) {
    return doProjeto(M.eacRevisoes, projetoId).slice().sort(function (a, b) { return a.revisao - b.revisao; });
  }
  function revisaoVigente(projetoId) { var r = revisoesEacDe(projetoId); return r.length ? r[r.length - 1] : null; }
  /* SMs aprovadas com impacto de custo ainda não incorporadas ao orçamento */
  function smsPendentesDe(projetoId) {
    var usadas = revisoesEacDe(projetoId).map(function (r) { return r.smRef; });
    return doProjeto(M.mudancas, projetoId).filter(function (s) {
      return SM_APROVADA.indexOf(s.situacao) >= 0 && s.impacto && s.impacto.custoCentavos && usadas.indexOf(s.codigo) < 0;
    }).map(copia);
  }
  function folhaPorCodigo(projetoId, codigo) {
    return doProjeto(M.eac, projetoId).filter(function (x) { return x.codigo === codigo && x.nivel === 3; })[0] || null;
  }
  /* TODO: API GET /projetos/{id}/eac (árvore, revisões, remanejamentos e SMs pendentes) */
  function eacDe(projetoId) {
    if (projetoId == null) {
      /* Portfólio: revisão vigente de cada projeto, remanejamentos das revisões vigentes e SMs pendentes de todos */
      var cod = function (pid) { return (porId(M.projetos)[pid] || {}).codigo || ""; };
      var vigs = projetosCarteira().map(function (p) { var v = revisaoVigente(p.id); if (!v) return null; var r0 = revisoesEacDe(p.id)[0];
        return Object.assign(copia(v), { projetoCodigo: p.codigo, projetoNome: p.nome, linhaBase: r0 ? r0.totalCentavos : null, revisoes: revisoesEacDe(p.id).length }); }).filter(Boolean);
      return responder({
        portfolio: true, mapa: mapaCarteira(), revisoes: vigs, vigente: null,
        remanejamentos: vigs.reduce(function (l, v) { return l.concat(doProjeto(M.eacRemanejamentos, v.projetoId).filter(function (r) { return r.revisao === v.revisao; }).map(function (r) { var x = copia(r); x.projetoCodigo = cod(r.projetoId); return x; })); }, []),
        remanejamentosPendentes: remanejamentosPendentesDe(null).map(function (r) { r.projetoCodigo = cod(r.projetoId); return r; }),
        smsPendentes: smsPendentesDe(null).map(function (sm) { sm.projetoCodigo = cod(sm.projetoId); return sm; }),
        reserva: (function () { var l = (M.reservas || []); return l.length ? { contingenciaCentavos: soma(l, "contingenciaCentavos") } : null; })(),
        indices: indicesCustoCarteira()
      });
    }
    var vig = revisaoVigente(projetoId);
    return responder({
      mapa: mapaControleDe(projetoId),
      revisoes: revisoesEacDe(projetoId),
      vigente: vig,
      remanejamentos: doProjeto(M.eacRemanejamentos, projetoId).filter(function (r) { return vig && r.revisao === vig.revisao; }),
      remanejamentosPendentes: remanejamentosPendentesDe(projetoId),
      smsPendentes: smsPendentesDe(projetoId),
      reserva: (M.reservas || []).filter(function (r) { return r.projetoId === projetoId; })[0] || null,
      indices: indicesCustoDe(projetoId)
    });
  }
  /* Remanejamento entre itens da EAC (elementos PEP): soma zero e só por gestão de mudanças.
     A solicitação vira SM do tipo "Remanejamento de orçamento" (08) com as transferências propostas;
     a aprovação da SM aplica as transferências (aplicarRemanejamentosSm). Nada muda valor sem SM.
     TODO: API POST /projetos/{id}/eac/remanejamentos (cria a SM) */
  function remanejar(projetoId, d) {
    return solicitarRemanejamento(projetoId, {
      titulo: d.titulo || ("Remanejamento de " + moedaBr(d.valorCentavos) + " do item " + d.origem + " para o " + d.destino),
      justificativa: d.justificativa, prioridade: d.prioridade,
      remanejamentos: [{ origem: d.origem, destino: d.destino, valorCentavos: d.valorCentavos }]
    });
  }
  /* Transferências propostas em SMs abertas (ainda não aplicadas na EAC) */
  function remanejamentosPendentesDe(projetoId) {
    var l = [];
    doProjeto(M.mudancas, projetoId).forEach(function (s) {
      if (!s.remanejamentos || s.remanejamentoAplicado || SM_TERMINAL.indexOf(s.situacao) >= 0) return;
      s.remanejamentos.forEach(function (t) {
        l.push({ projetoId: s.projetoId, smRef: s.codigo, situacaoSm: s.situacao, data: s.dataSolicitacao, origem: t.origem, destino: t.destino,
          valorCentavos: t.valorCentavos, novoItem: !!t.novoItem, justificativa: s.titulo, porId: s.solicitanteId, pendente: true });
      });
    });
    return l;
  }
  /* Nova revisão: consolida os remanejamentos na base, aplica os ajustes da SM
     (e itens novos) e reescala a linha de base de custo da Curva S financeira.
     TODO: API POST /projetos/{id}/eac/revisoes */
  function novaRevisao(projetoId, d) {
    var vig = revisaoVigente(projetoId);
    var erros = [];
    if (!d.justificativa) erros.push({ campo: "justificativa", msg: "Preencha este campo." });
    var smRev = d.smRef ? smsPendentesDe(projetoId).filter(function (s) { return s.codigo === d.smRef; })[0] : null;
    if (!smRev) erros.push({ campo: "sm", msg: "A revisão do orçamento exige SM aprovada com impacto em custo e ainda não incorporada (08 Governança)." });
    else {
      var acrescimo = soma(d.ajustes || [], "deltaCentavos") + soma(d.novos || [], "base");
      if (smRev.impacto.custoCentavos > 0 && acrescimo > smRev.impacto.custoCentavos) erros.push("O acréscimo (" + moedaBr(acrescimo) + ") supera o custo aprovado na " + smRev.codigo + " (" + moedaBr(smRev.impacto.custoCentavos) + ").");
    }
    (d.ajustes || []).forEach(function (a) { if (!folhaPorCodigo(projetoId, a.codigo)) erros.push("Item " + a.codigo + " não encontrado."); });
    if (erros.length) return rejeitar(erros);
    var eac = colecao("eac");
    doProjeto(eac, projetoId).forEach(function (x) {
      if (x.nivel !== 3) return;
      x.base += x.remanejamento; x.remanejamento = 0;
    });
    (d.ajustes || []).forEach(function (a) {
      var x = folhaPorCodigo(projetoId, a.codigo);
      x.base += a.deltaCentavos; x.projecao += a.deltaCentavos;
    });
    (d.novos || []).forEach(function (n) {
      var novo = copia(n);
      novo.id = eac.reduce(function (m, x) { return Math.max(m, x.id); }, 0) + 1;
      novo.projetoId = projetoId; novo.nivel = 3; novo.remanejamento = 0; novo.comprometido = novo.comprometido || 0; novo.realizado = novo.realizado || 0;
      novo.projecao = novo.projecao == null ? novo.base : novo.projecao;
      eac.push(novo);
    });
    var total = soma(doProjeto(eac, projetoId).filter(function (x) { return x.nivel === 3; }), "base");
    var rev = { id: colecao("eacRevisoes").reduce(function (m, x) { return Math.max(m, x.id); }, 0) + 1, projetoId: projetoId,
      revisao: vig ? vig.revisao + 1 : 0, data: REF, totalCentavos: total, justificativa: d.justificativa, smRef: d.smRef || null,
      aprovadoPorId: (M.sessao || {}).pessoaId };
    colecao("eacRevisoes").push(rev);
    var curva = curvaFinanceiraDe(projetoId);
    if (curva && vig && vig.totalCentavos && total !== vig.totalCentavos) {
      var f = total / vig.totalCentavos;
      curva.planejado = curva.planejado.map(function (v) { return v == null ? v : Math.round(v * f); });
      persistir("curvaFinanceira");
    }
    persistir("eac"); persistir("eacRevisoes");
    return responder(copia(rev));
  }
  /* Item novo: entra com recurso de remanejamento (sem mudar o total) ou por nova revisão (SM aprovada) */
  function proximoCodigoEac(projetoId, pai) {
    var n = doProjeto(M.eac, projetoId).filter(function (x) { return x.codigo.indexOf(pai + ".") === 0 && x.codigo.split(".").length === pai.split(".").length + 1; })
      .reduce(function (m, x) { return Math.max(m, Number(x.codigo.split(".").pop())); }, 0);
    return pai + "." + (n + 1);
  }
  /* Item novo (elemento PEP): por SM de remanejamento (recurso de outro item; o total não muda; o item
     nasce na aprovação) ou por nova revisão a partir de SM aprovada com custo.
     TODO: API POST /projetos/{id}/eac/itens */
  function novoItemEac(projetoId, item, recurso) {
    if (doProjeto(M.eac, projetoId).some(function (x) { return x.codigo === item.codigo; })) return rejeitar("Já existe item com o código " + item.codigo + ".");
    if (recurso.tipo === "revisao") {
      return novaRevisao(projetoId, { justificativa: recurso.justificativa, smRef: recurso.smRef, novos: [item] });
    }
    var spec = copia(item); var valor = spec.base; delete spec.base;
    return solicitarRemanejamento(projetoId, {
      titulo: "Novo item " + item.codigo + " " + item.descricao + " com recurso do item " + recurso.origem,
      justificativa: recurso.justificativa, prioridade: recurso.prioridade,
      remanejamentos: [{ origem: recurso.origem, destino: item.codigo, valorCentavos: valor, novoItem: spec }]
    });
  }
  /* Dados cadastrais do item (descrição, tipo, classificação, centro de custo, responsável): não mudam
     valor, então dispensam SM, mas exigem justificativa e ficam no histórico do item (trilha de auditoria).
     TODO: API PUT /projetos/{id}/eac/itens/{codigo} */
  var CAMPOS_CADASTRO_EAC = { descricao: "descrição", tipoCusto: "tipo de custo", capex: "classificação", centroCusto: "centro de custo", responsavelId: "responsável" };
  function editarItemEac(projetoId, codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite editar a EAC.");
    var x = folhaPorCodigo(projetoId, codigo);
    if (!x) return rejeitar("Item " + codigo + " não encontrado.");
    var e = [];
    if (!d.descricao || String(d.descricao).trim().length < 3) e.push({ campo: "descricao", msg: "Informe a descrição." });
    if (!d.justificativa || String(d.justificativa).trim().length < 10) e.push({ campo: "justificativa", msg: "Informe a justificativa da alteração (mínimo de 10 caracteres)." });
    if (e.length) return Promise.reject({ erros: e });
    var novo = { descricao: String(d.descricao).trim(), tipoCusto: d.tipoCusto, capex: !!d.capex, centroCusto: d.centroCusto || "", responsavelId: Number(d.responsavelId) };
    var mud = Object.keys(CAMPOS_CADASTRO_EAC).filter(function (k) { return String(x[k] == null ? "" : x[k]) !== String(novo[k] == null ? "" : novo[k]); });
    if (!mud.length) return responder({ codigo: codigo, alterados: 0 });
    var eac = colecao("eac"), item = eac.filter(function (y) { return y.projetoId === projetoId && y.codigo === codigo; })[0];
    var antes = {};
    mud.forEach(function (k) { antes[k] = item[k]; item[k] = novo[k]; });
    item.historicoCadastro = (item.historicoCadastro || []).concat([{ data: REF, porId: sessaoPessoa(), campos: mud.map(function (k) { return CAMPOS_CADASTRO_EAC[k]; }), antes: antes, justificativa: String(d.justificativa).trim() }]);
    persistir("eac");
    return responder({ codigo: codigo, alterados: mud.length });
  }
  /* Custos do ERP (fechamento do mês): comprometido, realizado e projeção por item.
     TODO: API POST /projetos/{id}/eac/custos (integração com o ERP) */
  function importarCustos(projetoId, linhas) {
    var n = 0;
    linhas.forEach(function (l) {
      var x = folhaPorCodigo(projetoId, l.codigo);
      if (!x) return;
      if (l.comprometido != null) x.comprometido = l.comprometido;
      if (l.realizado != null) x.realizado = l.realizado;
      if (l.projecao != null) x.projecao = l.projecao;
      n++;
    });
    persistir("eac");
    return responder(n);
  }
  /* Atualização da projeção no término de um item pelo responsável */
  function atualizarProjecao(projetoId, codigo, projecao, justificativa) {
    var x = folhaPorCodigo(projetoId, codigo);
    if (!x) return rejeitar("Item " + codigo + " não encontrado.");
    if (projecao < x.realizado) return rejeitar({ campo: "projecao", msg: "A projeção não pode ser menor que o realizado." });
    x.historicoProjecao = (x.historicoProjecao || []).concat([{ data: REF, de: x.projecao, para: projecao, justificativa: justificativa, porId: (M.sessao || {}).pessoaId }]);
    x.projecao = projecao;
    persistir("eac");
    return responder(copia(x));
  }

  /* ---------------- Contratos: consolidado e ficha ---------------- */
  var MARCO_PENDENTE = ["Previsto", "Evidência enviada"];
  function marcoCalculado(m) {
    var x = copia(m);
    x.atrasado = m.prevista < REF && MARCO_PENDENTE.indexOf(m.situacao) >= 0;
    x.diasAtraso = x.atrasado ? R.diasEntre(m.prevista, REF) : 0;
    return x;
  }
  function eotsDe(projetoId) {
    var contratos = porId(doProjeto(M.contratos, projetoId));
    return (M.extensoesPrazo || []).filter(function (e) { return contratos[e.contratoId]; }).map(function (e) {
      var x = copia(e); x.contrato = contratos[e.contratoId].numero; x.aberta = ["Solicitada", "Em análise"].indexOf(e.situacao) >= 0; return x;
    });
  }
  function marcosDe(projetoId) {
    var contratos = porId(doProjeto(M.contratos, projetoId));
    return (M.marcosPagamento || []).filter(function (m) { return contratos[m.contratoId]; }).map(function (m) {
      var x = marcoCalculado(m); x.contrato = contratos[m.contratoId].numero; return x;
    });
  }
  function avaliacoesDe(projetoId) {
    var contratos = porId(doProjeto(M.contratos, projetoId)), empresas = porId(M.empresas);
    return (M.avaliacoes || []).filter(function (a) { return contratos[a.contratoId]; }).map(function (a) {
      var x = avaliacaoCalculada(a), c = contratos[a.contratoId];
      x.contrato = c.numero; x.empresa = empresas[c.empresaId] ? empresas[c.empresaId].nome : ""; return x;
    });
  }
  function indicadoresContratos(projetoId) {
    var cts = contratosDe(projetoId), cls = claimsDe(projetoId), eots = eotsDe(projetoId), marcos = marcosDe(projetoId);
    var encerrados = cls.filter(function (c) { return ["Acordado", "Encerrado", "Rejeitado"].indexOf(c.situacao) >= 0 && c.direcao === "Da contratada"; });
    var pleiteado = soma(encerrados, "pleiteadoCentavos"), reconhecido = soma(encerrados, function (c) { return c.reconhecidoCentavos || 0; });
    var comFim = cls.filter(function (c) { return c.encerramento; });
    var duracao = soma(cts, function (c) { return R.diasEntre(c.inicio, c.terminoOriginal); });
    var concedidos = soma(eots, function (e) { return e.diasConcedidos || 0; });
    var previstoAteRef = soma(marcos.filter(function (m) { return m.prevista <= REF; }), "valorCentavos");
    var pago = soma(marcos.filter(function (m) { return m.situacao === "Pago"; }), "valorCentavos");
    return {
      exposicaoDaContratada: soma(cls.filter(function (c) { return c.aberto && c.direcao === "Da contratada"; }), "pleiteadoCentavos"),
      exposicaoDoContratante: soma(cls.filter(function (c) { return c.aberto && c.direcao === "Do contratante"; }), "pleiteadoCentavos"),
      taxaReconhecimento: pleiteado ? arred(reconhecido / pleiteado * 100, 1) : null,
      tempoMedioResolucao: comFim.length ? Math.round(soma(comFim, function (c) { return R.diasEntre(c.notificacao, c.encerramento); }) / comFim.length) : null,
      diasSolicitados: soma(eots, "diasSolicitados"), diasConcedidos: concedidos,
      extensaoPct: duracao ? arred(concedidos / duracao * 100, 1) : null,
      aprovadoNaoFaturado: soma(marcos.filter(function (m) { return m.situacao === "Aprovado"; }), "valorCentavos"),
      pagoPrevistoPct: previstoAteRef ? arred(pago / previstoAteRef * 100, 1) : null,
      notaMedia: (function () { var av = cts.filter(function (c) { return c.ultimaAvaliacao; }); return av.length ? arred(soma(av, function (c) { return c.ultimaAvaliacao.nota; }) / av.length, 1) : null; })()
    };
  }
  /* TODO: API GET /projetos/{id}/contratos/consolidado */
  function consolidadoContratos(projetoId) {
    return responder({
      contratos: contratosDe(projetoId), claims: claimsDe(projetoId), extensoes: eotsDe(projetoId), marcos: marcosDe(projetoId),
      avaliacoes: avaliacoesDe(projetoId), resumo: resumoContratos(projetoId), indicadores: indicadoresContratos(projetoId)
    });
  }
  /* TODO: API GET /contratos/{numero} */
  function contratoDetalhe(numero) {
    var c = (M.contratos || []).filter(function (x) { return x.numero === numero; })[0];
    if (!c) return responder(null);
    var x = contratosDe(c.projetoId).filter(function (y) { return y.id === c.id; })[0];
    x.aditivos = (M.aditivos || []).filter(function (a) { return a.contratoId === c.id; }).map(copia);
    x.medicoes = (M.medicoes || []).filter(function (m) { return m.contratoId === c.id; }).map(function (m) {
      var y = copia(m); y.retencaoCentavos = Math.round(m.brutoCentavos * c.retencaoPct / 100); y.liquidoCentavos = m.brutoCentavos - y.retencaoCentavos; return y;
    });
    x.marcos = (M.marcosPagamento || []).filter(function (m) { return m.contratoId === c.id; }).map(marcoCalculado);
    x.claims = claimsDe(c.projetoId).filter(function (m) { return m.contratoId === c.id; });
    x.extensoes = eotsDe(c.projetoId).filter(function (e) { return e.contratoId === c.id; });
    x.avaliacoes = avaliacoesDe(c.projetoId).filter(function (a) { return a.contratoId === c.id; }).sort(function (a, b) { return a.periodo < b.periodo ? -1 : 1; });
    x.duracaoOriginal = R.diasEntre(c.inicio, c.terminoOriginal);
    x.faturadoCentavos = soma(x.medicoes.filter(function (m) { return ["Faturada", "Paga"].indexOf(m.situacao) >= 0; }), "brutoCentavos");
    x.pagoCentavos = soma(x.medicoes.filter(function (m) { return m.situacao === "Paga"; }), "brutoCentavos");
    x.retidoCentavos = soma(x.medicoes.filter(function (m) { return MEDICAO_VALIDA.indexOf(m.situacao) >= 0; }), "retencaoCentavos");
    return responder(x);
  }
  /* Aditivo: soma ao valor e, com dias, prorroga o término vigente. TODO: API POST /contratos/{id}/aditivos */
  function salvarAditivo(contratoId, d) {
    var c = (M.contratos || []).filter(function (x) { return x.id === contratoId; })[0];
    if (!c) return rejeitar("Contrato não encontrado.");
    var lista = colecao("aditivos");
    var n = lista.filter(function (a) { return a.contratoId === contratoId; }).length + 1;
    var ad = { id: lista.reduce(function (m, x) { return Math.max(m, x.id); }, 0) + 1, contratoId: contratoId, numero: "AD-" + ("0" + n).slice(-2),
      data: d.data || REF, valorCentavos: d.valorCentavos || 0, dias: d.dias || 0, motivo: d.motivo, smRef: d.smRef || null, claimRef: d.claimRef || null };
    lista.push(ad);
    if (ad.dias) { c.terminoVigente = somarDiasIso(c.terminoVigente, ad.dias); persistir("contratos"); }
    persistir("aditivos");
    return responder(copia(ad));
  }
  function somarDiasIso(iso, dias) {
    var d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + dias);
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  /* Decisão da extensão de prazo: concedida prorroga o término vigente. TODO: API PUT /extensoes-prazo/{id}/decisao */
  function decidirEot(id, d) {
    var e = (M.extensoesPrazo || []).filter(function (x) { return x.id === id; })[0];
    if (!e) return rejeitar("Extensão não encontrada.");
    var c = (M.contratos || []).filter(function (x) { return x.id === e.contratoId; })[0];
    e.situacao = d.situacao; e.decisao = REF;
    e.diasConcedidos = d.situacao === "Negada" ? 0 : d.diasConcedidos;
    e.classificacao = d.classificacao || e.classificacao;
    if (e.diasConcedidos) { c.terminoVigente = somarDiasIso(c.terminoVigente, e.diasConcedidos); persistir("contratos"); }
    persistir("extensoesPrazo");
    return responder(copia(e));
  }

  /* ======================================================================
     04 Suprimentos
     Fonte única: pacotes (plano e processo), processos (RFx) e pedidos
     (diligenciamento). O MAS (Mapa de Suprimentos) é montado aqui a partir
     dessas coleções; nada do MAS é gravado em separado.
     ====================================================================== */
  var ETAPAS_SUP = ["Planejado", "Requisição", "RFx emitida", "Propostas recebidas", "Equalização técnica", "Equalização comercial",
    "Negociação", "Recomendação de adjudicação", "Aprovada", "Pedido/contrato emitido"];
  var MARCOS_AQ = [
    { id: "requisicao", nome: "Requisição" }, { id: "rfx", nome: "RFx emitida" }, { id: "propostas", nome: "Propostas" },
    { id: "eqTecnica", nome: "Equalização técnica" }, { id: "eqComercial", nome: "Equalização comercial" },
    { id: "adjudicacao", nome: "Aprovação" }, { id: "pedido", nome: "Pedido/contrato" }
  ];
  /* Marcos de fabricação no MAS e posição no cronograma do pedido (0 docs, 1 matéria-prima, 2 fabricação, 3 FAT, 4 embarque, 5 entrega) */
  var MARCOS_FAB = [
    { id: "documentos", nome: "Documentos aprovados", idx: 0 }, { id: "fabricacao", nome: "Fabricação", idx: 2 },
    { id: "inspecao", nome: "Inspeção / FAT", idx: 3 }, { id: "embarque", nome: "Embarque", idx: 4 }, { id: "entrega", nome: "Entrega", idx: 5 }
  ];
  var NOMES_MARCOS_PEDIDO = ["Aprovação de documentos", "Matéria-prima", "Fabricação", "Inspeção / FAT", "Embarque", "Entrega"];
  /* Proporção do prazo entre pedido e entrega em que cada marco de fabricação cai (LB estimada e pedido novo) */
  var PROP_FAB = [0.15, 0.3, 0.75, 0.85, 0.93, 1];
  var TIPOS_CONTRATO = ["Serviço", "EPC"];
  function ehServico(p) { return TIPOS_CONTRATO.indexOf(p.tipo) >= 0; }
  function etapaIdx(e) { return ETAPAS_SUP.indexOf(e); }
  function porCampo(lista, campo, valor) { return (lista || []).filter(function (x) { return x[campo] === valor; })[0] || null; }
  function proximoId(nome) { return colecao(nome).reduce(function (m, x) { return Math.max(m, Number(x.id) || 0); }, 0) + 1; }
  function sessaoPessoa() { return (M.sessao || {}).pessoaId || null; }
  function entre(ini, fim, fr) {
    var a = R.data(ini), b = R.data(fim);
    if (!a || !b) return null;
    return somarDiasIso(ini, Math.round((b - a) / 86400000 * fr));
  }
  function nomeEmpresa(id) { var e = porId(M.empresas)[id]; return e ? e.nome : ""; }
  function qualificacaoDe(empresaId) { return porCampo(M.fornecedores, "empresaId", empresaId); }
  function acaoAbertaDe(ref) {
    return (M.acoes || []).filter(function (a) { return a.origem === "Suprimentos" && a.origemRef === ref && !a.conclusao; })[0] || null;
  }
  function riscoDe(pedido) {
    if (pedido.riscoRef) return porCampo(M.riscos, "codigo", pedido.riscoRef);
    return (M.riscos || []).filter(function (r) { return !r.oculto && ["Encerrado", "Materializado"].indexOf(r.situacao) < 0 && String(r.origem || "").indexOf(pedido.numero) >= 0 && r.natureza === "Ameaça"; })[0] || null;
  }

  /* ---------------- Pedidos (diligenciamento) ---------------- */
  function pedidoCalculado(p, alerta) {
    var x = copia(p);
    var pac = porId(M.pacotes)[p.pacoteId];
    x.fornecedor = nomeEmpresa(p.fornecedorId);
    x.projetoCodigo = (porId(M.projetos)[p.projetoId] || {}).codigo || "";
    x.pacote = pac ? pac.codigo : "";
    x.compradorId = pac ? pac.compradorId : null;
    x.marcos.forEach(function (m) {
      var s = R.situacaoMarco({ lb: m.lb, previsao: m.realizada ? null : m.previsao, real: m.realizada }, REF);
      m.situacao = s.chave; m.desvio = s.desvio; m.diasVencido = s.diasVencido || 0;
    });
    var ent = x.marcos[5];
    x.previsao = ent ? ent.previsao : p.previsao;
    x.entregue = !!p.entrega;
    x.folgaDias = R.folga(p.ros, p.entrega || x.previsao);
    x.atrasoContratualDias = R.diasEntre(p.dataContratual, p.entrega || x.previsao);
    x.critico = !x.entregue && x.folgaDias < 0;
    x.faixaFolga = R.faixaFolga(x.folgaDias, alerta, x.entregue);
    x.proximoMarco = x.marcos.filter(function (m) { return !m.realizada; })[0] || null;
    x.marcosVencidos = x.marcos.filter(function (m) { return m.situacao === "vencido"; }).length;
    var acao = acaoAbertaDe(p.numero);
    x.acaoAberta = acao ? { id: acao.id, assunto: acao.assunto, prevista: acao.replanejada || acao.prevista } : null;
    var rsk = riscoDe(p);
    x.risco = rsk ? { codigo: rsk.codigo, titulo: rsk.titulo, situacao: rsk.situacao } : null;
    return x;
  }
  function pedidosDe(projetoId) {
    var alerta = P().suprimentos.folgaAlertaDias;
    return doProjeto(M.pedidos, projetoId).map(function (p) { return pedidoCalculado(p, alerta); });
  }
  /* TODO: API GET /projetos/{id}/pedidos (folga, situação dos marcos e pendências calculadas no servidor) */
  function listarPedidos(projetoId) { return responder(pedidosDe(projetoId)); }

  /* ---------------- MAS: Mapa de Suprimentos ---------------- */
  function linhaMas(p, ped, pesos, alerta, empresas, eacPorCodigo) {
    var serv = ehServico(p), plano = p.plano || {}, real = p.real || {}, prev = p.previsao || {};
    var marcos = MARCOS_AQ.map(function (m) {
      return { id: m.id, nome: m.nome, fase: "aquisicao", lb: plano[m.id] || null, real: real[m.id] || null, previsao: real[m.id] ? null : prev[m.id] || null };
    });
    /* Sem pedido: LB e previsão dos marcos de fabricação estimadas entre o pedido e a entrega do plano */
    var lbPed = real.pedido || plano.pedido, lbEnt = plano.entrega, pvPed = real.pedido || prev.pedido || plano.pedido, pvEnt = prev.entrega || plano.entrega;
    MARCOS_FAB.forEach(function (m) {
      var c = { id: m.id, nome: m.nome, fase: "fabricacao" };
      if (serv) c.na = true;
      else if (ped) {
        var x = ped.marcos[m.idx];
        c.lb = x.lb; c.real = x.realizada || null; c.previsao = x.realizada ? null : x.previsao;
      } else {
        c.estimada = m.idx < 5;
        c.lb = m.idx === 5 ? lbEnt || null : lbPed && lbEnt ? entre(plano.pedido, lbEnt, PROP_FAB[m.idx]) : null;
        c.previsao = m.idx === 5 ? prev.entrega || null : (pvPed && pvEnt && (prev.pedido || prev.entrega) ? entre(pvPed, pvEnt, PROP_FAB[m.idx]) : null);
        c.real = null;
      }
      marcos.push(c);
    });
    var total = 0, feito = 0, planejado = 0;
    marcos.forEach(function (m) {
      var s = R.situacaoMarco(m, REF);
      m.situacao = s.chave; m.desvio = s.desvio; m.diasVencido = s.diasVencido || 0;
      m.data = m.real || m.previsao || m.lb || null;
      m.peso = m.na ? 0 : Number(pesos[m.id] || 0);
      total += m.peso;
      if (m.real) feito += m.peso;
      if (m.lb && m.lb <= REF) planejado += m.peso;
    });
    marcos.forEach(function (m) { m.pesoPct = total ? arred(m.peso / total * 100, 1) : 0; });
    var dataFolga = serv ? (real.pedido || prev.pedido || plano.pedido) : ped ? (ped.entrega || ped.marcos[5].previsao) : (prev.entrega || plano.entrega);
    var concluido = serv ? !!real.pedido : !!(ped && ped.entrega);
    var folgaDias = dataFolga && p.ros ? R.folga(p.ros, dataFolga) : null;
    var faixa = R.faixaFolga(folgaDias, alerta, concluido);
    var vencidos = marcos.filter(function (m) { return m.situacao === "vencido"; }).length;
    var situacao = concluido ? (serv ? "Contratado" : "Entregue") : faixa === "critico" ? "Crítico" : (faixa === "atencao" || vencidos) ? "Atenção" : "No prazo";
    var proximo = marcos.filter(function (m) { return !m.na && !m.real; })[0] || null;
    var eacItem = eacPorCodigo[p.projetoId + "|" + p.eacCodigo];
    return {
      id: p.id, projetoId: p.projetoId, projetoCodigo: (porId(M.projetos)[p.projetoId] || {}).codigo || "", codigo: p.codigo, escopo: p.escopo, tipo: p.tipo, disciplina: p.disciplina, modalidade: p.modalidade,
      lli: !!p.lli, servico: serv, etapa: p.etapa, eacCodigo: p.eacCodigo, eacDescricao: eacItem ? eacItem.descricao : "",
      compradorId: p.compradorId, fornecedorId: p.fornecedorId, fornecedor: p.fornecedorId ? (empresas[p.fornecedorId] || {}).nome || "" : "",
      estimativaCentavos: p.estimativaCentavos, adjudicadoCentavos: p.adjudicadoCentavos, valorCentavos: p.adjudicadoCentavos || p.estimativaCentavos,
      pedido: ped ? ped.numero : null, contrato: p.contratoRef || null, processo: (porCampo(M.processos, "pacoteId", p.id) || {}).numero || null,
      ros: p.ros, dataFolga: dataFolga, folgaDias: folgaDias, faixaFolga: faixa, concluido: concluido, situacao: situacao,
      etapaAtual: concluido ? situacao : proximo ? proximo.nome : p.etapa, proximoMarco: proximo ? { id: proximo.id, nome: proximo.nome, data: proximo.data } : null,
      marcos: marcos, marcosVencidos: vencidos, marcosComAtraso: marcos.filter(function (m) { return m.situacao === "atraso"; }).length,
      avancoReal: total ? arred(feito / total * 100, 1) : 0, avancoPrevisto: total ? arred(planejado / total * 100, 1) : 0
    };
  }
  function masDe(projetoId) {
    var pesos = P().suprimentos.pesosMarcos, alerta = P().suprimentos.folgaAlertaDias;
    var empresas = porId(M.empresas), eacPorCodigo = {};
    doProjeto(M.eac, projetoId).forEach(function (x) { eacPorCodigo[x.projetoId + "|" + x.codigo] = x; });
    var linhas = doProjeto(M.pacotes, projetoId).map(function (p) {
      return linhaMas(p, porCampo(doProjeto(M.pedidos, projetoId), "pacoteId", p.id), pesos, alerta, empresas, eacPorCodigo);
    }).sort(function (a, b) { return a.codigo.localeCompare(b.codigo, "pt-BR", { numeric: true }); });
    var valor = soma(linhas, "valorCentavos");
    var real = valor ? soma(linhas, function (l) { return l.valorCentavos * l.avancoReal; }) / valor : 0;
    var prev = valor ? soma(linhas, function (l) { return l.valorCentavos * l.avancoPrevisto; }) / valor : 0;
    var conta = function (f) { return linhas.filter(f).length; };
    return {
      referencia: REF, marcos: MARCOS_AQ.map(function (m) { return { id: m.id, nome: m.nome, fase: "aquisicao", peso: pesos[m.id] }; })
        .concat(MARCOS_FAB.map(function (m) { return { id: m.id, nome: m.nome, fase: "fabricacao", peso: pesos[m.id] }; })),
      linhas: linhas,
      resumo: {
        itens: linhas.length, concluidos: conta(function (l) { return l.concluido; }), noPrazo: conta(function (l) { return l.situacao === "No prazo"; }),
        atencao: conta(function (l) { return l.situacao === "Atenção"; }), criticos: conta(function (l) { return l.situacao === "Crítico"; }),
        marcosVencidos: soma(linhas, "marcosVencidos"), marcosComAtraso: soma(linhas, "marcosComAtraso"),
        avancoReal: arred(real, 1), avancoPrevisto: arred(prev, 1), indice: prev ? arred(real / prev, 2) : null
      },
      curva: curvaAvancoDe(linhas)
    };
  }
  /* Curva S de suprimentos: % acumulado ponderado pelo valor, por mês (LB, real até a referência e tendência) */
  function fimDoMes(m) { var d = new Date(Number(m.slice(0, 4)), Number(m.slice(5, 7)), 0); return m + "-" + String(d.getDate()).padStart(2, "0"); }
  function curvaAvancoDe(linhas) {
    var datas = [];
    linhas.forEach(function (l) { l.marcos.forEach(function (m) { if (!m.na) [m.lb, m.real, m.previsao].forEach(function (d) { if (d) datas.push(d); }); }); });
    if (!datas.length) return null;
    datas.sort();
    var meses = [], m = mesDe(datas[0]), ult = mesDe(datas[datas.length - 1]);
    while (m <= ult) { meses.push(m); var a = Number(m.slice(0, 4)), n = Number(m.slice(5, 7)) + 1; if (n > 12) { n = 1; a++; } m = a + "-" + String(n).padStart(2, "0"); }
    var valor = soma(linhas, "valorCentavos"), mesRef = mesDe(REF);
    if (!valor) return null;
    function pct(fim, campo) {
      return arred(soma(linhas, function (l) {
        var tot = soma(l.marcos, "peso"); if (!tot) return 0;
        return l.valorCentavos * soma(l.marcos.filter(function (x) { var d = campo(x); return d && d <= fim; }), "peso") / tot;
      }) / valor * 100, 1);
    }
    return {
      meses: meses, corte: mesRef,
      planejado: meses.map(function (mm) { return pct(fimDoMes(mm), function (x) { return x.lb; }); }),
      real: meses.map(function (mm) { return mm > mesRef ? null : pct(mm === mesRef ? REF : fimDoMes(mm), function (x) { return x.real; }); }),
      tendencia: meses.map(function (mm) {
        if (mm < mesRef) return null;
        if (mm === mesRef) return pct(REF, function (x) { return x.real; });
        return pct(fimDoMes(mm), function (x) { return x.real || x.previsao || x.lb; });
      })
    };
  }
  /* TODO: API GET /projetos/{id}/mas (mapa, resumo e curva de avanço calculados no servidor) */
  function mas(projetoId) { return responder(masDe(projetoId)); }

  /* ---------------- Plano de compras ---------------- */
  function pacotesDe(projetoId) {
    var linhas = porId(masDe(projetoId).linhas);
    return doProjeto(M.pacotes, projetoId).map(function (p) {
      var x = copia(p), l = linhas[p.id];
      x.linha = l;
      x.etapaIndice = etapaIdx(p.etapa);
      x.adjudicado = p.adjudicadoCentavos != null;
      x.desvioAdjudicacaoDias = R.diasEntre(p.plano.adjudicacao, p.real.adjudicacao || p.previsao.adjudicacao || (p.plano.adjudicacao < REF && !p.real.adjudicacao ? REF : null));
      x.savingCentavos = x.adjudicado ? p.estimativaCentavos - p.adjudicadoCentavos : null;
      x.fornecedor = nomeEmpresa(p.fornecedorId);
      x.eacDescricao = l ? l.eacDescricao : "";
      x.editavelLb = p.etapa === "Planejado";
      return x;
    }).sort(function (a, b) { return a.codigo.localeCompare(b.codigo, "pt-BR", { numeric: true }); });
  }
  /* TODO: API GET /projetos/{id}/pacotes */
  function listarPacotes(projetoId) { return responder(pacotesDe(projetoId)); }
  function prefixoPacote(projetoId) {
    var cods = doProjeto(M.pacotes, projetoId).map(function (p) { return p.codigo.replace(/\d+$/, ""); });
    return cods.length ? cods[cods.length - 1] : "PC-";
  }
  function proximoCodigoPacote(projetoId) {
    var pre = prefixoPacote(projetoId);
    var n = doProjeto(M.pacotes, projetoId).filter(function (p) { return p.codigo.indexOf(pre) === 0; })
      .reduce(function (m, p) { return Math.max(m, parseInt(p.codigo.slice(pre.length), 10) || 0); }, 0);
    return pre + ("0" + (n + 1)).slice(-2);
  }
  /* Validação e montagem de um pacote do plano (usada no modal e na importação) */
  function montarPacote(projetoId, d, existente) {
    var erros = [], proj = porId(M.projetos)[projetoId];
    var folhas = doProjeto(M.eac, projetoId).filter(function (x) { return x.nivel === 3; });
    var req = function (campo, v) { if (v == null || v === "" || (typeof v === "number" && isNaN(v))) erros.push({ campo: campo, msg: "Preencha este campo." }); };
    ["escopo", "tipo", "modalidade", "disciplina", "requisicao", "rfx", "adjudicacao", "pedido", "ros"].forEach(function (c) { req(c, d[c]); });
    if (!(d.estimativaCentavos > 0)) erros.push({ campo: "estimativa", msg: "Informe uma estimativa maior que zero." });
    if (!d.compradorId) erros.push({ campo: "comprador", msg: "Preencha este campo." });
    if (folhas.length) {
      if (!d.eacCodigo) erros.push({ campo: "eac", msg: "Todo pacote nasce vinculado a um item da EAC." });
      else if (!folhas.some(function (x) { return x.codigo === d.eacCodigo; })) erros.push({ campo: "eac", msg: "Item " + d.eacCodigo + " não é item de custo (nível 3) da EAC." });
    }
    var serv = TIPOS_CONTRATO.indexOf(d.tipo) >= 0;
    var seq = [["requisicao", d.requisicao], ["rfx", d.rfx], ["adjudicacao", d.adjudicacao], ["pedido", d.pedido]];
    for (var i = 1; i < seq.length; i++) {
      if (seq[i][1] && seq[i - 1][1] && seq[i][1] < seq[i - 1][1]) { erros.push({ campo: seq[i][0], msg: "As datas do plano precisam ser crescentes: requisição, RFx, adjudicação e pedido." }); break; }
    }
    var entrega = null;
    if (!serv) {
      if (!(d.prazoEntregaDias > 0)) erros.push({ campo: "prazo", msg: "Informe o prazo de entrega após o pedido." });
      else if (d.pedido) entrega = somarDiasIso(d.pedido, d.prazoEntregaDias);
    }
    var fimAq = serv ? d.pedido : entrega;
    if (fimAq && d.ros && fimAq > d.ros) {
      erros.push({ campo: "ros", msg: (serv ? "O contrato planejado " : "A entrega planejada ") + "fica depois do ROS: o plano já nasceria com folga negativa. Revise as datas." });
    }
    if (d.lli && d.antecipadoFid && !d.gateLli) erros.push({ campo: "gate", msg: "LLI contratado antes do gate de investimento exige a aprovação específica (gate LLI)." });
    if (d.emergencial && !(d.justificativaEmergencial && d.justificativaEmergencial.length >= 20)) erros.push({ campo: "justEmergencial", msg: "Justifique a compra emergencial (mínimo de 20 caracteres)." });
    if (existente && !existente.editavelLb && d.justificativa != null && String(d.justificativa).length < 10) erros.push({ campo: "justificativa", msg: "Justifique a alteração (mínimo de 10 caracteres)." });
    if (erros.length) return { erros: erros };
    var prop = somarDiasIso(d.rfx, 21);
    if (prop > d.adjudicacao) prop = entre(d.rfx, d.adjudicacao, 0.4);
    var eqc = somarDiasIso(d.adjudicacao, -7);
    if (eqc < prop) eqc = entre(prop, d.adjudicacao, 0.6);
    var plano = { requisicao: d.requisicao, rfx: d.rfx, propostas: prop, eqTecnica: entre(prop, eqc, 0.5), eqComercial: eqc, adjudicacao: d.adjudicacao, pedido: d.pedido };
    if (entrega) plano.entrega = entrega;
    return {
      pacote: {
        projetoId: projetoId, escopo: d.escopo, tipo: d.tipo, modalidade: d.modalidade, disciplina: d.disciplina, lli: !!d.lli,
        gateLli: d.lli && d.antecipadoFid ? { data: REF, referencia: d.gateLli } : null,
        eacCodigo: d.eacCodigo || null, estimativaCentavos: d.estimativaCentavos, compradorId: Number(d.compradorId), ros: d.ros,
        prazoEntregaDias: serv ? null : d.prazoEntregaDias, plano: plano,
        emergencial: !!d.emergencial, justificativaEmergencial: d.emergencial ? d.justificativaEmergencial : null
      }, projeto: proj
    };
  }
  /* TODO: API POST /projetos/{id}/pacotes | PUT /pacotes/{id} */
  function salvarPacote(projetoId, d, pacoteId) {
    var existente = pacoteId ? porId(M.pacotes)[pacoteId] : null;
    if (existente) existente = Object.assign(copia(existente), { editavelLb: existente.etapa === "Planejado" });
    if (existente && !existente.editavelLb) {
      /* Depois da requisição a LB do pacote fica congelada: só escopo, comprador, estimativa e ROS, com justificativa */
      var alvo = porId(M.pacotes)[pacoteId];
      if (!d.justificativa || d.justificativa.length < 10) return rejeitar({ campo: "justificativa", msg: "Justifique a alteração (mínimo de 10 caracteres)." });
      if (!(d.estimativaCentavos > 0)) return rejeitar({ campo: "estimativa", msg: "Informe uma estimativa maior que zero." });
      var mudou = [];
      ["escopo", "estimativaCentavos", "compradorId", "ros"].forEach(function (c) { if (d[c] != null && String(d[c]) !== String(alvo[c])) { mudou.push(c); alvo[c] = c === "compradorId" ? Number(d[c]) : d[c]; } });
      alvo.historico = (alvo.historico || []).concat([{ data: REF, porId: sessaoPessoa(), campos: mudou, justificativa: d.justificativa }]);
      persistir("pacotes");
      return responder(copia(alvo));
    }
    var r = montarPacote(projetoId, d, existente);
    if (r.erros) return rejeitar(r.erros);
    var lista = colecao("pacotes");
    if (existente) {
      var atual = porId(lista)[pacoteId];
      Object.keys(r.pacote).forEach(function (k) { atual[k] = r.pacote[k]; });
      atual.historico = (atual.historico || []).concat([{ data: REF, porId: sessaoPessoa(), campos: ["plano"], justificativa: d.justificativa || "Ajuste do plano antes da requisição." }]);
      persistir("pacotes");
      return responder(copia(atual));
    }
    var novo = r.pacote;
    novo.id = proximoId("pacotes"); novo.codigo = proximoCodigoPacote(projetoId);
    novo.real = {}; novo.previsao = {}; novo.etapa = "Planejado"; novo.fornecedorId = null; novo.adjudicadoCentavos = null;
    novo.primeiraPropostaCentavos = null; novo.propostasValidas = 0; novo.fornecedorUnico = false;
    novo.historico = [{ data: REF, porId: sessaoPessoa(), campos: ["criacao"], justificativa: "Pacote incluído no plano de compras." }];
    lista.push(novo);
    persistir("pacotes");
    return responder(copia(novo));
  }
  /* TODO: API POST /projetos/{id}/pacotes/importacao */
  function importarPacotes(projetoId, linhas) {
    var n = 0, falhas = [];
    linhas.forEach(function (l, i) {
      var r = montarPacote(projetoId, l, null);
      if (r.erros) { falhas.push("Linha " + (i + 2) + ": " + r.erros.map(function (e) { return e.msg || e; }).join(" ")); return; }
      var novo = r.pacote;
      novo.id = proximoId("pacotes"); novo.codigo = proximoCodigoPacote(projetoId);
      novo.real = {}; novo.previsao = {}; novo.etapa = "Planejado"; novo.fornecedorId = null; novo.adjudicadoCentavos = null;
      novo.primeiraPropostaCentavos = null; novo.propostasValidas = 0; novo.fornecedorUnico = false;
      novo.historico = [{ data: REF, porId: sessaoPessoa(), campos: ["importacao"], justificativa: "Importado do plano de compras (planilha)." }];
      colecao("pacotes").push(novo); n++;
    });
    if (n) persistir("pacotes");
    return responder({ importados: n, falhas: falhas });
  }

  /* ---------------- Processos de compra (RFx) ---------------- */
  function processoCalculado(p) {
    var pr = porCampo(M.processos, "pacoteId", p.id);
    var x = { pacote: copia(p), etapa: p.etapa, etapaIndice: etapaIdx(p.etapa), servico: ehServico(p) };
    x.pacote.fornecedor = nomeEmpresa(p.fornecedorId);
    x.processo = pr ? copia(pr) : null;
    var props = pr ? x.processo.propostas : [];
    var validas = props.filter(function (q) { return q.tecnicamenteAprovada === true; });
    var menor = validas.length ? Math.min.apply(null, validas.map(function (q) { return q.valorCentavos; })) : null;
    var pt = pr ? pr.pesoTecnico : 50, pc = pr ? pr.pesoComercial : 50;
    props.forEach(function (q) {
      var neg = pr.negociacoes.filter(function (n) { return n.fornecedor === q.fornecedor; }).pop();
      q.negociadoCentavos = neg ? neg.valorCentavos : null;
      q.notaComercial = q.tecnicamenteAprovada && menor ? arred(R.notaComercial(q.valorCentavos, menor), 1) : null;
      q.notaFinal = q.notaComercial != null ? arred(R.notaFinal(q.notaTecnica, q.notaComercial, pt, pc), 1) : null;
      var qual = q.fornecedorId ? qualificacaoDe(q.fornecedorId) : null;
      q.qualificacao = qual ? qual.situacao : q.fornecedorId ? "Sem qualificação" : "Não cadastrado";
    });
    var rank = props.filter(function (q) { return q.notaFinal != null; }).sort(function (a, b) { return b.notaFinal - a.notaFinal || a.valorCentavos - b.valorCentavos; });
    rank.forEach(function (q, i) { q.ranking = i + 1; });
    x.propostasRecebidas = props.length;
    x.propostasAprovadas = validas.length;
    x.tecnicaConcluida = x.etapaIndice >= etapaIdx("Equalização comercial");
    x.comercialConcluida = x.etapaIndice >= etapaIdx("Negociação");
    x.melhor = rank[0] || null;
    var valorRef = pr && pr.recomendacao ? pr.recomendacao.valorCentavos : x.melhor ? (x.melhor.negociadoCentavos || x.melhor.valorCentavos) : p.estimativaCentavos;
    x.alcada = R.alcada(valorRef, P().suprimentos.alcadas);
    x.valorReferencia = valorRef;
    x.comprador = p.compradorId;
    var eac = p.eacCodigo ? porCampo(doProjeto(M.eac, p.projetoId), "codigo", p.eacCodigo) : null;
    x.eac = eac && eac.nivel === 3 ? { codigo: eac.codigo, descricao: eac.descricao, saldo: eac.base + eac.remanejamento - eac.comprometido } :
      eac ? { codigo: eac.codigo, descricao: eac.descricao, saldo: null } : null;
    x.minimo = P().suprimentos.propostasMinimas;
    x.cicloDias = p.real.requisicao ? R.diasEntre(p.real.requisicao, p.real.pedido || REF) : null;
    return x;
  }
  function processosDe(projetoId) {
    return doProjeto(M.pacotes, projetoId).map(processoCalculado)
      .sort(function (a, b) { return a.pacote.codigo.localeCompare(b.pacote.codigo, "pt-BR", { numeric: true }); });
  }
  /* TODO: API GET /projetos/{id}/processos */
  function listarProcessos(projetoId) { return responder(processosDe(projetoId)); }

  function registrarHistorico(pr, etapa, texto) {
    pr.historico = (pr.historico || []).concat([{ data: REF, etapa: etapa, porId: sessaoPessoa(), texto: texto }]);
  }
  function proximoNumeroCt() {
    var n = (M.contratos || []).reduce(function (m, c) { var k = parseInt(String(c.numero).replace(/^CT-\d{4}-/, ""), 10); return isNaN(k) ? m : Math.max(m, k); }, 0);
    return "CT-" + REF.slice(0, 4) + "-" + ("00" + (n + 1)).slice(-3);
  }
  function proximoNumeroRfx(servico) {
    var pre = (servico ? "RFP-" : "RFQ-") + REF.slice(0, 4) + "-";
    var n = (M.processos || []).reduce(function (m, x) { var k = parseInt(String(x.numero).slice(pre.length), 10); return String(x.numero).indexOf(pre) === 0 && !isNaN(k) ? Math.max(m, k) : m; }, 0);
    return pre + ("00" + (n + 1)).slice(-3);
  }
  /* Fluxo do processo: cada ação valida a etapa, grava o marco realizado no pacote (MAS) e o histórico.
     TODO: API POST /pacotes/{id}/processo/{acao} (regras repetidas no servidor) */
  function acaoProcesso(pacoteId, acao, d) {
    d = d || {};
    var p = porId(M.pacotes)[pacoteId];
    if (!p) return rejeitar("Pacote não encontrado.");
    var pr = porCampo(M.processos, "pacoteId", p.id);
    var par = P().suprimentos, min = par.propostasMinimas;
    var etapa = p.etapa, data = d.data || REF;
    function exige(etapas) { return etapas.indexOf(etapa) >= 0 ? null : "Ação não disponível na etapa " + etapa + "."; }
    function avancar(nova, marco, texto) {
      p.etapa = nova;
      if (marco) { p.real[marco] = data; if (p.previsao) delete p.previsao[marco]; }
      if (pr) registrarHistorico(pr, nova, texto);
    }
    if (data > REF) return rejeitar({ campo: "data", msg: "A data não pode ser posterior à data de referência." });
    var erro;
    switch (acao) {
      case "requisicao":
        if ((erro = exige(["Planejado"]))) return rejeitar(erro);
        avancar("Requisição", "requisicao");
        p.requisicao = { data: data, porId: sessaoPessoa(), documento: d.documento || "", observacao: d.observacao || "" };
        break;
      case "rfx":
        if ((erro = exige(["Requisição"]))) return rejeitar(erro);
        var conv = (d.convidados || []).filter(Boolean);
        if (!d.fornecedorUnico && conv.length < min) return rejeitar({ campo: "convidados", msg: "Convide ao menos " + min + " fornecedores (ou registre fornecedor único com justificativa)." });
        if (d.fornecedorUnico && !(d.justificativaUnico && d.justificativaUnico.length >= 20)) return rejeitar({ campo: "justUnico", msg: "Fornecedor único exige justificativa (mínimo de 20 caracteres)." });
        var bloq = conv.filter(function (nm) { var e = porCampo(M.empresas, "nome", nm), q = e ? qualificacaoDe(e.id) : null; return q && q.situacao === "Bloqueado"; });
        if (bloq.length) return rejeitar({ campo: "convidados", msg: "Fornecedor bloqueado não pode ser convidado: " + bloq.join(", ") + "." });
        if (!d.dataLimite || d.dataLimite < data) return rejeitar({ campo: "dataLimite", msg: "O prazo das propostas deve ser igual ou posterior à emissão da RFx." });
        if (d.pesoTecnico + d.pesoComercial !== 100) return rejeitar({ campo: "pesoTecnico", msg: "Os pesos técnico e comercial devem somar 100." });
        pr = { id: proximoId("processos"), pacoteId: p.id, numero: proximoNumeroRfx(ehServico(p)), pesoTecnico: d.pesoTecnico, pesoComercial: d.pesoComercial,
          dataLimitePropostas: d.dataLimite, convidados: conv, propostas: [], negociacoes: [], recomendacao: null, aprovacao: null, historico: [] };
        if (d.fornecedorUnico) pr.fornecedorUnico = { justificativa: d.justificativaUnico, porId: sessaoPessoa(), data: data };
        colecao("processos").push(pr);
        p.fornecedorUnico = !!d.fornecedorUnico;
        p.previsao.propostas = d.dataLimite;
        avancar("RFx emitida", "rfx", pr.numero + " emitida para " + conv.length + " fornecedores.");
        break;
      case "proposta":
        if ((erro = exige(["RFx emitida", "Propostas recebidas"]))) return rejeitar(erro);
        if (!d.fornecedor) return rejeitar({ campo: "fornecedor", msg: "Preencha este campo." });
        if (pr.propostas.some(function (q) { return U_norm(q.fornecedor) === U_norm(d.fornecedor); })) return rejeitar({ campo: "fornecedor", msg: "Este fornecedor já tem proposta registrada." });
        var emp = porCampo(M.empresas, "nome", d.fornecedor), ql = emp ? qualificacaoDe(emp.id) : null;
        if (ql && ql.situacao === "Bloqueado") return rejeitar({ campo: "fornecedor", msg: "Fornecedor bloqueado: a proposta não pode ser aceita." });
        if (!(d.valorCentavos > 0)) return rejeitar({ campo: "valor", msg: "Informe o valor da proposta." });
        if (!(d.prazoDias > 0)) return rejeitar({ campo: "prazo", msg: "Informe o prazo de entrega em dias." });
        pr.propostas.push({ id: pr.propostas.reduce(function (m, q) { return Math.max(m, q.id); }, 0) + 1, fornecedor: d.fornecedor, fornecedorId: emp ? emp.id : null,
          recebida: data, valorCentavos: d.valorCentavos, prazoDias: d.prazoDias, validade: d.validade || null,
          notaTecnica: null, tecnicamenteAprovada: null, desvios: "", anexos: d.anexos || [] });
        if (etapa === "RFx emitida") avancar("Propostas recebidas", null, "Primeira proposta recebida.");
        registrarHistorico(pr, p.etapa, "Proposta de " + d.fornecedor + " registrada.");
        break;
      case "encerrarRecebimento":
        if ((erro = exige(["Propostas recebidas"]))) return rejeitar(erro);
        if (pr.propostas.length < min && !pr.fornecedorUnico) {
          if (!(d.justificativa && d.justificativa.length >= 20)) return rejeitar({ campo: "justificativa", msg: "Só " + pr.propostas.length + " proposta(s); o mínimo é " + min + ". Justifique para seguir (mínimo de 20 caracteres) ou aguarde novas propostas." });
          pr.excecaoMinimo = { etapa: "Propostas", justificativa: d.justificativa, porId: sessaoPessoa(), data: data };
        }
        avancar("Equalização técnica", "propostas", "Recebimento encerrado com " + pr.propostas.length + " propostas.");
        break;
      case "eqTecnica":
        if ((erro = exige(["Equalização técnica"]))) return rejeitar(erro);
        var av = d.avaliacoes || [];
        var faltam = pr.propostas.filter(function (q) { var a = av.filter(function (x) { return x.id === q.id; })[0]; return !a || a.notaTecnica == null || isNaN(a.notaTecnica); });
        if (faltam.length) return rejeitar("Dê a nota técnica de todas as propostas (faltam " + faltam.map(function (q) { return q.fornecedor; }).join(", ") + ").");
        av.forEach(function (a) {
          var q = pr.propostas.filter(function (x) { return x.id === a.id; })[0];
          if (!q) return;
          q.notaTecnica = a.notaTecnica; q.tecnicamenteAprovada = !!a.aprovada; q.desvios = a.desvios || q.desvios || "";
        });
        var aprovadas = pr.propostas.filter(function (q) { return q.tecnicamenteAprovada; }).length;
        if (!aprovadas) return rejeitar("Nenhuma proposta aprovada tecnicamente: reabra a RFx ou revise a especificação.");
        if (aprovadas < min && !pr.fornecedorUnico && !pr.excecaoMinimo) {
          if (!(d.justificativa && d.justificativa.length >= 20)) return rejeitar({ campo: "justificativa", msg: "Só " + aprovadas + " proposta(s) aprovada(s) tecnicamente; o mínimo é " + min + ". Justifique para seguir (mínimo de 20 caracteres)." });
          pr.excecaoMinimo = { etapa: "Equalização técnica", justificativa: d.justificativa, porId: sessaoPessoa(), data: data };
        }
        pr.parecerTecnico = { data: data, porId: d.responsavelId || sessaoPessoa(), texto: d.parecer || "" };
        p.propostasValidas = aprovadas;
        avancar("Equalização comercial", "eqTecnica", "Parecer técnico: " + aprovadas + " de " + pr.propostas.length + " propostas aprovadas.");
        break;
      case "eqComercial":
        if ((erro = exige(["Equalização comercial"]))) return rejeitar(erro);
        if (d.pesoTecnico != null) {
          if (d.pesoTecnico + d.pesoComercial !== 100) return rejeitar({ campo: "pesoTecnico", msg: "Os pesos técnico e comercial devem somar 100." });
          pr.pesoTecnico = d.pesoTecnico; pr.pesoComercial = d.pesoComercial;
        }
        var calc = processoCalculado(p);
        pr.mapaComercial = { data: data, pesoTecnico: pr.pesoTecnico, pesoComercial: pr.pesoComercial,
          ranking: calc.processo.propostas.filter(function (q) { return q.ranking; }).sort(function (a, b) { return a.ranking - b.ranking; })
            .map(function (q) { return { fornecedor: q.fornecedor, notaFinal: q.notaFinal, valorCentavos: q.valorCentavos }; }) };
        avancar("Negociação", "eqComercial", "Mapa comercial concluído; melhor nota final: " + (calc.melhor ? calc.melhor.fornecedor : "") + ".");
        break;
      case "negociacao":
        if ((erro = exige(["Negociação"]))) return rejeitar(erro);
        var qn = pr.propostas.filter(function (q) { return q.fornecedor === d.fornecedor && q.tecnicamenteAprovada; })[0];
        if (!qn) return rejeitar({ campo: "fornecedor", msg: "Negocie só com propostas aprovadas tecnicamente." });
        if (!(d.valorCentavos > 0)) return rejeitar({ campo: "valor", msg: "Informe o valor negociado." });
        if (d.valorCentavos > qn.valorCentavos) return rejeitar({ campo: "valor", msg: "O valor negociado não pode superar a proposta original." });
        pr.negociacoes.push({ data: data, fornecedor: d.fornecedor, valorCentavos: d.valorCentavos, observacao: d.observacao || "" });
        registrarHistorico(pr, p.etapa, "Negociação com " + d.fornecedor + " registrada.");
        break;
      case "recomendacao":
        if ((erro = exige(["Negociação"]))) return rejeitar(erro);
        var cr = processoCalculado(p);
        var qr = cr.processo.propostas.filter(function (q) { return q.fornecedor === d.fornecedor && q.tecnicamenteAprovada; })[0];
        if (!qr) return rejeitar({ campo: "fornecedor", msg: "Recomende só propostas aprovadas tecnicamente." });
        if (!qr.fornecedorId) return rejeitar({ campo: "fornecedor", msg: "Cadastre e qualifique " + d.fornecedor + " em Fornecedores antes de recomendar." });
        var qq = qualificacaoDe(qr.fornecedorId);
        if (qq && qq.situacao === "Bloqueado") return rejeitar({ campo: "fornecedor", msg: "Fornecedor bloqueado não pode ser adjudicado." });
        var precisaJust = qr.ranking !== 1 || !qq || qq.situacao !== "Qualificado";
        if (precisaJust && !(d.justificativa && d.justificativa.length >= 20)) {
          return rejeitar({ campo: "justificativa", msg: (qr.ranking !== 1 ? "A recomendação não é a melhor nota final. " : "Fornecedor não está qualificado. ") + "Justifique (mínimo de 20 caracteres)." });
        }
        var valor = d.valorCentavos || qr.negociadoCentavos || qr.valorCentavos;
        pr.recomendacao = { data: data, fornecedor: qr.fornecedor, fornecedorId: qr.fornecedorId, valorCentavos: valor, porId: sessaoPessoa(), justificativa: d.justificativa || "" };
        avancar("Recomendação de adjudicação", null, "Recomendada a " + qr.fornecedor + ".");
        break;
      case "devolver":
        if ((erro = exige(["Recomendação de adjudicação"]))) return rejeitar(erro);
        if (!(d.motivo && d.motivo.length >= 10)) return rejeitar({ campo: "motivo", msg: "Informe o motivo (mínimo de 10 caracteres)." });
        pr.recomendacao = null;
        avancar("Negociação", null, "Recomendação devolvida: " + d.motivo);
        break;
      case "aprovar":
        if ((erro = exige(["Recomendação de adjudicação"]))) return rejeitar(erro);
        var rec = pr.recomendacao;
        if (!d.aprovadorId) return rejeitar({ campo: "aprovador", msg: "Preencha este campo." });
        if (Number(d.aprovadorId) === rec.porId || Number(d.aprovadorId) === p.compradorId) return rejeitar({ campo: "aprovador", msg: "Quem aprova não pode ser o comprador nem quem recomendou (segregação de funções)." });
        var proj = porId(M.projetos)[p.projetoId];
        if (p.lli && proj && p.real.requisicao && p.real.requisicao < proj.inicio && !p.gateLli) return rejeitar("LLI contratado antes do gate de investimento: registre a aprovação específica do gate LLI no plano de compras.");
        var item = p.eacCodigo ? porCampo(doProjeto(M.eac, p.projetoId), "codigo", p.eacCodigo) : null;
        if (item && item.nivel === 3) {
          var saldo = item.base + item.remanejamento - item.comprometido;
          if (rec.valorCentavos > saldo) return rejeitar("O valor recomendado supera o saldo a comprometer do item " + item.codigo + " da EAC (" +
            (saldo / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) + "). Faça remanejamento ou SM antes de aprovar.");
        }
        var alc = R.alcada(rec.valorCentavos, par.alcadas);
        pr.aprovacao = { data: data, porId: Number(d.aprovadorId), alcada: alc.papel, parecer: d.parecer || "" };
        avancar("Aprovada", "adjudicacao", "Aprovada na alçada: " + alc.papel + ".");
        break;
      case "emitir":
        if ((erro = exige(["Aprovada"]))) return rejeitar(erro);
        var rc = pr.recomendacao, serv = ehServico(p);
        var original = pr.propostas.filter(function (q) { return q.fornecedor === rc.fornecedor; })[0];
        var ref = "";
        if (serv) {
          if (!d.termino || d.termino <= data) return rejeitar({ campo: "termino", msg: "Informe o término contratual (posterior à emissão)." });
          var ct = { id: proximoId("contratos"), projetoId: p.projetoId, numero: proximoNumeroCt(), empresaId: rc.fornecedorId, objeto: p.escopo, modalidade: p.modalidade,
            eacCodigo: p.eacCodigo, pacoteCompra: p.codigo, valorOriginalCentavos: rc.valorCentavos, inicio: d.inicio || p.ros || data, terminoOriginal: d.termino, terminoVigente: d.termino,
            gestorId: (porId(M.projetos)[p.projetoId] || {}).gerenteId || null, fiscalId: d.fiscalId ? Number(d.fiscalId) : null, retencaoPct: d.retencaoPct == null ? 5 : d.retencaoPct,
            prazoNotificacaoClaimDias: (P().claims || {}).prazoNotificacaoPadraoDias || 30, situacao: "Em execução" };
          colecao("contratos").push(ct); persistir("contratos");
          p.contratoRef = ct.numero; ref = ct.numero;
        } else {
          var prazo = d.prazoDias || (original ? original.prazoDias : null);
          if (!(prazo > 0)) return rejeitar({ campo: "prazo", msg: "Informe o prazo de entrega em dias." });
          var contratual = somarDiasIso(data, prazo);
          var numero = proximoCodigo("pedidos", "PED-" + REF.slice(0, 4) + "-");
          var marcos = NOMES_MARCOS_PEDIDO.map(function (nm, i) { var dt = entre(data, contratual, PROP_FAB[i]); return { nome: nm, lb: dt, previsao: dt, realizada: null }; });
          var novoPed = { id: proximoId("pedidos"), projetoId: p.projetoId, numero: numero, pacoteId: p.id, fornecedorId: rc.fornecedorId, descricao: p.escopo,
            valorCentavos: rc.valorCentavos, lli: !!p.lli, emissao: data, dataContratual: contratual, previsao: contratual, ros: p.ros, entrega: null, marcos: marcos, historico: [] };
          colecao("pedidos").push(novoPed);
          persistir("pedidos");
          /* Pedido que já nasce com folga negativa: alerta e ação de diligenciamento na Central */
          var fNovo = R.folga(p.ros, contratual);
          if (fNovo < 0) criarAcaoSuprimentos(novoPed, fNovo);
          p.pedidoRef = numero; ref = numero;
        }
        var itemEac = p.eacCodigo ? porCampo(doProjeto(M.eac, p.projetoId), "codigo", p.eacCodigo) : null;
        if (itemEac && itemEac.nivel === 3) { itemEac.comprometido += rc.valorCentavos; persistir("eac"); }
        p.fornecedorId = rc.fornecedorId; p.adjudicadoCentavos = rc.valorCentavos;
        p.primeiraPropostaCentavos = original ? original.valorCentavos : rc.valorCentavos;
        p.propostasValidas = pr.propostas.filter(function (q) { return q.tecnicamenteAprovada; }).length;
        avancar("Pedido/contrato emitido", "pedido", (serv ? "Contrato " : "Pedido ") + ref + " emitido; valor comprometido na EAC.");
        break;
      default:
        return rejeitar("Ação desconhecida: " + acao);
    }
    persistir("pacotes"); if (pr) persistir("processos");
    return responder(processoCalculado(p));
  }
  function U_norm(t) { return String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim(); }

  /* ---------------- Diligenciamento: atualização, recebimento e integrações ---------------- */
  function criarAcaoSuprimentos(ped, folgaDias) {
    var pac = porId(M.pacotes)[ped.pacoteId];
    var acao = { id: proximoId("acoes"), projetoId: ped.projetoId, origem: "Suprimentos", origemRef: ped.numero, grupo: "Diligenciamento", tipo: "Ação",
      assunto: "Recuperar a folga do pedido " + ped.numero,
      descricao: "Previsão de entrega em " + ped.previsao.split("-").reverse().join("/") + " passa a data necessária na obra (" + ped.ros.split("-").reverse().join("/") + "): folga de " + folgaDias + " dias.",
      solicitanteId: sessaoPessoa(), responsavelId: pac ? pac.compradorId : sessaoPessoa(), prevista: somarDiasIso(REF, 7), replanejada: null, conclusao: null };
    colecao("acoes").push(acao); persistir("acoes");
    return acao;
  }
  /* TODO: API PUT /pedidos/{id}/marcos/{indice} */
  function atualizarMarco(pedidoId, d) {
    var p = porId(M.pedidos)[pedidoId];
    if (!p) return rejeitar("Pedido não encontrado.");
    var i = Number(d.indice), m = p.marcos[i];
    if (!m) return rejeitar({ campo: "marco", msg: "Escolha o marco." });
    if (m.realizada) return rejeitar({ campo: "marco", msg: "Este marco já foi realizado." });
    if (i === 5 && d.realizada) return rejeitar({ campo: "realizada", msg: "A entrega é registrada em Registrar recebimento (conferência na obra)." });
    var alerta = P().suprimentos.folgaAlertaDias;
    var antes = pedidoCalculado(p, alerta);
    var texto = "";
    if (d.realizada) {
      if (d.realizada > REF) return rejeitar({ campo: "realizada", msg: "A data realizada não pode ser posterior à data de referência." });
      if (i > 0 && !p.marcos[i - 1].realizada) return rejeitar({ campo: "realizada", msg: "Registre antes o marco anterior (" + p.marcos[i - 1].nome + ")." });
      if (i > 0 && d.realizada < p.marcos[i - 1].realizada) return rejeitar({ campo: "realizada", msg: "A data não pode ser anterior à do marco anterior." });
      if (i === 3) {
        if (!d.resultado) return rejeitar({ campo: "resultado", msg: "Informe o resultado da inspeção em fábrica." });
        var ins = { id: proximoId("inspecoesQualidade"), projetoId: p.projetoId, codigo: proximoCodigo("inspecoesQualidade", "INS-" + REF.slice(0, 4) + "-"), itpId: null,
          ponto: "Inspeção em fábrica (FAT) " + p.numero, tipoPonto: "H", data: d.realizada, empresaId: p.fornecedorId, inspetorId: d.inspetorId ? Number(d.inspetorId) : sessaoPessoa(),
          resultado: d.resultado, origem: "Suprimentos", origemRef: p.numero };
        colecao("inspecoesQualidade").push(ins); persistir("inspecoesQualidade");
        if (d.resultado === "Reprovado") {
          if (!d.previsao || d.previsao < REF) return rejeitar({ campo: "previsao", msg: "FAT reprovado: informe a nova previsão do reteste." });
          texto = "FAT reprovado (" + ins.codigo + "); reteste previsto. ";
        } else { m.realizada = d.realizada; m.previsao = d.realizada; texto = "FAT aprovado (" + ins.codigo + "). "; }
      } else { m.realizada = d.realizada; m.previsao = d.realizada; texto = m.nome + " realizado. "; }
    }
    if (d.previsao && !m.realizada) {
      if (d.previsao < REF) return rejeitar({ campo: "previsao", msg: "A previsão não pode ser anterior à data de referência." });
      var delta = R.diasEntre(m.previsao, d.previsao);
      m.previsao = d.previsao;
      if (d.cascata !== false && delta) {
        for (var k = i + 1; k < p.marcos.length; k++) if (!p.marcos[k].realizada) p.marcos[k].previsao = somarDiasIso(p.marcos[k].previsao, delta);
      }
      for (var j = i + 1; j < p.marcos.length; j++) {
        if (!p.marcos[j].realizada && p.marcos[j].previsao < p.marcos[j - 1].previsao) p.marcos[j].previsao = p.marcos[j - 1].previsao;
      }
      texto += "Previsão de " + m.nome + " para " + d.previsao.split("-").reverse().join("/") + ". ";
    }
    p.previsao = p.marcos[5].previsao;
    p.historico = (p.historico || []).concat([{ data: REF, porId: sessaoPessoa(), texto: (texto + (d.comentario || "")).trim(), anexos: d.anexos || [] }]);
    persistir("pedidos");
    var depois = pedidoCalculado(p, alerta), acaoCriada = null;
    if (depois.critico && !depois.acaoAberta) acaoCriada = criarAcaoSuprimentos(p, depois.folgaDias);
    return responder({ pedido: pedidoCalculado(p, alerta), passouACritico: depois.critico && !antes.critico, acaoCriada: acaoCriada ? copia(acaoCriada) : null,
      riscoSugerido: depois.critico && !depois.risco });
  }
  /* Recebimento na obra: conferência, avarias e pendências. TODO: API POST /pedidos/{id}/recebimento */
  function registrarRecebimento(pedidoId, d) {
    var p = porId(M.pedidos)[pedidoId];
    if (!p) return rejeitar("Pedido não encontrado.");
    if (p.entrega) return rejeitar("Pedido já recebido.");
    if (!p.marcos[4].realizada) return rejeitar("Registre o embarque antes do recebimento na obra.");
    if (!d.data || d.data > REF) return rejeitar({ campo: "data", msg: "Informe a data do recebimento (até a data de referência)." });
    if (d.data < p.marcos[4].realizada) return rejeitar({ campo: "data", msg: "O recebimento não pode ser anterior ao embarque." });
    if (d.avarias && !(d.descricaoAvarias && d.descricaoAvarias.length >= 10)) return rejeitar({ campo: "descricaoAvarias", msg: "Descreva as avarias (mínimo de 10 caracteres)." });
    p.entrega = d.data; p.previsao = d.data;
    p.marcos[5].realizada = d.data; p.marcos[5].previsao = d.data;
    p.recebimento = { data: d.data, conferido: !!d.conferido, avarias: !!d.avarias, descricaoAvarias: d.descricaoAvarias || "", pendencias: d.pendencias || "", anexos: d.anexos || [], porId: sessaoPessoa() };
    p.historico = (p.historico || []).concat([{ data: REF, porId: sessaoPessoa(), texto: "Recebimento na obra registrado." + (d.avarias ? " Com avarias." : "") }]);
    persistir("pedidos");
    return responder(pedidoCalculado(p, P().suprimentos.folgaAlertaDias));
  }
  /* TODO: API POST /pedidos/{id}/acao-central */
  function gerarAcaoPedido(pedidoId) {
    var p = porId(M.pedidos)[pedidoId];
    if (!p) return rejeitar("Pedido não encontrado.");
    var c = pedidoCalculado(p, P().suprimentos.folgaAlertaDias);
    if (c.acaoAberta) return rejeitar("Já existe ação aberta na Central para " + p.numero + ".");
    return responder(copia(criarAcaoSuprimentos(Object.assign(copia(p), { previsao: c.previsao }), c.folgaDias)));
  }
  /* Risco sugerido pelo diligenciamento (05): entra "Em análise", com avaliação inerente e sem plano
     (o dono define o plano de resposta no registro). TODO: API POST /projetos/{id}/riscos */
  function registrarRiscoPedido(pedidoId, d) {
    var p = porId(M.pedidos)[pedidoId];
    if (!p) return rejeitar("Pedido não encontrado.");
    if (!d.titulo || d.titulo.length < 10) return rejeitar({ campo: "titulo", msg: "Descreva o risco (mínimo de 10 caracteres)." });
    if (!(d.p >= 1 && d.p <= 5 && d.i >= 1 && d.i <= 5)) return rejeitar("Probabilidade e impacto de 1 a 5.");
    var c = pedidoCalculado(p, P().suprimentos.folgaAlertaDias);
    var proj = porId(M.projetos)[p.projetoId] || {};
    var codigo = proximoCodigo("riscos", (proj.padraoRisco || "RSK") + "-");
    var score = d.p * d.i;
    var sev = R.severidade(score, P().riscos, false);
    var cad = R.cadenciaRisco(sev.id, P().riscos.cadenciaDias);
    colecao("riscos").push({ id: proximoId("riscos"), projetoId: p.projetoId, codigo: codigo, titulo: d.titulo, categoria: "Suprimentos", subcategoria: "Fornecedores", natureza: "Ameaça",
      donoId: d.donoId ? Number(d.donoId) : sessaoPessoa(), identificadoPorId: sessaoPessoa(), identificadoEm: REF, origemTipo: "Diligenciamento", origem: "Diligenciamento " + p.numero,
      causa: d.causa || "", consequencia: d.consequencia || "", descricao: "Folga de " + c.folgaDias + " dias em relação à data necessária na obra (ROS " + p.ros.split("-").reverse().join("/") + ").",
      gatilho: "Previsão de entrega depois do ROS.", inerente: { p: d.p, i: d.i, dimensoes: { prazo: d.i } }, residual: null, riscoVida: false,
      dimensao: "Prazo", impactoPrazoDias: Math.max(0, -c.folgaDias), impactoCustoCentavos: d.impactoCustoCentavos || 0,
      estrategia: null, plano: "", respostaProposta: d.plano || "", severidadeAlvo: null, prazoAlvo: null,
      cadenciaDias: cad, ultimaRevisao: REF, proximaRevisao: somarDiasIso(REF, cad), situacao: "Em análise",
      revisoes: [{ data: REF, porId: sessaoPessoa(), tipo: "inerente", situacaoApurada: "Avaliação inicial", de: null, para: score, p: d.p, i: d.i, gatilho: false, texto: "Avaliação inicial a partir do diligenciamento." }],
      historico: [{ quando: agoraIso(), porId: sessaoPessoa(), texto: "Risco criado pelo diligenciamento do pedido " + p.numero + ". Avaliação inerente " + score + " (P" + d.p + " x I" + d.i + ")." }] });
    p.riscoRef = codigo;
    persistir("riscos"); persistir("pedidos");
    return responder(codigo);
  }
  /* Pedidos exportados do ERP: uma linha por marco (previsão e/ou realizada). TODO: API POST /projetos/{id}/pedidos/importacao (integração ERP) */
  function importarPedidos(projetoId, linhas) {
    var n = 0, acoes = 0, falhas = [];
    var alerta = P().suprimentos.folgaAlertaDias;
    linhas.forEach(function (l, k) {
      var p = porCampo(doProjeto(M.pedidos, projetoId), "numero", l.numero);
      if (!p) { falhas.push("Linha " + (k + 2) + ": pedido " + l.numero + " não encontrado."); return; }
      var i = NOMES_MARCOS_PEDIDO.indexOf(l.marco), m = p.marcos[i];
      if (!m) { falhas.push("Linha " + (k + 2) + ": marco inválido."); return; }
      if (l.realizada) {
        if (l.realizada > REF) { falhas.push("Linha " + (k + 2) + ": data realizada futura."); return; }
        m.realizada = l.realizada; m.previsao = l.realizada;
        if (i === 5) { p.entrega = l.realizada; p.recebimento = p.recebimento || { data: l.realizada, conferido: false, avarias: false, pendencias: "Conferência pendente (importado do ERP)." }; }
      } else if (l.previsao) {
        if (l.previsao < REF) { falhas.push("Linha " + (k + 2) + ": previsão anterior à data de referência."); return; }
        m.previsao = l.previsao;
      }
      p.previsao = p.marcos[5].previsao;
      p.historico = (p.historico || []).concat([{ data: REF, porId: sessaoPessoa(), texto: "Atualizado pela importação do ERP (" + l.marco + ")." }]);
      n++;
      var c = pedidoCalculado(p, alerta);
      if (c.critico && !c.acaoAberta) { criarAcaoSuprimentos(p, c.folgaDias); acoes++; }
    });
    if (n) persistir("pedidos");
    return responder({ atualizados: n, acoesCriadas: acoes, falhas: falhas });
  }

  /* ---------------- Fornecedores: qualificação e desempenho ---------------- */
  function fornecedoresDe() {
    var empresas = (M.empresas || []).filter(function (e) { return e.tipo !== "Gerenciadora"; });
    var contratos = M.contratos || [], pedidos = M.pedidos || [];
    return empresas.map(function (e) {
      var q = qualificacaoDe(e.id);
      var x = { empresaId: e.id, nome: e.nome, tipo: e.tipo, cadastrado: !!q };
      if (q) Object.keys(q).forEach(function (k) { if (k !== "empresaId") x[k] = copia(q[k]); });
      x.situacao = q ? q.situacao : "Sem qualificação";
      x.categorias = x.categorias || [];
      x.documentos = (x.documentos || []).map(function (d) { d.vencido = !!d.validade && d.validade < REF; d.aVencer = !d.vencido && !!d.validade && R.diasEntre(REF, d.validade) <= 30; return d; });
      x.documentosEmDia = x.documentos.every(function (d) { return !d.vencido; });
      x.qualificacaoVencida = !!x.validadeQualificacao && x.validadeQualificacao < REF;
      x.qualificacaoAVencer = !!x.validadeQualificacao && !x.qualificacaoVencida && R.diasEntre(REF, x.validadeQualificacao) <= 90;
      var cts = contratos.filter(function (c) { return c.empresaId === e.id; });
      var aval = (M.avaliacoes || []).filter(function (a) { return cts.some(function (c) { return c.id === a.contratoId; }); })
        .map(function (a) { var y = avaliacaoCalculada(a); y.contrato = (porId(cts)[a.contratoId] || {}).numero; return y; })
        .sort(function (a, b) { return a.periodo < b.periodo ? -1 : 1; });
      x.avaliacoes = aval;
      x.ultimaAvaliacao = aval.length ? aval[aval.length - 1] : null;
      x.notaMedia = aval.length ? arred(soma(aval, "nota") / aval.length, 1) : null;
      var peds = pedidos.filter(function (p) { return p.fornecedorId === e.id; });
      var ent = peds.filter(function (p) { return p.entrega; });
      x.pedidos = peds.map(function (p) { return { numero: p.numero, descricao: p.descricao, valorCentavos: p.valorCentavos, entrega: p.entrega, dataContratual: p.dataContratual }; });
      x.contratos = cts.map(function (c) { return { numero: c.numero, objeto: c.objeto, valorCentavos: c.valorOriginalCentavos }; });
      x.valorContratadoCentavos = soma(peds, "valorCentavos") + soma(cts, "valorOriginalCentavos");
      x.entregas = ent.length;
      x.otdPct = ent.length ? arred(ent.filter(function (p) { return p.entrega <= p.dataContratual; }).length / ent.length * 100, 1) : null;
      x.participacoes = (M.processos || []).filter(function (pr) { return pr.propostas.some(function (q) { return q.fornecedorId === e.id; }); }).length;
      return x;
    }).sort(function (a, b) { return a.nome.localeCompare(b.nome, "pt-BR"); });
  }
  /* TODO: API GET /fornecedores (qualificação por empresa; desempenho de contratos e pedidos) */
  function listarFornecedores() { return responder(fornecedoresDe()); }
  var SITUACOES_FORN = ["Qualificado", "Em qualificação", "Restrito", "Bloqueado"];
  /* TODO: API PUT /fornecedores/{empresaId}/qualificacao */
  function salvarQualificacao(empresaId, d) {
    var q = qualificacaoDe(empresaId);
    if (SITUACOES_FORN.indexOf(d.situacao) < 0) return rejeitar({ campo: "situacao", msg: "Preencha este campo." });
    if (d.situacao === "Qualificado" && !d.validade) return rejeitar({ campo: "validade", msg: "Fornecedor qualificado precisa de validade da qualificação." });
    if (d.validade && d.validade < REF) return rejeitar({ campo: "validade", msg: "A validade não pode estar vencida." });
    if (!d.categorias || !d.categorias.length) return rejeitar({ campo: "categorias", msg: "Informe ao menos uma categoria." });
    var anterior = q ? q.situacao : null;
    if (anterior && anterior !== d.situacao && !(d.justificativa && d.justificativa.length >= 10)) return rejeitar({ campo: "justificativa", msg: "Justifique a mudança de situação (mínimo de 10 caracteres)." });
    if (["Restrito", "Bloqueado"].indexOf(d.situacao) >= 0 && !(d.observacao || d.justificativa)) return rejeitar({ campo: "observacao", msg: "Registre o motivo da restrição ou do bloqueio." });
    if (!q) { q = { empresaId: empresaId, documentos: [], historico: [] }; colecao("fornecedores").push(q); }
    q.situacao = d.situacao; q.validadeQualificacao = d.validade || null; q.categorias = d.categorias; q.observacao = d.observacao || "";
    if (d.documentos) q.documentos = d.documentos;
    if (anterior !== d.situacao) q.historico = (q.historico || []).concat([{ data: REF, de: anterior, para: d.situacao, porId: sessaoPessoa(), justificativa: d.justificativa || "Cadastro inicial." }]);
    persistir("fornecedores");
    return responder(copia(q));
  }
  /* TODO: API POST /empresas + /fornecedores */
  function novoFornecedor(d) {
    if (!d.nome || d.nome.length < 3) return rejeitar({ campo: "nome", msg: "Informe a razão social ou o nome fantasia." });
    if ((M.empresas || []).some(function (e) { return U_norm(e.nome) === U_norm(d.nome); })) return rejeitar({ campo: "nome", msg: "Já existe empresa com este nome." });
    var emp = { id: proximoId("empresas"), nome: d.nome, tipo: d.tipo || "Fornecedor" };
    colecao("empresas").push(emp); persistir("empresas");
    return salvarQualificacao(emp.id, { situacao: "Em qualificação", validade: null, categorias: d.categorias, observacao: d.observacao || "", justificativa: "Cadastro inicial.",
      documentos: (d.documentos || []) }).then(function () { return copia(emp); });
  }

  /* ---------------- Indicadores ---------------- */
  function mesesEntre(a, b) {
    var r = [], m = a;
    while (m <= b) { r.push(m); var y = Number(m.slice(0, 4)), n = Number(m.slice(5, 7)) + 1; if (n > 12) { n = 1; y++; } m = y + "-" + String(n).padStart(2, "0"); }
    return r;
  }
  function indicadoresSuprimentosDe(projetoId) {
    var pacs = doProjeto(M.pacotes, projetoId);
    var planejadosAteRef = pacs.filter(function (p) { return p.plano.adjudicacao <= REF; });
    var adjudicados = pacs.filter(function (p) { return p.adjudicadoCentavos != null; });
    var est = soma(adjudicados, "estimativaCentavos"), adj = soma(adjudicados, "adjudicadoCentavos");
    var comPrimeira = adjudicados.filter(function (p) { return p.primeiraPropostaCentavos; });
    var prim = soma(comPrimeira, "primeiraPropostaCentavos"), negoc = soma(comPrimeira, "adjudicadoCentavos");
    var peds = pedidosDe(projetoId);
    var entregues = peds.filter(function (p) { return p.entregue; });
    var ciclos = adjudicados.filter(function (p) { return p.real.pedido; }).map(function (p) { return R.diasEntre(p.real.requisicao, p.real.pedido); });
    var competitivos = pacs.filter(function (p) { return p.propostasValidas; });
    var eacCod = {};
    idsEscopo(projetoId).forEach(function (pid) { mapaControleProjeto(pid).itens.forEach(function (x) { eacCod[pid + "|" + x.codigo] = x; }); });
    var codigos = {};
    adjudicados.forEach(function (p) { var k = p.projetoId + "|" + p.eacCodigo; if (p.eacCodigo && eacCod[k]) codigos[k] = true; });
    var orcadoLigado = soma(Object.keys(codigos).map(function (c) { return eacCod[c]; }), "atual");
    var emerg = soma(adjudicados.filter(function (p) { return p.emergencial; }), "adjudicadoCentavos");
    /* Curva de contratação (pacotes adjudicados acumulados) e saving acumulado por mês */
    var datas = pacs.map(function (p) { return p.plano.adjudicacao; }).concat(adjudicados.map(function (p) { return p.real.adjudicacao; })).filter(Boolean).sort();
    var meses = datas.length ? mesesEntre(mesDe(datas[0]), mesDe(datas[datas.length - 1]) > mesDe(REF) ? mesDe(datas[datas.length - 1]) : mesDe(REF)) : [];
    var mesRef = mesDe(REF);
    return {
      pacotes: pacs.length, planejadosAteRef: planejadosAteRef.length,
      adjudicados: adjudicados.length, emContratacao: pacs.filter(function (p) { var i = etapaIdx(p.etapa); return i >= 1 && i <= 8; }).length,
      adjudicadosAteRef: planejadosAteRef.filter(function (p) { return p.adjudicadoCentavos != null; }).length,
      aderenciaPct: planejadosAteRef.length ? arred(planejadosAteRef.filter(function (p) { return p.adjudicadoCentavos != null; }).length / planejadosAteRef.length * 100, 1) : null,
      estimativaAdjudicadosCentavos: est, adjudicadoCentavos: adj,
      savingCentavos: est - adj, savingPct: est ? arred((est - adj) / est * 100, 1) : null,
      savingNegociacaoCentavos: prim - negoc, savingNegociacaoPct: prim ? arred((prim - negoc) / prim * 100, 1) : null,
      cicloMedioDias: ciclos.length ? Math.round(soma(ciclos, function (v) { return v; }) / ciclos.length) : null,
      entregas: entregues.length, entregasNoPrazo: entregues.filter(function (p) { return p.atrasoContratualDias <= 0; }).length,
      otdPct: entregues.length ? arred(entregues.filter(function (p) { return p.atrasoContratualDias <= 0; }).length / entregues.length * 100, 1) : null,
      pedidos: peds.length, pedidosCriticos: peds.filter(function (p) { return p.critico; }).length,
      lliCriticos: peds.filter(function (p) { return p.critico && p.lli; }).length,
      pedidosAtencao: peds.filter(function (p) { return p.faixaFolga === "atencao"; }).length,
      mediaPropostas: competitivos.length ? arred(soma(competitivos, "propostasValidas") / competitivos.length, 1) : null,
      fornecedorUnicoPct: competitivos.length ? arred(competitivos.filter(function (p) { return p.fornecedorUnico; }).length / competitivos.length * 100, 1) : null,
      emergenciaisCentavos: emerg, emergenciaisPct: adj ? arred(emerg / adj * 100, 1) : null,
      comprometidoOrcadoPct: orcadoLigado ? arred(adj / orcadoLigado * 100, 1) : null, orcadoLigadoCentavos: orcadoLigado,
      curvaContratacao: {
        meses: meses, corte: mesRef,
        planejado: meses.map(function (m) { return pacs.filter(function (p) { return mesDe(p.plano.adjudicacao) <= m; }).length; }),
        realizado: meses.map(function (m) { return m > mesRef ? null : adjudicados.filter(function (p) { return mesDe(p.real.adjudicacao) <= m; }).length; })
      },
      savingMensal: {
        meses: meses,
        acumulado: meses.map(function (m) { return m > mesRef ? null : soma(adjudicados.filter(function (p) { return mesDe(p.real.adjudicacao) <= m; }), function (p) { return p.estimativaCentavos - p.adjudicadoCentavos; }); }),
        negociacao: meses.map(function (m) { return m > mesRef ? null : soma(comPrimeira.filter(function (p) { return mesDe(p.real.adjudicacao) <= m; }), function (p) { return p.primeiraPropostaCentavos - p.adjudicadoCentavos; }); })
      },
      porEtapa: ETAPAS_SUP.map(function (e) { return { etapa: e, total: pacs.filter(function (p) { return p.etapa === e; }).length }; })
    };
  }
  /* TODO: API GET /projetos/{id}/indicadores-suprimentos */
  function indicadoresSuprimentos(projetoId) { return responder(indicadoresSuprimentosDe(projetoId)); }

  /* ======================================================================
     05 Gestão de Riscos
     Score, severidade, VME, cadência e pauta calculados aqui (nunca na tela).
     Ações dos riscos são registros da Central (origem Risco).
     ====================================================================== */
  var ESTRATEGIAS_RISCO = { "Ameaça": ["Mitigar", "Transferir", "Evitar", "Aceitar"], "Oportunidade": ["Explorar", "Melhorar", "Compartilhar", "Aceitar"] };
  var ORIGENS_RISCO = ["Manual", "Ata de reunião", "Workshop de riscos", "Lições aprendidas", "Auditoria"];
  var SITUACOES_RISCO = ["Identificado", "Em análise", "Em tratamento", "Monitorado", "Materializado", "Encerrado"];
  var FECHADAS_RISCO = ["Materializado", "Encerrado"];
  var MOTIVOS_ENCERRAMENTO = ["Não se materializou", "Materializado", "Superado", "Transferido", "Duplicado"];
  var MOTIVOS_EXCLUSAO = ["Registro em duplicidade", "Criado por engano", "Não é risco (é problema já ocorrido)", "Outro"];
  var APURACOES = ["Sem mudança", "Risco reduzido", "Risco agravado", "Risco materializado", "Risco superado"];
  var DIMENSOES_RISCO = [{ id: "prazo", nome: "Prazo" }, { id: "custo", nome: "Custo" }, { id: "escopo", nome: "Escopo e qualidade" },
    { id: "sms", nome: "SMS" }, { id: "imagem", nome: "Imagem" }, { id: "legal", nome: "Legal e contratual" }];
  var INSTRUMENTOS_RISCO = ["Seguro", "Cláusula contratual", "Subcontratação", "Hedge financeiro"];
  var PAPEIS = ["Visualizador", "Membro", "Gestor", "Admin"];

  function temPapel(minimo) { return PAPEIS.indexOf((M.sessao || {}).papelCodigo) >= PAPEIS.indexOf(minimo); }
  function riscoFechado(r) { return FECHADAS_RISCO.indexOf(r.situacao) >= 0; }
  function riscoPorCodigo(codigo) { return porCampo(M.riscos, "codigo", codigo); }
  function faixasRisco() { return P().riscos.escalas[P().riscos.escalaAtiva].faixas.slice().sort(function (a, b) { return a.minimo - b.minimo; }); }
  function faixaPorId(id) { return faixasRisco().filter(function (f) { return f.id === id; })[0] || null; }
  function nomeFaixa(id) { var f = faixaPorId(id); return f ? f.nome : (id === "critico" ? "Crítico" : id || ""); }
  function ordem(id) { return R.ordemFaixa(id, P().riscos); }
  function pctFaixa(p) { var f = P().riscos.probabilidades.filter(function (x) { return x.nivel === p; })[0]; return f ? f.mediaPct : null; }
  function moedaBr(c) { return ((c || 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); }
  function dataBr(iso) { return iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : ""; }
  function nomePessoa(id) { var x = porId(M.pessoas)[id]; return x ? x.nome : ""; }
  function historicoRisco(r, texto) {
    if (!r.historico) r.historico = historicoDerivado(r);
    r.historico.unshift({ quando: agoraIso(), porId: sessaoPessoa(), texto: texto });
  }
  /* Trilha montada quando o registro não tem histórico gravado (dados anteriores à trilha) */
  function historicoDerivado(r) {
    var h = [];
    (r.revisoes || []).forEach(function (v) {
      var t = v.tipo === "inerente" ? "Avaliação inerente registrada: " + v.para + " (P" + v.p + " x I" + v.i + ")."
        : v.tipo === "residual" ? "Avaliação residual " + (v.de == null ? "registrada: " + v.para : v.de === v.para ? "confirmada em " + v.para : "alterada de " + v.de + " para " + v.para) + ". Justificativa registrada."
        : v.de === v.para ? "Revisão registrada, sem mudança de severidade." : "Revisão registrada: score de " + v.de + " para " + v.para + ".";
      h.push({ quando: v.data + "T09:00", porId: v.porId, texto: t });
    });
    if (r.aprovacao && r.aprovacao.exigida && r.aprovacao.situacao === "Aprovado" && r.aprovacao.data) {
      h.push({ quando: r.aprovacao.data + "T15:00", porId: r.aprovacao.porId, texto: "Plano de resposta aprovado pela gerência do projeto (" + r.estrategia + ")." });
    }
    if (r.encerramento) h.push({ quando: r.encerramento.data + "T17:00", porId: r.encerramento.porId, texto: "Risco encerrado: " + r.encerramento.motivo + "." });
    h.push({ quando: r.identificadoEm + "T08:00", porId: r.identificadoPorId, texto: "Risco criado (origem: " + (r.origem || r.origemTipo || "Manual") + ")." });
    return h.sort(function (a, b) { return a.quando < b.quando ? 1 : a.quando > b.quando ? -1 : 0; });
  }

  /* Ações de riscos na Central, agrupadas pelo código do risco */
  function acoesPorRisco() {
    var g = {};
    acoesComStatus(function (a) { return a.origem === "Risco" && a.ehAcao; }).forEach(function (a) { (g[a.origemRef] = g[a.origemRef] || []).push(a); });
    return g;
  }

  function riscoCalculado(r, acoes) {
    var pr = P().riscos;
    var x = copia(r);
    var ine = r.inerente, res = r.residual, vig = res || ine;
    var proj = porId(M.projetos)[r.projetoId] || {};
    x.projetoCodigo = proj.codigo || "";
    x.categoriaCompleta = r.categoria + (r.subcategoria ? " > " + r.subcategoria : "");
    x.scoreInerente = ine ? ine.p * ine.i : null;
    x.scoreResidual = res ? res.p * res.i : null;
    x.sevInerente = ine ? R.severidade(x.scoreInerente, pr, r.riscoVida) : null;
    x.sevResidual = res ? R.severidade(x.scoreResidual, pr, r.riscoVida) : null;
    x.scoreAtual = vig ? vig.p * vig.i : null;
    x.sevAtual = res ? x.sevResidual : x.sevInerente;
    x.avaliado = !!ine;
    x.probabilidadePct = vig ? pctFaixa(vig.p) : null;
    x.vmeInerenteCentavos = ine ? R.vme(ine.p, r.impactoCustoCentavos, pr.probabilidades) : 0;
    x.vmeCentavos = vig ? R.vme(vig.p, r.impactoCustoCentavos, pr.probabilidades) : 0;
    x.ativo = !riscoFechado(r);
    x.revisaoVencida = x.ativo && !!r.proximaRevisao && r.proximaRevisao < REF;
    x.diasRevisao = r.proximaRevisao ? R.diasEntre(REF, r.proximaRevisao) : null;
    x.semRevisao = !r.revisoes || !r.revisoes.length;
    var lista = acoes || [];
    x.acoes = lista.length;
    x.acoesAbertas = lista.filter(function (a) { return a.status !== "concluida"; }).length;
    x.acoesAtrasadas = lista.filter(function (a) { return a.status === "atrasada"; }).length;
    x.cadenciaMaxDias = x.sevAtual ? R.cadenciaRisco(x.sevAtual.id, pr.cadenciaDias) : null;
    x.temPlano = !!(r.estrategia && r.plano);
    x.planoPendente = x.temPlano && !!(r.aprovacao && r.aprovacao.exigida && r.aprovacao.situacao !== "Aprovado");
    x.exigeAcao = x.temPlano && r.estrategia !== "Aceitar" && x.sevInerente && ordem(x.sevInerente.id) >= ordem("alto");
    x.semReducao = x.temPlano && !!res && r.natureza === "Ameaça" && x.scoreResidual >= x.scoreInerente;
    x.diasAlvo = r.prazoAlvo ? R.diasEntre(REF, r.prazoAlvo) : null;
    x.acimaAlvo = false;
    if (x.temPlano && r.severidadeAlvo && x.sevAtual) {
      x.acimaAlvo = r.natureza === "Oportunidade" ? ordem(x.sevAtual.id) < ordem(r.severidadeAlvo) : ordem(x.sevAtual.id) > ordem(r.severidadeAlvo);
    }
    x.nomeAlvo = r.severidadeAlvo ? nomeFaixa(r.severidadeAlvo) : "";
    var motivos = [];
    if (x.ativo) {
      if (r.situacao === "Identificado") motivos.push("Identificado sem avaliação");
      if (x.sevAtual && ordem(x.sevAtual.id) === faixasRisco().length - 1 && !x.temPlano && r.natureza === "Ameaça") motivos.push(x.sevAtual.nome + " sem plano de resposta");
      if (x.acimaAlvo && x.diasAlvo != null && x.diasAlvo <= pr.pautaDiasAntesDoPrazo) {
        motivos.push((r.natureza === "Oportunidade" ? "Abaixo" : "Acima") + " da severidade-alvo (" + x.nomeAlvo + ") " +
          (x.diasAlvo >= 0 ? "a " + x.diasAlvo + " dias do prazo" : "com prazo vencido há " + (-x.diasAlvo) + " dias"));
      }
      if (x.semReducao) motivos.push("Sem redução após o plano");
      if (x.planoPendente) motivos.push("Plano aguardando aprovação");
      if (x.revisaoVencida) motivos.push("Revisão vencida");
      if (r.gatilhoOcorridoEm) motivos.push("Gatilho ocorrido em " + dataBr(r.gatilhoOcorridoEm));
    }
    x.pauta = motivos;
    return x;
  }

  /* filtro: número (projetoId) ou { projetoId, incluirOcultos } */
  function riscosDe(filtro) {
    var f = typeof filtro === "object" && filtro ? filtro : { projetoId: filtro };
    var g = acoesPorRisco();
    return (M.riscos || []).filter(function (r) {
      if (r.oculto && !(f.incluirOcultos && temPapel("Admin"))) return false;
      if (f.projetoId != null && f.projetoId !== "" && String(r.projetoId) !== String(f.projetoId)) return false;
      return true;
    }).map(function (r) { return riscoCalculado(r, g[r.codigo]); });
  }
  /* TODO: API GET /projetos/{id}/riscos */
  function listarRiscos(filtro) { return responder(riscosDe(filtro)); }

  function resumoRiscosDe(filtro) {
    var lista = riscosDe(filtro).filter(function (r) { return r.ativo; });
    var fx = faixasRisco().slice().reverse();
    function conta(id) {
      var l = lista.filter(function (r) { return r.sevAtual && r.sevAtual.id === id; });
      return { total: l.length, ameacas: l.filter(function (r) { return r.natureza === "Ameaça"; }).length, oportunidades: l.filter(function (r) { return r.natureza === "Oportunidade"; }).length };
    }
    var ameacas = lista.filter(function (r) { return r.natureza === "Ameaça"; });
    var reducoes = ameacas.filter(function (r) { return r.scoreResidual != null && r.scoreInerente > 0; })
      .map(function (r) { return (r.scoreInerente - r.scoreResidual) / r.scoreInerente; });
    return {
      ativos: lista.length,
      topo: Object.assign({ id: fx[0].id, nome: fx[0].nome }, conta(fx[0].id)),
      segunda: fx[1] ? Object.assign({ id: fx[1].id, nome: fx[1].nome }, conta(fx[1].id)) : null,
      emTratamento: lista.filter(function (r) { return r.situacao === "Em tratamento"; }).length,
      revisaoVencida: lista.filter(function (r) { return r.revisaoVencida; }).length,
      semAvaliacao: lista.filter(function (r) { return !r.avaliado; }).length,
      pauta: lista.filter(function (r) { return r.pauta.length; }).length,
      exposicaoCentavos: soma(ameacas, "vmeCentavos"),
      reducaoMediaPct: reducoes.length ? arred(soma(reducoes, function (v) { return v; }) / reducoes.length * 100, 0) : null
    };
  }
  /* TODO: API GET /projetos/{id}/riscos/resumo */
  function resumoRiscos(filtro) { return responder(resumoRiscosDe(filtro)); }

  /* Faixas da escala ativa com o intervalo de score (legenda) */
  function legendaFaixas() {
    var f = faixasRisco();
    return f.map(function (x, k) { return { id: x.id, nome: x.nome, minimo: x.minimo, maximo: f[k + 1] ? f[k + 1].minimo - 1 : 25 }; });
  }

  /* Matriz 5x5: contagem por célula e movimentação inerente para residual.
     opcoes: { projetoId, avaliacao: "residual" | "inerente", natureza: "" | "Ameaça" | "Oportunidade" }
     Residual: riscos sem avaliação residual entram com a inerente. TODO: API GET /projetos/{id}/riscos/matriz */
  function matrizRiscos(opcoes) {
    var o = opcoes || {};
    var pr = P().riscos;
    var lista = riscosDe(o).filter(function (r) { return r.ativo && (!o.natureza || r.natureza === o.natureza); });
    var avaliados = lista.filter(function (r) { return r.avaliado; });
    var celulas = [];
    for (var p = 5; p >= 1; p--) {
      for (var i = 1; i <= 5; i++) {
        var nela = avaliados.filter(function (r) {
          var av = o.avaliacao === "inerente" ? r.inerente : (r.residual || r.inerente);
          return av.p === p && av.i === i;
        });
        celulas.push({ p: p, i: i, score: p * i, sev: R.severidade(p * i, pr, false),
          riscos: nela.map(function (r) { return { codigo: r.codigo, curto: r.codigo.slice(-4), titulo: r.titulo, natureza: r.natureza, riscoVida: r.riscoVida }; }) });
      }
    }
    var mov = avaliados.filter(function (r) { return r.temPlano && r.scoreResidual != null; }).map(function (r) {
      return { codigo: r.codigo, curto: r.codigo.replace(/^RSK-[A-Z]+-\d{4}-/, "RSK-"), titulo: r.titulo, natureza: r.natureza,
        de: r.scoreInerente, para: r.scoreResidual, sevDe: r.sevInerente, sevPara: r.sevResidual, semReducao: r.semReducao };
    }).sort(function (a, b) { return b.de - a.de || (b.de - b.para) - (a.de - a.para); });
    return responder({ celulas: celulas, total: avaliados.length, semAvaliacao: lista.length - avaliados.length,
      riscoVida: avaliados.filter(function (r) { return r.riscoVida; }).length, faixas: legendaFaixas(), movimentacao: mov,
      escala: pr.escalas[pr.escalaAtiva].nome, riscoVidaEhAlto: !!pr.escalas[pr.escalaAtiva].riscoVidaEhAlto });
  }

  /* Painel de riscos do projeto: KPIs, exposição por categoria (RBS), evolução e pauta de escalonamento.
     filtro: { projetoId }. TODO: API GET /projetos/{id}/riscos/painel */
  function painelRiscos(filtro) {
    var f = filtro || {};
    var lista = riscosDe(f).filter(function (r) { return r.ativo; });
    var ameacas = lista.filter(function (r) { return r.natureza === "Ameaça" && r.avaliado; });
    var cats = {};
    ameacas.forEach(function (r) {
      var c = cats[r.categoria] = cats[r.categoria] || { grupo: r.categoria, score: 0, riscos: 0, vmeCentavos: 0 };
      c.score += r.scoreAtual; c.riscos += 1; c.vmeCentavos += r.vmeCentavos;
    });
    var projetos = (M.projetos || []).filter(function (p) {
      return (f.projetoId == null || f.projetoId === "" || String(p.id) === String(f.projetoId));
    }).map(function (p) { return p.id; });
    var mesRef = mesDe(REF), meses = [];
    var d = new Date(mesRef + "-01T00:00:00");
    for (var k = 5; k >= 0; k--) { var x = new Date(d.getFullYear(), d.getMonth() - k, 1); meses.push(x.getFullYear() + "-" + String(x.getMonth() + 1).padStart(2, "0")); }
    var evolucao = meses.map(function (m) {
      if (m === mesRef) return { mes: m, score: soma(ameacas, "scoreAtual"), atual: true };
      return { mes: m, score: soma((M.riscosEvolucao || []).filter(function (e) { return e.mes === m && projetos.indexOf(e.projetoId) >= 0; }), "scoreResidual") };
    });
    var pauta = lista.filter(function (r) { return r.pauta.length; })
      .sort(function (a, b) { return (b.scoreAtual || 0) - (a.scoreAtual || 0) || b.pauta.length - a.pauta.length; });
    return responder({
      resumo: resumoRiscosDe(f), projetos: projetos.length,
      porCategoria: Object.keys(cats).map(function (k) { return cats[k]; }).sort(function (a, b) { return b.score - a.score || b.vmeCentavos - a.vmeCentavos; }),
      evolucao: evolucao, pauta: pauta
    });
  }

  /* Ficha: risco calculado, ações (Central), revisões, histórico e vínculos. TODO: API GET /riscos/{codigo} */
  function detalheRisco(codigo) {
    var r = riscoPorCodigo(codigo);
    if (!r || (r.oculto && !temPapel("Admin"))) return responder(null);
    var acoes = acoesComStatus(function (a) { return a.origem === "Risco" && a.origemRef === codigo; })
      .sort(function (a, b) { return (Number(a.item) || 0) - (Number(b.item) || 0); });
    var x = riscoCalculado(r, acoes.filter(function (a) { return a.ehAcao; }));
    x.listaAcoes = acoes;
    x.historico = r.historico ? copia(r.historico) : historicoDerivado(r);
    var ata = r.ataId ? porId(M.atas)[r.ataId] : null;
    x.ata = ata ? { id: ata.id, numero: ata.numero, revisao: ata.revisao, data: ata.data } : null;
    var sm = r.smRef ? porCampo(M.mudancas, "codigo", r.smRef) : null;
    x.sm = sm ? { codigo: sm.codigo, titulo: sm.titulo, situacao: sm.situacao } : null;
    var enc = r.encerramento || {};
    var lic = enc.licaoRef ? porCampo(M.licoes, "codigo", enc.licaoRef) : null;
    x.licao = lic ? { codigo: lic.codigo, titulo: lic.titulo, situacao: lic.situacao } : null;
    var smE = enc.smRef ? porCampo(M.mudancas, "codigo", enc.smRef) : null;
    x.smEncerramento = smE ? { codigo: smE.codigo, titulo: smE.titulo, situacao: smE.situacao } : null;
    x.cadenciaMaxima = copia(P().riscos.cadenciaDias);
    return responder(x);
  }

  /* Prévia do score (a tela só exibe). dimensoes opcionais: impacto mínimo = maior dimensão. TODO: API POST /riscos/score */
  function previaRisco(d) {
    var iMin = d.dimensoes ? R.impactoResultante(d.dimensoes) : 0;
    var i = Math.max(Number(d.i) || 0, iMin);
    var p = Number(d.p) || 0;
    if (!(p >= 1 && p <= 5 && i >= 1 && i <= 5)) return responder({ iMinimo: iMin, i: i || null, score: null, sev: null });
    var sev = R.severidade(p * i, P().riscos, !!d.riscoVida);
    return responder({ iMinimo: iMin, i: i, score: p * i, sev: sev, pct: pctFaixa(p), cadenciaDias: R.cadenciaRisco(sev.id, P().riscos.cadenciaDias),
      vmeCentavos: d.impactoCustoCentavos != null ? R.vme(p, d.impactoCustoCentavos, P().riscos.probabilidades) : null });
  }

  function categoriaValida(grupo, nome) {
    return (M.riscoCategorias || []).some(function (c) { return c.grupo === grupo && (!nome || c.nome === nome); });
  }
  function errosTexto(d, campo, rotulo, min, max) {
    var t = String(d[campo] || "").trim();
    if (!t) return [{ campo: campo, msg: rotulo + " é obrigatório." }];
    if (min && t.length < min) return [{ campo: campo, msg: rotulo + ": mínimo de " + min + " caracteres." }];
    if (max && t.length > max) return [{ campo: campo, msg: rotulo + ": máximo de " + max + " caracteres." }];
    return [];
  }

  /* Novo risco ou edição (Identificação). Número reservado aqui, na gravação (RG-10, RT-02).
     TODO: API POST /projetos/{id}/riscos | PUT /riscos/{codigo} */
  function salvarRisco(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar riscos.");
    var r = d.codigo ? riscoPorCodigo(d.codigo) : null;
    if (d.codigo && !r) return rejeitar("Risco não encontrado.");
    if (r && riscoFechado(r)) return rejeitar("Risco encerrado não pode ser editado. Reabra o risco antes.");
    var e = [];
    if (["Ameaça", "Oportunidade"].indexOf(d.natureza) < 0) e.push({ campo: "natureza", msg: "Escolha a natureza." });
    var cat = String(d.categoria || "").split(" > ");
    if (!d.categoria || !categoriaValida(cat[0], cat[1])) e.push({ campo: "categoria", msg: "Escolha a categoria da RBS." });
    e = e.concat(errosTexto(d, "causa", "Causa", 10, 255), errosTexto(d, "titulo", "Evento", 10, 255), errosTexto(d, "consequencia", "Consequência", 10, 255));
    if (!d.donoId || !porId(M.pessoas)[d.donoId]) e.push({ campo: "donoId", msg: "O dono precisa ser um convidado ativo do cliente do projeto." });
    if (!d.identificadoEm) e.push({ campo: "identificadoEm", msg: "Informe a data de identificação." });
    else if (d.identificadoEm > REF) e.push({ campo: "identificadoEm", msg: "A data de identificação não pode ser futura." });
    var sistema = r && ORIGENS_RISCO.indexOf(r.origemTipo) < 0;
    if (!sistema && ORIGENS_RISCO.indexOf(d.origemTipo) < 0) e.push({ campo: "origemTipo", msg: "Escolha a origem." });
    var ata = null;
    if (!sistema && d.origemTipo === "Ata de reunião") {
      ata = d.ataId ? porId(M.atas)[d.ataId] : null;
      if (!ata) e.push({ campo: "ataId", msg: "Escolha a ata de origem." });
    }
    if (d.gatilho && d.gatilho.length > 255) e.push({ campo: "gatilho", msg: "Gatilho: máximo de 255 caracteres." });
    if (r && d.natureza !== r.natureza && r.estrategia) e.push({ campo: "natureza", msg: "Risco com plano de resposta: a natureza define as estratégias e não pode ser trocada. Encerre como duplicado e registre um novo." });
    var projetoId = r ? r.projetoId : Number(d.projetoId);
    var proj = porId(M.projetos)[projetoId];
    if (!proj) e.push("Projeto não encontrado.");
    if (e.length) return Promise.reject({ erros: e });

    var avisos = [];
    var igual = (M.riscos || []).filter(function (x) { return x.projetoId === projetoId && !x.oculto && x !== r && U_norm(x.titulo) === U_norm(d.titulo); })[0];
    if (igual) avisos.push("Já existe risco com o mesmo evento no projeto (" + igual.codigo + "). Verifique se não é duplicidade.");
    var novo = !r;
    if (novo) {
      r = { id: proximoId("riscos"), projetoId: projetoId, codigo: proximoCodigo("riscos", (proj.padraoRisco || "RSK") + "-"),
        identificadoPorId: sessaoPessoa(), inerente: null, residual: null, riscoVida: false, dimensao: null, impactoPrazoDias: 0, impactoCustoCentavos: 0,
        estrategia: null, plano: "", severidadeAlvo: null, prazoAlvo: null, cadenciaDias: null, ultimaRevisao: null, proximaRevisao: null,
        situacao: "Identificado", revisoes: [], historico: [] };
    }
    var antes = novo ? null : copia(r);
    r.natureza = d.natureza; r.categoria = cat[0]; r.subcategoria = cat[1] || "";
    r.causa = d.causa.trim(); r.titulo = d.titulo.trim(); r.consequencia = d.consequencia.trim();
    r.descricao = d.descricao ? d.descricao.trim() : null; r.gatilho = d.gatilho ? d.gatilho.trim() : null;   /* RT-01: vazio vira null */
    r.donoId = Number(d.donoId); r.identificadoEm = d.identificadoEm;
    if (!sistema) {
      r.origemTipo = d.origemTipo; r.ataId = ata ? ata.id : null;
      r.origem = ata ? "Ata " + ata.numero : d.origemTipo;
    }
    if (novo) {
      colecao("riscos").push(r);
      r.historico.push({ quando: agoraIso(), porId: sessaoPessoa(), texto: "Risco criado" + (ata ? " a partir da ata " + ata.numero : " (origem: " + r.origem + ")") + "." });
    } else {
      var mud = [];
      if (antes.donoId !== r.donoId) mud.push("dono de " + nomePessoa(antes.donoId) + " para " + nomePessoa(r.donoId));
      if (antes.titulo !== r.titulo) mud.push("evento");
      if (antes.causa !== r.causa) mud.push("causa");
      if (antes.consequencia !== r.consequencia) mud.push("consequência");
      if (antes.categoria !== r.categoria || antes.subcategoria !== r.subcategoria) mud.push("categoria para " + r.categoria + " > " + r.subcategoria);
      if (antes.natureza !== r.natureza) mud.push("natureza para " + r.natureza);
      historicoRisco(r, "Identificação alterada" + (mud.length ? ": " + mud.join(", ") : "") + ".");
    }
    persistir("riscos");
    return responder({ codigo: r.codigo, avisos: avisos, novo: novo });
  }

  /* Avaliação inerente ou residual (único lugar onde P e I mudam, além da revisão periódica).
     TODO: API PUT /riscos/{codigo}/avaliacao */
  function avaliarRisco(codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite avaliar riscos.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (riscoFechado(r)) return rejeitar("Risco encerrado não pode ser reavaliado.");
    var pr = P().riscos, e = [];
    var tipo = d.tipo === "residual" ? "residual" : "inerente";
    if (tipo === "residual" && !(r.estrategia && r.plano)) return rejeitar("A avaliação residual só é habilitada depois que o plano de resposta existir.");
    var dims = {};
    DIMENSOES_RISCO.forEach(function (x) { var v = Number((d.dimensoes || {})[x.id]) || 0; if (v >= 1 && v <= 5) dims[x.id] = v; });
    var iMin = R.impactoResultante(dims);
    var p = Number(d.p), i = Number(d.i);
    if (!(p >= 1 && p <= 5)) e.push({ campo: "p", msg: "Escolha a probabilidade." });
    if (!iMin) e.push({ campo: "dimensoes", msg: "Avalie ao menos uma dimensão de impacto." });
    if (!(i >= 1 && i <= 5)) e.push({ campo: "i", msg: "Escolha o impacto." });
    else if (i < iMin) e.push({ campo: "i", msg: "O impacto resultante não pode ser menor que a maior dimensão (" + iMin + ")." });
    if (d.impactoCustoCentavos != null && (!(d.impactoCustoCentavos >= 0) || Math.round(d.impactoCustoCentavos) !== d.impactoCustoCentavos)) e.push({ campo: "impactoCustoCentavos", msg: "Valor inválido." });
    if (d.impactoPrazoDias != null && !(d.impactoPrazoDias >= 0)) e.push({ campo: "impactoPrazoDias", msg: "Informe dias (zero ou mais)." });
    if (e.length) return Promise.reject({ erros: e });
    var score = p * i, sev = R.severidade(score, pr, !!d.riscoVida);
    var anterior = tipo === "residual" ? (r.residual || r.inerente) : r.inerente;
    var scoreAnt = anterior ? anterior.p * anterior.i : null;
    var sevAnt = anterior ? R.severidade(scoreAnt, pr, !!r.riscoVida) : null;
    var mudouSev = !!sevAnt && sevAnt.id !== sev.id;
    if (tipo === "residual" && r.natureza === "Ameaça" && r.inerente && score > r.inerente.p * r.inerente.i) {
      return rejeitar({ campo: "p", msg: "Para ameaças, o residual não pode superar o inerente. Se a resposta criou nova exposição, registre um risco secundário." });
    }
    var just = String(d.justificativa || "").trim();
    if ((mudouSev || (anterior && scoreAnt !== score)) && just.length < 10) return rejeitar({ campo: "justificativa", msg: "Justifique a avaliação (obrigatória quando o score ou a severidade mudam; mínimo de 10 caracteres)." });
    var maior = DIMENSOES_RISCO.filter(function (x) { return dims[x.id] === iMin; })[0];
    r[tipo] = { p: p, i: i, dimensoes: dims };
    r.riscoVida = !!d.riscoVida;
    if (maior) r.dimensao = maior.nome;
    if (d.impactoPrazoDias != null) r.impactoPrazoDias = Math.round(d.impactoPrazoDias);
    if (d.impactoCustoCentavos != null) r.impactoCustoCentavos = d.impactoCustoCentavos;
    var apurada = !anterior ? "Avaliação inicial" : score < scoreAnt ? "Risco reduzido" : score > scoreAnt ? "Risco agravado" : "Sem mudança";
    r.revisoes = r.revisoes || [];
    r.revisoes.unshift({ data: REF, porId: sessaoPessoa(), tipo: tipo, situacaoApurada: apurada, de: scoreAnt, para: score, p: p, i: i, gatilho: false,
      texto: just || (tipo === "inerente" ? "Avaliação inicial." : "Avaliação residual.") });
    var vig = r.residual || r.inerente;
    var sevVig = R.severidade(vig.p * vig.i, pr, r.riscoVida);
    r.cadenciaDias = R.cadenciaRisco(sevVig.id, pr.cadenciaDias);          /* RG-19 */
    r.ultimaRevisao = REF; r.proximaRevisao = somarDiasIso(REF, r.cadenciaDias);
    r.gatilhoOcorridoEm = null;
    if (r.situacao === "Identificado") r.situacao = "Em análise";
    var acoes = acoesComStatus(function (a) { return a.origem === "Risco" && a.origemRef === r.codigo && a.ehAcao; });
    var pend = r.aprovacao && r.aprovacao.exigida && r.aprovacao.situacao !== "Aprovado";
    if (tipo === "residual" && r.situacao === "Em tratamento" && !pend && acoes.length && acoes.every(function (a) { return a.status === "concluida"; })) r.situacao = "Monitorado";  /* RG-24 */
    historicoRisco(r, "Avaliação " + tipo + (anterior ? (scoreAnt === score ? " confirmada em " + score : " alterada de " + scoreAnt + " para " + score) : " registrada: " + score) +
      " (P" + p + " x I" + i + ", " + sev.nome + ")." + (just ? " Justificativa registrada." : "") + " Próxima revisão em " + dataBr(r.proximaRevisao) + ".");
    persistir("riscos");
    var topo = ordem(sev.id) === faixasRisco().length - 1;
    return responder({ codigo: r.codigo, score: score, sev: sev, exigePlano: topo && !(r.estrategia && r.plano) && r.natureza === "Ameaça",
      alertaGestor: topo && r.natureza === "Ameaça" && (!sevAnt || sevAnt.id !== sev.id), situacao: r.situacao });
  }

  /* Ação do risco: registro da Central com origem Risco (RG-25: herda o projeto). TODO: API POST /riscos/{codigo}/acoes */
  function validarAcaoRisco(d) {
    var e = errosTexto(d, "assunto", "Assunto", 5, 255);
    if (!d.solicitanteId || !porId(M.pessoas)[d.solicitanteId]) e.push({ campo: "solicitanteId", msg: "Escolha o solicitante." });
    if (!d.responsavelId || !porId(M.pessoas)[d.responsavelId]) e.push({ campo: "responsavelId", msg: "O responsável precisa ser um convidado ativo." });
    if (!d.prevista) e.push({ campo: "prevista", msg: "Informe a data prevista." });
    else if (d.prevista < REF) e.push({ campo: "prevista", msg: "A data prevista não pode ser anterior à data de referência." });
    return e;
  }
  function criarAcaoRisco(r, d, grupo) {
    var itens = (M.acoes || []).filter(function (a) { return a.origem === "Risco" && a.origemRef === r.codigo; })
      .map(function (a) { return Number(a.item) || 0; });
    var acao = { id: proximoId("acoes"), projetoId: r.projetoId, origem: "Risco", origemRef: r.codigo, item: String((itens.length ? Math.max.apply(null, itens) : 0) + 1),
      grupo: grupo || "Plano de resposta", tipo: "Ação", assunto: d.assunto.trim(), descricao: d.descricao ? d.descricao.trim() : "",
      solicitanteId: Number(d.solicitanteId || sessaoPessoa()), responsavelId: Number(d.responsavelId), prevista: d.prevista, replanejada: null, conclusao: null,
      contribuicao: { probabilidade: !!(d.contribuicao && d.contribuicao.probabilidade), impacto: !!(d.contribuicao && d.contribuicao.impacto) } };
    colecao("acoes").push(acao); persistir("acoes");
    return acao;
  }
  function novaAcaoRisco(codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite criar ações.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (riscoFechado(r)) return rejeitar("Risco encerrado não recebe novas ações.");
    var e = validarAcaoRisco(d);
    if (e.length) return Promise.reject({ erros: e });
    var a = criarAcaoRisco(r, d);
    if (r.situacao === "Monitorado" && r.estrategia) r.situacao = "Em tratamento";
    historicoRisco(r, "Ação " + a.item + " criada (" + a.assunto + "), responsável " + nomePessoa(a.responsavelId) + ", prevista para " + dataBr(a.prevista) + ".");
    persistir("riscos");
    return responder(copia(a));
  }

  /* Plano de resposta (RG-21 a RG-24). TODO: API PUT /riscos/{codigo}/plano */
  function salvarPlanoRisco(codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite alterar o plano de resposta.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (riscoFechado(r)) return rejeitar("Risco encerrado não pode ter o plano alterado.");
    if (!r.inerente) return rejeitar("Avalie o risco (inerente) antes de definir o plano de resposta.");
    var pr = P().riscos, e = [];
    var sevIne = R.severidade(r.inerente.p * r.inerente.i, pr, r.riscoVida);
    if ((ESTRATEGIAS_RISCO[r.natureza] || []).indexOf(d.estrategia) < 0) e.push({ campo: "estrategia", msg: "Escolha a estratégia." });
    var plano = String(d.plano || "").trim();
    if (!plano) e.push({ campo: "plano", msg: "Descreva o plano de resposta." });
    else if (d.estrategia === "Evitar" && plano.length < 80) e.push({ campo: "plano", msg: "Estratégia Evitar: descreva a mudança de escopo ou de solução (mínimo de 80 caracteres)." });
    else if (d.estrategia === "Aceitar" && plano.length < 30) e.push({ campo: "plano", msg: "Estratégia Aceitar: justifique a aceitação no plano (mínimo de 30 caracteres)." });
    else if (plano.length < 20) e.push({ campo: "plano", msg: "Detalhe o plano (mínimo de 20 caracteres)." });
    if (d.estrategia === "Transferir" && INSTRUMENTOS_RISCO.indexOf(d.instrumento) < 0) e.push({ campo: "instrumento", msg: "Indique o instrumento da transferência." });
    if (d.estrategia === "Evitar" && !d.smRef) e.push({ campo: "smRef", msg: "Evitar exige registro da mudança de escopo ou de solução (SM)." });
    if (d.smRef && d.smRef !== "nova" && !porCampo(doProjeto(M.mudancas, r.projetoId), "codigo", d.smRef)) e.push({ campo: "smRef", msg: "SM não encontrada no projeto." });
    if (!faixaPorId(d.severidadeAlvo)) e.push({ campo: "severidadeAlvo", msg: "Escolha a severidade-alvo." });
    else if (r.natureza === "Ameaça" && ordem(d.severidadeAlvo) > ordem(sevIne.id)) e.push({ campo: "severidadeAlvo", msg: "A severidade-alvo não pode ser maior que a inerente (" + sevIne.nome + ")." });
    if (!d.prazoAlvo) e.push({ campo: "prazoAlvo", msg: "Informe o prazo para atingir o alvo." });
    else if (d.prazoAlvo <= REF && d.prazoAlvo !== r.prazoAlvo) e.push({ campo: "prazoAlvo", msg: "O prazo para o alvo deve ser uma data futura." });
    if (d.custoRespostaCentavos != null && !(d.custoRespostaCentavos >= 0)) e.push({ campo: "custoRespostaCentavos", msg: "Valor inválido." });
    if (!d.responsavelPlanoId || !porId(M.pessoas)[d.responsavelPlanoId]) e.push({ campo: "responsavelPlanoId", msg: "Escolha o responsável pelo plano." });
    var acoes = (M.acoes || []).filter(function (a) { return a.origem === "Risco" && a.origemRef === r.codigo; });
    var novaAcao = d.novaAcao && d.novaAcao.assunto ? d.novaAcao : null;
    if (novaAcao) validarAcaoRisco(Object.assign({ solicitanteId: sessaoPessoa() }, novaAcao)).forEach(function (x) { e.push({ campo: "acao_" + x.campo, msg: x.msg }); });
    if (d.estrategia && d.estrategia !== "Aceitar" && ordem(sevIne.id) >= ordem("alto") && !acoes.length && !novaAcao) {
      e.push({ campo: "acao_assunto", msg: "Risco " + sevIne.nome + " exige pelo menos uma ação vinculada. Registre a primeira em Nova ação." });
    }
    if (e.length) return Promise.reject({ erros: e });

    var topo = ordem(sevIne.id) === faixasRisco().length - 1;
    var exigida = topo || !!d.exigirAprovacao;
    var mudouConteudo = r.estrategia !== d.estrategia || String(r.plano || "").trim() !== plano || r.severidadeAlvo !== d.severidadeAlvo || r.prazoAlvo !== d.prazoAlvo;
    var primeiro = !(r.estrategia && r.plano);
    r.estrategia = d.estrategia; r.plano = plano; r.severidadeAlvo = d.severidadeAlvo; r.prazoAlvo = d.prazoAlvo;
    r.custoRespostaCentavos = d.custoRespostaCentavos == null ? null : d.custoRespostaCentavos;
    r.responsavelPlanoId = Number(d.responsavelPlanoId);
    r.instrumento = d.estrategia === "Transferir" ? d.instrumento : null;
    var smNova = d.smRef === "nova";
    r.smRef = d.smRef && !smNova ? d.smRef : (smNova ? null : (d.estrategia === "Evitar" ? r.smRef : null));
    if (exigida) {
      if (primeiro || mudouConteudo || !r.aprovacao || !r.aprovacao.exigida) r.aprovacao = { exigida: true, situacao: "Pendente", solicitadaEm: REF };
    } else r.aprovacao = { exigida: false };
    var criada = null, criadaSm = null;
    if (novaAcao) criada = criarAcaoRisco(r, Object.assign({ solicitanteId: sessaoPessoa() }, novaAcao));
    if (smNova) {
      criadaSm = criarAcaoRisco(r, { assunto: "Registrar SM da mudança de solução do risco " + r.codigo, descricao: "Estratégia Evitar: registrar a solicitação de mudança no módulo 08 e vincular ao plano.",
        solicitanteId: sessaoPessoa(), responsavelId: r.responsavelPlanoId, prevista: somarDiasIso(REF, 7) });
    }
    var pend = r.aprovacao.exigida && r.aprovacao.situacao !== "Aprovado";
    if (pend) r.situacao = "Em análise";
    else if (d.estrategia === "Aceitar") r.situacao = "Monitorado";
    else if (r.situacao === "Identificado" || r.situacao === "Em análise" || criada) r.situacao = "Em tratamento";
    historicoRisco(r, "Plano de resposta " + (primeiro ? "registrado" : "alterado") + ": " + d.estrategia + ", alvo " + nomeFaixa(d.severidadeAlvo) + " até " + dataBr(d.prazoAlvo) + "." +
      (criada ? " Ação " + criada.item + " criada (" + criada.assunto + ")." : "") + (criadaSm ? " Ação para registrar a SM criada na Central." : "") +
      (pend ? " Aguardando aprovação da gerência do projeto." : ""));
    persistir("riscos");
    return responder({ codigo: r.codigo, situacao: r.situacao, aprovacaoPendente: pend, habilitaResidual: primeiro, acao: criada ? copia(criada) : null });
  }

  /* Aprovação do plano pela gerência do projeto (segregação: quem aprova não é o responsável pelo plano).
     TODO: API PUT /riscos/{codigo}/plano/aprovacao */
  function aprovarPlanoRisco(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Aprovação do plano exige papel Gestor.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (!(r.aprovacao && r.aprovacao.exigida && r.aprovacao.situacao === "Pendente")) return rejeitar("Não há plano aguardando aprovação.");
    if (r.responsavelPlanoId === sessaoPessoa()) return rejeitar("O responsável pelo plano não pode aprová-lo (segregação de funções).");
    var coment = String(d.comentario || "").trim();
    if (d.decisao === "Devolvido" && coment.length < 10) return rejeitar({ campo: "comentario", msg: "Explique o que precisa ser revisto (mínimo de 10 caracteres)." });
    if (["Aprovado", "Devolvido"].indexOf(d.decisao) < 0) return rejeitar({ campo: "decisao", msg: "Escolha a decisão." });
    r.aprovacao = { exigida: true, situacao: d.decisao, porId: sessaoPessoa(), data: REF, comentario: coment || null };
    if (d.decisao === "Aprovado") r.situacao = r.estrategia === "Aceitar" ? "Monitorado" : "Em tratamento";
    historicoRisco(r, "Plano de resposta " + (d.decisao === "Aprovado" ? "aprovado" : "devolvido para revisão") + " pelo gestor." + (coment ? " Comentário: " + coment : ""));
    persistir("riscos");
    return responder({ codigo: r.codigo, situacao: r.situacao });
  }

  /* Revisão periódica (RG-28 a RG-30): sempre grava linha na linha do tempo. TODO: API POST /riscos/{codigo}/revisoes */
  function revisarRisco(codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar revisões.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (riscoFechado(r)) return rejeitar("Risco encerrado não recebe revisões.");
    if (!r.inerente) return rejeitar("Avalie o risco antes de registrar a primeira revisão.");
    var pr = P().riscos, e = [];
    var alvoAv = r.residual ? "residual" : "inerente";
    var vig = r[alvoAv];
    var scoreAnt = vig.p * vig.i;
    var p = Number(d.p), i = Number(d.i);
    if (!d.data) e.push({ campo: "data", msg: "Informe a data da revisão." });
    else if (d.data > REF) e.push({ campo: "data", msg: "A data da revisão não pode ser futura." });
    else if (r.ultimaRevisao && d.data < r.ultimaRevisao) e.push({ campo: "data", msg: "A data não pode ser anterior à última revisão (" + dataBr(r.ultimaRevisao) + ")." });
    if (APURACOES.indexOf(d.situacaoApurada) < 0) e.push({ campo: "situacaoApurada", msg: "Escolha a situação apurada." });
    if (!(p >= 1 && p <= 5)) e.push({ campo: "p", msg: "Escolha a probabilidade atual." });
    if (!(i >= 1 && i <= 5)) e.push({ campo: "i", msg: "Escolha o impacto atual." });
    e = e.concat(errosTexto(d, "comentario", "Comentário", 10, 1000));
    if (d.gatilho !== "sim" && d.gatilho !== "nao") e.push({ campo: "gatilho", msg: "Informe se o gatilho ocorreu." });
    var score = p * i;
    var sev = p >= 1 && i >= 1 ? R.severidade(score, pr, r.riscoVida) : null;
    var cad = sev ? R.cadenciaRisco(sev.id, pr.cadenciaDias) : null;
    if (!d.proximaRevisao) e.push({ campo: "proximaRevisao", msg: "Informe a próxima revisão." });
    else if (d.data && d.proximaRevisao <= d.data) e.push({ campo: "proximaRevisao", msg: "A próxima revisão deve ser posterior à data desta revisão." });
    else if (d.data && cad && d.proximaRevisao > somarDiasIso(d.data, cad)) e.push({ campo: "proximaRevisao", msg: "Pela cadência da faixa " + sev.nome + " (" + cad + " dias), a próxima revisão deve ser até " + dataBr(somarDiasIso(d.data, cad)) + ". Pode antecipar, nunca postergar." });
    if (["Sem mudança", "Risco reduzido", "Risco agravado"].indexOf(d.situacaoApurada) >= 0 && sev) {
      var esperada = score < scoreAnt ? "Risco reduzido" : score > scoreAnt ? "Risco agravado" : "Sem mudança";
      if (esperada !== d.situacaoApurada) e.push({ campo: "situacaoApurada", msg: "Score de " + scoreAnt + " para " + score + ": a situação apurada deve ser “" + esperada + "”." });
    }
    if (e.length) return Promise.reject({ erros: e });
    var dims = copia(vig.dimensoes || {});
    Object.keys(dims).forEach(function (k) { if (dims[k] > i) dims[k] = i; });
    r[alvoAv] = { p: p, i: i, dimensoes: dims };
    var gat = d.gatilho === "sim";
    if (gat) r.gatilhoOcorridoEm = d.data;
    r.revisoes = r.revisoes || [];
    r.revisoes.unshift({ data: d.data, porId: sessaoPessoa(), tipo: "revisao", situacaoApurada: d.situacaoApurada, de: scoreAnt, para: score, p: p, i: i, gatilho: gat, texto: d.comentario.trim() });
    r.ultimaRevisao = d.data; r.proximaRevisao = d.proximaRevisao; r.cadenciaDias = R.diasEntre(d.data, d.proximaRevisao);
    historicoRisco(r, (scoreAnt === score ? "Revisão registrada, sem mudança de severidade." : "Revisão registrada: score de " + scoreAnt + " para " + score + " (" + sev.nome + ").") +
      (gat ? " Gatilho ocorreu: reavaliação obrigatória." : "") + " Próxima revisão em " + dataBr(d.proximaRevisao) + "." +
      (d.notificar ? " Dono e gestor notificados por e-mail (simulação)." : ""));
    persistir("riscos");
    var enc = d.situacaoApurada === "Risco materializado" ? "Materializado" : d.situacaoApurada === "Risco superado" ? "Superado" : null;
    return responder({ codigo: r.codigo, score: score, sev: sev, encerrar: enc, reavaliar: gat });
  }

  /* Encerramento (ato de gestor). Materializado: ações abertas continuam na Central, ação de tratamento do
     problema e, se preciso, SM (08). Lição aprendida sempre (vai para o acervo do 08).
     TODO: API POST /riscos/{codigo}/encerramento */
  function encerrarRisco(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Encerrar risco exige papel Gestor. Membro pode propor o encerramento na revisão.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (riscoFechado(r)) return rejeitar("O risco já está encerrado.");
    var e = [];
    var mat = d.motivo === "Materializado", oport = r.natureza === "Oportunidade";
    if (MOTIVOS_ENCERRAMENTO.indexOf(d.motivo) < 0) e.push({ campo: "motivo", msg: "Escolha o motivo do encerramento." });
    if (!d.data) e.push({ campo: "data", msg: "Informe a data do encerramento." });
    else if (d.data > REF) e.push({ campo: "data", msg: "A data do encerramento não pode ser futura." });
    else if (d.data < r.identificadoEm) e.push({ campo: "data", msg: "A data não pode ser anterior à identificação (" + dataBr(r.identificadoEm) + ")." });
    var abertas = acoesComStatus(function (a) { return a.origem === "Risco" && a.origemRef === r.codigo && a.ehAcao && !a.conclusao; });
    if (abertas.length && !mat) e.push("Existe" + (abertas.length > 1 ? "m " + abertas.length + " ações" : " 1 ação") + " em aberto vinculada" + (abertas.length > 1 ? "s" : "") + " a este risco (" +
      abertas.map(function (a) { return "item " + a.item; }).join(", ") + "). Conclua ou cancele antes de encerrar, salvo se o motivo for Materializado.");
    if (d.motivo === "Duplicado") {
      var dup = riscoPorCodigo(d.duplicadoDe);
      if (!dup || dup.codigo === r.codigo || dup.projetoId !== r.projetoId) e.push({ campo: "duplicadoDe", msg: "Escolha o risco original (mesmo projeto)." });
    }
    if (mat) {
      if (!(d.impactoRealPrazoDias >= 0)) e.push({ campo: "impactoRealPrazoDias", msg: "Informe o impacto real em prazo (zero ou mais)." });
      if (!(d.impactoRealCustoCentavos >= 0)) e.push({ campo: "impactoRealCustoCentavos", msg: "Informe o impacto real em custo (zero ou mais)." });
      if (!oport && d.gerarAcao) validarAcaoRisco({ assunto: d.acaoAssunto, solicitanteId: sessaoPessoa(), responsavelId: d.acaoResponsavelId, prevista: d.acaoPrevista })
        .forEach(function (x) { e.push({ campo: "acao" + x.campo.charAt(0).toUpperCase() + x.campo.slice(1), msg: x.msg }); });
    }
    e = e.concat(errosTexto(d, "licao", "Lição aprendida", 20, 1000));
    if (e.length) return Promise.reject({ erros: e });

    var proj = porId(M.projetos)[r.projetoId] || {};
    var enc = { motivo: d.motivo, data: d.data, porId: sessaoPessoa(), licao: d.licao.trim(), situacaoAnterior: r.situacao };
    if (d.motivo === "Duplicado") enc.duplicadoDe = d.duplicadoDe;
    var extras = [];
    if (mat) {
      enc.impactoRealPrazoDias = Math.round(d.impactoRealPrazoDias); enc.impactoRealCustoCentavos = d.impactoRealCustoCentavos;
      if (!oport && d.gerarAcao) {
        var a = criarAcaoRisco(r, { assunto: d.acaoAssunto, descricao: "Risco materializado: tratar o problema.", solicitanteId: sessaoPessoa(), responsavelId: d.acaoResponsavelId, prevista: d.acaoPrevista }, "Problema");
        enc.acaoRef = a.item; extras.push("ação " + a.item + " na Central");
      }
      if (!oport && d.abrirSm) {
        var tipoSm = r.dimensao === "Custo" ? "Custo" : r.dimensao === "Escopo e qualidade" ? "Escopo" : "Prazo";
        var sm = { id: proximoId("mudancas"), projetoId: r.projetoId, codigo: proximoCodigo("mudancas", "SM-" + (proj.padraoAta || "TN") + "-"),
          titulo: "Tratamento do risco materializado " + r.codigo, tipo: tipoSm, origem: "Risco materializado", prioridade: "Urgente",
          solicitanteId: sessaoPessoa(), dataSolicitacao: d.data, descricao: r.titulo + ". Impacto real: " + enc.impactoRealPrazoDias + " dias e R$ " + (enc.impactoRealCustoCentavos / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) + ".",
          impacto: null, fonteRecurso: null, alcada: null, decisao: null, situacao: "Registrada", encerramento: null, riscoRef: r.codigo };
        colecao("mudancas").push(sm); persistir("mudancas");
        enc.smRef = sm.codigo; extras.push("SM " + sm.codigo + " registrada");
      }
    }
    var lic = { id: proximoId("licoes"), projetoId: r.projetoId, codigo: proximoCodigo("licoes", "LA-" + (proj.padraoAta || "TN") + "-"),
      titulo: r.titulo.length > 110 ? r.titulo.slice(0, 107) + "..." : r.titulo, tipo: mat && !oport ? "A evitar" : "A repetir",
      fase: "Construção", area: "Riscos", disciplina: "", origem: "Risco " + r.codigo,
      aconteceu: "Risco encerrado: " + d.motivo + ".", causa: r.causa, impactoPrazoDias: mat ? enc.impactoRealPrazoDias : 0, impactoCustoCentavos: mat ? enc.impactoRealCustoCentavos : 0,
      recomendacao: enc.licao, palavrasChave: [r.categoria, r.subcategoria].filter(Boolean), autorId: sessaoPessoa(), aplicabilidade: "Projeto", situacao: "Rascunho", data: d.data, reusos: 0 };
    colecao("licoes").push(lic); persistir("licoes");
    enc.licaoRef = lic.codigo; extras.push("lição " + lic.codigo + " no acervo");
    r.encerramento = enc;
    r.situacao = mat ? "Materializado" : "Encerrado";
    r.proximaRevisao = null;
    historicoRisco(r, "Risco encerrado: " + d.motivo + (d.duplicadoDe ? " de " + d.duplicadoDe : "") + ". Gerado: " + extras.join(", ") + "." +
      (mat && abertas.length ? " Ações em aberto continuam na Central." : ""));
    persistir("riscos");
    return responder({ codigo: r.codigo, situacao: r.situacao, licao: lic.codigo, sm: enc.smRef || null, acao: enc.acaoRef || null });
  }

  /* Reabertura (gestor, com justificativa). TODO: API POST /riscos/{codigo}/reabertura */
  function reabrirRisco(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Reabrir risco exige papel Gestor.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (!riscoFechado(r)) return rejeitar("O risco não está encerrado.");
    var j = String(d.justificativa || "").trim();
    if (j.length < 10) return rejeitar({ campo: "justificativa", msg: "Justifique a reabertura (mínimo de 10 caracteres)." });
    var ant = r.encerramento && r.encerramento.situacaoAnterior;
    r.encerramentosAnteriores = (r.encerramentosAnteriores || []).concat(r.encerramento ? [r.encerramento] : []);
    r.encerramento = null;
    r.situacao = ant && FECHADAS_RISCO.indexOf(ant) < 0 ? ant : (r.estrategia ? "Em tratamento" : r.inerente ? "Em análise" : "Identificado");
    var vig = r.residual || r.inerente;
    if (vig) { r.cadenciaDias = R.cadenciaRisco(R.severidade(vig.p * vig.i, P().riscos, r.riscoVida).id, P().riscos.cadenciaDias); r.proximaRevisao = somarDiasIso(REF, r.cadenciaDias); }
    historicoRisco(r, "Risco reaberto. Justificativa: " + j);
    persistir("riscos");
    return responder({ codigo: r.codigo, situacao: r.situacao });
  }

  /* Exclusão lógica (RG-31 a RG-35). TODO: API DELETE /riscos/{codigo} (Oculto = verdadeiro) */
  function excluirRisco(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Excluir risco exige papel Gestor.");
    var r = riscoPorCodigo(codigo);
    if (!r) return rejeitar("Risco não encontrado.");
    if (riscoFechado(r)) return rejeitar("Risco encerrado não é excluído: já saiu da carteira ativa.");
    var abertas = acoesComStatus(function (a) { return a.origem === "Risco" && a.origemRef === r.codigo && a.ehAcao && !a.conclusao; });
    if (abertas.length) return rejeitar("Risco com ação em aberto não pode ser excluído: " + abertas.map(function (a) { return "item " + a.item + " (" + a.assunto + ")"; }).join("; ") + ".");
    if (MOTIVOS_EXCLUSAO.indexOf(d.motivo) < 0) return rejeitar({ campo: "motivo", msg: "Escolha o motivo da exclusão." });
    var obs = String(d.observacao || "").trim();
    if (d.motivo === "Outro" && obs.length < 10) return rejeitar({ campo: "observacao", msg: "Detalhe o motivo (obrigatório quando o motivo for Outro)." });
    r.oculto = true;
    r.exclusao = { motivo: d.motivo, observacao: obs || null, porId: sessaoPessoa(), data: REF };
    historicoRisco(r, "Risco excluído (exclusão lógica): " + d.motivo + (obs ? ". " + obs : "") + ".");
    persistir("riscos");
    return responder({ codigo: r.codigo });
  }
  /* Restauração (só Admin). TODO: API POST /riscos/{codigo}/restauracao */
  function restaurarRisco(codigo) {
    if (!temPapel("Admin")) return rejeitar("Somente Admin restaura riscos excluídos.");
    var r = riscoPorCodigo(codigo);
    if (!r || !r.oculto) return rejeitar("Risco não está excluído.");
    r.oculto = false; historicoRisco(r, "Risco restaurado pelo Admin.");
    persistir("riscos");
    return responder({ codigo: r.codigo });
  }

  /* Catálogo RBS (Configurações > Cadastros) e cadastro rápido. TODO: API GET/POST /cadastros/risco-categorias */
  function categoriasRisco() { return responder(M.riscoCategorias || []); }
  function novaCategoriaRisco(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite cadastrar categorias.");
    var g = String(d.grupo || "").trim(), n = String(d.nome || "").trim();
    if (g.length < 2) return rejeitar({ campo: "grupo", msg: "Informe o grupo (nível 1 da RBS)." });
    if (n.length < 2) return rejeitar({ campo: "nome", msg: "Informe a subcategoria." });
    if ((M.riscoCategorias || []).some(function (c) { return U_norm(c.grupo) === U_norm(g) && U_norm(c.nome) === U_norm(n); })) return rejeitar({ campo: "nome", msg: "Categoria já cadastrada." });
    var c = { id: proximoId("riscoCategorias"), grupo: g, nome: n };
    colecao("riscoCategorias").push(c); persistir("riscoCategorias");
    return responder(copia(c));
  }

  /* ======================================================================
     06 Gestão da Qualidade (PMBOK: gerenciar e controlar a qualidade; ISO 9001 8.7 e 10.2;
     ISO 19011 para auditorias). Regras e cálculos só aqui (as telas não calculam).
     RNC: Aberta > Em análise de causa > Ação corretiva > Verificação de eficácia > Encerrada
       (Cancelada só antes da ação corretiva, pelo Gestor). Contenção imediata obrigatória na
       abertura; prazo de tratamento pela severidade (parâmetros); disposição Reparo ou Usar como
       está exige concessão do cliente; ações corretivas são registros da Central (origem RNC);
       verificação de eficácia pelo Gestor, que não pode ser o responsável pela análise; ineficaz
       volta para Ação corretiva (reincidência).
     ITP: pontos H (espera), W (testemunho) e R (registro); inspeção só em ITP aprovado pelo
       cliente; reprovação abre RNC automaticamente.
     Auditorias: programa com data planejada; constatação do tipo Não conformidade abre RNC.
     ====================================================================== */
  var SITUACOES_RNC = ["Aberta", "Em análise de causa", "Ação corretiva", "Verificação de eficácia", "Encerrada", "Cancelada"];
  var TRATAMENTO_RNC = ["Aberta", "Em análise de causa", "Ação corretiva"];
  var SEVERIDADES_RNC = ["Crítica", "Maior", "Menor"];
  var ORIGENS_RNC = ["Inspeção", "Inspeção de fabricação", "Auditoria", "Fornecedor", "Processo", "Cliente"];
  var DISPOSICOES_RNC = ["Retrabalho", "Reparo", "Usar como está", "Rejeitar", "Reclassificar"];
  var DISPOSICOES_CONCESSAO = ["Reparo", "Usar como está"];
  var METODOS_RNC = ["5 porquês", "Diagrama de Ishikawa", "Árvore de causas"];
  var DISCIPLINAS_QUALIDADE = ["Civil", "Estrutura metálica", "Mecânica", "Tubulação", "Elétrica", "Instrumentação", "Pintura", "Isolamento"];
  var SIGLA_DISCIPLINA = { "Civil": "CIV", "Estrutura metálica": "EST", "Mecânica": "MEC", "Tubulação": "TUB", "Elétrica": "ELE", "Instrumentação": "INS", "Pintura": "PIN", "Isolamento": "ISO" };
  var TIPOS_PONTO = ["H", "W", "R"];
  var RESPONSAVEIS_PONTO = ["Contratada", "Fiscalização", "Cliente", "Laboratório", "Fabricante"];
  var RESULTADOS_INSPECAO = ["Aprovado", "Aprovado com ressalva", "Reprovado"];
  var TIPOS_AUDITORIA = ["Contratada", "Fornecedor", "Interna"];
  var TIPOS_CONSTATACAO = ["Não conformidade", "Observação", "Oportunidade de melhoria"];

  function parQ() {
    return P().qualidade || { prazoTratamentoDias: { critica: 15, maior: 30, menor: 45 }, verificacaoEficaciaDias: 30,
      metaAprovacaoInspecaoPct: 95, metaConformidadeAuditoriaPct: 90, notificacaoClienteHoras: 48 };
  }
  function chaveSeveridade(s) { return s === "Crítica" ? "critica" : s === "Menor" ? "menor" : "maior"; }
  function prazoRnc(data, severidade) { return somarDiasIso(data, parQ().prazoTratamentoDias[chaveSeveridade(severidade)]); }
  function rncPorCodigo(c) { return porCampo(M.rncs, "codigo", c); }
  function itpPorCodigo(c) { return porCampo(M.itps, "codigo", c); }
  function auditoriaPorCodigo(c) { return porCampo(M.auditorias, "codigo", c); }
  function acoesDaRnc(c) { return acoesComStatus(function (a) { return a.origem === "RNC" && a.origemRef === c; }); }
  function padraoProjeto(pid) { return (porId(M.projetos)[Number(pid)] || {}).padraoAta || "TN-2026"; }
  function codigoProj(pid) { return (porId(M.projetos)[Number(pid)] || {}).codigo || ""; }
  function rncAtiva(r) { return r.situacao !== "Encerrada" && r.situacao !== "Cancelada"; }
  function aprovadaInspecao(i) { return i.resultado === "Aprovado" || i.resultado === "Aprovado com ressalva"; }

  function historicoRncDerivado(r) {
    var h = [{ quando: r.data, porId: r.abertaPorId, texto: "RNC aberta (" + r.origem + (r.origemRef ? " " + r.origemRef : "") + "). Contenção: " + (r.contencao || "não registrada") + "." }];
    if (r.responsavelId) h.unshift({ quando: r.data, porId: r.abertaPorId, texto: "Análise de causa atribuída a " + nomePessoa(r.responsavelId) + "." });
    if (r.causaRaiz) h.unshift({ quando: (r.concessao && r.concessao.data) || r.data, porId: r.responsavelId, texto: "Análise registrada (" + r.metodo + "). Causa raiz: " + r.causaRaiz + " Disposição: " + r.disposicao + "." });
    if (r.eficacia) h.unshift({ quando: r.eficacia.data, porId: r.eficacia.porId, texto: (r.eficacia.eficaz ? "Eficácia verificada e RNC encerrada: " : "Ação ineficaz: ") + r.eficacia.texto });
    return h;
  }
  function historicoRnc(r, texto) {
    if (!r.historico) r.historico = historicoRncDerivado(r);
    r.historico.unshift({ quando: agoraIso(), porId: sessaoPessoa(), texto: texto });
  }
  var PROXIMA_ETAPA_RNC = { "Aberta": "Atribuir a análise de causa", "Em análise de causa": "Registrar causa raiz, disposição e ações",
    "Ação corretiva": "Concluir as ações e enviar para verificação", "Verificação de eficácia": "Verificar a eficácia", "Encerrada": "", "Cancelada": "" };

  /* Visão calculada da RNC: prazos, ações na Central e próxima etapa */
  function rncCalculada(r) {
    if (!r) return null;
    var x = copia(r);
    x.projetoCodigo = codigoProj(r.projetoId);
    x.ativa = rncAtiva(r);
    x.emTratamento = TRATAMENTO_RNC.indexOf(r.situacao) >= 0;
    x.vencida = x.emTratamento && r.prazo < REF;
    x.diasAtraso = x.vencida ? R.diasEntre(r.prazo, REF) : 0;
    x.diasAberta = R.diasEntre(r.data, r.encerramento || REF);
    x.verificacaoVencida = r.situacao === "Verificação de eficácia" && !!r.verificacaoPrevista && r.verificacaoPrevista < REF;
    x.exigeConcessao = DISPOSICOES_CONCESSAO.indexOf(r.disposicao) >= 0;
    x.concessaoPendente = x.exigeConcessao && !r.concessao;
    var acoes = acoesDaRnc(r.codigo).filter(function (a) { return a.ehAcao; });
    x.acoesTotal = acoes.length;
    x.acoesAbertas = acoes.filter(function (a) { return a.status !== "concluida"; }).length;
    x.acoesAtrasadas = acoes.filter(function (a) { return a.status === "atrasada"; }).length;
    x.reincidencias = r.reincidencias || 0;
    x.proximaEtapa = PROXIMA_ETAPA_RNC[r.situacao] || "";
    return x;
  }
  /* TODO: API GET /projetos/{id}/rncs?situacao&severidade&disciplina&empresaId&origem&busca */
  function listarRncsDe(filtro) {
    filtro = filtro || {};
    var lista = doProjeto(M.rncs, filtro.projetoId).map(rncCalculada);
    if (filtro.situacao === "ativas") lista = lista.filter(function (r) { return r.ativa; });
    else if (filtro.situacao === "vencidas") lista = lista.filter(function (r) { return r.vencida || r.verificacaoVencida; });
    else if (filtro.situacao) lista = lista.filter(function (r) { return r.situacao === filtro.situacao; });
    if (filtro.severidade) lista = lista.filter(function (r) { return r.severidade === filtro.severidade; });
    if (filtro.disciplina) lista = lista.filter(function (r) { return r.disciplina === filtro.disciplina; });
    if (filtro.origem) lista = lista.filter(function (r) { return r.origem === filtro.origem; });
    if (filtro.empresaId) lista = lista.filter(function (r) { return r.empresaId === Number(filtro.empresaId); });
    if (filtro.busca) {
      var t = U_norm(filtro.busca);
      lista = lista.filter(function (r) { return [r.codigo, r.descricao, r.origemRef, r.disciplina, nomeEmpresa(r.empresaId)].some(function (v) { return U_norm(v).indexOf(t) >= 0; }); });
    }
    lista.sort(function (a, b) { return a.data < b.data ? 1 : a.data > b.data ? -1 : (a.codigo < b.codigo ? 1 : -1); });
    return lista;
  }
  /* TODO: API GET /rncs/{codigo} */
  function obterRnc(codigo) {
    var r = rncPorCodigo(codigo);
    var x = rncCalculada(r);
    if (x) { x.acoesLista = acoesDaRnc(codigo); x.historicoExibicao = r.historico || historicoRncDerivado(r); }
    return responder(x);
  }
  /* Abertura (tela, inspeção reprovada ou constatação de auditoria). Devolve o registro ou { erros }. */
  function abrirRncDe(d) {
    var erros = [];
    if (semProjeto(d.projetoId)) return { erros: [{ msg: "Escolha o projeto da RNC." }] };
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data da constatação." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    if (ORIGENS_RNC.indexOf(d.origem) < 0) erros.push({ campo: "origem", msg: "Escolha a origem." });
    if (DISCIPLINAS_QUALIDADE.indexOf(d.disciplina) < 0) erros.push({ campo: "disciplina", msg: "Escolha a disciplina." });
    if (!d.empresaId) erros.push({ campo: "empresaId", msg: "Escolha a empresa responsável." });
    if (!d.descricao || String(d.descricao).trim().length < 15) erros.push({ campo: "descricao", msg: "Descreva a não conformidade (mínimo de 15 caracteres): o que, onde e o requisito não atendido." });
    if (SEVERIDADES_RNC.indexOf(d.severidade) < 0) erros.push({ campo: "severidade", msg: "Escolha a severidade." });
    if (!d.contencao || String(d.contencao).trim().length < 10) erros.push({ campo: "contencao", msg: "Registre a contenção imediata (mínimo de 10 caracteres): bloqueio, segregação ou suspensão." });
    if (erros.length) return { erros: erros };
    var r = { id: proximoId("rncs"), projetoId: Number(d.projetoId), codigo: proximoCodigo("rncs", "RNC-" + padraoProjeto(d.projetoId) + "-"), data: d.data,
      origem: d.origem, origemRef: d.origemRef || null, disciplina: d.disciplina, empresaId: Number(d.empresaId), descricao: String(d.descricao).trim(),
      severidade: d.severidade, contencao: String(d.contencao).trim(), responsavelId: null, disposicao: null, concessao: null, metodo: null, causaRaiz: null,
      prazo: prazoRnc(d.data, d.severidade), encerramento: null, situacao: "Aberta", custoNaoQualidadeCentavos: 0, abertaPorId: sessaoPessoa(), licaoRef: null };
    r.historico = [{ quando: agoraIso(), porId: sessaoPessoa(), texto: "RNC aberta (" + r.origem + (r.origemRef ? " " + r.origemRef : "") + "). Contenção: " + r.contencao + "." }];
    colecao("rncs").push(r); persistir("rncs");
    return r;
  }
  /* TODO: API POST /projetos/{id}/rncs */
  function salvarRnc(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite abrir RNC.");
    var r = abrirRncDe(d);
    if (r.erros) return rejeitar(r.erros);
    return responder({ codigo: r.codigo, prazo: r.prazo });
  }
  /* TODO: API PUT /rncs/{codigo}/analise/responsavel */
  function iniciarAnaliseRnc(codigo, d) {
    var r = rncPorCodigo(codigo);
    if (!r) return rejeitar("RNC não encontrada.");
    if (r.situacao !== "Aberta") return rejeitar("A análise desta RNC já foi iniciada.");
    if (!d || !d.responsavelId) return rejeitar({ campo: "responsavelId", msg: "Escolha o responsável pela análise de causa." });
    r.responsavelId = Number(d.responsavelId);
    r.situacao = "Em análise de causa";
    historicoRnc(r, "Análise de causa atribuída a " + nomePessoa(r.responsavelId) + ".");
    persistir("rncs");
    return responder({ codigo: codigo });
  }
  function validarAcoesRnc(lista) {
    var erros = [];
    (lista || []).forEach(function (a, i) {
      if (!a.assunto || !String(a.assunto).trim()) erros.push({ msg: "Ação " + (i + 1) + ": informe o assunto." });
      if (!a.responsavelId) erros.push({ msg: "Ação " + (i + 1) + ": escolha o responsável." });
      if (!a.prevista) erros.push({ msg: "Ação " + (i + 1) + ": informe a data prevista." });
      else if (a.prevista < REF) erros.push({ msg: "Ação " + (i + 1) + ": a data prevista não pode ser anterior à referência." });
    });
    return erros;
  }
  function criarAcoesRnc(r, lista, grupo) {
    var base = acoesDaRnc(r.codigo).length;
    lista.forEach(function (a, i) {
      colecao("acoes").push({ id: proximoId("acoes"), projetoId: r.projetoId, origem: "RNC", origemRef: r.codigo, item: String(base + i + 1), grupo: grupo || "Ação corretiva", tipo: "Ação",
        assunto: String(a.assunto).trim(), descricao: a.descricao || "", solicitanteId: sessaoPessoa(), responsavelId: Number(a.responsavelId), prevista: a.prevista, replanejada: null, conclusao: null });
    });
    persistir("acoes");
  }
  /* Análise de causa, disposição (com concessão quando exigida), custo da não qualidade e ações corretivas.
     TODO: API PUT /rncs/{codigo}/analise */
  function registrarAnaliseRnc(codigo, d) {
    var r = rncPorCodigo(codigo);
    if (!r) return rejeitar("RNC não encontrada.");
    if (r.situacao !== "Em análise de causa") return rejeitar("Atribua a análise antes de registrar a causa raiz.");
    var erros = [];
    if (METODOS_RNC.indexOf(d.metodo) < 0) erros.push({ campo: "metodo", msg: "Escolha o método de análise." });
    if (!d.causaRaiz || String(d.causaRaiz).trim().length < 15) erros.push({ campo: "causaRaiz", msg: "Descreva a causa raiz (mínimo de 15 caracteres)." });
    if (DISPOSICOES_RNC.indexOf(d.disposicao) < 0) erros.push({ campo: "disposicao", msg: "Escolha a disposição do produto não conforme." });
    var exige = DISPOSICOES_CONCESSAO.indexOf(d.disposicao) >= 0;
    if (exige && (!d.concessaoReferencia || String(d.concessaoReferencia).trim().length < 5)) erros.push({ campo: "concessaoReferencia", msg: "Reparo e Usar como está exigem a concessão do cliente: informe o documento." });
    if (exige && !d.concessaoData) erros.push({ campo: "concessaoData", msg: "Informe a data da concessão." });
    if (d.custoCentavos != null && !(Number(d.custoCentavos) >= 0)) erros.push({ campo: "custoCentavos", msg: "O custo da não qualidade não pode ser negativo." });
    if (!d.acoes || !d.acoes.length) erros.push({ campo: "acoes", msg: "Inclua ao menos uma ação corretiva (elimina a causa raiz)." });
    erros = erros.concat(validarAcoesRnc(d.acoes));
    if (erros.length) return rejeitar(erros);
    r.metodo = d.metodo; r.causaRaiz = String(d.causaRaiz).trim(); r.disposicao = d.disposicao;
    r.concessao = exige ? { referencia: String(d.concessaoReferencia).trim(), data: d.concessaoData } : null;
    r.custoNaoQualidadeCentavos = Number(d.custoCentavos || 0);
    criarAcoesRnc(r, d.acoes, "Ação corretiva");
    r.situacao = "Ação corretiva";
    historicoRnc(r, "Análise registrada (" + r.metodo + "). Causa raiz: " + r.causaRaiz + " Disposição: " + r.disposicao +
      (r.concessao ? " (concessão " + r.concessao.referencia + ")" : "") + ". " + U_plural(d.acoes.length, "ação corretiva criada", "ações corretivas criadas") + " na Central.");
    persistir("rncs");
    return responder({ codigo: codigo, criadas: d.acoes.length });
  }
  /* TODO: API POST /rncs/{codigo}/acoes */
  function definirAcoesRnc(codigo, lista) {
    var r = rncPorCodigo(codigo);
    if (!r) return rejeitar("RNC não encontrada.");
    if (r.situacao !== "Ação corretiva") return rejeitar("Novas ações só na etapa Ação corretiva.");
    if (!lista || !lista.length) return rejeitar("Inclua ao menos uma ação.");
    var erros = validarAcoesRnc(lista);
    if (erros.length) return rejeitar(erros);
    criarAcoesRnc(r, lista, "Ação corretiva");
    historicoRnc(r, U_plural(lista.length, "ação corretiva criada", "ações corretivas criadas") + " na Central.");
    persistir("rncs");
    return responder({ codigo: codigo, criadas: lista.length });
  }
  /* TODO: API PUT /rncs/{codigo}/verificacao */
  function enviarVerificacaoRnc(codigo) {
    var r = rncPorCodigo(codigo);
    if (!r) return rejeitar("RNC não encontrada.");
    if (r.situacao !== "Ação corretiva") return rejeitar("A RNC não está na etapa Ação corretiva.");
    var acoes = acoesDaRnc(codigo).filter(function (a) { return a.ehAcao; });
    if (!acoes.length) return rejeitar("Inclua ao menos uma ação corretiva antes da verificação.");
    var abertas = acoes.filter(function (a) { return a.status !== "concluida"; });
    if (abertas.length) return rejeitar((abertas.length === 1 ? "Existe 1 ação corretiva em aberto" : "Existem " + abertas.length + " ações corretivas em aberto") + ". Conclua-as na Central antes da verificação.");
    if (DISPOSICOES_CONCESSAO.indexOf(r.disposicao) >= 0 && !r.concessao) return rejeitar("Registre a concessão do cliente antes da verificação.");
    r.situacao = "Verificação de eficácia";
    r.verificacaoPrevista = somarDiasIso(REF, parQ().verificacaoEficaciaDias);
    historicoRnc(r, "Ações concluídas; verificação de eficácia prevista para " + dataBr(r.verificacaoPrevista) + ".");
    persistir("rncs");
    return responder({ codigo: codigo, verificacaoPrevista: r.verificacaoPrevista });
  }
  /* Eficaz encerra (lição opcional em Rascunho no 08); ineficaz volta para Ação corretiva.
     TODO: API PUT /rncs/{codigo}/eficacia */
  function verificarEficaciaRnc(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Verificar a eficácia exige papel Gestor.");
    var r = rncPorCodigo(codigo);
    if (!r) return rejeitar("RNC não encontrada.");
    if (r.situacao !== "Verificação de eficácia") return rejeitar("A RNC não está na etapa de verificação de eficácia.");
    if (r.responsavelId && sessaoPessoa() === r.responsavelId) return rejeitar("Quem respondeu pela análise não verifica a própria eficácia (segregação de funções).");
    var erros = [];
    if (d.eficaz !== true && d.eficaz !== false) erros.push({ campo: "eficaz", msg: "Informe se a ação foi eficaz." });
    if (!d.texto || String(d.texto).trim().length < 15) erros.push({ campo: "texto", msg: "Descreva a evidência da verificação (mínimo de 15 caracteres)." });
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data da verificação." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    else if (d.data < r.data) erros.push({ campo: "data", msg: "A data não pode ser anterior à abertura." });
    if (d.eficaz && d.registrarLicao) {
      if (!d.licaoTitulo || String(d.licaoTitulo).trim().length < 10) erros.push({ campo: "licaoTitulo", msg: "Informe o título da lição (mínimo de 10 caracteres)." });
      if (!d.licaoRecomendacao || String(d.licaoRecomendacao).trim().length < 15) erros.push({ campo: "licaoRecomendacao", msg: "Informe a recomendação da lição (mínimo de 15 caracteres)." });
    }
    if (erros.length) return rejeitar(erros);
    r.eficacia = { data: d.data, eficaz: !!d.eficaz, texto: String(d.texto).trim(), porId: sessaoPessoa() };
    var extra = "";
    if (d.eficaz) {
      r.situacao = "Encerrada"; r.encerramento = d.data; r.verificacaoPrevista = null;
      if (d.registrarLicao) {
        var lic = { id: proximoId("licoes"), projetoId: r.projetoId, codigo: proximoCodigo("licoes", "LA-" + padraoProjeto(r.projetoId) + "-"),
          titulo: String(d.licaoTitulo).trim(), tipo: "A evitar", fase: "Construção", area: "Qualidade", disciplina: r.disciplina, origem: "RNC " + r.codigo,
          aconteceu: r.descricao, causa: r.causaRaiz || "", impactoPrazoDias: 0, impactoCustoCentavos: r.custoNaoQualidadeCentavos || 0,
          recomendacao: String(d.licaoRecomendacao).trim(), palavrasChave: [r.disciplina, r.origem, "não conformidade"], autorId: sessaoPessoa(), aplicabilidade: "Projeto",
          situacao: "Rascunho", data: d.data, reusos: 0, historico: [{ quando: agoraIso(), porId: sessaoPessoa(), texto: "Lição criada no encerramento da " + r.codigo + "." }] };
        colecao("licoes").push(lic); persistir("licoes");
        r.licaoRef = lic.codigo; extra = " Lição " + lic.codigo + " em Rascunho.";
      }
      historicoRnc(r, "Eficácia verificada e RNC encerrada: " + r.eficacia.texto + extra);
    } else {
      r.situacao = "Ação corretiva"; r.verificacaoPrevista = null; r.reincidencias = (r.reincidencias || 0) + 1;
      historicoRnc(r, "Ação ineficaz: " + r.eficacia.texto + " A RNC volta para Ação corretiva; registre novas ações.");
    }
    persistir("rncs");
    return responder({ codigo: codigo, encerrada: !!d.eficaz, licaoRef: r.licaoRef || null });
  }
  /* TODO: API PUT /rncs/{codigo}/cancelamento */
  function cancelarRnc(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Cancelar RNC exige papel Gestor.");
    var r = rncPorCodigo(codigo);
    if (!r) return rejeitar("RNC não encontrada.");
    if (["Aberta", "Em análise de causa"].indexOf(r.situacao) < 0) return rejeitar("Só é possível cancelar antes da ação corretiva.");
    if (!d || !d.motivo || String(d.motivo).trim().length < 10) return rejeitar({ campo: "motivo", msg: "Informe o motivo do cancelamento (mínimo de 10 caracteres)." });
    r.situacao = "Cancelada"; r.encerramento = REF;
    historicoRnc(r, "RNC cancelada: " + String(d.motivo).trim() + ".");
    persistir("rncs");
    return responder({ codigo: codigo });
  }
  /* Custo da não qualidade apurado (retrabalho, reparo, ensaios, perda de material). TODO: API PUT /rncs/{codigo}/custo */
  function atualizarCustoRnc(codigo, d) {
    var r = rncPorCodigo(codigo);
    if (!r) return rejeitar("RNC não encontrada.");
    if (!rncAtiva(r)) return rejeitar("RNC encerrada ou cancelada não muda de custo.");
    if (d.custoCentavos == null || !(Number(d.custoCentavos) >= 0)) return rejeitar({ campo: "custoCentavos", msg: "Informe o custo (zero ou mais)." });
    if (!d.justificativa || String(d.justificativa).trim().length < 10) return rejeitar({ campo: "justificativa", msg: "Informe a composição do custo (mínimo de 10 caracteres)." });
    var antes = r.custoNaoQualidadeCentavos || 0;
    r.custoNaoQualidadeCentavos = Number(d.custoCentavos);
    historicoRnc(r, "Custo da não qualidade de R$ " + (antes / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) + " para R$ " +
      (r.custoNaoQualidadeCentavos / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) + ": " + String(d.justificativa).trim() + ".");
    persistir("rncs");
    return responder({ codigo: codigo });
  }

  /* ---------------- ITP e inspeções ---------------- */
  function itpCalculado(i) {
    var x = copia(i);
    x.projetoCodigo = codigoProj(i.projetoId);
    var pontos = i.pontos || [];
    x.totalPontos = pontos.length;
    x.porTipo = { H: 0, W: 0, R: 0 };
    pontos.forEach(function (p) { x.porTipo[p.tipo] = (x.porTipo[p.tipo] || 0) + 1; });
    var ins = (M.inspecoesQualidade || []).filter(function (n) { return n.itpId === i.id; });
    x.inspecoes = ins.length;
    x.aprovadas = ins.filter(aprovadaInspecao).length;
    x.reprovadas = ins.filter(function (n) { return n.resultado === "Reprovado"; }).length;
    x.aprovacaoPct = ins.length ? arred(x.aprovadas / ins.length * 100, 1) : null;
    var tocados = {};
    ins.forEach(function (n) { if (n.pontoId) tocados[n.pontoId] = true; });
    x.pontosInspecionados = Object.keys(tocados).length;
    x.ultimaInspecao = ins.reduce(function (m, n) { return !m || n.data > m ? n.data : m; }, null);
    return x;
  }
  /* TODO: API GET /projetos/{id}/itps */
  function listarItpsDe(filtro) {
    filtro = filtro || {};
    var lista = doProjeto(M.itps, filtro.projetoId).map(itpCalculado);
    if (filtro.disciplina) lista = lista.filter(function (i) { return i.disciplina === filtro.disciplina; });
    if (filtro.busca) {
      var t = U_norm(filtro.busca);
      lista = lista.filter(function (i) { return [i.codigo, i.titulo, i.disciplina].some(function (v) { return U_norm(v).indexOf(t) >= 0; }); });
    }
    return lista.sort(function (a, b) { return a.codigo < b.codigo ? -1 : 1; });
  }
  /* Novo ITP (rev 0) ou nova revisão (volta a pedir a aprovação do cliente).
     Pontos casados pela atividade: ponto com inspeção registrada não pode sair. TODO: API POST/PUT /itps */
  function salvarItp(d, codigo) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite editar ITP.");
    var atual = codigo ? itpPorCodigo(codigo) : null;
    if (codigo && !atual) return rejeitar("ITP não encontrado.");
    var pid = atual ? atual.projetoId : Number(d.projetoId);
    if (!atual && semProjeto(pid)) return rejeitar("Escolha o projeto do ITP.");
    var erros = [];
    if (!d.titulo || String(d.titulo).trim().length < 5) erros.push({ campo: "titulo", msg: "Informe o título do ITP (mínimo de 5 caracteres)." });
    if (DISCIPLINAS_QUALIDADE.indexOf(d.disciplina) < 0) erros.push({ campo: "disciplina", msg: "Escolha a disciplina." });
    if (!d.empresaId) erros.push({ campo: "empresaId", msg: "Escolha a empresa executante." });
    var pontos = d.pontos || [];
    if (!pontos.length) erros.push({ campo: "pontos", msg: "Inclua ao menos um ponto de inspeção." });
    pontos.forEach(function (p, k) {
      if (!p.atividade || String(p.atividade).trim().length < 3) erros.push({ campo: "pontos." + k + ".atividade", msg: "Ponto " + (k + 1) + ": informe a atividade." });
      if (TIPOS_PONTO.indexOf(p.tipo) < 0) erros.push({ campo: "pontos." + k + ".tipo", msg: "Ponto " + (k + 1) + ": escolha H, W ou R." });
      if (!p.criterio || String(p.criterio).trim().length < 3) erros.push({ campo: "pontos." + k + ".criterio", msg: "Ponto " + (k + 1) + ": informe o critério de aceitação." });
    });
    var nomes = pontos.map(function (p) { return U_norm(p.atividade); });
    if (nomes.some(function (n, k) { return nomes.indexOf(n) !== k; })) erros.push({ campo: "pontos", msg: "Há atividades repetidas no ITP." });
    if (erros.length) return rejeitar(erros);
    var antigos = atual ? atual.pontos : [];
    var maior = antigos.reduce(function (m, p) { return Math.max(m, p.id); }, 0);
    var novos = pontos.map(function (p) {
      var igual = antigos.filter(function (a) { return U_norm(a.atividade) === U_norm(p.atividade); })[0];
      return { id: igual ? igual.id : ++maior, atividade: String(p.atividade).trim(), tipo: p.tipo, criterio: String(p.criterio).trim(),
        referencia: String(p.referencia || "").trim(), responsavel: p.responsavel || "Contratada" };
    });
    if (atual) {
      var usados = {};
      (M.inspecoesQualidade || []).forEach(function (n) { if (n.itpId === atual.id && n.pontoId) usados[n.pontoId] = true; });
      var removidos = antigos.filter(function (a) { return usados[a.id] && !novos.some(function (n) { return n.id === a.id; }); });
      if (removidos.length) return rejeitar("Pontos com inspeção registrada não podem sair do ITP: " + removidos.map(function (a) { return a.atividade; }).join(", ") + ".");
      atual.titulo = String(d.titulo).trim(); atual.disciplina = d.disciplina; atual.empresaId = Number(d.empresaId); atual.pontos = novos;
      atual.revisao = (atual.revisao || 0) + 1; atual.data = REF; atual.aprovadoCliente = false; atual.aprovacao = null;
      persistir("itps");
      return responder({ codigo: atual.codigo, revisao: atual.revisao });
    }
    var pre = "ITP-" + padraoProjeto(pid).split("-")[0] + "-" + (SIGLA_DISCIPLINA[d.disciplina] || "GER") + "-";
    var n = doProjeto(M.itps, pid).filter(function (i) { return i.codigo.indexOf(pre) === 0; })
      .reduce(function (m, i) { return Math.max(m, parseInt(i.codigo.slice(pre.length), 10) || 0); }, 0);
    var itp = { id: proximoId("itps"), projetoId: pid, codigo: pre + ("0" + (n + 1)).slice(-2), disciplina: d.disciplina, titulo: String(d.titulo).trim(),
      revisao: 0, data: REF, empresaId: Number(d.empresaId), aprovadoCliente: false, pontos: novos };
    colecao("itps").push(itp); persistir("itps");
    return responder({ codigo: itp.codigo, revisao: 0 });
  }
  /* TODO: API PUT /itps/{codigo}/aprovacao */
  function aprovarItp(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Registrar a aprovação do ITP exige papel Gestor.");
    var i = itpPorCodigo(codigo);
    if (!i) return rejeitar("ITP não encontrado.");
    if (i.aprovadoCliente) return rejeitar("Esta revisão do ITP já está aprovada.");
    if (!d || !d.referencia || String(d.referencia).trim().length < 5) return rejeitar({ campo: "referencia", msg: "Informe o documento de aprovação do cliente." });
    if (!d.data || d.data > REF) return rejeitar({ campo: "data", msg: "Informe a data da aprovação (até a referência)." });
    i.aprovadoCliente = true; i.aprovacao = { referencia: String(d.referencia).trim(), data: d.data, porId: sessaoPessoa() };
    persistir("itps");
    return responder({ codigo: codigo });
  }
  function inspecaoCalculada(n) {
    var x = copia(n);
    var itp = porId(M.itps)[n.itpId];
    x.projetoCodigo = codigoProj(n.projetoId);
    x.itpCodigo = itp ? itp.codigo : ""; x.itpTitulo = itp ? itp.titulo : (n.origem === "Suprimentos" ? "Inspeção em fábrica (04)" : "");
    x.disciplina = itp ? itp.disciplina : "";
    var r = n.rncRef ? rncPorCodigo(n.rncRef) : null;
    x.rncSituacao = r ? r.situacao : null;
    return x;
  }
  /* TODO: API GET /projetos/{id}/inspecoes-qualidade?itp&resultado&tipo&busca */
  function listarInspecoesDe(filtro) {
    filtro = filtro || {};
    var lista = doProjeto(M.inspecoesQualidade, filtro.projetoId).map(inspecaoCalculada);
    if (filtro.itpId) lista = lista.filter(function (n) { return n.itpId === Number(filtro.itpId); });
    if (filtro.resultado) lista = lista.filter(function (n) { return n.resultado === filtro.resultado; });
    if (filtro.tipoPonto) lista = lista.filter(function (n) { return n.tipoPonto === filtro.tipoPonto; });
    if (filtro.busca) {
      var t = U_norm(filtro.busca);
      lista = lista.filter(function (n) { return [n.codigo, n.ponto, n.itpCodigo, n.rncRef, nomeEmpresa(n.empresaId)].some(function (v) { return U_norm(v).indexOf(t) >= 0; }); });
    }
    return lista.sort(function (a, b) { return a.data < b.data ? 1 : a.data > b.data ? -1 : (a.codigo < b.codigo ? 1 : -1); });
  }
  /* Registro de inspeção no ponto do ITP. Reprovado abre RNC (origem Inspeção) com a contenção informada.
     TODO: API POST /projetos/{id}/inspecoes-qualidade */
  function registrarInspecao(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar inspeções.");
    var itp = porId(M.itps)[Number(d.itpId)];
    if (!itp) return rejeitar({ campo: "itpId", msg: "Escolha o ITP." });
    if (!itp.aprovadoCliente) return rejeitar({ campo: "itpId", msg: "O ITP " + itp.codigo + " rev " + itp.revisao + " ainda não tem aprovação do cliente: inspeção só em ITP aprovado." });
    var ponto = (itp.pontos || []).filter(function (p) { return p.id === Number(d.pontoId); })[0];
    var erros = [];
    if (!ponto) erros.push({ campo: "pontoId", msg: "Escolha o ponto do ITP." });
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data da inspeção." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    if (!d.inspetorId) erros.push({ campo: "inspetorId", msg: "Escolha o inspetor." });
    if (RESULTADOS_INSPECAO.indexOf(d.resultado) < 0) erros.push({ campo: "resultado", msg: "Escolha o resultado." });
    if (d.resultado && d.resultado !== "Aprovado" && (!d.observacao || String(d.observacao).trim().length < 10)) erros.push({ campo: "observacao", msg: "Descreva a ressalva ou a reprovação (mínimo de 10 caracteres)." });
    if (d.resultado === "Reprovado") {
      if (SEVERIDADES_RNC.indexOf(d.severidade) < 0) erros.push({ campo: "severidade", msg: "Reprovação abre RNC: escolha a severidade." });
      if (!d.contencao || String(d.contencao).trim().length < 10) erros.push({ campo: "contencao", msg: "Reprovação abre RNC: registre a contenção imediata (mínimo de 10 caracteres)." });
    }
    if (ponto && ponto.tipo !== "R" && d.notificacao && d.data && d.notificacao > d.data) erros.push({ campo: "notificacao", msg: "A notificação ao cliente não pode ser posterior à inspeção." });
    if (erros.length) return rejeitar(erros);
    var n = { id: proximoId("inspecoesQualidade"), projetoId: itp.projetoId, codigo: proximoCodigo("inspecoesQualidade", "INS-" + REF.slice(0, 4) + "-"), itpId: itp.id,
      pontoId: ponto.id, ponto: ponto.atividade, tipoPonto: ponto.tipo, data: d.data, empresaId: itp.empresaId, inspetorId: Number(d.inspetorId),
      resultado: d.resultado, observacao: String(d.observacao || "").trim(), notificacao: ponto.tipo !== "R" ? (d.notificacao || null) : null, rncRef: null };
    var avisos = [];
    if (ponto.tipo !== "R") {
      var horas = n.notificacao ? R.diasEntre(n.notificacao, n.data) * 24 : null;
      if (horas == null) avisos.push("Ponto " + ponto.tipo + " sem registro da notificação ao cliente.");
      else if (horas < parQ().notificacaoClienteHoras) avisos.push("Notificação ao cliente com antecedência menor que " + parQ().notificacaoClienteHoras + " horas.");
    }
    var rnc = null;
    if (d.resultado === "Reprovado") {
      rnc = abrirRncDe({ projetoId: itp.projetoId, data: d.data, origem: "Inspeção", origemRef: n.codigo, disciplina: itp.disciplina, empresaId: itp.empresaId,
        descricao: ponto.atividade + " (" + itp.codigo + "): " + n.observacao, severidade: d.severidade, contencao: d.contencao });
      if (rnc.erros) return rejeitar(rnc.erros);
      n.rncRef = rnc.codigo;
    }
    colecao("inspecoesQualidade").push(n); persistir("inspecoesQualidade");
    return responder({ codigo: n.codigo, rnc: rnc ? rnc.codigo : null, avisos: avisos });
  }

  /* ---------------- Auditorias ---------------- */
  function auditoriaCalculada(a) {
    var x = copia(a);
    x.projetoCodigo = codigoProj(a.projetoId);
    x.atrasada = a.situacao === "Planejada" && a.data < REF;
    x.diasAtraso = x.atrasada ? R.diasEntre(a.data, REF) : 0;
    x.conformidadePct = a.situacao === "Realizada" && a.itensVerificados ? arred(a.itensConformes / a.itensVerificados * 100, 1) : null;
    var lista = a.constatacoes || [];
    x.constatacoesTotal = lista.length;
    x.porTipo = {};
    TIPOS_CONSTATACAO.forEach(function (t) { x.porTipo[t] = lista.filter(function (c) { return c.tipo === t; }).length; });
    x.ncAbertas = lista.filter(function (c) { var r = c.rncRef ? rncPorCodigo(c.rncRef) : null; return c.tipo === "Não conformidade" && r && rncAtiva(r); }).length;
    return x;
  }
  /* TODO: API GET /projetos/{id}/auditorias?situacao&tipo&busca */
  function listarAuditoriasDe(filtro) {
    filtro = filtro || {};
    var lista = doProjeto(M.auditorias, filtro.projetoId).map(auditoriaCalculada);
    if (filtro.situacao === "Atrasada") lista = lista.filter(function (a) { return a.atrasada; });
    else if (filtro.situacao) lista = lista.filter(function (a) { return a.situacao === filtro.situacao; });
    if (filtro.tipo) lista = lista.filter(function (a) { return a.tipo === filtro.tipo; });
    if (filtro.busca) {
      var t = U_norm(filtro.busca);
      lista = lista.filter(function (a) { return [a.codigo, a.escopo, nomeEmpresa(a.auditadoId)].some(function (v) { return U_norm(v).indexOf(t) >= 0; }); });
    }
    return lista.sort(function (a, b) { return a.data < b.data ? -1 : a.data > b.data ? 1 : 0; });
  }
  /* Planejar (nova) ou reprogramar (Planejada; mudança de data exige justificativa). TODO: API POST/PUT /auditorias */
  function salvarAuditoria(d, codigo) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite planejar auditorias.");
    var atual = codigo ? auditoriaPorCodigo(codigo) : null;
    if (codigo && !atual) return rejeitar("Auditoria não encontrada.");
    if (atual && atual.situacao !== "Planejada") return rejeitar("Só a auditoria planejada pode ser reprogramada.");
    var pid = atual ? atual.projetoId : Number(d.projetoId);
    if (!atual && semProjeto(pid)) return rejeitar("Escolha o projeto da auditoria.");
    var erros = [];
    if (TIPOS_AUDITORIA.indexOf(d.tipo) < 0) erros.push({ campo: "tipo", msg: "Escolha o tipo de auditoria." });
    if (!d.auditadoId) erros.push({ campo: "auditadoId", msg: "Escolha a empresa ou a área auditada." });
    if (!d.escopo || String(d.escopo).trim().length < 5) erros.push({ campo: "escopo", msg: "Informe o escopo (mínimo de 5 caracteres)." });
    if (!d.criterio || String(d.criterio).trim().length < 3) erros.push({ campo: "criterio", msg: "Informe os critérios (normas, procedimentos, contrato)." });
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data planejada." });
    else if (!atual && d.data < REF) erros.push({ campo: "data", msg: "A data planejada não pode ser anterior à referência." });
    if (!d.auditorId) erros.push({ campo: "auditorId", msg: "Escolha o auditor líder." });
    var mudouData = atual && d.data !== atual.data;
    if (mudouData && d.data < REF) erros.push({ campo: "data", msg: "A nova data não pode ser anterior à referência." });
    if (mudouData && (!d.justificativa || String(d.justificativa).trim().length < 10)) erros.push({ campo: "justificativa", msg: "Reprogramação exige justificativa (mínimo de 10 caracteres)." });
    if (erros.length) return rejeitar(erros);
    if (atual) {
      var antes = atual.data;
      atual.tipo = d.tipo; atual.auditadoId = Number(d.auditadoId); atual.escopo = String(d.escopo).trim(); atual.criterio = String(d.criterio).trim();
      atual.data = d.data; atual.auditorId = Number(d.auditorId);
      if (mudouData) atual.reprogramacoes = (atual.reprogramacoes || []).concat([{ de: antes, para: d.data, justificativa: String(d.justificativa).trim(), porId: sessaoPessoa(), quando: agoraIso() }]);
      persistir("auditorias");
      return responder({ codigo: atual.codigo, reprogramada: !!mudouData });
    }
    var pre = "AUD-" + padraoProjeto(pid) + "-";
    var n = doProjeto(M.auditorias, pid).filter(function (a) { return a.codigo.indexOf(pre) === 0; })
      .reduce(function (m, a) { return Math.max(m, parseInt(a.codigo.slice(pre.length), 10) || 0); }, 0);
    var a = { id: proximoId("auditorias"), projetoId: pid, codigo: pre + ("0" + (n + 1)).slice(-2), tipo: d.tipo, auditadoId: Number(d.auditadoId),
      escopo: String(d.escopo).trim(), criterio: String(d.criterio).trim(), data: d.data, situacao: "Planejada", auditorId: Number(d.auditorId) };
    colecao("auditorias").push(a); persistir("auditorias");
    return responder({ codigo: a.codigo });
  }
  /* Resultado: itens verificados e conformes, constatações; cada Não conformidade abre RNC (origem Auditoria).
     TODO: API PUT /auditorias/{codigo}/resultado */
  function registrarResultadoAuditoria(codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar auditorias.");
    var a = auditoriaPorCodigo(codigo);
    if (!a) return rejeitar("Auditoria não encontrada.");
    if (a.situacao !== "Planejada") return rejeitar("O resultado desta auditoria já foi registrado.");
    var erros = [];
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data de realização." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    var ver = Number(d.itensVerificados), conf = Number(d.itensConformes);
    if (!(ver >= 1)) erros.push({ campo: "itensVerificados", msg: "Informe os itens verificados (1 ou mais)." });
    if (!(conf >= 0) || conf > ver) erros.push({ campo: "itensConformes", msg: "Itens conformes entre zero e o total verificado." });
    var lista = d.constatacoes || [];
    lista.forEach(function (c, k) {
      if (TIPOS_CONSTATACAO.indexOf(c.tipo) < 0) erros.push({ campo: "constatacoes." + k + ".tipo", msg: "Constatação " + (k + 1) + ": escolha o tipo." });
      if (!c.descricao || String(c.descricao).trim().length < 10) erros.push({ campo: "constatacoes." + k + ".descricao", msg: "Constatação " + (k + 1) + ": descreva (mínimo de 10 caracteres)." });
      if (c.tipo === "Não conformidade") {
        if (!c.requisito || String(c.requisito).trim().length < 3) erros.push({ campo: "constatacoes." + k + ".requisito", msg: "Constatação " + (k + 1) + ": informe o requisito não atendido." });
        if (DISCIPLINAS_QUALIDADE.indexOf(c.disciplina) < 0) erros.push({ campo: "constatacoes." + k + ".disciplina", msg: "Constatação " + (k + 1) + ": escolha a disciplina da RNC." });
        if (SEVERIDADES_RNC.indexOf(c.severidade) < 0) erros.push({ campo: "constatacoes." + k + ".severidade", msg: "Constatação " + (k + 1) + ": escolha a severidade da RNC." });
      }
    });
    var ncs = lista.filter(function (c) { return c.tipo === "Não conformidade"; }).length;
    if (ver >= 1 && conf <= ver && ncs > ver - conf) erros.push({ campo: "itensConformes", msg: "Há mais não conformidades (" + ncs + ") que itens não conformes (" + (ver - conf) + ")." });
    if (erros.length) return rejeitar(erros);
    var abertas = [];
    a.constatacoes = lista.map(function (c) {
      var item = { tipo: c.tipo, descricao: String(c.descricao).trim(), requisito: String(c.requisito || "").trim() };
      if (c.tipo === "Não conformidade") {
        var r = abrirRncDe({ projetoId: a.projetoId, data: d.data, origem: "Auditoria", origemRef: a.codigo, disciplina: c.disciplina, empresaId: a.auditadoId,
          descricao: item.descricao + " Requisito: " + item.requisito + ".", severidade: c.severidade, contencao: "Contenção a definir pelo auditado em até 48 horas da auditoria " + a.codigo + "." });
        if (!r.erros) { item.rncRef = r.codigo; abertas.push(r.codigo); }
      }
      return item;
    });
    a.situacao = "Realizada"; a.realizadaEm = d.data; a.itensVerificados = ver; a.itensConformes = conf; a.resumo = String(d.resumo || "").trim();
    persistir("auditorias");
    return responder({ codigo: codigo, rncs: abertas });
  }

  /* ---------------- Indicadores e painel ---------------- */
  function indicadoresQualidadeDe(projetoId) {
    var rncs = doProjeto(M.rncs, projetoId).map(rncCalculada);
    var ativas = rncs.filter(function (r) { return r.ativa; });
    var encerradas = rncs.filter(function (r) { return r.situacao === "Encerrada"; });
    var insp = doProjeto(M.inspecoesQualidade, projetoId);
    var aud = doProjeto(M.auditorias, projetoId).map(auditoriaCalculada);
    var realizadas = aud.filter(function (a) { return a.situacao === "Realizada"; });
    var previstasAteHoje = aud.filter(function (a) { return a.data <= REF; });
    var itps = doProjeto(M.itps, projetoId);
    return {
      rncAbertas: ativas.length, rncEncerradas: encerradas.length,
      rncVencidas: rncs.filter(function (r) { return r.vencida; }).length,
      verificacoesVencidas: rncs.filter(function (r) { return r.verificacaoVencida; }).length,
      rncCriticasAbertas: ativas.filter(function (r) { return r.severidade === "Crítica"; }).length,
      tempoMedioTratamentoDias: encerradas.length ? Math.round(soma(encerradas, function (r) { return R.diasEntre(r.data, r.encerramento); }) / encerradas.length) : null,
      eficaciaPrimeiraPct: encerradas.length ? arred(encerradas.filter(function (r) { return !r.reincidencias; }).length / encerradas.length * 100, 1) : null,
      inspecoes: insp.length, inspecoesReprovadas: insp.filter(function (i) { return i.resultado === "Reprovado"; }).length,
      aprovacaoInspecoesPct: insp.length ? arred(insp.filter(aprovadaInspecao).length / insp.length * 100, 1) : null,
      metaAprovacaoInspecaoPct: parQ().metaAprovacaoInspecaoPct,
      conformidadeAuditoriasPct: realizadas.length ? arred(soma(realizadas, "itensConformes") / soma(realizadas, "itensVerificados") * 100, 1) : null,
      metaConformidadeAuditoriaPct: parQ().metaConformidadeAuditoriaPct,
      auditoriasRealizadas: realizadas.length, auditoriasPrevistasAteHoje: previstasAteHoje.length,
      aderenciaProgramaPct: previstasAteHoje.length ? arred(previstasAteHoje.filter(function (a) { return a.situacao === "Realizada"; }).length / previstasAteHoje.length * 100, 1) : null,
      auditoriasAtrasadas: aud.filter(function (a) { return a.atrasada; }).length,
      ncAuditoriaAbertas: soma(aud, "ncAbertas"),
      itps: itps.length, itpsSemAprovacao: itps.filter(function (i) { return !i.aprovadoCliente; }).length,
      custoNaoQualidadeCentavos: soma(rncs, "custoNaoQualidadeCentavos")
    };
  }
  function indicadoresQualidade(projetoId) { return responder(indicadoresQualidadeDe(projetoId)); }
  /* Painel: indicadores, série de 6 meses, Pareto por disciplina, empresas, origens e pauta.
     TODO: API GET /projetos/{id}/qualidade/painel */
  function painelQualidadeDe(projetoId) {
    var rncs = doProjeto(M.rncs, projetoId).map(rncCalculada);
    var insp = doProjeto(M.inspecoesQualidade, projetoId);
    var serie = serieQualidade(rncs, insp, mesDe(REF));
    return montarPainelQualidade(projetoId, rncs, insp, serie);
  }
  function seisMeses(ultimo) {
    var meses = [], d = new Date(ultimo + "-01T00:00:00");
    for (var k = 0; k < 6; k++) { meses.unshift(d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0")); d.setMonth(d.getMonth() - 1); }
    return meses;
  }
  function serieQualidade(rncs, insp, ultimo) {
    return seisMeses(ultimo).map(function (m) {
      var im = insp.filter(function (i) { return mesDe(i.data) === m; });
      return { mes: m, abertas: rncs.filter(function (r) { return mesDe(r.data) === m; }).length,
        encerradas: rncs.filter(function (r) { return r.situacao === "Encerrada" && mesDe(r.encerramento) === m; }).length,
        emAberto: rncs.filter(function (r) { var fim = r.encerramento ? mesDe(r.encerramento) : null; return mesDe(r.data) <= m && (!fim || fim > m); }).length,
        inspecoes: im.length, aprovacaoPct: im.length ? arred(im.filter(aprovadaInspecao).length / im.length * 100, 1) : null };
    });
  }
  function montarPainelQualidade(projetoId, rncs, insp, serie) {
    function agrupar(chave, nome) {
      var g = {};
      rncs.filter(function (r) { return r.situacao !== "Cancelada"; }).forEach(function (r) {
        var c = chave(r);
        if (!g[c]) g[c] = { chave: c, nome: nome(c), total: 0, ativas: 0, custoCentavos: 0 };
        g[c].total++; if (r.ativa) g[c].ativas++; g[c].custoCentavos += r.custoNaoQualidadeCentavos || 0;
      });
      var lista = Object.keys(g).map(function (k) { return g[k]; }).sort(function (a, b) { return b.total - a.total || b.custoCentavos - a.custoCentavos; });
      var tot = soma(lista, "total"), acum = 0;
      lista.forEach(function (x) { acum += x.total; x.pct = tot ? arred(x.total / tot * 100, 1) : 0; x.acumuladoPct = tot ? arred(acum / tot * 100, 1) : 0; });
      return lista;
    }
    var empresas = {};
    insp.forEach(function (i) {
      var e = empresas[i.empresaId] || (empresas[i.empresaId] = { empresaId: i.empresaId, nome: nomeEmpresa(i.empresaId), inspecoes: 0, reprovadas: 0, rncs: 0, custoCentavos: 0 });
      e.inspecoes++; if (i.resultado === "Reprovado") e.reprovadas++;
    });
    rncs.filter(function (r) { return r.situacao !== "Cancelada"; }).forEach(function (r) {
      var e = empresas[r.empresaId] || (empresas[r.empresaId] = { empresaId: r.empresaId, nome: nomeEmpresa(r.empresaId), inspecoes: 0, reprovadas: 0, rncs: 0, custoCentavos: 0 });
      e.rncs++; e.custoCentavos += r.custoNaoQualidadeCentavos || 0;
    });
    var porEmpresa = Object.keys(empresas).map(function (k) {
      var e = empresas[k]; e.aprovacaoPct = e.inspecoes ? arred((e.inspecoes - e.reprovadas) / e.inspecoes * 100, 1) : null; return e;
    }).sort(function (a, b) { return b.rncs - a.rncs || b.custoCentavos - a.custoCentavos; });
    var pauta = rncs.filter(function (r) { return r.vencida || r.verificacaoVencida || (r.ativa && r.severidade === "Crítica") || r.concessaoPendente; }).map(function (r) {
      var motivos = [];
      if (r.vencida) motivos.push("prazo de tratamento vencido há " + r.diasAtraso + (r.diasAtraso === 1 ? " dia" : " dias"));
      if (r.verificacaoVencida) motivos.push("verificação de eficácia vencida");
      if (r.ativa && r.severidade === "Crítica") motivos.push("severidade crítica");
      if (r.concessaoPendente) motivos.push("concessão do cliente pendente");
      r.motivos = motivos; return r;
    }).sort(function (a, b) { return b.diasAtraso - a.diasAtraso; });
    return { indicadores: indicadoresQualidadeDe(projetoId), serie: serie,
      porDisciplina: agrupar(function (r) { return r.disciplina; }, function (c) { return c; }),
      porOrigem: agrupar(function (r) { return r.origem; }, function (c) { return c; }),
      porSeveridade: SEVERIDADES_RNC.map(function (s) { return { severidade: s, ativas: rncs.filter(function (r) { return r.ativa && r.severidade === s; }).length }; }),
      porEmpresa: porEmpresa, pauta: pauta,
      auditoriasAtrasadas: listarAuditoriasDe({ projetoId: projetoId, situacao: "Atrasada" }) };
  }

  /* ======================================================================
     07 HSE
     ====================================================================== */
  var LTI = ["Fatalidade", "Acidente com afastamento"];
  var REGISTRAVEIS = ["Fatalidade", "Acidente com afastamento", "Trabalho restrito", "Tratamento médico"];
  function indicadoresHSEDe(projetoId, periodo) {
    periodo = periodo || {};
    var ini = periodo.inicio || REF.slice(0, 4) + "-01", fim = periodo.fim || mesDe(REF);
    var dentro = function (mes) { return mes >= ini && mes <= fim; };
    var par = P().hse;
    var hht = soma(doProjeto(M.hht, projetoId).filter(function (r) { return dentro(r.mes); }), "hht");
    var todas = doProjeto(M.ocorrencias, projetoId);
    var oc = todas.filter(function (o) { return dentro(mesDe(o.dataHora)) && !o.ambiental; });
    var conta = function (tipos) { return oc.filter(function (o) { return tipos.indexOf(o.tipo) >= 0; }).length; };
    var mensal = doProjeto(M.hseMensal, projetoId).filter(function (r) { return dentro(r.mes); });
    var niveis = [0, 0, 0, 0, 0];
    oc.forEach(function (o) { var n = R.nivelPiramide(o.tipo); if (n) niveis[n - 1]++; });
    niveis[4] = soma(mensal, "desvios");
    var ultimaLTI = todas.filter(function (o) { return LTI.indexOf(o.tipo) >= 0; }).map(function (o) { return o.dataHora.slice(0, 10); }).sort().pop();
    var inicioProj = projetoId == null ? inicioCarteira() : (porId(M.projetos)[projetoId] || {}).inicio;
    var recs = [];
    doProjeto(M.analisesRisco, projetoId).forEach(function (a) { recs = recs.concat(a.recomendacoes); });
    var acoesHSE = acoesComStatus(function (a) { return (a.origem === "HSE" || a.grupo === "HSE") && (projetoId == null || a.projetoId === projetoId) && a.ehAcao; });
    var vencidas = acoesHSE.filter(function (a) { return (a.replanejada || a.prevista) <= REF; });
    var noPrazo = vencidas.filter(function (a) { return a.conclusao && a.conclusao <= (a.replanejada || a.prevista); });
    var lti = conta(LTI), reg = conta(REGISTRAVEIS);
    return {
      periodo: { inicio: ini, fim: fim }, base: par.baseTaxa, hht: hht,
      lti: lti, registraveis: reg,
      tf: arred(R.taxaHSE(lti, hht, par.baseTaxa), 2),
      trif: arred(R.taxaHSE(reg, hht, par.baseTaxa), 2),
      tg: arred(R.taxaHSE(soma(oc, function (o) { return (o.diasPerdidos || 0) + (o.diasDebitados || 0); }), hht, par.baseTaxa), 1),
      /* Sem LTI registrada, a contagem começa no início do projeto (boa prática: dias sem afastamento desde a mobilização) */
      ultimaLTI: ultimaLTI || null, inicioContagem: ultimaLTI || inicioProj || null,
      diasSemAfastamento: (ultimaLTI || inicioProj) ? Math.max(0, R.diasEntre(ultimaLTI || inicioProj, REF)) : null,
      hipo: oc.filter(function (o) { return o.hipo; }).length,
      hipoMes: oc.filter(function (o) { return o.hipo && mesDe(o.dataHora) === mesDe(REF); }).length,
      ambientais: todas.filter(function (o) { return o.ambiental && dentro(mesDe(o.dataHora)); }).length,
      piramide: niveis,
      relatoQuaseAcidente: reg ? arred(niveis[3] / reg, 1) : null,
      ddsPct: arred(soma(mensal, "ddsRealizados") / soma(mensal, "ddsProgramados") * 100, 1),
      conformidadeInspecoesPct: arred(soma(mensal, "itensConformes") / soma(mensal, "itensInspecionados") * 100, 1),
      observacoesPor10k: hht ? arred(soma(mensal, "observacoes") / hht * 10000, 1) : null,
      recomendacoesFechadasPct: recs.length ? arred(recs.filter(function (r) { return r.situacao === "Fechada"; }).length / recs.length * 100, 1) : null,
      acoesNoPrazoPct: vencidas.length ? arred(noPrazo.length / vencidas.length * 100, 1) : null,
      comunicacoesForaDoPrazo: oc.filter(function (o) { return o.comunicacaoHoras > par.prazos.comunicacaoHoras; }).length
    };
  }
  /* TODO: API GET /projetos/{id}/indicadores-hse?inicio&fim */
  function indicadoresHSE(projetoId, periodo) { return responder(indicadoresHSEDe(projetoId, periodo)); }
  /* Painel: indicadores do período + evolução mensal (TF, TRIF) + distribuição por área e por empresa.
     TODO: API GET /projetos/{id}/hse/painel?inicio&fim */
  function mesesComHht(projetoId) {
    var set = {};
    doProjeto(M.hht, projetoId).forEach(function (r) { set[r.mes] = true; });
    return Object.keys(set).sort();
  }
  function painelHSEDe(projetoId, periodo) {
    var ind = indicadoresHSEDe(projetoId, periodo);
    var evolucao = mesesComHht(projetoId).map(function (mes) {
      var d = indicadoresHSEDe(projetoId, { inicio: mes, fim: mes });
      return { mes: mes, tf: d.tf, trif: d.trif };
    });
    var ini = (periodo && periodo.inicio) || REF.slice(0, 4) + "-01", fim = (periodo && periodo.fim) || mesDe(REF);
    var dentro = function (mes) { return mes >= ini && mes <= fim; };
    var oc = doProjeto(M.ocorrencias, projetoId).filter(function (o) { return dentro(mesDe(o.dataHora)) && !o.ambiental; });
    function contarPor(campo) {
      var por = {};
      oc.forEach(function (o) { var k = String(o[campo]); por[k] = (por[k] || 0) + 1; });
      return Object.keys(por).map(function (k) { return { chave: campo === "empresaId" ? Number(k) : k, total: por[k] }; }).sort(function (a, b) { return b.total - a.total; });
    }
    return { indicadores: ind, evolucao: evolucao, porArea: contarPor("area"), porEmpresa: contarPor("empresaId") };
  }
  function painelHSE(projetoId, periodo) { return responder(painelHSEDe(projetoId, periodo)); }

  /* ---------------- 07 HSE: registro e fluxo das ocorrências ----------------
     Ciclo: Registrada -> Em investigação -> Ações definidas -> Em tratamento -> Encerrada.
     Nível 5 (desvios) não tem registro individual (vem consolidado de hseMensal; ver mock-hse.js). */
  var NIVEIS_PIRAMIDE_NOMES = ["Lesão grave", "Lesão leve", "Dano material", "Quase acidente", "Desvio"];
  var TIPOS_OCORRENCIA_PIRAMIDE = {
    1: ["Fatalidade", "Acidente com afastamento"],
    2: ["Trabalho restrito", "Tratamento médico", "Primeiros socorros"],
    3: ["Dano material"],
    4: ["Quase acidente"]
  };
  var TIPOS_COM_FUNCAO = ["Fatalidade", "Acidente com afastamento", "Trabalho restrito", "Tratamento médico", "Primeiros socorros"];
  var SITUACOES_OCORRENCIA = ["Registrada", "Em investigação", "Ações definidas", "Em tratamento", "Encerrada"];
  var METODOS_INVESTIGACAO = ["5 porquês", "Árvore de causas"];
  var CAUSAS_IMEDIATAS_HSE = ["Procedimento não seguido", "Condição insegura do local", "Falha de planejamento da tarefa",
    "EPI inadequado", "Falta de sinalização", "Equipamento sem inspeção", "Outra"];
  var SUBTIPOS_AMBIENTAL = ["Vazamento", "Emissão", "Resíduo", "Outro"];
  var SEVERIDADES_AMBIENTAL = ["Baixa", "Moderada", "Alta"];

  function ocorrenciaPorCodigo(codigo) { return porCampo(M.ocorrencias, "codigo", codigo); }
  function acoesDaOcorrencia(codigo) { return acoesComStatus(function (a) { return a.origem === "HSE" && a.origemRef === codigo; }); }
  function historicoOcorrencia(o, texto) {
    if (!o.historico) o.historico = [{ quando: o.dataHora, porId: null, texto: "Ocorrência registrada." }];
    o.historico.unshift({ quando: agoraIso(), porId: sessaoPessoa(), texto: texto });
  }
  /* Visão calculada: nível da pirâmide, faixa do potencial, prazos (comunicação, investigação
     preliminar e relatório final de LTI/HiPo) e ações vinculadas na Central. Prazos em horas são
     comparados em dias (granularidade das datas do protótipo); TODO: API prazos com data e hora. */
  function ocorrenciaCalculada(o) {
    if (!o) return null;
    var x = copia(o);
    var par = P().hse.prazos;
    var dataEvento = o.dataHora.slice(0, 10);
    x.nivel = R.nivelPiramide(o.tipo);
    x.nivelNome = x.nivel ? NIVEIS_PIRAMIDE_NOMES[x.nivel - 1] : (o.ambiental ? "Ambiental" : null);
    x.potencialFaixa = o.potencial ? R.faixaPotencialHSE(o.potencial.p, o.potencial.i) : null;
    x.prazoComunicacao = o.comunicacaoHoras == null ? null : { horas: o.comunicacaoHoras, foraDoPrazo: o.comunicacaoHoras > par.comunicacaoHoras };
    var diasInvestigacao = Math.ceil(par.investigacaoPreliminarHoras / 24);
    x.prazoInvestigacao = o.investigacao
      ? { data: o.investigacao.data, foraDoPrazo: R.diasEntre(dataEvento, o.investigacao.data) > diasInvestigacao }
      : { vencido: o.situacao === "Registrada" && R.diasEntre(dataEvento, REF) > diasInvestigacao };
    var exigeRelatorio = x.nivel === 1 || o.hipo;
    if (exigeRelatorio) {
      var limite = somarDiasIso(dataEvento, par.relatorioFinalDias);
      x.prazoRelatorio = o.encerramento ? { exige: true, limite: limite, foraDoPrazo: o.encerramento.data > limite }
        : { exige: true, limite: limite, vencido: REF > limite };
    } else x.prazoRelatorio = { exige: false };
    var acoes = acoesDaOcorrencia(o.codigo);
    x.acoesTotal = acoes.length; x.acoesAbertas = acoes.filter(function (a) { return a.ehAcao && a.status !== "concluida"; }).length;
    return x;
  }
  /* TODO: API GET /projetos/{id}/ocorrencias?situacao&tipo&area&empresaId&hipo&ambiental&busca */
  function listarOcorrenciasDe(filtro) {
    filtro = filtro || {};
    var lista = doProjeto(M.ocorrencias, filtro.projetoId).map(ocorrenciaCalculada);
    if (filtro.situacao) lista = lista.filter(function (o) { return o.situacao === filtro.situacao; });
    if (filtro.tipo) lista = lista.filter(function (o) { return o.tipo === filtro.tipo; });
    if (filtro.area) lista = lista.filter(function (o) { return o.area === filtro.area; });
    if (filtro.empresaId) lista = lista.filter(function (o) { return o.empresaId === Number(filtro.empresaId); });
    if (filtro.hipo) lista = lista.filter(function (o) { return o.hipo; });
    if (filtro.ambiental != null) lista = lista.filter(function (o) { return !!o.ambiental === !!filtro.ambiental; });
    if (filtro.busca) {
      var t = U_norm(filtro.busca);
      lista = lista.filter(function (o) { return U_norm(o.codigo).indexOf(t) >= 0 || U_norm(o.area).indexOf(t) >= 0 || U_norm(o.descricao || "").indexOf(t) >= 0; });
    }
    lista.sort(function (a, b) { return a.dataHora < b.dataHora ? 1 : a.dataHora > b.dataHora ? -1 : 0; });
    return lista;
  }
  function listarOcorrencias(filtro) { return responder(listarOcorrenciasDe(filtro)); }
  /* TODO: API GET /ocorrencias/{codigo} */
  function obterOcorrencia(codigo) {
    var o = ocorrenciaCalculada(ocorrenciaPorCodigo(codigo));
    if (o) { o.acoesLista = acoesDaOcorrencia(codigo); o.historicoExibicao = (ocorrenciaPorCodigo(codigo).historico || [{ quando: o.dataHora, porId: null, texto: "Ocorrência registrada." }]); }
    return responder(o);
  }
  /* TODO: API POST /projetos/{id}/ocorrencias */
  function salvarOcorrencia(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar ocorrências.");
    var ambiental = d.tipo === "Ambiental";
    var erros = [];
    if (!d.dataHora) erros.push({ campo: "dataHora", msg: "Informe a data e a hora." });
    else if (d.dataHora.slice(0, 10) > REF) erros.push({ campo: "dataHora", msg: "A data não pode ser posterior à referência." });
    if (!d.area) erros.push({ campo: "area", msg: "Informe a área ou o local." });
    if (!d.empresaId) erros.push({ campo: "empresaId", msg: "Escolha a empresa." });
    if (!d.tipo) erros.push({ campo: "tipo", msg: "Escolha o tipo de ocorrência." });
    if (ambiental) {
      if (!d.subtipo) erros.push({ campo: "subtipo", msg: "Escolha o subtipo ambiental." });
      if (!d.severidadeAmbiental) erros.push({ campo: "severidadeAmbiental", msg: "Escolha a severidade." });
    } else {
      if (!d.descricao || d.descricao.trim().length < 10) erros.push({ campo: "descricao", msg: "Descreva o ocorrido (mínimo de 10 caracteres)." });
      if (!d.causaImediata) erros.push({ campo: "causaImediata", msg: "Escolha a causa imediata." });
      if (!d.potencialP || !d.potencialI) erros.push({ campo: "potencialP", msg: "Informe a probabilidade e o impacto potenciais." });
      if (!d.gravidadeReal) erros.push({ campo: "gravidadeReal", msg: "Informe a gravidade real observada." });
      if (TIPOS_COM_FUNCAO.indexOf(d.tipo) >= 0 && !d.funcao) erros.push({ campo: "funcao", msg: "Informe a função da pessoa envolvida (sem nome, por LGPD)." });
    }
    if (erros.length) return rejeitar(erros);
    if (semProjeto(d.projetoId)) return rejeitar("Escolha o projeto da ocorrência.");
    var codigo = proximoCodigo("ocorrencias", "OCR-" + ((porId(M.projetos)[Number(d.projetoId)] || {}).padraoAta || "TN-2026") + "-");
    var o = {
      id: proximoId("ocorrencias"), codigo: codigo, projetoId: d.projetoId, dataHora: d.dataHora, area: d.area,
      empresaId: Number(d.empresaId), tipo: d.tipo, descricao: ambiental ? "" : String(d.descricao).trim(),
      funcao: ambiental ? null : (d.funcao || null), pessoasEnvolvidas: ambiental ? 0 : Number(d.pessoasEnvolvidas || 0),
      gravidadeReal: ambiental ? null : Number(d.gravidadeReal),
      potencial: ambiental ? null : { p: Number(d.potencialP), i: Number(d.potencialI) },
      hipo: !ambiental && !!d.hipo, diasPerdidos: Number(d.diasPerdidos || 0), diasDebitados: Number(d.diasDebitados || 0),
      cat: !ambiental && !!d.cat, causaImediata: ambiental ? null : d.causaImediata,
      comunicacaoHoras: Number(d.comunicacaoHoras || 0), ambiental: ambiental,
      subtipo: ambiental ? d.subtipo : null, severidadeAmbiental: ambiental ? d.severidadeAmbiental : null,
      situacao: "Registrada"
    };
    historicoOcorrencia(o, "Ocorrência registrada.");
    colecao("ocorrencias").push(o); persistir("ocorrencias");
    var avisos = [];
    if (o.comunicacaoHoras > P().hse.prazos.comunicacaoHoras) avisos.push("Comunicação registrada fora do prazo de " + P().hse.prazos.comunicacaoHoras + " horas.");
    return responder({ codigo: codigo, avisos: avisos });
  }
  /* TODO: API PUT /ocorrencias/{codigo}/investigacao */
  function investigarOcorrencia(codigo, d) {
    var o = ocorrenciaPorCodigo(codigo);
    if (!o) return rejeitar("Ocorrência não encontrada.");
    if (o.situacao !== "Registrada") return rejeitar("Esta ocorrência já foi investigada.");
    if (!d.metodo || METODOS_INVESTIGACAO.indexOf(d.metodo) < 0) return rejeitar({ campo: "metodo", msg: "Escolha o método de investigação." });
    if (!d.causaRaiz || d.causaRaiz.trim().length < 10) return rejeitar({ campo: "causaRaiz", msg: "Descreva a causa raiz (mínimo de 10 caracteres)." });
    if (!d.data) return rejeitar({ campo: "data", msg: "Informe a data da investigação." });
    if (d.data > REF) return rejeitar({ campo: "data", msg: "A data não pode ser posterior à referência." });
    if (d.data < o.dataHora.slice(0, 10)) return rejeitar({ campo: "data", msg: "A data não pode ser anterior à do evento." });
    o.investigacao = { metodo: d.metodo, causaRaiz: d.causaRaiz.trim(), data: d.data, porId: sessaoPessoa() };
    o.situacao = "Em investigação";
    var diasLimite = Math.ceil(P().hse.prazos.investigacaoPreliminarHoras / 24);
    var foraDoPrazo = R.diasEntre(o.dataHora.slice(0, 10), d.data) > diasLimite;
    historicoOcorrencia(o, "Investigação registrada (" + d.metodo + "). Causa raiz: " + d.causaRaiz.trim() + (foraDoPrazo ? " · fora do prazo preliminar." : "."));
    persistir("ocorrencias");
    return responder({ codigo: codigo, foraDoPrazo: foraDoPrazo });
  }
  /* Ações corretivas (uma ou mais); vão para a Central com origem HSE. TODO: API POST /ocorrencias/{codigo}/acoes */
  function definirAcoesOcorrencia(codigo, lista) {
    var o = ocorrenciaPorCodigo(codigo);
    if (!o) return rejeitar("Ocorrência não encontrada.");
    if (o.situacao === "Registrada") return rejeitar("Investigue a ocorrência antes de definir as ações.");
    if (o.situacao === "Encerrada") return rejeitar("Ocorrência já encerrada.");
    if (!lista || !lista.length) return rejeitar("Inclua ao menos uma ação corretiva.");
    var erros = [];
    lista.forEach(function (a, i) {
      if (!a.assunto || !a.assunto.trim()) erros.push({ msg: "Ação " + (i + 1) + ": informe o assunto." });
      if (!a.responsavelId) erros.push({ msg: "Ação " + (i + 1) + ": escolha o responsável." });
      if (!a.prevista) erros.push({ msg: "Ação " + (i + 1) + ": informe a data prevista." });
    });
    if (erros.length) return rejeitar(erros);
    var itemBase = o.acoesItens || 0;
    var criadas = lista.map(function (a, i) {
      var acao = { id: proximoId("acoes"), projetoId: o.projetoId, origem: "HSE", origemRef: o.codigo, item: String(itemBase + i + 1),
        grupo: "Ação corretiva", tipo: "Ação", assunto: a.assunto.trim(), descricao: a.descricao || "",
        solicitanteId: sessaoPessoa(), responsavelId: Number(a.responsavelId), prevista: a.prevista, replanejada: null, conclusao: null };
      colecao("acoes").push(acao);
      return acao;
    });
    o.acoesItens = itemBase + lista.length;
    if (o.situacao === "Em investigação") o.situacao = "Ações definidas";
    historicoOcorrencia(o, U_plural(criadas.length, "ação corretiva criada", "ações corretivas criadas") + " na Central.");
    persistir("acoes"); persistir("ocorrencias");
    return responder({ codigo: codigo, criadas: criadas.length });
  }
  function U_plural(n, singular, pluralTxt) { return n + " " + (n === 1 ? singular : pluralTxt); }
  /* TODO: API PUT /ocorrencias/{codigo}/tratamento */
  function iniciarTratamentoOcorrencia(codigo) {
    var o = ocorrenciaPorCodigo(codigo);
    if (!o) return rejeitar("Ocorrência não encontrada.");
    if (o.situacao !== "Ações definidas") return rejeitar("Defina as ações corretivas antes de iniciar o tratamento.");
    o.situacao = "Em tratamento";
    historicoOcorrencia(o, "Tratamento iniciado.");
    persistir("ocorrencias");
    return responder({ codigo: codigo });
  }
  /* Encerramento com verificação de eficácia; exige as ações corretivas concluídas. TODO: API PUT /ocorrencias/{codigo}/encerramento */
  function encerrarOcorrencia(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Encerrar ocorrência exige papel Gestor.");
    var o = ocorrenciaPorCodigo(codigo);
    if (!o) return rejeitar("Ocorrência não encontrada.");
    if (o.situacao === "Encerrada") return rejeitar("Ocorrência já encerrada.");
    if (o.situacao !== "Em tratamento") return rejeitar("Só é possível encerrar depois de iniciado o tratamento.");
    var abertas = acoesDaOcorrencia(codigo).filter(function (a) { return a.ehAcao && a.status !== "concluida"; });
    if (abertas.length) return rejeitar((abertas.length === 1 ? "Existe 1 ação corretiva em aberto" : "Existem " + abertas.length + " ações corretivas em aberto") + ". Conclua-as antes de encerrar.");
    if (!d.eficacia || d.eficacia.trim().length < 10) return rejeitar({ campo: "eficacia", msg: "Registre a verificação de eficácia (mínimo de 10 caracteres)." });
    if (!d.data) return rejeitar({ campo: "data", msg: "Informe a data do encerramento." });
    if (d.data > REF) return rejeitar({ campo: "data", msg: "A data não pode ser posterior à referência." });
    if (d.data < o.dataHora.slice(0, 10)) return rejeitar({ campo: "data", msg: "A data não pode ser anterior à do evento." });
    o.encerramento = { data: d.data, eficacia: d.eficacia.trim(), porId: sessaoPessoa() };
    o.situacao = "Encerrada";
    var par = P().hse.prazos, exigeRel = R.nivelPiramide(o.tipo) === 1 || o.hipo;
    var foraDoPrazo = exigeRel && d.data > somarDiasIso(o.dataHora.slice(0, 10), par.relatorioFinalDias);
    historicoOcorrencia(o, "Ocorrência encerrada. Eficácia: " + d.eficacia.trim() + (foraDoPrazo ? " · relatório final fora do prazo de " + par.relatorioFinalDias + " dias." : "."));
    persistir("ocorrencias");
    return responder({ codigo: codigo, relatorioForaDoPrazo: !!foraDoPrazo });
  }

  /* ---------------- 07 HSE: horas trabalhadas (HHT) ---------------- */
  /* TODO: API GET /projetos/{id}/hht?inicio&fim */
  /* Histograma de mão de obra previsto (HHT e efetivo por mês). TODO: API GET /projetos/{id}/histograma-mao-de-obra */
  function histogramaDe(projetoId) { return doProjeto(M.histogramaMaoDeObra || [], projetoId).map(copia); }
  function hhtPrevistoDe(projetoId, ateMes, soMes) {
    var l = histogramaDe(projetoId).filter(function (h) { return soMes ? h.mes === ateMes : !ateMes || h.mes <= ateMes; });
    return l.length ? { hht: soma(l, "hhtPrevisto"), efetivo: soma(l, "efetivoPrevisto") } : null;
  }
  function listarHht(filtro) {
    filtro = filtro || {};
    return doProjeto(M.hht, filtro.projetoId).slice().sort(function (a, b) { return a.mes === b.mes ? a.empresaId - b.empresaId : (a.mes < b.mes ? 1 : -1); });
  }
  /* Upsert por mês e empresa (formulário ou linha da importação). TODO: API POST/PUT /projetos/{id}/hht */
  function salvarHht(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar HHT.");
    if (!d.mes || !/^\d{4}-\d{2}$/.test(d.mes)) return rejeitar({ campo: "mes", msg: "Informe o mês (AAAA-MM)." });
    if (d.mes > mesDe(REF)) return rejeitar({ campo: "mes", msg: "Não é possível registrar um mês futuro em relação à referência." });
    if (!d.empresaId) return rejeitar({ campo: "empresaId", msg: "Escolha a empresa." });
    if (d.efetivoMedio == null || Number(d.efetivoMedio) < 0) return rejeitar({ campo: "efetivoMedio", msg: "Informe o efetivo médio (0 ou mais)." });
    if (d.hht == null || Number(d.hht) < 0) return rejeitar({ campo: "hht", msg: "Informe as horas-homem trabalhadas (0 ou mais)." });
    var lista = colecao("hht");
    var existente = lista.filter(function (r) { return r.projetoId === d.projetoId && r.mes === d.mes && r.empresaId === Number(d.empresaId); })[0];
    if (existente) { existente.efetivoMedio = Number(d.efetivoMedio); existente.hht = Number(d.hht); }
    else lista.push({ projetoId: d.projetoId, mes: d.mes, empresaId: Number(d.empresaId), efetivoMedio: Number(d.efetivoMedio), hht: Number(d.hht) });
    persistir("hht");
    return responder({ mes: d.mes, empresaId: Number(d.empresaId), novo: !existente });
  }

  /* ---------------- 07 HSE: inspeções, observações e DDS (consolidado mensal) ----------------
     Sem registro individual no protótipo (ver mock-hse.js); a entrada grava o total do mês. */
  /* TODO: API GET /projetos/{id}/hse-mensal?inicio&fim */
  function listarHseMensal(filtro) {
    filtro = filtro || {};
    return doProjeto(M.hseMensal, filtro.projetoId).slice().sort(function (a, b) { return a.mes < b.mes ? 1 : -1; });
  }
  /* TODO: API POST/PUT /projetos/{id}/hse-mensal */
  function salvarHseMensal(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar estes dados.");
    if (!d.mes || !/^\d{4}-\d{2}$/.test(d.mes)) return rejeitar({ campo: "mes", msg: "Informe o mês (AAAA-MM)." });
    if (d.mes > mesDe(REF)) return rejeitar({ campo: "mes", msg: "Não é possível registrar um mês futuro em relação à referência." });
    var campos = ["ddsProgramados", "ddsRealizados", "itensInspecionados", "itensConformes", "observacoes", "desvios"];
    for (var k = 0; k < campos.length; k++) {
      if (d[campos[k]] == null || Number(d[campos[k]]) < 0) return rejeitar({ campo: campos[k], msg: "Informe um valor de 0 ou mais." });
    }
    if (Number(d.ddsRealizados) > Number(d.ddsProgramados)) return rejeitar({ campo: "ddsRealizados", msg: "Não pode ser maior que o programado." });
    if (Number(d.itensConformes) > Number(d.itensInspecionados)) return rejeitar({ campo: "itensConformes", msg: "Não pode ser maior que o inspecionado." });
    var lista = colecao("hseMensal");
    var existente = lista.filter(function (r) { return r.projetoId === d.projetoId && r.mes === d.mes; })[0];
    var registro = { projetoId: d.projetoId, mes: d.mes, desvios: Number(d.desvios), observacoes: Number(d.observacoes),
      ddsProgramados: Number(d.ddsProgramados), ddsRealizados: Number(d.ddsRealizados),
      itensInspecionados: Number(d.itensInspecionados), itensConformes: Number(d.itensConformes) };
    if (existente) { Object.keys(registro).forEach(function (k2) { existente[k2] = registro[k2]; }); } else lista.push(registro);
    persistir("hseMensal");
    return responder({ mes: d.mes, novo: !existente });
  }

  /* ---------------- 07 HSE: análises de risco (APR/JSA e HAZOP) ---------------- */
  function analisePorCodigo(codigo) { return porCampo(M.analisesRisco, "codigo", codigo); }
  function analiseCalculada(a) {
    var x = copia(a);
    x.abertas = x.recomendacoes.filter(function (r) { return r.situacao === "Aberta"; }).length;
    x.fechadas = x.recomendacoes.filter(function (r) { return r.situacao === "Fechada"; }).length;
    x.atrasadas = x.recomendacoes.filter(function (r) { return r.situacao === "Aberta" && r.prazo < REF; }).length;
    return x;
  }
  /* TODO: API GET /projetos/{id}/analises-risco?tipo&area&busca */
  function listarAnalisesRiscoDe(filtro) {
    filtro = filtro || {};
    var lista = doProjeto(M.analisesRisco, filtro.projetoId).map(analiseCalculada);
    if (filtro.tipo) lista = lista.filter(function (a) { return a.tipo === filtro.tipo; });
    if (filtro.area) lista = lista.filter(function (a) { return a.area === filtro.area; });
    if (filtro.situacao === "abertas") lista = lista.filter(function (a) { return a.abertas > 0; });
    if (filtro.busca) {
      var t = U_norm(filtro.busca);
      lista = lista.filter(function (a) { return U_norm(a.codigo).indexOf(t) >= 0 || U_norm(a.titulo).indexOf(t) >= 0 || U_norm(a.area).indexOf(t) >= 0; });
    }
    lista.sort(function (a, b) { return a.data < b.data ? 1 : a.data > b.data ? -1 : 0; });
    return lista;
  }
  function listarAnalisesRisco(filtro) { return responder(listarAnalisesRiscoDe(filtro)); }
  function obterAnaliseRisco(codigo) { return responder(analiseCalculada(analisePorCodigo(codigo))); }
  /* Numeração por tipo (APR-TN-2026-000n ou HAZOP-TN-2026-000n). TODO: API POST /projetos/{id}/analises-risco */
  function salvarAnaliseRisco(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar estudos.");
    var erros = [];
    if (["APR", "HAZOP"].indexOf(d.tipo) < 0) erros.push({ campo: "tipo", msg: "Escolha o tipo de estudo." });
    if (!d.area) erros.push({ campo: "area", msg: "Informe a área." });
    if (!d.titulo || d.titulo.trim().length < 5) erros.push({ campo: "titulo", msg: "Informe o título do estudo (mínimo de 5 caracteres)." });
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    if (!d.participantesIds || !d.participantesIds.length) erros.push({ campo: "participantesIds", msg: "Escolha ao menos um participante." });
    var recs = (d.recomendacoes || []).filter(function (r) { return r.descricao && r.descricao.trim(); });
    if (!recs.length) erros.push({ msg: "Inclua ao menos uma recomendação." });
    recs.forEach(function (r, i) {
      if (!r.responsavelId) erros.push({ msg: "Recomendação " + (i + 1) + ": escolha o responsável." });
      if (!r.prazo) erros.push({ msg: "Recomendação " + (i + 1) + ": informe o prazo." });
    });
    if (erros.length) return rejeitar(erros);
    if (semProjeto(d.projetoId)) return rejeitar("Escolha o projeto do estudo.");
    var prefixo = d.tipo + "-" + ((porId(M.projetos)[Number(d.projetoId)] || {}).padraoAta || "TN-2026") + "-";
    var a = { id: proximoId("analisesRisco"), projetoId: d.projetoId, codigo: proximoCodigo("analisesRisco", prefixo), tipo: d.tipo,
      area: d.area, titulo: d.titulo.trim(), data: d.data, participantesIds: d.participantesIds.map(Number),
      recomendacoes: recs.map(function (r) { return { descricao: r.descricao.trim(), responsavelId: Number(r.responsavelId), prazo: r.prazo, situacao: "Aberta" }; }) };
    colecao("analisesRisco").push(a); persistir("analisesRisco");
    return responder({ codigo: a.codigo });
  }
  /* TODO: API PUT /analises-risco/{codigo}/recomendacoes/{indice} */
  function fecharRecomendacao(codigo, indice, d) {
    var a = analisePorCodigo(codigo);
    if (!a) return rejeitar("Estudo não encontrado.");
    var r = a.recomendacoes[indice];
    if (!r) return rejeitar("Recomendação não encontrada.");
    if (r.situacao === "Fechada") return rejeitar("Recomendação já fechada.");
    if (!d || !d.data) return rejeitar({ campo: "data", msg: "Informe a data de conclusão." });
    if (d.data > REF) return rejeitar({ campo: "data", msg: "A data não pode ser posterior à referência." });
    r.situacao = "Fechada"; r.dataConclusao = d.data; r.evidencia = d.evidencia || null;
    persistir("analisesRisco");
    return responder({ codigo: codigo, indice: indice });
  }
  /* Recomendação vira ação na Central (origem HSE, origemRef = código do estudo). TODO: API POST /analises-risco/{codigo}/recomendacoes/{indice}/acao */
  function criarAcaoRecomendacao(codigo, indice) {
    var a = analisePorCodigo(codigo);
    if (!a) return rejeitar("Estudo não encontrado.");
    var r = a.recomendacoes[indice];
    if (!r) return rejeitar("Recomendação não encontrada.");
    if (r.acaoCriada) return rejeitar("Já existe uma ação na Central para esta recomendação.");
    var acao = { id: proximoId("acoes"), projetoId: a.projetoId, origem: "HSE", origemRef: a.codigo, item: String(indice + 1),
      grupo: a.tipo + " · Recomendação", tipo: "Ação", assunto: r.descricao, descricao: a.titulo + " (" + a.area + ")",
      solicitanteId: sessaoPessoa(), responsavelId: r.responsavelId, prevista: r.prazo, replanejada: null, conclusao: null };
    colecao("acoes").push(acao); r.acaoCriada = true;
    persistir("acoes"); persistir("analisesRisco");
    return responder({ item: acao.item });
  }

  /* ======================================================================
     08 Governança
     Controle integrado de mudanças (SM) e gestão do conhecimento (lições).
     Regras, alçada, prazos e integrações ficam aqui (nunca na tela).
     ====================================================================== */
  var SM_APROVADA = ["Aprovada", "Aprovada com condições", "Em implementação", "Encerrada"];
  var TIPO_REMANEJAMENTO = "Remanejamento de orçamento";
  var TIPO_LIBERACAO = "Liberação de reserva";
  var TIPOS_SM = ["Escopo", "Prazo", "Custo", "Qualidade/Especificação", "Contratual", TIPO_REMANEJAMENTO, TIPO_LIBERACAO];
  var ORIGENS_SM = ["Cliente", "Contratada", "Engenharia", "Interna", "Legal/regulatória"];
  var PRIORIDADES_SM = ["Normal", "Urgente", "Emergencial"];
  var SITUACOES_SM = ["Registrada", "Em análise de impacto", "Aguardando comitê", "Aprovada", "Aprovada com condições", "Rejeitada", "Adiada",
    "Em implementação", "Encerrada", "Cancelada"];
  var SM_TERMINAL = ["Rejeitada", "Encerrada", "Cancelada"];
  var SM_CANCELAVEL = ["Registrada", "Em análise de impacto", "Aguardando comitê", "Adiada"];
  var RESULTADOS_SM = ["Aprovada", "Aprovada com condições", "Rejeitada", "Adiada"];
  var FONTES_SM = ["Aditivo de orçamento", "Reserva de contingência", "Reserva gerencial"];
  var ALCADAS_SM = ["Gerente do projeto", "Comitê"];
  var ETAPAS_SM = ["Solicitação", "Análise de impacto", "Decisão", "Implementação", "Encerramento"];
  var SEM_IMPACTO = /^sem impacto$/i;

  function parMud() { return P().mudancas || { alcadaGerentePctOrcamento: 1, prazoAnaliseDias: 10, quorumComite: 3, prazoAcoesDias: 15, ratificacaoDias: 7 }; }
  function smPorCodigo(codigo) { return porCampo(M.mudancas, "codigo", codigo); }
  function temImpacto(txt) { return !!txt && !SEM_IMPACTO.test(String(txt).trim()); }
  function pessoaPorFuncao(funcao, padrao) { var p = (M.pessoas || []).filter(function (x) { return x.funcao === funcao; })[0]; return p ? p.id : padrao; }
  function acoesDaMudanca(codigo) {
    return acoesComStatus(function (a) { return a.origem === "Mudança" && a.origemRef === codigo; })
      .sort(function (a, b) { return (Number(a.item) || 0) - (Number(b.item) || 0) || (a.id > b.id ? 1 : -1); });
  }
  /* Saldo da reserva de contingência sem a SM informada (consumo = SMs aprovadas com essa fonte) */
  function saldoContingencia(projetoId, excetoCodigo, fonte) {
    fonte = fonte || "Reserva de contingência";
    if (projetoId == null) {
      var partes = projetosCarteira().map(function (p) { return saldoContingencia(p.id, excetoCodigo, fonte); }).filter(Boolean);
      return partes.length ? { total: soma(partes, "total"), consumido: soma(partes, "consumido"), saldo: soma(partes, "saldo") } : null;
    }
    var reserva = (M.reservas || []).filter(function (r) { return r.projetoId === projetoId; })[0];
    if (!reserva) return null;
    var total = fonte === "Reserva gerencial" ? reserva.gerencialCentavos || 0 : reserva.contingenciaCentavos;
    var consumo = soma(doProjeto(M.mudancas, projetoId).filter(function (s) {
      return s.codigo !== excetoCodigo && s.fonteRecurso === fonte && SM_APROVADA.indexOf(s.situacao) >= 0;
    }), function (s) { return s.impacto ? Math.max(0, s.impacto.custoCentavos || 0) : 0; });
    var rotulo = fonte === "Reserva gerencial" ? "Gerencial" : "Contingência";
    var liberado = soma(doProjeto(M.mudancas, projetoId).filter(function (s) {
      return s.codigo !== excetoCodigo && s.liberacao && s.liberacao.reserva === rotulo && SM_APROVADA.indexOf(s.situacao) >= 0;
    }), function (s) { return s.liberacao.valorCentavos; });
    return { total: total, consumido: consumo, liberado: liberado, saldo: total - consumo - liberado };
  }
  /* Alçada pelo maior valor entre o impacto em custo e o total remanejado na EAC */
  function alcadaExigidaSm(s, impacto) {
    var proj = porId(M.projetos)[s.projetoId] || {};
    var im = impacto || s.impacto;
    if (!im && !s.remanejamentos) return null;
    im = im || {};
    var valor = Math.max(Math.abs(im.custoCentavos || 0), totalRemanejadoSm(s));
    return R.alcadaMudanca(valor, proj.orcamentoCentavos, !!im.afetaMarcoContratual, parMud().alcadaGerentePctOrcamento);
  }
  /* ---------- Remanejamento de orçamento (EAC do 03) por SM ---------- */
  function totalRemanejadoSm(s) { return soma(s.remanejamentos || [], "valorCentavos"); }
  /* Valor de cada item de origem já reservado por SMs abertas ainda não aplicadas */
  function reservadoEmSms(projetoId, excetoCodigo) {
    var r = {};
    doProjeto(M.mudancas, projetoId).forEach(function (s) {
      if (s.codigo === excetoCodigo || !s.remanejamentos || s.remanejamentoAplicado || SM_TERMINAL.indexOf(s.situacao) >= 0) return;
      s.remanejamentos.forEach(function (t) { r[t.origem] = (r[t.origem] || 0) + (t.valorCentavos || 0); });
    });
    return r;
  }
  /* Saldo livre para remanejar = orçado atual menos comprometido menos o reservado em outras SMs */
  function saldoLivreEac(projetoId, codigo, excetoCodigo) {
    var f = folhaPorCodigo(projetoId, codigo);
    if (!f) return null;
    return f.base + f.remanejamento - f.comprometido - (reservadoEmSms(projetoId, excetoCodigo)[codigo] || 0);
  }
  function validarRemanejamentosSm(projetoId, lista, excetoCodigo) {
    var e = [];
    if (!lista || !lista.length) return [{ campo: "remanejamentos", msg: "Inclua ao menos uma transferência (origem, destino e valor)." }];
    var porOrigem = {}, novos = {};
    lista.forEach(function (t, i) {
      var p = "remanejamentos." + i + ".";
      var novo = !!(t.novoItem && t.novoItem.codigo === t.destino);
      if (!folhaPorCodigo(projetoId, t.origem)) e.push({ campo: p + "origem", msg: "A origem precisa ser item de custo (nível 3) da EAC." });
      if (novo) {
        if (folhaPorCodigo(projetoId, t.destino) && !t.aplicado) e.push({ campo: p + "destino", msg: "Já existe item com o código " + t.destino + "." });
        if (novos[t.destino]) e.push({ campo: p + "destino", msg: "Item novo repetido: " + t.destino + "." });
        novos[t.destino] = true;
      } else if (!folhaPorCodigo(projetoId, t.destino)) e.push({ campo: p + "destino", msg: "O destino precisa ser item de custo (nível 3) da EAC." });
      if (t.origem && t.origem === t.destino) e.push({ campo: p + "destino", msg: "O destino precisa ser diferente da origem." });
      if (!(t.valorCentavos > 0) || Math.round(t.valorCentavos) !== t.valorCentavos) e.push({ campo: p + "valorCentavos", msg: "Informe um valor maior que zero." });
      else if (folhaPorCodigo(projetoId, t.origem)) porOrigem[t.origem] = (porOrigem[t.origem] || 0) + t.valorCentavos;
    });
    Object.keys(porOrigem).forEach(function (c) {
      var livre = saldoLivreEac(projetoId, c, excetoCodigo);
      if (porOrigem[c] > livre) e.push("O item " + c + " só tem " + moedaBr(livre) + " livres para remanejar (orçado atual menos comprometido e menos o reservado em outras SMs abertas).");
    });
    return e;
  }
  /* Aplicação na aprovação: transferências (e itens novos) entram na revisão vigente com a SM de referência */
  function aplicarRemanejamentosSm(s, data) {
    var vig = revisaoVigente(s.projetoId), eac = colecao("eac"), lista = colecao("eacRemanejamentos");
    s.remanejamentos.forEach(function (t) {
      if (t.novoItem && !folhaPorCodigo(s.projetoId, t.destino)) {
        var n = copia(t.novoItem);
        n.id = eac.reduce(function (m, x) { return Math.max(m, x.id); }, 0) + 1;
        n.projetoId = s.projetoId; n.nivel = 3; n.base = 0; n.remanejamento = 0; n.comprometido = 0; n.realizado = 0; n.projecao = t.valorCentavos;
        eac.push(n);
      }
      var o = folhaPorCodigo(s.projetoId, t.origem), de = folhaPorCodigo(s.projetoId, t.destino);
      o.remanejamento -= t.valorCentavos; de.remanejamento += t.valorCentavos;
      lista.push({ id: lista.reduce(function (m, x) { return Math.max(m, x.id); }, 0) + 1, projetoId: s.projetoId, revisao: vig ? vig.revisao : 0, data: data,
        origem: t.origem, destino: t.destino, valorCentavos: t.valorCentavos, porId: sessaoPessoa(), smRef: s.codigo, novoItem: !!t.novoItem, justificativa: s.titulo });
      t.aplicado = true;
    });
    s.remanejamentoAplicado = { data: data, porId: sessaoPessoa(), revisao: vig ? vig.revisao : 0 };
    persistir("eac"); persistir("eacRemanejamentos");
  }
  /* Liberação de saldo de reserva (fim da exposição, encerramento ou devolução ao patrocinador): só por SM do Comitê.
     Valor até o saldo da reserva menos o já pedido em outras SMs abertas da mesma reserva. */
  function validarLiberacaoSm(projetoId, lib, excetoCodigo) {
    var e = [];
    if (["Contingência", "Gerencial"].indexOf(lib.reserva) < 0) e.push({ campo: "liberacaoReserva", msg: "Escolha a reserva a liberar." });
    if (!(lib.valorCentavos > 0) || Math.round(lib.valorCentavos) !== lib.valorCentavos) e.push({ campo: "liberacaoValor", msg: "Informe um valor maior que zero." });
    if (e.length) return e;
    var fonte = lib.reserva === "Gerencial" ? "Reserva gerencial" : "Reserva de contingência";
    var sc = saldoContingencia(projetoId, excetoCodigo, fonte);
    if (!sc) return [{ campo: "liberacaoReserva", msg: "O projeto não tem reservas constituídas." }];
    var pedido = soma(doProjeto(M.mudancas, projetoId).filter(function (s) {
      if (s.codigo === excetoCodigo || SM_TERMINAL.indexOf(s.situacao) >= 0 || SM_APROVADA.indexOf(s.situacao) >= 0) return false;
      return (s.liberacao && s.liberacao.reserva === lib.reserva) || (s.fonteRecurso === fonte && s.impacto && s.impacto.custoCentavos > 0);
    }), function (s) { return s.liberacao ? s.liberacao.valorCentavos : s.impacto.custoCentavos; });
    if (lib.valorCentavos > sc.saldo - pedido) e.push({ campo: "liberacaoValor", msg: "A reserva tem " + moedaBr(sc.saldo - pedido) + " livres para liberar (saldo menos o pedido em outras SMs abertas)." });
    return e;
  }
  /* Solicitação de remanejamento aberta a partir do 03 (cria a SM com as transferências) */
  function solicitarRemanejamento(projetoId, d) {
    return salvarMudanca({ projetoId: projetoId, titulo: (d.titulo || "").slice(0, 150), tipo: TIPO_REMANEJAMENTO, origem: "Interna", prioridade: d.prioridade || "Normal",
      descricao: d.justificativa || "", dataSolicitacao: REF, solicitanteId: sessaoPessoa(), remanejamentos: d.remanejamentos });
  }
  function historicoMudanca(s, texto) {
    if (!s.historico) s.historico = historicoDerivadoSm(s);
    s.historico.unshift({ quando: agoraIso(), porId: sessaoPessoa(), texto: texto });
  }
  /* Trilha montada a partir das datas quando o registro é anterior à trilha */
  function historicoDerivadoSm(s) {
    var h = [{ quando: s.dataSolicitacao + "T08:00", porId: s.solicitanteId, texto: "Solicitação registrada (" + s.tipo + ", origem " + s.origem + ", prioridade " + s.prioridade + ")." }];
    if (s.impacto && s.impacto.dataAnalise) {
      h.push({ quando: s.impacto.dataAnalise + "T10:00", porId: s.impacto.analistaId || null, texto: "Análise de impacto concluída e enviada para decisão (" + (s.alcada || "Comitê") + ")." });
    }
    if (s.decisao && s.decisao.data) {
      h.push({ quando: s.decisao.data + "T15:00", porId: (s.decisao.participantesIds || [])[0] || null, texto: "Decisão: " + s.decisao.resultado + "." + (s.decisao.justificativa ? " " + s.decisao.justificativa : "") });
    }
    if (s.implementacao && s.implementacao.inicio) h.push({ quando: s.implementacao.inicio + "T09:00", porId: null, texto: "Implementação iniciada." });
    if (s.situacao === "Encerrada" && s.encerramento) h.push({ quando: s.encerramento + "T17:00", porId: null, texto: "Mudança encerrada com as linhas de base atualizadas." });
    return h.sort(function (a, b) { return a.quando < b.quando ? 1 : a.quando > b.quando ? -1 : 0; });
  }
  function etapaSm(sit) {
    if (sit === "Registrada") return 0;
    if (sit === "Em análise de impacto") return 1;
    if (sit === "Aguardando comitê" || sit === "Adiada") return 2;
    if (sit === "Aprovada" || sit === "Aprovada com condições" || sit === "Em implementação") return 3;
    return 4;
  }
  /* Visão calculada: etapa, próxima etapa, alçada, prazos, ações e integrações */
  function mudancaCalculada(s) {
    var x = copia(s);
    var par = parMud();
    x.aberta = SM_TERMINAL.indexOf(s.situacao) < 0;
    x.aprovada = SM_APROVADA.indexOf(s.situacao) >= 0;
    x.etapa = etapaSm(s.situacao);
    x.custoCentavos = s.impacto ? s.impacto.custoCentavos : null;
    x.prazoDias = s.impacto ? s.impacto.prazoDias : null;
    var ex = alcadaExigidaSm(s);
    x.alcadaExigida = ex ? ex.alcada : null;
    x.limiteGerenteCentavos = ex ? ex.limiteCentavos : null;
    x.diasDecisao = s.decisao && s.decisao.data ? R.diasEntre(s.dataSolicitacao, s.decisao.data) : null;
    x.diasEmAberto = x.aberta ? R.diasEntre(s.dataSolicitacao, REF) : null;
    x.analiseVencida = s.situacao === "Em análise de impacto" && !!(s.analise && s.analise.prazo && s.analise.prazo < REF);
    var acoes = acoesDaMudanca(s.codigo).filter(function (a) { return a.ehAcao; });
    x.acoesTotal = acoes.length;
    x.acoesAbertas = acoes.filter(function (a) { return a.status !== "concluida"; }).length;
    x.acoesAtrasadas = acoes.filter(function (a) { return a.status === "atrasada"; }).length;
    var rev = doProjeto(M.eacRevisoes, s.projetoId).filter(function (r) { return r.smRef === s.codigo; })[0];
    x.eacRevisao = rev ? rev.revisao : null;
    x.exigeEac = !!(s.impacto && s.impacto.custoCentavos);
    x.remanejamentoTotal = s.remanejamentos ? totalRemanejadoSm(s) : null;
    x.liberacao = s.liberacao ? copia(s.liberacao) : null;
    x.remanejamentoAplicado = s.remanejamentoAplicado ? copia(s.remanejamentoAplicado) : null;
    var revEap = doProjeto(M.eapRevisoes, s.projetoId).filter(function (r) { return r.smRef === s.codigo; })[0];
    x.eapRevisao = revEap ? revEap.revisao : null;
    x.exigeEap = !!(s.impacto && temImpacto(s.impacto.escopo)) && temEap(s.projetoId);
    x.aditivos = (M.aditivos || []).filter(function (a) { return a.smRef === s.codigo; }).map(function (a) {
      var ct = porId(M.contratos)[a.contratoId]; return { contrato: ct ? ct.numero : "", numero: a.numero, valorCentavos: a.valorCentavos, dias: a.dias || 0 };
    });
    x.emergenciaPendente = !!(s.emergencia && !s.decisao && x.aberta);
    x.ratificacaoAte = s.emergencia ? somarDiasIso(s.emergencia.inicio, par.ratificacaoDias) : null;
    x.ratificacaoVencida = x.emergenciaPendente && x.ratificacaoAte < REF;
    /* Próxima etapa (texto de orientação) */
    var prox = "";
    switch (s.situacao) {
      case "Registrada": prox = "Iniciar a análise de impacto"; break;
      case "Em análise de impacto": prox = "Concluir a análise de impacto" + (s.analise && s.analise.prazo ? " até " + dataBr(s.analise.prazo) : ""); break;
      case "Aguardando comitê": prox = s.alcada === "Gerente do projeto" ? "Decisão do gerente do projeto" : "Decisão do Comitê"; break;
      case "Adiada": prox = "Reapresentar para decisão" + (s.decisao && s.decisao.reapresentarEm ? " em " + dataBr(s.decisao.reapresentarEm) : ""); break;
      case "Aprovada": case "Aprovada com condições": prox = "Iniciar a implementação"; break;
      case "Em implementação":
        prox = x.acoesAbertas ? "Concluir " + (x.acoesAbertas === 1 ? "1 ação" : x.acoesAbertas + " ações") + " de implementação"
          : x.exigeEac && x.eacRevisao == null ? "Incorporar a SM na EAC (nova revisão)"
          : x.exigeEap && x.eapRevisao == null ? "Incorporar a SM na EAP (nova revisão)" : "Encerrar a mudança";
        break;
      default: prox = "";
    }
    x.proximaEtapa = prox;
    return x;
  }

  /* TODO: API GET /projetos/{id}/mudancas?situacao&tipo&origem&prioridade&alcada&busca */
  function listarMudancasDe(filtro) {
    filtro = filtro || {};
    var lista = doProjeto(M.mudancas, filtro.projetoId).map(mudancaCalculada);
    if (filtro.situacao === "abertas") lista = lista.filter(function (s) { return s.aberta; });
    else if (filtro.situacao === "em-analise") lista = lista.filter(function (s) { return s.situacao === "Registrada" || s.situacao === "Em análise de impacto"; });
    else if (filtro.situacao === "aprovadas") lista = lista.filter(function (s) { return s.aprovada; });
    else if (filtro.situacao) lista = lista.filter(function (s) { return s.situacao === filtro.situacao; });
    ["tipo", "origem", "prioridade", "alcada"].forEach(function (k) { if (filtro[k]) lista = lista.filter(function (s) { return s[k] === filtro[k]; }); });
    if (filtro.busca) {
      var t = U_norm(filtro.busca);
      lista = lista.filter(function (s) { return [s.codigo, s.titulo, s.descricao, s.tipo, s.origem].some(function (v) { return U_norm(v).indexOf(t) >= 0; }); });
    }
    return lista.sort(function (a, b) { return a.codigo < b.codigo ? 1 : -1; });
  }
  function listarMudancas(filtro) { return responder(listarMudancasDe(filtro)); }

  function resumoMudancasDe(projetoId) {
    var lista = doProjeto(M.mudancas, projetoId);
    var aprovadas = lista.filter(function (s) { return SM_APROVADA.indexOf(s.situacao) >= 0; });
    var decididas = lista.filter(function (s) { return s.decisao && s.decisao.data; });
    var definitivas = decididas.filter(function (s) { return s.decisao.resultado !== "Adiada"; });
    var proj = projetoOuCarteira(projetoId);
    var valor = soma(aprovadas, function (s) { return s.impacto ? s.impacto.custoCentavos : 0; });
    var ano = REF.slice(0, 4);
    return {
      total: lista.length,
      emAnalise: lista.filter(function (s) { return s.situacao === "Em análise de impacto" || s.situacao === "Registrada"; }).length,
      analiseVencida: lista.filter(function (s) { return s.situacao === "Em análise de impacto" && s.analise && s.analise.prazo < REF; }).length,
      aguardandoComite: lista.filter(function (s) { return s.situacao === "Aguardando comitê"; }).length,
      adiadas: lista.filter(function (s) { return s.situacao === "Adiada"; }).length,
      emImplementacao: lista.filter(function (s) { return s.situacao === "Em implementação"; }).length,
      aprovadas: aprovadas.length,
      aprovadasAno: aprovadas.filter(function (s) { return s.decisao && String(s.decisao.data).slice(0, 4) === ano; }).length,
      ano: ano,
      valorAprovadoCentavos: valor,
      valorAprovadoPct: proj && proj.orcamentoCentavos ? arred(valor / proj.orcamentoCentavos * 100, 1) : null,
      prazoAprovadoDias: soma(aprovadas, function (s) { return s.impacto ? s.impacto.prazoDias : 0; }),
      tempoMedioDecisaoDias: decididas.length ? Math.round(soma(decididas, function (s) { return R.diasEntre(s.dataSolicitacao, s.decisao.data); }) / decididas.length) : null,
      taxaAprovacaoPct: definitivas.length ? arred(definitivas.filter(function (s) { return s.decisao.resultado !== "Rejeitada"; }).length / definitivas.length * 100, 1) : null,
      emergenciaisPendentes: lista.filter(function (s) { return s.emergencia && !s.decisao && SM_TERMINAL.indexOf(s.situacao) < 0; }).length,
      smsNaoIncorporadas: smsPendentesDe(projetoId).length
    };
  }
  function resumoMudancas(projetoId) { return responder(resumoMudancasDe(projetoId)); }

  /* Painel: situação, Pareto por origem, tipo, valor aprovado e prazo acumulados por mês.
     TODO: API GET /projetos/{id}/mudancas/painel */
  function painelMudancas(projetoId) {
    var lista = doProjeto(M.mudancas, projetoId);
    function contar(campo, ordemFixa) {
      var por = {};
      lista.forEach(function (s) { por[s[campo]] = (por[s[campo]] || 0) + 1; });
      var chaves = ordemFixa ? ordemFixa.filter(function (k) { return por[k]; }).concat(Object.keys(por).filter(function (k) { return ordemFixa.indexOf(k) < 0; })) : Object.keys(por);
      return chaves.map(function (k) { return { chave: k, total: por[k] }; });
    }
    var porOrigem = contar("origem").sort(function (a, b) { return b.total - a.total || (a.chave < b.chave ? -1 : 1); });
    var acum = 0;
    porOrigem.forEach(function (o) { acum += o.total; o.pct = arred(o.total / lista.length * 100, 1); o.acumPct = arred(acum / lista.length * 100, 1); });
    var aprovadas = lista.filter(function (s) { return SM_APROVADA.indexOf(s.situacao) >= 0 && s.decisao && s.decisao.data; });
    var inicio = lista.reduce(function (m, s) { return !m || s.dataSolicitacao < m ? s.dataSolicitacao : m; }, null);
    var meses = [];
    if (inicio) {
      var d = new Date(mesDe(inicio) + "-01T00:00:00"), fim = mesDe(REF);
      while (true) {
        var mm = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
        meses.push(mm); if (mm >= fim) break; d.setMonth(d.getMonth() + 1);
      }
    }
    var valorAc = 0, prazoAc = 0;
    var mensal = meses.map(function (m) {
      var doMes = aprovadas.filter(function (s) { return mesDe(s.decisao.data) === m; });
      valorAc += soma(doMes, function (s) { return s.impacto.custoCentavos; });
      prazoAc += soma(doMes, function (s) { return s.impacto.prazoDias; });
      return { mes: m, aprovadas: doMes.length, solicitadas: lista.filter(function (s) { return mesDe(s.dataSolicitacao) === m; }).length, valorAcumulado: valorAc, prazoAcumulado: prazoAc };
    });
    return responder({
      resumo: resumoMudancasDe(projetoId),
      porSituacao: contar("situacao", SITUACOES_SM), porOrigem: porOrigem, porTipo: contar("tipo", TIPOS_SM),
      mensal: mensal, contingencia: saldoContingencia(projetoId, null)
    });
  }

  /* Ações sugeridas na aprovação, pelo que a análise de impacto apontou (integrações 02, 03 e 05) */
  function acoesSugeridasSm(s) {
    var im = s.impacto || {}, lista = [];
    var proj = porId(M.projetos)[s.projetoId] || {};
    if (im.custoCentavos) lista.push({ chave: "eac", assunto: "Incorporar a " + s.codigo + " na EAC (nova revisão do orçamento)", responsavelId: pessoaPorFuncao("Custos", proj.gerenteId), modulo: "03" });
    if (im.prazoDias) lista.push({ chave: "cronograma", assunto: "Atualizar a linha de base do cronograma e a Curva S (" + s.codigo + ")", responsavelId: pessoaPorFuncao("Planejamento", proj.gerenteId), modulo: "02" });
    if (temImpacto(im.contrato)) lista.push({ chave: "contrato", assunto: "Formalizar o aditivo contratual da " + s.codigo + " (" + im.contrato + ")", responsavelId: pessoaPorFuncao("Fiscal de contratos", proj.gerenteId), modulo: "03" });
    if (temImpacto(im.riscos)) lista.push({ chave: "riscos", assunto: "Revisar os riscos afetados pela " + s.codigo + " (" + im.riscos + ")", responsavelId: proj.gerenteId, modulo: "05" });
    if (temImpacto(im.sms)) lista.push({ chave: "sms", assunto: "Atualizar a análise de risco de SMS da " + s.codigo + " (" + im.sms + ")", responsavelId: pessoaPorFuncao("HSE", proj.gerenteId), modulo: "07" });
    if (temImpacto(im.qualidade)) lista.push({ chave: "qualidade", assunto: "Atualizar especificação e plano de inspeção da " + s.codigo + " (" + im.qualidade + ")", responsavelId: pessoaPorFuncao("Qualidade", proj.gerenteId), modulo: "06" });
    return lista;
  }

  /* Ficha: SM calculada, ações, histórico, vínculos e o que a aprovação vai gerar. TODO: API GET /mudancas/{codigo} */
  function obterMudanca(codigo) {
    var s = smPorCodigo(codigo);
    if (!s) return responder(null);
    var x = mudancaCalculada(s);
    x.acoesLista = acoesDaMudanca(codigo);
    x.historicoExibicao = s.historico ? copia(s.historico) : historicoDerivadoSm(s);
    x.acoesSugeridas = acoesSugeridasSm(s);
    x.contingencia = saldoContingencia(s.projetoId, s.codigo);
    x.gerencial = saldoContingencia(s.projetoId, s.codigo, "Reserva gerencial");
    var ata = s.decisao && s.decisao.ataId ? porId(M.atas)[s.decisao.ataId] : null;
    x.ata = ata ? { id: ata.id, numero: ata.numero, revisao: ata.revisao, data: ata.data } : null;
    var lic = s.encerramentoDetalhe && s.encerramentoDetalhe.licaoRef ? porCampo(M.licoes, "codigo", s.encerramentoDetalhe.licaoRef) : null;
    x.licao = lic ? { codigo: lic.codigo, titulo: lic.titulo, situacao: lic.situacao } : null;
    var rsk = s.riscoRef ? riscoPorCodigo(s.riscoRef) : null;
    x.risco = rsk ? { codigo: rsk.codigo, titulo: rsk.titulo, situacao: rsk.situacao } : null;
    /* Riscos do 05 que apontam esta SM (estratégia Evitar ou encerramento com SM) */
    x.riscosVinculados = (M.riscos || []).filter(function (r) { return !r.oculto && (r.smRef === codigo || (r.encerramento && r.encerramento.smRef === codigo)); })
      .map(function (r) { return { codigo: r.codigo, titulo: r.titulo, situacao: r.situacao }; });
    x.remanejamentosDetalhe = (s.remanejamentos || []).map(function (t) {
      var o = folhaPorCodigo(s.projetoId, t.origem), de = folhaPorCodigo(s.projetoId, t.destino);
      return { origem: t.origem, origemDescricao: o ? o.descricao : "", destino: t.destino, destinoDescricao: de ? de.descricao : (t.novoItem ? t.novoItem.descricao : ""),
        novoItem: !!t.novoItem, valorCentavos: t.valorCentavos, aplicado: !!s.remanejamentoAplicado,
        saldoLivre: s.remanejamentoAplicado ? null : saldoLivreEac(s.projetoId, t.origem, s.codigo) };
    });
    x.eacItensDetalhe = ((s.impacto && s.impacto.eacItens) || []).map(function (c) { var f = folhaPorCodigo(s.projetoId, c); return { codigo: c, descricao: f ? f.descricao : "item não encontrado" }; });
    return responder(x);
  }

  function validarCamposSm(d) {
    var e = [];
    e = e.concat(errosTexto(d, "titulo", "Título", 10, 150));
    if (TIPOS_SM.indexOf(d.tipo) < 0) e.push({ campo: "tipo", msg: "Escolha o tipo da mudança." });
    if (ORIGENS_SM.indexOf(d.origem) < 0) e.push({ campo: "origem", msg: "Escolha a origem." });
    if (PRIORIDADES_SM.indexOf(d.prioridade) < 0) e.push({ campo: "prioridade", msg: "Escolha a prioridade." });
    e = e.concat(errosTexto(d, "descricao", "Descrição e justificativa", 20, 1000));
    if (!d.dataSolicitacao) e.push({ campo: "dataSolicitacao", msg: "Informe a data da solicitação." });
    else if (d.dataSolicitacao > REF) e.push({ campo: "dataSolicitacao", msg: "A data não pode ser posterior à referência." });
    if (!d.solicitanteId || !porId(M.pessoas)[d.solicitanteId]) e.push({ campo: "solicitanteId", msg: "Escolha o solicitante." });
    if (d.prioridade === "Emergencial" && d.execucaoAntecipada) {
      if (!d.inicioEmergencia) e.push({ campo: "inicioEmergencia", msg: "Informe quando a execução começou." });
      else if (d.inicioEmergencia > REF) e.push({ campo: "inicioEmergencia", msg: "A data não pode ser posterior à referência." });
      else if (d.dataSolicitacao && d.inicioEmergencia < d.dataSolicitacao) e.push({ campo: "inicioEmergencia", msg: "A execução não pode começar antes do registro (registro imediato é obrigatório)." });
      e = e.concat(errosTexto(d, "justificativaEmergencia", "Justificativa da emergência", 20, 500));
    }
    return e;
  }

  /* Nova solicitação ou edição (só Registrada ou Em análise). Toda mudança nasce como SM formal.
     TODO: API POST /projetos/{id}/mudancas | PUT /mudancas/{codigo} */
  function salvarMudanca(d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar solicitações de mudança.");
    var s = d.codigo ? smPorCodigo(d.codigo) : null;
    if (d.codigo && !s) return rejeitar("Solicitação não encontrada.");
    if (s && ["Registrada", "Em análise de impacto"].indexOf(s.situacao) < 0) return rejeitar("Só é possível editar a solicitação antes da decisão (Registrada ou Em análise de impacto).");
    var e = validarCamposSm(d);
    var projetoId = s ? s.projetoId : Number(d.projetoId);
    var proj = porId(M.projetos)[projetoId];
    if (!proj) e.push("Projeto não encontrado.");
    var remanejamentos = null;
    if (proj && d.tipo === TIPO_REMANEJAMENTO) {
      remanejamentos = (d.remanejamentos || (s && s.remanejamentos) || []).map(function (t) {
        var x = { origem: String(t.origem || "").trim(), destino: String(t.destino || "").trim(), valorCentavos: Number(t.valorCentavos) };
        var ant = !t.novoItem && s && s.remanejamentos ? s.remanejamentos.filter(function (y) { return y.novoItem && y.destino === x.destino; })[0] : null;
        if (t.novoItem || ant) x.novoItem = copia(t.novoItem || ant.novoItem);
        return x;
      });
      e = e.concat(validarRemanejamentosSm(projetoId, remanejamentos, s ? s.codigo : null));
    }
    var liberacao = null;
    if (proj && d.tipo === TIPO_LIBERACAO) {
      var libAnt = s && s.liberacao ? s.liberacao : {};
      liberacao = { reserva: d.liberacaoReserva || (d.liberacao && d.liberacao.reserva) || libAnt.reserva || "",
        valorCentavos: Number(d.liberacaoValor != null ? d.liberacaoValor : (d.liberacao ? d.liberacao.valorCentavos : libAnt.valorCentavos)) };
      e = e.concat(validarLiberacaoSm(projetoId, liberacao, s ? s.codigo : null));
    }
    if (e.length) return Promise.reject({ erros: e });
    var avisos = [];
    var igual = doProjeto(M.mudancas, projetoId).filter(function (x) { return x !== s && SM_TERMINAL.indexOf(x.situacao) < 0 && U_norm(x.titulo) === U_norm(d.titulo); })[0];
    if (igual) avisos.push("Já existe solicitação aberta com o mesmo título (" + igual.codigo + "). Verifique se não é duplicidade.");
    var novo = !s;
    if (novo) {
      s = { id: proximoId("mudancas"), projetoId: projetoId, codigo: proximoCodigo("mudancas", "SM-" + (proj.padraoAta || "TN") + "-"),
        impacto: null, fonteRecurso: null, alcada: null, decisao: null, situacao: "Registrada", encerramento: null, historico: [] };
    }
    var antes = novo ? null : copia(s);
    s.titulo = d.titulo.trim(); s.tipo = d.tipo; s.origem = d.origem; s.prioridade = d.prioridade;
    s.descricao = d.descricao.trim(); s.dataSolicitacao = d.dataSolicitacao; s.solicitanteId = Number(d.solicitanteId);
    s.emergencia = d.prioridade === "Emergencial" && d.execucaoAntecipada ? { inicio: d.inicioEmergencia, justificativa: d.justificativaEmergencia.trim() } : null;
    if (d.anexos && d.anexos.length) s.anexos = (s.anexos || []).concat(d.anexos);
    if (remanejamentos) s.remanejamentos = remanejamentos; else delete s.remanejamentos;
    if (liberacao) s.liberacao = liberacao; else delete s.liberacao;
    if (novo) {
      colecao("mudancas").push(s);
      s.historico.push({ quando: agoraIso(), porId: sessaoPessoa(), texto: "Solicitação registrada (" + s.tipo + ", origem " + s.origem + ", prioridade " + s.prioridade + ")." +
        (liberacao ? " Liberação proposta: " + moedaBr(liberacao.valorCentavos) + " da reserva " + (liberacao.reserva === "Gerencial" ? "gerencial" : "de contingência") + "." : "") +
        (remanejamentos ? " Remanejamento proposto na EAC: " + remanejamentos.map(function (t) { return moedaBr(t.valorCentavos) + " de " + t.origem + " para " + t.destino + (t.novoItem ? " (item novo)" : ""); }).join("; ") + "." : "") +
        (s.emergencia ? " Execução emergencial iniciada em " + dataBr(s.emergencia.inicio) + ": ratificação obrigatória pelo Comitê." : "") });
      if (s.emergencia) avisos.push("Mudança emergencial: o Comitê precisa ratificar a decisão até " + dataBr(somarDiasIso(s.emergencia.inicio, parMud().ratificacaoDias)) + ".");
    } else {
      var mud = [];
      ["titulo", "tipo", "origem", "prioridade", "descricao", "dataSolicitacao", "solicitanteId"].forEach(function (k) { if (antes[k] !== s[k]) mud.push(k); });
      historicoMudanca(s, mud.length ? "Solicitação editada (" + mud.map(function (k) {
        return { titulo: "título", tipo: "tipo", origem: "origem", prioridade: "prioridade", descricao: "descrição", dataSolicitacao: "data", solicitanteId: "solicitante" }[k];
      }).join(", ") + ")." : "Solicitação salva sem alterações.");
    }
    persistir("mudancas");
    return responder({ codigo: s.codigo, novo: novo, avisos: avisos });
  }

  /* Registrada -> Em análise de impacto (responsável e prazo). TODO: API POST /mudancas/{codigo}/analise/inicio */
  function iniciarAnaliseSm(codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite conduzir a análise de impacto.");
    var s = smPorCodigo(codigo);
    if (!s) return rejeitar("Solicitação não encontrada.");
    if (s.situacao !== "Registrada") return rejeitar("A análise só pode ser iniciada em solicitação Registrada.");
    var e = [];
    if (!d.responsavelId || !porId(M.pessoas)[d.responsavelId]) e.push({ campo: "responsavelId", msg: "Escolha o responsável pela análise." });
    if (!d.prazo) e.push({ campo: "prazo", msg: "Informe o prazo da análise." });
    else if (d.prazo < REF) e.push({ campo: "prazo", msg: "O prazo não pode ser anterior à data de referência." });
    if (e.length) return Promise.reject({ erros: e });
    s.analise = { responsavelId: Number(d.responsavelId), prazo: d.prazo, inicio: REF };
    s.situacao = "Em análise de impacto";
    historicoMudanca(s, "Análise de impacto iniciada. Responsável: " + nomePessoa(s.analise.responsavelId) + "; prazo " + dataBr(d.prazo) + ".");
    persistir("mudancas");
    return responder({ codigo: codigo });
  }

  /* Análise de impacto (obrigatória antes da decisão). enviar=true conclui e envia para decisão.
     TODO: API PUT /mudancas/{codigo}/analise */
  function salvarAnaliseSm(codigo, d, enviar) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar a análise de impacto.");
    var s = smPorCodigo(codigo);
    if (!s) return rejeitar("Solicitação não encontrada.");
    if (["Em análise de impacto", "Aguardando comitê", "Adiada"].indexOf(s.situacao) < 0) return rejeitar("A análise de impacto só pode ser registrada com a solicitação em análise (ou revista antes da decisão).");
    var e = [];
    if (d.custoCentavos == null || isNaN(d.custoCentavos)) e.push({ campo: "custoCentavos", msg: "Informe o impacto em custo (zero se não houver; negativo para redução)." });
    if (d.prazoDias == null || isNaN(d.prazoDias) || Math.round(d.prazoDias) !== Number(d.prazoDias)) e.push({ campo: "prazoDias", msg: "Informe o impacto em prazo em dias inteiros (zero se não houver; negativo para antecipação)." });
    [["escopo", "Escopo"], ["qualidade", "Qualidade"], ["riscos", "Riscos novos ou alterados"], ["sms", "SMS"], ["contrato", "Contrato"]].forEach(function (c) {
      e = e.concat(errosTexto(d, c[0], c[1], 3, 300));
    });
    var itens = String(d.eacItens || "").split(/[,;\s]+/).map(function (c) { return c.trim(); }).filter(Boolean);
    if (s.liberacao) {
      if (d.custoCentavos != null && !isNaN(d.custoCentavos) && d.custoCentavos !== 0) e.push({ campo: "custoCentavos", msg: "Liberação de reserva não muda o orçado da EAC: impacto em custo zero." });
      if (d.alcada && d.alcada !== "Comitê") e.push({ campo: "alcada", msg: "Liberação de reserva é decidida pelo Comitê (patrocinador)." });
    }
    if (s.remanejamentos) {
      if (d.custoCentavos != null && !isNaN(d.custoCentavos) && d.custoCentavos !== 0) e.push({ campo: "custoCentavos", msg: "Remanejamento não muda o total do orçamento: impacto em custo zero. Acréscimo exige SM de custo com fonte de recurso." });
      s.remanejamentos.forEach(function (t) { [t.origem, t.destino].forEach(function (c) { if (itens.indexOf(c) < 0) itens.push(c); }); });
      itens = itens.filter(function (c) { return folhaPorCodigo(s.projetoId, c) || s.remanejamentos.some(function (t) { return t.novoItem && t.destino === c; }); });
    }
    itens.forEach(function (c) { if (!folhaPorCodigo(s.projetoId, c) && !(s.remanejamentos || []).some(function (t) { return t.novoItem && t.destino === c; })) e.push({ campo: "eacItens", msg: "Item " + c + " não é item de custo (nível 3) da EAC do projeto." }); });
    if (d.custoCentavos > 0 && FONTES_SM.indexOf(d.fonteRecurso) < 0) e.push({ campo: "fonteRecurso", msg: "Informe a fonte do recurso (aditivo de orçamento, reserva de contingência ou reserva gerencial)." });
    if (d.custoCentavos > 0 && d.fonteRecurso === "Reserva gerencial" && d.alcada !== "Comitê") e.push({ campo: "alcada", msg: "A reserva gerencial só é liberada pelo Comitê (patrocinador): eleve a alçada." });
    var ex = alcadaExigidaSm(s, { custoCentavos: d.custoCentavos, afetaMarcoContratual: !!d.afetaMarcoContratual });
    if (ALCADAS_SM.indexOf(d.alcada) < 0) e.push({ campo: "alcada", msg: "Escolha a alçada de decisão." });
    else if (ex && ex.alcada === "Comitê" && d.alcada !== "Comitê") e.push({ campo: "alcada", msg: "O impacto exige decisão do Comitê: a alçada pode ser elevada, nunca rebaixada." });
    if (e.length) return Promise.reject({ erros: e });
    var avisos = [];
    if ((d.fonteRecurso === "Reserva de contingência" || d.fonteRecurso === "Reserva gerencial") && d.custoCentavos > 0) {
      var sc = saldoContingencia(s.projetoId, s.codigo, d.fonteRecurso);
      if (sc && d.custoCentavos > sc.saldo) avisos.push("Custo acima do saldo da " + d.fonteRecurso.toLowerCase() + " (" + moedaBr(sc.saldo) + "): a decisão exigirá aditivo de orçamento.");
    }
    var primeira = !s.impacto || !s.impacto.dataAnalise;
    s.impacto = { custoCentavos: Math.round(d.custoCentavos), prazoDias: Math.round(d.prazoDias), afetaMarcoContratual: !!d.afetaMarcoContratual,
      escopo: d.escopo.trim(), qualidade: d.qualidade.trim(), riscos: d.riscos.trim(), sms: d.sms.trim(), contrato: d.contrato.trim(),
      eacItens: itens, atividades: (d.atividades || "").trim(),
      dataAnalise: enviar ? REF : (s.impacto && s.impacto.dataAnalise) || null, analistaId: sessaoPessoa() };
    s.fonteRecurso = d.custoCentavos > 0 ? d.fonteRecurso : null;
    s.alcada = d.alcada;
    var texto = "Análise de impacto " + (primeira ? "registrada" : "revista") + ": custo " + (s.impacto.custoCentavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) +
      ", prazo " + s.impacto.prazoDias + " dias; alçada " + s.alcada + (ex && ex.alcada !== s.alcada ? " (elevada pelo analista)" : "") + ".";
    if (enviar && s.situacao === "Em análise de impacto") { s.situacao = "Aguardando comitê"; texto += " Enviada para decisão."; }
    historicoMudanca(s, texto);
    persistir("mudancas");
    return responder({ codigo: codigo, situacao: s.situacao, alcadaExigida: ex ? ex.alcada : null, avisos: avisos });
  }

  /* Decisão (Comitê ou gerente, conforme a alçada). Aprovada gera as ações de implementação na Central.
     TODO: API POST /mudancas/{codigo}/decisao */
  function decidirMudanca(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Registrar a decisão exige papel Gestor (secretaria do Comitê ou gerente do projeto).");
    var s = smPorCodigo(codigo);
    if (!s) return rejeitar("Solicitação não encontrada.");
    if (s.situacao !== "Aguardando comitê") return rejeitar("Só há decisão para solicitação Aguardando comitê. Conclua a análise de impacto antes.");
    if (!s.impacto || !s.impacto.dataAnalise) return rejeitar("A análise de impacto é obrigatória antes da decisão.");
    var par = parMud(), proj = porId(M.projetos)[s.projetoId] || {};
    var e = [];
    if (RESULTADOS_SM.indexOf(d.resultado) < 0) e.push({ campo: "resultado", msg: "Escolha a decisão." });
    if (!d.data) e.push({ campo: "data", msg: "Informe a data da decisão." });
    else if (d.data > REF) e.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    else if (d.data < s.impacto.dataAnalise) e.push({ campo: "data", msg: "A decisão não pode ser anterior à análise de impacto (" + dataBr(s.impacto.dataAnalise) + ")." });
    var part = (d.participantesIds || []).map(Number).filter(function (id) { return porId(M.pessoas)[id]; });
    if (s.alcada === "Comitê" && part.length < par.quorumComite) e.push({ campo: "participantesIds", msg: "O Comitê exige quórum de " + par.quorumComite + " participantes." });
    if (s.alcada === "Gerente do projeto" && part.indexOf(proj.gerenteId) < 0) e.push({ campo: "participantesIds", msg: "Na alçada do gerente do projeto, " + nomePessoa(proj.gerenteId) + " precisa constar como decisor." });
    e = e.concat(errosTexto(d, "justificativa", "Justificativa da decisão", 10, 600));
    if (d.resultado === "Aprovada com condições") e = e.concat(errosTexto(d, "condicoes", "Condições", 10, 600));
    if (d.resultado === "Adiada") {
      if (!d.reapresentarEm) e.push({ campo: "reapresentarEm", msg: "Informe quando a solicitação volta à pauta." });
      else if (d.data && d.reapresentarEm <= d.data) e.push({ campo: "reapresentarEm", msg: "A reapresentação precisa ser depois da decisão." });
    }
    var aprova = d.resultado === "Aprovada" || d.resultado === "Aprovada com condições";
    if (aprova && (s.fonteRecurso === "Reserva de contingência" || s.fonteRecurso === "Reserva gerencial") && s.impacto.custoCentavos > 0) {
      var sc = saldoContingencia(s.projetoId, s.codigo, s.fonteRecurso);
      if (sc && s.impacto.custoCentavos > sc.saldo) e.push("Saldo da " + s.fonteRecurso.toLowerCase() + " insuficiente (" + moedaBr(sc.saldo) + "). Revise a análise para aditivo de orçamento.");
      if (s.fonteRecurso === "Reserva gerencial" && s.alcada !== "Comitê") e.push("A reserva gerencial só é liberada pelo Comitê (patrocinador).");
    }
    if (aprova && s.liberacao) { e = e.concat(validarLiberacaoSm(s.projetoId, s.liberacao, s.codigo).map(function (x) { return x.msg || x; })); if (s.alcada !== "Comitê") e.push("Liberação de reserva é decidida pelo Comitê (patrocinador)."); }
    if (aprova && s.remanejamentos && !s.remanejamentoAplicado) e = e.concat(validarRemanejamentosSm(s.projetoId, s.remanejamentos, s.codigo).map(function (x) { return x.msg || x; }));
    var ata = d.ataId ? porId(M.atas)[d.ataId] : null;
    if (d.ataId && !ata) e.push({ campo: "ataId", msg: "Ata não encontrada." });
    var gerar = aprova ? acoesSugeridasSm(s).filter(function (a) { return (d.acoes || []).indexOf(a.chave) >= 0; }) : [];
    if (aprova && gerar.length) {
      if (!d.prevista) e.push({ campo: "prevista", msg: "Informe a data prevista das ações de implementação." });
      else if (d.data && d.prevista < d.data) e.push({ campo: "prevista", msg: "A data prevista não pode ser anterior à decisão." });
    }
    if (e.length) return Promise.reject({ erros: e });

    s.decisao = { data: d.data, resultado: d.resultado, participantesIds: part, justificativa: d.justificativa.trim(),
      condicoes: d.resultado === "Aprovada com condições" ? d.condicoes.trim() : "", ataId: ata ? ata.id : null,
      reapresentarEm: d.resultado === "Adiada" ? d.reapresentarEm : null, registradaPorId: sessaoPessoa(),
      ratificacao: !!s.emergencia };
    var extras = [];
    if (aprova) {
      s.situacao = d.resultado;
      var base = acoesDaMudanca(s.codigo).reduce(function (m, a) { return Math.max(m, Number(a.item) || 0); }, 0);
      gerar.forEach(function (g, k) {
        colecao("acoes").push({ id: proximoId("acoes"), projetoId: s.projetoId, origem: "Mudança", origemRef: s.codigo, item: String(base + k + 1),
          grupo: "Implementação", tipo: "Ação", assunto: g.assunto, descricao: "Implementação da mudança aprovada em " + dataBr(d.data) + " (" + g.modulo + ").",
          solicitanteId: sessaoPessoa(), responsavelId: g.responsavelId, prevista: d.prevista, replanejada: null, conclusao: null });
      });
      if (gerar.length) { persistir("acoes"); extras.push(gerar.length === 1 ? "1 ação de implementação na Central" : gerar.length + " ações de implementação na Central"); }
      if (s.impacto.custoCentavos) extras.push("custo aprovado disponível para nova revisão da EAC (03)");
      if (s.liberacao) extras.push("liberação de " + moedaBr(s.liberacao.valorCentavos) + " da reserva " + (s.liberacao.reserva === "Gerencial" ? "gerencial" : "de contingência"));
      if (s.remanejamentos && !s.remanejamentoAplicado) {
        aplicarRemanejamentosSm(s, d.data);
        extras.push("remanejamento aplicado na EAC (" + (s.remanejamentos.length === 1 ? "1 transferência" : s.remanejamentos.length + " transferências") + ", " + moedaBr(totalRemanejadoSm(s)) + ")");
      }
    } else if (d.resultado === "Rejeitada") {
      s.situacao = "Rejeitada"; s.encerramento = d.data;
    } else {
      s.situacao = "Adiada";
    }
    historicoMudanca(s, (s.emergencia ? "Ratificação da mudança emergencial: " : "Decisão: ") + d.resultado + " (" + s.alcada + ", " + part.length + (part.length === 1 ? " participante" : " participantes") + ")." +
      (d.resultado === "Aprovada com condições" ? " Condições: " + s.decisao.condicoes : "") + (d.resultado === "Adiada" ? " Volta à pauta em " + dataBr(d.reapresentarEm) + "." : "") +
      (ata ? " Ata " + ata.numero + "." : "") + (extras.length ? " Gerado: " + extras.join("; ") + "." : ""));
    persistir("mudancas");
    return responder({ codigo: codigo, situacao: s.situacao, acoes: gerar.length });
  }

  /* Adiada -> Aguardando comitê. TODO: API POST /mudancas/{codigo}/reapresentacao */
  function reapresentarMudanca(codigo) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite reapresentar a solicitação.");
    var s = smPorCodigo(codigo);
    if (!s) return rejeitar("Solicitação não encontrada.");
    if (s.situacao !== "Adiada") return rejeitar("Só solicitação Adiada pode ser reapresentada.");
    s.decisoesAnteriores = (s.decisoesAnteriores || []).concat([s.decisao]);
    s.decisao = null;
    s.situacao = "Aguardando comitê";
    historicoMudanca(s, "Solicitação reapresentada para decisão.");
    persistir("mudancas");
    return responder({ codigo: codigo });
  }

  /* Aprovada -> Em implementação. TODO: API POST /mudancas/{codigo}/implementacao */
  function iniciarImplementacaoSm(codigo) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite iniciar a implementação.");
    var s = smPorCodigo(codigo);
    if (!s) return rejeitar("Solicitação não encontrada.");
    if (["Aprovada", "Aprovada com condições"].indexOf(s.situacao) < 0) return rejeitar("Só mudança aprovada entra em implementação.");
    s.implementacao = { inicio: REF, porId: sessaoPessoa() };
    s.situacao = "Em implementação";
    historicoMudanca(s, "Implementação iniciada.");
    persistir("mudancas");
    return responder({ codigo: codigo });
  }

  /* Conferência do encerramento: o que a tela mostra e o que bloqueia */
  function conferenciaEncerramento(s) {
    var x = mudancaCalculada(s), im = s.impacto || {};
    return {
      acoesAbertas: x.acoesAbertas, exigeEac: x.exigeEac, eacRevisao: x.eacRevisao, exigeEap: x.exigeEap, eapRevisao: x.eapRevisao,
      exigeCronograma: !!im.prazoDias, exigeContrato: temImpacto(im.contrato), exigeRiscos: temImpacto(im.riscos),
      aditivos: x.aditivos
    };
  }
  /* Encerramento (Gestor): ações concluídas, EAC incorporada e linhas de base confirmadas; lição opcional.
     TODO: API POST /mudancas/{codigo}/encerramento */
  function encerrarMudanca(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("Encerrar a mudança exige papel Gestor.");
    var s = smPorCodigo(codigo);
    if (!s) return rejeitar("Solicitação não encontrada.");
    if (s.situacao !== "Em implementação") return rejeitar("Só mudança Em implementação pode ser encerrada.");
    var c = conferenciaEncerramento(s), e = [];
    if (c.acoesAbertas) e.push(c.acoesAbertas === 1 ? "Existe 1 ação de implementação em aberto na Central. Conclua-a antes de encerrar." : "Existem " + c.acoesAbertas + " ações de implementação em aberto na Central. Conclua-as antes de encerrar.");
    if (c.exigeEac && c.eacRevisao == null) e.push("O custo aprovado ainda não foi incorporado à EAC. Gere a nova revisão do orçamento em 03 Gestão Financeira > EAC.");
    if (c.exigeEap && c.eapRevisao == null) e.push("O impacto em escopo ainda não foi incorporado à EAP. Gere a nova revisão em 02 Planejamento > EAP.");
    if (c.exigeCronograma && !d.cronograma) e.push({ campo: "cronograma", msg: "Confirme a atualização da linha de base do cronograma e da Curva S." });
    if (c.exigeContrato && !d.contrato) e.push({ campo: "contrato", msg: "Confirme a formalização do aditivo contratual." });
    if (c.exigeRiscos && !d.riscos) e.push({ campo: "riscos", msg: "Confirme a revisão dos riscos afetados." });
    if (!d.data) e.push({ campo: "data", msg: "Informe a data do encerramento." });
    else if (d.data > REF) e.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    else if (s.implementacao && d.data < s.implementacao.inicio) e.push({ campo: "data", msg: "A data não pode ser anterior ao início da implementação." });
    if (d.registrarLicao) {
      e = e.concat(errosTexto(d, "licaoTitulo", "Título da lição", 10, 150), errosTexto(d, "licaoRecomendacao", "Recomendação", 20, 1000));
      if (TIPOS_LICAO.indexOf(d.licaoTipo) < 0) e.push({ campo: "licaoTipo", msg: "Escolha o tipo da lição." });
    }
    if (e.length) return Promise.reject({ erros: e });
    var det = { data: d.data, porId: sessaoPessoa(), cronograma: !!d.cronograma, contrato: !!d.contrato, riscos: !!d.riscos, eacRevisao: c.eacRevisao, eapRevisao: c.eapRevisao,
      observacao: (d.observacao || "").trim(), licaoRef: null };
    var extras = [];
    if (d.registrarLicao) {
      var proj = porId(M.projetos)[s.projetoId] || {};
      var lic = { id: proximoId("licoes"), projetoId: s.projetoId, codigo: proximoCodigo("licoes", "LA-" + (proj.padraoAta || "TN") + "-"),
        titulo: d.licaoTitulo.trim(), tipo: d.licaoTipo, fase: d.licaoFase || "Construção", area: AREA_POR_TIPO_SM[s.tipo] || "Escopo", disciplina: d.licaoDisciplina || "",
        origem: "Mudança " + s.codigo, aconteceu: s.titulo + ". " + s.descricao, causa: "Mudança " + s.tipo.toLowerCase() + " de origem " + s.origem.toLowerCase() + ".",
        impactoPrazoDias: Math.max(0, s.impacto.prazoDias || 0), impactoCustoCentavos: Math.max(0, s.impacto.custoCentavos || 0),
        recomendacao: d.licaoRecomendacao.trim(), palavrasChave: [s.tipo, s.origem, "mudança"], autorId: sessaoPessoa(), aplicabilidade: "Projeto",
        situacao: "Rascunho", data: d.data, reusos: 0, historico: [{ quando: agoraIso(), porId: sessaoPessoa(), texto: "Lição criada no encerramento da mudança " + s.codigo + "." }] };
      colecao("licoes").push(lic); persistir("licoes");
      det.licaoRef = lic.codigo; extras.push("lição " + lic.codigo + " em Rascunho");
    }
    s.encerramentoDetalhe = det;
    s.encerramento = d.data;
    s.situacao = "Encerrada";
    var revs = [c.eacRevisao != null ? "EAC Rev " + c.eacRevisao : "", c.eapRevisao != null ? "EAP Rev " + c.eapRevisao : ""].filter(Boolean).join(", ");
    historicoMudanca(s, "Mudança encerrada. Linhas de base conferidas" + (revs ? " (" + revs + ")" : "") + "." + (extras.length ? " Gerado: " + extras.join(", ") + "." : "") +
      (det.observacao ? " " + det.observacao : ""));
    persistir("mudancas");
    return responder({ codigo: codigo, licao: det.licaoRef });
  }

  /* Cancelamento a pedido do solicitante (ou Gestor), com justificativa. TODO: API POST /mudancas/{codigo}/cancelamento */
  function cancelarMudanca(codigo, d) {
    var s = smPorCodigo(codigo);
    if (!s) return rejeitar("Solicitação não encontrada.");
    if (!(temPapel("Gestor") || (temPapel("Membro") && s.solicitanteId === sessaoPessoa()))) return rejeitar("Só o solicitante ou um Gestor pode cancelar a solicitação.");
    if (SM_CANCELAVEL.indexOf(s.situacao) < 0) return rejeitar("Mudança já decidida não pode ser cancelada" + (s.situacao === "Em implementação" || s.situacao.indexOf("Aprovada") === 0 ? ": registre nova SM para reverter." : "."));
    var e = errosTexto(d, "justificativa", "Justificativa do cancelamento", 10, 500);
    if (e.length) return Promise.reject({ erros: e });
    s.cancelamento = { data: REF, porId: sessaoPessoa(), justificativa: d.justificativa.trim(), situacaoAnterior: s.situacao };
    s.situacao = "Cancelada"; s.encerramento = REF;
    historicoMudanca(s, "Solicitação cancelada: " + s.cancelamento.justificativa);
    persistir("mudancas");
    return responder({ codigo: codigo });
  }

  /* ---------------- 08 Governança: lições aprendidas ----------------
     Fluxo: Rascunho -> Em validação -> Validada -> Publicada (validação pelo PMO ou pela gerência do
     projeto, que não pode ser o autor). Aplicabilidade: Projeto (restrita ao projeto) ou Corporativa
     (compartilhada com a organização para os próximos projetos). */
  var TIPOS_LICAO = ["A repetir", "A evitar"];
  var FASES_LICAO = ["Iniciação", "Engenharia", "Suprimentos", "Construção", "Comissionamento", "Encerramento"];
  var AREAS_LICAO = ["Escopo", "Cronograma", "Custos", "Qualidade", "Recursos", "Comunicações", "Riscos", "Aquisições", "Partes interessadas", "SMS"];
  var SITUACOES_LICAO = ["Rascunho", "Em validação", "Validada", "Publicada"];
  var APLICABILIDADES = ["Projeto", "Corporativa"];
  var AREA_POR_TIPO_SM = { "Escopo": "Escopo", "Prazo": "Cronograma", "Custo": "Custos", "Qualidade/Especificação": "Qualidade", "Contratual": "Aquisições", "Remanejamento de orçamento": "Custos", "Liberação de reserva": "Custos" };
  /* Origens rastreáveis: palavra do registro -> tipo exibido e módulo */
  var ORIGENS_LICAO = [
    { tipo: "Ata (01)", palavra: "Ata" }, { tipo: "Punch list (02)", palavra: "Punch" },
    { tipo: "Contrato ou claim (03)", palavra: "Contrato" }, { tipo: "Suprimentos (04)", palavra: "Suprimentos" },
    { tipo: "Risco encerrado (05)", palavra: "Risco" }, { tipo: "RNC (06)", palavra: "RNC" },
    { tipo: "Ocorrência HSE (07)", palavra: "Ocorrência" }, { tipo: "Mudança (08)", palavra: "Mudança" },
    { tipo: "Workshop de lições", palavra: "Workshop de lições" }, { tipo: "Encerramento do projeto", palavra: "Encerramento do projeto" }
  ];
  var PALAVRA_TIPO = { "Ata": "Ata (01)", "Punch": "Punch list (02)", "Contrato": "Contrato ou claim (03)", "Claim": "Contrato ou claim (03)", "Avaliação": "Contrato ou claim (03)",
    "Suprimentos": "Suprimentos (04)", "Processo": "Suprimentos (04)", "Pedido": "Suprimentos (04)", "Risco": "Risco encerrado (05)", "RNC": "RNC (06)",
    "Ocorrência": "Ocorrência HSE (07)", "Mudança": "Mudança (08)", "Workshop": "Workshop de lições", "Encerramento": "Encerramento do projeto" };

  function licaoPorCodigo(codigo) { return porCampo(M.licoes, "codigo", codigo); }
  function origemDaLicao(l) {
    var o = String(l.origem || "").trim();
    var m = /^(.*?)\s+((?:[A-Z]{2,}-)[A-Z0-9-]*\d)$/.exec(o);
    var palavra = m ? m[1] : o, ref = m ? m[2] : null;
    var tipo = PALAVRA_TIPO[palavra.split(" ")[0]] || (palavra ? palavra : "Registro direto");
    return { tipo: tipo, ref: ref, texto: o };
  }
  /* Referência do registro de origem existe no módulo? (vínculo rastreável) */
  function refOrigemValida(tipo, ref, projetoId) {
    if (!ref) return false;
    switch (tipo) {
      case "Ata (01)": return (M.atas || []).some(function (a) { return a.numero === ref; });
      case "Punch list (02)": return !!porCampo(M.punch, "codigo", ref);
      case "Contrato ou claim (03)": return !!porCampo(M.contratos, "numero", ref) || !!porCampo(M.claims, "codigo", ref);
      case "Suprimentos (04)": return !!porCampo(M.pedidos, "numero", ref) || !!porCampo(M.pacotes, "codigo", ref);
      case "Risco encerrado (05)": return !!riscoPorCodigo(ref);
      case "RNC (06)": return !!porCampo(M.rncs, "codigo", ref);
      case "Ocorrência HSE (07)": return !!porCampo(M.ocorrencias, "codigo", ref);
      case "Mudança (08)": return !!smPorCodigo(ref);
      default: return true;
    }
  }
  var PALAVRA_ORIGEM = { "Ata (01)": "Ata", "Punch list (02)": "Punch list", "Contrato ou claim (03)": "Contrato", "Suprimentos (04)": "Suprimentos",
    "Risco encerrado (05)": "Risco", "RNC (06)": "RNC", "Ocorrência HSE (07)": "Ocorrência", "Mudança (08)": "Mudança" };
  function exigeRefOrigem(tipo) { return !!PALAVRA_ORIGEM[tipo]; }

  function historicoLicao(l, texto) {
    if (!l.historico) l.historico = [{ quando: l.data + "T08:00", porId: l.autorId, texto: "Lição registrada (" + origemDaLicao(l).texto + ")." }];
    l.historico.unshift({ quando: agoraIso(), porId: sessaoPessoa(), texto: texto });
  }
  function licaoCalculada(l) {
    var x = copia(l);
    var o = origemDaLicao(l);
    x.origemTipo = o.tipo; x.origemRef = o.ref;
    var proj = porId(M.projetos)[l.projetoId] || {};
    x.projetoCodigo = proj.codigo || "";
    x.aplicacoes = l.aplicacoes || [];
    x.reusos = l.reusos || 0;
    x.publicada = l.situacao === "Publicada";
    x.historicoExibicao = l.historico ? copia(l.historico) : [{ quando: l.data + "T08:00", porId: l.autorId, texto: "Lição registrada (" + o.texto + ")." }];
    if (o.tipo === "Ata (01)" && o.ref) { var ata = porCampo(M.atas, "numero", o.ref); x.ataId = ata ? ata.id : null; }
    return x;
  }
  /* Sistema de um projeto: o acervo é o das lições do projeto; lições de outros projetos só entram se
     vierem publicadas como Corporativas (importação futura do acervo da organização). */
  function licaoVisivel(l, ctxProjetoId) {
    if (ctxProjetoId == null || l.projetoId === ctxProjetoId) return true;
    return l.situacao === "Publicada" && l.aplicabilidade === "Corporativa";
  }
  /* TODO: API GET /licoes?contexto&busca&fase&area&disciplina&tipo&origem&projetoId&situacao&aplicabilidade */
  function listarLicoesDe(filtro) {
    filtro = filtro || {};
    var ctx = filtro.contextoProjetoId != null ? Number(filtro.contextoProjetoId) : null;
    var lista = (M.licoes || []).filter(function (l) { return licaoVisivel(l, ctx); }).map(licaoCalculada);   /* contexto null (Portfólio): acervo de todos os projetos */
    ["fase", "area", "tipo", "situacao", "aplicabilidade", "origemTipo"].forEach(function (k) { if (filtro[k]) lista = lista.filter(function (l) { return l[k] === filtro[k]; }); });
    if (filtro.disciplina) lista = lista.filter(function (l) { return U_norm(l.disciplina) === U_norm(filtro.disciplina); });
    if (filtro.projetoId) lista = lista.filter(function (l) { return l.projetoId === Number(filtro.projetoId); });
    if (filtro.busca) {
      var termos = U_norm(filtro.busca).split(/\s+/).filter(Boolean);
      lista = lista.filter(function (l) {
        var alvo = U_norm([l.codigo, l.titulo, l.aconteceu, l.causa, l.recomendacao, l.disciplina, l.origem].concat(l.palavrasChave || []).join(" "));
        return termos.every(function (t) { return alvo.indexOf(t) >= 0; });
      });
    }
    var ordem = { "Publicada": 0, "Validada": 1, "Em validação": 2, "Rascunho": 3 };
    return lista.sort(function (a, b) { return (ordem[a.situacao] - ordem[b.situacao]) || (a.data < b.data ? 1 : a.data > b.data ? -1 : 0); });
  }
  function listarLicoes(filtro) { return responder(listarLicoesDe(filtro)); }
  function obterLicao(codigo) { var l = licaoPorCodigo(codigo); return responder(l ? licaoCalculada(l) : null); }
  function disciplinasLicao() {
    var set = {};
    (M.licoes || []).forEach(function (l) { if (l.disciplina) set[l.disciplina] = true; });
    ["Civil", "Mecânica", "Tubulação", "Elétrica", "Automação", "Estruturas", "Processo"].forEach(function (d) { set[d] = true; });
    return Object.keys(set).sort(function (a, b) { return a.localeCompare(b); });
  }

  /* Nova lição ou edição (Rascunho; autor ou Gestor). enviar=true já manda para validação.
     TODO: API POST /licoes | PUT /licoes/{codigo} */
  function salvarLicao(d, enviar) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar lições.");
    var l = d.codigo ? licaoPorCodigo(d.codigo) : null;
    if (d.codigo && !l) return rejeitar("Lição não encontrada.");
    if (l && l.situacao !== "Rascunho") return rejeitar("Só lição em Rascunho pode ser editada (lição devolvida volta a Rascunho).");
    if (l && l.autorId !== sessaoPessoa() && !temPapel("Gestor")) return rejeitar("Só o autor ou um Gestor edita a lição.");
    var e = [];
    e = e.concat(errosTexto(d, "titulo", "Título", 10, 150));
    if (TIPOS_LICAO.indexOf(d.tipo) < 0) e.push({ campo: "tipo", msg: "Escolha o tipo." });
    if (FASES_LICAO.indexOf(d.fase) < 0) e.push({ campo: "fase", msg: "Escolha a fase." });
    if (AREAS_LICAO.indexOf(d.area) < 0) e.push({ campo: "area", msg: "Escolha a área de conhecimento." });
    e = e.concat(errosTexto(d, "disciplina", "Disciplina", 3, 60));
    var tiposOrigem = ORIGENS_LICAO.map(function (o) { return o.tipo; }).concat(["Registro direto"]);
    if (tiposOrigem.indexOf(d.origemTipo) < 0) e.push({ campo: "origemTipo", msg: "Escolha a origem." });
    else if (exigeRefOrigem(d.origemTipo)) {
      var ref = String(d.origemRef || "").trim().toUpperCase();
      if (!ref) e.push({ campo: "origemRef", msg: "Informe o número do registro de origem (rastreabilidade)." });
      else if (!refOrigemValida(d.origemTipo, ref)) e.push({ campo: "origemRef", msg: "Registro " + ref + " não encontrado no módulo de origem." });
    }
    e = e.concat(errosTexto(d, "aconteceu", "O que aconteceu", 20, 1000), errosTexto(d, "causa", "Causa", 10, 600), errosTexto(d, "recomendacao", "Recomendação", 20, 1000));
    if (d.impactoPrazoDias == null || d.impactoPrazoDias < 0 || Math.round(d.impactoPrazoDias) !== Number(d.impactoPrazoDias)) e.push({ campo: "impactoPrazoDias", msg: "Informe o impacto em prazo em dias (zero ou mais)." });
    if (d.impactoCustoCentavos == null || isNaN(d.impactoCustoCentavos) || d.impactoCustoCentavos < 0) e.push({ campo: "impactoCustoCentavos", msg: "Informe o impacto em custo (zero ou mais)." });
    var palavras = String(d.palavrasChave || "").split(/[,;]/).map(function (p) { return p.trim(); }).filter(Boolean);
    if (!palavras.length) e.push({ campo: "palavrasChave", msg: "Informe ao menos uma palavra-chave (separe por vírgula)." });
    else if (palavras.length > 8) e.push({ campo: "palavrasChave", msg: "Use no máximo 8 palavras-chave." });
    if (APLICABILIDADES.indexOf(d.aplicabilidade) < 0) e.push({ campo: "aplicabilidade", msg: "Escolha a aplicabilidade." });
    var projetoId = l ? l.projetoId : Number(d.projetoId);
    var proj = porId(M.projetos)[projetoId];
    if (!proj) e.push("Projeto não encontrado.");
    if (e.length) return Promise.reject({ erros: e });
    var novo = !l;
    if (novo) {
      l = { id: proximoId("licoes"), projetoId: projetoId, codigo: proximoCodigo("licoes", "LA-" + (proj.padraoAta || "TN") + "-"),
        autorId: sessaoPessoa(), situacao: "Rascunho", data: REF, reusos: 0, historico: [] };
    }
    l.titulo = d.titulo.trim(); l.tipo = d.tipo; l.fase = d.fase; l.area = d.area; l.disciplina = d.disciplina.trim();
    l.origem = exigeRefOrigem(d.origemTipo) ? PALAVRA_ORIGEM[d.origemTipo] + " " + String(d.origemRef).trim().toUpperCase() : d.origemTipo;
    l.aconteceu = d.aconteceu.trim(); l.causa = d.causa.trim(); l.recomendacao = d.recomendacao.trim();
    l.impactoPrazoDias = Math.round(d.impactoPrazoDias); l.impactoCustoCentavos = Math.round(d.impactoCustoCentavos);
    l.palavrasChave = palavras; l.aplicabilidade = d.aplicabilidade;
    if (novo) { colecao("licoes").push(l); l.historico.push({ quando: agoraIso(), porId: sessaoPessoa(), texto: "Lição registrada (" + l.origem + ")." }); }
    else historicoLicao(l, "Lição editada.");
    if (enviar) { l.situacao = "Em validação"; l.devolucao = null; historicoLicao(l, "Enviada para validação."); }
    persistir("licoes");
    return responder({ codigo: l.codigo, situacao: l.situacao, novo: novo });
  }
  /* Rascunho -> Em validação. TODO: API POST /licoes/{codigo}/envio */
  function enviarLicaoValidacao(codigo) {
    var l = licaoPorCodigo(codigo);
    if (!l) return rejeitar("Lição não encontrada.");
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite enviar a lição.");
    if (l.situacao !== "Rascunho") return rejeitar("Só lição em Rascunho pode ser enviada para validação.");
    if (l.autorId !== sessaoPessoa() && !temPapel("Gestor")) return rejeitar("Só o autor ou um Gestor envia a lição para validação.");
    if (!l.recomendacao || l.recomendacao.length < 20 || !l.disciplina) return rejeitar("Complete a lição (disciplina e recomendação com 20 caracteres ou mais) antes de enviar. Use Editar.");
    l.situacao = "Em validação"; l.devolucao = null;
    historicoLicao(l, "Enviada para validação.");
    persistir("licoes");
    return responder({ codigo: codigo });
  }
  /* Validação pelo PMO ou gerência do projeto (Gestor, diferente do autor).
     resultado: "Validada" | "Publicada" (valida e publica) | "Devolvida" (volta a Rascunho com comentário).
     TODO: API POST /licoes/{codigo}/validacao */
  function validarLicao(codigo, d) {
    if (!temPapel("Gestor")) return rejeitar("A validação é feita pelo PMO ou pela gerência do projeto (papel Gestor).");
    var l = licaoPorCodigo(codigo);
    if (!l) return rejeitar("Lição não encontrada.");
    if (l.situacao !== "Em validação") return rejeitar("Só lição Em validação pode ser validada ou devolvida.");
    if (l.autorId === sessaoPessoa()) return rejeitar("O autor não pode validar a própria lição (segregação de funções).");
    var e = [];
    if (["Validada", "Publicada", "Devolvida"].indexOf(d.resultado) < 0) e.push({ campo: "resultado", msg: "Escolha o resultado da validação." });
    if (d.resultado === "Devolvida") e = e.concat(errosTexto(d, "comentario", "Comentário para o autor", 10, 500));
    if (d.resultado !== "Devolvida" && APLICABILIDADES.indexOf(d.aplicabilidade) < 0) e.push({ campo: "aplicabilidade", msg: "Confirme a aplicabilidade." });
    if (e.length) return Promise.reject({ erros: e });
    if (d.resultado === "Devolvida") {
      l.situacao = "Rascunho"; l.devolucao = { data: REF, porId: sessaoPessoa(), comentario: d.comentario.trim() };
      historicoLicao(l, "Devolvida ao autor: " + l.devolucao.comentario);
    } else {
      var mudouAplic = l.aplicabilidade !== d.aplicabilidade;
      l.aplicabilidade = d.aplicabilidade;
      l.validacao = { data: REF, porId: sessaoPessoa(), comentario: (d.comentario || "").trim() };
      l.situacao = d.resultado;
      if (d.resultado === "Publicada") l.dataPublicacao = REF;
      historicoLicao(l, (d.resultado === "Publicada" ? "Validada e publicada no acervo" : "Validada") + " (aplicabilidade " + l.aplicabilidade + (mudouAplic ? ", ajustada na validação" : "") + ")." +
        (l.validacao.comentario ? " " + l.validacao.comentario : ""));
    }
    persistir("licoes");
    return responder({ codigo: codigo, situacao: l.situacao });
  }
  /* Validada -> Publicada. TODO: API POST /licoes/{codigo}/publicacao */
  function publicarLicao(codigo) {
    if (!temPapel("Gestor")) return rejeitar("Publicar no acervo exige papel Gestor.");
    var l = licaoPorCodigo(codigo);
    if (!l) return rejeitar("Lição não encontrada.");
    if (l.situacao !== "Validada") return rejeitar("Só lição Validada pode ser publicada.");
    l.situacao = "Publicada"; l.dataPublicacao = REF;
    historicoLicao(l, "Publicada no acervo (aplicabilidade " + l.aplicabilidade + ").");
    persistir("licoes");
    return responder({ codigo: codigo });
  }
  /* Aplicar em projeto: registra o reuso e pode gerar ação na Central (origem Lição) ou risco no 05.
     TODO: API POST /licoes/{codigo}/aplicacoes */
  function aplicarLicao(codigo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar a aplicação da lição.");
    var l = licaoPorCodigo(codigo);
    if (!l) return rejeitar("Lição não encontrada.");
    if (l.situacao !== "Publicada") return rejeitar("Só lição publicada no acervo pode ser aplicada.");
    var projetoId = Number(d.projetoId), proj = porId(M.projetos)[projetoId];
    var e = [];
    if (!proj) e.push({ campo: "projetoId", msg: "Escolha o projeto." });
    else if (!licaoVisivel(l, projetoId)) e.push({ campo: "projetoId", msg: "A aplicabilidade da lição (" + l.aplicabilidade + ") não alcança este projeto." });
    if (!d.data) e.push({ campo: "data", msg: "Informe a data." });
    else if (d.data > REF) e.push({ campo: "data", msg: "A data não pode ser posterior à referência." });
    e = e.concat(errosTexto(d, "como", "Como a lição será aplicada", 20, 600));
    if (["nada", "acao", "risco"].indexOf(d.gerar) < 0) e.push({ campo: "gerar", msg: "Escolha o que gerar." });
    if (d.gerar === "acao") {
      if (!d.responsavelId || !porId(M.pessoas)[d.responsavelId]) e.push({ campo: "responsavelId", msg: "Escolha o responsável pela ação." });
      if (!d.prevista) e.push({ campo: "prevista", msg: "Informe a data prevista." });
      else if (d.prevista < REF) e.push({ campo: "prevista", msg: "A data prevista não pode ser anterior à referência." });
    }
    var cat = String(d.categoria || "").split(" > ");
    if (d.gerar === "risco") {
      if (!d.categoria || !categoriaValida(cat[0], cat[1])) e.push({ campo: "categoria", msg: "Escolha a categoria da RBS." });
      if (!d.donoId || !porId(M.pessoas)[d.donoId]) e.push({ campo: "donoId", msg: "Escolha o dono do risco." });
    }
    if (e.length) return Promise.reject({ erros: e });
    var ap = { projetoId: projetoId, data: d.data, como: d.como.trim(), porId: sessaoPessoa(), acaoItem: null, riscoRef: null };
    var extras = [];
    if (d.gerar === "acao") {
      var item = acoesComStatus(function (a) { return a.origem === "Lição" && a.origemRef === l.codigo; }).reduce(function (m, a) { return Math.max(m, Number(a.item) || 0); }, 0) + 1;
      colecao("acoes").push({ id: proximoId("acoes"), projetoId: projetoId, origem: "Lição", origemRef: l.codigo, item: String(item), grupo: "Reuso", tipo: "Ação",
        assunto: "Aplicar a lição " + l.codigo + ": " + l.titulo, descricao: ap.como, solicitanteId: sessaoPessoa(), responsavelId: Number(d.responsavelId),
        prevista: d.prevista, replanejada: null, conclusao: null });
      persistir("acoes"); ap.acaoItem = String(item); extras.push("ação na Central");
    } else if (d.gerar === "risco") {
      var natureza = l.tipo === "A evitar" ? "Ameaça" : "Oportunidade";
      var r = { id: proximoId("riscos"), projetoId: projetoId, codigo: proximoCodigo("riscos", (proj.padraoRisco || "RSK") + "-"),
        identificadoPorId: sessaoPessoa(), inerente: null, residual: null, riscoVida: false, dimensao: null, impactoPrazoDias: l.impactoPrazoDias || 0,
        impactoCustoCentavos: l.impactoCustoCentavos || 0, estrategia: null, plano: "", severidadeAlvo: null, prazoAlvo: null, cadenciaDias: null,
        ultimaRevisao: null, proximaRevisao: null, situacao: "Identificado", revisoes: [], natureza: natureza, categoria: cat[0], subcategoria: cat[1] || "",
        causa: l.causa, titulo: l.titulo, consequencia: l.aconteceu, descricao: "Identificado a partir da lição " + l.codigo + ". Recomendação: " + l.recomendacao,
        gatilho: null, donoId: Number(d.donoId), identificadoEm: d.data > REF ? REF : d.data, origemTipo: "Lições aprendidas", origem: "Lição " + l.codigo, ataId: null,
        historico: [{ quando: agoraIso(), porId: sessaoPessoa(), texto: "Risco criado a partir da lição " + l.codigo + " (Aplicar em projeto)." }] };
      colecao("riscos").push(r); persistir("riscos");
      ap.riscoRef = r.codigo; extras.push("risco " + r.codigo + " no registro");
    }
    l.aplicacoes = (l.aplicacoes || []).concat([ap]);
    l.reusos = (l.reusos || 0) + 1;
    historicoLicao(l, "Aplicada no projeto " + proj.codigo + "." + (extras.length ? " Gerado: " + extras.join(", ") + "." : ""));
    persistir("licoes");
    return responder({ codigo: codigo, acao: ap.acaoItem, risco: ap.riscoRef });
  }

  /* Painel do acervo: por fase, área e tipo; publicadas no período; reuso; dias sem registro de lição.
     TODO: API GET /projetos/{id}/licoes/painel */
  function painelLicoes(filtro) {
    filtro = filtro || {};
    var lista = listarLicoesDe({ contextoProjetoId: filtro.contextoProjetoId, projetoId: filtro.projetoId });
    var dias = (P().licoes || {}).alertaSemRegistroDias || 90;
    var desde = somarDiasIso(REF, -dias);
    var publicadas = lista.filter(function (l) { return l.situacao === "Publicada"; });
    function por(campo, ordem) {
      return ordem.map(function (k) {
        var doK = lista.filter(function (l) { return l[campo] === k; });
        return { chave: k, total: doK.length, aRepetir: doK.filter(function (l) { return l.tipo === "A repetir"; }).length, aEvitar: doK.filter(function (l) { return l.tipo === "A evitar"; }).length,
          publicadas: doK.filter(function (l) { return l.situacao === "Publicada"; }).length };
      });
    }
    var pid = filtro.contextoProjetoId != null ? Number(filtro.contextoProjetoId) : projetoAtualId();
    var ultima = (M.licoes || []).filter(function (l) { return pid == null || l.projetoId === pid; }).map(function (l) { return l.data; }).sort().pop() || null;
    return responder({
      total: lista.length, publicadas: publicadas.length,
      publicadasPeriodo: publicadas.filter(function (l) { return (l.dataPublicacao || l.data) >= desde; }).length,
      emFluxo: lista.filter(function (l) { return l.situacao !== "Publicada"; }).length,
      emValidacao: lista.filter(function (l) { return l.situacao === "Em validação"; }).length,
      aRepetir: lista.filter(function (l) { return l.tipo === "A repetir"; }).length, aEvitar: lista.filter(function (l) { return l.tipo === "A evitar"; }).length,
      taxaReusoPct: publicadas.length ? arred(publicadas.filter(function (l) { return l.reusos > 0; }).length / publicadas.length * 100, 1) : null,
      reusos: soma(publicadas, "reusos"),
      impactoEvitarCentavos: soma(lista.filter(function (l) { return l.tipo === "A evitar"; }), "impactoCustoCentavos"),
      porFase: por("fase", FASES_LICAO), porArea: por("area", AREAS_LICAO).filter(function (a) { return a.total; }).sort(function (a, b) { return b.total - a.total; }),
      porSituacao: SITUACOES_LICAO.map(function (s) { return { chave: s, total: lista.filter(function (l) { return l.situacao === s; }).length }; }),
      ultimaLicao: ultima, diasSemRegistro: ultima ? R.diasEntre(ultima, REF) : null, semRegistroAlerta: !ultima || ultima < desde, diasAlerta: dias,
      maisReusadas: publicadas.filter(function (l) { return l.reusos > 0; }).sort(function (a, b) { return b.reusos - a.reusos; }).slice(0, 5)
    });
  }

  /* ======================================================================
     02 Planejamento > Produtividade
     Plano de quantidades da linha de base (LB) por empresa, distribuído por semana ISO,
     com apontamento semanal do realizado e das HH apropriadas; horas efetivas registradas
     pela fiscalização (capacidade produtiva, amostragem do trabalho e paralisações);
     KPIs de performance geral e por empresa. Cálculos só aqui (as telas não calculam).
     ====================================================================== */
  var GRUPOS_QTD = ["Cabo elétrico", "Concreto", "Aço", "Tubulação", "Painel elétrico", "Outros"];
  var UNIDADES_QTD = ["m", "m³", "t", "un", "m²", "kg"];
  var PERFIS_QTD = [
    { id: "curvaS", nome: "Curva S (rampa, pico e desmobilização)" }, { id: "linear", nome: "Linear (uniforme)" },
    { id: "inicio", nome: "Concentrado no início" }, { id: "fim", nome: "Concentrado no fim" }
  ];
  var MOTIVOS_PARADO = ["Direcionamento da liderança para execução", "Descanso entre atividades", "Término da atividade antecessora",
    "Raio de ação de içamento (munck, guindaste)", "Pit stop", "Raio de ação de máquina", "Dúvida de execução / interferência",
    "Mais pessoas que a frente de serviço comporta", "Material / insumo / acessório", "Sobreposição de atividades na própria frente",
    "Direito de recusa (trabalho seguro)", "Máquina ou equipamento indisponível"];
  var MOTIVOS_TRANSITO = ["Material / insumo / acessório", "Água / banheiro", "Entre frentes de serviço", "Ferramenta", "Máquina / equipamento"];
  var MOTIVOS_PARALISACAO = ["Chuva / condição climática", "Falta de material", "Falta de liberação de área / permissão de trabalho",
    "Interferência com a operação da planta", "Aguardando equipamento de içamento", "Quebra de máquina / equipamento",
    "Aguardando frente (atividade predecessora)", "Falta de projeto / dúvida técnica", "Parada de segurança", "Terceiros (concreteira, concessionária)"];
  var RESPONSABILIDADES = ["Contratada", "Cliente", "Gerenciadora", "Clima", "Terceiros"];
  /* Responsabilidade que não é da contratada: tempo perdido potencialmente excusável (e, se do cliente, compensável): base de pleito (03) */
  var RESP_EXTERNA = ["Cliente", "Gerenciadora", "Terceiros"];
  var SM_REVISAO_LB = ["Aprovada", "Aprovada com condições", "Em implementação"];

  function parProd() {
    var d = { jornadaDiariaHoras: 8.8, metaTrabalhandoPct: 60, metaUtilizacaoPct: 75, aderenciaFaixas: [75, 90], pfFaixas: [1.0, 1.1], semanasMedia: 4 };
    var p = (M.parametros || {}).produtividade || {};
    Object.keys(p).forEach(function (k) { d[k] = p[k]; });
    return d;
  }
  function semanaAtual() { return R.semanaIso(REF); }
  function arredQtd(v, casas) { return arred(v, casas == null ? 2 : casas); }
  function casasUnidade(u) { return u === "t" ? 1 : 0; }

  /* ---- Quantidades ---- */
  function calcularItemQtd(it, corte, janela) {
    var sem = corte || semanaAtual(), N = janela || parProd().semanasMedia;
    var ini = R.somarSemanas(sem, -(N - 1));
    var prevAcum = 0, realAcum = 0, hhAcum = 0, prevSem = 0, realSem = null, prevJan = 0, realJan = 0, hhJan = 0, realCapJan = 0;
    var dist = {}; it.distribuicao.forEach(function (d) { dist[d.semana] = d.previsto; });
    it.distribuicao.forEach(function (d) {
      if (d.semana <= sem) prevAcum += d.previsto;
      if (d.semana === sem) prevSem = d.previsto;
      if (d.semana >= ini && d.semana <= sem) prevJan += d.previsto;
    });
    var semanasComApont = [];
    it.apontamentos.forEach(function (a) {
      if (a.semana > sem) return;
      realAcum += a.realizado; hhAcum += a.hh || 0;
      if (a.semana === sem) realSem = a.realizado;
      if (a.semana >= ini) { realJan += a.realizado; hhJan += a.hh || 0; realCapJan += Math.min(a.realizado, dist[a.semana] || 0); }
      semanasComApont.push(a.semana);
    });
    var c = it.casas;
    prevAcum = arredQtd(prevAcum, c); realAcum = arredQtd(realAcum, c); prevJan = arredQtd(prevJan, c); realJan = arredQtd(realJan, c);
    var aprovado = it.situacao === "Aprovada";
    var ativo = aprovado && it.inicio <= sem && (sem <= it.fim || realAcum < it.total);
    var pendente = ativo && realSem == null && sem <= semanaAtual() && (prevSem > 0 || realAcum < it.total);
    var hg = realAcum * it.indiceHH, hp = prevAcum * it.indiceHH, ho = it.total * it.indiceHH;
    var saldo = arredQtd(Math.max(0, it.total - realAcum), c);
    /* Tendência de término pelo prazo agregado (earned schedule): ES = semanas da LB necessárias
       para chegar ao realizado acumulado; SPI(t) = ES ÷ semanas decorridas; duração prevista = duração da LB ÷ SPI(t). */
    var ritmo = realJan / N, tendencia = null, desvioSemanas = null, spiT = null;
    if (aprovado && realAcum > 0) {
      if (saldo <= 0) tendencia = semanasComApont.sort()[semanasComApont.length - 1];
      else {
        var decorridas = R.semanasEntre(it.inicio, sem) + 1, acc = 0, es = 0;
        for (var k = 0; k < it.distribuicao.length; k++) {
          var pv = it.distribuicao[k].previsto;
          if (acc + pv >= realAcum) { es = k + (pv ? (realAcum - acc) / pv : 0); break; }
          acc += pv; es = k + 1;
        }
        spiT = decorridas > 0 ? es / decorridas : null;
        if (spiT > 0) tendencia = R.somarSemanas(it.inicio, Math.max(decorridas, Math.ceil(it.distribuicao.length / spiT)) - 1);
      }
      if (tendencia) desvioSemanas = R.semanasEntre(it.fim, tendencia);
    }
    return {
      prevAcum: prevAcum, realAcum: realAcum, hhAcum: hhAcum, prevSem: prevSem, realSem: realSem, saldo: saldo,
      pctPrev: it.total ? arred(prevAcum / it.total * 100, 1) : null, pctReal: it.total ? arred(realAcum / it.total * 100, 1) : null,
      desvioPp: it.total ? arred((realAcum - prevAcum) / it.total * 100, 1) : null,
      aderenciaSem: prevSem > 0 && realSem != null ? arred(Math.min(realSem, prevSem) / prevSem * 100, 1) : null,
      realSobrePrevSem: prevSem > 0 && realSem != null ? arred(realSem / prevSem * 100, 1) : null,
      aderenciaJan: prevJan > 0 ? arred(realCapJan / prevJan * 100, 1) : null,
      pf: hg > 0 ? arred(hhAcum / hg, 2) : null, pfJan: realJan > 0 ? arred(hhJan / (realJan * it.indiceHH), 2) : null,
      hg: hg, hp: hp, ho: ho, hhJan: hhJan, hgJan: realJan * it.indiceHH, prevJanHH: prevJan * it.indiceHH, realCapJanHH: realCapJan * it.indiceHH,
      prevSemHH: prevSem * it.indiceHH, realSemCapHH: realSem == null ? 0 : Math.min(realSem, prevSem) * it.indiceHH,
      ritmo: arredQtd(ritmo, c), spiT: arred(spiT, 2), tendencia: tendencia, desvioSemanas: desvioSemanas, ativo: ativo, pendente: pendente, aprovado: aprovado
    };
  }
  function itensQtdDe(projetoId) { return doProjeto(M.produtividadeItens, projetoId); }
  function itemQtdCalculado(it, corte) { var x = copia(it); x.calc = calcularItemQtd(it, corte); return x; }

  /* Série semanal (previsto e realizado; em HH ganhas quando mistura unidades) */
  function serieQtd(itens, emHH) {
    var semanas = {};
    itens.forEach(function (it) {
      it.distribuicao.forEach(function (d) { semanas[d.semana] = true; });
      it.apontamentos.forEach(function (a) { semanas[a.semana] = true; });
    });
    var lista = Object.keys(semanas).sort();
    var total = soma(itens, function (it) { return emHH ? it.total * it.indiceHH : it.total; });
    var prev = [], real = [], pa = 0, ra = 0, prevAc = [], realAc = [];
    var atual = semanaAtual();
    lista.forEach(function (s) {
      var p = 0, r = null;
      itens.forEach(function (it) {
        var f = emHH ? it.indiceHH : 1;
        it.distribuicao.forEach(function (d) { if (d.semana === s) p += d.previsto * f; });
        it.apontamentos.forEach(function (a) { if (a.semana === s) r = (r || 0) + a.realizado * f; });
      });
      pa += p; prev.push(arred(p, 1)); prevAc.push(total ? arred(pa / total * 100, 1) : null);
      if (s <= atual) { ra += r || 0; real.push(r == null ? (s < atual ? 0 : null) : arred(r, 1)); realAc.push(total ? arred(ra / total * 100, 1) : null); }
      else { real.push(null); realAc.push(null); }
    });
    return { semanas: lista, previsto: prev, realizado: real, prevAcumPct: prevAc, realAcumPct: realAc, emHH: !!emHH };
  }

  function resumoGrupos(itens) {
    var g = {};
    itens.forEach(function (it) {
      if (!it.calc.aprovado) return;
      var k = it.grupo + "|" + it.unidade;
      if (!g[k]) g[k] = { grupo: it.grupo, unidade: it.unidade, casas: it.casas, itens: 0, total: 0, prevAcum: 0, realAcum: 0, prevSem: 0, realSem: 0 };
      var x = g[k];
      x.itens += 1; x.total += it.total; x.prevAcum += it.calc.prevAcum; x.realAcum += it.calc.realAcum; x.prevSem += it.calc.prevSem; x.realSem += it.calc.realSem || 0;
    });
    return GRUPOS_QTD.map(function (nome) {
      return Object.keys(g).filter(function (k) { return g[k].grupo === nome; }).map(function (k) {
        var x = g[k];
        ["total", "prevAcum", "realAcum", "prevSem", "realSem"].forEach(function (c) { x[c] = arredQtd(x[c], x.casas); });
        x.pctPrev = x.total ? arred(x.prevAcum / x.total * 100, 1) : null; x.pctReal = x.total ? arred(x.realAcum / x.total * 100, 1) : null;
        return x;
      });
    }).reduce(function (a, b) { return a.concat(b); }, []);
  }

  /* TODO: API GET /projetos/{id}/produtividade/quantidades?corte&empresa&grupo */
  function quantidades(projetoId, opcoes) {
    opcoes = opcoes || {};
    var corte = opcoes.corte || semanaAtual();
    var todos = itensQtdDe(projetoId);
    var filtrados = todos.filter(function (it) {
      return (!opcoes.empresaId || it.empresaId === Number(opcoes.empresaId)) && (!opcoes.grupo || it.grupo === opcoes.grupo);
    });
    var itens = filtrados.map(function (it) { return itemQtdCalculado(it, corte); });
    var aprov = itens.filter(function (it) { return it.calc.aprovado; });
    var semanasCorte = {};
    todos.forEach(function (it) { if (it.inicio <= semanaAtual()) semanasCorte[it.inicio] = true; });
    var primeira = Object.keys(semanasCorte).sort()[0] || semanaAtual();
    var unidades = {}; aprov.forEach(function (it) { unidades[it.unidade] = true; });
    var emHH = !opcoes.grupo || Object.keys(unidades).length > 1;
    return responder({
      corte: corte, semanaAtual: semanaAtual(), semanasCorte: R.listaSemanas(primeira, semanaAtual()),
      itens: itens, grupos: resumoGrupos(itens),
      indicadores: indicadoresQtd(aprov.map(function (x) { return x.calc; })),
      emElaboracao: itens.filter(function (it) { return it.situacao === "Em elaboração"; }).length,
      serie: serieQtd(filtrados.filter(function (it) { return it.situacao === "Aprovada"; }), emHH),
      unidadeSerie: emHH ? "HH" : Object.keys(unidades)[0] || ""
    });
  }
  function indicadoresQtd(calcs) {
    var ho = soma(calcs, "ho"), hg = soma(calcs, "hg"), hp = soma(calcs, "hp"), hh = soma(calcs, "hhAcum");
    var prevSemHH = soma(calcs, "prevSemHH"), realSemCap = soma(calcs, "realSemCapHH");
    var comApont = calcs.filter(function (c) { return c.prevSemHH > 0 && c.realSem != null; });
    var prevSemApont = soma(comApont, "prevSemHH");
    return {
      itens: calcs.length, pctPrev: ho ? arred(hp / ho * 100, 1) : null, pctReal: ho ? arred(hg / ho * 100, 1) : null,
      spi: hp ? arred(hg / hp, 2) : null, pf: hg ? arred(hh / hg, 2) : null,
      pfJan: soma(calcs, "hgJan") ? arred(soma(calcs, "hhJan") / soma(calcs, "hgJan"), 2) : null,
      aderenciaSem: prevSemApont ? arred(soma(comApont, "realSemCapHH") / prevSemApont * 100, 1) : null,
      aderenciaJan: soma(calcs, "prevJanHH") ? arred(soma(calcs, "realCapJanHH") / soma(calcs, "prevJanHH") * 100, 1) : null,
      pendentes: calcs.filter(function (c) { return c.pendente; }).length,
      tendenciaAtraso: calcs.filter(function (c) { return c.desvioSemanas > 0; }).length,
      hhApropriadas: hh, horasGanhas: arred(hg, 0), horasOrcadas: arred(ho, 0), prevSemHH: arred(prevSemHH, 0), realSemCapHH: arred(realSemCap, 0)
    };
  }

  function validarDistribuicao(d, casas, congeladas) {
    var erros = [];
    var tol = Math.pow(10, -(casas || 0)) / 2;
    if (!d.valores || !d.valores.length) erros.push("Distribua a quantidade por semana.");
    else {
      if (d.valores.some(function (v) { return v == null || isNaN(v) || v < 0; })) erros.push({ campo: "distribuicao", msg: "As quantidades semanais devem ser números maiores ou iguais a zero." });
      var s = d.valores.reduce(function (a, v) { return a + (Number(v) || 0); }, 0) + (congeladas || 0);
      if (Math.abs(s - d.total) > tol) erros.push({ campo: "distribuicao", msg: "A soma das semanas (" + arredQtd(s, casas) + ") precisa fechar com o total da LB (" + d.total + ")." });
    }
    return erros;
  }
  function proximoCodigoQtd(projetoId) {
    var itens = itensQtdDe(projetoId);
    var n = itens.reduce(function (m, it) { var k = parseInt(String(it.codigo).replace(/^.*\D/, ""), 10); return isNaN(k) ? m : Math.max(m, k); }, 0) + 1;
    var pref = itens.length ? String(itens[0].codigo).replace(/\d+$/, "") : "QTD-";
    return pref + (n < 10 ? "0" : "") + n;
  }
  /* Novo item ou edição de item em elaboração. TODO: API POST /projetos/{id}/produtividade/itens, PUT /produtividade/itens/{id} */
  function salvarItemQtd(d) {
    var existente = d.id ? porId(M.produtividadeItens)[d.id] : null;
    if (existente && existente.situacao === "Aprovada") {
      existente.observacoes = d.observacoes || "";
      persistir("produtividadeItens");
      return responder(existente);
    }
    var erros = [];
    if (!d.empresaId) erros.push({ campo: "empresaId", msg: "Escolha a empresa." });
    if (!d.grupo) erros.push({ campo: "grupo", msg: "Escolha o grupo." });
    if (!d.tipo || d.tipo.length < 3) erros.push({ campo: "tipo", msg: "Descreva o tipo (ex.: Cabo de controle)." });
    if (!(d.total > 0)) erros.push({ campo: "total", msg: "A quantidade total da LB deve ser maior que zero." });
    if (!(d.indiceHH > 0)) erros.push({ campo: "indiceHH", msg: "Informe o índice orçado (HH por unidade), maior que zero." });
    var sem = R.listaSemanas(d.inicio, d.fim);
    if (!R.inicioSemana(d.inicio) || !R.inicioSemana(d.fim) || !sem.length) erros.push({ campo: "fim", msg: "A semana final deve ser igual ou posterior à inicial." });
    else if (sem.length > 104) erros.push({ campo: "fim", msg: "A distribuição passa de 104 semanas; divida o item." });
    var casas = casasUnidade(d.unidade);
    if (!erros.length) erros = erros.concat(validarDistribuicao({ total: d.total, valores: d.valores }, casas));
    if (!erros.length && d.valores.length !== sem.length) erros.push("A distribuição não corresponde às semanas escolhidas.");
    if (erros.length) return rejeitar(erros);
    var it = existente || { id: proximoId("produtividadeItens"), projetoId: d.projetoId, codigo: proximoCodigoQtd(d.projetoId), situacao: "Em elaboração", revisao: 0,
      aprovadoPorId: null, aprovadoEm: null, apontamentos: [], revisoes: [], elaboradoPorId: sessaoPessoa() };
    it.empresaId = Number(d.empresaId); it.grupo = d.grupo; it.tipo = d.tipo; it.disciplina = d.disciplina || ""; it.unidade = d.unidade; it.casas = casas;
    it.total = d.total; it.indiceHH = d.indiceHH; it.inicio = d.inicio; it.fim = d.fim; it.perfil = d.perfil || "curvaS"; it.observacoes = d.observacoes || "";
    it.distribuicao = sem.map(function (s, k) { return { semana: s, previsto: arredQtd(Number(d.valores[k]), casas) }; });
    if (!existente) colecao("produtividadeItens").push(it);
    persistir("produtividadeItens");
    return responder(it);
  }
  /* Aprovação da LB do item (congela a distribuição). TODO: API POST /produtividade/itens/{id}/aprovacao */
  function aprovarItemQtd(id) {
    var it = porId(M.produtividadeItens)[id];
    if (!it) return rejeitar("Item não encontrado.");
    if (!temPapel("Gestor")) return rejeitar("Só o papel Gestor aprova a linha de base.");
    if (it.situacao !== "Em elaboração") return rejeitar("O item já está aprovado.");
    if (it.elaboradoPorId && it.elaboradoPorId === sessaoPessoa()) return rejeitar("Quem elaborou a distribuição não pode aprová-la (segregação de funções).");
    it.situacao = "Aprovada"; it.aprovadoPorId = sessaoPessoa(); it.aprovadoEm = REF;
    it.revisoes = (it.revisoes || []).concat([{ rev: it.revisao || 0, data: REF, porId: sessaoPessoa(), total: it.total, smRef: null, justificativa: "Linha de base aprovada." }]);
    persistir("produtividadeItens");
    return responder(it);
  }
  /* Revisão da LB de item aprovado: só com SM aprovada (08); semanas até a atual ficam congeladas.
     TODO: API POST /produtividade/itens/{id}/revisoes */
  function revisarItemQtd(id, d) {
    var it = porId(M.produtividadeItens)[id];
    if (!it) return rejeitar("Item não encontrado.");
    if (it.situacao !== "Aprovada") return rejeitar("Item em elaboração não precisa de revisão: edite a distribuição.");
    var erros = [];
    var sm = porCampo(doProjeto(M.mudancas, it.projetoId), "codigo", d.smRef);
    if (!sm || SM_REVISAO_LB.indexOf(sm.situacao) < 0) erros.push({ campo: "smRef", msg: "Escolha uma SM aprovada (08) que autoriza a revisão da linha de base." });
    if (!d.justificativa || d.justificativa.length < 15) erros.push({ campo: "justificativa", msg: "Justifique a revisão (mínimo de 15 caracteres)." });
    var atual = semanaAtual(), primeiraLivre = R.somarSemanas(atual, 1);
    var real = calcularItemQtd(it, atual).realAcum;
    if (!(d.total >= real)) erros.push({ campo: "total", msg: "O novo total não pode ser menor que o realizado acumulado (" + real + " " + it.unidade + ")." });
    if (!d.fim || d.fim < primeiraLivre) erros.push({ campo: "fim", msg: "A nova semana final deve ser posterior à semana atual (" + atual + ")." });
    var congeladas = it.distribuicao.filter(function (x) { return x.semana <= atual; });
    var somaCong = soma(congeladas, "previsto");
    var livres = d.fim ? R.listaSemanas(it.inicio > primeiraLivre ? it.inicio : primeiraLivre, d.fim) : [];
    if (!erros.length && (!d.valores || d.valores.length !== livres.length)) erros.push("A distribuição não corresponde às semanas futuras.");
    if (!erros.length) erros = erros.concat(validarDistribuicao({ total: d.total, valores: d.valores }, it.casas, somaCong));
    if (erros.length) return rejeitar(erros);
    var anterior = it.total;
    it.distribuicao = congeladas.concat(livres.map(function (s, k) { return { semana: s, previsto: arredQtd(Number(d.valores[k]), it.casas) }; }));
    it.total = d.total; it.fim = d.fim; it.revisao = (it.revisao || 0) + 1; it.perfil = d.perfil || it.perfil;
    it.revisoes = (it.revisoes || []).concat([{ rev: it.revisao, data: REF, porId: sessaoPessoa(), total: d.total, totalAnterior: anterior, smRef: d.smRef, desde: livres[0], justificativa: d.justificativa }]);
    persistir("produtividadeItens");
    return responder(it);
  }
  /* TODO: API DELETE /produtividade/itens/{id} */
  function excluirItemQtd(id) {
    var it = porId(M.produtividadeItens)[id];
    if (!it) return rejeitar("Item não encontrado.");
    if (it.situacao !== "Em elaboração" || (it.apontamentos || []).length) return rejeitar("Só item em elaboração e sem apontamento pode ser excluído.");
    return excluir("produtividadeItens", id);
  }
  /* Apontamento semanal da contratada (realizado e HH apropriadas), upsert por item e semana.
     TODO: API PUT /projetos/{id}/produtividade/apontamentos/{semana}?empresa */
  function apontarSemanaQtd(projetoId, empresaId, semana, linhas) {
    var erros = [];
    if (!R.inicioSemana(semana)) erros.push({ campo: "semana", msg: "Escolha a semana." });
    else if (semana > semanaAtual()) erros.push({ campo: "semana", msg: "Não é possível apontar semana futura." });
    var mapa = porId(M.produtividadeItens);
    (linhas || []).forEach(function (l) {
      var it = mapa[l.itemId];
      if (!it || it.projetoId !== projetoId || it.empresaId !== Number(empresaId)) { erros.push("Item inválido para a empresa."); return; }
      if (it.situacao !== "Aprovada") erros.push(it.codigo + ": a linha de base ainda não foi aprovada.");
      if (l.realizado == null && l.hh == null) return;
      if ((l.realizado || 0) < 0 || (l.hh || 0) < 0) erros.push(it.codigo + ": use valores maiores ou iguais a zero.");
      if ((l.realizado || 0) > 0 && !(l.hh > 0)) erros.push(it.codigo + ": informe as HH apropriadas da semana (base do fator de produtividade).");
      var outras = soma(it.apontamentos.filter(function (a) { return a.semana !== semana; }), "realizado");
      if (outras + (l.realizado || 0) > it.total + Math.pow(10, -(it.casas || 0)) / 2) {
        erros.push(it.codigo + ": o acumulado (" + arredQtd(outras + (l.realizado || 0), it.casas) + " " + it.unidade + ") passa o total da LB (" + it.total + "). Registre uma SM (08) para revisar a linha de base antes de apontar.");
      }
    });
    if (erros.length) return rejeitar(erros);
    var n = 0;
    linhas.forEach(function (l) {
      if (l.realizado == null && l.hh == null) return;
      var it = mapa[l.itemId];
      var a = it.apontamentos.filter(function (x) { return x.semana === semana; })[0];
      if (!a) { a = { semana: semana }; it.apontamentos.push(a); it.apontamentos.sort(function (x, y) { return x.semana < y.semana ? -1 : 1; }); }
      a.realizado = arredQtd(l.realizado || 0, it.casas); a.hh = Math.round(l.hh || 0); a.informadoEm = REF; a.informadoPorId = sessaoPessoa();
      n++;
    });
    persistir("produtividadeItens");
    return responder(n);
  }
  /* Importação do plano de quantidades (itens entram em elaboração, distribuídos pelo perfil).
     TODO: API POST /projetos/{id}/produtividade/itens/importacao */
  function importarItensQtd(projetoId, linhas) {
    var empresas = M.empresas || [];
    var criados = [];
    linhas.forEach(function (l) {
      var emp = empresas.filter(function (e) { return e.nome === l.empresa; })[0];
      var perfil = (PERFIS_QTD.filter(function (p) { return p.nome.indexOf(l.perfil) === 0 || p.id === l.perfil; })[0] || PERFIS_QTD[0]).id;
      var sem = R.listaSemanas(l.inicio, l.fim);
      var casas = casasUnidade(l.unidade);
      var it = { id: proximoId("produtividadeItens"), projetoId: projetoId, codigo: proximoCodigoQtd(projetoId), empresaId: emp ? emp.id : null, grupo: l.grupo, tipo: l.tipo,
        disciplina: l.disciplina || "", unidade: l.unidade, casas: casas, total: l.total, indiceHH: l.indiceHH, inicio: l.inicio, fim: l.fim, perfil: perfil,
        situacao: "Em elaboração", revisao: 0, aprovadoPorId: null, aprovadoEm: null, observacoes: "Importado do Excel", apontamentos: [], revisoes: [], elaboradoPorId: sessaoPessoa(),
        distribuicao: [] };
      var v = R.distribuirQuantidade(l.total, sem.length, perfil, casas);
      it.distribuicao = sem.map(function (s, k) { return { semana: s, previsto: v[k] }; });
      colecao("produtividadeItens").push(it);
      criados.push(it.codigo);
    });
    persistir("produtividadeItens");
    return responder(criados);
  }

  /* ---- Horas efetivas (fiscalização de campo) ---- */
  function noFiltro(x, f) {
    return (!f.projetoId || x.projetoId === f.projetoId) && (!f.empresaId || x.empresaId === Number(f.empresaId)) &&
      (!f.area || x.area === f.area) && (!f.encarregado || x.encarregado === f.encarregado) &&
      (!f.de || x.data >= f.de) && (!f.ate || x.data <= f.ate);
  }
  function calcularJornada(j) {
    var mn = R.minutos;
    var atrasoM = mn(j.manha.inicio) - mn(j.manha.chegada), execM = R.duracaoHoras(j.manha.inicio, j.manha.termino);
    var almoco = mn(j.tarde.chegada) - mn(j.manha.termino), atrasoT = mn(j.tarde.inicio) - mn(j.tarde.chegada), execT = R.duracaoHoras(j.tarde.inicio, j.tarde.termino);
    var cp = (execM || 0) + (execT || 0), jor = parProd().jornadaDiariaHoras;
    return { atrasoManhaMin: atrasoM, execManha: execM, almocoMin: almoco, atrasoTardeMin: atrasoT, execTarde: execT, cp: arred(cp, 2),
      utilizacao: arred(cp / jor * 100, 1), hhEfetivas: arred(cp * j.efetivo, 1), hhImprodutivas: arred(Math.max(0, jor - cp) * j.efetivo, 1), semana: R.semanaIso(j.data) };
  }
  function media(lista, fn) { var v = lista.map(fn).filter(function (x) { return x != null && !isNaN(x); }); return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : null; }
  function hhmm(min) { if (min == null) return null; min = Math.round(min); return ("0" + Math.floor(min / 60)).slice(-2) + ":" + ("0" + (min % 60)).slice(-2); }
  function resumoJornadas(js) {
    var mn = R.minutos;
    var r = {
      registros: js.length, efetivoMedio: arred(media(js, function (j) { return j.efetivo; }), 1),
      manha: { chegada: hhmm(media(js, function (j) { return mn(j.manha.chegada); })), inicio: hhmm(media(js, function (j) { return mn(j.manha.inicio); })), termino: hhmm(media(js, function (j) { return mn(j.manha.termino); })) },
      tarde: { chegada: hhmm(media(js, function (j) { return mn(j.tarde.chegada); })), inicio: hhmm(media(js, function (j) { return mn(j.tarde.inicio); })), termino: hhmm(media(js, function (j) { return mn(j.tarde.termino); })) },
      atrasoManhaMin: arred(media(js, function (j) { return j.calc.atrasoManhaMin; }), 0), atrasoTardeMin: arred(media(js, function (j) { return j.calc.atrasoTardeMin; }), 0),
      cpManha: arred(media(js, function (j) { return j.calc.execManha; }), 2), cpTarde: arred(media(js, function (j) { return j.calc.execTarde; }), 2),
      almocoMin: arred(media(js, function (j) { return j.calc.almocoMin; }), 0),
      cp: arred(media(js, function (j) { return j.calc.cp; }), 2),
      hhEfetivas: arred(soma(js, function (j) { return j.calc.hhEfetivas; }), 0), hhImprodutivas: arred(soma(js, function (j) { return j.calc.hhImprodutivas; }), 0)
    };
    r.utilizacao = r.cp == null ? null : arred(r.cp / parProd().jornadaDiariaHoras * 100, 1);
    return r;
  }
  function agrupar(lista, chave) {
    var g = {};
    lista.forEach(function (x) { var k = typeof chave === "function" ? chave(x) : x[chave]; (g[k] = g[k] || []).push(x); });
    return g;
  }
  function resumoAmostras(as) {
    var t = soma(as, "trabalhando"), tr = soma(as, "transito"), p = soma(as, "parado"), n = t + tr + p;
    return { observacoes: as.length, pessoas: n, trabalhando: t, transito: tr, parado: p,
      pctTrabalhando: n ? arred(t / n * 100, 2) : null, pctTransito: n ? arred(tr / n * 100, 2) : null, pctParado: n ? arred(p / n * 100, 2) : null };
  }
  function contarMotivos(as, campo, catalogo) {
    var c = {};
    as.forEach(function (a) { (a[campo] || []).forEach(function (m) { c[m.motivo] = (c[m.motivo] || 0) + m.qtd; }); });
    return Object.keys(c).map(function (k) { return { chave: k, total: c[k] }; }).sort(function (a, b) { return b.total - a.total || catalogo.indexOf(a.chave) - catalogo.indexOf(b.chave); });
  }
  function calcularParalisacao(p) {
    var h = R.duracaoHoras(p.inicio, p.termino) || 0;
    return { horas: arred(h, 2), total: arred(h * p.quantidade, 1), externa: RESP_EXTERNA.indexOf(p.responsabilidade) >= 0, semana: R.semanaIso(p.data) };
  }
  function resumoParalisacoes(ps) {
    var ef = ps.filter(function (p) { return p.tipo === "Efetivo"; }), mq = ps.filter(function (p) { return p.tipo !== "Efetivo"; });
    function porCh(lista, ch) {
      var g = agrupar(lista, ch);
      return Object.keys(g).map(function (k) { return { chave: k, total: arred(soma(g[k], function (p) { return p.calc.total; }), 1), eventos: g[k].length }; })
        .sort(function (a, b) { return b.total - a.total; });
    }
    return {
      eventos: ps.length, hhora: arred(soma(ef, function (p) { return p.calc.total; }), 1), mhora: arred(soma(mq, function (p) { return p.calc.total; }), 1),
      hhoraExterna: arred(soma(ef.filter(function (p) { return p.calc.externa; }), function (p) { return p.calc.total; }), 1),
      hhoraCliente: arred(soma(ef.filter(function (p) { return p.responsabilidade === "Cliente"; }), function (p) { return p.calc.total; }), 1),
      hhoraClima: arred(soma(ef.filter(function (p) { return p.responsabilidade === "Clima"; }), function (p) { return p.calc.total; }), 1),
      porMotivoEfetivo: porCh(ef, "motivo"), porMotivoMaquina: porCh(mq, "motivo"), porResponsabilidade: porCh(ef, "responsabilidade"),
      porResponsabilidadeMaquina: porCh(mq, "responsabilidade")
    };
  }
  function jornadasDe(f) { return (M.jornadasCampo || []).filter(function (j) { return noFiltro(j, f); }).map(function (j) { var x = copia(j); x.calc = calcularJornada(j); return x; }); }
  function amostrasDe(f) { return (M.amostragens || []).filter(function (a) { return noFiltro(a, f); }).map(copia); }
  function paralisacoesDe(f) { return (M.paralisacoes || []).filter(function (p) { return noFiltro(p, f); }).map(function (p) { var x = copia(p); x.calc = calcularParalisacao(p); return x; }); }

  /* TODO: API GET /projetos/{id}/produtividade/horas-efetivas?de&ate&empresa&area&encarregado */
  function horasEfetivas(filtro) {
    var f = filtro || {};
    var js = jornadasDe(f), as = amostrasDe(f), ps = paralisacoesDe(f);
    var base = { projetoId: f.projetoId };
    var todasJ = (M.jornadasCampo || []).filter(function (j) { return noFiltro(j, base); });
    var areas = {}, encs = {};
    todasJ.concat(M.amostragens || []).concat(M.paralisacoes || []).forEach(function (x) {
      if (f.projetoId && x.projetoId !== f.projetoId) return;
      if (x.area) areas[x.area] = true;
      if (x.encarregado && (!f.empresaId || x.empresaId === Number(f.empresaId))) encs[x.encarregado] = true;
    });
    var jPorArea = agrupar(js, "area"), pPorArea = agrupar(ps, "area");
    var nomesAreas = Object.keys(jPorArea).concat(Object.keys(pPorArea)).filter(function (x, k, a) { return a.indexOf(x) === k; }).sort();
    var porArea = nomesAreas.map(function (a) {
      var rj = resumoJornadas(jPorArea[a] || []), rp = resumoParalisacoes(pPorArea[a] || []);
      return { area: a, cp: rj.cp, utilizacao: rj.utilizacao, hhora: rp.hhora, mhora: rp.mhora, registros: rj.registros };
    });
    var jPorDia = agrupar(js, "data"), aPorDia = agrupar(as, "data");
    var dias = Object.keys(jPorDia).concat(Object.keys(aPorDia)).filter(function (x, k, a) { return a.indexOf(x) === k; }).sort();
    var porDia = dias.map(function (d) {
      var rj = resumoJornadas(jPorDia[d] || []), ra = resumoAmostras(aPorDia[d] || []);
      return { data: d, cp: rj.cp, pctTrabalhando: ra.pctTrabalhando, pctTransito: ra.pctTransito, pctParado: ra.pctParado };
    });
    /* amostragem por empresa e encarregado */
    var aPorEmp = agrupar(as, "empresaId");
    var porEmpresa = Object.keys(aPorEmp).map(function (e) {
      var r = resumoAmostras(aPorEmp[e]); r.empresaId = Number(e);
      var pe = agrupar(aPorEmp[e], "encarregado");
      r.encarregados = Object.keys(pe).sort().map(function (n) { var x = resumoAmostras(pe[n]); x.encarregado = n; return x; });
      return r;
    });
    return responder({
      filtro: f, areas: Object.keys(areas).sort(), encarregados: Object.keys(encs).sort(),
      jornadas: js.sort(function (a, b) { return a.data < b.data ? 1 : a.data > b.data ? -1 : a.id - b.id; }),
      capacidade: resumoJornadas(js), porArea: porArea, porDia: porDia,
      amostragem: resumoAmostras(as), amostras: as.sort(function (a, b) { return a.data < b.data ? 1 : a.data > b.data ? -1 : (a.hora < b.hora ? 1 : -1); }),
      motivosParado: contarMotivos(as, "motivosParado", MOTIVOS_PARADO), motivosTransito: contarMotivos(as, "motivosTransito", MOTIVOS_TRANSITO),
      amostragemPorEmpresa: porEmpresa,
      paralisacoes: ps.sort(function (a, b) { return a.data < b.data ? 1 : a.data > b.data ? -1 : b.id - a.id; }), resumoParalisacoes: resumoParalisacoes(ps),
      parametros: parProd()
    });
  }
  function validarHora(v) { return R.minutos(v) != null; }
  /* TODO: API POST/PUT /projetos/{id}/produtividade/jornadas */
  function salvarJornada(d) {
    var erros = [];
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "Não é possível registrar data futura." });
    if (!d.empresaId) erros.push({ campo: "empresaId", msg: "Escolha a empresa." });
    if (!d.area) erros.push({ campo: "area", msg: "Informe a área (CWA)." });
    if (!d.encarregado) erros.push({ campo: "encarregado", msg: "Informe o encarregado." });
    if (!(d.efetivo >= 1)) erros.push({ campo: "efetivo", msg: "Informe o efetivo na frente (1 ou mais)." });
    var campos = [["mChegada", "manha", "chegada"], ["mInicio", "manha", "inicio"], ["mTermino", "manha", "termino"], ["tChegada", "tarde", "chegada"], ["tInicio", "tarde", "inicio"], ["tTermino", "tarde", "termino"]];
    var ok = true;
    campos.forEach(function (c) { if (!validarHora(d[c[0]])) { erros.push({ campo: c[0], msg: "Informe a hora (hh:mm)." }); ok = false; } });
    if (ok) {
      var seq = campos.map(function (c) { return R.minutos(d[c[0]]); });
      for (var k = 1; k < seq.length; k++) if (seq[k] < seq[k - 1]) { erros.push({ campo: campos[k][0], msg: "Os horários devem seguir a ordem: chegada, início e término de cada turno, e a tarde depois da manhã." }); break; }
    }
    var dup = (M.jornadasCampo || []).filter(function (j) { return j.id !== Number(d.id) && j.projetoId === d.projetoId && j.data === d.data && j.empresaId === Number(d.empresaId) && j.area === d.area && j.encarregado === d.encarregado; })[0];
    if (dup) erros.push("Já existe registro desta frente (empresa, área e encarregado) nesta data. Edite o registro existente.");
    if (erros.length) return rejeitar(erros);
    var j = d.id ? porId(M.jornadasCampo)[d.id] : null;
    if (!j) { j = { id: proximoId("jornadasCampo"), projetoId: d.projetoId, registradoPorId: sessaoPessoa() }; colecao("jornadasCampo").push(j); }
    j.data = d.data; j.empresaId = Number(d.empresaId); j.area = d.area; j.encarregado = d.encarregado; j.efetivo = d.efetivo;
    j.manha = { chegada: d.mChegada, inicio: d.mInicio, termino: d.mTermino }; j.tarde = { chegada: d.tChegada, inicio: d.tInicio, termino: d.tTermino };
    j.observacoes = d.observacoes || "";
    persistir("jornadasCampo");
    return responder(j);
  }
  /* TODO: API POST/PUT /projetos/{id}/produtividade/amostragens */
  function salvarAmostragem(d) {
    var erros = [];
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "Não é possível registrar data futura." });
    if (!validarHora(d.hora)) erros.push({ campo: "hora", msg: "Informe a hora da rodada." });
    if (!d.empresaId) erros.push({ campo: "empresaId", msg: "Escolha a empresa." });
    if (!d.area) erros.push({ campo: "area", msg: "Informe a área (CWA)." });
    if (!d.encarregado) erros.push({ campo: "encarregado", msg: "Informe o encarregado." });
    function lista(obj, cat) { return cat.map(function (m) { return { motivo: m, qtd: Math.max(0, Math.round(Number((obj || {})[m]) || 0)) }; }).filter(function (x) { return x.qtd > 0; }); }
    var mp = lista(d.motivosParado, MOTIVOS_PARADO), mt = lista(d.motivosTransito, MOTIVOS_TRANSITO);
    var trab = Math.max(0, Math.round(Number(d.trabalhando) || 0));
    var total = trab + soma(mp, "qtd") + soma(mt, "qtd");
    if (!(total > 0)) erros.push({ campo: "trabalhando", msg: "Registre ao menos uma pessoa observada." });
    if (erros.length) return rejeitar(erros);
    var a = d.id ? porId(M.amostragens)[d.id] : null;
    if (!a) { a = { id: proximoId("amostragens"), projetoId: d.projetoId, observadorId: sessaoPessoa() }; colecao("amostragens").push(a); }
    a.data = d.data; a.hora = d.hora; a.empresaId = Number(d.empresaId); a.area = d.area; a.encarregado = d.encarregado;
    a.trabalhando = trab; a.transito = soma(mt, "qtd"); a.parado = soma(mp, "qtd"); a.motivosParado = mp; a.motivosTransito = mt;
    persistir("amostragens");
    return responder(a);
  }
  /* TODO: API POST/PUT /projetos/{id}/produtividade/paralisacoes */
  function salvarParalisacao(d) {
    var erros = [];
    if (!d.data) erros.push({ campo: "data", msg: "Informe a data." });
    else if (d.data > REF) erros.push({ campo: "data", msg: "Não é possível registrar data futura." });
    if (!d.empresaId) erros.push({ campo: "empresaId", msg: "Escolha a empresa." });
    if (!d.area) erros.push({ campo: "area", msg: "Informe a área (CWA)." });
    if (["Efetivo", "Máquina/Equipamento"].indexOf(d.tipo) < 0) erros.push({ campo: "tipo", msg: "Escolha o tipo." });
    if (!d.recurso) erros.push({ campo: "recurso", msg: "Descreva o recurso parado (equipe, máquina ou equipamento)." });
    if (!(d.quantidade >= 1)) erros.push({ campo: "quantidade", msg: "Informe a quantidade (1 ou mais)." });
    if (!validarHora(d.inicio)) erros.push({ campo: "inicio", msg: "Informe a hora de início." });
    if (!validarHora(d.termino)) erros.push({ campo: "termino", msg: "Informe a hora de término." });
    else if (validarHora(d.inicio) && R.minutos(d.termino) <= R.minutos(d.inicio)) erros.push({ campo: "termino", msg: "O término deve ser depois do início." });
    if (MOTIVOS_PARALISACAO.indexOf(d.motivo) < 0) erros.push({ campo: "motivo", msg: "Escolha o motivo." });
    if (RESPONSABILIDADES.indexOf(d.responsabilidade) < 0) erros.push({ campo: "responsabilidade", msg: "Escolha a responsabilidade." });
    if (erros.length) return rejeitar(erros);
    var p = d.id ? porId(M.paralisacoes)[d.id] : null;
    if (!p) { p = { id: proximoId("paralisacoes"), projetoId: d.projetoId, registradoPorId: sessaoPessoa() }; colecao("paralisacoes").push(p); }
    ["data", "area", "tipo", "recurso", "inicio", "termino", "motivo", "responsabilidade"].forEach(function (k) { p[k] = d[k]; });
    p.empresaId = Number(d.empresaId); p.quantidade = d.quantidade; p.descricao = d.descricao || "";
    persistir("paralisacoes");
    return responder(p);
  }

  /* ---- KPIs de performance: geral e por empresa ----
     Janela: N semanas até a semana de corte (parâmetro semanasMedia).
     TODO: API GET /projetos/{id}/produtividade/kpis?corte */
  function kpisProdutividade(projetoId, corte) { return responder(kpisProdutividadeDe(projetoId, corte)); }
  function kpisProdutividadeDe(projetoId, corte) {
    corte = corte || semanaAtual();
    var par = parProd(), N = par.semanasMedia;
    var iniJan = R.somarSemanas(corte, -(N - 1));
    var de = R.inicioSemana(iniJan), ateD = new Date(R.inicioSemana(corte) + "T12:00:00Z"); ateD.setUTCDate(ateD.getUTCDate() + 6);
    var ate = ateD.toISOString().slice(0, 10);
    if (ate > REF) ate = REF;
    var itens = itensQtdDe(projetoId);
    var semanasJan = R.listaSemanas(iniJan, corte);
    var tendSemanas = R.listaSemanas(R.somarSemanas(corte, -11), corte);
    var empresasIds = {};
    itens.forEach(function (it) { empresasIds[it.empresaId] = true; });
    (M.jornadasCampo || []).concat(M.amostragens || []).concat(M.paralisacoes || []).forEach(function (x) { if (projetoId == null || x.projetoId === projetoId) empresasIds[x.empresaId] = true; });

    function bloco(empresaId) {
      var its = itens.filter(function (it) { return !empresaId || it.empresaId === empresaId; });
      var aprov = its.filter(function (it) { return it.situacao === "Aprovada"; });
      var q = indicadoresQtd(aprov.map(function (it) { return calcularItemQtd(it, corte); }));
      var f = { projetoId: projetoId, empresaId: empresaId || null, de: de, ate: ate };
      var rj = resumoJornadas(jornadasDe(f)), ra = resumoAmostras(amostrasDe(f)), rp = resumoParalisacoes(paralisacoesDe(f));
      var hhDisp = soma(jornadasDe(f), function (j) { return j.efetivo * par.jornadaDiariaHoras; });
      /* tendência semanal: PF, aderência, % trabalhando, CP */
      var tend = tendSemanas.map(function (s) {
        var cs = aprov.map(function (it) {
          var a = it.apontamentos.filter(function (x) { return x.semana === s; })[0];
          var d = it.distribuicao.filter(function (x) { return x.semana === s; })[0];
          return { hh: a ? a.hh || 0 : 0, hg: a ? a.realizado * it.indiceHH : 0, prev: d ? d.previsto * it.indiceHH : 0, cap: a && d ? Math.min(a.realizado, d.previsto) * it.indiceHH : 0, temA: !!a };
        });
        var hg = soma(cs, "hg"), hh = soma(cs, "hh"), prev = soma(cs.filter(function (c) { return c.temA; }), "prev");
        var ini = R.inicioSemana(s), fimD = new Date(ini + "T12:00:00Z"); fimD.setUTCDate(fimD.getUTCDate() + 6);
        var fs = { projetoId: projetoId, empresaId: empresaId || null, de: ini, ate: fimD.toISOString().slice(0, 10) };
        return { semana: s, pf: hg ? arred(hh / hg, 2) : null, aderencia: prev ? arred(soma(cs, "cap") / prev * 100, 1) : null,
          pctTrabalhando: resumoAmostras(amostrasDe(fs)).pctTrabalhando, cp: resumoJornadas(jornadasDe(fs)).cp };
      });
      return {
        empresaId: empresaId || null, quantidades: q, capacidade: rj, amostragem: ra, paralisacoes: rp,
        hhDisponiveis: arred(hhDisp, 0), pctHhoraParalisada: hhDisp ? arred(rp.hhora / hhDisp * 100, 2) : null,
        itensSemLb: its.filter(function (it) { return it.situacao !== "Aprovada"; }).length,
        acaoAberta: acaoProdutividadeAberta(projetoId, empresaId, corte), tendencia: tend,
        faixas: {
          aderencia: R.faixaIndicador(q.aderenciaJan, par.aderenciaFaixas, true), pf: R.faixaIndicador(q.pfJan, par.pfFaixas, false),
          spi: q.spi == null ? null : q.spi >= (par.spiFaixas || [0.85, 0.95])[1] ? "success" : q.spi >= (par.spiFaixas || [0.85, 0.95])[0] ? "warning" : "danger",
          trabalhando: ra.pctTrabalhando == null ? null : ra.pctTrabalhando >= par.metaTrabalhandoPct ? "success" : ra.pctTrabalhando >= par.metaTrabalhandoPct - 10 ? "warning" : "danger",
          utilizacao: rj.utilizacao == null ? null : rj.utilizacao >= par.metaUtilizacaoPct ? "success" : rj.utilizacao >= par.metaUtilizacaoPct - 10 ? "warning" : "danger"
        }
      };
    }
    var geral = bloco(null);
    var porEmpresa = Object.keys(empresasIds).map(Number).sort(function (a, b) { return nomeEmpresa(a).localeCompare(nomeEmpresa(b)); }).map(bloco);
    porEmpresa.forEach(function (b) {
      var f = b.faixas;
      b.alertas = ["aderencia", "pf", "spi", "trabalhando", "utilizacao"].filter(function (k) { return f[k] === "danger"; });
      b.atencao = ["aderencia", "pf", "spi", "trabalhando", "utilizacao"].filter(function (k) { return f[k] === "warning"; });
    });
    return { corte: corte, janela: { semanas: semanasJan, de: de, ate: ate, n: N }, parametros: par, geral: geral, porEmpresa: porEmpresa };
  }
  function refAcaoProdutividade(empresaId, corte) { return "PRD-" + corte + "-" + ("0" + empresaId).slice(-2); }
  function acaoProdutividadeAberta(projetoId, empresaId, corte) {
    if (!empresaId) return null;
    var ref = refAcaoProdutividade(empresaId, corte);
    var a = acoesComStatus(function (x) { return (projetoId == null || x.projetoId === projetoId) && x.origem === "Produtividade" && x.origemRef === ref && !x.conclusao; })[0];
    return a ? { id: a.id, ref: ref } : null;
  }
  /* Plano de recuperação na Central (origem Produtividade). TODO: API POST /projetos/{id}/produtividade/acoes */
  function gerarAcaoProdutividade(projetoId, empresaId, corte, d) {
    var erros = [];
    if (!d.assunto || d.assunto.length < 10) erros.push({ campo: "assunto", msg: "Descreva a ação (mínimo de 10 caracteres)." });
    if (!d.responsavelId) erros.push({ campo: "responsavelId", msg: "Escolha o responsável." });
    if (!d.prevista) erros.push({ campo: "prevista", msg: "Informe a data prevista." });
    else if (d.prevista < REF) erros.push({ campo: "prevista", msg: "A data prevista não pode ser anterior à data de referência." });
    if (acaoProdutividadeAberta(projetoId, empresaId, corte)) erros.push("Já existe ação aberta na Central para esta empresa e semana.");
    if (erros.length) return rejeitar(erros);
    var ref = refAcaoProdutividade(empresaId, corte);
    var acao = { id: proximoId("acoes"), projetoId: projetoId, origem: "Produtividade", origemRef: ref, item: "1", grupo: "Produtividade", tipo: "Ação",
      assunto: d.assunto, descricao: d.descricao || "", solicitanteId: sessaoPessoa(), responsavelId: Number(d.responsavelId), prevista: d.prevista, replanejada: null, conclusao: null };
    colecao("acoes").push(acao); persistir("acoes");
    return responder(copia(acao));
  }

  /* ======================================================================
     Home: um indicador-chave por módulo e pontos de atenção
     TODO: API GET /projetos/{id}/resumo
     ====================================================================== */
  function resumoHome(projetoId) {
    if (projetoId === undefined) projetoId = projetoAtualId();
    var proj = projetoOuCarteira(projetoId);
    var cod = function (pid) { return projetoId == null ? ((porId(M.projetos)[pid] || {}).codigo || "") + " · " : ""; };
    var acoes = resumoAcoes(projetoId);
    var fis = indicesFisicos(projetoId);
    var custo = indicesCustoDe(projetoId);
    var sup = indicadoresSuprimentosDe(projetoId);
    var rsk = resumoRiscosDe(projetoId);
    var qual = indicadoresQualidadeDe(projetoId);
    var hse = indicadoresHSEDe(projetoId);
    var sm = resumoMudancasDe(projetoId);
    var pl = resumoPunch(projetoId);
    var ctr = resumoContratos(projetoId);

    var alertas = [];
    acoesComStatus(function (a) { return (projetoId == null || a.projetoId === projetoId) && a.status === "atrasada"; })
      .sort(function (a, b) { return b.diasAtraso - a.diasAtraso; }).slice(0, projetoId == null ? 4 : 3).forEach(function (a) {
        alertas.push({ modulo: "central-acoes", nivel: "danger", projetoId: a.projetoId, titulo: cod(a.projetoId) + a.assunto, detalhe: a.origem + " " + (a.origemRef || "") + " · " + a.diasAtraso + " dias de atraso" });
      });
    pedidosDe(projetoId).filter(function (p) { return p.critico; }).forEach(function (p) {
      alertas.push({ modulo: "suprimentos", nivel: "danger", projetoId: p.projetoId, titulo: cod(p.projetoId) + p.numero + " " + p.descricao, detalhe: "Folga de " + p.folgaDias + " dias em relação à data necessária na obra" });
    });
    idsEscopo(projetoId).forEach(function (pid) {
      var plp = resumoPunch(pid);
      if (plp.sistemasBloqueados.length) {
        alertas.push({ modulo: "planejamento", nivel: "warning", projetoId: pid, titulo: cod(pid) + plp.abertosA + (plp.abertosA === 1 ? " item A aberto" : " itens A abertos") + " na Punch list",
          detalhe: "Sistemas bloqueados: " + plp.sistemasBloqueados.map(function (s) { return s.codigo + " " + s.nome; }).join(", ") });
      }
    });
    riscosDe(projetoId).filter(function (r) { return r.revisaoVencida; }).forEach(function (r) {
      alertas.push({ modulo: "riscos", nivel: "warning", projetoId: r.projetoId, titulo: cod(r.projetoId) + r.codigo + " com revisão vencida", detalhe: r.titulo });
    });
    claimsDe(projetoId).filter(function (c) { return c.aberto && c.foraDoPrazo; }).forEach(function (c) {
      var ct = porCampo(M.contratos, "numero", c.contrato) || {};
      alertas.push({ modulo: "financeiro", nivel: "warning", projetoId: ct.projetoId, titulo: cod(ct.projetoId) + c.codigo + " notificado fora do prazo contratual", detalhe: c.contrato + " · " + c.diasParaNotificar + " dias entre evento e notificação",
        destino: { tela: "contratos", params: { busca: c.codigo } } });
    });
    listarMudancasDe({ projetoId: projetoId }).forEach(function (s) {
      if (s.ratificacaoVencida) alertas.push({ modulo: "governanca", nivel: "danger", projetoId: s.projetoId, titulo: cod(s.projetoId) + s.codigo + " emergencial sem ratificação do Comitê", detalhe: "Prazo de ratificação vencido em " + dataBr(s.ratificacaoAte),
        destino: { tela: "mudanca", params: { codigo: s.codigo } } });
      else if (s.analiseVencida) alertas.push({ modulo: "governanca", nivel: "warning", projetoId: s.projetoId, titulo: cod(s.projetoId) + s.codigo + " com análise de impacto vencida", detalhe: s.titulo,
        destino: { tela: "mudanca", params: { codigo: s.codigo } } });
    });
    listarRncsDe({ projetoId: projetoId }).filter(function (r) { return r.vencida || (r.ativa && r.severidade === "Crítica"); }).forEach(function (r) {
      alertas.push({ modulo: "qualidade", nivel: r.severidade === "Crítica" ? "danger" : "warning", projetoId: r.projetoId,
        titulo: cod(r.projetoId) + r.codigo + (r.vencida ? " com prazo de tratamento vencido" : " crítica em aberto"), detalhe: r.descricao,
        destino: { tela: "rnc", params: { busca: r.codigo } } });
    });
    if (hse.hipoMes) alertas.push({ modulo: "hse", nivel: "danger", titulo: hse.hipoMes + (hse.hipoMes === 1 ? " ocorrência" : " ocorrências") + " de alto potencial no mês", detalhe: "Relatório final em até " + P().hse.prazos.relatorioFinalDias + " dias" });

    return responder({
      referencia: REF, projeto: proj, portfolio: projetoId == null, carteira: projetoId == null ? resumoCarteiraDe() : null,
      modulos: {
        "central-acoes": acoes,
        planejamento: { fisico: fis, punch: pl },
        financeiro: { custo: custo, contratos: ctr },
        suprimentos: sup, riscos: rsk, qualidade: qual, hse: hse, governanca: sm
      },
      alertas: alertas
    });
  }

  /* ======================================================================
     02 Planejamento > Relato do período
     Um registro por projeto, tipo (Semanal ou Mensal) e período (semana ISO "2026-S38" ou mês
     "2026-08"): o semanal e o mensal são registros distintos. Campos: atividades do período,
     atividades do próximo período e pontos de atenção, cada ponto com o risco atrelado (ameaça
     ou oportunidade). Esse risco é a leitura do planejamento sobre o ponto de atenção e NÃO tem
     vínculo com o registro do 05 Gestão de Riscos. Alimenta a página 2 do Planejamento no
     relatório gerencial (Início).
     ====================================================================== */
  var TIPOS_RELATO = ["Semanal", "Mensal"];
  var NATUREZAS_RELATO = ["Ameaça", "Oportunidade"];
  var MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
  var LIMITES_RELATO = { itens: 20, textoItem: 300, pontos: 12, textoPonto: 400, minimoPonto: 10 };

  function projetoDe(projetoId) { return porId(M.projetos)[projetoId] || null; }
  /* Dados do período: limites, rótulos, corte (fim do período limitado à data de referência) */
  function infoPeriodo(tipo, periodo) {
    var lim = R.limitesPeriodo(tipo, periodo);
    if (!lim) return null;
    var rotulo, curto;
    if (tipo === "Semanal") {
      var n = Number(periodo.split("-S")[1]);
      rotulo = "Semana " + n + " · " + dataBr(lim.inicio).slice(0, 5) + " a " + dataBr(lim.fim);
      curto = "S" + (n < 10 ? "0" : "") + n;
    } else {
      var p = periodo.split("-");
      rotulo = MESES_PT[Number(p[1]) - 1] + " de " + p[0];
      curto = MESES_PT[Number(p[1]) - 1].slice(0, 3).toLowerCase() + "/" + p[0].slice(2);
    }
    return { tipo: tipo, periodo: periodo, inicio: lim.inicio, fim: lim.fim, corte: lim.fim < REF ? lim.fim : REF,
      emAndamento: lim.inicio <= REF && lim.fim >= REF, futuro: lim.inicio > REF, rotulo: rotulo, rotuloCurto: curto };
  }
  /* Primeiro e último período possíveis: do início do projeto ao período da data de referência */
  function faixaPeriodos(projetoId, tipo) {
    var pj = projetoOuCarteira(projetoId) || {};
    return { primeiro: R.periodoDaData(tipo, pj.inicio || REF), ultimo: R.periodoDaData(tipo, REF) };
  }
  function relatoCalculado(r) {
    var x = copia(r);
    x.info = infoPeriodo(r.tipo, r.periodo);
    x.proximo = infoPeriodo(r.tipo, R.somarPeriodos(r.tipo, r.periodo, 1));
    x.pontos = x.pontos || [];
    x.ameacas = x.pontos.filter(function (p) { return p.natureza === "Ameaça"; }).length;
    x.oportunidades = x.pontos.filter(function (p) { return p.natureza === "Oportunidade"; }).length;
    return x;
  }
  function relatosDe(projetoId) { return doProjeto(M.relatos, projetoId); }
  function relatoDoPeriodo(projetoId, tipo, periodo) {
    return relatosDe(projetoId).filter(function (r) { return r.tipo === tipo && r.periodo === periodo; })[0] || null;
  }
  /* TODO: API GET /projetos/{id}/relatos?tipo */
  function listarRelatos(projetoId, filtro) {
    var f = filtro || {};
    return responder(relatosDe(projetoId).filter(function (r) { return !f.tipo || r.tipo === f.tipo; }).map(relatoCalculado)
      .sort(function (a, b) { return a.info.inicio < b.info.inicio ? 1 : a.info.inicio > b.info.inicio ? -1 : (a.tipo === "Mensal" ? -1 : 1); }));
  }
  /* TODO: API GET /projetos/{id}/relatos/{tipo}/{periodo} */
  function obterRelato(projetoId, tipo, periodo) {
    var r = relatoDoPeriodo(projetoId, tipo, periodo);
    return responder(r ? relatoCalculado(r) : null);
  }
  /* Períodos do tipo, do mais recente ao mais antigo, com a situação do relato.
     TODO: API GET /projetos/{id}/relatos/periodos?tipo */
  function periodosRelato(projetoId, tipo) {
    var fx = faixaPeriodos(projetoId, tipo);
    return responder(R.listaPeriodos(tipo, fx.primeiro, fx.ultimo).reverse().map(function (p) {
      var i = infoPeriodo(tipo, p), r = relatoDoPeriodo(projetoId, tipo, p);
      i.relatoId = r ? r.id : null;
      return i;
    }));
  }
  /* Resumo para os KPIs da tela: último período fechado de cada tipo e o relato mais recente */
  function resumoRelatos(projetoId) {
    var ant = {};
    TIPOS_RELATO.forEach(function (t) {
      var p = R.somarPeriodos(t, R.periodoDaData(t, REF), -1), r = relatoDoPeriodo(projetoId, t, p);
      ant[t] = { info: infoPeriodo(t, p), registrado: !!r };
    });
    var lista = relatosDe(projetoId).map(relatoCalculado);
    var semanais = lista.filter(function (r) { return r.tipo === "Semanal"; }).sort(function (a, b) { return a.periodo < b.periodo ? 1 : -1; });
    return responder({ semanaAnterior: ant.Semanal, mesAnterior: ant.Mensal, ultimoSemanal: semanais[0] || null,
      semanais: semanais.length, mensais: lista.length - semanais.length, total: lista.length });
  }

  function limparLista(lista) {
    return (lista || []).map(function (t) { return String(t == null ? "" : t).replace(/\s+/g, " ").trim(); }).filter(Boolean);
  }
  /* Grava (novo ou edição). Tipo e período não mudam depois de criado. TODO: API PUT /projetos/{id}/relatos/{tipo}/{periodo} */
  function salvarRelato(projetoId, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar o relato do período.");
    var e = [];
    var existente = d.id != null ? (M.relatos || []).filter(function (r) { return String(r.id) === String(d.id); })[0] : null;
    var tipo = existente ? existente.tipo : d.tipo, periodo = existente ? existente.periodo : d.periodo;
    if (TIPOS_RELATO.indexOf(tipo) < 0) e.push({ campo: "tipo", msg: "Escolha o tipo do relato (semanal ou mensal)." });
    else if (!R.periodoValido(tipo, periodo)) e.push({ campo: "periodo", msg: "Escolha o período do relato." });
    else {
      var fx = faixaPeriodos(projetoId, tipo);
      if (periodo < fx.primeiro) e.push({ campo: "periodo", msg: "O período é anterior ao início do projeto." });
      else if (periodo > fx.ultimo) e.push({ campo: "periodo", msg: "O período ainda não começou; registre a partir do período corrente." });
      else if (!existente && relatoDoPeriodo(projetoId, tipo, periodo)) e.push({ campo: "periodo", msg: "Já existe relato " + tipo.toLowerCase() + " para este período; edite o registro existente." });
    }
    var atv = limparLista(d.atividadesPeriodo), prox = limparLista(d.atividadesProximo);
    [["atividadesPeriodo", atv, "Atividades do período"], ["atividadesProximo", prox, "Atividades do próximo período"]].forEach(function (c) {
      if (!c[1].length) e.push({ campo: c[0], msg: "Informe ao menos uma atividade (uma por linha)." });
      else if (c[1].length > LIMITES_RELATO.itens) e.push({ campo: c[0], msg: c[2] + ": no máximo " + LIMITES_RELATO.itens + " linhas." });
      else if (c[1].some(function (t) { return t.length > LIMITES_RELATO.textoItem; })) e.push({ campo: c[0], msg: "Cada linha pode ter até " + LIMITES_RELATO.textoItem + " caracteres." });
    });
    var pontos = (d.pontos || []).map(function (p) {
      return { descricao: String(p.descricao || "").trim(), natureza: p.natureza || "", risco: String(p.risco || "").trim() };
    }).filter(function (p) { return p.descricao || p.risco || p.natureza; });
    if (pontos.length > LIMITES_RELATO.pontos) e.push({ campo: "pontos", msg: "No máximo " + LIMITES_RELATO.pontos + " pontos de atenção por relato." });
    pontos.forEach(function (p, k) {
      var id = "pontos." + k + ".";
      if (p.descricao.length < LIMITES_RELATO.minimoPonto) e.push({ campo: id + "descricao", msg: "Descreva o ponto de atenção (mínimo de " + LIMITES_RELATO.minimoPonto + " caracteres)." });
      else if (p.descricao.length > LIMITES_RELATO.textoPonto) e.push({ campo: id + "descricao", msg: "Até " + LIMITES_RELATO.textoPonto + " caracteres." });
      if (NATUREZAS_RELATO.indexOf(p.natureza) < 0) e.push({ campo: id + "natureza", msg: "Escolha ameaça ou oportunidade." });
      if (p.risco.length < LIMITES_RELATO.minimoPonto) e.push({ campo: id + "risco", msg: "Descreva o risco atrelado (mínimo de " + LIMITES_RELATO.minimoPonto + " caracteres)." });
      else if (p.risco.length > LIMITES_RELATO.textoPonto) e.push({ campo: id + "risco", msg: "Até " + LIMITES_RELATO.textoPonto + " caracteres." });
    });
    if (e.length) return rejeitar(e);
    var reg = existente || { id: proximoId("relatos"), projetoId: projetoId, tipo: tipo, periodo: periodo, criadoPorId: sessaoPessoa(), criadoEm: agoraIso() };
    reg.atividadesPeriodo = atv; reg.atividadesProximo = prox; reg.pontos = pontos;
    reg.atualizadoPorId = sessaoPessoa(); reg.atualizadoEm = agoraIso();
    if (!existente) colecao("relatos").push(reg);
    persistir("relatos");
    return responder(relatoCalculado(reg));
  }
  /* Exclusão (Gestor). TODO: API DELETE /projetos/{id}/relatos/{id} */
  function excluirRelato(id) {
    if (!temPapel("Gestor")) return rejeitar("A exclusão do relato exige papel Gestor.");
    var lista = colecao("relatos"), i = lista.findIndex(function (r) { return String(r.id) === String(id); });
    if (i < 0) return rejeitar("Relato não encontrado.");
    var r = lista.splice(i, 1)[0];
    persistir("relatos");
    return responder({ id: r.id, tipo: r.tipo, periodo: r.periodo });
  }

  /* ======================================================================
     Início > Relatório gerencial (semanal ou mensal)
     Consolida Planejamento (curva e KPIs + relato), Financeiro, Suprimentos e Riscos para o
     período escolhido. Regras de corte (documentadas no README):
     * corte = fim do período, limitado à data de referência (período em andamento sai parcial);
     * Planejamento: a Curva S é mensal. No mensal usa o ponto do mês (igual às telas); no semanal,
       interpola linearmente dentro do mês até o fim da semana (o real do mês de corte vale na data
       de referência);
     * Financeiro: custo é apurado por mês. No mensal usa o mês; no semanal, o último mês fechado
       até o fim da semana;
     * Suprimentos: por datas dos eventos (adjudicação, emissão e entrega) até o corte; pedidos
       críticos na data de referência;
     * Riscos: o registro não guarda fotografia por data; KPIs, matriz e principais riscos saem na
       data de referência; identificados no período e evolução mensal saem do histórico.
     ====================================================================== */
  function diasNoMesRg(mes) { return Number(R.ultimoDiaMes(mes).slice(8, 10)); }
  /* Acumulado de uma série mensal (valor no fim de cada mês) numa data, com interpolação linear
     no mês. ancoraRef: no mês da referência o último valor vale na data de referência. */
  function acumuladoNaDataRg(meses, serie, iso, ancoraRef) {
    var m = iso.slice(0, 7), i = meses.indexOf(m);
    if (i < 0) {
      if (iso < meses[0] + "-01") return 0;
      for (var k = serie.length - 1; k >= 0; k--) if (serie[k] != null) return serie[k];
      return null;
    }
    if (serie[i] == null) return null;
    var ant = i > 0 ? serie[i - 1] : 0;
    if (ant == null) return null;
    var dia = Number(iso.slice(8, 10)), total = diasNoMesRg(m);
    if (ancoraRef && m === mesDe(REF)) { total = Number(REF.slice(8, 10)); dia = Math.min(dia, total); }
    return ant + (serie[i] - ant) * dia / total;
  }
  function posicaoFisicaRg(c, tipo, periodo) {
    if (tipo === "Mensal") {
      var i = c.meses.indexOf(periodo), prevI = i - 1;
      var prev = i >= 0 ? c.baseline[i] : acumuladoNaDataRg(c.meses, c.baseline, R.ultimoDiaMes(periodo), false);
      var real = i >= 0 ? c.real[i] : null;
      var prevAnt = prevI >= 0 ? c.baseline[prevI] : 0, realAnt = prevI >= 0 ? c.real[prevI] : 0;
      return { previsto: prev, real: real, previstoAnterior: prevAnt, realAnterior: realAnt };
    }
    var lim = R.limitesPeriodo(tipo, periodo);
    var corte = lim.fim < REF ? lim.fim : REF, antes = R.somarDias(lim.inicio, -1);
    return {
      previsto: acumuladoNaDataRg(c.meses, c.baseline, corte, false), real: acumuladoNaDataRg(c.meses, c.real, corte, true),
      previstoAnterior: acumuladoNaDataRg(c.meses, c.baseline, antes, false), realAnterior: acumuladoNaDataRg(c.meses, c.real, antes, true)
    };
  }
  function planejamentoRg(projetoId, tipo, periodo, info) {
    var c = curvaFisicaDe(projetoId);
    if (!c) return null;
    var pos = posicaoFisicaRg(c, tipo, periodo);
    var r1 = function (v) { return v == null ? null : arred(v, 1); };
    /* Série de barras: 8 semanas ou 6 meses até o período (avanço no período, em p.p.) */
    var n = tipo === "Semanal" ? 8 : 6, serie = { rotulos: [], previsto: [], real: [] }, primeiro = faixaPeriodos(projetoId, tipo).primeiro;
    for (var k = n - 1; k >= 0; k--) {
      var p = R.somarPeriodos(tipo, periodo, -k);
      if (p < primeiro) continue;
      var ip = infoPeriodo(tipo, p), ps = posicaoFisicaRg(c, tipo, p);
      serie.rotulos.push(ip.rotuloCurto);
      serie.previsto.push(ps.previsto == null ? null : r1(ps.previsto - (ps.previstoAnterior || 0)));
      serie.real.push(ip.futuro || ps.real == null ? null : r1(ps.real - (ps.realAnterior || 0)));
    }
    /* Curva S mensal com o real até o mês do corte (o ponto do mês do corte recebe o real do corte) */
    var mesCorte = info.corte.slice(0, 7), atual = mesCorte === c.corte;
    var real = c.meses.map(function (m, i) { return m < mesCorte ? c.real[i] : m === mesCorte ? r1(pos.real) : null; });
    var tend = c.meses.map(function (m, i) { return !atual ? null : m === mesCorte ? r1(pos.real) : m > mesCorte ? c.tendencia[i] : null; });
    var ind = indicesFisicos(projetoId);
    var areas = avancoAreasDe(projetoId).map(function (a) { return { area: a.area, projetoId: a.projetoId, peso: a.peso, previsto: a.previsto, real: a.real, desvio: arred(a.real - a.previsto, 1) }; });
    return {
      previsto: r1(pos.previsto), real: r1(pos.real), desvioPP: pos.real == null ? null : r1(pos.real - pos.previsto),
      spi: pos.real == null || !pos.previsto ? null : arred(pos.real / pos.previsto, 2),
      previstoPeriodo: r1(pos.previsto - (pos.previstoAnterior || 0)), realPeriodo: pos.real == null ? null : r1(pos.real - (pos.realAnterior || 0)),
      spiAnterior: pos.realAnterior && pos.previstoAnterior ? arred(pos.realAnterior / pos.previstoAnterior, 2) : null,
      interpolado: tipo === "Semanal",
      terminoBaseline: ind ? ind.terminoBaseline : null, terminoTendencia: ind ? ind.terminoTendencia : null,
      curva: { meses: c.meses, baseline: c.baseline, real: real, tendencia: tend, mesCorte: mesCorte },
      serie: serie, areas: areas, areasNaReferencia: info.corte < REF,
      relato: projetoId == null ? null : (function () { var r = relatoDoPeriodo(projetoId, tipo, periodo); return r ? relatoCalculado(r) : null; })(),
      /* Portfólio: relato de cada projeto no período (pontos de atenção consolidados na folha) */
      relatosProjetos: projetoId != null ? null : projetosCarteira().map(function (p) {
        var r = relatoDoPeriodo(p.id, tipo, periodo);
        return { projetoId: p.id, projetoCodigo: p.codigo, projetoNome: p.nome, relato: r ? relatoCalculado(r) : null };
      })
    };
  }
  /* Mês de competência do financeiro: no mensal, o próprio mês; no semanal, o último mês fechado
     até o fim da semana. Limitado ao corte da curva financeira. */
  function mesFinanceiroRg(fin, tipo, periodo) {
    var lim = R.limitesPeriodo(tipo, periodo);
    var mes = tipo === "Mensal" ? periodo : (R.ultimoDiaMes(lim.fim.slice(0, 7)) <= lim.fim ? lim.fim.slice(0, 7) : R.somarPeriodos("Mensal", lim.fim.slice(0, 7), -1));
    if (mes > fin.corte) mes = fin.corte;
    return mes;
  }
  /* Linha de tendência da Curva S financeira no relatório: parte do realizado no mês do relatório e chega à
     EAC por desempenho (EAC = BAC ÷ CPI, isto é, AC + (BAC - EV) ÷ CPI), distribuindo o custo restante pelo perfil
     do planejado. Calculada no próprio mês, sem usar dados posteriores ao período (vale para períodos passados). */
  function tendenciaCustoRg(fin, j, bac, va) {
    if (!va || !va.cpi || j < 0 || fin.realizado[j] == null) return null;
    var ac = fin.realizado[j], eac = Math.round(bac / divide(va.ev, va.ac)), pvj = fin.planejado[j] || 0, resta = bac - pvj;
    return fin.meses.map(function (m, i) {
      if (i < j) return null;
      if (i === j) return ac;
      var fr = resta > 0 ? Math.min(1, Math.max(0, ((fin.planejado[i] || 0) - pvj) / resta)) : 1;
      return Math.round(ac + fr * (eac - ac));
    });
  }
  function financeiroRg(projetoId, tipo, periodo) {
    var fis = curvaFisicaDe(projetoId), fin = curvaFinanceiraDe(projetoId);
    if (!fis || !fin) return null;
    var mapa = mapaControleDe(projetoId), bac = mapa.total.atual;
    var mes = mesFinanceiroRg(fin, tipo, periodo), j = fin.meses.indexOf(mes);
    if (j < 0) return { semFechamento: true, mesAnterior: mes, bac: bac };
    var va = vaNoMes(projetoId, fis, fin, bac, mes);
    var anterior = j > 0 ? vaNoMes(projetoId, fis, fin, bac, fin.meses[j - 1]) : null;
    var ind = indicesCustoDe(projetoId);
    var realizado = j >= 0 ? fin.realizado[j] : null, realAnt = j > 0 ? fin.realizado[j - 1] : 0;
    var planejado = j >= 0 ? fin.planejado[j] : null, planAnt = j > 0 ? fin.planejado[j - 1] : 0;
    var p = mes.split("-");
    return {
      mes: mes, mesRotulo: MESES_PT[Number(p[1]) - 1] + " de " + p[0], mesCorrente: mes === fin.corte, fechadoNoSemanal: tipo === "Semanal",
      bac: bac, planejado: planejado, realizado: realizado, comprometido: j >= 0 ? fin.comprometido[j] : null,
      realizadoMes: realizado == null ? null : realizado - (realAnt || 0), planejadoMes: planejado == null ? null : planejado - (planAnt || 0),
      valorAgregado: va, anterior: anterior,
      projecaoTermino: mapa.total.projecao, vac: bac - mapa.total.projecao, desvioPct: mapa.total.desvioPct, faixa: mapa.total.faixa,
      eacPorCpi: va && va.cpi ? Math.round(bac / divide(va.ev, va.ac)) : null,
      contingencia: ind ? ind.contingencia : null, contingenciaConsumida: ind ? ind.contingenciaConsumida : null, contingenciaPct: ind ? ind.contingenciaPct : null,
      curva: { meses: fin.meses, planejado: fin.planejado,
        realizado: fin.meses.map(function (m, i) { return m <= mes ? fin.realizado[i] : null; }),
        comprometido: fin.meses.map(function (m, i) { return m <= mes ? fin.comprometido[i] : null; }),
        projecao: fin.projecao, projecaoAtual: mes !== fin.corte, mes: mes, tendencia: tendenciaCustoRg(fin, j, bac, va), eacTendencia: va && va.cpi ? Math.round(bac / divide(va.ev, va.ac)) : null },
      historico: fin.meses.slice(Math.max(0, j - 5), j + 1).map(function (m) { return vaNoMes(projetoId, fis, fin, bac, m); }).filter(Boolean),
      pacotes: mapa.itens.filter(function (x) { return x.nivel === 1; }).map(function (x) {
        return { codigo: x.codigo, descricao: x.descricao, projetoId: x.projetoId || null, projetoCodigo: x.projetoCodigo || "", projetoNome: x.projetoNome || "", atual: x.atual, comprometido: x.comprometido, realizado: x.realizado, projecao: x.projecao,
          desvio: x.desvio, desvioPct: x.desvioPct, faixa: x.faixa };
      }),
      total: { atual: mapa.total.atual, comprometido: mapa.total.comprometido, realizado: mapa.total.realizado, projecao: mapa.total.projecao,
        desvio: mapa.total.desvio, desvioPct: mapa.total.desvioPct, faixa: mapa.total.faixa }
    };
  }
  function suprimentosRg(projetoId, tipo, periodo, info, proximo) {
    var ini = info.inicio, corte = info.corte;
    var pacs = doProjeto(M.pacotes, projetoId), peds = pedidosDe(projetoId);
    var noPeriodo = function (d) { return !!d && d >= ini && d <= corte; };
    var planejados = pacs.filter(function (p) { return p.plano.adjudicacao && p.plano.adjudicacao <= corte; });
    var adjudicados = pacs.filter(function (p) { return p.adjudicadoCentavos != null && p.real.adjudicacao && p.real.adjudicacao <= corte; });
    var noPrazo = planejados.filter(function (p) { return p.real.adjudicacao && p.real.adjudicacao <= corte; });
    var est = soma(adjudicados, "estimativaCentavos"), adj = soma(adjudicados, "adjudicadoCentavos");
    var entregues = peds.filter(function (p) { return p.entrega && p.entrega <= corte; });
    var noPrazoEnt = entregues.filter(function (p) { return p.entrega <= p.dataContratual; });
    var pacPorId = porId(pacs);
    var codProj = function (pid) { return (porId(M.projetos)[pid] || {}).codigo || ""; };
    function evento(tipoEv, data, codigo, descricao, extra) { return Object.assign({ tipo: tipoEv, data: data, codigo: codigo, descricao: descricao }, extra || {}); }
    /* Realizados no período: adjudicações, pedidos emitidos e marcos dos pedidos (documentos a entrega) */
    var eventos = [];
    pacs.forEach(function (p) { if (noPeriodo(p.real.adjudicacao)) eventos.push(evento("Adjudicação", p.real.adjudicacao, p.codigo, p.escopo, { valor: p.adjudicadoCentavos, projetoCodigo: codProj(p.projetoId) })); });
    peds.forEach(function (p) {
      if (noPeriodo(p.emissao)) eventos.push(evento("Pedido emitido", p.emissao, p.numero, p.descricao, { valor: p.valorCentavos, projetoCodigo: p.projetoCodigo }));
      (p.marcos || []).forEach(function (m) {
        if (noPeriodo(m.realizada)) eventos.push(evento(m.nome, m.realizada, p.numero, p.descricao, { desvioDias: R.diasEntre(m.lb, m.realizada), projetoCodigo: p.projetoCodigo }));
      });
    });
    eventos.sort(function (a, b) { return a.data < b.data ? -1 : a.data > b.data ? 1 : a.codigo < b.codigo ? -1 : 1; });
    /* Previstos no horizonte (semanal: 4 semanas seguintes; mensal: mês seguinte): adjudicações e entregas */
    var hIni = R.somarDias(info.fim, 1), hFim = tipo === "Semanal" ? R.somarDias(info.fim, 28) : (proximo ? proximo.fim : hIni);
    var noHorizonte = function (d) { return !!d && d >= hIni && d <= hFim; };
    var previstos = [];
    pacs.forEach(function (p) {
      var d = p.adjudicadoCentavos == null ? (p.previsao && p.previsao.adjudicacao) || p.plano.adjudicacao : null;
      if (noHorizonte(d)) previstos.push(evento("Adjudicação", d, p.codigo, p.escopo, { desvioDias: R.diasEntre(p.plano.adjudicacao, d), projetoCodigo: codProj(p.projetoId) }));
    });
    peds.forEach(function (p) {
      if (!p.entregue && noHorizonte(p.previsao)) previstos.push(evento("Entrega", p.previsao, p.numero, p.descricao, { desvioDias: R.diasEntre(p.dataContratual, p.previsao), folgaDias: p.folgaDias, projetoCodigo: p.projetoCodigo }));
    });
    previstos.sort(function (a, b) { return a.data < b.data ? -1 : 1; });
    var ind = indicadoresSuprimentosDe(projetoId), cc = ind.curvaContratacao, mesCorte = corte.slice(0, 7);
    return {
      pacotes: pacs.length, planejadosAteCorte: planejados.length, adjudicadosAteCorte: adjudicados.length,
      aderenciaPct: planejados.length ? arred(noPrazo.length / planejados.length * 100, 1) : null,
      adjudicadoCentavos: adj, savingCentavos: est - adj, savingPct: est ? arred((est - adj) / est * 100, 1) : null,
      entregas: entregues.length, entregasNoPrazo: noPrazoEnt.length, otdPct: entregues.length ? arred(noPrazoEnt.length / entregues.length * 100, 1) : null,
      pedidos: peds.filter(function (p) { return p.emissao <= corte; }).length,
      criticos: peds.filter(function (p) { return p.critico; }).map(function (p) {
        return { numero: p.numero, projetoId: p.projetoId, projetoCodigo: p.projetoCodigo, descricao: p.descricao, fornecedor: p.fornecedor, ros: p.ros, previsao: p.previsao, folgaDias: p.folgaDias, lli: !!p.lli,
          pacote: pacPorId[p.pacoteId] ? pacPorId[p.pacoteId].codigo : "" };
      }).sort(function (a, b) { return a.folgaDias - b.folgaDias; }),
      emAtencao: peds.filter(function (p) { return p.faixaFolga === "atencao"; }).length,
      eventos: eventos, previstos: previstos, horizonte: { inicio: hIni, fim: hFim, semanas: tipo === "Semanal" ? 4 : null },
      curva: { meses: cc.meses, planejado: cc.planejado, realizado: cc.meses.map(function (m, i) { return m <= mesCorte ? cc.realizado[i] : null; }) }
    };
  }
  function riscosRg(projetoId, info) {
    var lista = riscosDe(projetoId);
    var ativos = lista.filter(function (r) { return r.ativo; });
    var resumo = resumoRiscosDe(projetoId);
    var celulas = {};
    ativos.filter(function (r) { return r.avaliado; }).forEach(function (r) {
      var av = r.residual || r.inerente, k = av.p + "-" + av.i;
      celulas[k] = celulas[k] || { ameacas: 0, oportunidades: 0 };
      celulas[k][r.natureza === "Oportunidade" ? "oportunidades" : "ameacas"]++;
    });
    var matriz = [];
    for (var p = 5; p >= 1; p--) for (var i = 1; i <= 5; i++) {
      var c = celulas[p + "-" + i] || { ameacas: 0, oportunidades: 0 };
      matriz.push({ p: p, i: i, score: p * i, sev: R.severidade(p * i, P().riscos, false), ameacas: c.ameacas, oportunidades: c.oportunidades });
    }
    var principais = ativos.filter(function (r) { return r.avaliado; }).sort(function (a, b) { return (b.scoreAtual || 0) - (a.scoreAtual || 0) || (b.vmeCentavos || 0) - (a.vmeCentavos || 0); }).slice(0, 8)
      .map(function (r) {
        return { codigo: r.codigo, projetoId: r.projetoId, projetoCodigo: r.projetoCodigo, titulo: r.titulo, natureza: r.natureza, scoreAtual: r.scoreAtual, sevAtual: r.sevAtual, situacao: r.situacao,
          estrategia: r.estrategia || "", donoId: r.donoId, proximaRevisao: r.proximaRevisao || null, revisaoVencida: r.revisaoVencida, vmeCentavos: r.vmeCentavos };
      });
    var mesRef = mesDe(REF), meses = [];
    for (var k = 5; k >= 0; k--) meses.push(R.somarPeriodos("Mensal", mesRef, -k));
    var ameacasAval = ativos.filter(function (r) { return r.natureza === "Ameaça" && r.avaliado; });
    return {
      resumo: resumo, ameacas: ativos.filter(function (r) { return r.natureza === "Ameaça"; }).length, oportunidades: ativos.filter(function (r) { return r.natureza === "Oportunidade"; }).length,
      identificadosNoPeriodo: lista.filter(function (r) { return r.identificadoEm && r.identificadoEm >= info.inicio && r.identificadoEm <= info.corte; }).length,
      encerradosNoPeriodo: lista.filter(function (r) { return r.encerramento && r.encerramento.data && r.encerramento.data >= info.inicio && r.encerramento.data <= info.corte; }).length,
      matriz: matriz, legenda: legendaFaixas(), principais: principais,
      evolucao: meses.map(function (m) {
        return { mes: m, score: m === mesRef ? soma(ameacasAval, "scoreAtual") : soma((M.riscosEvolucao || []).filter(function (e) { return e.mes === m && (projetoId == null || e.projetoId === projetoId); }), "scoreResidual") };
      })
    };
  }
  var SECOES_RG = ["planejamento", "financeiro", "suprimentos", "riscos", "qualidade", "hse"];
  /* opcoes: { tipo: "Semanal" | "Mensal", periodo, secoes: [...] }. TODO: API GET /projetos/{id}/relatorio-gerencial?tipo&periodo&secoes */
  function relatorioGerencial(projetoId, opcoes) {
    var o = opcoes || {};
    var tipo = o.tipo, periodo = o.periodo;
    if (TIPOS_RELATO.indexOf(tipo) < 0 || !R.periodoValido(tipo, periodo)) return rejeitar("Escolha o tipo e o período do relatório.");
    var fx = faixaPeriodos(projetoId, tipo);
    if (periodo < fx.primeiro || periodo > fx.ultimo) return rejeitar("Período fora do intervalo do projeto (do início até o período corrente).");
    var secoes = (o.secoes && o.secoes.length ? o.secoes : SECOES_RG).filter(function (s) { return SECOES_RG.indexOf(s) >= 0; });
    if (!secoes.length) return rejeitar("Escolha ao menos uma seção.");
    var info = infoPeriodo(tipo, periodo), proximo = infoPeriodo(tipo, R.somarPeriodos(tipo, periodo, 1));
    var r = { projeto: copia(projetoOuCarteira(projetoId)), portfolio: projetoId == null, referencia: REF, emitidoPor: sessaoAtual().nome, periodo: info, proximo: proximo, secoes: secoes };
    if (projetoId == null) r.carteira = resumoCarteiraDe(info);
    if (secoes.indexOf("planejamento") >= 0) r.planejamento = planejamentoRg(projetoId, tipo, periodo, info);
    if (secoes.indexOf("financeiro") >= 0) r.financeiro = financeiroRg(projetoId, tipo, periodo);
    if (secoes.indexOf("suprimentos") >= 0) r.suprimentos = suprimentosRg(projetoId, tipo, periodo, info, proximo);
    if (secoes.indexOf("riscos") >= 0) r.riscos = riscosRg(projetoId, info);
    if (secoes.indexOf("qualidade") >= 0) r.qualidade = qualidadeRg(projetoId, tipo, periodo, info);
    if (secoes.indexOf("hse") >= 0) r.hse = hseRg(projetoId, tipo, periodo, info);
    if (r.planejamento) r.planejamento.produtividade = produtividadeRg(projetoId, info);
    /* Análise do período de cada seção, com os desvios negativos detectados e os comentários */
    r.analises = {};
    secoes.forEach(function (m) { r.analises[m] = analiseMontada(projetoId, m, tipo, periodo, r[m], r); });
    return responder(r);
  }

  /* ======================================================================
     Análise do período (comentário executivo e analítico por módulo)
     Um registro por projeto, módulo, tipo (Semanal ou Mensal) e período, inserido e editado em
     modal no próprio módulo (02, 03, 04, 05 e 07). Texto executivo: panorama, desempenho dos
     períodos anteriores, causas e tendência. Nos módulos 02, 03 e 04, todo desvio negativo
     detectado no período exige comentário próprio (análise de variação: PMBOK, relatório de
     desempenho). Os desvios são calculados aqui com os mesmos dados do relatório gerencial.
     ====================================================================== */
  var MODULOS_ANALISE = { planejamento: "02 Planejamento", financeiro: "03 Gestão Financeira", suprimentos: "04 Suprimentos", riscos: "05 Gestão de Riscos", qualidade: "06 Gestão da Qualidade", hse: "07 HSE" };
  var DESVIO_OBRIGATORIO = { planejamento: true, financeiro: true, suprimentos: true, riscos: false, qualidade: false, hse: false };
  var LIMITES_ANALISE = { minimo: 150, maximo: 2500, minimoDesvio: 20, maximoDesvio: 600 };

  /* Produtividade no corte: janela de N semanas terminando na semana do corte */
  function produtividadeRg(projetoId, info) {
    var semana = R.periodoDaData("Semanal", info.corte);
    var k = kpisProdutividadeDe(projetoId, semana), g = k.geral, q = g.quantidades, par = k.parametros;
    return {
      semana: semana, janela: k.janela, spi: q.spi, pctPrev: q.pctPrev, pctReal: q.pctReal, pf: q.pfJan, aderencia: q.aderenciaJan,
      cp: g.capacidade.cp, utilizacao: g.capacidade.utilizacao, pctTrabalhando: g.amostragem.pctTrabalhando,
      hhoraParalisada: g.paralisacoes.hhora, pctHhoraParalisada: g.pctHhoraParalisada, faixas: g.faixas,
      metas: { aderencia: par.aderenciaFaixas[1], pf: par.pfFaixas[0], trabalhando: par.metaTrabalhandoPct, utilizacao: par.metaUtilizacaoPct },
      empresasEmAlerta: k.porEmpresa.filter(function (b) { return b.alertas && b.alertas.length; }).map(function (b) { return nomeEmpresa(b.empresaId); })
    };
  }
  /* HSE: base mensal (HHT e registro mensal). Mensal: o mês; semanal: o mês que contém o corte, com as
     ocorrências da própria semana à parte. Acumulado do primeiro mês com HHT até o mês. */
  /* 06 Qualidade no período: abertas e encerradas no período, posição no corte (em aberto e custo),
     inspeções e auditorias do período; pauta e auditorias atrasadas na data de referência. */
  function qualidadeRg(projetoId, tipo, periodo, info) {
    var ini = info.inicio, corte = info.corte, q = parQ();
    var rncs = doProjeto(M.rncs, projetoId).map(rncCalculada).filter(function (r) { return r.data <= corte; });
    var noPeriodo = function (d) { return d && d >= ini && d <= corte; };
    var emAberto = rncs.filter(function (r) { return !r.encerramento || r.encerramento > corte; });
    var insp = doProjeto(M.inspecoesQualidade, projetoId).filter(function (i) { return noPeriodo(i.data); });
    var aud = doProjeto(M.auditorias, projetoId).map(auditoriaCalculada);
    var audPer = aud.filter(function (a) { return a.situacao === "Realizada" && noPeriodo(a.realizadaEm || a.data); });
    var ver = soma(audPer, "itensVerificados"), conf = soma(audPer, "itensConformes");
    var painel = painelQualidadeDe(projetoId);
    return {
      abertasPeriodo: rncs.filter(function (r) { return noPeriodo(r.data); }).length,
      encerradasPeriodo: rncs.filter(function (r) { return r.situacao === "Encerrada" && noPeriodo(r.encerramento); }).length,
      emAbertoCorte: emAberto.filter(function (r) { return r.situacao !== "Cancelada"; }).length,
      criticasCorte: emAberto.filter(function (r) { return r.situacao !== "Cancelada" && r.severidade === "Crítica"; }).length,
      vencidas: painel.pauta.filter(function (r) { return r.vencida; }),
      custoAcumuladoCentavos: soma(rncs.filter(function (r) { return r.situacao !== "Cancelada"; }), "custoNaoQualidadeCentavos"),
      custoPeriodoCentavos: soma(rncs.filter(function (r) { return noPeriodo(r.data) && r.situacao !== "Cancelada"; }), "custoNaoQualidadeCentavos"),
      inspecoes: insp.length, reprovadas: insp.filter(function (i) { return i.resultado === "Reprovado"; }).map(inspecaoCalculada),
      aprovacaoPct: insp.length ? arred(insp.filter(aprovadaInspecao).length / insp.length * 100, 1) : null, metaAprovacaoPct: q.metaAprovacaoInspecaoPct,
      auditoriasPeriodo: audPer.length, conformidadePct: ver ? arred(conf / ver * 100, 1) : null, metaConformidadePct: q.metaConformidadeAuditoriaPct,
      auditoriasAtrasadas: painel.auditoriasAtrasadas, pauta: painel.pauta.slice(0, 6), porDisciplina: painel.porDisciplina,
      serie: serieQualidade(doProjeto(M.rncs, projetoId).map(rncCalculada), doProjeto(M.inspecoesQualidade, projetoId), mesDe(corte))
    };
  }
  function hseRg(projetoId, tipo, periodo, info) {
    var mes = tipo === "Mensal" ? periodo : mesDe(info.corte);
    var meses = mesesComHht(projetoId), primeiro = meses[0] || mes;
    var indMes = indicadoresHSEDe(projetoId, { inicio: mes, fim: mes });
    var indAcum = indicadoresHSEDe(projetoId, { inicio: primeiro, fim: mes });
    var oc = doProjeto(M.ocorrencias, projetoId).filter(function (o) { var d = o.dataHora.slice(0, 10); return !o.ambiental && d >= info.inicio && d <= info.corte; });
    var niveisPeriodo = [0, 0, 0, 0];
    oc.forEach(function (o) { var n = R.nivelPiramide(o.tipo); if (n && n <= 4) niveisPeriodo[n - 1]++; });
    /* Dias sem afastamento na data de corte do período (não na data de referência) */
    var ltis = doProjeto(M.ocorrencias, projetoId).filter(function (o) { return LTI.indexOf(o.tipo) >= 0 && o.dataHora.slice(0, 10) <= info.corte; }).map(function (o) { return o.dataHora.slice(0, 10); }).sort();
    var desde = ltis.pop() || (projetoId == null ? inicioCarteira() : (porId(M.projetos)[projetoId] || {}).inicio) || null;
    return { mes: mes, mesParcial: mes === mesDe(REF), primeiroMes: primeiro, mes_: indMes, acumulado: indAcum, referencia: P().hse.referenciaPiramide || "bird",
      diasSemAfastamento: desde ? Math.max(0, R.diasEntre(desde, info.corte)) : null, semAfastamentoDesde: desde,
      ocorrenciasPeriodo: oc.length, niveisPeriodo: niveisPeriodo, hipoPeriodo: oc.filter(function (o) { return o.hipo; }).length,
      evolucao: meses.filter(function (m) { return m <= mes; }).slice(-6).map(function (m) { var d = indicadoresHSEDe(projetoId, { inicio: m, fim: m }); return { mes: m, trif: d.trif, tf: d.tf }; }) };
  }

  /* Desvios negativos do período (estruturados; o texto é montado na tela, no idioma ativo) */
  function desviosDe(modulo, d) {
    var l = [];
    if (!d) return l;
    if (modulo === "planejamento") {
      if (d.desvioPP != null && d.desvioPP < 0) l.push({ chave: "avanco", indicador: "Avanço físico acumulado", dados: { real: d.real, previsto: d.previsto, desvio: d.desvioPP, spi: d.spi } });
      if (d.realPeriodo != null && d.previstoPeriodo != null && d.realPeriodo < d.previstoPeriodo) l.push({ chave: "avanco_periodo", indicador: "Avanço no período", dados: { real: d.realPeriodo, previsto: d.previstoPeriodo } });
      if (d.terminoTendencia && d.terminoBaseline && d.terminoTendencia > d.terminoBaseline) l.push({ chave: "termino", indicador: "Término pela tendência", dados: { tendencia: d.terminoTendencia, baseline: d.terminoBaseline } });
      var areas = (d.areas || []).filter(function (a) { return a.desvio < 0; });
      if (areas.length) l.push({ chave: "areas", indicador: "Avanço por área", dados: { itens: areas.map(function (a) { return { area: a.area, desvio: a.desvio }; }) } });
      var p = d.produtividade;
      if (p) {
        var it = [];
        if (p.spi != null && p.spi < 1) it.push({ chave: "spi", valor: p.spi, meta: 1 });
        if (p.pf != null && p.pf > p.metas.pf) it.push({ chave: "pf", valor: p.pf, meta: p.metas.pf });
        if (p.aderencia != null && p.aderencia < p.metas.aderencia) it.push({ chave: "aderencia", valor: p.aderencia, meta: p.metas.aderencia });
        if (p.pctTrabalhando != null && p.pctTrabalhando < p.metas.trabalhando) it.push({ chave: "trabalhando", valor: p.pctTrabalhando, meta: p.metas.trabalhando });
        if (p.utilizacao != null && p.utilizacao < p.metas.utilizacao) it.push({ chave: "utilizacao", valor: p.utilizacao, meta: p.metas.utilizacao });
        if (it.length) l.push({ chave: "produtividade", indicador: "Produtividade", dados: { itens: it, semanas: p.janela.n } });
      }
    } else if (modulo === "financeiro") {
      if (d.semFechamento) return l;
      var va = d.valorAgregado || {};
      if (va.cpi != null && va.cpi < 1) l.push({ chave: "cpi", indicador: "CPI (desempenho de custo)", dados: { cpi: va.cpi, cv: va.cv, ev: va.ev, ac: va.ac } });
      if (va.spi != null && va.spi < 1) l.push({ chave: "spi_custo", indicador: "SPI de custo (valor agregado)", dados: { spi: va.spi, sv: va.sv } });
      if (d.vac < 0) l.push({ chave: "vac", indicador: "Projeção no término", dados: { projecao: d.projecaoTermino, bac: d.bac, vac: d.vac, pct: d.desvioPct } });
      var pac = (d.pacotes || []).filter(function (x) { return x.desvio > 0; });
      if (pac.length) l.push({ chave: "pacotes", indicador: "Pacotes com sobrecusto projetado", dados: { itens: pac.map(function (x) { return { codigo: x.codigo, descricao: x.descricao, desvio: x.desvio, pct: x.desvioPct }; }) } });
    } else if (modulo === "suprimentos") {
      if (d.aderenciaPct != null && d.aderenciaPct < 100) l.push({ chave: "aderencia", indicador: "Aderência ao plano de compras", dados: { adjudicados: d.adjudicadosAteCorte, planejados: d.planejadosAteCorte, pct: d.aderenciaPct } });
      if (d.otdPct != null && d.otdPct < 100) l.push({ chave: "otd", indicador: "Entregas no prazo (OTD)", dados: { noPrazo: d.entregasNoPrazo, total: d.entregas, pct: d.otdPct } });
      if (d.criticos && d.criticos.length) l.push({ chave: "criticos", indicador: "Pedidos críticos", dados: { itens: d.criticos.map(function (c) { return { numero: c.numero, descricao: c.descricao, folga: c.folgaDias }; }) } });
      var atrasados = (d.eventos || []).filter(function (e) { return e.desvioDias > 0; });
      if (atrasados.length) l.push({ chave: "marcos_atrasados", indicador: "Marcos realizados com atraso no período", dados: { itens: atrasados.map(function (e) { return { codigo: e.codigo, marco: e.tipo, dias: e.desvioDias }; }) } });
    } else if (modulo === "qualidade") {
      if (d.vencidas && d.vencidas.length) l.push({ chave: "rnc_vencidas", indicador: "RNC com prazo de tratamento vencido", dados: { itens: d.vencidas.map(function (r) { return { codigo: r.codigo, dias: r.diasAtraso }; }) } });
      if (d.aprovacaoPct != null && d.aprovacaoPct < d.metaAprovacaoPct) l.push({ chave: "aprovacao_inspecao", indicador: "Aprovação em inspeções", dados: { pct: d.aprovacaoPct, meta: d.metaAprovacaoPct, reprovadas: d.reprovadas.length, total: d.inspecoes } });
      if (d.conformidadePct != null && d.conformidadePct < d.metaConformidadePct) l.push({ chave: "conformidade_auditoria", indicador: "Conformidade em auditorias", dados: { pct: d.conformidadePct, meta: d.metaConformidadePct } });
      if (d.auditoriasAtrasadas && d.auditoriasAtrasadas.length) l.push({ chave: "auditorias_atrasadas", indicador: "Auditorias atrasadas", dados: { itens: d.auditoriasAtrasadas.map(function (a) { return { codigo: a.codigo, dias: a.diasAtraso }; }) } });
    }
    return l;
  }
  /* Resumo de indicadores do período para o modal (contexto de quem escreve a análise) */
  function resumoAnalise(modulo, d) {
    if (!d) return [];
    function i(rotulo, valor, tipo, extra) { return Object.assign({ rotulo: rotulo, valor: valor, tipo: tipo || "num" }, extra || {}); }
    switch (modulo) {
      case "planejamento":
        return [i("Avanço previsto", d.previsto, "pct"), i("Avanço real", d.real, "pct"), i("SPI físico", d.spi, "indice"), i("SPI físico do período anterior", d.spiAnterior, "indice"),
          i("Avanço no período (real)", d.realPeriodo, "pp"), i("Avanço no período (previsto)", d.previstoPeriodo, "pp"),
          i("Término pela tendência", d.terminoTendencia, "mes"), i("Término da linha de base", d.terminoBaseline, "mes")].concat(d.produtividade ? [
          i("SPI de quantidades", d.produtividade.spi, "indice"), i("Fator de produtividade", d.produtividade.pf, "indice"), i("Aderência semanal", d.produtividade.aderencia, "pct")] : []);
      case "financeiro":
        if (d.semFechamento) return [];
        var va = d.valorAgregado || {}, an = d.anterior || {};
        return [i("Orçamento vigente (BAC)", d.bac, "moeda"), i("Realizado acumulado", d.realizado, "moeda"), i("Valor agregado (EV)", va.ev, "moeda"),
          i("CPI", va.cpi, "indice"), i("CPI do mês anterior", an.cpi, "indice"), i("SPI de custo", va.spi, "indice"), i("Projeção no término", d.projecaoTermino, "moeda"),
          i("Contingência consumida", d.contingenciaPct, "pct")];
      case "suprimentos":
        return [i("Aderência ao plano de compras", d.aderenciaPct, "pct"), i("Saving", d.savingPct, "pct"), i("Entregas no prazo (OTD)", d.otdPct, "pct"),
          i("Pedidos críticos", d.criticos.length, "num"), i("Pedidos em atenção", d.emAtencao, "num"), i("Pacotes adjudicados", d.adjudicadosAteCorte, "num")];
      case "riscos":
        return [i("Riscos ativos", d.resumo.ativos, "num"), i(d.resumo.topo.nome + "s", d.resumo.topo.total, "num"), i("Exposição (VME)", d.resumo.exposicaoCentavos, "moeda"),
          i("Revisão vencida", d.resumo.revisaoVencida, "num"), i("Identificados no período", d.identificadosNoPeriodo, "num"), i("Redução média", d.resumo.reducaoMediaPct, "pct")];
      case "qualidade":
        return [i("RNC abertas no período", d.abertasPeriodo, "num"), i("RNC encerradas no período", d.encerradasPeriodo, "num"), i("RNC em aberto no corte", d.emAbertoCorte, "num"),
          i("Aprovação em inspeções", d.aprovacaoPct, "pct"), i("Conformidade em auditorias", d.conformidadePct, "pct"), i("Custo da não qualidade acumulado", d.custoAcumuladoCentavos, "moeda")];
      case "hse":
        return [i("TF no mês", d.mes_.tf, "num2"), i("TRIF no mês", d.mes_.trif, "num2"), i("TRIF acumulada", d.acumulado.trif, "num2"), i("Dias sem afastamento", d.diasSemAfastamento, "num"),
          i("HiPo no mês", d.mes_.hipo, "num"), i("HHT no mês", d.mes_.hht, "num"), i("Ocorrências no período", d.ocorrenciasPeriodo, "num")];
    }
    return [];
  }
  /* Dados do módulo no período (mesmas funções do relatório gerencial) */
  function dadosModuloRg(projetoId, modulo, tipo, periodo) {
    var info = infoPeriodo(tipo, periodo), proximo = infoPeriodo(tipo, R.somarPeriodos(tipo, periodo, 1));
    switch (modulo) {
      case "planejamento": var p = planejamentoRg(projetoId, tipo, periodo, info); if (p) p.produtividade = produtividadeRg(projetoId, info); return p;
      case "financeiro": return financeiroRg(projetoId, tipo, periodo);
      case "suprimentos": return suprimentosRg(projetoId, tipo, periodo, info, proximo);
      case "riscos": return riscosRg(projetoId, info);
      case "qualidade": return qualidadeRg(projetoId, tipo, periodo, info);
      case "hse": return hseRg(projetoId, tipo, periodo, info);
    }
    return null;
  }
  function analiseRegistro(projetoId, modulo, tipo, periodo) {
    return doEscopo(M.analisesPeriodo, projetoId).filter(function (a) { return a.modulo === modulo && a.tipo === tipo && a.periodo === periodo; })[0] || null;
  }
  /* Registro + desvios atuais com o comentário gravado (por chave) */
  function analiseMontada(projetoId, modulo, tipo, periodo, dados) {
    var reg = analiseRegistro(projetoId, modulo, tipo, periodo);
    var coment = {};
    ((reg && reg.desvios) || []).forEach(function (x) { coment[x.chave] = x.comentario; });
    var desvios = desviosDe(modulo, dados).map(function (x) { x.comentario = coment[x.chave] || ""; return x; });
    return { modulo: modulo, nomeModulo: MODULOS_ANALISE[modulo], obrigatorio: !!DESVIO_OBRIGATORIO[modulo], registro: reg ? copia(reg) : null,
      desvios: desvios, pendentes: DESVIO_OBRIGATORIO[modulo] ? desvios.filter(function (x) { return !x.comentario; }).length : 0 };
  }
  function validarModuloAnalise(modulo) { return Object.prototype.hasOwnProperty.call(MODULOS_ANALISE, modulo); }
  /* TODO: API GET /projetos/{id}/analises/{modulo}/{tipo}/{periodo} */
  function analisePeriodo(projetoId, modulo, tipo, periodo) {
    if (!validarModuloAnalise(modulo)) return rejeitar("Módulo inválido.");
    if (TIPOS_RELATO.indexOf(tipo) < 0 || !R.periodoValido(tipo, periodo)) return rejeitar("Escolha o tipo e o período.");
    var dados = dadosModuloRg(projetoId, modulo, tipo, periodo);
    var x = analiseMontada(projetoId, modulo, tipo, periodo, dados);
    x.info = infoPeriodo(tipo, periodo);
    x.resumo = resumoAnalise(modulo, dados);
    var ant = analiseRegistro(projetoId, modulo, tipo, R.somarPeriodos(tipo, periodo, -1));
    x.anterior = ant ? { periodo: ant.periodo, rotulo: infoPeriodo(tipo, ant.periodo).rotulo, analise: ant.analise } : null;
    return responder(x);
  }
  /* Períodos com a situação da análise do módulo. TODO: API GET /projetos/{id}/analises/{modulo}/periodos?tipo */
  function periodosAnalise(projetoId, modulo, tipo) {
    var fx = faixaPeriodos(projetoId, tipo);
    return responder(R.listaPeriodos(tipo, fx.primeiro, fx.ultimo).reverse().map(function (p) {
      var i = infoPeriodo(tipo, p), r = analiseRegistro(projetoId, modulo, tipo, p);
      i.analiseId = r ? r.id : null;
      return i;
    }));
  }
  /* Situação das análises de um período em todos os módulos (modal do relatório no Início) */
  function situacaoAnalises(projetoId, tipo, periodo) {
    if (TIPOS_RELATO.indexOf(tipo) < 0 || !R.periodoValido(tipo, periodo)) return rejeitar("Escolha o tipo e o período.");
    return responder(Object.keys(MODULOS_ANALISE).map(function (m) {
      var x = analiseMontada(projetoId, m, tipo, periodo, dadosModuloRg(projetoId, m, tipo, periodo));
      return { modulo: m, nome: MODULOS_ANALISE[m], registrada: !!x.registro, desvios: x.desvios.length, pendentes: x.pendentes, obrigatorio: x.obrigatorio };
    }));
  }
  /* Grava a análise (novo ou edição). TODO: API PUT /projetos/{id}/analises/{modulo}/{tipo}/{periodo} */
  function salvarAnalisePeriodo(projetoId, modulo, d) {
    if (!temPapel("Membro")) return rejeitar("Seu papel não permite registrar a análise do período.");
    if (!validarModuloAnalise(modulo)) return rejeitar("Módulo inválido.");
    if (TIPOS_RELATO.indexOf(d.tipo) < 0 || !R.periodoValido(d.tipo, d.periodo)) return rejeitar("Escolha o tipo e o período.");
    var fx = faixaPeriodos(projetoId, d.tipo);
    if (d.periodo < fx.primeiro || d.periodo > fx.ultimo) return rejeitar("Período fora do intervalo do projeto (do início até o período corrente).");
    var e = [], texto = String(d.analise || "").trim();
    if (texto.length < LIMITES_ANALISE.minimo) e.push({ campo: "analise", msg: "A análise deve ter ao menos " + LIMITES_ANALISE.minimo + " caracteres: panorama, desempenho dos períodos anteriores, causas e tendência." });
    else if (texto.length > LIMITES_ANALISE.maximo) e.push({ campo: "analise", msg: "Até " + LIMITES_ANALISE.maximo + " caracteres." });
    var desvios = desviosDe(modulo, dadosModuloRg(projetoId, modulo, d.tipo, d.periodo));
    var coment = d.desvios || {};
    var gravar = desvios.map(function (x, k) {
      var c = String(coment[x.chave] || "").trim();
      if (DESVIO_OBRIGATORIO[modulo] && c.length < LIMITES_ANALISE.minimoDesvio) e.push({ campo: "desvio_" + k, msg: "Todo desvio negativo exige comentário (mínimo de " + LIMITES_ANALISE.minimoDesvio + " caracteres): causa, efeito e ação." });
      else if (c.length > LIMITES_ANALISE.maximoDesvio) e.push({ campo: "desvio_" + k, msg: "Até " + LIMITES_ANALISE.maximoDesvio + " caracteres." });
      return { chave: x.chave, indicador: x.indicador, comentario: c };
    }).filter(function (x) { return x.comentario; });
    if (e.length) return rejeitar(e);
    var reg = analiseRegistro(projetoId, modulo, d.tipo, d.periodo);
    if (!reg) { reg = { id: proximoId("analisesPeriodo"), projetoId: projetoId, modulo: modulo, tipo: d.tipo, periodo: d.periodo, criadoPorId: sessaoPessoa(), criadoEm: agoraIso() }; colecao("analisesPeriodo").push(reg); }
    reg.analise = texto; reg.desvios = gravar; reg.atualizadoPorId = sessaoPessoa(); reg.atualizadoEm = agoraIso();
    persistir("analisesPeriodo");
    return responder({ id: reg.id, modulo: modulo, tipo: d.tipo, periodo: d.periodo, rotulo: infoPeriodo(d.tipo, d.periodo).rotulo });
  }
  /* Exclusão (Gestor). TODO: API DELETE /projetos/{id}/analises/{id} */
  function excluirAnalisePeriodo(id) {
    if (!temPapel("Gestor")) return rejeitar("A exclusão da análise exige papel Gestor.");
    var lista = colecao("analisesPeriodo"), i = lista.findIndex(function (a) { return String(a.id) === String(id); });
    if (i < 0) return rejeitar("Análise não encontrada.");
    lista.splice(i, 1);
    persistir("analisesPeriodo");
    return responder({ id: id });
  }

  /* ======================================================================
     Portfólio: projetos da carteira, ponderação e visões consolidadas
     Regras (README, "Portfólio: regras"):
     * Peso do projeto na carteira: ponderação composta (parametros.portfolio.criterios), com o
       critério de valor sobre o orçamento vigente da EAC e os critérios qualitativos sobre as notas
       de 1 a 5 de cada projeto (projetos[].ponderacao). Pesos somam 100% (GI.regras.ponderarPortfolio).
     * Curva S física da carteira: média ponderada pelos pesos das curvas dos projetos, mês a mês,
       no calendário comum (antes do início do projeto vale 0; depois do fim, 100% na LB e o último
       valor no real). Curva S financeira: soma dos valores em R$ (sem ponderação).
     * Valor agregado da carteira: soma do EV, PV e AC de cada projeto (CPI = soma EV / soma AC).
       Por isso o SPI de custo da carteira pode diferir do SPI físico ponderado (documentado).
     * EAP e EAC da carteira: linha 0 = portfólio, nível 1 = projeto, nível 2 = pacotes principais
       (nível 1 da estrutura de cada projeto), com a numeração da carteira (1, 1.1 ...).
     TODO: API GET /portfolio (e as visões consolidadas de cada módulo com projetoId ausente)
     ====================================================================== */
  function projetosCarteira() { return (M.projetos || []).slice().sort(function (a, b) { return a.id - b.id; }); }
  function idsEscopo(projetoId) { return projetoId == null ? projetosCarteira().map(function (p) { return p.id; }) : [projetoId]; }
  function inicioCarteira() { return projetosCarteira().reduce(function (m, p) { return p.inicio && (!m || p.inicio < m) ? p.inicio : m; }, null); }
  function terminoCarteira() { return projetosCarteira().reduce(function (m, p) { return p.terminoPrevisto && (!m || p.terminoPrevisto > m) ? p.terminoPrevisto : m; }, null); }
  function parPortfolio() {
    return P().portfolio || { criterios: [{ id: "valor", nome: "Valor financeiro (orçamento vigente)", peso: 100, fonte: "orcamento" }], notaMinima: 1, notaMaxima: 5 };
  }
  /* Projeto do escopo ou o "projeto" sintético da carteira (cabeçalho de relatórios e telas) */
  function projetoOuCarteira(projetoId) {
    if (projetoId != null) return projetoDe(projetoId);
    var l = projetosCarteira();
    return { id: null, portfolio: true, codigo: "Portfólio", nome: "Portfólio de projetos", projetos: l.length,
      inicio: inicioCarteira(), terminoPrevisto: terminoCarteira(), orcamentoCentavos: soma(l, orcamentoVigente), gerenteId: null, clienteId: l.length ? l[0].clienteId : null };
  }
  function orcamentoVigente(p) {
    var t = mapaControleProjeto(p.id).total;
    return t && t.atual ? t.atual : (p.orcamentoCentavos || 0);
  }
  function pesosCarteira() {
    var lista = projetosCarteira().map(function (p) { return { id: p.id, orcamentoCentavos: orcamentoVigente(p), notas: p.ponderacao || {} }; });
    return R.ponderarPortfolio(lista, parPortfolio().criterios);
  }
  function pesoDe(id) { var w = pesosCarteira()[id]; return w ? w.peso : 0; }
  function proximoMes(m) { var y = Number(m.slice(0, 4)), n = Number(m.slice(5, 7)) + 1; if (n > 12) { n = 1; y++; } return y + "-" + String(n).padStart(2, "0"); }
  function mesAnterior(m) { var y = Number(m.slice(0, 4)), n = Number(m.slice(5, 7)) - 1; if (n < 1) { n = 12; y--; } return y + "-" + String(n).padStart(2, "0"); }
  function mesesUniao(curvas) {
    var ini = null, fim = null;
    curvas.forEach(function (c) { if (!c || !c.meses.length) return; if (!ini || c.meses[0] < ini) ini = c.meses[0]; var u = c.meses[c.meses.length - 1]; if (!fim || u > fim) fim = u; });
    return ini ? mesesEntre(ini, fim) : [];
  }
  function ultimoValor(serie) { for (var k = serie.length - 1; k >= 0; k--) if (serie[k] != null) return serie[k]; return null; }
  /* Valor de uma série acumulada num mês do calendário comum: antes do início = 0; depois do fim = depois */
  function valorAcum(c, serie, mes, depois) {
    var i = c.meses.indexOf(mes);
    if (i >= 0) return c[serie][i];
    if (mes < c.meses[0]) return 0;
    return depois;
  }

  /* ---- 02: Curva S física da carteira (ponderada) ---- */
  function curvaFisicaCarteira() {
    var pesos = pesosCarteira();
    var cs = projetosCarteira().map(function (p) { return { p: p, c: curvaFisicaProjeto(p.id), w: pesos[p.id] ? pesos[p.id].peso : 0 }; }).filter(function (x) { return x.c; });
    if (!cs.length) return null;
    var meses = mesesUniao(cs.map(function (x) { return x.c; }));
    var corte = cs.reduce(function (m, x) { return !m || x.c.corte > m ? x.c.corte : m; }, null);
    var somaW = soma(cs, "w") || 1;
    function media(fn) { return arred(soma(cs, function (x) { var v = fn(x.c); return v == null ? 0 : x.w * v; }) / somaW, 1); }
    return {
      id: null, projetoId: null, portfolio: true, corte: corte, meses: meses,
      baseline: meses.map(function (m) { return media(function (c) { return valorAcum(c, "baseline", m, 100); }); }),
      real: meses.map(function (m) { return m > corte ? null : media(function (c) { var v = valorAcum(c, "real", m, ultimoValor(c.real)); return v == null ? ultimoValor(c.real.filter(function (x, k) { return c.meses[k] <= m; })) : v; }); }),
      tendencia: meses.map(function (m) {
        if (m < corte) return null;
        return media(function (c) {
          var i = c.meses.indexOf(m);
          if (i >= 0) return c.tendencia[i] != null ? c.tendencia[i] : (m <= c.corte ? c.real[i] : c.baseline[i]);
          return m < c.meses[0] ? 0 : 100;
        });
      }),
      projetos: cs.map(function (x) { return { projetoId: x.p.id, codigo: x.p.codigo, peso: x.w }; })
    };
  }
  function curvaFisicaDe(projetoId) { return projetoId == null ? curvaFisicaCarteira() : curvaFisicaProjeto(projetoId); }
  /* Avanço por área; no Portfólio, uma linha por projeto (peso na carteira e índices da Curva S) */
  function avancoAreasDe(projetoId) {
    if (projetoId != null) return doProjeto(M.avancoAreas, projetoId).map(copia);
    var pesos = pesosCarteira();
    return projetosCarteira().map(function (p) {
      var ind = indicesFisicos(p.id) || {};
      return { id: p.id, projetoId: p.id, area: p.codigo + " · " + p.nome, codigo: p.codigo, nome: p.nome, peso: pesos[p.id] ? pesos[p.id].peso : 0,
        previsto: ind.previsto != null ? ind.previsto : 0, real: ind.real != null ? ind.real : 0 };
    });
  }

  /* ---- 03: Curva S financeira da carteira (soma em R$) e valor agregado ---- */
  function curvaFinanceiraCarteira() {
    var cs = projetosCarteira().map(function (p) { return curvaFinanceiraProjeto(p.id); }).filter(Boolean);
    if (!cs.length) return null;
    var meses = mesesUniao(cs), corte = cs.reduce(function (m, c) { return !m || c.corte > m ? c.corte : m; }, null);
    function somaSerie(serie, ateCorte, desdeCorte) {
      return meses.map(function (m) {
        if (ateCorte && m > corte) return null;
        if (desdeCorte && m < corte) return null;
        return soma(cs, function (c) { var v = valorAcum(c, serie, m, ultimoValor(c[serie])); return v == null ? 0 : v; });
      });
    }
    return { id: null, projetoId: null, portfolio: true, corte: corte, meses: meses,
      planejado: somaSerie("planejado"), comprometido: somaSerie("comprometido", true), realizado: somaSerie("realizado", true), projecao: somaSerie("projecao", false, true) };
  }
  function curvaFinanceiraDe(projetoId) { return projetoId == null ? curvaFinanceiraCarteira() : curvaFinanceiraProjeto(projetoId); }
  function vaCarteiraNoMes(mes) {
    var ev = 0, pv = 0, ac = 0, n = 0;
    projetosCarteira().forEach(function (p) {
      var fis = curvaFisicaProjeto(p.id), fin = curvaFinanceiraProjeto(p.id);
      if (!fis || !fin) return;
      var v = valorAgregadoNoMes(fis, fin, mapaControleProjeto(p.id).total.atual, mes);
      if (!v) return;
      ev += v.ev; pv += v.pv; ac += v.ac; n++;
    });
    if (!n) return null;
    return { mes: mes, ev: ev, pv: pv, ac: ac, cv: ev - ac, sv: ev - pv, cpi: arred(divide(ev, ac), 2), spi: arred(divide(ev, pv), 2), projetos: n };
  }
  function vaNoMes(projetoId, fis, fin, bac, mes) { return projetoId == null ? vaCarteiraNoMes(mes) : valorAgregadoNoMes(fis, fin, bac, mes); }

  /* ---- 03: EAC (mapa de controle) da carteira: projeto > pacotes principais ---- */
  function mapaCarteira() {
    var limites = P().financeiro.faixasDesvio, itens = [], pesos = pesosCarteira();
    projetosCarteira().forEach(function (p, k) {
      var m = mapaControleProjeto(p.id);
      if (!m.itens.length) return;
      var n = String(k + 1);
      itens.push(Object.assign(copia(m.total), { codigo: n, descricao: p.codigo + " · " + p.nome, nivel: 1, projetoId: p.id, projetoCodigo: p.codigo, projetoNome: p.nome,
        responsavelId: p.gerenteId, folha: false, projeto: true, peso: pesos[p.id] ? pesos[p.id].peso : 0 }));
      m.itens.filter(function (x) { return x.nivel === 1; }).forEach(function (x) {
        itens.push(Object.assign(copia(x), { codigo: n + "." + x.codigo, codigoProjeto: x.codigo, nivel: 2, projetoId: p.id, projetoCodigo: p.codigo, projetoNome: p.nome, folha: false }));
      });
    });
    var raiz = itens.filter(function (x) { return x.nivel === 1; });
    var total = { codigo: "", descricao: "Total do portfólio", nivel: 0 };
    CAMPOS_EAC.concat(["atual", "saldoAComprometer", "desvio"]).forEach(function (c) { total[c] = soma(raiz, c); });
    total.desvioPct = total.atual ? arred(total.desvio / total.atual * 100, 1) : null;
    total.faixa = total.desvioPct == null ? "neutro" : R.faixaDesvio(total.desvioPct, limites);
    return { itens: itens, total: total, portfolio: true };
  }
  function mapaControleDe(projetoId) { return projetoId == null ? mapaCarteira() : mapaControleProjeto(projetoId); }

  function indicesCustoCarteira() {
    var ind = projetosCarteira().map(function (p) { var x = indicesCustoProjeto(p.id); if (x) { x.projetoId = p.id; x.codigo = p.codigo; x.nome = p.nome; } return x; }).filter(Boolean);
    if (!ind.length) return null;
    var corte = ind.reduce(function (m, x) { return !m || x.corte > m ? x.corte : m; }, null);
    var atual = vaCarteiraNoMes(corte), anterior = vaCarteiraNoMes(mesAnterior(corte));
    var bac = soma(ind, "bac"), proj = soma(ind, "projecaoTermino"), comp = soma(ind, "comprometido");
    var cont = soma(ind, "contingencia"), consumida = soma(ind, "contingenciaConsumida");
    return {
      corte: corte, bac: bac, projecaoTermino: proj, vac: bac - proj,
      eacPorCpi: atual && atual.cpi ? Math.round(bac / divide(atual.ev, atual.ac)) : null,
      tcpi: atual ? arred(divide(bac - atual.ev, bac - atual.ac), 2) : null,
      atual: atual, anterior: anterior, comprometido: comp, comprometidoPct: bac ? arred(comp / bac * 100, 1) : null,
      contingencia: cont, contingenciaConsumida: consumida, contingenciaPct: cont ? arred(consumida / cont * 100, 1) : null,
      portfolio: true, porProjeto: ind
    };
  }
  function indicesCustoDe(projetoId) { return projetoId == null ? indicesCustoCarteira() : indicesCustoProjeto(projetoId); }

  /* ---- 03: Cronograma de desembolso da carteira ---- */
  function desembolsoCarteira() {
    var ds = projetosCarteira().map(function (p) { var d = desembolsoProjeto(p.id); return d ? { p: p, d: d } : null; }).filter(Boolean);
    if (!ds.length) return null;
    var meses = mesesUniao(ds.map(function (x) { return x.d; })), corte = ds.reduce(function (m, x) { return !m || x.d.corte > m ? x.d.corte : m; }, null);
    var futuros = meses.filter(function (m) { return m > corte; });
    function mensal(campo, nulo) {
      return meses.map(function (m) {
        var vals = ds.map(function (x) { var i = x.d.meses.indexOf(m); return i >= 0 ? x.d[campo][i] : null; });
        if (vals.every(function (v) { return v == null; })) return nulo ? null : 0;
        return vals.reduce(function (s, v) { return s + (v || 0); }, 0);
      });
    }
    var itens = [];
    ds.forEach(function (x, k) {
      var n = String(k + 1), nivel1 = x.d.itens.filter(function (i) { return i.nivel === 1; });
      var linha = { codigo: n, descricao: x.p.codigo + " · " + x.p.nome, nivel: 1, folha: false, projetoId: x.p.id, projecao: soma(nivel1, "projecao"), realizado: soma(nivel1, "realizado"), saldo: soma(nivel1, "saldo"), meses: {} };
      futuros.forEach(function (m) { linha.meses[m] = soma(nivel1, function (i) { return i.meses[m] || 0; }); });
      itens.push(linha);
      nivel1.forEach(function (i) { itens.push(Object.assign(copia(i), { codigo: n + "." + i.codigo, nivel: 2, folha: false, projetoId: x.p.id })); });
    });
    var totalMeses = {};
    futuros.forEach(function (m) { totalMeses[m] = soma(itens.filter(function (x) { return x.nivel === 1; }), function (x) { return x.meses[m] || 0; }); });
    var fin = curvaFinanceiraCarteira(), kc = fin.meses.indexOf(corte);
    return { corte: corte, meses: meses, futuros: futuros, planejado: mensal("planejado"), realizado: mensal("realizado", true), projetado: mensal("projetado", true),
      itens: itens, totalMeses: totalMeses, saldo: soma(itens.filter(function (x) { return x.nivel === 1; }), "saldo"),
      realizadoAcumulado: fin.realizado[kc], projecaoTermino: mapaCarteira().total.projecao, portfolio: true };
  }
  function desembolsoDe(projetoId) { return projetoId == null ? desembolsoCarteira() : desembolsoProjeto(projetoId); }

  /* ---- 02: EAP da carteira: projeto > pacotes principais (áreas) ---- */
  function eapCarteira() {
    var pesos = pesosCarteira(), faixas = parEap().faixasDesvioPP, itens = [], dadosP = [];
    projetosCarteira().forEach(function (p, k) {
      if (!temEap(p.id)) return;
      var d = eapDadosDe(p.id), t = d.arvore.total, n = String(k + 1), w = pesos[p.id] ? pesos[p.id].peso : 0;
      dadosP.push({ p: p, d: d, w: w });
      var areas = d.arvore.itens.filter(function (x) { return x.nivel === 1; });
      itens.push({ codigo: n, descricao: p.codigo + " · " + p.nome, nivel: 1, projeto: true, projetoId: p.id, projetoCodigo: p.codigo, peso: w, pesoNoPai: w,
        previsto: t.previsto, real: t.real, desvioPP: t.desvioPP, faixa: t.faixa, responsavelId: p.gerenteId,
        inicio: areas.reduce(function (m, x) { return x.inicio && (!m || x.inicio < m) ? x.inicio : m; }, null),
        termino: areas.reduce(function (m, x) { return x.termino && (!m || x.termino > m) ? x.termino : m; }, null),
        pacotes: d.indicadores.pacotes, planejamento: d.indicadores.planejamento, vencido: d.indicadores.vencidos > 0, folha: false,
        revisao: d.vigente ? d.vigente.revisao : null });
      areas.forEach(function (a) {
        itens.push(Object.assign(copia(a), { codigo: n + "." + a.codigo, codigoProjeto: a.codigo, nivel: 2, projetoId: p.id, projetoCodigo: p.codigo,
          pesoProjeto: a.peso, peso: arred(a.peso * w / 100, 2), pesoNoPai: a.peso, folha: false }));
      });
    });
    var somaW = soma(dadosP, "w") || 1;
    var total = { codigo: "", descricao: "Total do portfólio", nivel: 0, peso: arred(soma(dadosP, "w"), 2) };
    total.previsto = arred(soma(dadosP, function (x) { return x.w * x.d.arvore.total.previsto; }) / somaW, 2);
    total.real = arred(soma(dadosP, function (x) { return x.w * x.d.arvore.total.real; }) / somaW, 2);
    total.desvioPP = arred(total.real - total.previsto, 1);
    total.faixa = R.faixaDesvioFisico(total.desvioPP, faixas);
    var c = curvaFisicaCarteira(), i = c ? c.meses.indexOf(c.corte) : -1;
    var curva = c && i >= 0 ? { corte: c.corte, previsto: c.baseline[i], real: c.real[i], diferencaPP: arred(total.real - c.real[i], 1) } : null;
    var somaInd = function (campo) { return soma(dadosP, function (x) { return x.d.indicadores[campo] || 0; }); };
    var cod = function (pid) { return (porId(M.projetos)[pid] || {}).codigo || ""; };
    return {
      portfolio: true, arvore: { itens: itens, total: total },
      revisoes: dadosP.map(function (x) { return Object.assign(copia(x.d.vigente || {}), { projetoId: x.p.id, projetoCodigo: x.p.codigo, projetoNome: x.p.nome, revisoes: x.d.revisoes.length }); }),
      vigente: null, desdobramentos: [],
      smsPendentes: [].concat.apply([], dadosP.map(function (x) { return x.d.smsPendentes.map(function (s) { s.projetoCodigo = cod(s.projetoId); return s; }); })),
      curva: curva, referencia: REF,
      indicadores: {
        previsto: total.previsto, real: total.real, desvioPP: total.desvioPP, spi: arred(divide(total.real, total.previsto), 2),
        pacotes: somaInd("pacotes"), planejamento: somaInd("planejamento"), pesoPlanejamento: null, areas: somaInd("areas"), subareas: somaInd("subareas"),
        vencidos: somaInd("vencidos"), naoIniciados: somaInd("naoIniciados"), atrasados: somaInd("atrasados"), projetos: dadosP.length
      },
      parametros: copia(parEap())
    };
  }

  /* ---- Resumo da carteira: uma linha por projeto com peso, prazo, custo, riscos e alertas ---- */
  function faixaIndiceSaude(v, limites) { return v == null ? null : v >= limites[0] ? "success" : v >= limites[1] ? "warning" : "danger"; }
  function resumoCarteiraDe() {
    var pesos = pesosCarteira();
    var linhas = projetosCarteira().map(function (p) {
      var fis = indicesFisicos(p.id) || {}, custo = indicesCustoProjeto(p.id) || {}, va = custo.atual || {};
      var rsk = resumoRiscosDe(p.id), peds = pedidosDe(p.id), hse = indicadoresHSEDe(p.id), sm = resumoMudancasDe(p.id), ac = resumoAcoes(p.id);
      var prazo = faixaIndiceSaude(fis.spi, [0.95, 0.9]), cst = faixaIndiceSaude(va.cpi, [0.98, 0.93]);
      var ordemF = { success: 0, warning: 1, danger: 2 };
      var saude = [prazo, cst].filter(Boolean).sort(function (a, b) { return ordemF[b] - ordemF[a]; })[0] || null;
      return {
        projetoId: p.id, codigo: p.codigo, nome: p.nome, gerenteId: p.gerenteId, inicio: p.inicio, terminoPrevisto: p.terminoPrevisto,
        peso: pesos[p.id] ? pesos[p.id].peso : 0, partes: pesos[p.id] ? pesos[p.id].partes : {}, notas: copia(p.ponderacao || {}),
        bac: custo.bac != null ? custo.bac : orcamentoVigente(p), projecaoTermino: custo.projecaoTermino, vac: custo.vac,
        previsto: fis.previsto, real: fis.real, desvioPP: fis.desvioPP, spi: fis.spi, terminoBaseline: fis.terminoBaseline, terminoTendencia: fis.terminoTendencia,
        cpi: va.cpi != null ? va.cpi : null, spiCusto: va.spi != null ? va.spi : null, realizado: va.ac, ev: va.ev,
        riscosAtivos: rsk.ativos, riscosTopo: rsk.topo.total, nomeTopo: rsk.topo.nome, exposicaoCentavos: rsk.exposicaoCentavos,
        pedidosCriticos: peds.filter(function (x) { return x.critico; }).length, acoesAtrasadas: ac.atrasadas, smsAguardando: sm.aguardandoComite,
        trif: hse.trif, diasSemAfastamento: hse.diasSemAfastamento, faixaPrazo: prazo, faixaCusto: cst, saude: saude
      };
    });
    var c = curvaFisicaCarteira(), ic = indicesCustoCarteira() || {}, va = ic.atual || {}, ind = indicesFisicos(null) || {};
    return {
      referencia: REF, criterios: copia(parPortfolio().criterios), projetos: linhas,
      total: {
        projetos: linhas.length, bac: soma(linhas, "bac"), projecaoTermino: soma(linhas, function (l) { return l.projecaoTermino || 0; }),
        vac: soma(linhas, function (l) { return l.vac || 0; }), previsto: ind.previsto, real: ind.real, desvioPP: ind.desvioPP, spi: ind.spi,
        terminoBaseline: ind.terminoBaseline, terminoTendencia: ind.terminoTendencia, cpi: va.cpi, spiCusto: va.spi,
        riscosTopo: soma(linhas, "riscosTopo"), exposicaoCentavos: soma(linhas, "exposicaoCentavos"), pedidosCriticos: soma(linhas, "pedidosCriticos"),
        acoesAtrasadas: soma(linhas, "acoesAtrasadas"), smsAguardando: soma(linhas, "smsAguardando"), corte: c ? c.corte : null
      }
    };
  }
  /* TODO: API GET /portfolio/resumo */
  function carteira() { return responder(resumoCarteiraDe()); }
  /* Ponderação: pesos dos critérios (somam 100) e notas de 1 a 5 por projeto. Gera nova versão dos
     parâmetros (vigência) e grava as notas nos projetos. Só Gestor ou Admin. TODO: API PUT /portfolio/ponderacao */
  function salvarPonderacao(d, justificativa) {
    var sessao = M.sessao || {};
    if (["Gestor", "Admin"].indexOf(sessao.papelCodigo) < 0) return rejeitar("Somente Gestor ou Admin altera a ponderação da carteira.");
    var par = parPortfolio(), e = [];
    if (!justificativa || String(justificativa).trim().length < 10) e.push({ campo: "justificativa", msg: "Informe a justificativa da alteração (mínimo de 10 caracteres)." });
    var criterios = par.criterios.map(function (c) {
      var v = d.criterios && d.criterios[c.id] != null ? Number(d.criterios[c.id]) : c.peso;
      if (isNaN(v) || v < 0 || v > 100) e.push({ campo: "peso_" + c.id, msg: "Use um peso entre 0 e 100%." });
      return Object.assign({}, c, { peso: v });
    });
    var somaC = soma(criterios, "peso");
    if (Math.abs(somaC - 100) > 0.001) e.push({ campo: "peso_" + criterios[0].id, msg: "Os pesos dos critérios devem somar 100% (hoje somam " + arred(somaC, 2) + "%)." });
    var notas = d.notas || {};
    projetosCarteira().forEach(function (p) {
      criterios.filter(function (c) { return c.fonte === "nota"; }).forEach(function (c) {
        var v = notas[p.id] && notas[p.id][c.id] != null ? Number(notas[p.id][c.id]) : (p.ponderacao || {})[c.id];
        if (!(v >= par.notaMinima && v <= par.notaMaxima) || Math.round(v) !== v) e.push({ campo: "nota_" + p.id + "_" + c.id, msg: "Nota inteira de " + par.notaMinima + " a " + par.notaMaxima + "." });
      });
    });
    if (e.length) return rejeitar(e);
    var novos = copia(M.parametros);
    novos.portfolio = Object.assign({}, par, { criterios: criterios });
    var erros = R.validarParametros(novos);
    if (erros.length) return rejeitar(erros);
    var anterior = copia(M.parametros);
    anterior.vigenciaFim = REF;
    M.parametrosHistorico = (M.parametrosHistorico || []).concat([anterior]);
    novos.versao = anterior.versao + 1; novos.vigenciaInicio = REF; novos.alteradoPor = sessao.nome; novos.justificativa = String(justificativa).trim();
    M.parametros = novos;
    projetosCarteira().forEach(function (p) {
      var alvo = porId(M.projetos)[p.id];
      alvo.ponderacao = Object.assign({}, alvo.ponderacao || {});
      criterios.filter(function (c) { return c.fonte === "nota"; }).forEach(function (c) { if (notas[p.id] && notas[p.id][c.id] != null) alvo.ponderacao[c.id] = Number(notas[p.id][c.id]); });
    });
    persistir("parametrosHistorico"); persistir("parametros"); persistir("projetos");
    return responder(resumoCarteiraDe());
  }

  GI.api = {
    /* sessão */
    sessaoAtual: sessaoAtual, referencia: referencia, projetoAtualId: projetoAtualId, emPortfolio: emPortfolio, definirEscopo: definirEscopo,
    /* portfólio */
    portfolio: {
      resumo: carteira, pesos: function () { return copia(pesosCarteira()); }, salvarPonderacao: salvarPonderacao,
      projetos: function () { return copia(projetosCarteira()); }, criterios: function () { return copia(parPortfolio()); },
      projeto: function (id) { return copia(projetoOuCarteira(id == null ? null : Number(id))); }
    },
    restaurarDados: restaurarDados, haAlteracoes: haAlteracoes,
    /* genérico */
    listar: listar, obter: obter, salvar: salvar, excluir: excluir, proximoCodigo: proximoCodigo, cadastros: cadastros,
    /* parâmetros */
    parametros: parametros, salvarParametros: salvarParametros, historicoParametros: historicoParametros,
    /* módulos */
    central: { acoes: listarAcoes, resumo: function (id) { return responder(resumoAcoes(id)); } },
    planejamento: { curvaFisica: curvaFisica,
      eap: eapDe, eapRegistrarAvanco: eapRegistrarAvanco, eapImportarAvanco: eapImportarAvanco, eapEditarPacote: eapEditarPacote,
      eapNovoPacote: eapNovoPacote, eapNovaRevisao: eapNovaRevisao, eapPrevistoLinear: function (i, t) { return previstoLinearEap(i, t); },
      proximoCodigoEap: function (projetoId, pai) { return proximoCodigoEap(projetoId, pai); },
      punch: listarPunch, resumoPunch: function (id) { return responder(resumoPunch(id)); },
      relatos: listarRelatos, relato: obterRelato, periodosRelato: periodosRelato, resumoRelatos: resumoRelatos,
      salvarRelato: salvarRelato, excluirRelato: excluirRelato, infoPeriodo: function (tipo, periodo) { return copia(infoPeriodo(tipo, periodo)); },
      pode: function (papel) { return temPapel(papel); },
      TIPOS_RELATO: TIPOS_RELATO.slice(), NATUREZAS_RELATO: NATUREZAS_RELATO.slice(), LIMITES_RELATO: copia(LIMITES_RELATO),
      lookahead: listarLookahead, programacoes: listarProgramacoes, calcularProgramacao: calcularProgramacao,
      avancoAreas: function (id) { return responder(avancoAreasDe(id)); },
      produtividade: {
        quantidades: quantidades, salvarItem: salvarItemQtd, aprovarItem: aprovarItemQtd, revisarItem: revisarItemQtd, excluirItem: excluirItemQtd,
        apontar: apontarSemanaQtd, importarItens: importarItensQtd, item: function (id, corte) { var it = porId(M.produtividadeItens)[id]; return responder(it ? itemQtdCalculado(it, corte) : null); },
        horasEfetivas: horasEfetivas, salvarJornada: salvarJornada, salvarAmostragem: salvarAmostragem, salvarParalisacao: salvarParalisacao,
        kpis: kpisProdutividade, gerarAcao: gerarAcaoProdutividade, semanaAtual: semanaAtual, parametros: function () { return copia(parProd()); },
        smsRevisao: function (projetoId) { return responder(doProjeto(M.mudancas, projetoId).filter(function (s) { return SM_REVISAO_LB.indexOf(s.situacao) >= 0; }).map(function (s) { return { codigo: s.codigo, titulo: s.titulo, situacao: s.situacao }; })); },
        pode: function (papel) { return temPapel(papel); }, sessaoPessoa: function () { return sessaoPessoa(); },
        GRUPOS: GRUPOS_QTD.slice(), UNIDADES: UNIDADES_QTD.slice(), PERFIS: copia(PERFIS_QTD), MOTIVOS_PARADO: MOTIVOS_PARADO.slice(), MOTIVOS_TRANSITO: MOTIVOS_TRANSITO.slice(),
        MOTIVOS_PARALISACAO: MOTIVOS_PARALISACAO.slice(), RESPONSABILIDADES: RESPONSABILIDADES.slice(), RESP_EXTERNA: RESP_EXTERNA.slice()
      } },
    financeiro: { mapaControle: mapaControle, curvaFinanceira: curvaFinanceira, indicadores: indicadoresCusto, historicoIndices: historicoIndices,
      desembolso: desembolso, contingencia: contingencia, eac: eacDe, remanejar: remanejar, novaRevisao: novaRevisao, novoItemEac: novoItemEac,
      saldoLivre: function (projetoId, codigo) { return saldoLivreEac(projetoId, codigo, null); }, editarItem: editarItemEac,
      proximoCodigoEac: function (projetoId, pai) { return proximoCodigoEac(projetoId, pai); },
      importarCustos: importarCustos, atualizarProjecao: atualizarProjecao,
      contratos: listarContratos, claims: listarClaims, resumoContratos: function (id) { return responder(resumoContratos(id)); },
      consolidadoContratos: consolidadoContratos, contrato: contratoDetalhe, salvarAditivo: salvarAditivo, decidirEot: decidirEot,
      avaliacao: function (a) { return responder(avaliacaoCalculada(a)); } },
    suprimentos: { pedidos: listarPedidos, indicadores: indicadoresSuprimentos, mas: mas, pacotes: listarPacotes, salvarPacote: salvarPacote,
      importarPacotes: importarPacotes, proximoCodigoPacote: function (id) { return proximoCodigoPacote(id); },
      processos: listarProcessos, acaoProcesso: acaoProcesso, atualizarMarco: atualizarMarco, registrarRecebimento: registrarRecebimento,
      gerarAcao: gerarAcaoPedido, registrarRisco: registrarRiscoPedido, importarPedidos: importarPedidos,
      fornecedores: listarFornecedores, salvarQualificacao: salvarQualificacao, novoFornecedor: novoFornecedor,
      ETAPAS: ETAPAS_SUP.slice(), MARCOS_PEDIDO: NOMES_MARCOS_PEDIDO.slice(), SITUACOES_FORNECEDOR: SITUACOES_FORN.slice() },
    riscos: { lista: listarRiscos, resumo: resumoRiscos, matriz: matrizRiscos, painel: painelRiscos, risco: detalheRisco, previa: previaRisco,
      salvar: salvarRisco, avaliar: avaliarRisco, plano: salvarPlanoRisco, aprovarPlano: aprovarPlanoRisco, novaAcao: novaAcaoRisco,
      revisar: revisarRisco, encerrar: encerrarRisco, reabrir: reabrirRisco, excluir: excluirRisco, restaurar: restaurarRisco,
      categorias: categoriasRisco, novaCategoria: novaCategoriaRisco, legenda: function () { return legendaFaixas(); },
      pode: function (papel) { return temPapel(papel); },
      ESTRATEGIAS: copia(ESTRATEGIAS_RISCO), ORIGENS: ORIGENS_RISCO.slice(), SITUACOES: SITUACOES_RISCO.slice(), MOTIVOS_ENCERRAMENTO: MOTIVOS_ENCERRAMENTO.slice(),
      MOTIVOS_EXCLUSAO: MOTIVOS_EXCLUSAO.slice(), APURACOES: APURACOES.slice(), DIMENSOES: copia(DIMENSOES_RISCO), INSTRUMENTOS: INSTRUMENTOS_RISCO.slice() },
    qualidade: { indicadores: indicadoresQualidade, painel: function (projetoId) { return responder(painelQualidadeDe(projetoId)); },
      rncs: function (filtro) { return responder(listarRncsDe(filtro)); }, rnc: obterRnc, salvarRnc: salvarRnc, iniciarAnalise: iniciarAnaliseRnc,
      registrarAnalise: registrarAnaliseRnc, definirAcoes: definirAcoesRnc, enviarVerificacao: enviarVerificacaoRnc, verificarEficacia: verificarEficaciaRnc,
      cancelarRnc: cancelarRnc, atualizarCusto: atualizarCustoRnc,
      itps: function (filtro) { return responder(listarItpsDe(filtro)); }, itp: function (codigo) { var i = itpPorCodigo(codigo); return responder(i ? itpCalculado(i) : null); },
      salvarItp: salvarItp, aprovarItp: aprovarItp,
      inspecoes: function (filtro) { return responder(listarInspecoesDe(filtro)); }, registrarInspecao: registrarInspecao,
      auditorias: function (filtro) { return responder(listarAuditoriasDe(filtro)); },
      auditoria: function (codigo) { var a = auditoriaPorCodigo(codigo); return responder(a ? auditoriaCalculada(a) : null); },
      salvarAuditoria: salvarAuditoria, registrarResultado: registrarResultadoAuditoria,
      pode: function (papel) { return temPapel(papel); }, sessaoPessoa: function () { return sessaoPessoa(); },
      SITUACOES: SITUACOES_RNC.slice(), SEVERIDADES: SEVERIDADES_RNC.slice(), ORIGENS: ORIGENS_RNC.slice(), DISPOSICOES: DISPOSICOES_RNC.slice(),
      DISPOSICOES_CONCESSAO: DISPOSICOES_CONCESSAO.slice(), METODOS: METODOS_RNC.slice(), DISCIPLINAS: DISCIPLINAS_QUALIDADE.slice(),
      TIPOS_PONTO: TIPOS_PONTO.slice(), RESPONSAVEIS_PONTO: RESPONSAVEIS_PONTO.slice(), RESULTADOS: RESULTADOS_INSPECAO.slice(),
      TIPOS_AUDITORIA: TIPOS_AUDITORIA.slice(), TIPOS_CONSTATACAO: TIPOS_CONSTATACAO.slice()
    },
    hse: { indicadores: indicadoresHSE, painel: painelHSE,
      histograma: function (projetoId) { return responder(histogramaDe(projetoId)); },
      hhtPrevisto: function (projetoId, ateMes, soMes) { return hhtPrevistoDe(projetoId, ateMes, soMes); },
      metas: function () { return copia((P().hse || {}).metas || { observacoesPor10MilHht: 40, desviosPor10MilHht: 12 }); },
      ocorrencias: listarOcorrencias, ocorrencia: obterOcorrencia, salvarOcorrencia: salvarOcorrencia,
      investigar: investigarOcorrencia, definirAcoes: definirAcoesOcorrencia, iniciarTratamento: iniciarTratamentoOcorrencia, encerrarOcorrencia: encerrarOcorrencia,
      hht: function (filtro) { return responder(listarHht(filtro)); }, salvarHht: salvarHht,
      hseMensal: function (filtro) { return responder(listarHseMensal(filtro)); }, salvarHseMensal: salvarHseMensal,
      analisesRisco: listarAnalisesRisco, analiseRisco: obterAnaliseRisco, salvarAnaliseRisco: salvarAnaliseRisco,
      fecharRecomendacao: fecharRecomendacao, criarAcaoRecomendacao: criarAcaoRecomendacao,
      pode: function (papel) { return temPapel(papel); },
      TIPOS_PIRAMIDE: copia(TIPOS_OCORRENCIA_PIRAMIDE), NIVEIS_NOMES: NIVEIS_PIRAMIDE_NOMES.slice(),
      SITUACOES: SITUACOES_OCORRENCIA.slice(), METODOS_INVESTIGACAO: METODOS_INVESTIGACAO.slice(),
      CAUSAS_IMEDIATAS: CAUSAS_IMEDIATAS_HSE.slice(), SUBTIPOS_AMBIENTAL: SUBTIPOS_AMBIENTAL.slice(), SEVERIDADES_AMBIENTAL: SEVERIDADES_AMBIENTAL.slice()
    },
    governanca: { resumoMudancas: resumoMudancas, mudancas: listarMudancas, mudanca: obterMudanca, painelMudancas: painelMudancas,
      salvarMudanca: salvarMudanca, iniciarAnalise: iniciarAnaliseSm, salvarAnalise: salvarAnaliseSm, decidir: decidirMudanca,
      TIPO_LIBERACAO: TIPO_LIBERACAO,
      saldoReserva: function (projetoId, reserva, exceto) { return saldoContingencia(projetoId, exceto || null, reserva === "Gerencial" ? "Reserva gerencial" : "Reserva de contingência"); },
      remanejamentosPendentes: function (projetoId) { return responder(remanejamentosPendentesDe(projetoId)); }, TIPO_REMANEJAMENTO: TIPO_REMANEJAMENTO,
      saldoLivreEac: function (projetoId, codigo, exceto) { return saldoLivreEac(projetoId, codigo, exceto || null); },
      reapresentar: reapresentarMudanca, iniciarImplementacao: iniciarImplementacaoSm, encerrar: encerrarMudanca, cancelar: cancelarMudanca,
      conferencia: function (codigo) { var s = smPorCodigo(codigo); return responder(s ? conferenciaEncerramento(s) : null); },
      alcadaExigida: function (projetoId, custoCentavos, afetaMarco) {
        var proj = porId(M.projetos)[projetoId] || {};
        return R.alcadaMudanca(custoCentavos, proj.orcamentoCentavos, !!afetaMarco, parMud().alcadaGerentePctOrcamento);
      },
      licoes: listarLicoes, licao: obterLicao, painelLicoes: painelLicoes, salvarLicao: salvarLicao, enviarValidacao: enviarLicaoValidacao,
      validarLicao: validarLicao, publicarLicao: publicarLicao, aplicarLicao: aplicarLicao, disciplinas: disciplinasLicao,
      pode: function (papel) { return temPapel(papel); }, sessaoPessoa: function () { return sessaoPessoa(); },
      TIPOS: TIPOS_SM.slice(), ORIGENS: ORIGENS_SM.slice(), PRIORIDADES: PRIORIDADES_SM.slice(), SITUACOES: SITUACOES_SM.slice(),
      RESULTADOS: RESULTADOS_SM.slice(), FONTES: FONTES_SM.slice(), ALCADAS: ALCADAS_SM.slice(), ETAPAS: ETAPAS_SM.slice(),
      TIPOS_LICAO: TIPOS_LICAO.slice(), FASES: FASES_LICAO.slice(), AREAS: AREAS_LICAO.slice(), SITUACOES_LICAO: SITUACOES_LICAO.slice(),
      APLICABILIDADES: APLICABILIDADES.slice(), ORIGENS_LICAO: ORIGENS_LICAO.map(function (o) { return o.tipo; }).concat(["Registro direto"]),
      exigeRefOrigem: exigeRefOrigem },
    resumoHome: resumoHome,
    /* Início > relatório gerencial */
    relatorioGerencial: relatorioGerencial,
    /* Análise do período por módulo (02, 03, 04, 05 e 07) */
    analises: { periodo: analisePeriodo, periodos: periodosAnalise, situacao: situacaoAnalises, salvar: salvarAnalisePeriodo, excluir: excluirAnalisePeriodo,
      infoPeriodo: function (tipo, periodo) { return copia(infoPeriodo(tipo, periodo)); },
      pode: function (papel) { return temPapel(papel); },
      MODULOS: copia(MODULOS_ANALISE), OBRIGATORIO: copia(DESVIO_OBRIGATORIO), LIMITES: copia(LIMITES_ANALISE), TIPOS: TIPOS_RELATO.slice() },
    periodoPadraoRelatorio: function (tipo) { return R.somarPeriodos(tipo, R.periodoDaData(tipo, REF), -1); }
  };
})(window.GI = window.GI || {});
