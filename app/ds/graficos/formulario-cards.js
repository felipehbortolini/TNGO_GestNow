/* ============================================================
   graficos/formulario-cards.js — Formulário de Cards

   Porte de "Formulário de Cards.html" (docs/referencia/graficos/): uma lista
   de registros em cartões pequenos (código, categoria, situação e a seta),
   com a busca no alto e a contagem "visíveis / total". Tocar num cartão
   abre o detalhe, no lugar da lista: a faixa colorida, os campos em duas
   colunas e as seções de texto; a barra Voltar traz de volta a lista (e
   limpa a busca). Serve as restrições do 6WLA e o acervo de lições.

   Contrato dos dados (data-dados):
     {
       "titulo": "Registros",
       "itens": [{
         "id": "PRJ-001", "titulo": "PRJ-001", "subtitulo": "Categoria B",
         "situacao": { "rotulo": "Em andamento", "papel": "alerta" },
         "faixa": { "rotulo": "Subcategoria", "valor": "Categoria B", "papel": "atencao" },
         "campos": [
           { "rotulo": "Responsável", "valor": "Carlos Lima" },
           { "rotulo": "Término", "data": "2026-09-12" },
           { "rotulo": "Área", "situacao": { "rotulo": "Não", "papel": "erro" } }
         ],
         "secoes": [{ "rotulo": "Descrição", "texto": "Inspeção de integridade dos dutos." }]
       }],
       "rotulos": { "buscar": "Pesquisar por código...", "voltar": "Voltar",
                    "detalhes": "Detalhes do registro",
                    "semResultados": "Nenhum registro encontrado." }
     }
   Cada campo traz o texto em `valor`, uma data ISO em `data` (escrita na
   língua do documento) ou uma pílula em `situacao`. A busca olha o título, o
   subtítulo e o texto de `busca` (opcional), sem maiúscula nem acento. Os
   papéis de cor são os de sempre (ok, alerta, atencao, erro, neutro, info).

     <div data-grafico="formulario-cards" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;
  const D = A.datas;

  const ROTULOS = {
    buscar: "Pesquisar por código...",
    voltar: "Voltar",
    detalhes: "Detalhes do registro",
    semResultados: "Nenhum registro encontrado.",
  };

  /* ---------- Contas ---------- */

  function textoDeBusca(item) {
    return A.semAcento([item.titulo, item.subtitulo, item.busca].filter(Boolean).join(" "));
  }

  /* ---------- Peças ---------- */

  function pilula(situacao, classe) {
    return G.el("span", { class: classe + " " + A.tom(situacao.papel), texto: situacao.rotulo });
  }

  /* A data ISO vira texto na língua do documento; sem data que exista, vale
     o `valor`. */
  function textoDoCampo(campo) {
    const dia = campo.data ? D.dia(campo.data) : null;
    return dia === null ? campo.valor : D.completa(dia);
  }

  function valorDoCampo(campo) {
    if (campo.situacao) return pilula(campo.situacao, "graf-fc__pilula");
    return G.el("div", { class: "graf-fc__campo-valor", texto: textoDoCampo(campo) });
  }

  function cartaoDeCampo(campo) {
    return G.el("div", { class: "graf-fc__campo" }, [G.el("div", { class: "graf-fc__rotulo", texto: campo.rotulo }), valorDoCampo(campo)]);
  }

  function secaoDeTexto(secao) {
    return G.el("div", { class: "graf-fc__secao" }, [
      G.el("div", { class: "graf-fc__rotulo", texto: secao.rotulo }),
      G.el("div", { class: "graf-fc__caixa" }, [A.icone("layers", 18), G.el("div", { class: "graf-fc__texto", texto: secao.texto })]),
    ]);
  }

  function faixaDoDetalhe(faixa) {
    return G.el("div", { class: "graf-fc__faixa " + A.tom(faixa.papel) }, [
      G.el("div", { class: "graf-fc__faixa-rotulo", texto: faixa.rotulo }),
      G.el("div", { class: "graf-fc__faixa-valor", texto: faixa.valor }),
    ]);
  }

  /* O detalhe de um registro. */
  function detalhe(item, ctx) {
    const corpo = [];
    if (item.faixa) corpo.push(faixaDoDetalhe(item.faixa));
    if (Array.isArray(item.campos) && item.campos.length) {
      corpo.push(G.el("div", { class: "graf-fc__grade" }, item.campos.map(cartaoDeCampo)));
    }
    if (Array.isArray(item.secoes) && item.secoes.length) {
      corpo.push(G.el("div", { class: "graf-fc__divisor" }));
      item.secoes.forEach(function (secao) {
        corpo.push(secaoDeTexto(secao));
      });
    }
    return G.el("div", { class: "graf-fc__detalhe-cartao" }, [
      G.el("div", { class: "graf-fc__cabecalho" }, [
        G.el("div", { class: "graf-fc__eyebrow", texto: ctx.rotulo("detalhes") }),
        G.el("div", { class: "graf-fc__titulo", texto: item.titulo }),
      ]),
      G.el("div", { class: "graf-fc__corpo" }, corpo),
    ]);
  }

  function miniCartao(item) {
    const direita = [];
    if (item.situacao) direita.push(pilula(item.situacao, "graf-fc__status"));
    direita.push(G.el("span", { class: "graf-fc__seta", "aria-hidden": "true", texto: "›" }));
    return G.el("button", { type: "button", class: "graf-fc__mini" }, [
      G.el("span", { class: "graf-fc__mini-esq" }, [
        G.el("span", { class: "graf-fc__mini-titulo", texto: item.titulo }),
        item.subtitulo ? G.el("span", { class: "graf-fc__mini-sub", texto: item.subtitulo }) : null,
      ].filter(Boolean)),
      G.el("span", { class: "graf-fc__mini-dir" }, direita),
    ]);
  }

  function barraVoltar(ctx) {
    const seta = G.el("span", { class: "graf-fc__voltar-seta", "aria-hidden": "true" }, [A.icone("arrowLeft", 14)]);
    const codigo = G.el("span", { class: "graf-fc__voltar-codigo" });
    const botao = G.el("button", { type: "button", class: "graf-fc__voltar", hidden: true }, [
      seta,
      G.el("span", { class: "graf-fc__voltar-rotulo", texto: ctx.rotulo("voltar") }),
      codigo,
    ]);
    return { botao: botao, codigo: codigo };
  }

  /* ---------- Montagem ---------- */

  G.registrar("formulario-cards", function (host, dados) {
    const itens = Array.isArray(dados.itens) ? dados.itens : [];
    if (!itens.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const ctx = { rotulo: A.rotulador(dados, ROTULOS) };
    const textos = itens.map(textoDeBusca);
    const minis = itens.map(miniCartao);
    const lista = G.el("div", { class: "graf-fc__lista" }, minis);
    const vazio = G.el("p", { class: "graf__vazio", hidden: true, texto: ctx.rotulo("semResultados") });
    const aberto = G.el("div", { class: "graf-fc__detalhe", hidden: true });
    const busca = A.barraDeBusca(ctx.rotulo("buscar"), filtrar);
    const voltar = barraVoltar(ctx);
    const conteudo = G.el("div", { class: "graf-fc__conteudo" }, [lista, vazio, aberto]);
    const raiz = G.el("div", { class: "graf-fc", role: "group", "aria-label": dados.titulo }, [busca.elemento, voltar.botao, conteudo]);
    let ultimo = 0;

    function filtrar(consulta) {
      let visiveis = 0;
      minis.forEach(function (mini, i) {
        const mostrar = consulta === "" || textos[i].includes(consulta);
        mini.hidden = !mostrar;
        if (mostrar) visiveis += 1;
      });
      vazio.hidden = visiveis > 0;
      busca.contar(visiveis, itens.length);
    }

    function abrir(indice) {
      ultimo = indice;
      aberto.replaceChildren(detalhe(itens[indice], ctx));
      voltar.codigo.textContent = itens[indice].titulo;
      busca.elemento.hidden = true;
      lista.hidden = true;
      vazio.hidden = true;
      aberto.hidden = false;
      voltar.botao.hidden = false;
      conteudo.scrollTop = 0;
      voltar.botao.focus();
    }

    function fechar() {
      aberto.hidden = true;
      voltar.botao.hidden = true;
      busca.elemento.hidden = false;
      lista.hidden = false;
      busca.campo.value = "";
      filtrar("");
      conteudo.scrollTop = 0;
      minis[ultimo].focus();
    }

    minis.forEach(function (mini, i) {
      mini.addEventListener("click", function () {
        abrir(i);
      });
    });
    voltar.botao.addEventListener("click", fechar);
    host.replaceChildren(raiz);
    filtrar("");
    return null;
  });

  G.formularioCards = { textoDeBusca: textoDeBusca };
})();
