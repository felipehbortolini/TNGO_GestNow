/* ==========================================================================
   ui.js | Comportamentos genéricos: abas, controle segmentado, toasts,
   contador de caracteres e formatação pt-BR.

   Abas:        <div class="tabs" role="tablist" data-tabs>
                  <button class="tab" role="tab" aria-selected="true" aria-controls="p1">...</button>
                </div>
                <section class="tab-panel" id="p1" role="tabpanel">...</section>
   Segmentado:  <div class="segmented" data-segmented>
                  <button class="segmented__opt" aria-pressed="true" data-value="a">A</button>
                </div>   (dispara "segmented:change" com detail.value)
   Contador:    <textarea id="x" maxlength="150" data-counter></textarea>
                <span class="field__counter" data-counter-for="x"></span>
   Toast:       GI.ui.toast("Mensagem", "success" | "danger" | "warning" | "info")
   Formatação:  GI.fmt.moeda(centavos) | GI.fmt.moedaCompacta(centavos) | GI.fmt.indice(v)
                GI.fmt.pct(valor, casas) | GI.fmt.num(valor, casas) | GI.fmt.data(dataIsoOuDate)
   ========================================================================== */
(function (GI) {
  "use strict";

  /* ---------------- Abas ---------------- */
  function selecionarAba(tab) {
    var lista = tab.closest("[data-tabs]");
    if (!lista) return;
    Array.prototype.forEach.call(lista.querySelectorAll('[role="tab"]'), function (t) {
      var ativa = t === tab;
      t.setAttribute("aria-selected", ativa ? "true" : "false");
      t.setAttribute("tabindex", ativa ? "0" : "-1");
      t.classList.toggle("is-active", ativa);
      var painel = document.getElementById(t.getAttribute("aria-controls"));
      if (painel) painel.hidden = !ativa;
    });
    lista.dispatchEvent(new CustomEvent("tabs:change", { bubbles: true, detail: { id: tab.getAttribute("aria-controls") } }));
  }

  document.addEventListener("click", function (ev) {
    var tab = ev.target.closest('[data-tabs] [role="tab"]');
    if (tab) { selecionarAba(tab); return; }

    var opt = ev.target.closest("[data-segmented] .segmented__opt");
    if (opt) {
      var grupo = opt.closest("[data-segmented]");
      Array.prototype.forEach.call(grupo.querySelectorAll(".segmented__opt"), function (o) {
        o.setAttribute("aria-pressed", o === opt ? "true" : "false");
      });
      grupo.dispatchEvent(new CustomEvent("segmented:change", { bubbles: true, detail: { value: opt.getAttribute("data-value") } }));
    }
  });

  document.addEventListener("keydown", function (ev) {
    var tab = ev.target.closest && ev.target.closest('[data-tabs] [role="tab"]');
    if (!tab || (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft")) return;
    var abas = Array.prototype.slice.call(tab.closest("[data-tabs]").querySelectorAll('[role="tab"]'));
    var i = abas.indexOf(tab) + (ev.key === "ArrowRight" ? 1 : -1);
    var prox = abas[(i + abas.length) % abas.length];
    prox.focus();
    selecionarAba(prox);
  });

  /* ---------------- Contador de caracteres ---------------- */
  function atualizarContador(campo) {
    var alvo = document.querySelector('[data-counter-for="' + campo.id + '"]');
    if (!alvo) return;
    var max = parseInt(campo.getAttribute("maxlength"), 10) || 0;
    var n = campo.value.length;
    alvo.textContent = n + (max ? " / " + max : "");
    alvo.classList.toggle("is-limit", max > 0 && n >= max);
  }
  document.addEventListener("input", function (ev) {
    if (ev.target.hasAttribute && ev.target.hasAttribute("data-counter")) atualizarContador(ev.target);
  });

  /* ---------------- Toasts ---------------- */
  var ICONE_TOAST = { success: "checkCircle", danger: "alertTriangle", warning: "alertCircle", info: "info" };

  function toast(mensagem, tipo, duracao) {
    tipo = tipo || "info";
    var pilha = document.querySelector(".toast-stack");
    if (!pilha) {
      pilha = document.createElement("div");
      pilha.className = "toast-stack";
      pilha.setAttribute("role", "status");
      pilha.setAttribute("aria-live", "polite");
      document.body.appendChild(pilha);
    }
    var el = document.createElement("div");
    el.className = "toast toast--" + tipo;
    var icone = GI.icons ? GI.icons.svg(ICONE_TOAST[tipo] || "info") : "";
    var fechar = GI.icons ? GI.icons.svg("x") : "×";
    el.innerHTML = icone + '<div class="toast__text"></div>' +
      '<button type="button" class="btn btn--ghost btn--icon btn--sm" aria-label="Fechar aviso">' + fechar + "</button>";
    el.querySelector(".toast__text").textContent = mensagem;
    el.querySelector("button").addEventListener("click", function () { remover(); });
    pilha.appendChild(el);
    var t = setTimeout(remover, duracao || 4500);
    function remover() { clearTimeout(t); if (el.parentNode) el.parentNode.removeChild(el); }
    return el;
  }

  /* ---------------- Formatação pt-BR ---------------- */
  var fmtMoeda = new Intl.NumberFormat((GI.i18n ? GI.i18n.locale : "pt-BR"), { style: "currency", currency: "BRL" });
  var fmtMoedaCompacta = new Intl.NumberFormat((GI.i18n ? GI.i18n.locale : "pt-BR"), { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
  var fmt = {
    /* Valores financeiros trafegam em centavos (inteiros): 1050 -> "R$ 10,50" */
    moeda: function (centavos) {
      if (centavos == null || centavos === "") return "";
      return fmtMoeda.format(Math.round(Number(centavos)) / 100);
    },
    /* Resumos e KPIs: 4525500000 -> "R$ 45,3 mi" */
    moedaCompacta: function (centavos) {
      if (centavos == null || centavos === "") return "";
      return fmtMoedaCompacta.format(Math.round(Number(centavos)) / 100);
    },
    /* KPIs: 4460000000 -> { moeda: "R$", numero: "44,6", escala: "mi" } (sinal: +/- explícito) */
    moedaPartes: function (centavos, sinal) {
      var r = { moeda: "", numero: "", escala: "" };
      new Intl.NumberFormat((GI.i18n ? GI.i18n.locale : "pt-BR"), { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1,
        signDisplay: sinal ? "exceptZero" : "auto" }).formatToParts(Math.round(Number(centavos) || 0) / 100).forEach(function (p) {
        if (p.type === "currency") r.moeda += p.value;
        else if (p.type === "compact") r.escala += p.value;
        else if (p.type !== "literal") r.numero += p.value;
      });
      return r;
    },
    /* Índices (CPI, SPI): 0.96 -> "0,96" */
    indice: function (v) {
      if (v == null || isNaN(v)) return "";
      return Number(v).toLocaleString((GI.i18n ? GI.i18n.locale : "pt-BR"), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
    num: function (v, casas) {
      if (v == null || v === "" || isNaN(v)) return "";
      casas = casas == null ? 0 : casas;
      return Number(v).toLocaleString((GI.i18n ? GI.i18n.locale : "pt-BR"), { minimumFractionDigits: casas, maximumFractionDigits: casas });
    },
    pct: function (v, casas) {
      if (v == null || v === "" || isNaN(v)) return "";
      return fmt.num(v, casas == null ? 1 : casas) + "%";
    },
    data: function (d) {
      if (!d) return "";
      var dt = d instanceof Date ? d : new Date(String(d).length === 10 ? d + "T00:00:00" : d);
      return isNaN(dt) ? String(d) : dt.toLocaleDateString((GI.i18n ? GI.i18n.locale : "pt-BR"));
    }
  };

  function init(root) {
    root = root || document;
    Array.prototype.forEach.call(root.querySelectorAll("[data-counter]"), atualizarContador);
    Array.prototype.forEach.call(root.querySelectorAll("[data-tabs]"), function (lista) {
      var ativa = lista.querySelector('[role="tab"][aria-selected="true"]') || lista.querySelector('[role="tab"]');
      if (ativa) selecionarAba(ativa);
    });
    if (GI.icons) GI.icons.hydrate(root);
  }

  GI.ui = { toast: toast, init: init, selecionarAba: selecionarAba };
  GI.fmt = fmt;
})(window.GI = window.GI || {});
