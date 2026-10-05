/* ============================================================
   ui.js — Componentes imperativos do Timenow Design System
   Toast, modal, confirmação, guarda de saída, loading e helpers.

   Portado de Projeto_Piloto/js/ui.js + js/modals.js em 13/08/2026.
   O que mudou em relação à origem:
     - namespace global unificado em TN. O prefixo anterior era a sigla
       de um app específico ("Central de Ações e Atas") e não cabia em
       um kit que serve a qualquer projeto.
     - assets por nome semântico e caminho absoluto, não mais por UUID
     - só o que serve a qualquer app: modais de ata, participante,
       reincidência e filtro ficaram no Piloto de propósito

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const $ = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  const $$ = function (sel, ctx) {
    return Array.prototype.slice.call((ctx || document).querySelectorAll(sel));
  };

  /* Contador para gerar id único de título de modal — dois diálogos
     empilhados não podem disputar o mesmo id. */
  let _seqModal = 0;

  const TN = {
    $: $,
    $$: $$,

    /* Registro das páginas (D3): cada app/paginas/<modulo>/<tela>.js se registra
       em TN.paginas["<modulo>/<tela>"] com iniciar(raiz), e a view o aciona por
       x-init. Nasce aqui para existir quando o primeiro desses scripts rodar. */
    paginas: {},

    /* icons.js define window.icon; é carregado antes deste arquivo */
    icon: function (nome, tamanho, classe) {
      return typeof window.icon === "function" ? window.icon(nome, tamanho, classe) : "";
    },

    esc: function (s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    },

    /* ---------- Formatação ---------- */

    fmtDate: function (d, comHora) {
      if (!d) return "";
      const dt = new Date(d);
      if (isNaN(dt)) return "";
      const dd = String(dt.getDate()).padStart(2, "0");
      const mm = String(dt.getMonth() + 1).padStart(2, "0");
      const yyyy = dt.getFullYear();
      if (comHora) {
        const hh = String(dt.getHours()).padStart(2, "0");
        const mi = String(dt.getMinutes()).padStart(2, "0");
        return dd + "/" + mm + "/" + yyyy + " " + hh + ":" + mi;
      }
      return dd + "/" + mm + "/" + yyyy;
    },

    fmtMesAno: function (mes, ano) {
      const nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
      return nomes[mes - 1] + " de " + ano;
    },

    /* ---------- Avatar ---------- */

    avatar: function (nome, tamanho = 36) {
      let iniciais = "?";
      if (nome && String(nome).trim()) {
        const partes = String(nome).trim().split(/\s+/);
        iniciais = (partes[0][0] + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
      }
      const cores = ["#E6F8F4", "#E9F3F9", "#FDF8E5", "#F1EBF7", "#F0F4F6", "#FAEBEB"];
      let h = 0;
      for (let i = 0; i < String(nome).length; i++) {
        h = (h + String(nome).charCodeAt(i)) % cores.length;
      }
      return '<div class="avatar" style="width:' + tamanho + "px;height:" + tamanho +
        "px;font-size:" + Math.round(tamanho / 3) + "px;background:" + cores[h] + '">' +
        this.esc(iniciais) + "</div>";
    },

    /* ---------- Toast ---------- */

    toast: function (msg, tipo) {
      const root = $("#toast-root");
      if (!root) return;

      /* Mapa em vez de ternário aninhado: com três variantes o encadeamento
         já obriga a ler da direita para a esquerda, e a quarta pioraria. */
      const VARIANTES = { erro: " toast--erro", aviso: " toast--aviso" };

      const el = document.createElement("div");
      el.className = "toast" + (VARIANTES[tipo] || "");
      el.innerHTML = (tipo === "erro" ? this.icon("errorCircle", 18) : this.icon("checkCircle", 18)) +
        "<span>" + this.esc(msg) + "</span>";
      root.appendChild(el);
      setTimeout(function () { el.classList.add("is-out"); }, 3200);
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 3600);
    },

    /* ---------- Overlay de carregamento ---------- */

    loading: function (mostrar, msg) {
      const prev = $("#overlay-loading");
      if (prev) prev.remove();
      if (!mostrar) return;
      const el = document.createElement("div");
      el.id = "overlay-loading";
      el.className = "overlay";
      el.setAttribute("role", "status");
      el.setAttribute("aria-live", "polite");
      el.innerHTML =
        '<img src="/ds/assets/loading-pequeno.gif" alt="" style="width:120px;height:120px"/>' +
        '<p class="overlay-msg">' + this.esc(msg || "Aguarde...") + "</p>";
      document.body.appendChild(el);
    },

    /* ---------- Modal genérico ---------- */

    modal: function (opts) {
      const o = opts || {};
      o.width = o.width || 600;
      o.title = o.title || "";
      o.subtitle = o.subtitle || "";
      o.body = o.body || "";

      const anterior = document.activeElement;

      /* Nome acessível do diálogo. Sem isto o leitor de tela anuncia só
         "diálogo" e a pessoa não sabe o que abriu — é o que o axe aponta
         como aria-dialog-name, de impacto sério.

         Com título visível, aponta para ele por aria-labelledby: o nome
         falado passa a ser o mesmo que está na tela. Sem título — caso da
         guarda de saída — cai num aria-label descritivo. */
      _seqModal += 1;
      const idTitulo = "tn-modal-titulo-" + _seqModal;
      const rotulo = o.title
        ? ' aria-labelledby="' + idTitulo + '"'
        : ' aria-label="' + this.esc(o.ariaLabel || "Confirmação") + '"';

      const root = document.createElement("div");
      root.className = "modal-backdrop";
      root.innerHTML =
        '<div class="modal modal--gen" role="dialog" aria-modal="true"' + rotulo +
        ' style="max-width:' + (o.width + 64) + 'px">' +
        '<div class="modal__head">' +
        '<div><h2 class="modal__title" id="' + idTitulo + '">' + this.esc(o.title) + "</h2>" +
        (o.subtitle ? '<p class="modal__subtitle">' + this.esc(o.subtitle) + "</p>" : "") + "</div>" +
        '<button class="iconbtn modal__close" type="button" aria-label="Fechar">' + this.icon("dismiss", 18) + "</button>" +
        "</div>" +
        '<div class="modal__body">' + o.body + "</div>" +
        "</div>";

      (document.getElementById("modal-root") || document.body).appendChild(root);

      const fechar = function () {
        if (o.onClose && o.onClose() === false) return;
        root.classList.add("is-out");
        document.removeEventListener("keydown", onKey);
        setTimeout(function () {
          if (root.parentNode) root.parentNode.removeChild(root);
          if (anterior && anterior.focus) anterior.focus();
        }, 200);
      };

      /* Esc fecha — faltava na versão do Piloto */
      function onKey(e) { if (e.key === "Escape") fechar(); }
      document.addEventListener("keydown", onKey);

      root.querySelector(".modal__close").addEventListener("click", fechar);
      if (o.onBackdrop !== false) {
        root.addEventListener("click", function (e) { if (e.target === root) fechar(); });
      }

      const foco = root.querySelector("input, select, textarea, button:not(.modal__close)");
      if (foco) foco.focus();

      return { el: root, close: fechar, body: root.querySelector(".modal__body") };
    },

    /* ---------- Confirmação ---------- */

    confirm: function (opts) {
      const o = opts || {};
      let rows = "";
      (o.rows || []).forEach(function (r) {
        rows += '<div class="conf__row"><span class="conf__label">' + this.esc(r.label) + "</span>" +
          '<span class="conf__valor">' + this.esc(r.valor) + "</span></div>";
      }, this);

      const m = this.modal({
        title: o.title || "Confirmação",
        subtitle: o.subtitle || "",
        width: 600,
        onClose: o.onClose,
        body: '<div class="conf">' +
          (o.mensagem !== "" ? '<p class="conf__msg">' + this.esc(o.mensagem || "Você confirma a exclusão?") + "</p>" : "") +
          (rows ? '<div class="conf__destaque">' + rows + "</div>" : "") +
          '<div class="modal__actions">' +
          '<button type="button" class="btn btn--secondary" data-acao="cancelar">Não, cancelar</button>' +
          '<button type="button" class="btn btn--danger" data-acao="confirmar">' +
          this.esc(o.labelConfirmar || "Excluir") + "</button></div></div>"
      });

      m.body.querySelector('[data-acao="cancelar"]').addEventListener("click", function () {
        m.close(); if (o.onCancel) o.onCancel();
      });
      m.body.querySelector('[data-acao="confirmar"]').addEventListener("click", function () {
        if (o.onConfirm) o.onConfirm(); m.close();
      });

      return m;
    },

    /* Versão em Promise — resolve(true) confirma, resolve(false) cancela */
    confirmarExclusao: function (opts) {
      const o = opts || {};
      const self = this;
      return new Promise(function (resolve) {
        self.confirm({
          title: o.title || "Confirmação de Exclusão",
          mensagem: o.mensagem || "Você confirma a exclusão do item abaixo?",
          rows: o.rows || [],
          labelConfirmar: o.labelConfirmar || "Excluir",
          onConfirm: function () { resolve(true); },
          onCancel: function () { resolve(false); },
          onClose: function () { resolve(false); }
        });
      });
    },

    /* Guarda de saída com dados não salvos.
       resolve(true) = sair sem salvar | resolve(false) = continuar editando */
    confirmarSaida: function (mensagem) {
      const self = this;
      return new Promise(function (resolve) {
        const m = self.modal({
          title: "",
          /* Sem título visível, o nome acessível vem daqui — senão o leitor
             de tela anuncia só "diálogo". */
          ariaLabel: "Sair sem salvar as alterações",
          width: 600,
          onBackdrop: false,
          onClose: function () { resolve(false); },
          body:
            '<div class="guard-center">' +
            '<img src="/ds/assets/ilustra-aviso.png" alt="" style="width:200px"/>' +
            '<p class="conf__msg guard-msg">' +
            self.esc(mensagem || "Se você sair agora, os dados preenchidos serão perdidos.") +
            "</p>" +
            '<div class="modal__actions">' +
            '<button type="button" class="btn btn--danger" data-g="sair">Sair sem salvar</button>' +
            '<button type="button" class="btn btn--primary" data-g="ficar">Continuar editando</button>' +
            "</div></div>"
        });
        m.body.querySelector('[data-g="sair"]').addEventListener("click", function () { m.close(); resolve(true); });
        m.body.querySelector('[data-g="ficar"]').addEventListener("click", function () { m.close(); resolve(false); });
      });
    },

    /* ---------- Detalhes em tabela ---------- */

    detalhesTabela: function (linhas, opts) {
      const o = opts || {};
      let rows = "";
      (linhas || []).forEach(function (l) {
        rows += '<div class="det__row"><span class="det__label">' + this.esc(l.label) + "</span>" +
          '<span class="det__valor">' + this.esc(l.valor) + "</span></div>";
      }, this);
      return this.modal({
        title: o.title || "Detalhes",
        subtitle: o.subtitle || "",
        width: 600,
        onClose: o.onClose,
        body: '<div class="det">' + rows + "</div>"
      });
    },

    /* ---------- Pills ---------- */

    pill: function (texto, variante) {
      return '<span class="pill pill--' + this.esc(variante || "neutral") + '">' + this.esc(texto) + "</span>";
    },

    selecionarTexto: function () {
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return false;
      return sel.toString().trim() !== "";
    }
  };

  window.TN = TN;

  /* ============================================================
     Ponte com o Alpine AJAX

     No modelo hipermídia o servidor devolve fragmentos; o feedback ao
     usuário é disparado por evento, não por chamada imperativa da página.
     O servidor pede a ação por cabeçalho de resposta:

       X-TN-Toast: mensagem (percent-encoded, por causa de acento)
       X-TN-Toast-Tipo: ok | erro | aviso

     Contrato dos eventos do Alpine AJAX 0.12.7, verificado no navegador:

       ajax:before   detail = null
       ajax:success  detail = { ok, redirected, url, status, html, raw, headers }
       ajax:sent     idem — dispara por último, mesmo em caso de erro
       ajax:error    idem — dispara em QUALQUER status fora da faixa 2xx,
                     inclusive no 422 de validação, não só em falha de rede

     `headers` é um objeto Headers nativo: só responde a .get(). Não existe
     `detail.xhr` nem evento `ajax:after`.
     ============================================================ */

  function lerCabecalho(detalhe, nome) {
    const h = detalhe && detalhe.headers;
    if (!h) return null;
    if (typeof h.get === "function") return h.get(nome);
    return h[nome] || h[nome.toLowerCase()] || null;
  }

  document.addEventListener("ajax:success", function (e) {
    let msg = lerCabecalho(e.detail, "X-TN-Toast");
    if (!msg) return;
    const tipo = lerCabecalho(e.detail, "X-TN-Toast-Tipo") || "ok";
    try {
      msg = decodeURIComponent(msg);
    } catch {
      /* mensagem não codificada — usa como veio */
    }
    TN.toast(msg, tipo);
  });

  /* Falha que o servidor NÃO tratou.

     O ajax:error dispara em todo status fora de 2xx, inclusive no 422 de
     validação — e ali o formulário já volta com a mensagem em cada campo.
     Um toast vermelho por cima disso é ruído, então 4xx fica de fora: são
     respostas que o servidor desenhou e que já se explicam na tela.

     Sobram falha de rede (status 0 ou ausente) e erro de servidor (5xx),
     onde a pessoa não recebe nenhuma outra pista do que aconteceu. */
  document.addEventListener("ajax:error", function (e) {
    const status = (e.detail && e.detail.status) || 0;
    if (status >= 400 && status < 500) return;
    TN.toast("Não foi possível concluir a operação. Tente novamente.", "erro");
  });

  /* Overlay durante requisições demoradas */
  document.addEventListener("ajax:before", function (e) {
    const alvo = e.target && e.target.closest && e.target.closest("[data-tn-loading]");
    if (alvo) TN.loading(true, alvo.getAttribute("data-tn-loading") || "Aguarde...");
  });

  /* ajax:sent é o último a disparar, inclusive quando dá erro */
  document.addEventListener("ajax:sent", function () { TN.loading(false); });
  document.addEventListener("ajax:error", function () { TN.loading(false); });
})();
