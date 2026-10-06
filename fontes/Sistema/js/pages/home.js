/* ==========================================================================
   home.js | Início: contexto do projeto ou do portfólio, um indicador-chave por
   módulo, carteira de projetos com a ponderação (só no Portfólio), pontos de
   atenção, acesso aos módulos e emissão do relatório gerencial (modal: escopo
   Portfólio ou projeto, tipo semanal ou mensal, período e seções).
   Dados só via GI.api.resumoHome() e GI.api.planejamento.periodosRelato().
   URL: ?relatorio=1&tipo=&periodo=&escopo= reabre o modal (vindo do relatório).
   ========================================================================== */
(function (GI) {
  "use strict";

  var F = GI.fmt;
  var RAIZ = document.body.getAttribute("data-root") || "";

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function icone(nome) { return GI.icons.svg(nome); }
  function tela(modulo, item, params) {
    var q = params ? "?" + Object.keys(params).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(params[k]); }).join("&") : "";
    return RAIZ + "modulos/" + modulo + "/" + item + ".html" + q;
  }

  /* Índices de desempenho: 1 ou mais = no plano; 0,95 a 0,99 = atenção; abaixo = crítico */
  function classeIndice(v) { return v == null ? "info" : v >= 1 ? "success" : v >= 0.95 ? "warning" : "danger"; }
  function delta(atual, anterior) {
    if (atual == null || anterior == null) return "";
    var d = Math.round((atual - anterior) * 100) / 100;
    if (d === 0) return '<span class="kpi__delta kpi__delta--flat">estável</span>';
    var sobe = d > 0;
    return '<span class="kpi__delta kpi__delta--' + (sobe ? "up" : "down") + '">' + icone(sobe ? "arrowUp" : "arrowDown") +
      F.indice(Math.abs(d)) + "</span>";
  }

  function kpi(o) {
    return '<a class="kpi kpi--' + o.cor + '" href="' + o.href + '">' +
      '<span class="kpi__modulo">' + esc(o.modulo) + "</span>" +
      '<span class="kpi__label">' + icone(o.icone) + esc(o.rotulo) + "</span>" +
      '<span class="kpi__value">' + o.valor + "</span>" + GI.util.kpiEsperado(o.esperado) +
      '<span class="kpi__foot">' + o.rodape + "</span></a>";
  }

  function renderKpis(r) {
    var m = r.modulos;
    var ac = m["central-acoes"], fis = m.planejamento.fisico, custo = m.financeiro.custo;
    var sup = m.suprimentos, rsk = m.riscos, q = m.qualidade, hse = m.hse, gov = m.governanca;
    var Z = { rotulo: "Esperado", valor: "0" }, IDX = { rotulo: "Meta", valor: "≥ " + F.indice(1) };
    var inicios = (r.portfolio ? GI.util.listaProjetos() : [r.projeto || {}]).map(function (p) { return p.inicio; }).filter(Boolean).sort();
    var diasDesdeInicio = inicios.length ? Math.round((new Date(r.referencia + "T00:00:00") - new Date(inicios[0] + "T00:00:00")) / 86400000) : null;
    var desvioProj = custo ? Math.round((custo.projecaoTermino - custo.bac) / custo.bac * 1000) / 10 : null;

    var tiles = [
      { modulo: "01 Central de Ações", icone: "actions", rotulo: "Ações atrasadas", cor: ac.atrasadas ? "danger" : "success",
        href: tela("central-acoes", "acoes"), valor: F.num(ac.atrasadas),
        esperado: Z, rodape: "de " + F.num(ac.emAndamento) + " ações em aberto" },
      { modulo: "02 Planejamento", icone: "curve", rotulo: r.portfolio ? "SPI ponderado da carteira" : "SPI (desempenho de prazo)", cor: classeIndice(fis && fis.spi),
        href: tela("planejamento", "kpis"), valor: fis ? F.indice(fis.spi) : "sem dados", esperado: IDX,
        rodape: fis ? delta(fis.spi, fis.anterior && fis.anterior.spi) + "real " + F.pct(fis.real) + " x previsto " + F.pct(fis.previsto) : "" },
      { modulo: "03 Gestão Financeira", icone: "money", rotulo: r.portfolio ? "CPI da carteira" : "CPI (desempenho de custo)", cor: classeIndice(custo && custo.atual && custo.atual.cpi),
        href: tela("financeiro", "kpis"), valor: custo && custo.atual ? F.indice(custo.atual.cpi) : "sem dados", esperado: IDX,
        rodape: custo ? delta(custo.atual.cpi, custo.anterior && custo.anterior.cpi) + "projeção " + F.moedaCompacta(custo.projecaoTermino) +
          " (" + (desvioProj > 0 ? "+" : "") + F.pct(desvioProj) + ")" : "" },
      { modulo: "04 Suprimentos", icone: "truck", rotulo: "Pedidos críticos", cor: sup.pedidosCriticos ? "danger" : "success",
        href: tela("suprimentos", "diligenciamento"), valor: F.num(sup.pedidosCriticos), esperado: Z,
        rodape: "folga negativa em relação ao ROS · " + F.num(sup.lliCriticos) + " de longo prazo" },
      { modulo: "05 Gestão de Riscos", icone: "alertTriangle", rotulo: "Riscos " + rsk.topo.nome.toLowerCase() + "s", cor: rsk.topo.total ? "danger" : "success",
        href: tela("riscos", "registro"), valor: F.num(rsk.topo.total), esperado: Z,
        rodape: (rsk.segunda ? F.num(rsk.segunda.total) + " " + rsk.segunda.nome.toLowerCase() + " · " : "") + "exposição " + F.moedaCompacta(rsk.exposicaoCentavos) },
      { modulo: "06 Gestão da Qualidade", icone: "octagonAlert", rotulo: "Não conformidades abertas", cor: q.rncVencidas ? "danger" : q.rncAbertas ? "warning" : "success",
        href: tela("qualidade", "rnc"), valor: F.num(q.rncAbertas), esperado: { rotulo: "Limite", valor: "0 vencidas" },
        rodape: F.num(q.rncVencidas) + " vencida" + (q.rncVencidas === 1 ? "" : "s") + " · inspeções aprovadas " + F.pct(q.aprovacaoInspecoesPct) },
      { modulo: "07 HSE", icone: "hardHat", rotulo: "Dias sem acidente com afastamento", cor: hse.hipoMes ? "warning" : "success",
        href: tela("hse", "painel"), valor: hse.diasSemAfastamento == null ? "sem registro" : F.num(hse.diasSemAfastamento),
        esperado: { rotulo: "Esperado", valor: diasDesdeInicio == null ? "·" : F.num(diasDesdeInicio) },
        rodape: "TF " + F.num(hse.tf, 2) + (hse.hipoMes ? ' <span class="badge badge--danger">' + icone("alertTriangle") + F.num(hse.hipoMes) + " HiPo no mês</span>" : "") },
      { modulo: "08 Governança", icone: "swap", rotulo: "Mudanças aguardando comitê", cor: gov.aguardandoComite ? "info" : "success",
        href: tela("governanca", "mudancas", { situacao: "Aguardando comitê" }), valor: F.num(gov.aguardandoComite), esperado: Z,
        rodape: F.moedaCompacta(gov.valorAprovadoCentavos) + " aprovados (" + F.pct(gov.valorAprovadoPct) + (r.portfolio ? " do orçamento da carteira)" : " do orçamento)") }
    ];
    document.getElementById("home-kpis").innerHTML = tiles.map(kpi).join("");
  }

  var DESTINO_ALERTA = {
    "central-acoes": "acoes", planejamento: "punch-list", financeiro: "contratos",
    suprimentos: "diligenciamento", riscos: "registro", qualidade: "rnc", hse: "ocorrencias", governanca: "mudancas"
  };
  function renderAlertas(r) {
    var lista = document.getElementById("home-alertas");
    var total = document.getElementById("home-alertas-total");
    if (!r.alertas.length) {
      total.hidden = true;
      lista.innerHTML = '<li class="empty"><span class="empty__icon">' + icone("checkCircle") + "</span>Nenhum ponto de atenção na data de referência.</li>";
      return;
    }
    total.textContent = r.alertas.length + (r.alertas.length === 1 ? " item" : " itens");
    lista.innerHTML = r.alertas.map(function (a) {
      var href = a.destino ? tela(a.modulo, a.destino.tela, a.destino.params) : tela(a.modulo, DESTINO_ALERTA[a.modulo] || "");
      return '<li class="feed__item feed__item--' + a.nivel + '">' +
        '<span class="feed__icon" aria-hidden="true">' + icone(a.nivel === "danger" ? "alertTriangle" : "alertCircle") + "</span>" +
        '<div class="feed__body"><span class="feed__title">' + esc(a.titulo) + '</span><span class="feed__detail">' + esc(a.detalhe) + "</span></div>" +
        '<a class="btn btn--ghost btn--icon btn--sm" href="' + href + '" aria-label="Abrir: ' + esc(a.titulo) + '">' + icone("chevronRight") + "</a></li>";
    }).join("");
  }

  var TEXTO_MODULO = {
    "central-acoes": "Ações de todas as origens, atas e dashboards.",
    planejamento: "EAP, Curva S, KPIs, 6WLA, programação semanal, produtividade e punch list.",
    financeiro: "EAC, mapa de controle, desembolso, Curva S e contratos.",
    suprimentos: "Plano de compras, RFx, diligenciamento e fornecedores.",
    riscos: "Registro, matriz P x I, ficha e painel de riscos.",
    qualidade: "Não conformidades, inspeções e ITP, auditorias.",
    hse: "Ocorrências, pirâmide de segurança, inspeções e HHT.",
    governanca: "Gestão de mudanças e lições aprendidas."
  };
  var ACENTO = {
    "central-acoes": "--module-central", planejamento: "--module-planejamento", financeiro: "--module-financeiro",
    suprimentos: "--module-suprimentos", riscos: "--module-riscos", qualidade: "--module-qualidade", hse: "--module-hse", governanca: "--module-governanca"
  };
  function selo(texto, tipo) { return '<span class="badge badge--' + tipo + ' badge--dot">' + esc(texto) + "</span>"; }
  function selosModulo(id, m) {
    switch (id) {
      case "central-acoes": return selo(m["central-acoes"].atrasadas + " atrasadas", m["central-acoes"].atrasadas ? "danger" : "success");
      case "planejamento": return selo(m.planejamento.punch.abertosA + " itens A abertos", m.planejamento.punch.abertosA ? "warning" : "success");
      case "financeiro": return selo(m.financeiro.contratos.claimsAbertos + " claims em aberto", m.financeiro.contratos.claimsAbertos ? "warning" : "success");
      case "suprimentos": return selo("aderência ao plano " + F.pct(m.suprimentos.aderenciaPct), "info");
      case "riscos": return selo(m.riscos.revisaoVencida + " revisão vencida", m.riscos.revisaoVencida ? "warning" : "success");
      case "qualidade": return selo(m.qualidade.rncAbertas + " RNC abertas", m.qualidade.rncAbertas ? "warning" : "success");
      case "hse": return selo("TRIF " + F.num(m.hse.trif, 2), "info");
      case "governanca": return selo(m.governanca.emAnalise + " em análise de impacto", "info");
      default: return "";
    }
  }
  function renderModulos(r) {
    document.getElementById("home-modulos").innerHTML = GI.layout.nav.map(function (mod) {
      return '<a class="card card--interactive module-card" href="' + tela(mod.id, mod.itens[0].id) + '" style="--module-accent: var(' + ACENTO[mod.id] + ')">' +
        '<div class="module-card__top"><span class="module-card__icon">' + icone(mod.icone) + '</span><span class="module-card__num">' + mod.num + "</span></div>" +
        '<h3 class="module-card__title">' + esc(mod.nome) + "</h3>" +
        '<p class="module-card__text">' + esc(TEXTO_MODULO[mod.id]) + "</p>" +
        '<div class="module-card__links">' + selosModulo(mod.id, r.modulos) + "</div></a>";
    }).join("");
  }

  function renderContexto(r) {
    var p = r.projeto;
    document.getElementById("home-meta").innerHTML =
      (r.portfolio ? '<span class="badge badge--primary">' + esc("Portfólio de projetos") + '</span>' + selo(GI.util.plural(p.projetos, "projeto"), "neutral")
        : p ? '<span class="badge badge--primary" data-sem-traducao>' + esc(p.codigo + " · " + p.nome) + "</span>" : selo("Nenhum projeto selecionado", "neutral")) +
      selo("Data de referência " + F.data(r.referencia), "info") +
      (p ? selo("Orçamento " + F.moedaCompacta(p.orcamentoCentavos), "neutral") + selo("Término previsto " + F.data(p.terminoPrevisto), "neutral") : "") +
      selo("Dados fictícios", "purple");
  }

  /* ---------------- Carteira de projetos (só no Portfólio) ---------------- */
  var tCarteira = null;
  function saudeSelo(f) {
    var t = { success: "No plano", warning: "Atenção", danger: "Crítico" };
    return f ? '<span class="badge badge--' + f + ' badge--dot">' + esc(t[f]) + "</span>" : "";
  }
  function indiceHtml(v) { return v == null ? "" : '<span class="num text-strong valor--' + (v >= 1 ? "positivo" : v >= 0.95 ? "atencao" : "negativo") + '">' + esc(F.indice(v)) + "</span>"; }
  function renderCarteira(r) {
    var sec = document.getElementById("home-carteira-sec");
    sec.hidden = !r.portfolio;
    if (!r.portfolio || !r.carteira) return;
    var c = r.carteira, crit = c.criterios.map(function (x) { return x.nome + " " + F.num(x.peso) + "%"; }).join(" · ");
    document.getElementById("home-carteira-sub").textContent = "Peso na carteira pela ponderação composta: " + crit + ". Posição na data de referência.";
    if (!tCarteira) {
      tCarteira = GI.tabela.criar("home-carteira", {
        porPagina: 0, pilha: true, legenda: "Carteira de projetos", ordem: { coluna: "peso", direcao: "desc" },
        colunas: [
          { id: "codigo", titulo: "Projeto", fixa: true, classe: "col-projeto", valor: function (x) { return x.codigo + " " + x.nome; },
            html: function (x) { return '<b data-sem-traducao>' + esc(x.codigo) + '</b><span class="linha-sub" data-sem-traducao>' + esc(x.nome) + "</span>"; } },
          { id: "peso", titulo: "Peso na carteira", tipo: "pct", casas: 1,
            html: function (x) { return '<div class="progress-row"><div class="progress progress--sm progress--accent" role="img" aria-label="' + esc(F.pct(x.peso)) + '"><div class="progress__bar" style="width:' + Math.min(100, x.peso) + '%"></div></div><span class="num">' + esc(F.pct(x.peso)) + "</span></div>"; } },
          { id: "bac", titulo: "Orçamento vigente", tipo: "moeda", html: function (x) { return esc(F.moedaCompacta(x.bac)); } },
          { id: "real", titulo: "Avanço real x previsto", tipo: "pct", html: function (x) { return x.real == null ? "" : '<span class="num">' + esc(F.pct(x.real)) + '</span> <span class="text-small text-muted">x ' + esc(F.pct(x.previsto)) + "</span>"; } },
          { id: "spi", titulo: "SPI", tipo: "indice", html: function (x) { return indiceHtml(x.spi); } },
          { id: "cpi", titulo: "CPI", tipo: "indice", html: function (x) { return indiceHtml(x.cpi); } },
          { id: "projecaoTermino", titulo: "Projeção no término", tipo: "moeda",
            html: function (x) { return x.projecaoTermino == null ? "" : esc(F.moedaCompacta(x.projecaoTermino)) + (x.vac ? ' <span class="text-small ' + (x.vac < 0 ? "valor--sobrecusto" : "valor--positivo") + '">(' + (x.vac < 0 ? "+" : "−") + esc(F.moedaCompacta(Math.abs(x.vac))) + ")</span>" : ""); } },
          { id: "terminoTendencia", titulo: "Término pela tendência", valor: function (x) { return x.terminoTendencia || ""; },
            html: function (x) { return x.terminoTendencia ? '<span class="' + (x.terminoTendencia > x.terminoBaseline ? "valor--negativo" : "") + '">' + esc(GI.util.mesCurto(x.terminoTendencia)) + "</span>" + (x.terminoBaseline ? ' <span class="text-small text-muted">LB ' + esc(GI.util.mesCurto(x.terminoBaseline)) + "</span>" : "") : ""; } },
          { id: "riscosTopo", titulo: "Riscos no topo", tipo: "num" },
          { id: "pedidosCriticos", titulo: "Pedidos críticos", tipo: "num" },
          { id: "acoesAtrasadas", titulo: "Ações atrasadas", tipo: "num" },
          { id: "saude", titulo: "Situação", valor: function (x) { return x.saude || ""; }, html: function (x) { return saudeSelo(x.saude); } }
        ],
        acoes: function (x) {
          return '<button type="button" class="btn btn--ghost btn--sm" data-abrir-projeto="' + x.projetoId + '" title="Abrir o projeto ' + esc(x.codigo) + '">' + icone("chevronRight") + "Abrir</button>";
        },
        rodape: function () {
          var t = c.total;
          return { codigo: "<b>Portfólio</b>", peso: '<b class="num">100%</b>', bac: "<b>" + esc(F.moedaCompacta(t.bac)) + "</b>",
            real: '<b class="num">' + esc(F.pct(t.real)) + '</b> <span class="text-small text-muted">x ' + esc(F.pct(t.previsto)) + "</span>",
            spi: "<b>" + indiceHtml(t.spi) + "</b>", cpi: "<b>" + indiceHtml(t.cpi) + "</b>", projecaoTermino: "<b>" + esc(F.moedaCompacta(t.projecaoTermino)) + "</b>",
            terminoTendencia: t.terminoTendencia ? "<b>" + esc(GI.util.mesCurto(t.terminoTendencia)) + "</b>" : "",
            riscosTopo: "<b>" + F.num(t.riscosTopo) + "</b>", pedidosCriticos: "<b>" + F.num(t.pedidosCriticos) + "</b>", acoesAtrasadas: "<b>" + F.num(t.acoesAtrasadas) + "</b>" };
        }
      });
      document.getElementById("home-carteira").addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-abrir-projeto]");
        if (b) GI.layout.trocarEscopo(Number(b.getAttribute("data-abrir-projeto")));
      });
    }
    tCarteira.atualizar(c.projetos);
  }

  /* Ponderação da carteira: pesos dos critérios e notas dos projetos (Gestor ou Admin) */
  function ponderacao() {
    var c = ultimo && ultimo.carteira;
    if (!c) return;
    var sessao = GI.api.sessaoAtual();
    if (["Gestor", "Admin"].indexOf(sessao.papelCodigo) < 0) { GI.ui.toast("Somente Gestor ou Admin altera a ponderação da carteira.", "warning"); return; }
    var par = GI.api.portfolio.criterios(), notas = par.criterios.filter(function (x) { return x.fonte === "nota"; });
    var campos = par.criterios.map(function (x) {
      return { id: "peso_" + x.id, rotulo: "Peso: " + x.nome + " (%)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, passo: 1, valor: x.peso,
        ajuda: x.fonte === "orcamento" ? "Participação do orçamento vigente (EAC) do projeto na carteira." : "Participação da nota do projeto (" + par.notaMinima + " a " + par.notaMaxima + ")." };
    });
    campos.push({ id: "soma", rotulo: "Soma dos pesos", tipo: "info", html: "" });
    c.projetos.forEach(function (p) {
      notas.forEach(function (n) {
        campos.push({ id: "nota_" + p.projetoId + "_" + n.id, rotulo: p.codigo + ": " + n.nome, tipo: "numero", obrigatorio: true, min: par.notaMinima, maxNumero: par.notaMaxima, passo: 1,
          valor: p.notas && p.notas[n.id] != null ? p.notas[n.id] : null });
      });
    });
    campos.push({ id: "previa", rotulo: "Pesos resultantes", tipo: "info", html: "", largura: "full" });
    campos.push({ id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300, largura: "full" });
    GI.form.abrir({
      titulo: "Ponderação da carteira", subtitulo: "Define a relevância de cada projeto na Curva S física e nos índices ponderados do portfólio", tamanho: "lg",
      intro: '<p class="text-small text-muted">Peso do projeto = soma de (peso do critério x participação do projeto no critério). O critério de valor usa o orçamento vigente; os demais, a nota de ' + par.notaMinima + " a " + par.notaMaxima + ". A alteração gera nova versão dos parâmetros, com vigência a partir da data de referência.</p>",
      campos: campos,
      aoMudar: function (v, ctx) {
        var soma = par.criterios.reduce(function (s, x) { return s + (Number(v["peso_" + x.id]) || 0); }, 0);
        ctx.info("soma", '<b class="num' + (Math.abs(soma - 100) > 0.001 ? " valor--negativo" : "") + '">' + esc(F.num(soma, 1)) + "%</b>");
        /* prévia com a regra da api (mesmos critérios, orçamento vigente atual) */
        var crit = par.criterios.map(function (x) { return { id: x.id, fonte: x.fonte, peso: Number(v["peso_" + x.id]) || 0 }; });
        var lista = c.projetos.map(function (p) {
          var nt = {}; notas.forEach(function (n) { nt[n.id] = Number(v["nota_" + p.projetoId + "_" + n.id]) || 0; });
          return { id: p.projetoId, orcamentoCentavos: p.bac, notas: nt };
        });
        var r = GI.regras.ponderarPortfolio(lista, crit);
        ctx.info("previa", '<div class="cluster">' + c.projetos.map(function (p) { return '<span class="badge badge--outline" data-sem-traducao>' + esc(p.codigo) + " " + esc(F.pct(r[p.projetoId].peso)) + "</span>"; }).join("") + "</div>");
      },
      aoSalvar: function (v) {
        var d = { criterios: {}, notas: {} };
        par.criterios.forEach(function (x) { d.criterios[x.id] = Number(v["peso_" + x.id]); });
        c.projetos.forEach(function (p) { d.notas[p.projetoId] = {}; notas.forEach(function (n) { d.notas[p.projetoId][n.id] = Number(v["nota_" + p.projetoId + "_" + n.id]); }); });
        return GI.api.portfolio.salvarPonderacao(d, v.justificativa).then(function () {
          GI.ui.toast("Ponderação da carteira atualizada.", "success");
          return carregar();
        });
      }
    });
  }

  /* Exportação da Home (painel): indicadores e pontos de atenção */
  var ultimo = null;
  GI.exportar.registrar(function () {
    var alertas = ultimo ? ultimo.alertas : [];
    var nomeModulo = function (id) { var m = GI.layout.nav.filter(function (x) { return x.id === id; })[0]; return m ? m.num + " " + m.nome : id; };
    var blocos = [];
    if (ultimo && ultimo.portfolio && tCarteira) blocos.push({ tipo: "tabela", titulo: "Carteira de projetos", dados: tCarteira.exportacao() });
    return {
      titulo: ultimo && ultimo.portfolio ? "Resumo do portfólio" : "Resumo do projeto",
      subtitulo: ultimo && ultimo.projeto ? (ultimo.portfolio ? "Portfólio de projetos" : ultimo.projeto.codigo + " " + ultimo.projeto.nome) : "",
      arquivo: ultimo && ultimo.portfolio ? "resumo-portfolio" : "resumo-projeto",
      blocos: blocos.concat([
        { tipo: "kpis", titulo: "Indicadores-chave por módulo", itens: Array.prototype.map.call(document.querySelectorAll("#home-kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__modulo").textContent + " · " + k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Pontos de atenção", dados: {
            colunas: [{ titulo: "Módulo" }, { titulo: "Nível" }, { titulo: "Ponto de atenção" }, { titulo: "Detalhe" }],
            bruto: alertas.map(function (a) { return [nomeModulo(a.modulo), a.nivel === "danger" ? "Crítico" : "Atenção", a.titulo, a.detalhe]; }),
            texto: alertas.map(function (a) { return [nomeModulo(a.modulo), a.nivel === "danger" ? "Crítico" : "Atenção", a.titulo, a.detalhe]; })
          } }
      ])
    };
  });


  /* ---------------- Relatório gerencial (modal de emissão) ---------------- */
  var SECOES_RG = [
    { valor: "planejamento", texto: "Planejamento: Curva S, KPIs e produtividade; análise e relato do período (2 páginas)" },
    { valor: "financeiro", texto: "Financeiro (1 página)" },
    { valor: "suprimentos", texto: "Suprimentos (1 página)" },
    { valor: "riscos", texto: "Riscos (1 página)" },
    { valor: "qualidade", texto: "Qualidade (1 página)" },
    { valor: "hse", texto: "HSE: KPIs e pirâmide (1 página)" }
  ];
  /* Tela de cada módulo onde a análise do período é registrada (modal "Análise do período") */
  var TELA_ANALISE = { planejamento: ["planejamento", "relato"], financeiro: ["financeiro", "kpis"], suprimentos: ["suprimentos", "painel"], riscos: ["riscos", "painel"], qualidade: ["qualidade", "painel"], hse: ["hse", "painel"] };
  function emitirRelatorio(preset) {
    var pre = preset || {}, API = GI.api.planejamento;
    var pid = pre.escopo === "portfolio" ? null : pre.escopo ? Number(pre.escopo) : GI.api.projetoAtualId();
    Promise.all([API.periodosRelato(pid, "Semanal"), API.periodosRelato(pid, "Mensal"), pid == null ? API.relatos(null) : Promise.resolve([])]).then(function (r) {
      var relatosTodos = r[2];
      var per = { Semanal: r[0], Mensal: r[1] };
      var padrao = { Semanal: GI.api.periodoPadraoRelatorio("Semanal"), Mensal: GI.api.periodoPadraoRelatorio("Mensal") };
      var tipoIni = pre.tipo === "Mensal" ? "Mensal" : "Semanal", ultimoTipo = tipoIni, m = null;
      var periodoIni = pre.periodo && per[tipoIni].some(function (x) { return x.periodo === pre.periodo; }) ? pre.periodo : padrao[tipoIni];
      var proj = pid == null ? { codigo: "Portfólio", nome: "Portfólio de projetos" } : GI.util.projeto(pid) || {};
      function opcoes(tipo, sel) {
        return per[tipo].map(function (x) {
          return '<option value="' + esc(x.periodo) + '"' + (x.periodo === sel ? " selected" : "") + ">" + esc(x.rotulo + (x.emAndamento ? " (em andamento)" : "") + (x.periodo === padrao[tipo] ? " (padrão)" : "")) + "</option>";
        }).join("");
      }
      function situacaoRelato(tipo, periodo) {
        var x = per[tipo].filter(function (p) { return p.periodo === periodo; })[0];
        if (!x) return "";
        if (pid == null) {
          /* Portfólio: situação do relato de cada projeto (os pontos de atenção entram na página 2 do Planejamento) */
          return '<ul class="rel-situacao">' + GI.util.listaProjetos().map(function (p) {
            var reg = relatosTodos.some(function (rl) { return rl.projetoId === p.id && rl.tipo === tipo && rl.periodo === periodo; });
            var urlP = tela("planejamento", "relato", { tipo: tipo, periodo: periodo, abrir: "1", projeto: p.id });
            return "<li>" + (reg ? '<span class="badge badge--success badge--dot">Registrado</span>' : '<span class="badge badge--warning badge--dot">Pendente</span>') +
              ' <span class="text-small"><span data-sem-traducao>' + esc(p.codigo) + "</span> · <a href=\"" + urlP + '">' + (reg ? "Ver relato" : "Registrar agora") + "</a></span></li>";
          }).join("") + "</ul>" + (x.emAndamento ? '<p class="text-small text-muted mt-2">Período em andamento: o relatório sai parcial, com dados até a data de referência.</p>' : "");
        }
        var url = tela("planejamento", "relato", { tipo: tipo, periodo: periodo, abrir: "1" });
        var parcial = x.emAndamento ? '<p class="text-small text-muted mt-2">Período em andamento: o relatório sai parcial, com dados até a data de referência.</p>' : "";
        return (x.relatoId
          ? '<span class="badge badge--success badge--dot">Registrado</span> <span class="text-small">A página 2 do Planejamento traz as atividades, os pontos de atenção e os riscos. <a href="' + url + '">Ver relato</a></span>'
          : '<span class="badge badge--warning badge--dot">Pendente</span> <span class="text-small">Sem relato ' + tipo.toLowerCase() + " neste período: a página 2 do Planejamento sai com o aviso. " +
            '<a href="' + url + '">Registrar agora</a></span>') + parcial;
      }
      /* Situação das análises do período por módulo (texto e comentários dos desvios negativos) */
      function situacaoAnalises(tipo, periodo) {
        var alvo = m && m.el.querySelector('[data-campo="analises"] [data-info]');
        if (!alvo || !periodo) return;
        GI.api.analises.situacao(pid, tipo, periodo).then(function (lista) {
          alvo.innerHTML = '<ul class="rel-situacao">' + lista.map(function (a) {
            var t = TELA_ANALISE[a.modulo], url = tela(t[0], t[1], { analise: "1", tipo: tipo, periodo: periodo, projeto: pid == null ? "portfolio" : pid });
            var selo = !a.registrada ? '<span class="badge badge--warning badge--dot">Pendente</span>'
              : a.pendentes ? '<span class="badge badge--warning badge--dot">' + esc(GI.util.plural(a.pendentes, "desvio sem comentário", "desvios sem comentário")) + "</span>"
              : '<span class="badge badge--success badge--dot">Registrada</span>';
            return "<li>" + selo + ' <span class="text-small">' + esc(a.nome) + (a.obrigatorio && a.desvios ? " · " + esc(GI.util.plural(a.desvios, "desvio negativo", "desvios negativos")) : "") +
              ' · <a href="' + url + '">' + (a.registrada ? "Ver ou editar" : "Registrar") + "</a></span></li>";
          }).join("") + "</ul>";
        }).catch(function () { alvo.innerHTML = ""; });
      }
      function info() {
        if (!m) return;
        var sel = m.el.querySelector('[data-campo="periodo"] select'), v = m.ler();
        var alvo = m.el.querySelector('[data-campo="relato"] [data-info]');
        if (alvo && sel) alvo.innerHTML = situacaoRelato(v.tipo || "Semanal", sel.value);
        if (sel) situacaoAnalises(v.tipo || "Semanal", sel.value);
      }
      var opcoesEscopo = [{ valor: "portfolio", texto: "Portfólio (todos os projetos)" }].concat(GI.util.listaProjetos().map(function (p) { return { valor: String(p.id), texto: p.codigo + " · " + p.nome }; }));
      m = GI.form.abrir({
        titulo: "Emitir relatório gerencial", subtitulo: pid == null ? "Portfólio de projetos" : (proj.codigo || "") + " · " + (proj.nome || ""), tamanho: "lg", textoSalvar: "Emitir relatório",
        campos: [
          { id: "escopo", rotulo: "Relatório de", tipo: "select", obrigatorio: true, largura: "full", valor: pid == null ? "portfolio" : String(pid), opcoes: opcoesEscopo,
            ajuda: pid == null ? "Portfólio: visão da carteira, Curva S física ponderada e financeira consolidada, e a análise do PMO por módulo." : "Projeto: mesmo formato do relatório do projeto." },
          { id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, valor: tipoIni, opcoes: [
            { valor: "Semanal", texto: "Semanal", sub: "semana ISO, segunda a domingo" }, { valor: "Mensal", texto: "Mensal", sub: "mês civil" }] },
          { id: "periodo", rotulo: "Período", tipo: "select", obrigatorio: true, opcoes: [], ajuda: "Padrão: a semana anterior (no mensal, o mês anterior)." },
          { id: "relato", rotulo: "Relato do período (02 Planejamento)", tipo: "info", html: "" },
          { id: "analises", rotulo: "Análise do período por módulo", tipo: "info", html: "" },
          { id: "secoes", rotulo: "Conteúdo", tipo: "multi", obrigatorio: true, valor: pre.secoes || SECOES_RG.map(function (x) { return x.valor; }), opcoes: SECOES_RG },
          { id: "formato", rotulo: "Formato", tipo: "info", html: '<p class="text-small">A4 na horizontal, uma página por seção (Planejamento em duas). Cada página traz a análise do período do módulo; desvio negativo sem comentário aparece como pendente. O relatório abre em nova aba, pronto para imprimir ou salvar em PDF pela impressão do navegador.</p>' }
        ],
        aoMudar: function (v) {
          if (!m) return;
          if (v.escopo && v.escopo !== (pid == null ? "portfolio" : String(pid))) {
            /* troca de escopo: reabre o modal com os períodos, relatos e análises do novo escopo */
            var sp = m.el.querySelector('[data-campo="periodo"] select');
            var pre2 = { escopo: v.escopo, tipo: v.tipo, periodo: sp ? sp.value : null, secoes: v.secoes };
            var fechar = m.el.querySelector("[data-modal-close]");
            if (fechar) fechar.click();
            setTimeout(function () { emitirRelatorio(pre2); }, 0);
            return;
          }
          var sel = m.el.querySelector('[data-campo="periodo"] select');
          if (v.tipo && v.tipo !== ultimoTipo) { ultimoTipo = v.tipo; sel.innerHTML = opcoes(v.tipo, padrao[v.tipo]); }
          info();
        },
        aoSalvar: function (v) {
          var url = "relatorio.html?" + [["escopo", v.escopo || "portfolio"], ["tipo", v.tipo], ["periodo", v.periodo], ["secoes", v.secoes.join(",")]].map(function (x) {
            return encodeURIComponent(x[0]) + "=" + encodeURIComponent(x[1]);
          }).join("&");
          var aba = window.open(url, "_blank");
          if (!aba) window.location.href = url;
          else GI.ui.toast("Relatório aberto em nova aba.", "success");
        }
      });
      m.el.querySelector('[data-campo="periodo"] select').innerHTML = opcoes(tipoIni, periodoIni);
      info();
    }).catch(function (e) { GI.ui.toast("Não foi possível abrir a emissão do relatório.", "danger"); if (window.console) console.error(e); });
  }
  document.getElementById("btn-relatorio").addEventListener("click", function () { emitirRelatorio(); });

  GI.util.pronto().then(function () {
    if (GI.util.param("relatorio") === "1") emitirRelatorio({ tipo: GI.util.param("tipo"), periodo: GI.util.param("periodo"), escopo: GI.util.param("escopo") });
  });
  document.getElementById("btn-ponderacao").addEventListener("click", ponderacao);
  function carregar() {
    return GI.api.resumoHome(GI.api.projetoAtualId()).then(function (r) {
      ultimo = r;
      renderContexto(r);
      renderKpis(r);
      renderCarteira(r);
      renderAlertas(r);
      renderModulos(r);
    }).catch(function (e) {
      GI.ui.toast("Não foi possível carregar o resumo.", "danger");
      if (window.console) console.error(e);
    });
  }
  GI.util.pronto().then(carregar);
})(window.GI = window.GI || {});
