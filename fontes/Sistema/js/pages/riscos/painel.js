/* ==========================================================================
   Gestão de Riscos > Painel de riscos (mockup 04)
   Visão consolidada dos riscos do projeto (sistema de controle de um projeto):
   KPIs, exposição por categoria (RBS), evolução mensal e pauta de escalonamento
   ao gerente do projeto, com envio simulado por e-mail.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.rsk, API = GI.api.riscos;
  var projetoId = GI.api.projetoAtualId(), dados = null, tabela = null, riscos = [], contingencia = null;

  function escopo() {
    var pj = U.projeto(projetoId);
    return pj ? "Projeto " + pj.codigo + " " + pj.nome : "Portfólio de projetos";
  }
  function linkRegistro(extra) { return U.tela("riscos", "registro", extra || null); }

  /* Referências dos cards: severidade-alvo dos riscos ativos (meta da resposta) e
     saldo da contingência dividido pela cobertura mínima (limite da exposição). */
  function referencias(s) {
    var faixas = API.legenda(), porId = {};
    faixas.forEach(function (f, i) { porId[f.id] = { ordem: i, maximo: f.maximo }; });
    var ativos = riscos.filter(function (r) { return r.ativo; });
    function metaFaixa(id) { return ativos.filter(function (r) { return (r.severidadeAlvo || (r.sevAtual && r.sevAtual.id)) === id; }).length; }
    /* Redução mínima para levar cada ameaça avaliada até o teto da faixa-alvo */
    var metas = ativos.filter(function (r) { return r.natureza === "Ameaça" && r.scoreResidual != null && r.scoreInerente > 0 && r.severidadeAlvo && porId[r.severidadeAlvo]; })
      .map(function (r) { return Math.max(0, (r.scoreInerente - porId[r.severidadeAlvo].maximo) / r.scoreInerente); });
    var c = contingencia && contingencia.contingencia;
    return {
      topo: metaFaixa(s.topo.id), segunda: s.segunda ? metaFaixa(s.segunda.id) : null,
      reducaoPct: metas.length ? Math.round(metas.reduce(function (a, v) { return a + v; }, 0) / metas.length * 100) : null,
      limiteExposicao: c && contingencia.coberturaMinimaPct ? Math.round(c.saldo * 100 / contingencia.coberturaMinimaPct) : null
    };
  }

  function render() {
    var s = dados.resumo, ref = referencias(s);
    function k(o, extra) { var h = linkRegistro(extra); if (h) o.href = h; return U.kpi(o); }
    document.getElementById("kpis").innerHTML = [
      k({ rotulo: s.topo.nome + "s", valor: F.num(s.topo.total), icone: "alertTriangle", cor: s.topo.total ? "danger" : "success", esperado: { rotulo: "Meta", valor: F.num(ref.topo) },
        rodape: U.plural(s.topo.ameacas, "ameaça") + (s.topo.oportunidades ? " · " + U.plural(s.topo.oportunidades, "oportunidade") : "") }, { severidade: s.topo.id }),
      s.segunda ? k({ rotulo: s.segunda.nome + "s", valor: F.num(s.segunda.total), icone: "alertCircle", cor: s.segunda.total ? "warning" : "success", esperado: { rotulo: "Meta", valor: F.num(ref.segunda) },
        rodape: U.plural(s.segunda.ameacas, "ameaça") + (s.segunda.oportunidades ? " · " + U.plural(s.segunda.oportunidades, "oportunidade") : "") }, { severidade: s.segunda.id }) : "",
      U.kpi({ rotulo: "Exposição (VME)", moeda: s.exposicaoCentavos, icone: "money", cor: "primary",
        esperado: { rotulo: "Limite", valor: ref.limiteExposicao == null ? "·" : F.moedaCompacta(ref.limiteExposicao) }, rodape: "ameaças ativas; probabilidade média da faixa x impacto em custo" }),
      k({ rotulo: "Revisão vencida", valor: F.num(s.revisaoVencida), icone: "calendarClock", cor: s.revisaoVencida ? "danger" : "success", esperado: { rotulo: "Esperado", valor: "0" }, rodape: U.plural(s.ativos, "risco ativo", "riscos ativos") }, { revisao: "vencidas" }),
      U.kpi({ rotulo: "Redução média", valor: s.reducaoMediaPct == null ? "·" : F.num(s.reducaoMediaPct), unidade: s.reducaoMediaPct == null ? "" : "%", icone: "arrowDown", cor: "info",
        esperado: { rotulo: "Meta", valor: ref.reducaoPct == null ? "·" : "≥ " + F.pct(ref.reducaoPct, 0) },
        rodape: "inerente para residual, ameaças com avaliação residual" })
    ].join("");

    var max = dados.porCategoria.reduce(function (m, c) { return Math.max(m, c.score); }, 0) || 1;
    document.getElementById("categorias").innerHTML = dados.porCategoria.length ? '<ul class="mov">' + dados.porCategoria.map(function (c) {
      var h = linkRegistro({ categoria: c.grupo });
      var tag = h ? "a" : "div";
      return "<li><" + tag + ' class="mov__row"' + (h ? ' href="' + h + '"' : "") + ' title="' + U.esc(c.grupo + ": " + U.plural(c.riscos, "risco", "riscos") + ", VME " + F.moeda(c.vmeCentavos)) + '">' +
        '<span class="mov__id">' + U.esc(c.grupo) + '</span><span class="mov__trilho" aria-hidden="true"><span class="mov__barra" style="width:' + (c.score / max * 100) + '%"></span></span>' +
        '<span class="mov__val">' + c.score + '</span><span class="sr-only">score somado ' + c.score + ", " + U.plural(c.riscos, "risco", "riscos") + "</span></" + tag + "></li>";
    }).join("") + "</ul>" : U.vazio("Nenhuma ameaça ativa avaliada no projeto.", "pieChart");

    GI.charts.bar("g-evolucao", {
      labels: dados.evolucao.map(function (e) { return U.mesCurto(e.mes); }), ariaLabel: "Score residual somado das ameaças por mês",
      series: [{ label: "Score residual somado", data: dados.evolucao.map(function (e) { return e.score; }), color: "chart-1" }]
    });

    document.getElementById("sub-pauta").textContent = dados.pauta.length
      ? U.plural(dados.pauta.length, "risco exige", "riscos exigem") + " decisão do gerente do projeto: severidade fora do alvo perto do prazo, sem redução após o plano, plano aguardando aprovação, gatilho ocorrido ou revisão vencida"
      : "Nenhum risco exige decisão do gerente do projeto";
    tabela.atualizar(dados.pauta);
  }
  function carregar() {
    return Promise.all([API.painel({ projetoId: projetoId }), API.lista({ projetoId: projetoId }), GI.api.financeiro.contingencia(projetoId)])
      .then(function (r) { dados = r[0]; riscos = r[1] || []; contingencia = r[2]; render(); });
  }

  /* Enviar por e-mail: mesmo motor do follow-up da Central (simulado) */
  function enviar() {
    if (!dados.pauta.length) { GI.ui.toast("Pauta vazia: nada a enviar.", "info"); return; }
    var texto = "Prezados,\n\nSegue a pauta de escalonamento de riscos (" + escopo() + "), referência " + F.data(GI.api.referencia()) + ":\n\n" +
      dados.pauta.map(function (r) { return "* " + r.codigo + " " + r.titulo + ": residual " + r.scoreAtual + " " + r.sevAtual.nome + ". Motivo: " + r.pauta.join("; ") + ". Dono: " + U.pessoa(r.donoId) + "."; }).join("\n") +
      "\n\nSolicitamos decisão na próxima reunião de acompanhamento do projeto.\n\nPMO · Gestão Integrada AMT";
    /* Portfólio: gerentes dos projetos com risco na pauta */
    var ids = projetoId != null ? [projetoId] : dados.pauta.map(function (r) { return r.projetoId; }).filter(function (v, k, a) { return a.indexOf(v) === k; });
    var dest = ids.map(function (id) { var pj = U.projeto(id) || {}, ger = U.mapas.pessoas[pj.gerenteId]; return ger ? ger.nome + " <" + ger.email + ">" : ""; }).filter(Boolean).join("; ");
    var m = GI.modal.create({
      title: "Enviar pauta por e-mail", size: "lg",
      body: '<p class="text-small text-muted mb-4">Texto padrão de Configurações; no protótipo nenhum e-mail é enviado.</p>' +
        '<div class="form-grid"><div class="field field--full"><span class="field__label">' + (projetoId == null ? "Para (gerentes dos projetos)" : "Para (gerente do projeto)") + '</span><span class="text-small">' + U.esc(dest || "sem destinatário") + "</span></div>" +
        '<div class="field field--full"><label class="field__label" for="pauta-texto">Mensagem (prévia)</label><textarea class="textarea" id="pauta-texto" rows="12"></textarea></div></div>',
      buttons: [
        { label: "Cancelar", variant: "secondary" },
        { label: "Copiar texto", variant: "secondary", onClick: function () {
            var t = document.getElementById("pauta-texto").value;
            if (navigator.clipboard) navigator.clipboard.writeText(t).then(function () { GI.ui.toast("Texto copiado.", "success"); }, function () { GI.ui.toast("Não foi possível copiar.", "warning"); });
          } },
        { label: "Enviar", variant: "primary", onClick: function (api) {
            /* TODO: API POST /riscos/pauta/envio (motor de e-mail da Central) */
            api.close(); GI.ui.toast("Simulação: pauta preparada para o gerente do projeto. Nada foi enviado no protótipo.", "info", 6000);
          } }
      ]
    });
    m.el.querySelector("#pauta-texto").value = texto;
  }

  document.getElementById("btn-email").addEventListener("click", enviar);

  GI.exportar.registrar(function () {
    return {
      titulo: "Painel de riscos", subtitulo: escopo(), arquivo: "painel-de-riscos" + (projetoId == null ? "-portfolio" : ""),
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Exposição por categoria (RBS)", dados: {
          colunas: [{ titulo: "Categoria", tipo: "texto" }, { titulo: "Score residual somado", tipo: "num" }, { titulo: "Riscos", tipo: "num" }, { titulo: "VME", tipo: "moeda" }],
          bruto: dados.porCategoria.map(function (c) { return [c.grupo, c.score, c.riscos, c.vmeCentavos]; }),
          texto: dados.porCategoria.map(function (c) { return [c.grupo, String(c.score), String(c.riscos), F.moeda(c.vmeCentavos)]; }) } },
        { tipo: "grafico", titulo: "Evolução da exposição total", canvas: document.getElementById("g-evolucao") },
        { tipo: "tabela", titulo: "Pauta de escalonamento", dados: tabela.exportacao() }
      ]
    };
  });

  S.pronto().then(function () {
    document.getElementById("escopo").textContent = escopo();
    tabela = GI.tabela.criar("pauta", {
      porPagina: 10, legenda: "Pauta de escalonamento", vazio: "Nenhum risco na pauta.",
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº", classe: "nowrap", valor: function (r) { return r.codigo; }, html: function (r) { return S.linkFicha(r.codigo); } },
        { id: "titulo", titulo: "Risco", valor: function (r) { return r.titulo; },
          html: function (r) { return '<div class="cell-title"><b>' + U.esc(r.titulo) + "</b><small>" + U.esc(r.categoriaCompleta) + "</small></div>"; },
          exportar: function (r) { return r.titulo + " · " + r.categoria; } },
        { id: "residual", titulo: "Residual", tipo: "num", valor: function (r) { return r.scoreAtual; }, html: function (r) { return S.sev(r.sevAtual, r.scoreAtual, r.natureza); },
          exportar: function (r) { return r.scoreAtual + " " + (r.sevAtual ? r.sevAtual.nome : ""); } },
        { id: "motivo", titulo: "Motivo", valor: function (r) { return r.pauta.join(" · "); } },
        { id: "dono", titulo: "Dono", valor: function (r) { return U.pessoa(r.donoId); } }
      ]),
      ordem: { coluna: "residual", direcao: "desc" }
    });
    return carregar();
  });
})(window.GI = window.GI || {});
