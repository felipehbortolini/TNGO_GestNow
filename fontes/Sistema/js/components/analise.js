/* ==========================================================================
   analise.js | Análise do período (GI.analise): comentário executivo e analítico
   por módulo (02 Planejamento, 03 Financeiro, 04 Suprimentos, 05 Riscos e 07 HSE),
   um registro por tipo (Semanal ou Mensal) e período, inserido e editado em modal.

   GI.analise.abrir(modulo, { tipo, periodo })  sem período: passo 1 (escolha do período);
                                                com período: passo 2 (texto e desvios).
   GI.analise.textoDesvio(desvio)  descrição numérica do desvio no idioma ativo (modal e relatório).
   GI.analise.valor(itemResumo)    formata um item do resumo do período.

   Botões: qualquer elemento com data-analise="<modulo>" abre o modal (ligação automática).
   URL: ?analise=1&tipo=&periodo= abre o modal ao carregar a tela (vindo do relatório gerencial).
   Ao gravar ou excluir, dispara o evento "analise:alterada" no document (detail: { modulo, tipo, periodo }).
   Regra: nos módulos 02, 03 e 04, todo desvio negativo detectado no período exige comentário
   próprio (causa, efeito e ação). A lista de desvios vem da api (mesmos dados do relatório).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  function API() { return GI.api.analises; }
  function projetoId() { return GI.api.projetoAtualId(); }
  function en() { return !!(GI.i18n && GI.i18n.idioma === "en"); }
  function t(pt, ing) { return en() ? ing : pt; }
  function erroApi(e) { GI.ui.toast((e && e.erros ? e.erros.map(function (x) { return x.msg || x; }).join(" ") : String(e)), "warning", 7000); }

  /* ---------------- Formatação ---------------- */
  function sinalNum(v, casas) { return (v > 0 ? "+" : "") + F.num(v, casas); }
  function pp(v, sinal) { return (sinal ? sinalNum(v, 1) : F.num(v, 1)) + t(" p.p.", " pp"); }
  function moeda(c, sinal) { return (sinal && c > 0 ? "+" : "") + F.moedaCompacta(c); }
  function dias(n) { return sinalNum(n, 0) + t(" d", " d"); }
  var PROD = {
    spi: ["SPI de quantidades", "Quantity SPI"],
    pf: ["Fator de produtividade", "Productivity factor"],
    aderencia: ["Aderência semanal", "Weekly adherence"],
    trabalhando: ["Pessoas trabalhando", "People working"],
    utilizacao: ["Utilização da jornada", "Shift utilization"]
  };

  function textoDesvio(x) {
    var d = x.dados || {};
    function lista(itens, fn) { return itens.map(fn).join("; "); }
    switch (x.chave) {
      case "avanco":
        return t("Real ", "Actual ") + F.pct(d.real) + t(" x previsto ", " vs planned ") + F.pct(d.previsto) + " (" + pp(d.desvio, true) + "; SPI " + F.indice(d.spi) + ")";
      case "avanco_periodo":
        return t("No período: real ", "In the period: actual ") + pp(d.real) + t(" x previsto ", " vs planned ") + pp(d.previsto) + " (" + pp(d.real - d.previsto, true) + ")";
      case "termino":
        return t("Tendência ", "Trend ") + U.mesCurto(d.tendencia) + t(" x linha de base ", " vs baseline ") + U.mesCurto(d.baseline);
      case "areas":
        return lista(d.itens, function (a) { return a.area + " " + pp(a.desvio, true); });
      case "produtividade":
        return lista(d.itens, function (i) {
          var n = PROD[i.chave] ? PROD[i.chave][en() ? 1 : 0] : i.chave;
          var pct = i.chave === "aderencia" || i.chave === "trabalhando" || i.chave === "utilizacao";
          var v = pct ? F.pct(i.valor) : F.indice(i.valor), m = pct ? F.pct(i.meta, 0) : F.indice(i.meta);
          return n + " " + v + " (" + t("meta ", "target ") + (i.chave === "pf" ? "≤ " : "") + m + ")";
        }) + t(" · últimas ", " · last ") + d.semanas + t(" semanas", " weeks");
      case "cpi":
        return "CPI " + F.indice(d.cpi) + " · CV " + moeda(d.cv) + " (EV " + moeda(d.ev) + " x AC " + moeda(d.ac) + ")";
      case "spi_custo":
        return t("SPI de custo ", "Cost SPI ") + F.indice(d.spi) + " · SV " + moeda(d.sv);
      case "vac":
        return t("Projeção ", "Forecast ") + moeda(d.projecao) + t(" x orçamento ", " vs budget ") + moeda(d.bac) + " (VAC " + moeda(d.vac) + "; " + sinalNum(d.pct, 1) + "%)";
      case "pacotes":
        return lista(d.itens, function (p) { return p.codigo + " " + p.descricao + " " + moeda(p.desvio, true) + " (" + sinalNum(p.pct, 1) + "%)"; });
      case "aderencia":
        return F.num(d.adjudicados) + t(" de ", " of ") + F.num(d.planejados) + t(" pacotes adjudicados até o corte (", " packages awarded up to the cut-off (") + F.pct(d.pct) + ")";
      case "otd":
        return F.num(d.noPrazo) + t(" de ", " of ") + F.num(d.total) + t(" entregas no prazo (", " deliveries on time (") + F.pct(d.pct) + ")";
      case "criticos":
        return lista(d.itens, function (c) { return c.numero + " " + c.descricao + " (" + t("folga ", "float ") + dias(c.folga) + ")"; });
      case "rnc_vencidas":
        return lista(d.itens, function (r) { return r.codigo + " (" + dias(r.dias) + ")"; });
      case "aprovacao_inspecao":
        return F.pct(d.pct) + t(" (meta ", " (target ") + F.pct(d.meta, 0) + ") · " + F.num(d.reprovadas) + (d.reprovadas === 1 ? t(" reprovada em ", " rejected out of ") : t(" reprovadas em ", " rejected out of ")) + F.num(d.total);
      case "conformidade_auditoria":
        return F.pct(d.pct) + t(" (meta ", " (target ") + F.pct(d.meta, 0) + ")";
      case "auditorias_atrasadas":
        return lista(d.itens, function (a) { return a.codigo + " (" + dias(a.dias) + ")"; });
      case "marcos_atrasados":
        return lista(d.itens, function (e) { return e.codigo + " " + (en() && GI.t ? GI.t(e.marco) : e.marco) + " (" + dias(e.dias) + ")"; });
    }
    return "";
  }
  function valor(r) {
    var v = r.valor;
    if (v == null || v === "" || (typeof v === "number" && isNaN(v))) return "·";
    switch (r.tipo) {
      case "pct": return F.pct(v);
      case "indice": return F.indice(v);
      case "moeda": return F.moedaCompacta(v);
      case "mes": return U.mesCurto(v);
      case "pp": return pp(v);
      case "num2": return F.num(v, 2);
    }
    return F.num(v);
  }
  function quando(iso) { return iso ? F.data(iso.slice(0, 10)) + " " + iso.slice(11, 16) : ""; }
  function avisar(modulo, tipo, periodo) {
    var ev;
    try { ev = new CustomEvent("analise:alterada", { detail: { modulo: modulo, tipo: tipo, periodo: periodo } }); }
    catch (e) { ev = document.createEvent("CustomEvent"); ev.initCustomEvent("analise:alterada", false, false, { modulo: modulo, tipo: tipo, periodo: periodo }); }
    document.dispatchEvent(ev);
  }

  /* ---------------- Passo 1: tipo e período ---------------- */
  function opcoes(lista, atual) {
    return lista.map(function (p) {
      var sit = p.analiseId ? "análise registrada" : p.emAndamento ? "em andamento" : "pendente";
      return '<option value="' + U.esc(p.periodo) + '"' + (p.periodo === atual ? " selected" : "") + ">" + U.esc(p.rotulo + " (" + sit + ")") + "</option>";
    }).join("");
  }
  function escolher(modulo, o) {
    o = o || {};
    var A = API(), nome = A.MODULOS[modulo];
    return Promise.all([A.periodos(projetoId(), modulo, "Semanal"), A.periodos(projetoId(), modulo, "Mensal")]).then(function (r) {
      var per = { Semanal: r[0], Mensal: r[1] };
      var tipoIni = o.tipo && per[o.tipo] ? o.tipo : "Semanal";
      function padrao(tipo) { return GI.api.periodoPadraoRelatorio(tipo); }
      var periodoIni = o.periodo || padrao(tipoIni), ultimoTipo = tipoIni;
      var m = GI.form.abrir({
        titulo: "Análise do período", subtitulo: nome, textoSalvar: "Continuar",
        intro: '<p class="text-small text-muted">Escolha o tipo e o período. Semanal e mensal são registros distintos; o texto alimenta a página do módulo no relatório gerencial (Início).</p>',
        campos: [
          { id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, valor: tipoIni, opcoes: A.TIPOS.map(function (x) { return { valor: x, texto: x, sub: x === "Semanal" ? "semana ISO, segunda a domingo" : "mês civil" }; }) },
          { id: "periodo", rotulo: "Período", tipo: "select", obrigatorio: true, opcoes: [], valor: periodoIni }
        ],
        aoMudar: function (v) {
          if (!m) return;
          var sel = m.el.querySelector('[data-campo="periodo"] select');
          if (sel && v.tipo && v.tipo !== ultimoTipo) { ultimoTipo = v.tipo; sel.innerHTML = opcoes(per[v.tipo], padrao(v.tipo)); }
        },
        aoSalvar: function (v) { setTimeout(function () { editar(modulo, v.tipo, v.periodo); }, 0); return true; }
      });
      var sel = m.el.querySelector('[data-campo="periodo"] select');
      if (sel) sel.innerHTML = opcoes(per[tipoIni], periodoIni);
      return m;
    }).catch(erroApi);
  }

  /* ---------------- Passo 2: análise e comentários dos desvios ---------------- */
  function introHtml(x) {
    var A = API();
    var resumo = x.resumo.length ? '<div class="analise-resumo" role="list" aria-label="Indicadores do período">' + x.resumo.map(function (r) {
      return '<div class="analise-resumo__item" role="listitem"><span>' + U.esc(r.rotulo) + "</span><b>" + U.esc(valor(r)) + "</b></div>";
    }).join("") + "</div>" : (x.modulo === "financeiro" ? '<p class="text-small text-muted">Sem fechamento mensal de custos até o corte deste período.</p>' : "");
    var desvios = "";
    if (x.obrigatorio) {
      desvios = x.desvios.length
        ? '<div class="alert alert--warning mt-3">' + U.icone("alertTriangle") + '<div class="alert__body">' + U.esc(U.plural(x.desvios.length, "desvio negativo", "desvios negativos")) +
          " no período. Todo desvio negativo exige comentário próprio (causa, efeito e ação), com ao menos " + A.LIMITES.minimoDesvio + " caracteres.</div></div>"
        : '<p class="text-small text-muted mt-3">Nenhum desvio negativo detectado no período.</p>';
    }
    return resumo +
      '<p class="text-small text-muted mt-3">Texto executivo e analítico: panorama do projeto, desempenho dos períodos anteriores, causas dos desvios e tendência para os próximos períodos.</p>' +
      desvios +
      (x.registro ? '<p class="text-small text-muted mt-2">Atualizada em ' + U.esc(quando(x.registro.atualizadoEm)) + " por " + U.esc(U.pessoa(x.registro.atualizadoPorId)) + ".</p>" : "");
  }
  function editar(modulo, tipo, periodo) {
    var A = API();
    return A.periodo(projetoId(), modulo, tipo, periodo).then(function (x) {
      var novo = !x.registro;
      if (!A.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar a análise do período.", "warning"); return; }
      var campos = [
        { id: "analise", rotulo: "Análise do período", tipo: "textarea", obrigatorio: true, linhas: 9, max: A.LIMITES.maximo, valor: x.registro ? x.registro.analise : "",
          placeholder: "Panorama, desempenho dos períodos anteriores, causas e tendência para os próximos períodos",
          ajuda: "Mínimo de " + A.LIMITES.minimo + " caracteres." }
      ];
      x.desvios.forEach(function (d, k) {
        campos.push({ id: "desvio_" + k, rotulo: d.indicador, tipo: "textarea", obrigatorio: x.obrigatorio, linhas: 2, max: A.LIMITES.maximoDesvio, valor: d.comentario || "",
          antes: '<p class="analise-desvio">' + U.icone("arrowDown") + "<span>" + U.esc(textoDesvio(d)) + "</span></p>",
          placeholder: "Causa, efeito e ação" });
      });
      var extras = [{ texto: "Trocar período", variante: "ghost", acao: function (ctx) { ctx.fechar(); escolher(modulo, { tipo: tipo, periodo: periodo }); } }];
      if (x.anterior) extras.push({ texto: "Copiar do período anterior", variante: "ghost", acao: function (ctx) {
        ctx.definir({ analise: x.anterior.analise });
        GI.ui.toast("Texto de " + x.anterior.rotulo + " copiado para revisão. Atualize os números e a tendência.", "info", 6000);
      } });
      if (!novo && A.pode("Gestor")) extras.push({ texto: "Excluir", variante: "ghost", acao: function (ctx) {
        GI.modal.confirm({ title: "Excluir análise", message: "Excluir a análise de " + x.info.rotulo + "? O período volta a ficar pendente no relatório gerencial.", okText: "Excluir", danger: true }).then(function (ok) {
          if (!ok) return;
          A.excluir(x.registro.id).then(function () { ctx.fechar(); GI.ui.toast("Análise excluída.", "success"); avisar(modulo, tipo, periodo); }).catch(erroApi);
        });
      } });
      return GI.form.abrir({
        titulo: (novo ? "Registrar análise " : "Editar análise ") + (tipo === "Mensal" ? "mensal" : "semanal"), subtitulo: x.nomeModulo + " · " + x.info.rotulo + (x.info.emAndamento ? " (em andamento)" : ""),
        tamanho: "lg", textoSalvar: novo ? "Registrar análise" : "Salvar alterações",
        intro: introHtml(x), campos: campos, extras: extras,
        validar: function (v) {
          var e = [], n = String(v.analise || "").trim().length;
          if (n && n < A.LIMITES.minimo) e.push({ campo: "analise", msg: "A análise deve ter ao menos " + A.LIMITES.minimo + " caracteres: panorama, desempenho dos períodos anteriores, causas e tendência." });
          if (x.obrigatorio) x.desvios.forEach(function (d, k) {
            var c = String(v["desvio_" + k] || "").trim().length;
            if (c && c < A.LIMITES.minimoDesvio) e.push({ campo: "desvio_" + k, msg: "Todo desvio negativo exige comentário (mínimo de " + A.LIMITES.minimoDesvio + " caracteres): causa, efeito e ação." });
          });
          return e;
        },
        aoSalvar: function (v) {
          var coment = {};
          x.desvios.forEach(function (d, k) { coment[d.chave] = v["desvio_" + k] || ""; });
          return A.salvar(projetoId(), modulo, { tipo: tipo, periodo: periodo, analise: v.analise, desvios: coment }).then(function (r) {
            GI.ui.toast("Análise " + (tipo === "Mensal" ? "mensal" : "semanal") + " de " + r.rotulo + (novo ? " registrada." : " atualizada."), "success");
            avisar(modulo, tipo, periodo);
          });
        }
      });
    }).catch(erroApi);
  }

  function abrir(modulo, o) {
    o = o || {};
    if (!GI.api.analises || !GI.api.analises.MODULOS[modulo]) return Promise.resolve(null);
    if (o.tipo && o.periodo) return editar(modulo, o.tipo, o.periodo);
    return escolher(modulo, o);
  }

  /* Ligação automática dos botões e abertura pela URL */
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-analise]");
    if (!b) return;
    ev.preventDefault();
    abrir(b.getAttribute("data-analise"));
  });
  if (U && U.pronto) U.pronto().then(function () {
    if (U.param("analise") !== "1") return;
    var b = document.querySelector("[data-analise]");
    if (b) abrir(b.getAttribute("data-analise"), { tipo: U.param("tipo"), periodo: U.param("periodo") });
  });

  GI.analise = { abrir: abrir, textoDesvio: textoDesvio, valor: valor };
})(window.GI = window.GI || {});
