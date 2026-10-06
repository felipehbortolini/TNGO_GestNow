/* ==========================================================================
   layout.js | Estrutura única de todas as páginas: header, sidebar, gaveta
   mobile, fundo escurecido e abas do módulo. Uma única fonte de navegação.

   Cada página declara no <body>:
     data-root="../../"            caminho até a raiz do sistema ("" na raiz)
     data-page="planejamento/curva-s"   módulo/tela atual (item destacado)
   e contém:
     <div class="app"><main class="app-main" id="conteudo"><div class="container">...</div></main></div>
   Opcional na página: <nav data-module-tabs></nav> recebe as abas do módulo.

   Escopo (Portfólio ou projeto): seletor no header (> 768px) e no topo da gaveta
   (<= 768px). A troca grava a escolha (GI.api.definirEscopo) e recarrega a tela com
   ?projeto=portfolio ou ?projeto=<id>; telas de detalhe voltam para a lista do módulo.

   Estados na div .app (ver css/layout.css):
     > 1024px   .is-sidebar-collapsed  trilho de ícones (preferência salva)
     769-1024   .is-sidebar-expanded   trilho abre sobreposto
     <= 768px   .is-drawer-open        gaveta com fundo escurecido
   ========================================================================== */
(function (GI) {
  "use strict";

  /* ---------------- Navegação (fonte única) ---------------- */
  var NAV = [
    { id: "central-acoes", num: "01", nome: "Central de Ações", icone: "actions", itens: [
      { id: "acoes", nome: "Ações", icone: "list" },
      { id: "dashboard", nome: "Dashboards e KPIs", icone: "dashboard" },
      { id: "atas", nome: "Atas", icone: "fileText", detalhes: ["ata"] }
    ] },
    { id: "planejamento", num: "02", nome: "Planejamento", icone: "curve", itens: [
      { id: "eap", nome: "EAP", icone: "listTree" },
      { id: "curva-s", nome: "Curva S", icone: "curve" },
      { id: "kpis", nome: "KPIs", icone: "gauge" },
      { id: "relato", nome: "Relato do período", curto: "Relato", icone: "fileText" },
      { id: "6wla", nome: "6WLA", icone: "calendarRange" },
      { id: "programacao-semanal", nome: "Programação Semanal", icone: "calendarDays" },
      { id: "produtividade", nome: "Produtividade", icone: "trendingUp" },
      { id: "punch-list", nome: "Punch list", icone: "listChecks" }
    ] },
    { id: "financeiro", num: "03", nome: "Gestão Financeira", icone: "money", itens: [
      { id: "eac", nome: "EAC", icone: "listTree" },
      { id: "mapa-controle", nome: "Mapa de controle", icone: "matrix" },
      { id: "desembolso", nome: "Cronograma de desembolso", curto: "Desembolso", icone: "coins" },
      { id: "kpis", nome: "KPIs de custo", curto: "KPIs", icone: "gauge" },
      { id: "curva-s", nome: "Curva S financeira", curto: "Curva S", icone: "curve" },
      { id: "contingencia", nome: "Contingência", icone: "shieldCheck" },
      { id: "contratos", nome: "Contratos", icone: "fileContract", detalhes: ["contrato"] }
    ] },
    { id: "suprimentos", num: "04", nome: "Suprimentos", icone: "cart", itens: [
      { id: "painel", nome: "Painel", icone: "dashboard" },
      { id: "plano-compras", nome: "Plano de compras", curto: "Plano", icone: "listChecks" },
      { id: "processos", nome: "Processos de compra", curto: "Processos", icone: "fileSearch" },
      { id: "mas", nome: "Mapa de Suprimentos (MAS)", curto: "MAS", icone: "matrix" },
      { id: "diligenciamento", nome: "Diligenciamento", icone: "truck" },
      { id: "fornecedores", nome: "Fornecedores", icone: "package" }
    ] },
    { id: "riscos", num: "05", nome: "Gestão de Riscos", icone: "alertTriangle", itens: [
      { id: "registro", nome: "Registro", icone: "list", detalhes: ["ficha"] },
      { id: "matriz", nome: "Matriz P x I", icone: "matrix" },
      { id: "painel", nome: "Painel", icone: "pieChart" }
    ] },
    { id: "qualidade", num: "06", nome: "Gestão da Qualidade", icone: "shieldCheck", itens: [
      { id: "painel", nome: "Painel", icone: "dashboard" },
      { id: "rnc", nome: "Não conformidades", icone: "octagonAlert" },
      { id: "inspecoes", nome: "Inspeções / ITP", icone: "clipboardCheck" },
      { id: "auditorias", nome: "Auditorias", icone: "clipboardList" }
    ] },
    { id: "hse", num: "07", nome: "HSE", icone: "hardHat", itens: [
      { id: "painel", nome: "Painel HSE", icone: "pyramid" },
      { id: "ocorrencias", nome: "Ocorrências", icone: "octagonAlert" },
      { id: "inspecoes", nome: "Inspeções e observações", icone: "clipboardCheck" },
      { id: "analises-risco", nome: "APR e HAZOP", icone: "fileSearch" },
      { id: "hht", nome: "Horas trabalhadas", icone: "clock" }
    ] },
    { id: "governanca", num: "08", nome: "Governança", icone: "landmark", itens: [
      { id: "mudancas", nome: "Gestão de mudanças", icone: "swap", detalhes: ["mudanca"] },
      { id: "licoes", nome: "Lições aprendidas", icone: "lightbulb" }
    ] }
  ];
  var EXTRAS = [
    { id: "configuracoes/parametros", nome: "Configurações", icone: "sliders", papeis: ["Gestor", "Admin"] }
  ];
  /* Páginas fora do menu (só contexto do header) */
  var AVULSAS = { styleguide: "Styleguide do design system" };

  var CHAVE_RECOLHIDO = "gi.sidebar.recolhida";
  var localAtual = null, raizAtual = "";
  var mqMobile = window.matchMedia("(max-width: 768px)");
  var mqTablet = window.matchMedia("(min-width: 769px) and (max-width: 1024px)");

  function svg(nome) { return GI.icons ? GI.icons.svg(nome) : ""; }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function hrefItem(raiz, modulo, item) { return raiz + "modulos/" + modulo.id + "/" + item.id + ".html"; }

  /* Página atual: "modulo/tela" (ou "home"); telas de detalhe herdam o item da lista */
  function localizar(pagina) {
    if (!pagina || pagina === "home") return { home: true };
    var partes = pagina.split("/");
    for (var i = 0; i < NAV.length; i++) {
      var m = NAV[i];
      if (m.id !== partes[0]) continue;
      for (var j = 0; j < m.itens.length; j++) {
        var it = m.itens[j];
        if (it.id === partes[1] || (it.detalhes && it.detalhes.indexOf(partes[1]) >= 0)) {
          return { modulo: m, item: it, detalhe: it.id !== partes[1] };
        }
      }
      return { modulo: m };
    }
    for (var k = 0; k < EXTRAS.length; k++) if (EXTRAS[k].id === pagina) return { extra: EXTRAS[k] };
    if (AVULSAS[pagina]) return { extra: { id: pagina, nome: AVULSAS[pagina] } };
    return {};
  }

  function lerPreferencia() {
    try { return window.localStorage.getItem(CHAVE_RECOLHIDO) === "1"; } catch (e) { return false; }
  }
  function salvarPreferencia(v) {
    try { window.localStorage.setItem(CHAVE_RECOLHIDO, v ? "1" : "0"); } catch (e) { /* armazenamento indisponível */ }
  }

  /* Seletor de idioma PT | IN (inglês): troca e recarrega a página */
  function seletorIdioma() {
    var atual = GI.i18n ? GI.i18n.idioma : "pt";
    return '<div class="segmented lang-toggle" role="group" aria-label="Idioma" data-sem-traducao>' +
      '<button type="button" class="segmented__opt" data-idioma="pt" aria-pressed="' + (atual === "pt") + '" title="Português" aria-label="Português">PT</button>' +
      '<button type="button" class="segmented__opt" data-idioma="en" aria-pressed="' + (atual === "en") + '" title="English" aria-label="English">IN</button></div>';
  }

  /* Seletor de escopo: Portfólio (consolidado) ou um projeto da carteira */
  function seletorEscopo(id) {
    var api = GI.api && GI.api.portfolio;
    if (!api) return "";
    var projetos = api.projetos(), atual = GI.api.projetoAtualId();
    return '<label class="sr-only" for="' + id + '">Escopo</label>' +
      '<select class="select escopo-select" id="' + id + '" data-escopo title="Portfólio ou projeto">' +
      '<option value="portfolio"' + (atual == null ? " selected" : "") + ">Portfólio (" + projetos.length + " projetos)</option>" +
      projetos.map(function (p) {
        return '<option value="' + p.id + '"' + (atual === p.id ? " selected" : "") + ">" + esc(p.codigo + " · " + p.nome) + "</option>";
      }).join("") + "</select>";
  }
  function rotuloEscopo() {
    var atual = GI.api && GI.api.projetoAtualId ? GI.api.projetoAtualId() : null;
    if (atual == null) return "Portfólio";
    var p = GI.api.portfolio.projetos().filter(function (x) { return x.id === atual; })[0];
    return p ? p.codigo : "";
  }
  function trocarEscopo(valor, local, raiz) {
    GI.api.definirEscopo(valor === "portfolio" ? null : Number(valor));
    var destino = local && local.detalhe ? raiz + "modulos/" + local.modulo.id + "/" + local.item.id + ".html" : window.location.pathname;
    window.location.href = destino + "?projeto=" + encodeURIComponent(valor);
  }

  /* Telas de detalhe completam o contexto do header (ex.: "· Ata TN-2026-0031 Rev 1") */
  var detalhePendente = null;
  function detalhe(texto) {
    var ctx = document.querySelector(".app-header__context");
    if (!ctx) { detalhePendente = texto; return; }
    var no = ctx.lastChild;   /* texto do contexto (depois do rótulo do escopo, que só aparece no celular) */
    if (!no || no.nodeType !== 3) { no = document.createTextNode(""); ctx.appendChild(no); }
    var base = ctx.getAttribute("data-base") || no.nodeValue;
    ctx.setAttribute("data-base", base);
    no.nodeValue = base + (texto ? " · " + (GI.t ? GI.t(texto) : texto) : "");
  }

  /* ---------------- Montagem ---------------- */
  function montar() {
    var body = document.body;
    var app = document.querySelector(".app");
    if (!app) return;
    var raiz = body.getAttribute("data-root") || "";
    var pagina = body.getAttribute("data-page") || "home";
    var local = localizar(pagina);
    var sessao = GI.api && GI.api.sessaoAtual ? GI.api.sessaoAtual() : { nome: "Usuário", papel: "", iniciais: "U" };

    /* Link de pular para o conteúdo */
    var pular = document.createElement("a");
    pular.className = "skip-link";
    pular.href = "#conteudo";
    pular.textContent = "Pular para o conteúdo";
    body.insertBefore(pular, body.firstChild);

    /* Contexto do header */
    var contexto = local.home ? "Início"
      : local.modulo ? local.modulo.num + " " + local.modulo.nome + (local.item ? " · " + local.item.nome : "")
      : local.extra ? local.extra.nome : "";

    var header = document.createElement("header");
    header.className = "app-header";
    header.innerHTML =
      '<div class="app-header__brand"><a href="' + raiz + 'index.html" aria-label="Início: Gestão Integrada AMT">' +
        '<img class="app-header__logo--full" src="' + raiz + 'assets/logos/timenow-horizontal.png" alt="Timenow">' +
        '<img class="app-header__logo--icon" src="' + raiz + 'assets/logos/timenow-icone.png" alt="Timenow"></a></div>' +
      '<button type="button" class="btn btn--ghost btn--icon app-header__toggle" aria-controls="menu-principal" aria-expanded="false" aria-label="Abrir ou recolher o menu">' + svg("menu") + "</button>" +
      '<div class="app-header__title"><span class="app-header__system">Gestão Integrada AMT</span>' +
        '<span class="app-header__context"><span class="app-header__escopo">' + esc(rotuloEscopo()) + '</span>' + esc(contexto) + "</span></div>" +
      '<div class="app-header__actions">' +
        '<div class="app-header__escopo-sel">' + seletorEscopo("escopo-header") + "</div>" +
        seletorIdioma() +
        '<div class="app-header__user"><b>' + esc(sessao.nome) + "</b><span>" + esc(sessao.papel) + "</span></div>" +
        '<span class="avatar" aria-hidden="true">' + esc(sessao.iniciais) + "</span></div>";

    /* Sidebar */
    var nav = '<a class="nav-link' + (local.home ? " is-active" : "") + '" href="' + raiz + 'index.html"' +
      (local.home ? ' aria-current="page"' : "") + ' title="Início">' + svg("home") + '<span class="nav-link__text">Início</span></a>';

    NAV.forEach(function (m) {
      var atual = local.modulo && local.modulo.id === m.id;
      var itens = m.itens.map(function (it) {
        var ativo = atual && local.item && local.item.id === it.id;
        return '<a class="nav-link' + (ativo ? " is-active" : "") + '" href="' + hrefItem(raiz, m, it) + '"' +
          (ativo && !local.detalhe ? ' aria-current="page"' : "") + ' title="' + esc(it.nome) + '">' +
          svg(it.icone) + '<span class="nav-link__text">' + esc(it.nome) + "</span></a>";
      }).join("");
      nav += '<div class="nav-group' + (atual ? " is-open is-current" : "") + '" data-modulo="' + m.id + '">' +
        '<button type="button" class="nav-group__head" aria-expanded="' + (atual ? "true" : "false") + '" ' +
          'data-primeiro="' + hrefItem(raiz, m, m.itens[0]) + '" title="' + esc(m.num + " " + m.nome) + '">' +
          '<span class="nav-group__icon">' + svg(m.icone) + "</span>" +
          '<span class="nav-group__num">' + m.num + '</span><span class="nav-group__name">' + esc(m.nome) + "</span>" +
          '<span class="nav-group__chevron">' + svg("chevronDown") + "</span></button>" +
        '<div class="nav-group__items">' + itens + "</div></div>";
    });

    EXTRAS.forEach(function (x) {
      if (x.papeis && x.papeis.indexOf(sessao.papelCodigo || sessao.papel) < 0) return;
      var ativo = local.extra && local.extra.id === x.id;
      nav += '<div class="nav-separador" role="separator"></div>' +
        '<a class="nav-link' + (ativo ? " is-active" : "") + '" href="' + raiz + "modulos/" + x.id + '.html"' +
        (ativo ? ' aria-current="page"' : "") + ' title="' + esc(x.nome) + '">' + svg(x.icone) +
        '<span class="nav-link__text">' + esc(x.nome) + "</span></a>";
    });

    var sidebar = document.createElement("aside");
    sidebar.className = "app-sidebar";
    sidebar.id = "menu-principal";
    sidebar.setAttribute("aria-label", "Menu principal");
    sidebar.innerHTML =
      '<div class="app-sidebar__drawer-head">' +
        '<img src="' + raiz + 'assets/logos/timenow-horizontal.png" alt="Timenow">' +
        '<button type="button" class="btn btn--ghost btn--icon" data-fechar-gaveta aria-label="Fechar menu">' + svg("x") + "</button></div>" +
      '<div class="app-sidebar__escopo">' + seletorEscopo("escopo-gaveta") + "</div>" +
      '<div class="app-sidebar__scroll"><nav class="sidebar-nav">' + nav + "</nav></div>" +
      '<div class="app-sidebar__foot"><span class="app-sidebar__foot-text">Protótipo · dados fictícios · ' +
        '<a class="app-sidebar__foot-link" href="' + raiz + 'styleguide.html">Styleguide</a></span>' +
        (GI.api && GI.api.haAlteracoes && GI.api.haAlteracoes()
          ? '<button type="button" class="btn btn--on-dark btn--sm app-sidebar__restaurar" data-restaurar>' + svg("refresh") + "Restaurar dados de demonstração</button>" : "") +
      "</div>";

    var fundo = document.createElement("div");
    fundo.className = "app-backdrop";
    fundo.setAttribute("aria-hidden", "true");

    app.insertBefore(fundo, app.firstChild);
    app.insertBefore(sidebar, fundo);
    app.insertBefore(header, sidebar);

    if (lerPreferencia()) app.classList.add("is-sidebar-collapsed");

    /* Abas do módulo (opcional na página) */
    var abas = document.querySelector("[data-module-tabs]");
    if (abas && local.modulo) {
      abas.classList.add("tabs");
      abas.setAttribute("aria-label", "Telas do módulo " + local.modulo.nome);
      abas.innerHTML = local.modulo.itens.map(function (it) {
        var ativo = local.item && local.item.id === it.id;
        return '<a class="tab' + (ativo ? " is-active" : "") + '" href="' + hrefItem(raiz, local.modulo, it) + '"' +
          (ativo ? ' aria-current="page"' : "") + (it.curto ? ' title="' + esc(it.nome) + '"' : "") + ">" + svg(it.icone) + esc(it.curto || it.nome) + "</a>";
      }).join("");
      /* No celular as abas rolam na horizontal: mostra a aba ativa */
      var abaAtiva = abas.querySelector(".tab.is-active");
      if (abaAtiva && abas.scrollWidth > abas.clientWidth) abas.scrollLeft = Math.max(0, abaAtiva.getBoundingClientRect().left - abas.getBoundingClientRect().left - 16);
    }

    localAtual = local; raizAtual = raiz;
    comportamentos(app, header, sidebar, fundo);
    if (detalhePendente) detalhe(detalhePendente);
    observarBarra();

    /* Componentes da página (ícones, abas, contadores) */
    if (GI.ui) GI.ui.init(document);
  }

  /* ---------------- Barra da página ----------------
     Abas à esquerda e ações à direita na mesma linha. Quando não cabem, entra o
     modo compacto (menos respiro e "Exportar" oculto nos botões de exportação) e,
     se preciso, o segundo nível (abas sem ícone, com o nome no title); se ainda
     assim não couber, as ações quebram para a linha de baixo. */
  function ajustarBarra() {
    var barra = document.querySelector(".page-bar");
    if (!barra) return;
    var esq = barra.firstElementChild, dir = barra.querySelector(".page-actions");
    barra.classList.remove("is-compacta", "is-compacta-2");
    if (!esq || !dir || esq === dir || !dir.children.length || window.innerWidth <= 768) return;
    function quebrou() { return dir.getBoundingClientRect().top >= esq.getBoundingClientRect().bottom - 2; }
    if (quebrou()) barra.classList.add("is-compacta");
    if (quebrou()) barra.classList.add("is-compacta-2");
  }
  function observarBarra() {
    var barra = document.querySelector(".page-bar");
    if (!barra) return;
    var largura = -1;
    if (window.ResizeObserver) {
      new ResizeObserver(function (ent) {
        var w = Math.round(ent[0].contentRect.width);
        if (w !== largura) { largura = w; ajustarBarra(); }
      }).observe(barra);
    } else {
      window.addEventListener("resize", ajustarBarra);
    }
    var dir = barra.querySelector(".page-actions");
    if (dir && window.MutationObserver) new MutationObserver(function () { ajustarBarra(); }).observe(dir, { childList: true, subtree: true, characterData: true });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(ajustarBarra);
    window.requestAnimationFrame(ajustarBarra);
  }

  /* ---------------- Comportamentos ---------------- */
  function comportamentos(app, header, sidebar, fundo) {
    var botao = header.querySelector(".app-header__toggle");

    function emTrilho() {
      if (mqMobile.matches) return false;
      if (mqTablet.matches) return !app.classList.contains("is-sidebar-expanded");
      return app.classList.contains("is-sidebar-collapsed");
    }
    function atualizarAria() {
      var aberto = mqMobile.matches ? app.classList.contains("is-drawer-open") : !emTrilho();
      botao.setAttribute("aria-expanded", aberto ? "true" : "false");
    }
    function abrirGaveta() {
      app.classList.add("is-drawer-open");
      document.body.classList.add("has-modal");
      var primeiro = sidebar.querySelector(".nav-link, .nav-group__head");
      if (primeiro) primeiro.focus();
      atualizarAria();
    }
    function fecharGaveta(devolverFoco) {
      if (!app.classList.contains("is-drawer-open")) return;
      app.classList.remove("is-drawer-open");
      document.body.classList.remove("has-modal");
      if (devolverFoco) botao.focus();
      atualizarAria();
    }

    botao.addEventListener("click", function () {
      if (mqMobile.matches) {
        if (app.classList.contains("is-drawer-open")) fecharGaveta(true); else abrirGaveta();
      } else if (mqTablet.matches) {
        app.classList.toggle("is-sidebar-expanded");
      } else {
        var recolher = !app.classList.contains("is-sidebar-collapsed");
        app.classList.toggle("is-sidebar-collapsed", recolher);
        salvarPreferencia(recolher);
      }
      atualizarAria();
    });

    fundo.addEventListener("click", function () { fecharGaveta(true); });

    /* Escopo: Portfólio ou projeto */
    Array.prototype.forEach.call(document.querySelectorAll("[data-escopo]"), function (sel) {
      sel.addEventListener("change", function () { trocarEscopo(sel.value, localAtual, raizAtual); });
    });

    /* Idioma */
    header.querySelector(".lang-toggle").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-idioma]");
      if (!b || b.getAttribute("aria-pressed") === "true" || !GI.i18n) return;
      GI.i18n.definir(b.getAttribute("data-idioma"));
    });

    /* Protótipo: descarta o que foi gravado nesta sessão e volta aos dados fictícios */
    var restaurar = sidebar.querySelector("[data-restaurar]");
    if (restaurar) restaurar.addEventListener("click", function () {
      GI.modal.confirm({ title: "Restaurar dados de demonstração", message: "Tudo o que foi incluído ou alterado nesta sessão será descartado.", okText: "Restaurar", danger: true })
        .then(function (ok) { if (ok) { GI.api.restaurarDados(); window.location.reload(); } });
    });
    sidebar.querySelector("[data-fechar-gaveta]").addEventListener("click", function () { fecharGaveta(true); });

    document.addEventListener("keydown", function (ev) {
      if (ev.key !== "Escape") return;
      if (app.classList.contains("is-drawer-open")) { fecharGaveta(true); return; }
      if (mqTablet.matches && app.classList.contains("is-sidebar-expanded")) {
        app.classList.remove("is-sidebar-expanded"); atualizarAria(); botao.focus();
      }
    });

    /* Tablet: clicar fora recolhe a sidebar sobreposta */
    document.addEventListener("click", function (ev) {
      if (!mqTablet.matches || !app.classList.contains("is-sidebar-expanded")) return;
      if (sidebar.contains(ev.target) || botao.contains(ev.target)) return;
      app.classList.remove("is-sidebar-expanded");
      atualizarAria();
    });

    /* Gaveta: foco preso enquanto aberta */
    sidebar.addEventListener("keydown", function (ev) {
      if (ev.key !== "Tab" || !app.classList.contains("is-drawer-open")) return;
      var focaveis = Array.prototype.filter.call(sidebar.querySelectorAll("a[href], button"), function (n) { return n.offsetParent !== null; });
      if (!focaveis.length) return;
      var primeiro = focaveis[0], ultimo = focaveis[focaveis.length - 1];
      if (ev.shiftKey && document.activeElement === primeiro) { ev.preventDefault(); ultimo.focus(); }
      else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primeiro.focus(); }
    });

    /* Grupos: no trilho navegam para a primeira tela; expandidos abrem e fecham */
    Array.prototype.forEach.call(sidebar.querySelectorAll(".nav-group__head"), function (cab) {
      cab.addEventListener("click", function () {
        if (emTrilho()) { window.location.href = cab.getAttribute("data-primeiro"); return; }
        var grupo = cab.parentNode;
        var aberto = grupo.classList.toggle("is-open");
        cab.setAttribute("aria-expanded", aberto ? "true" : "false");
      });
    });

    /* Mudança de faixa: limpa estados que não se aplicam */
    function aoMudarFaixa() {
      if (!mqMobile.matches) fecharGaveta(false);
      if (!mqTablet.matches) app.classList.remove("is-sidebar-expanded");
      atualizarAria();
    }
    if (mqMobile.addEventListener) { mqMobile.addEventListener("change", aoMudarFaixa); mqTablet.addEventListener("change", aoMudarFaixa); }
    else { mqMobile.addListener(aoMudarFaixa); mqTablet.addListener(aoMudarFaixa); }
    atualizarAria();
  }

  GI.layout = { nav: NAV, montar: montar, localizar: localizar, detalhe: detalhe, ajustarBarra: ajustarBarra, rotuloEscopo: rotuloEscopo,
    trocarEscopo: function (valor) { trocarEscopo(valor == null ? "portfolio" : String(valor), localAtual, raizAtual); } };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", montar);
  else montar();
})(window.GI = window.GI || {});
