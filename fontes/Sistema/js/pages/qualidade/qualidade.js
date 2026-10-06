/* ==========================================================================
   qualidade.js | Apoio comum às telas do módulo 06 Gestão da Qualidade (GI.qld)

   GI.qld.pronto()                          -> Promise (cadastros e parâmetros da qualidade)
   GI.qld.projeto()                         -> id do projeto atual (null = Portfólio)
   GI.qld.situacaoRnc(t) / severidade(s) / resultado(r) / tipoPonto(t) / situacaoAuditoria(a)
   Modais RNC: novaRnc, atribuirAnalise, registrarAnalise, novaAcao, enviarVerificacao,
               verificarEficacia, cancelarRnc, atualizarCusto, verRnc, acoesRnc (botões por etapa)
   Modais ITP e inspeção: editarItp, aprovarItp, verItp, registrarInspecao
   Modais auditoria: planejarAuditoria, registrarResultado, verAuditoria
   Regras e cálculos ficam em GI.api.qualidade; a tela só exibe o que a api devolve.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, API = GI.api.qualidade;
  var REF = GI.api.referencia();
  var param = null, carregando = null, seq = 0;

  function pronto() {
    if (!carregando) {
      carregando = Promise.all([U.pronto(), GI.api.parametros()]).then(function (r) { param = r[1].qualidade; return param; });
    }
    return carregando;
  }
  function projeto() { return GI.api.projetoAtualId(); }
  function erroApi(e) { GI.ui.toast((e && e.erros ? e.erros.map(function (x) { return x.msg || x; }).join(" ") : String(e)), "warning", 7000); }

  function pessoas() {
    return Object.keys(U.mapas.pessoas).map(function (k) { var p = U.mapas.pessoas[k]; return { valor: k, texto: p.nome + " (" + p.funcao + ")" }; })
      .sort(function (a, b) { return a.texto.localeCompare(b.texto); });
  }
  function empresas() {
    return Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; })
      .sort(function (a, b) { return a.texto.localeCompare(b.texto); });
  }
  function lista(arr) { return arr.map(function (x) { return { valor: x, texto: x }; }); }

  /* ---------------- Selos ---------------- */
  var COR_SIT = { "Aberta": "neutral", "Em análise de causa": "warning", "Ação corretiva": "info", "Verificação de eficácia": "purple", "Encerrada": "success", "Cancelada": "neutral" };
  function situacaoRnc(t) { return U.badge(t, COR_SIT[t] || "neutral", true); }
  var COR_SEV = { "Crítica": "danger", "Maior": "warning", "Menor": "info" };
  function severidade(s) { return s ? U.badge(s, COR_SEV[s] || "neutral") : ""; }
  var COR_RES = { "Aprovado": "success", "Aprovado com ressalva": "warning", "Reprovado": "danger" };
  function resultado(r) { return U.badge(r, COR_RES[r] || "neutral", true); }
  var NOME_PONTO = { H: "Espera (H)", W: "Testemunho (W)", R: "Registro (R)" };
  var COR_PONTO = { H: "danger", W: "info", R: "neutral" };
  function tipoPonto(t) { return '<span class="badge badge--' + (COR_PONTO[t] || "neutral") + '" title="' + U.esc(NOME_PONTO[t] || t) + '">' + U.esc(t) + "</span>"; }
  function situacaoAuditoria(a) {
    if (a.atrasada) return U.badge("Atrasada", "danger", true);
    return U.badge(a.situacao, a.situacao === "Realizada" ? "success" : "info", true);
  }
  function campoInfo(rotulo, html) { return '<div class="field"><span class="field__label">' + U.esc(rotulo) + "</span><div>" + (html || "·") + "</div></div>"; }
  function historicoTabela(idEl, linhas) {
    var t = GI.tabela.criar(idEl, {
      porPagina: 10, legenda: "Histórico", compacta: true, ordem: { coluna: "quando", direcao: "desc" },
      colunas: [
        { id: "quando", titulo: "Quando", classe: "nowrap", valor: function (h) { return h.quando; },
          html: function (h) { return F.data(h.quando.slice(0, 10)) + (h.quando.length > 10 ? " " + h.quando.slice(11, 16) : ""); },
          exportar: function (h) { return F.data(h.quando.slice(0, 10)); } },
        { id: "quem", titulo: "Quem", valor: function (h) { return h.porId ? U.pessoa(h.porId) : ""; } },
        { id: "texto", titulo: "O que aconteceu" }
      ]
    });
    t.atualizar(linhas || []);
    return t;
  }
  function subcamposAcao() {
    return [
      { id: "assunto", rotulo: "Ação corretiva", tipo: "texto", obrigatorio: true, max: 255, largura: "full" },
      { id: "responsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: pessoas() },
      { id: "prevista", rotulo: "Data prevista", tipo: "data", obrigatorio: true }
    ];
  }
  function prazoTexto(sev) {
    if (!param || !sev) return "";
    var k = sev === "Crítica" ? "critica" : sev === "Menor" ? "menor" : "maior";
    return "Prazo de tratamento: " + param.prazoTratamentoDias[k] + " dias (" + sev + ").";
  }

  /* ======================================================================
     RNC
     ====================================================================== */
  function novaRnc(projetoId, aoConcluir, pre) {
    if (projetoId == null) { U.noProjeto("nova", "Nova RNC"); return; }
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite abrir RNC.", "warning"); return; }
    pre = pre || {};
    return pronto().then(function () {
      return GI.form.abrir({
        titulo: "Nova não conformidade (RNC)", tamanho: "lg", textoSalvar: "Abrir RNC",
        intro: '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">Fluxo: Aberta &rarr; Em análise de causa &rarr; Ação corretiva &rarr; Verificação de eficácia &rarr; Encerrada. ' +
          "A contenção imediata é obrigatória; o prazo de tratamento vem da severidade.</div></div>",
        campos: [
          { id: "data", rotulo: "Data da constatação", tipo: "data", obrigatorio: true, valor: REF, maxData: REF },
          { id: "origem", rotulo: "Origem", tipo: "select", obrigatorio: true, opcoes: lista(API.ORIGENS), valor: pre.origem || "" },
          { id: "origemRef", rotulo: "Referência da origem", tipo: "texto", max: 40, placeholder: "Ex.: INS-2026-0160, AUD-TN-2026-02, PED-2026-0004", valor: pre.origemRef || "" },
          { id: "disciplina", rotulo: "Disciplina", tipo: "select", obrigatorio: true, opcoes: lista(API.DISCIPLINAS), valor: pre.disciplina || "" },
          { id: "empresaId", rotulo: "Empresa responsável", tipo: "select", obrigatorio: true, opcoes: empresas(), valor: pre.empresaId || "" },
          { id: "severidade", rotulo: "Severidade", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: [
            { valor: "Crítica", texto: "Crítica", sub: "segurança, integridade ou requisito legal" },
            { valor: "Maior", texto: "Maior", sub: "afeta função, prazo ou custo" },
            { valor: "Menor", texto: "Menor", sub: "desvio pontual sem efeito na função" }] },
          { id: "prazoInfo", tipo: "info", html: "" },
          { id: "descricao", rotulo: "Descrição da não conformidade", tipo: "textarea", obrigatorio: true, max: 600, linhas: 3,
            placeholder: "O que foi constatado, onde e qual requisito (desenho, especificação, norma) não foi atendido" },
          { id: "contencao", rotulo: "Contenção imediata", tipo: "textarea", obrigatorio: true, max: 400, linhas: 2,
            placeholder: "Bloqueio, segregação, identificação ou suspensão da atividade" },
          { id: "evidencias", rotulo: "Evidências (fotos, relatórios)", tipo: "arquivo", multiplo: true, aceitar: ["jpg", "jpeg", "png", "pdf"] }
        ],
        aoMudar: function (v, ctx) { ctx.info("prazoInfo", v.severidade ? '<span class="text-small text-muted">' + U.esc(prazoTexto(v.severidade)) + "</span>" : ""); },
        aoSalvar: function (v) {
          return API.salvarRnc({ projetoId: projetoId, data: v.data, origem: v.origem, origemRef: v.origemRef, disciplina: v.disciplina, empresaId: v.empresaId,
            severidade: v.severidade, descricao: v.descricao, contencao: v.contencao }).then(function (r) {
            GI.ui.toast(r.codigo + " aberta. Prazo de tratamento: " + F.data(r.prazo) + ".", "success", 6000);
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }

  function comRnc(codigo, fn) {
    return API.rnc(codigo).then(function (r) {
      if (!r) { GI.ui.toast("RNC não encontrada.", "warning"); return; }
      return fn(r);
    });
  }

  function atribuirAnalise(codigo, aoConcluir) {
    return comRnc(codigo, function (r) {
      return GI.form.abrir({
        titulo: "Atribuir análise de causa · " + r.codigo, subtitulo: r.descricao, tamanho: "sm", textoSalvar: "Atribuir",
        campos: [{ id: "responsavelId", rotulo: "Responsável pela análise", tipo: "select", obrigatorio: true, opcoes: pessoas(),
          ajuda: "Normalmente o responsável técnico da empresa que gerou a não conformidade." }],
        aoSalvar: function (v) {
          return API.iniciarAnalise(r.codigo, v).then(function () { GI.ui.toast("Análise atribuída.", "success"); if (aoConcluir) aoConcluir(r.codigo); });
        }
      });
    });
  }

  function registrarAnalise(codigo, aoConcluir) {
    return comRnc(codigo, function (r) {
      return pronto().then(function () {
        return GI.form.abrir({
          titulo: "Análise de causa e disposição · " + r.codigo, subtitulo: r.disciplina + " · " + U.empresa(r.empresaId), tamanho: "lg", textoSalvar: "Registrar análise",
          intro: '<p class="text-small text-muted mb-4">' + U.esc(r.descricao) + "</p>",
          campos: [
            { id: "metodo", rotulo: "Método de análise", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: lista(API.METODOS) },
            { id: "causaRaiz", rotulo: "Causa raiz", tipo: "textarea", obrigatorio: true, max: 800, linhas: 3 },
            { id: "disposicao", rotulo: "Disposição do produto não conforme", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: [
              { valor: "Retrabalho", texto: "Retrabalho", sub: "volta ao requisito" }, { valor: "Reparo", texto: "Reparo", sub: "aceitável com concessão" },
              { valor: "Usar como está", texto: "Usar como está", sub: "com concessão" }, { valor: "Rejeitar", texto: "Rejeitar", sub: "sucata ou devolução" },
              { valor: "Reclassificar", texto: "Reclassificar", sub: "outro uso" }] },
            { id: "concessaoReferencia", rotulo: "Concessão do cliente (documento)", tipo: "texto", obrigatorio: true, max: 120,
              placeholder: "Ex.: carta, parecer de engenharia ou aceite formal", mostrarSe: function (v) { return API.DISPOSICOES_CONCESSAO.indexOf(v.disposicao) >= 0; } },
            { id: "concessaoData", rotulo: "Data da concessão", tipo: "data", obrigatorio: true, maxData: REF, mostrarSe: function (v) { return API.DISPOSICOES_CONCESSAO.indexOf(v.disposicao) >= 0; } },
            { id: "custoCentavos", rotulo: "Custo da não qualidade estimado", tipo: "moeda", valor: r.custoNaoQualidadeCentavos || 0,
              ajuda: "Retrabalho, reparo, ensaios, perda de material e paralisação." },
            { id: "acoes", rotulo: "Ações corretivas (vão para a Central de Ações, origem RNC)", tipo: "repetir", rotuloItem: "Ação", textoAdicionar: "Adicionar ação",
              minimo: 1, maximo: 8, valor: [{}], itens: subcamposAcao() }
          ],
          aoSalvar: function (v) {
            return API.registrarAnalise(r.codigo, v).then(function (x) {
              GI.ui.toast("Análise registrada; " + U.plural(x.criadas, "ação corretiva criada", "ações corretivas criadas") + " na Central.", "success", 6000);
              if (aoConcluir) aoConcluir(r.codigo);
            });
          }
        });
      });
    });
  }

  function novaAcao(codigo, aoConcluir) {
    return comRnc(codigo, function (r) {
      return GI.form.abrir({
        titulo: "Nova ação corretiva · " + r.codigo, subtitulo: r.descricao, tamanho: "lg",
        campos: subcamposAcao().concat([{ id: "descricao", rotulo: "Descrição", tipo: "textarea", max: 500 }]),
        aoSalvar: function (v) {
          return API.definirAcoes(r.codigo, [v]).then(function () { GI.ui.toast("Ação corretiva criada na Central.", "success"); if (aoConcluir) aoConcluir(r.codigo); });
        }
      });
    });
  }

  function enviarVerificacao(codigo, aoConcluir) {
    GI.modal.confirm({ title: "Enviar para verificação de eficácia",
      message: "Todas as ações corretivas da " + codigo + " estão concluídas? A verificação fica prevista para " + (param ? param.verificacaoEficaciaDias : 30) + " dias à frente." }).then(function (ok) {
      if (!ok) return;
      API.enviarVerificacao(codigo).then(function (r) {
        GI.ui.toast("Verificação de eficácia prevista para " + F.data(r.verificacaoPrevista) + ".", "success");
        if (aoConcluir) aoConcluir(codigo);
      }).catch(erroApi);
    });
  }

  function verificarEficacia(codigo, aoConcluir) {
    return comRnc(codigo, function (r) {
      return GI.form.abrir({
        titulo: "Verificar eficácia · " + r.codigo, subtitulo: r.descricao, tamanho: "lg", textoSalvar: "Registrar verificação",
        intro: '<p class="text-small text-muted mb-4">Causa raiz: ' + U.esc(r.causaRaiz || "") + "</p>",
        campos: [
          { id: "eficaz", rotulo: "Resultado", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: [
            { valor: "sim", texto: "Eficaz", sub: "a causa foi eliminada; encerra a RNC" }, { valor: "nao", texto: "Ineficaz", sub: "volta para Ação corretiva" }] },
          { id: "texto", rotulo: "Evidência da verificação", tipo: "textarea", obrigatorio: true, max: 600, linhas: 3,
            placeholder: "Inspeções seguintes, ensaios, auditoria ou indicador que comprovam o resultado" },
          { id: "data", rotulo: "Data da verificação", tipo: "data", obrigatorio: true, valor: REF, maxData: REF },
          { id: "registrarLicao", rotulo: "Registrar lição aprendida (Rascunho no 08 Governança)", tipo: "check", largura: "full", mostrarSe: function (v) { return v.eficaz === "sim"; } },
          { id: "licaoTitulo", rotulo: "Título da lição", tipo: "texto", obrigatorio: true, max: 120, largura: "full", mostrarSe: function (v) { return v.eficaz === "sim" && v.registrarLicao; } },
          { id: "licaoRecomendacao", rotulo: "Recomendação", tipo: "textarea", obrigatorio: true, max: 500, mostrarSe: function (v) { return v.eficaz === "sim" && v.registrarLicao; } }
        ],
        aoSalvar: function (v) {
          return API.verificarEficacia(r.codigo, { eficaz: v.eficaz === "sim" ? true : v.eficaz === "nao" ? false : null, texto: v.texto, data: v.data,
            registrarLicao: v.registrarLicao, licaoTitulo: v.licaoTitulo, licaoRecomendacao: v.licaoRecomendacao }).then(function (x) {
            GI.ui.toast(x.encerrada ? "RNC encerrada." + (x.licaoRef ? " Lição " + x.licaoRef + " em Rascunho." : "") : "Ação ineficaz: a RNC voltou para Ação corretiva.", x.encerrada ? "success" : "warning", 6000);
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }

  function cancelarRnc(codigo, aoConcluir) {
    return GI.form.abrir({
      titulo: "Cancelar RNC · " + codigo, tamanho: "sm", textoSalvar: "Cancelar RNC",
      intro: '<p class="text-small text-muted mb-4">Só antes da ação corretiva, quando o registro foi indevido ou duplicado.</p>',
      campos: [{ id: "motivo", rotulo: "Motivo", tipo: "textarea", obrigatorio: true, max: 300 }],
      aoSalvar: function (v) { return API.cancelarRnc(codigo, v).then(function () { GI.ui.toast("RNC cancelada.", "success"); if (aoConcluir) aoConcluir(codigo); }); }
    });
  }

  function atualizarCusto(codigo, aoConcluir) {
    return comRnc(codigo, function (r) {
      return GI.form.abrir({
        titulo: "Custo da não qualidade · " + r.codigo, tamanho: "sm",
        campos: [
          { id: "custoCentavos", rotulo: "Custo apurado", tipo: "moeda", obrigatorio: true, valor: r.custoNaoQualidadeCentavos || 0 },
          { id: "justificativa", rotulo: "Composição do custo", tipo: "textarea", obrigatorio: true, max: 300, placeholder: "Horas de retrabalho, ensaios, material, equipamento parado" }
        ],
        aoSalvar: function (v) { return API.atualizarCusto(r.codigo, v).then(function () { GI.ui.toast("Custo atualizado.", "success"); if (aoConcluir) aoConcluir(r.codigo); }); }
      });
    });
  }

  /* Botões de fluxo da RNC conforme a etapa (lista e ficha) */
  function acoesRnc(r, compacto) {
    var b = [], cls = "btn btn--ghost btn--sm";
    function bt(acao, icone, texto) { return '<button type="button" class="' + cls + '" data-rnc-acao="' + acao + '" data-codigo="' + U.esc(r.codigo) + '">' + U.icone(icone) + U.esc(texto) + "</button>"; }
    /* Na lista (compacto) só o passo seguinte, com rótulo curto; na ficha, todos os botões da etapa */
    if (r.situacao === "Aberta") b.push(bt("atribuir", "user", compacto ? "Atribuir" : "Atribuir análise"));
    if (r.situacao === "Em análise de causa") b.push(bt("analisar", "fileSearch", compacto ? "Analisar" : "Registrar análise"));
    if (r.situacao === "Ação corretiva") { if (!compacto) b.push(bt("acao", "plus", "Ação")); b.push(bt("verificacao", "send", compacto ? "Verificação" : "Enviar para verificação")); }
    if (r.situacao === "Verificação de eficácia") b.push(bt("eficacia", "checkCircle", compacto ? "Eficácia" : "Verificar eficácia"));
    if (!compacto && r.ativa) b.push(bt("custo", "coins", "Custo"));
    if (!compacto && (r.situacao === "Aberta" || r.situacao === "Em análise de causa")) b.push(bt("cancelar", "x", "Cancelar RNC"));
    return b.join("");
  }
  function executarAcaoRnc(acao, codigo, aoConcluir) {
    var m = { atribuir: atribuirAnalise, analisar: registrarAnalise, acao: novaAcao, verificacao: enviarVerificacao, eficacia: verificarEficacia,
      custo: atualizarCusto, cancelar: cancelarRnc, ver: verRnc }[acao];
    if (m) { var p = m(codigo, aoConcluir); if (p && p.catch) p.catch(erroApi); }
  }

  function verRnc(codigo, aoConcluir) {
    return comRnc(codigo, function (r) {
      var n = ++seq, corpo = document.createElement("div");
      corpo.innerHTML = '<div class="form-grid mb-4">' +
        campoInfo("Situação", situacaoRnc(r.situacao) + (r.reincidencias ? " " + U.badge(U.plural(r.reincidencias, "reincidência", "reincidências"), "danger") : "")) +
        campoInfo("Severidade", severidade(r.severidade)) +
        campoInfo("Projeto", U.esc(r.projetoCodigo)) +
        campoInfo("Data", U.esc(F.data(r.data))) +
        campoInfo("Origem", U.esc(r.origem + (r.origemRef ? " · " + r.origemRef : ""))) +
        campoInfo("Disciplina", U.esc(r.disciplina)) +
        campoInfo("Empresa", U.esc(U.empresa(r.empresaId))) +
        campoInfo("Responsável pela análise", r.responsavelId ? U.esc(U.pessoa(r.responsavelId)) : '<span class="text-muted">a atribuir</span>') +
        campoInfo("Prazo de tratamento", U.esc(F.data(r.prazo)) + (r.vencida ? " " + U.badge("vencido há " + r.diasAtraso + (r.diasAtraso === 1 ? " dia" : " dias"), "danger") : "")) +
        campoInfo("Custo da não qualidade", '<span class="num">' + U.esc(F.moeda(r.custoNaoQualidadeCentavos || 0)) + "</span>") +
        (r.verificacaoPrevista ? campoInfo("Verificação prevista", U.esc(F.data(r.verificacaoPrevista)) + (r.verificacaoVencida ? " " + U.badge("vencida", "danger") : "")) : "") +
        (r.licaoRef ? campoInfo("Lição aprendida", '<a href="' + U.tela("governanca", "licoes", { busca: r.licaoRef }) + '">' + U.esc(r.licaoRef) + "</a>") : "") +
        "</div>" +
        "<p class=\"mb-4\">" + U.esc(r.descricao) + "</p>" +
        '<div class="alert mb-4">' + U.icone("shieldCheck") + '<div class="alert__body"><b>Contenção</b>: ' + U.esc(r.contencao || "não registrada") + "</div></div>" +
        (r.causaRaiz ? '<div class="alert mb-4">' + U.icone("fileSearch") + '<div class="alert__body"><b>Causa raiz (' + U.esc(r.metodo) + ")</b>: " + U.esc(r.causaRaiz) +
          "<br><b>Disposição</b>: " + U.esc(r.disposicao) + (r.concessao ? " · concessão " + U.esc(r.concessao.referencia) + " (" + U.esc(F.data(r.concessao.data)) + ")" : "") + "</div></div>" : "") +
        (r.eficacia ? '<div class="alert ' + (r.eficacia.eficaz ? "alert--success" : "alert--warning") + ' mb-4">' + U.icone(r.eficacia.eficaz ? "checkCircle" : "alertTriangle") +
          '<div class="alert__body"><b>' + (r.eficacia.eficaz ? "Eficácia verificada" : "Última verificação: ineficaz") + "</b> (" + U.esc(F.data(r.eficacia.data)) + "): " + U.esc(r.eficacia.texto) + "</div></div>" : "") +
        (r.acoesLista && r.acoesLista.length ? '<h3 class="section-title">Ações na Central</h3><div id="t-acoes-rnc-' + n + '" class="mb-4"></div>' : "") +
        '<h3 class="section-title">Histórico</h3><div id="t-hist-rnc-' + n + '"></div>';
      var botoes = [{ label: "Fechar", variant: "secondary" }];
      var m = GI.modal.create({ title: r.codigo, subtitle: r.proximaEtapa ? "Próxima etapa: " + r.proximaEtapa : r.situacao, size: "lg", body: corpo, buttons: botoes });
      var barra = document.createElement("div");
      barra.className = "btn-group mb-4";
      barra.innerHTML = acoesRnc(r, false);
      if (barra.innerHTML) corpo.insertBefore(barra, corpo.firstChild);
      barra.addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-rnc-acao]"); if (!b) return;
        m.close(); executarAcaoRnc(b.getAttribute("data-rnc-acao"), r.codigo, aoConcluir);
      });
      if (r.acoesLista && r.acoesLista.length) {
        GI.tabela.criar("t-acoes-rnc-" + n, {
          porPagina: 0, compacta: true, legenda: "Ações na Central",
          colunas: [
            { id: "item", titulo: "Item", classe: "nowrap" },
            { id: "assunto", titulo: "Assunto" },
            { id: "responsavel", titulo: "Responsável", valor: function (a) { return U.pessoa(a.responsavelId); } },
            { id: "prevista", titulo: "Prevista", tipo: "data", valor: function (a) { return a.replanejada || a.prevista; } },
            { id: "status", titulo: "Status", valor: function (a) { return a.statusRotulo; }, html: function (a) { return U.badge(a.statusRotulo, U.statusAcao(a.status)); } }
          ]
        }).atualizar(r.acoesLista);
      }
      historicoTabela("t-hist-rnc-" + n, r.historicoExibicao);
      GI.ui.init(m.el);
      return m;
    });
  }

  /* ======================================================================
     ITP e inspeções
     ====================================================================== */
  function editarItp(projetoId, itp, aoConcluir) {
    if (!itp && projetoId == null) { U.noProjeto("novo-itp", "Novo ITP"); return; }
    return pronto().then(function () {
      return GI.form.abrir({
        titulo: itp ? "Nova revisão · " + itp.codigo : "Novo plano de inspeção e testes (ITP)", subtitulo: itp ? "Rev " + itp.revisao + " para Rev " + (itp.revisao + 1) + "; volta a pedir a aprovação do cliente" : "",
        tamanho: "xl",
        intro: '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">H = ponto de espera (a atividade seguinte só é liberada com o registro aprovado); W = testemunho (cliente notificado com ' +
          (param ? param.notificacaoClienteHoras : 48) + " horas de antecedência); R = revisão de registros. Inspeção só em ITP aprovado pelo cliente.</div></div>",
        campos: [
          { id: "titulo", rotulo: "Título", tipo: "texto", obrigatorio: true, max: 120, largura: "full", valor: itp ? itp.titulo : "" },
          { id: "disciplina", rotulo: "Disciplina", tipo: "select", obrigatorio: true, opcoes: lista(API.DISCIPLINAS), valor: itp ? itp.disciplina : "" },
          { id: "empresaId", rotulo: "Empresa executante", tipo: "select", obrigatorio: true, opcoes: empresas(), valor: itp ? String(itp.empresaId) : "" },
          { id: "pontos", rotulo: "Pontos de inspeção", tipo: "repetir", rotuloItem: "Ponto", textoAdicionar: "Adicionar ponto", minimo: 1, maximo: 40,
            valor: itp ? itp.pontos.map(function (p) { return { atividade: p.atividade, tipo: p.tipo, criterio: p.criterio, referencia: p.referencia, responsavel: p.responsavel }; }) : [{}],
            itens: [
              { id: "atividade", rotulo: "Atividade", tipo: "texto", obrigatorio: true, max: 120, largura: "full" },
              { id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, opcoes: [{ valor: "H", texto: "H", sub: "espera" }, { valor: "W", texto: "W", sub: "testemunho" }, { valor: "R", texto: "R", sub: "revisão de registro" }] },
              { id: "responsavel", rotulo: "Executa / inspeciona", tipo: "select", obrigatorio: true, opcoes: lista(API.RESPONSAVEIS_PONTO) },
              { id: "criterio", rotulo: "Critério de aceitação", tipo: "texto", obrigatorio: true, max: 160, largura: "full" },
              { id: "referencia", rotulo: "Documento de referência", tipo: "texto", max: 60 }
            ] }
        ],
        aoSalvar: function (v) {
          return API.salvarItp({ projetoId: projetoId, titulo: v.titulo, disciplina: v.disciplina, empresaId: v.empresaId, pontos: v.pontos }, itp ? itp.codigo : null).then(function (r) {
            GI.ui.toast((itp ? "Revisão " + r.revisao + " de " : "ITP ") + r.codigo + " gravada. Registre a aprovação do cliente antes das inspeções.", "success", 6000);
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }

  function aprovarItp(itp, aoConcluir) {
    return GI.form.abrir({
      titulo: "Aprovação do cliente · " + itp.codigo, subtitulo: itp.titulo + " · Rev " + itp.revisao, tamanho: "sm", textoSalvar: "Registrar aprovação",
      campos: [
        { id: "referencia", rotulo: "Documento de aprovação", tipo: "texto", obrigatorio: true, max: 120, placeholder: "Ex.: carta, comentário de revisão ou ata" },
        { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: REF, maxData: REF }
      ],
      aoSalvar: function (v) { return API.aprovarItp(itp.codigo, v).then(function () { GI.ui.toast("ITP " + itp.codigo + " aprovado pelo cliente.", "success"); if (aoConcluir) aoConcluir(itp.codigo); }); }
    });
  }

  function verItp(itp) {
    var n = ++seq, corpo = document.createElement("div");
    corpo.innerHTML = '<div class="form-grid mb-4">' +
      campoInfo("Projeto", U.esc(itp.projetoCodigo)) + campoInfo("Disciplina", U.esc(itp.disciplina)) + campoInfo("Executante", U.esc(U.empresa(itp.empresaId))) +
      campoInfo("Revisão", "Rev " + itp.revisao + " · " + U.esc(F.data(itp.data))) +
      campoInfo("Aprovação do cliente", itp.aprovadoCliente ? U.badge("Aprovado", "success", true) + (itp.aprovacao ? " " + U.esc(itp.aprovacao.referencia) : "") : U.badge("Pendente", "warning", true)) +
      campoInfo("Inspeções", F.num(itp.inspecoes) + (itp.aprovacaoPct != null ? " · " + F.pct(itp.aprovacaoPct) + " aprovadas" : "")) +
      '</div><div id="t-itp-' + n + '"></div>';
    var m = GI.modal.create({ title: itp.codigo + " " + itp.titulo, subtitle: itp.totalPontos + " pontos · H " + itp.porTipo.H + " · W " + itp.porTipo.W + " · R " + itp.porTipo.R, size: "lg", body: corpo,
      buttons: [{ label: "Fechar", variant: "secondary" }] });
    GI.tabela.criar("t-itp-" + n, {
      porPagina: 0, compacta: true, legenda: "Pontos do ITP",
      colunas: [
        { id: "id", titulo: "Nº", tipo: "num" },
        { id: "atividade", titulo: "Atividade" },
        { id: "tipo", titulo: "Tipo", html: function (p) { return tipoPonto(p.tipo); } },
        { id: "criterio", titulo: "Critério de aceitação" },
        { id: "referencia", titulo: "Referência" },
        { id: "responsavel", titulo: "Executa / inspeciona" }
      ]
    }).atualizar(itp.pontos);
    GI.ui.init(m.el);
    return m;
  }

  function registrarInspecao(projetoId, itps, aoConcluir, pre) {
    if (projetoId == null) { U.noProjeto("inspecao", "Registrar inspeção"); return; }
    pre = pre || {};
    var aprovados = itps.filter(function (i) { return i.projetoId === projetoId && i.aprovadoCliente; });
    if (!aprovados.length) { GI.ui.toast("Nenhum ITP aprovado pelo cliente neste projeto.", "warning"); return; }
    var porId = {};
    aprovados.forEach(function (i) { porId[i.id] = i; });
    function opcoesPontos(itpId) {
      var i = porId[itpId];
      return i ? i.pontos.map(function (p) { return { valor: String(p.id), texto: p.id + ". " + p.atividade + " (" + p.tipo + ")" }; }) : [];
    }
    return pronto().then(function () {
      var m = GI.form.abrir({
        titulo: "Registrar inspeção", tamanho: "lg", textoSalvar: "Registrar",
        campos: [
          { id: "itpId", rotulo: "ITP", tipo: "select", obrigatorio: true, largura: "full", valor: pre.itpId ? String(pre.itpId) : "",
            opcoes: aprovados.map(function (i) { return { valor: String(i.id), texto: i.codigo + " · " + i.titulo + " (Rev " + i.revisao + ")" }; }) },
          { id: "pontoId", rotulo: "Ponto do ITP", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesPontos(pre.itpId) },
          { id: "pontoInfo", tipo: "info", html: "" },
          { id: "data", rotulo: "Data da inspeção", tipo: "data", obrigatorio: true, valor: REF, maxData: REF },
          { id: "inspetorId", rotulo: "Inspetor", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: "9" },
          { id: "notificacao", rotulo: "Notificação ao cliente", tipo: "data", maxData: REF, ajuda: "Pontos H e W: data em que o cliente foi convocado." },
          { id: "resultado", rotulo: "Resultado", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: [
            { valor: "Aprovado", texto: "Aprovado" }, { valor: "Aprovado com ressalva", texto: "Aprovado com ressalva", sub: "pendência menor registrada" },
            { valor: "Reprovado", texto: "Reprovado", sub: "abre RNC" }] },
          { id: "observacao", rotulo: "Ressalva ou motivo da reprovação", tipo: "textarea", obrigatorio: true, max: 500, linhas: 2, mostrarSe: function (v) { return v.resultado && v.resultado !== "Aprovado"; } },
          { id: "severidade", rotulo: "Severidade da RNC", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: lista(API.SEVERIDADES), mostrarSe: function (v) { return v.resultado === "Reprovado"; } },
          { id: "contencao", rotulo: "Contenção imediata", tipo: "textarea", obrigatorio: true, max: 400, linhas: 2, mostrarSe: function (v) { return v.resultado === "Reprovado"; } },
          { id: "evidencias", rotulo: "Registros (relatório, fotos, certificados)", tipo: "arquivo", multiplo: true, aceitar: ["pdf", "jpg", "jpeg", "png", "xlsx"] }
        ],
        aoMudar: function (v, ctx) {
          var sel = m && m.el ? m.el.querySelector("[id$='-pontoId']") : null;
          if (sel && sel.getAttribute("data-itp") !== String(v.itpId || "")) {
            sel.setAttribute("data-itp", String(v.itpId || ""));
            sel.innerHTML = U.opcoes(opcoesPontos(v.itpId), "", "Selecione...");
          }
          var i = porId[v.itpId], p = i && v.pontoId ? i.pontos.filter(function (x) { return String(x.id) === String(v.pontoId); })[0] : null;
          ctx.info("pontoInfo", p ? '<span class="text-small">' + tipoPonto(p.tipo) + " " + U.esc(NOME_PONTO[p.tipo]) + " · <b>Critério</b>: " + U.esc(p.criterio) + (p.referencia ? " · " + U.esc(p.referencia) : "") + "</span>" : "");
        },
        aoSalvar: function (v) {
          return API.registrarInspecao(v).then(function (r) {
            GI.ui.toast("Inspeção " + r.codigo + " registrada." + (r.rnc ? " " + r.rnc + " aberta." : ""), r.rnc ? "warning" : "success", 6000);
            (r.avisos || []).forEach(function (a) { GI.ui.toast(a, "info", 7000); });
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
      var selPonto = m.el.querySelector("[id$='-pontoId']");
      if (selPonto) selPonto.setAttribute("data-itp", pre.itpId ? String(pre.itpId) : "");
      return m;
    });
  }

  /* ======================================================================
     Auditorias
     ====================================================================== */
  function planejarAuditoria(projetoId, a, aoConcluir) {
    if (!a && projetoId == null) { U.noProjeto("nova", "Planejar auditoria"); return; }
    return GI.form.abrir({
      titulo: a ? "Reprogramar auditoria · " + a.codigo : "Planejar auditoria", tamanho: "lg",
      campos: [
        { id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, largura: "full", valor: a ? a.tipo : "", opcoes: [
          { valor: "Contratada", texto: "Contratada", sub: "segunda parte, na obra" }, { valor: "Fornecedor", texto: "Fornecedor", sub: "na fábrica" }, { valor: "Interna", texto: "Interna", sub: "processos da gerenciadora" }] },
        { id: "auditadoId", rotulo: "Auditado", tipo: "select", obrigatorio: true, opcoes: empresas(), valor: a ? String(a.auditadoId) : "" },
        { id: "auditorId", rotulo: "Auditor líder", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: a ? String(a.auditorId) : "9" },
        { id: "escopo", rotulo: "Escopo", tipo: "texto", obrigatorio: true, max: 160, largura: "full", valor: a ? a.escopo : "" },
        { id: "criterio", rotulo: "Critérios", tipo: "texto", obrigatorio: true, max: 160, largura: "full", valor: a ? a.criterio || "" : "", placeholder: "Normas, procedimentos e cláusulas contratuais" },
        { id: "data", rotulo: "Data planejada", tipo: "data", obrigatorio: true, valor: a ? a.data : "" },
        { id: "justificativa", rotulo: "Justificativa da reprogramação", tipo: "textarea", max: 300, mostrarSe: function (v) { return !!a && v.data !== a.data; } }
      ],
      aoSalvar: function (v) {
        return API.salvarAuditoria(Object.assign({ projetoId: projetoId }, v), a ? a.codigo : null).then(function (r) {
          GI.ui.toast(a ? (r.reprogramada ? "Auditoria reprogramada." : "Auditoria atualizada.") : "Auditoria " + r.codigo + " planejada.", "success");
          if (aoConcluir) aoConcluir(r.codigo);
        });
      }
    });
  }

  function registrarResultado(a, aoConcluir) {
    return GI.form.abrir({
      titulo: "Resultado da auditoria · " + a.codigo, subtitulo: a.escopo + " · " + U.empresa(a.auditadoId), tamanho: "xl", textoSalvar: "Registrar resultado",
      intro: '<p class="text-small text-muted mb-4">Cada constatação do tipo Não conformidade abre uma RNC (origem Auditoria) com o prazo da severidade.</p>',
      campos: [
        { id: "data", rotulo: "Data de realização", tipo: "data", obrigatorio: true, valor: a.data <= REF ? a.data : REF, maxData: REF },
        { id: "itensVerificados", rotulo: "Itens verificados", tipo: "numero", obrigatorio: true, min: 1, maxNumero: 500 },
        { id: "itensConformes", rotulo: "Itens conformes", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 500 },
        { id: "conformidade", tipo: "info", html: "" },
        { id: "constatacoes", rotulo: "Constatações", tipo: "repetir", rotuloItem: "Constatação", textoAdicionar: "Adicionar constatação", maximo: 30, valor: [],
          vazio: "Nenhuma constatação. Use o botão abaixo para incluir.",
          itens: [
            { id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: lista(API.TIPOS_CONSTATACAO) },
            { id: "descricao", rotulo: "Descrição", tipo: "textarea", obrigatorio: true, linhas: 2, max: 400 },
            { id: "requisito", rotulo: "Requisito", tipo: "texto", max: 80, placeholder: "Norma, procedimento ou cláusula" },
            { id: "disciplina", rotulo: "Disciplina (RNC)", tipo: "select", opcoes: lista(API.DISCIPLINAS) },
            { id: "severidade", rotulo: "Severidade (RNC)", tipo: "select", opcoes: lista(API.SEVERIDADES) }
          ] },
        { id: "resumo", rotulo: "Conclusão da auditoria", tipo: "textarea", max: 600 }
      ],
      aoMudar: function (v, ctx) {
        var ok = v.itensVerificados > 0 && v.itensConformes >= 0 && v.itensConformes <= v.itensVerificados;
        ctx.info("conformidade", ok ? '<span class="text-small">Conformidade: <b>' + U.esc(F.pct(v.itensConformes / v.itensVerificados * 100)) + "</b> (meta " +
          U.esc(F.pct(param ? param.metaConformidadeAuditoriaPct : 90, 0)) + ")</span>" : "");
      },
      aoSalvar: function (v) {
        return API.registrarResultado(a.codigo, v).then(function (r) {
          GI.ui.toast("Resultado registrado." + (r.rncs.length ? " " + U.plural(r.rncs.length, "RNC aberta", "RNCs abertas") + ": " + r.rncs.join(", ") + "." : ""), r.rncs.length ? "warning" : "success", 7000);
          if (aoConcluir) aoConcluir(a.codigo);
        });
      }
    });
  }

  function verAuditoria(a) {
    var n = ++seq, corpo = document.createElement("div");
    corpo.innerHTML = '<div class="form-grid mb-4">' +
      campoInfo("Situação", situacaoAuditoria(a)) + campoInfo("Projeto", U.esc(a.projetoCodigo)) + campoInfo("Tipo", U.esc(a.tipo)) +
      campoInfo("Auditado", U.esc(U.empresa(a.auditadoId))) + campoInfo("Auditor líder", U.esc(U.pessoa(a.auditorId))) +
      campoInfo("Data", U.esc(F.data(a.realizadaEm || a.data))) + campoInfo("Critérios", U.esc(a.criterio || "")) +
      (a.conformidadePct != null ? campoInfo("Conformidade", F.pct(a.conformidadePct) + " (" + F.num(a.itensConformes) + " de " + F.num(a.itensVerificados) + ")") : "") +
      "</div>" + (a.resumo ? "<p class=\"mb-4\">" + U.esc(a.resumo) + "</p>" : "") +
      ((a.reprogramacoes || []).length ? '<p class="text-small text-muted mb-4">Reprogramada: ' + a.reprogramacoes.map(function (x) { return U.esc(F.data(x.de) + " para " + F.data(x.para) + " (" + x.justificativa + ")"); }).join("; ") + "</p>" : "") +
      ((a.constatacoes || []).length ? '<h3 class="section-title">Constatações</h3><div id="t-aud-' + n + '"></div>' : "");
    var m = GI.modal.create({ title: a.codigo, subtitle: a.escopo, size: "lg", body: corpo, buttons: [{ label: "Fechar", variant: "secondary" }] });
    if ((a.constatacoes || []).length) {
      GI.tabela.criar("t-aud-" + n, {
        porPagina: 0, compacta: true, legenda: "Constatações",
        colunas: [
          { id: "tipo", titulo: "Tipo", html: function (c) { return U.badge(c.tipo, c.tipo === "Não conformidade" ? "danger" : c.tipo === "Observação" ? "warning" : "info"); } },
          { id: "descricao", titulo: "Descrição" },
          { id: "requisito", titulo: "Requisito" },
          { id: "rncRef", titulo: "RNC", html: function (c) { return c.rncRef ? '<a href="' + U.tela("qualidade", "rnc", { busca: c.rncRef }) + '">' + U.esc(c.rncRef) + "</a>" : ""; } }
        ]
      }).atualizar(a.constatacoes);
    }
    GI.ui.init(m.el);
    return m;
  }

  GI.qld = {
    pronto: pronto, projeto: projeto, erroApi: erroApi, pessoas: pessoas, empresas: empresas,
    situacaoRnc: situacaoRnc, severidade: severidade, resultado: resultado, tipoPonto: tipoPonto, situacaoAuditoria: situacaoAuditoria, NOME_PONTO: NOME_PONTO,
    novaRnc: novaRnc, atribuirAnalise: atribuirAnalise, registrarAnalise: registrarAnalise, novaAcao: novaAcao, enviarVerificacao: enviarVerificacao,
    verificarEficacia: verificarEficacia, cancelarRnc: cancelarRnc, atualizarCusto: atualizarCusto, verRnc: verRnc, acoesRnc: acoesRnc, executarAcaoRnc: executarAcaoRnc,
    editarItp: editarItp, aprovarItp: aprovarItp, verItp: verItp, registrarInspecao: registrarInspecao,
    planejarAuditoria: planejarAuditoria, registrarResultado: registrarResultado, verAuditoria: verAuditoria
  };
})(window.GI = window.GI || {});
