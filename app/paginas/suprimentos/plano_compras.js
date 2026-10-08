/* ============================================================
   plano_compras.js — Comportamento da tela Plano de compras (suprimentos/plano_compras)

   Pacotes do plano com datas da linha de base, ROS e vínculo à EAC (ISSUE-058).

   Registra um único objeto em TN.paginas["suprimentos/plano_compras"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   erro ou sem-permissao) mora no x-data da view; os estados vazio de origem e vazio por filtro
   vêm do servidor, dentro do fragmento. O servidor desenha tudo
   (api/src/templates/suprimentos/plano_compras.html): KPIs, busca, filtros, tabela e páginas são
   links ou um formulário GET com x-target. Aqui moram os modais que o Design System abre por
   JavaScript — Novo pacote, Editar pacote e a importação genérica de Excel —, cujo corpo o
   servidor entrega por GET no alvo do modal, a conta de prévia do saldo a comprometer e da folga
   planejada (o servidor revalida) e a ação pendente do mecanismo de inclusão do Portfólio
   (?acao=novo|importar, TN.escopo).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "pacote-modal-corpo";
  const LARGURA_DO_FORM = 880;
  const LARGURA_DA_IMPORTACAO = 880;
  const DIAS_DE_ALERTA = 7;

  let modalAberto = null;
  let importando = false;
  let acaoPendente = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector("main.pagina--suprimentos-plano_compras");
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function recarregarConteudo() {
    const raiz = raizDaTela();
    if (!raiz) return;
    const filtro = raiz.querySelector("#plano-compras-conteudo form.busca");
    if (filtro) filtro.requestSubmit();
    else window.Alpine.$data(raiz).carregar();
  }

  /* ---------- Modais ---------- */

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function abrirModal(opcoes) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo,
      width: opcoes.largura,
      onClose: function () {
        modalAberto = null;
        if (importando) {
          importando = false;
          recarregarConteudo();
        }
      },
      body: corpoCarregando(opcoes.endereco)
    });
  }

  function abrirEdicao(botao) {
    abrirModal({
      titulo: botao.dataset.pacoteModalTitulo,
      subtitulo: botao.dataset.pacoteModalSubtitulo,
      largura: LARGURA_DO_FORM,
      endereco: botao.dataset.pacoteModalUrl
    });
  }

  function abrirNovo(botao) {
    abrirModal({
      titulo: "Novo pacote de compra",
      subtitulo: "O saldo a comprometer do item da EAC e a folga planejada aparecem ao preencher",
      largura: LARGURA_DO_FORM,
      endereco: botao.dataset.pacoteUrl
    });
  }

  function abrirImportacao(botao) {
    importando = true;
    abrirModal({
      titulo: "Importar plano de compras",
      subtitulo: "Um pacote por linha; o código é gerado na importação e nada grava antes da confirmação",
      largura: LARGURA_DA_IMPORTACAO,
      endereco: botao.dataset.pacoteUrl
    });
  }

  function abrirAcaoPendente() {
    if (!acaoPendente) return;
    const raiz = raizDaTela();
    const botao = raiz && raiz.querySelector('[data-tn-incluir="' + acaoPendente + '"]');
    if (!botao) return;
    acaoPendente = null;
    botao.click();
  }

  /* ---------- A conta de prévia do formulário (o servidor revalida) ---------- */

  function centavos(texto) {
    const limpo = String(texto || "").replace(/[R$\s.]/g, "").replace(",", ".");
    if (!limpo) return null;
    const valor = Number(limpo);
    return Number.isFinite(valor) ? Math.round(valor * 100) : null;
  }

  function diasEntre(inicio, fim) {
    return Math.round(
      (new Date(fim + "T00:00:00") - new Date(inicio + "T00:00:00")) / 86400000
    );
  }

  function atualizarSaldo(formulario) {
    const alvo = formulario.querySelector("#pacote-saldo");
    const selecao = formulario.querySelector("#pacote-eac");
    if (!alvo || !selecao) return;
    const opcao = selecao.selectedOptions[0];
    if (!opcao || !opcao.value) {
      alvo.textContent = "Escolha o item da EAC.";
      return;
    }
    const estimativa = centavos(formulario.elements.estimativa ? formulario.elements.estimativa.value : "");
    const saldo = Number(opcao.dataset.saldoCentavos || 0);
    const saldoTexto = "Saldo a comprometer: " + (opcao.dataset.saldo || "—");
    if (estimativa !== null && estimativa > saldo) {
      alvo.textContent = saldoTexto + " — a estimativa fica acima do saldo: avalie remanejamento ou SM antes da adjudicação.";
      alvo.classList.add("valor--negativo");
    } else {
      alvo.textContent = saldoTexto;
      alvo.classList.remove("valor--negativo");
    }
  }

  function atualizarFolga(formulario) {
    const alvo = formulario.querySelector("#pacote-folga");
    const pedido = formulario.elements.pedido;
    const ros = formulario.elements.ros;
    if (!alvo || !pedido || !ros) return;
    if (!pedido.value || !ros.value) {
      alvo.textContent = "Informe as datas do pedido e o ROS.";
      return;
    }
    const dias = diasEntre(pedido.value, ros.value);
    const sinal = dias > 0 ? "+" : "";
    let aviso = " — folga confortável.";
    if (dias < 0) aviso = " — o plano nasceria com folga negativa.";
    else if (dias <= DIAS_DE_ALERTA) aviso = " — atenção.";
    alvo.textContent = "Folga planejada: " + sinal + dias + " d" + aviso;
    alvo.classList.toggle("valor--negativo", dias < 0);
  }

  function preparar(formulario) {
    if (!formulario) return;
    atualizarSaldo(formulario);
    atualizarFolga(formulario);
  }

  /* ---------- Eventos ---------- */

  function aoClicar(evento) {
    if (!raizDaTela()) return;
    const editar = evento.target.closest ? evento.target.closest("[data-pacote-modal-url]") : null;
    if (editar) {
      evento.preventDefault();
      abrirEdicao(editar);
      return;
    }
    const fechar = evento.target.closest ? evento.target.closest("[data-pacote-fechar-modal]") : null;
    if (fechar) {
      evento.preventDefault();
      fecharModal();
      return;
    }
    const acao = evento.target.closest ? evento.target.closest("[data-pacote-acao]") : null;
    if (!acao) return;
    if (acao.dataset.pacoteAcao === "importar") {
      evento.preventDefault();
      abrirImportacao(acao);
    } else if (acao.dataset.pacoteAcao === "novo") {
      evento.preventDefault();
      abrirNovo(acao);
    }
  }

  function aoMudar(evento) {
    const alvo = evento.target;
    if (!alvo || !alvo.closest) return;
    const formulario = document.getElementById("pacote-form");
    if (!formulario || !formulario.contains(alvo)) return;
    preparar(formulario);
  }

  function aoFalhar(evento) {
    const raiz = raizDaTela();
    if (!raiz) return;
    if (evento.detail && evento.detail.status === 403) estadoDaTela("sem-permissao");
    else estadoDaTela("erro");
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("input", aoMudar);
    document.addEventListener("change", aoMudar);
  }

  window.TN.paginas["suprimentos/plano_compras"] = {
    preparar: preparar,
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      acaoPendente = window.TN.escopo.acaoPendente();
      ouvir();

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js) ou a mensagem no modal. */
      function aoErro(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("ajax:error", aoErro);
          return;
        }
        if (dados.estado !== "carregando") return;
        aoFalhar(evento);
      }

      function carregar() {
        dados.estado = "carregando";
        dados
          .carregar()
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
            abrirAcaoPendente();
          })
          .catch(function () {
            /* aoErro já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoErro);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-plano-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
