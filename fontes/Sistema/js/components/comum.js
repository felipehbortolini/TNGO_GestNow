/* ==========================================================================
   comum.js | Utilitários das telas (GI.util). Sem acesso direto aos dados:
   nomes de pessoas e empresas vêm de GI.api.cadastros().

   GI.util.pronto()              -> Promise com os cadastros carregados (uma vez)
   GI.util.pessoa(id) / empresa(id) / projeto(id) / sistema(id)
   GI.util.esc(texto)            -> texto seguro para HTML
   GI.util.icone(nome)           -> SVG
   GI.util.badge(texto, tipo, dot)
   GI.util.kpi({...})            -> HTML de um KPI (filtro, link ou estático); moeda: centavos (R$ e escala menores), sinal: +/-
   GI.util.vazio(texto, icone)   -> HTML de estado vazio
   GI.util.param(nome)           -> parâmetro da URL (?id=3)
   GI.util.tela(modulo, tela, params) -> href relativo à raiz
   GI.util.opcoes(lista, selecionado, vazio) -> <option>s
   GI.util.statusAcao(chave)     -> tipo de badge do status da ação
   GI.util.escopo()              -> { portfolio, projetoId, projeto } do escopo atual (Portfólio ou projeto)
   GI.util.codigoProjeto(id) / colunaProjeto(campo) -> código do projeto / coluna "Projeto" das tabelas consolidadas
   GI.util.noProjeto(acao, titulo) -> no Portfólio, pede o projeto e reabre a tela no projeto com ?acao=
   GI.util.acaoPendente()        -> ?acao= da URL (lido uma vez e retirado da URL)
   GI.util.selosProjeto(ids)     -> etiquetas com os códigos dos projetos
   ========================================================================== */
