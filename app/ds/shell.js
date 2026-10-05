/* ============================================================
   shell.js — O shell do GestNow: barra lateral, roteador e escopo

   O shell é o único documento HTML completo (D2). Cada tela é um fragmento
   que troca o conteúdo; este arquivo cuida do resto:

     trilho      a barra lateral nunca some: acima de 1100 px pode ser
                 recolhida num trilho de ícones, abaixo disso já é trilho
     roteador    o endereço que a pessoa vê é /<modulo>/<tela>?projeto=<escopo>
                 (ex.: /central-acoes/atas?projeto=2). Em toda navegação o
                 servidor (/api/nav) diz qual tela abre e devolve a barra
                 lateral e as abas; o shell só carrega a view. Recarregar o
                 endereço abre a mesma tela no mesmo escopo
     escopo      Portfólio ou projeto (D8). O parâmetro projeto da URL é a
                 autoridade: vai em toda chamada a /api/. O cookie só lembra
     inclusão    no Portfólio, botão com data-tn-incluir pede o projeto antes
                 e reabre a tela no projeto com ?acao= (TN.escopo.acaoPendente)

   Links de tela usam <a href="/modulo/tela?..." data-tn-tela>. A lista de
   telas e a regra de qual está ativa são do servidor (core/navigation.py).

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CLASSE_TRILHO = "sidebar-trilho";
  const CHAVE_RECOLHIDA = "gestnow.sidebar.recolhida";
  const LARGURA_ESTREITA = "(max-width: 1100px)";
  const PORTFOLIO = "portfolio";
  const INICIO = "/";
  const TITULO_PADRAO = "Timenow GestNow";
  const VALIDADE_SAUDE_MS = 60000;

  const raiz = document.documentElement;
  const estreita = window.matchMedia(LARGURA_ESTREITA);

  /* ---------- Trilho de ícones ---------- */

  function lerRecolhida() {
    try {
      return localStorage.getItem(CHAVE_RECOLHIDA) === "1";
    } catch {
      return false; /* armazenamento bloqueado: vale o padrão */
    }
  }

  function guardarRecolhida(valor) {
    try {
      localStorage.setItem(CHAVE_RECOLHIDA, valor ? "1" : "0");
    } catch {
      /* sem armazenamento, a escolha vale só até recarregar */
    }
  }

  let recolhida = lerRecolhida();

  function emTrilho() {
    return raiz.classList.contains(CLASSE_TRILHO);
  }

  /* Trilho = tela estreita OU recolhida pela pessoa. O script do <head> faz o
     mesmo antes da primeira pintura; aqui a classe é mantida e a barra, avisada. */
  function aplicarTrilho() {
    raiz.classList.toggle(CLASSE_TRILHO, estreita.matches || recolhida);
    window.dispatchEvent(new CustomEvent("tn-trilho", { detail: emTrilho() }));
  }

  function alternarTrilho() {
    recolhida = !recolhida;
    guardarRecolhida(recolhida);
    aplicarTrilho();
  }

  /* ---------- Sessão e saúde, buscadas uma vez ----------
     A barra lateral é trocada a cada navegação; sem este cache cada troca
     repetiria as duas consultas. */

  let consultaUsuario = null;

  function usuarioLogado() {
    if (!consultaUsuario) {
      consultaUsuario = fetch("/.auth/me")
        .then(function (resposta) { return resposta.ok ? resposta.json() : null; })
        .then(function (dados) { return (dados && dados.clientPrincipal) || null; })
        .catch(function () { return null; });
    }
    return consultaUsuario;
  }

  let ultimaSaude = null;

  async function estadoDaApi() {
    if (ultimaSaude && Date.now() - ultimaSaude.em < VALIDADE_SAUDE_MS) return ultimaSaude.valor;
    let valor = "offline";
    try {
      const resposta = await fetch("/api/health");
      valor = (await resposta.json()).status;
    } catch {
      /* API fora do ar: fica offline */
    }
    ultimaSaude = { valor: valor, em: Date.now() };
    return valor;
  }

  /* ---------- Roteador ---------- */

  function enderecoAtual() {
    return window.location.pathname + window.location.search;
  }

  function shell() {
    return window.Alpine.$data(document.querySelector(".app"));
  }

  /* O que o servidor decidiu, lido dos data-* da barra lateral recém-trocada. */
  function lerInformacoes() {
    const barra = document.getElementById("main-nav");
    const dados = barra ? barra.dataset : {};
    return {
      escopo: dados.escopo || PORTFOLIO,
      caminho: dados.caminho || INICIO,
      tela: dados.tela || "",
      titulo: dados.titulo || TITULO_PADRAO
    };
  }

  /* Põe na barra de endereço o caminho canônico e o escopo resolvido, mantendo
     os demais parâmetros da tela (?codigo=, ?acao=). */
  function atualizarEndereco(url, info, modo) {
    const destino = new URL(url.href);
    destino.pathname = info.caminho;
    destino.searchParams.set("projeto", info.escopo);
    const texto = destino.pathname + destino.search;
    if (texto === enderecoAtual()) return;
    if (modo === "empurrar") window.history.pushState({ tn: true }, "", texto);
    else window.history.replaceState({ tn: true }, "", texto);
  }

  /* Tela de guarda do próprio shell, só com texto fixo (nada vem de dado). */
  function mostrarGuarda(ilustracao, titulo, texto) {
    const principal = document.getElementById("app-shell");
    if (!principal) return null;
    principal.innerHTML =
      '<div class="guard"><img src="/ds/assets/' + ilustracao + '" alt="" />' +
      "<h1>" + titulo + "</h1><p>" + texto + "</p></div>";
    return principal;
  }

  function mostrarFalha() {
    const principal = mostrarGuarda(
      "ilustra-erro.png",
      "Não foi possível abrir a tela",
      "Confira a conexão e tente de novo."
    );
    if (!principal) return;
    const botao = document.createElement("button");
    botao.type = "button";
    botao.className = "btn btn--primary";
    botao.textContent = "Tentar de novo";
    botao.addEventListener("click", function () { window.location.reload(); });
    principal.querySelector(".guard").appendChild(botao);
  }

  /* Quando a view não existe, o servidor devolve o próprio shell (o
     navigationFallback do Static Web Apps) e o Alpine AJAX o encaixa no lugar
     da tela: o "Carregando..." do shell reaparece. Aqui isso vira aviso. */
  function viewAusente() {
    return document.querySelector("#app-shell .page-loading") !== null;
  }

  /* Depois da troca: o foco vai ao conteúdo (quem navega por teclado ou leitor
     de tela não fica no link que sumiu) e a aba ativa entra na área visível. */
  function concluirNavegacao() {
    window.TN.dica.esconder();
    const principal = document.getElementById("app-shell");
    if (principal) {
      principal.setAttribute("tabindex", "-1");
      principal.focus({ preventScroll: true });
    }
    const aba = document.querySelector("#module-tabs .tab.is-active");
    if (aba) aba.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  /* ---------- Escopo (D8) ---------- */

  const escopo = {
    /* "portfolio" ou o id do projeto, como o servidor resolveu na última navegação */
    parametro: null,

    noPortfolio: function () {
      return escopo.parametro === PORTFOLIO;
    },

    /* A tela chama no iniciar(): devolve a ação pedida pelo mecanismo de
       inclusão (ex.: "nova") e a tira do endereço, para recarregar não reabrir. */
    acaoPendente: function () {
      const url = new URL(window.location.href);
      const acao = url.searchParams.get("acao");
      if (acao) {
        url.searchParams.delete("acao");
        window.history.replaceState(window.history.state, "", url.pathname + url.search);
      }
      return acao;
    },

    /* No Portfólio todo registro pertence a um projeto: pergunta qual antes de
       abrir o formulário. Cada projeto é um link do servidor que reabre esta
       tela no projeto, com ?acao= (ver nav/escolher_projeto.html). */
    pedirProjeto: function (acao) {
      const consulta = new URLSearchParams({ caminho: window.location.pathname });
      if (acao) consulta.set("acao", acao);
      const modal = window.TN.modal({
        title: "Escolha o projeto",
        subtitle: "No Portfólio, todo registro pertence a um projeto.",
        width: 520,
        body: '<div id="escopo-escolha"><p class="muted">Carregando...</p></div>'
      });
      modal.body.addEventListener("click", function (e) {
        if (e.target.closest("a[data-tn-tela]")) modal.close();
      });
      shell()
        .buscar("/api/escopo/projetos?" + consulta.toString(), "escopo-escolha")
        .catch(function () { modal.close(); });
    }
  };

  /* O parâmetro projeto da URL é a autoridade do escopo: vai em toda chamada a
     /api/ que não o traga, e assim duas abas em projetos diferentes não se
     misturam pelo cookie, que é compartilhado. */
  document.addEventListener("ajax:send", function (e) {
    const opcoes = e.detail;
    if (!opcoes || !escopo.parametro) return;
    const alvo = new URL(opcoes.action, window.location.href);
    if (!alvo.pathname.startsWith("/api/") || alvo.searchParams.has("projeto")) return;
    alvo.searchParams.set("projeto", escopo.parametro);
    opcoes.action = alvo.toString();
  });

  /* Mecanismo de inclusão: no Portfólio o clique no botão pede o projeto em vez
     de seguir. Na captura, para correr antes de qualquer @click da tela. */
  document.addEventListener("click", function (e) {
    const botao = e.target.closest ? e.target.closest("[data-tn-incluir]") : null;
    if (!botao || !escopo.noPortfolio()) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    escopo.pedirProjeto(botao.dataset.tnIncluir);
  }, true);

  /* Link de tela: troca a view sem recarregar o documento. Clique com tecla
     modificadora segue o comportamento do navegador (nova aba, por exemplo). */
  function cliqueSimples(e) {
    return !e.defaultPrevented && e.button === 0 && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey);
  }

  document.addEventListener("click", function (e) {
    if (!cliqueSimples(e)) return;
    const link = e.target.closest ? e.target.closest("a[data-tn-tela]") : null;
    if (!link) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    e.preventDefault();
    window.TN.shell.navegar(url.pathname + url.search, { historico: "empurrar" });
  });

  /* ---------- Componentes Alpine ---------- */

  function componenteShell() {
    return {
      ocupado: false,
      pendente: null,

      async init() {
        window.addEventListener("popstate", () => {
          this.navegar(enderecoAtual(), { historico: "nenhum" });
        });
        if (!(await usuarioLogado())) {
          await this.buscar("/login.html", "app-shell");
          return;
        }
        document.getElementById("main-nav").style.display = "";
        this.buscar("/api/glossario", "glossario").catch(function () {
          /* sem glossário, só some a dica das siglas */
        });
        await this.navegar(enderecoAtual(), { historico: "substituir" });
      },

      buscar(url, alvos) {
        return this.$ajax(url, { targets: [].concat(alvos) });
      },

      /* Uma navegação por vez; se várias chegam juntas, vale a última. */
      navegar(destino, opcoes) {
        this.pendente = { destino: destino, opcoes: opcoes || {} };
        return this.ocupado ? Promise.resolve() : this.esvaziarFila();
      },

      async esvaziarFila() {
        this.ocupado = true;
        try {
          while (this.pendente) {
            const proxima = this.pendente;
            this.pendente = null;
            await this.executar(proxima.destino, proxima.opcoes);
          }
        } finally {
          this.ocupado = false;
        }
      },

      async executar(destino, opcoes) {
        const url = new URL(destino, window.location.origin);
        const consulta = new URLSearchParams({ caminho: url.pathname });
        if (url.searchParams.get("projeto")) consulta.set("projeto", url.searchParams.get("projeto"));
        try {
          await this.buscar("/api/nav?" + consulta.toString(), ["main-nav", "module-tabs"]);
        } catch {
          mostrarFalha();
          return;
        }
        const info = lerInformacoes();
        escopo.parametro = info.escopo;
        if (!info.tela) {
          window.TN.toast("Endereço não encontrado. Abrimos o Início.", "aviso");
          await this.executar(INICIO + "?projeto=" + info.escopo, { historico: "substituir" });
          return;
        }
        atualizarEndereco(url, info, opcoes.historico);
        document.title = info.titulo;
        try {
          await this.buscar(info.tela, "app-shell");
        } catch {
          mostrarFalha();
          return;
        }
        if (viewAusente()) {
          mostrarGuarda(
            "ilustra-em-construcao.png",
            "Esta tela ainda não está disponível",
            "Ela chega numa próxima etapa da migração."
          );
        }
        concluirNavegacao();
      }
    };
  }

  function componenteSidebar() {
    return {
      usuario: null,
      saude: "…",
      trilho: emTrilho(),

      async init() {
        const marca = this.$el.querySelector(".sidebar__logo-link");
        if (marca) {
          marca.innerHTML =
            '<span class="sidebar__logo sidebar__logo--completa">' + window.LOGO_FULL + "</span>" +
            '<span class="sidebar__logo sidebar__logo--atomo">' + window.logoAtom(28) + "</span>";
        }
        this.usuario = await usuarioLogado();
        this.saude = await estadoDaApi();
      },

      alternarTrilho: alternarTrilho,

      /* O servidor diz para onde ir (data-destino): a mesma tela, ou a lista de
         onde veio o detalhe. A navegação refaz tudo no escopo novo. */
      trocarEscopo(valor) {
        const caixa = this.$el.querySelector(".sidebar__escopo");
        const destino = (caixa && caixa.dataset.destino) || INICIO;
        window.TN.shell.navegar(destino + "?projeto=" + encodeURIComponent(valor), {
          historico: "empurrar"
        });
      },

      get nome() {
        if (!this.usuario) return "";
        const afirmacao = (this.usuario.claims || []).find(function (c) { return c.typ === "name"; });
        return (afirmacao && afirmacao.val) || this.usuario.userDetails || "";
      },

      get email() {
        return this.usuario ? this.usuario.userDetails || "" : "";
      },

      get iniciais() {
        const partes = (this.nome || "?").trim().split(/\s+/);
        const ultima = partes.length > 1 ? partes[partes.length - 1][0] : "";
        return (partes[0][0] + ultima).toUpperCase();
      }
    };
  }

  document.addEventListener("alpine:init", function () {
    window.Alpine.data("shell", componenteShell);
    window.Alpine.data("sidebar", componenteSidebar);
  });

  estreita.addEventListener("change", aplicarTrilho);
  aplicarTrilho();

  window.TN.escopo = escopo;
  window.TN.shell = {
    navegar: function (destino, opcoes) {
      return shell().navegar(destino, opcoes);
    }
  };
})();
