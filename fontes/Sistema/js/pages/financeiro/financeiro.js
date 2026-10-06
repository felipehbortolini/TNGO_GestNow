/* ==========================================================================
   financeiro.js | Apoio comum às telas do módulo 03 Gestão Financeira (GI.fin)

   GI.fin.projeto(aoTrocar)     -> id do projeto (URL ?projeto= ou atual); preenche #f-projeto
   GI.fin.mil(centavos)         -> "9.000,0" (R$ mil, 1 casa) para grades financeiras
   GI.fin.calor(item)           -> selo do mapa de calor do desvio (sinal, seta e cor)
   GI.fin.arvore(itens, filtro) -> itens da EAC filtrados, mantendo os ancestrais
   GI.fin.recolhimento(idTabela, aoMudar) -> recolher/expandir pacotes e subpacotes (ver abaixo)
   GI.fin.classeNivel(item)     -> classe da linha pelo nível (1 pacote, 2 subpacote, 3 item)
   GI.fin.legendaCalor(limites) -> legenda das faixas do mapa de calor
   GI.fin.situacao(texto)       -> selo da situação (medição, claim, EOT, marco)
   GI.fin.classe(c, descricao)  -> selo da classe da contratada (A a D)
   GI.fin.linkContrato(numero)  -> link para a ficha do contrato
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;

  function projeto(aoTrocar) {
    var id = GI.api.projetoAtualId();   /* null = Portfólio */
    var sel = document.getElementById("f-projeto");
    if (sel) {
      sel.innerHTML = U.opcoes(Object.keys(U.mapas.projetos).map(function (k) {
        var p = U.mapas.projetos[k]; return { valor: k, texto: p.codigo + " " + p.nome };
      }), id);
      sel.addEventListener("change", function () { aoTrocar(Number(sel.value)); });
    }
    return id;
  }

  function mil(c) { return c == null ? "" : F.num(c / 100000, 1); }

  function calor(x) {
    if (x.desvioPct == null) return "";
    var faixa = x.faixa || "neutro";
    var icone = faixa.indexOf("sobrecusto") === 0 ? U.icone("arrowUp") : faixa.indexOf("economia") === 0 ? U.icone("arrowDown") : "";
    return '<span class="heat heat--' + faixa + '">' + icone + (x.desvioPct > 0 ? "+" : "") + F.num(x.desvioPct, 1) + "%</span>";
  }

  /* filtro: { busca, nivel (1..3), so: fn(item), raiz: { descricao, ...totais } }
     raiz: primeira linha da árvore, a atividade resumo do projeto (código "0", como a tarefa
     resumo do projeto no MS Project), com os totais do projeto. Sempre aparece, mesmo com filtro. */
  function arvore(itens, filtro) {
    filtro = filtro || {};
    var nivel = filtro.nivel || 3;
    var casa = itens.filter(function (x) {
      return x.nivel <= nivel && (!filtro.busca || U.contem(x.codigo + " " + x.descricao, filtro.busca)) && (!filtro.so || filtro.so(x));
    });
    var lista = casa;
    if (filtro.busca || filtro.so) {
      var codigos = {};
      casa.forEach(function (x) {
        codigos[x.codigo] = true;
        var partes = x.codigo.split(".");
        for (var k = 1; k < partes.length; k++) codigos[partes.slice(0, k).join(".")] = true;
      });
      lista = itens.filter(function (x) { return codigos[x.codigo] && x.nivel <= nivel; });
    }
    return filtro.raiz ? [Object.assign({}, filtro.raiz, { codigo: "0", nivel: 0, raiz: true })].concat(lista) : lista;
  }

  function classeNivel(x) { return x.raiz ? "row--raiz" : x.nivel === 0 ? "row--total" : "row--nivel-" + x.nivel; }

  /* Recolher/expandir da árvore (como as atividades resumo do MS Project).
     r.aplicar(lista) -> lista sem as linhas de ancestrais recolhidos (chamar antes de tabela.atualizar)
     r.botao(item)    -> seta para a coluna Código (vazio se o item não tem filhos na lista)
     r.limpar()       -> expande tudo
     O clique é ligado ao elemento #idTabela; aoMudar() deve redesenhar a tabela. */
  function recolhimento(idTabela, aoMudar) {
    var fechados = {}, pais = {};
    function oculto(x) {
      if (x.raiz) return false;
      if (fechados["0"]) return true;   /* atividade resumo do projeto recolhida */
      var p = x.codigo.split(".");
      for (var k = 1; k < p.length; k++) if (fechados[p.slice(0, k).join(".")]) return true;
      return false;
    }
    function alternar(codigo) {
      if (fechados[codigo]) delete fechados[codigo]; else fechados[codigo] = true;
      aoMudar();
      var b = document.querySelector("#" + idTabela + ' [data-alternar="' + codigo + '"]');
      if (b) b.focus();
    }
    document.getElementById(idTabela).addEventListener("click", function (ev) {
      var t = ev.target.closest("[data-alternar]");
      if (t) alternar(t.getAttribute("data-alternar"));
    });
    return {
      aplicar: function (lista) {
        pais = {};
        lista.forEach(function (x) { if (x.raiz) return; pais["0"] = true; var p = x.codigo.split("."); if (p.length > 1) pais[p.slice(0, -1).join(".")] = true; });
        if (!lista.some(function (x) { return x.raiz; })) delete pais["0"];
        return lista.filter(function (x) { return !oculto(x); });
      },
      botao: function (x) {
        if (!pais[x.codigo]) return "";
        var r = !!fechados[x.codigo], c = U.esc(x.codigo), rot = (r ? "Expandir " : "Recolher ") + c;
        return '<button type="button" class="tree-toggle" data-alternar="' + c + '" aria-expanded="' + (r ? "false" : "true") +
          '" aria-label="' + rot + '" title="' + rot + '">' + U.icone(r ? "chevronRight" : "chevronDown") + "</button>";
      },
      limpar: function () { fechados = {}; }
    };
  }

  function legendaCalor(limites) {
    var l = limites || [1, 5, 10];
    function item(faixa, texto) { return '<span class="legend__item"><span class="heat heat--' + faixa + '" aria-hidden="true"></span>' + U.esc(texto) + "</span>"; }
    return '<div class="legend" aria-label="Faixas do mapa de calor">' +
      item("economia-2", "Economia") +
      item("neutro", "Até " + F.num(l[0]) + "%") +
      item("sobrecusto-1", F.num(l[0]) + "% a " + F.num(l[1]) + "%") +
      item("sobrecusto-2", F.num(l[1]) + "% a " + F.num(l[2]) + "%") +
      item("sobrecusto-3", "Acima de " + F.num(l[2]) + "%") + "</div>";
  }

  /* Selos de situação da administração contratual */
  var TIPO_SITUACAO = {
    "Em execução": "primary", "Encerrado": "neutral",
    "Em análise": "info", "Aprovada": "primary", "Faturada": "purple", "Paga": "success", "Devolvida": "danger",
    "Notificado": "neutral", "Em negociação": "warning", "Acordado": "success", "Rejeitado": "neutral", "Em disputa": "danger",
    "Solicitada": "neutral", "Concedida": "success", "Concedida parcialmente": "warning", "Negada": "neutral",
    "Previsto": "neutral", "Evidência enviada": "info", "Aprovado": "primary", "Faturado": "purple", "Pago": "success"
  };
  function situacao(texto) { return texto ? U.badge(texto, TIPO_SITUACAO[texto] || "neutral", true) : ""; }
  var TIPO_CLASSE = { A: "success", B: "primary", C: "warning", D: "danger" };
  function classe(c, descricao) { return c ? U.badge("Classe " + c, TIPO_CLASSE[c] || "neutral") + (descricao ? ' <span class="text-small text-muted">' + U.esc(descricao) + "</span>" : "") : ""; }
  function linkContrato(numero) { return '<a href="' + U.tela("financeiro", "contrato", { numero: numero }) + '">' + U.esc(numero) + "</a>"; }

  GI.fin = { projeto: projeto, mil: mil, calor: calor, arvore: arvore, classeNivel: classeNivel, recolhimento: recolhimento, legendaCalor: legendaCalor,
    situacao: situacao, classe: classe, linkContrato: linkContrato };
})(window.GI = window.GI || {});
