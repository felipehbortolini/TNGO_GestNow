/* ============================================================
   eac.js — Comportamento da tela EAC (financeiro/eac)

   Árvore da Estrutura Analítica de Custos, com as revisões do orçamento, os
   remanejamentos e a importação de itens.

   Registra um único objeto em TN.paginas["financeiro/eac"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, vazio-origem, vazio-filtro, erro ou sem-permissao) mora
   no x-data da view e vem do marcador data-resultado que o servidor põe no
   conteúdo; 403 vira sem-permissao e qualquer outra falha vira erro.

   Também cuida de recolher e expandir a árvore (os totais já vêm somados do
   servidor, aqui só se esconde linha), de manter os links de Excel e PDF com
   os mesmos filtros que a tela mostra, de abrir e fechar os formulários dos
   painéis (que vêm do servidor e nascem fechados), de sincronizar os filtros
   escondidos neles, das dicas de saldo livre e de próximo código, e do modal da
   importação, em que a conferência e a confirmação acontecem sem sair da tela.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem", "vazio-filtro"];
  const ROTA_IMPORTACAO = "/api/financeiro/eac/revisoes/importar/formulario";
  const CONFIRMACAO_DA_IMPORTACAO = "/importar/confirmar";
  const ALVO_DO_MODAL = "eac-importar-modal";
  const LARGURA_DO_MODAL = 820;

  let modalImportacao = null;

  function definirEstado(raiz, estado) {
    window.Alpine.$data(raiz).estado = estado;
  }

  function filhas(tabela, codigo) {
    const linhas = Array.prototype.slice.call(tabela.querySelectorAll("tr[data-codigo]"));
    return linhas.filter(function (linha) {
      const c = linha.getAttribute("data-codigo");
      if (c === codigo) return false;
      return codigo === "0" || c.indexOf(codigo + ".") === 0;
    });
  }

  function alternar(botao) {
    const tabela = botao.closest("table");
    const codigo = botao.getAttribute("data-alternar");
    const recolher = botao.getAttribute("aria-expanded") === "true";
    botao.setAttribute("aria-expanded", recolher ? "false" : "true");
    const rotulo = (recolher ? "Expandir " : "Recolher ") + codigo;
    botao.setAttribute("aria-label", rotulo);
    botao.setAttribute("title", rotulo);
    filhas(tabela, codigo).forEach(function (linha) {
      linha.hidden = recolher;
      const proprio = linha.querySelector("[data-alternar]");
      if (proprio) {
        // Ao expandir um pai, os descendentes voltam abertos.
        proprio.setAttribute("aria-expanded", "true");
      }
    });
  }

  function atualizarExportacao(raiz) {
    const form = raiz.querySelector("[data-filtros]");
    if (!form) return;
    const consulta = new URLSearchParams(new FormData(form)).toString();
    raiz.querySelectorAll("[data-exportar]").forEach(function (link) {
      const base = link.getAttribute("href").split("?")[0];
      link.setAttribute("href", consulta ? base + "?" + consulta : base);
    });
  }

  function sincronizarFiltros(raiz) {
    const filtros = raiz.querySelector("[data-filtros]");
    if (!filtros) return;
    const dados = new FormData(filtros);
    raiz.querySelectorAll("[data-filtros-ocultos] input").forEach(function (campo) {
      const valor = dados.get(campo.getAttribute("name"));
      campo.value = valor == null ? "" : valor;
    });
  }

  function consultaDosFiltros(raiz) {
    const filtros = raiz.querySelector("[data-filtros]");
    if (!filtros) return "";
    return new URLSearchParams(new FormData(filtros)).toString();
  }

  function alternarFormulario(raiz, botao) {
    const alvo = document.getElementById(botao.getAttribute("data-eac-form"));
    if (!alvo) return;
    const abrindo = alvo.hasAttribute("hidden");
    raiz.querySelectorAll(".eac-form").forEach(function (form) {
      form.setAttribute("hidden", "");
    });
    raiz.querySelectorAll("[data-eac-form]").forEach(function (outro) {
      outro.setAttribute("aria-expanded", "false");
    });
    if (!abrindo) return;
    alvo.removeAttribute("hidden");
    botao.setAttribute("aria-expanded", "true");
    const primeiro = alvo.querySelector("select, input, textarea");
    if (primeiro) primeiro.focus();
    alvo.scrollIntoView({ block: "nearest" });
  }

  function fecharFormulario(raiz, form) {
    if (!form) return;
    form.setAttribute("hidden", "");
    form.reset();
    raiz.querySelectorAll("[data-eac-form='" + form.id + "']").forEach(function (outro) {
      outro.setAttribute("aria-expanded", "false");
    });
  }

  function atualizarSaldo(select) {
    const dica = document.getElementById(select.getAttribute("data-eac-saldo"));
    if (!dica) return;
    const opcao = select.options[select.selectedIndex];
    const saldo = opcao ? opcao.getAttribute("data-saldo") : "";
    dica.textContent = saldo
      ? "Saldo livre na origem: " + saldo + "."
      : "Só entram os itens com saldo livre; ele desconta o reservado em outras SMs abertas.";
  }

  function atualizarCodigo(select) {
    const campo = document.getElementById(select.getAttribute("data-eac-pai"));
    if (!campo) return;
    const opcao = select.options[select.selectedIndex];
    const sugerido = opcao ? opcao.getAttribute("data-proximo") || "" : "";
    if (!sugerido) return;
    const anterior = campo.getAttribute("data-eac-sugerido") || "";
    if (!campo.value || campo.value === anterior) {
      campo.value = sugerido;
      campo.setAttribute("data-eac-sugerido", sugerido);
    }
  }

  function fecharModal() {
    if (modalImportacao) modalImportacao.close();
    modalImportacao = null;
  }

  function abrirImportacao(raiz) {
    const consulta = consultaDosFiltros(raiz);
    const endereco = ROTA_IMPORTACAO + (consulta ? "?" + consulta : "");
    fecharModal();
    modalImportacao = window.TN.modal({
      title: "Importar itens da EAC",
      subtitle: "Itens de custo (nível 3) em subpacotes existentes; a importação gera uma revisão",
      width: LARGURA_DO_MODAL,
      onClose: function () { modalImportacao = null; },
      body: '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
        " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando a importação"></div></div>'
    });
  }

  function aoResponder(raiz) {
    const marcador = raiz.querySelector("[data-resultado]");
    if (!marcador) return;
    const resultado = marcador.getAttribute("data-resultado");
    definirEstado(raiz, ESTADOS_DE_RESULTADO.indexOf(resultado) >= 0 ? resultado : "erro");
    atualizarExportacao(raiz);
  }

  function aoClicar(raiz, evento) {
    const botaoAlternar = evento.target.closest("[data-alternar]");
    if (botaoAlternar && raiz.contains(botaoAlternar)) {
      alternar(botaoAlternar);
      return;
    }
    const abrir = evento.target.closest("[data-eac-form]");
    if (abrir) {
      alternarFormulario(raiz, abrir);
      return;
    }
    const fechar = evento.target.closest("[data-eac-fechar]");
    if (fechar) {
      fecharFormulario(raiz, fechar.closest(".eac-form"));
      return;
    }
    if (evento.target.closest("[data-eac-importar]")) abrirImportacao(raiz);
  }

  function aoMudar(raiz, evento) {
    const campo = evento.target;
    atualizarExportacao(raiz);
    sincronizarFiltros(raiz);
    if (campo.hasAttribute && campo.hasAttribute("data-eac-saldo")) atualizarSaldo(campo);
    if (campo.hasAttribute && campo.hasAttribute("data-eac-pai")) atualizarCodigo(campo);
  }

  function aoConcluir(raiz, evento) {
    const url = (evento.detail && evento.detail.url) || "";
    const alvo = evento.target;
    if (alvo instanceof Element && alvo.classList.contains("eac-form")) {
      fecharFormulario(raiz, alvo);
    }
    window.setTimeout(function () { aoResponder(raiz); }, 0);
    if (url.indexOf(CONFIRMACAO_DA_IMPORTACAO) >= 0) fecharModal();
  }

  window.TN.paginas["financeiro/eac"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");

      raiz.addEventListener("ajax:success", function (e) {
        aoConcluir(raiz, e);
      });

      raiz.addEventListener("ajax:error", function (e) {
        const status = e.detail && e.detail.status;
        if (status === 403) definirEstado(raiz, "sem-permissao");
        else if (status !== 422 && status !== 409) definirEstado(raiz, "erro");
      });

      raiz.addEventListener("click", function (e) {
        aoClicar(raiz, e);
      });

      raiz.addEventListener("change", function (e) {
        aoMudar(raiz, e);
      });
    }
  };
})();
