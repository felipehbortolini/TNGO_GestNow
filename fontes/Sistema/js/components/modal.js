/* ==========================================================================
   modal.js | Modais acessíveis (ESC, clique no fundo, foco preso, retorno de foco)

   Marcação esperada:
     <div class="modal" id="m-exemplo" hidden>
       <div class="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="m-exemplo-t">
         <header class="modal__header"><h2 class="modal__title" id="m-exemplo-t">...</h2>
           <button class="btn btn--ghost btn--icon" data-modal-close aria-label="Fechar">...</button></header>
         <div class="modal__body">...</div>
         <footer class="modal__footer">...</footer>
       </div>
     </div>

   Gatilhos declarativos:  data-modal-open="m-exemplo"  |  data-modal-close
   API:  GI.modal.open(idOuElemento) | GI.modal.close(idOuElemento)
         GI.modal.confirm({ title, message, okText, cancelText, danger }) -> Promise<boolean>
         GI.modal.create({ title, subtitle, size, body, buttons }) -> { el, close }
   Atributo data-static no .modal impede fechar ao clicar no fundo.
   ========================================================================== */
(function (GI) {
  "use strict";

  var FOCAVEIS = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
                 'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  var pilha = [];   // modais abertos, o último é o do topo
  var seq = 0;

  function resolver(alvo) {
    return typeof alvo === "string" ? document.getElementById(alvo) : alvo;
  }

  function focaveis(el) {
    return Array.prototype.filter.call(el.querySelectorAll(FOCAVEIS), function (n) {
      return n.offsetParent !== null || n === document.activeElement;
    });
  }

  function open(alvo, origem) {
    var el = resolver(alvo);
    if (!el || el.classList.contains("is-open")) return el;
    el._origemFoco = origem || document.activeElement;
    el.hidden = false;
    el.classList.add("is-open");
    document.body.classList.add("has-modal");
    pilha.push(el);

    // Foco no primeiro campo do corpo; se não houver, no próprio diálogo
    var corpo = el.querySelector(".modal__body");
    var alvoFoco = (corpo && focaveis(corpo)[0]) || focaveis(el)[0];
    var dialogo = el.querySelector(".modal__dialog");
    if (alvoFoco) alvoFoco.focus();
    else if (dialogo) { dialogo.setAttribute("tabindex", "-1"); dialogo.focus(); }

    el.dispatchEvent(new CustomEvent("modal:open", { bubbles: true }));
    return el;
  }

  function close(alvo) {
    var el = alvo ? resolver(alvo) : pilha[pilha.length - 1];
    if (!el || !el.classList.contains("is-open")) return;
    el.classList.remove("is-open");
    el.hidden = true;
    pilha = pilha.filter(function (m) { return m !== el; });
    if (!pilha.length) document.body.classList.remove("has-modal");
    el.dispatchEvent(new CustomEvent("modal:close", { bubbles: true }));
    var origem = el._origemFoco;
    if (origem && typeof origem.focus === "function" && document.contains(origem)) origem.focus();
    if (el.hasAttribute("data-temporario")) el.parentNode.removeChild(el);
  }

  /* Delegação de eventos (uma vez para a página toda) */
  document.addEventListener("click", function (ev) {
    var abrir = ev.target.closest("[data-modal-open]");
    if (abrir) { ev.preventDefault(); open(abrir.getAttribute("data-modal-open"), abrir); return; }

    var fechar = ev.target.closest("[data-modal-close]");
    if (fechar) { ev.preventDefault(); close(fechar.closest(".modal")); return; }

    if (ev.target.classList && ev.target.classList.contains("modal") &&
        ev.target.classList.contains("is-open") && !ev.target.hasAttribute("data-static")) {
      close(ev.target);
    }
  });

  document.addEventListener("keydown", function (ev) {
    var topo = pilha[pilha.length - 1];
    if (!topo) return;
    if (ev.key === "Escape" && !topo.hasAttribute("data-static")) { ev.preventDefault(); close(topo); return; }
    if (ev.key !== "Tab") return;
    var lista = focaveis(topo);
    if (!lista.length) { ev.preventDefault(); return; }
    var primeiro = lista[0], ultimo = lista[lista.length - 1];
    if (ev.shiftKey && document.activeElement === primeiro) { ev.preventDefault(); ultimo.focus(); }
    else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primeiro.focus(); }
  });

  function escapar(txt) {
    return String(txt == null ? "" : txt).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Cria um modal temporário (removido do DOM ao fechar) */
  function create(cfg) {
    cfg = cfg || {};
    var id = "gi-modal-" + (++seq);
    var el = document.createElement("div");
    el.className = "modal";
    el.id = id;
    el.hidden = true;
    el.setAttribute("data-temporario", "");
    var tamanho = cfg.size ? " modal__dialog--" + cfg.size : "";
    var fecharIcone = GI.icons ? GI.icons.svg("x") : "×";
    el.innerHTML =
      '<div class="modal__dialog' + tamanho + '" role="dialog" aria-modal="true" aria-labelledby="' + id + '-t">' +
        '<header class="modal__header"><h2 class="modal__title" id="' + id + '-t">' + escapar(cfg.title) +
          (cfg.subtitle ? '<span class="modal__subtitle">' + escapar(cfg.subtitle) + "</span>" : "") + "</h2>" +
          '<button type="button" class="btn btn--ghost btn--icon" data-modal-close aria-label="Fechar">' + fecharIcone + "</button>" +
        "</header>" +
        '<div class="modal__body"></div>' +
        '<footer class="modal__footer"></footer>' +
      "</div>";
    var corpo = el.querySelector(".modal__body");
    if (typeof cfg.body === "string") corpo.innerHTML = cfg.body;
    else if (cfg.body) corpo.appendChild(cfg.body);

    var rodape = el.querySelector(".modal__footer");
    (cfg.buttons || []).forEach(function (b) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn " + (b.variant ? "btn--" + b.variant : "btn--secondary");
      btn.textContent = b.label;
      btn.addEventListener("click", function () { if (b.onClick) b.onClick(api); else close(el); });
      rodape.appendChild(btn);
    });
    if (!rodape.children.length) rodape.parentNode.removeChild(rodape);

    document.body.appendChild(el);
    var api = { el: el, close: function () { close(el); } };
    open(el);
    return api;
  }

  function confirm(cfg) {
    cfg = cfg || {};
    return new Promise(function (resolve) {
      var respondeu = false;
      var m = create({
        title: cfg.title || "Confirmar",
        size: "sm",
        body: "<p>" + escapar(cfg.message || "Deseja continuar?") + "</p>",
        buttons: [
          { label: cfg.cancelText || "Cancelar", variant: "secondary", onClick: function (api) { respondeu = true; resolve(false); api.close(); } },
          { label: cfg.okText || "Confirmar", variant: cfg.danger ? "danger" : "primary", onClick: function (api) { respondeu = true; resolve(true); api.close(); } }
        ]
      });
      m.el.addEventListener("modal:close", function () { if (!respondeu) resolve(false); });
    });
  }

  GI.modal = { open: open, close: close, create: create, confirm: confirm };
})(window.GI = window.GI || {});