(function (GI) {
  "use strict";

  var mapas = { pessoas: {}, empresas: {}, projetos: {}, sistemas: {} };
  var carregando = null;

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function icone(nome, tamanho) { return GI.icons ? GI.icons.svg(nome, tamanho ? { size: tamanho } : undefined) : ""; }

  function pronto() {
    if (!carregando) {
      carregando = GI.api.cadastros().then(function (c) {
        Object.keys(mapas).forEach(function (k) { (c[k] || []).forEach(function (x) { mapas[k][x.id] = x; }); });
        return c;
      });
    }
    return carregando;
  }
  function nome(mapa, id, campo) { var x = mapas[mapa][id]; return x ? x[campo || "nome"] : ""; }

  function badge(texto, tipo, dot) {
    return '<span class="badge badge--' + (tipo || "neutral") + (dot ? " badge--dot" : "") + '">' + esc(texto) + "</span>";
  }

  /* KPI: href = link; filtro = { valor, ativo } vira botão pílula que filtra; senão estático.
     esperado = { rotulo, valor } (ou [{...}, {...}]): referência logo abaixo do valor (previsto, meta,
     linha de base, orçado, limite ou esperado). Regra: todo card com valor informa a referência;
     sem referência aplicável, use { rotulo: "Referência", valor: "sem meta" } com o motivo no rodapé. */
  function esperadoHtml(e) {
    if (!e) return "";
    var l = Array.isArray(e) ? e : [e];
    return '<span class="kpi__esperado">' + l.filter(Boolean).map(function (x) {
      return '<span class="kpi__esperado-item"><span class="kpi__esperado-rot">' + esc(x.rotulo) + '</span> <b class="kpi__esperado-val">' + esc(x.valor == null || x.valor === "" ? "·" : x.valor) + "</b></span>";
    }).join("") + "</span>";
  }
  function kpi(o) {
    var tag = o.href ? "a" : "div";
    var cls = "kpi kpi--" + (o.cor || "primary") + (o.filtro ? " kpi--filter" + (o.filtro.ativo ? " is-active" : "") : "");
    var attrs = o.href ? ' href="' + o.href + '"' : "";
    var valor = o.valor == null || o.valor === "" ? "·" : o.valor;
    if (o.moeda != null) {
      var mp = GI.fmt.moedaPartes(o.moeda, o.sinal);
      valor = '<span class="kpi__unit kpi__unit--pre">' + esc(mp.moeda) + "</span>" + esc(mp.numero) + (mp.escala ? '<span class="kpi__unit">' + esc(mp.escala) + "</span>" : "");
    }
    var html = "<" + tag + ' class="' + cls + '"' + attrs + (o.id ? ' id="' + o.id + '"' : "") + ">" +
      (o.modulo ? '<span class="kpi__modulo">' + esc(o.modulo) + "</span>" : "") +
      '<span class="kpi__label">' + icone(o.icone || "gauge") + esc(o.rotulo) + "</span>" +
      '<span class="kpi__value">' + valor + (o.unidade ? '<span class="kpi__unit">' + esc(o.unidade) + "</span>" : "") + "</span>" +
      esperadoHtml(o.esperado) +
      (o.rodape ? '<span class="kpi__foot">' + o.rodape + "</span>" : "");
    if (o.filtro) {
      html += '<button type="button" class="btn btn--ghost btn--sm btn--stretch kpi__action" data-filtro="' + esc(o.filtro.valor) + '" aria-pressed="' +
        (o.filtro.ativo ? "true" : "false") + '">' + (o.filtro.ativo ? "Filtrando" : "Filtrar") + "</button>";
    }
    return html + "</" + tag + ">";
  }

  function vazio(texto, nomeIcone, titulo) {
    return '<div class="empty"><span class="empty__icon">' + icone(nomeIcone || "search") + "</span>" +
      (titulo ? '<span class="empty__title">' + esc(titulo) + "</span>" : "") + "<p>" + esc(texto) + "</p></div>";
  }

  function param(nomeParam) {
    try { return new URLSearchParams(window.location.search).get(nomeParam); } catch (e) { return null; }
  }
  function raiz() { return document.body.getAttribute("data-root") || ""; }
  function tela(modulo, nomeTela, params) {
    /* projeto: null/undefined = Portfólio */
    var q = params ? "?" + Object.keys(params).map(function (k) { var v = params[k]; if (k === "projeto" && v == null) v = "portfolio"; return encodeURIComponent(k) + "=" + encodeURIComponent(v); }).join("&") : "";
    return raiz() + "modulos/" + modulo + "/" + nomeTela + ".html" + q;
  }

  function opcoes(lista, selecionado, textoVazio) {
    var html = textoVazio != null ? '<option value="">' + esc(textoVazio) + "</option>" : "";
    return html + (lista || []).map(function (o) {
      var v = typeof o === "object" ? o.valor : o, t = typeof o === "object" ? o.texto : o;
      return '<option value="' + esc(v) + '"' + (String(v) === String(selecionado) ? " selected" : "") + ">" + esc(t) + "</option>";
    }).join("");
  }

  var TIPO_STATUS_ACAO = { atrasada: "danger", andamento: "info", concluida: "success", info: "purple" };
  function statusAcao(chave) { return TIPO_STATUS_ACAO[chave] || "neutral"; }

  /* Link para o registro de origem de uma ação */
  function linkOrigem(a) {
    var r = a.origemRef || "";
    if (a.origem === "Ata" && a.ataId) return tela("central-acoes", "ata", { id: a.ataId });
    if (a.origem === "Punch list") return tela("planejamento", "punch-list", { item: r });
    if (a.origem === "Risco") return tela("riscos", "ficha", { codigo: r });
    if (a.origem === "Contrato") return r.indexOf("CT-") === 0 ? tela("financeiro", "contrato", { numero: r }) : tela("financeiro", "contratos", { busca: r });
    if (a.origem === "Suprimentos") return tela("suprimentos", "diligenciamento", { busca: r });
    if (a.origem === "RNC") return tela("qualidade", "rnc", { busca: r });
    if (a.origem === "HSE") return /^(APR|HAZOP)-/.test(r) ? tela("hse", "analises-risco", { busca: r }) : tela("hse", "ocorrencias", { busca: r });
    if (a.origem === "Mudança") return tela("governanca", "mudanca", { codigo: r });
    if (a.origem === "Lição") return tela("governanca", "licoes", { busca: r });
    if (a.origem === "Produtividade") {
      var m = /^PRD-(\d{4}-S\d{2})-(\d+)$/.exec(r);
      return tela("planejamento", "produtividade", m ? { aba: "kpis", corte: m[1], empresa: Number(m[2]) } : { aba: "kpis" });
    }
    return null;
  }

  /* ---------------- Portfólio ---------------- */
  function escopo() {
    var id = GI.api.projetoAtualId();
    return { portfolio: id == null, projetoId: id, projeto: id == null ? null : mapas.projetos[id] || null };
  }
  function listaProjetos() { return Object.keys(mapas.projetos).map(function (k) { return mapas.projetos[k]; }).sort(function (a, b) { return a.id - b.id; }); }
  function codigoProjeto(id) { var p = mapas.projetos[id]; return p ? p.codigo : ""; }
  function colunaProjeto(campo, opcoes) {
    var c = campo || "projetoId";
    return Object.assign({ id: "projeto", titulo: "Projeto", classe: "nowrap",
      valor: function (x) { return codigoProjeto(x[c]); },
      html: function (x) { var p = mapas.projetos[x[c]]; return p ? '<span title="' + esc(p.nome) + '">' + esc(p.codigo) + "</span>" : ""; } }, opcoes || {});
  }
  function selosProjeto(ids) {
    return (ids || []).map(function (id) { var p = mapas.projetos[id]; return p ? badge(p.codigo, "outline") : ""; }).join(" ");
  }
  /* Cadastro no Portfólio: registros pertencem a um projeto. Pede o projeto e reabre a mesma tela
     no escopo do projeto escolhido, com ?acao= para a tela abrir o cadastro pedido. */
  function noProjeto(acao, titulo, params) {
    var lista = listaProjetos();
    var corpo = '<p class="text-small text-muted">Cada registro pertence a um projeto. A tela abre no projeto escolhido para continuar.</p>' +
      '<div class="radio-list mt-3" role="radiogroup" aria-label="Projeto">' + lista.map(function (p, k) {
        return '<label class="check"><input type="radio" name="escolha-projeto" value="' + p.id + '"' + (k === 0 ? " checked" : "") + "> " +
          '<span data-sem-traducao>' + esc(p.codigo + " · " + p.nome) + "</span></label>";
      }).join("") + "</div>";
    GI.modal.create({
      title: titulo || "Escolha o projeto", size: "sm", body: corpo,
      buttons: [{ label: "Cancelar", variant: "secondary" },
        { label: "Continuar", variant: "primary", onClick: function (api) {
          var sel = api.el.querySelector('input[name="escolha-projeto"]:checked');
          if (!sel) return false;
          GI.api.definirEscopo(Number(sel.value));
          var q = Object.assign({ projeto: sel.value }, acao ? { acao: acao } : {}, params || {});
          window.location.href = window.location.pathname + "?" + Object.keys(q).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(q[k]); }).join("&");
          return false;
        } }]
    });
  }
  var acaoLida = null, acaoConsumida = false;
  function acaoPendente() {
    if (acaoConsumida) return acaoLida;
    acaoConsumida = true;
    acaoLida = param("acao");
    if (acaoLida && window.history && window.history.replaceState) {
      try {
        var u = new URL(window.location.href); u.searchParams.delete("acao");
        window.history.replaceState(null, "", u.pathname + (u.search || "") + u.hash);
      } catch (e) { /* URL sem suporte: segue com a ação lida */ }
    }
    return acaoLida;
  }

  function debounce(fn, ms) {
    var t;
    return function () { var args = arguments, ctx = this; clearTimeout(t); t = setTimeout(function () { fn.apply(ctx, args); }, ms || 200); };
  }

  /* Normaliza texto para busca (sem acento, minúsculo) */
  function normalizar(t) {
    return String(t == null ? "" : t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function contem(texto, termo) { return !termo || normalizar(texto).indexOf(normalizar(termo)) >= 0; }

  function plural(n, singular, pluralTxt) { return GI.fmt.num(n) + " " + (n === 1 ? singular : (pluralTxt || singular + "s")); }

  /* Mês "2026-09" -> "set/26" */
  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function mesCurto(m) {
    if (!m) return "";
    var lista = GI.i18n && GI.i18n.idioma === "en" ? MONTHS : MESES;
    return lista[Number(m.slice(5, 7)) - 1] + "/" + m.slice(2, 4);
  }

  GI.util = {
    pronto: pronto,
    pessoa: function (id) { return nome("pessoas", id); },
    empresa: function (id) { return nome("empresas", id); },
    projeto: function (id) { return mapas.projetos[id] || null; },
    sistema: function (id) { return mapas.sistemas[id] || null; },
    mapas: mapas,
    esc: esc, icone: icone, badge: badge, kpi: kpi, kpiEsperado: esperadoHtml, vazio: vazio, param: param, raiz: raiz, tela: tela,
    opcoes: opcoes, statusAcao: statusAcao, linkOrigem: linkOrigem, debounce: debounce,
    escopo: escopo, listaProjetos: listaProjetos, codigoProjeto: codigoProjeto, colunaProjeto: colunaProjeto, selosProjeto: selosProjeto,
    noProjeto: noProjeto, acaoPendente: acaoPendente,
    normalizar: normalizar, contem: contem, plural: plural, mesCurto: mesCurto
  };
})(window.GI = window.GI || {});
