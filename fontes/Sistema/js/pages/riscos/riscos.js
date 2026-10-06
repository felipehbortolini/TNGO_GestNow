/* ==========================================================================
   riscos.js | Apoio comum às telas do módulo 05 Gestão de Riscos (GI.rsk)
   e os modais 10 a 17 dos mockups, usados no registro, na matriz e na ficha.

   GI.rsk.pronto()                    -> Promise (cadastros, parâmetros e catálogo RBS)
   GI.rsk.projeto(aoTrocar)           -> id do projeto (?projeto= ou atual); preenche #f-projeto
   GI.rsk.contexto(projetoId)         -> etiquetas: projeto, cliente, numeração e apetite
   GI.rsk.sev(sev, score, natureza)   -> pílula da severidade (oportunidade com cor invertida)
   GI.rsk.scoreCel(av, sev, natureza) -> pílula + "P4 x I5"
   GI.rsk.situacao(t) / natureza(t) / estrategia(t) / apurada(chave, natureza)
   GI.rsk.cadencia(dias)              -> "quinzenal", "mensal"...
   Modais (codigo, ..., aoConcluir):  novo, editar, avaliar, plano, aprovarPlano, novaAcao,
                                      revisar, encerrar, reabrir, excluir
   Regras e cálculos ficam em GI.api.riscos; a tela só exibe o que a api devolve.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var REF = GI.api.referencia();
  var API = GI.api.riscos;
  var param = null, categorias = [], clientes = {}, carregando = null;

  function pronto() {
    if (!carregando) {
      carregando = Promise.all([U.pronto(), GI.api.parametros(), API.categorias()]).then(function (r) {
        (r[0].clientes || []).forEach(function (c) { clientes[c.id] = c; });
        param = r[1].riscos; categorias = r[2];
        return param;
      });
    }
    return carregando;
  }

  /* ---------------- Formatação ---------------- */
  function sev(s, score, natureza) {
    if (!s) return '<span class="text-small text-muted">não avaliado</span>';
    return '<span class="sev sev--' + U.esc(s.id) + (natureza === "Oportunidade" ? " sev--op" : "") + '">' + (score != null ? "<b>" + score + "</b> " : "") + U.esc(s.nome) + "</span>";
  }
  /* compacto: pílula só com o score e o nome da faixa abaixo (tabelas largas) */
  function scoreCel(av, s, natureza, compacto) {
    if (!av) return '<span class="text-small text-muted">não avaliado</span>';
    if (compacto) {
      return '<span class="score-cel"><span class="sev sev--' + U.esc(s.id) + (natureza === "Oportunidade" ? " sev--op" : "") + '"><b>' + (av.p * av.i) + "</b></span><small>" + U.esc(s.nome) + "</small><small>P" + av.p + " x I" + av.i + "</small></span>";
    }
    return '<span class="score-cel">' + sev(s, av.p * av.i, natureza) + "<small>P" + av.p + " x I" + av.i + "</small></span>";
  }
  var TIPO_SITUACAO = { "Identificado": "neutral", "Em análise": "warning", "Em tratamento": "info", "Monitorado": "success", "Materializado": "danger", "Encerrado": "neutral" };
  function situacao(t, semPonto) { return t ? U.badge(t, TIPO_SITUACAO[t] || "neutral", !semPonto) : ""; }
  function natureza(t) { return U.badge(t, t === "Oportunidade" ? "success" : "outline"); }
  function estrategia(t) { return t ? U.badge(t, "purple") : '<span class="text-small text-muted">sem plano</span>'; }
  var APURADA_OP = { "Risco reduzido": "Oportunidade reduzida", "Risco agravado": "Oportunidade ampliada", "Risco materializado": "Oportunidade capturada", "Risco superado": "Oportunidade superada" };
  function apurada(k, nat) { return nat === "Oportunidade" && APURADA_OP[k] ? APURADA_OP[k] : k; }
  function cadencia(d) {
    return d === 15 ? "quinzenal" : d === 30 ? "mensal" : d === 60 ? "bimestral" : d === 90 ? "trimestral" : d ? "a cada " + d + " dias" : "";
  }
  function nomeProb(p) { var x = (param.probabilidades || []).filter(function (f) { return f.nivel === p; })[0]; return x ? x.nome : ""; }
  function nomeImp(i) { return param.impactos[i - 1] || ""; }
  function linkFicha(codigo, texto) { return '<a href="' + U.tela("riscos", "ficha", { codigo: codigo }) + '">' + U.esc(texto || codigo) + "</a>"; }
  function somaDias(iso, n) { var d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + n); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function pessoas() {
    return Object.keys(U.mapas.pessoas).map(function (k) { var p = U.mapas.pessoas[k]; return { valor: k, texto: p.nome + " (" + p.funcao + ")" }; })
      .sort(function (a, b) { return a.texto.localeCompare(b.texto); });
  }
  function ordemFaixa(id) {
    var l = API.legenda();
    for (var k = 0; k < l.length; k++) if (l[k].id === id) return k;
    return id === "critico" ? l.length - 1 : -1;
  }
  function erroApi(e) { GI.ui.toast((e && e.erros ? e.erros.map(function (x) { return x.msg || x; }).join(" ") : String(e)), "warning", 7000); }

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
  function contexto(projetoId) {
    var p = U.projeto(projetoId);
    if (projetoId == null) {
      /* Portfólio: numeração e apetite são definidos em cada projeto */
      return '<div class="contexto-risco" aria-label="Contexto do portfólio">' + U.badge("Portfólio: " + U.plural(U.listaProjetos().length, "projeto"), "outline") +
        U.listaProjetos().map(function (x) { var a = API.legenda().filter(function (f) { return f.id === x.apetiteRisco; })[0];
          return U.badge(x.codigo + " · apetite " + (a ? a.nome : "não definido"), "outline"); }).join("") + "</div>";
    }
    if (!p) return "";
    var cl = clientes[p.clienteId] || null;
    var alvo = API.legenda().filter(function (f) { return f.id === p.apetiteRisco; })[0];
    return '<div class="contexto-risco" aria-label="Contexto do projeto">' +
      U.badge("Projeto: " + p.codigo, "outline") + U.badge("Cliente: " + (cl ? cl.sigla : ""), "outline") +
      U.badge("Numeração: " + (p.padraoRisco || ""), "outline") + U.badge("Apetite: " + (alvo ? alvo.nome : "não definido"), "primary") + "</div>";
  }

  /* ======================================================================
     Modal 1: Novo risco e edição
     ====================================================================== */
  function opcoesCategoria() {
    return categorias.map(function (c) { var t = c.grupo + " > " + c.nome; return { valor: t, texto: t }; })
      .sort(function (a, b) { return a.texto.localeCompare(b.texto); });
  }
  function novaCategoria(selEl) {
    var grupos = [];
    categorias.forEach(function (c) { if (grupos.indexOf(c.grupo) < 0) grupos.push(c.grupo); });
    GI.form.abrir({
      titulo: "Nova categoria (RBS)", tamanho: "sm",
      intro: '<p class="text-small text-muted">Cadastro rápido do catálogo mantido em Configurações > Cadastros.</p>',
      campos: [
        { id: "grupo", rotulo: "Grupo (nível 1)", tipo: "texto", obrigatorio: true, max: 60, sugestoes: grupos, largura: "full" },
        { id: "nome", rotulo: "Subcategoria", tipo: "texto", obrigatorio: true, max: 60, largura: "full" }
      ],
      aoSalvar: function (v) {
        return API.novaCategoria(v).then(function (c) {
          categorias.push(c);
          var t = c.grupo + " > " + c.nome;
          selEl.innerHTML = U.opcoes(opcoesCategoria(), t, "Selecione...");
          selEl.dispatchEvent(new Event("change", { bubbles: true }));
          GI.ui.toast("Categoria " + t + " cadastrada.", "success");
        });
      }
    });
  }
  function atasDoProjeto(projetoId) {
    return GI.api.listar("atas", { projetoId: projetoId }).then(function (l) {
      var por = {};
      l.forEach(function (a) { if (!por[a.numero] || a.revisao > por[a.numero].revisao) por[a.numero] = { id: a.id, numero: a.numero, revisao: a.revisao, data: por[a.numero] ? por[a.numero].data : a.data }; if (a.revisao === 0) por[a.numero].data = a.data; });
      return Object.keys(por).sort().reverse().map(function (k) { var a = por[k]; return { valor: a.id, texto: a.numero + " (" + F.data(a.data) + ")" }; });
    });
  }
  function formRisco(projetoId, r, aoConcluir) {
    return Promise.all([pronto(), atasDoProjeto(projetoId)]).then(function (res) {
      var atas = res[1];
      var proj = U.projeto(projetoId) || {};
      var sistema = r && GI.api.riscos.ORIGENS.indexOf(r.origemTipo) < 0;
      var campos = [
        { id: "projeto", rotulo: "Projeto", tipo: "info", html: '<span class="text-strong">' + U.esc(proj.codigo + " · " + proj.nome) + "</span>" },
        { id: "numero", rotulo: "Número", tipo: "info", html: r ? "<b>" + U.esc(r.codigo) + "</b>" : '<span class="text-muted">gerado ao salvar</span>' },
        { id: "natureza", rotulo: "Natureza", tipo: "escolha", obrigatorio: true, valor: r ? r.natureza : "Ameaça", desabilitado: !!(r && r.estrategia),
          opcoes: [{ valor: "Ameaça", texto: "Ameaça" }, { valor: "Oportunidade", texto: "Oportunidade" }],
          ajuda: r && r.estrategia ? "Risco com plano de resposta: a natureza não pode ser trocada." : "Define as estratégias de resposta disponíveis no plano." },
        { id: "categoria", rotulo: "Categoria (RBS)", tipo: "select", obrigatorio: true, valor: r ? r.categoria + " > " + r.subcategoria : "", opcoes: opcoesCategoria() },
        { id: "novaCategoria", tipo: "info", rotulo: "", html: '<button type="button" class="btn btn--ghost btn--sm" data-nova-categoria>' + U.icone("plus") + "Nova categoria</button>" },
        { id: "causa", rotulo: "Causa (por que pode acontecer)", tipo: "texto", obrigatorio: true, max: 255, largura: "full", valor: r ? r.causa : "" },
        { id: "titulo", rotulo: "Evento (o que pode acontecer)", tipo: "textarea", obrigatorio: true, max: 255, linhas: 2, valor: r ? r.titulo : "",
          ajuda: "É o título usado nas listas e relatórios." },
        { id: "consequencia", rotulo: "Consequência (efeito no projeto)", tipo: "texto", obrigatorio: true, max: 255, largura: "full", valor: r ? r.consequencia : "" },
        { id: "descricao", rotulo: "Descrição detalhada", tipo: "textarea", max: 1000, valor: r ? r.descricao : "", placeholder: "Contexto, premissas e evidências que sustentam o risco" },
        { id: "donoId", rotulo: "Dono do risco", tipo: "select", obrigatorio: true, valor: r ? r.donoId : "", opcoes: pessoas(), ajuda: "Precisa ser convidado ativo do cliente do projeto." },
        { id: "identificadoEm", rotulo: "Data de identificação", tipo: "data", obrigatorio: true, maxData: REF, valor: r ? r.identificadoEm : REF },
        sistema
          ? { id: "origemInfo", rotulo: "Origem", tipo: "info", html: U.esc(r.origem) + '<br><small class="text-muted">Gerada pelo sistema; não editável.</small>' }
          : { id: "origemTipo", rotulo: "Origem", tipo: "select", obrigatorio: true, valor: r ? r.origemTipo : "Manual",
              opcoes: GI.api.riscos.ORIGENS.map(function (o) { return { valor: o, texto: o }; }) },
        { id: "ataId", rotulo: "Ata de origem", tipo: "select", obrigatorio: true, valor: r ? r.ataId : "", opcoes: atas,
          mostrarSe: function (v) { return !sistema && v.origemTipo === "Ata de reunião"; }, ajuda: "Grava o vínculo de navegação com a ata." },
        { id: "gatilho", rotulo: "Gatilho (sinal de alerta)", tipo: "texto", max: 255, largura: "full", valor: r ? r.gatilho : "",
          ajuda: "Usado no monitoramento: quando o gatilho ocorre, o sistema sugere reavaliação imediata." }
      ];
      var m = GI.form.abrir({
        titulo: r ? "Editar risco " + r.codigo : "Novo risco", subtitulo: r ? r.titulo : proj.codigo + " · " + proj.nome, tamanho: "lg",
        intro: r ? "" : '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">O número é reservado pelo sistema ao salvar, a partir do padrão do projeto (' +
          U.esc(proj.padraoRisco || "") + "). Nada é numerado no navegador.</div></div>",
        campos: campos,
        extras: r && r.avaliado ? [] : [{ texto: "Salvar e avaliar", acao: "avaliar" }],
        aoSalvar: function (v, api, acao) {
          return API.salvar({ codigo: r ? r.codigo : null, projetoId: projetoId, natureza: v.natureza, categoria: v.categoria, causa: v.causa, titulo: v.titulo,
            consequencia: v.consequencia, descricao: v.descricao, donoId: v.donoId, identificadoEm: v.identificadoEm,
            origemTipo: sistema ? r.origemTipo : v.origemTipo, ataId: v.ataId, gatilho: v.gatilho }).then(function (res2) {
            GI.ui.toast(res2.novo ? "Risco " + res2.codigo + " registrado (situação Identificado)." : "Risco " + res2.codigo + " atualizado.", "success");
            res2.avisos.forEach(function (a) { GI.ui.toast(a, "warning", 7000); });
            if (acao === "avaliar") setTimeout(function () { avaliar(res2.codigo, { tipo: "inerente" }, aoConcluir); }, 50);
            if (aoConcluir) aoConcluir(res2.codigo);
          });
        }
      });
      m.el.addEventListener("click", function (ev) {
        if (ev.target.closest("[data-nova-categoria]")) novaCategoria(m.el.querySelector('[data-campo="categoria"] select'));
      });
      return m;
    });
  }
  function novo(projetoId, aoConcluir) {
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar riscos.", "warning"); return; }
    if (projetoId == null) { U.noProjeto("novo", "Novo risco"); return; }
    return formRisco(projetoId, null, aoConcluir);
  }
  function editar(codigo, aoConcluir) {
    return API.risco(codigo).then(function (r) {
      if (!r) return;
      if (!r.ativo) { GI.ui.toast("Risco encerrado não pode ser editado. Reabra o risco antes.", "warning"); return; }
      return formRisco(r.projetoId, r, aoConcluir);
    });
  }

  /* ======================================================================
     Modal 2: Avaliação (inerente ou residual)
     ====================================================================== */
  function avaliar(codigo, opcoes, aoConcluir) {
    return Promise.all([API.risco(codigo), pronto()]).then(function (res) {
      var r = res[0];
      if (!r) return;
      if (!r.ativo) { GI.ui.toast("Risco encerrado não pode ser reavaliado.", "warning"); return; }
      var op = r.natureza === "Oportunidade";
      var tipoIni = (opcoes && opcoes.tipo) || (r.temPlano ? "residual" : "inerente");
      if (tipoIni === "residual" && !r.temPlano) tipoIni = "inerente";
      function base(tipo) { return (tipo === "residual" ? (r.residual || r.inerente) : r.inerente) || { p: null, i: null, dimensoes: {} }; }
      var b = base(tipoIni), ultimoTipo = tipoIni, modal = null, seq = 0;
      var escalaImp = [1, 2, 3, 4, 5].map(function (n) { return { valor: n, numero: n, texto: nomeImp(n) }; });
      var campos = [
        { id: "tipo", rotulo: "Avaliação", tipo: "escolha", obrigatorio: true, largura: "full", valor: tipoIni,
          opcoes: [{ valor: "inerente", texto: "Inerente" }, { valor: "residual", texto: "Residual", desabilitado: !r.temPlano }] },
        { id: "orientacao", tipo: "info", rotulo: "", html: "" },
        { id: "p", rotulo: op ? "Probabilidade de captura" : "Probabilidade", tipo: "escolha", obrigatorio: true, largura: "full", valor: b.p,
          opcoes: param.probabilidades.map(function (x) { return { valor: x.nivel, numero: x.nivel, texto: x.nome, sub: x.faixa }; }) },
        { id: "dimTitulo", tipo: "info", rotulo: op ? "Benefício por dimensão" : "Impacto por dimensão",
          html: '<p class="text-small text-muted">Avalie ao menos uma dimensão. Em branco: não se aplica.</p>' }
      ].concat(API.DIMENSOES.map(function (d) {
        return { id: "d_" + d.id, rotulo: d.nome, tipo: "select", vazio: "Não se aplica", valor: (b.dimensoes || {})[d.id] || "",
          opcoes: [1, 2, 3, 4, 5].map(function (n) { return { valor: n, texto: n + " " + nomeImp(n) }; }) };
      })).concat([
        { id: "i", rotulo: op ? "Benefício (resultante)" : "Impacto (resultante)", tipo: "escolha", obrigatorio: true, largura: "full", valor: b.i, opcoes: escalaImp },
        { id: "regra", tipo: "info", rotulo: "", html: "" },
        { id: "impactoPrazoDias", rotulo: op ? "Benefício em prazo (dias)" : "Impacto em prazo (dias)", tipo: "numero", min: 0, maxNumero: 999, valor: r.impactoPrazoDias,
          ajuda: op ? "Dias de antecipação no caminho crítico." : "Dias de atraso no caminho crítico; alimenta o painel." },
        { id: "impactoCustoCentavos", rotulo: op ? "Benefício em custo" : "Impacto em custo", tipo: "moeda", valor: r.impactoCustoCentavos, ajuda: "Gravado em centavos. Base do VME." },
        { id: "riscoVida", rotulo: "Envolve risco à vida (SMS)", tipo: "check", valor: r.riscoVida, largura: "full",
          ajuda: "Na escala CIPM, risco à vida é sempre classificado na faixa mais alta." },
        { id: "justificativa", rotulo: "Justificativa da avaliação", tipo: "textarea", max: 500, linhas: 3,
          ajuda: "Obrigatória sempre que o score ou a severidade mudarem em relação à avaliação anterior." },
        { id: "resumo", tipo: "info", rotulo: "", html: "" }
      ]);
      function dims(v) { var o = {}; API.DIMENSOES.forEach(function (d) { if (v["d_" + d.id]) o[d.id] = Number(v["d_" + d.id]); }); return o; }
      modal = GI.form.abrir({
        titulo: "Avaliação do risco " + r.codigo, subtitulo: r.titulo, tamanho: "lg", textoSalvar: "Salvar avaliação", campos: campos,
        aoMudar: function (v, ctx) {
          if (modal && v.tipo && v.tipo !== ultimoTipo) {
            ultimoTipo = v.tipo;
            var nb = base(v.tipo), valores = { p: nb.p, i: nb.i };
            API.DIMENSOES.forEach(function (d) { valores["d_" + d.id] = (nb.dimensoes || {})[d.id] || ""; });
            modal.definir(valores);
            return;
          }
          ctx.info("orientacao", '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">' + (v.tipo === "residual"
            ? "<b>Avaliação residual:</b> considere o risco com o plano de resposta executado. Para ameaças, o residual não supera o inerente."
            : "<b>Avaliação inerente:</b> considere o risco sem nenhum tratamento." + (r.temPlano ? "" : " A avaliação residual só é habilitada depois que o plano de resposta existir.")) + "</div></div>");
          var d = dims(v);
          var nomes = API.DIMENSOES.filter(function (x) { return d[x.id]; });
          var iMin = nomes.reduce(function (mx, x) { return Math.max(mx, d[x.id]); }, 0);
          var piores = nomes.filter(function (x) { return d[x.id] === iMin; }).map(function (x) { return x.nome; });
          if (modal) {
            Array.prototype.forEach.call(modal.el.querySelectorAll('[data-campo="i"] .escolha__opt'), function (o) { o.disabled = Number(o.getAttribute("data-value")) < iMin; });
            if (iMin && (!v.i || Number(v.i) < iMin)) { modal.definir({ i: iMin }); return; }
          }
          ctx.info("regra", '<p class="text-small text-muted">' + (iMin ? "O impacto do risco é o maior valor entre as dimensões (regra do pior caso). Aqui: " + iMin + " (" + piores.join(", ") + "). Pode ser elevado, nunca reduzido."
            : "Avalie as dimensões: o impacto resultante acompanha a maior delas.") + "</p>");
          var n = ++seq;
          API.previa({ p: Number(v.p), i: Number(v.i), dimensoes: d, riscoVida: v.riscoVida, impactoCustoCentavos: v.impactoCustoCentavos }).then(function (pv) {
            if (n !== seq) return;
            var ant = base(v.tipo), scoreAnt = ant.p ? ant.p * ant.i : null;
            var faixa = pv.sev ? API.legenda().filter(function (f) { return f.id === pv.sev.id; })[0] : null;
            ctx.info("resumo", !pv.score ? '<p class="text-small text-muted">Escolha probabilidade e impacto para ver o score.</p>' :
              '<div class="aval-card"><span class="aval-card__rotulo">Score ' + (v.tipo === "residual" ? "residual" : "inerente") + "</span>" +
              '<div class="aval-card__score"><b>' + pv.score + '</b><span class="aval-card__pi">P' + v.p + " x I" + pv.i + "</span>" + sev(pv.sev, null, r.natureza) +
              (faixa ? '<span class="text-small text-muted">Faixa ' + faixa.minimo + " a " + faixa.maximo + "</span>" : "") + "</div>" +
              '<span class="text-small">' + (scoreAnt != null ? "Anterior: " + scoreAnt + " · " : "") + "VME " + F.moeda(pv.vmeCentavos || 0) + " (" + pv.pct + "% x impacto em custo) · revisão " + cadencia(pv.cadenciaDias) + "</span></div>");
          });
        },
        aoSalvar: function (v) {
          return API.avaliar(r.codigo, { tipo: v.tipo, p: Number(v.p), i: Number(v.i), dimensoes: dims(v), impactoPrazoDias: v.impactoPrazoDias,
            impactoCustoCentavos: v.impactoCustoCentavos, riscoVida: v.riscoVida, justificativa: v.justificativa }).then(function (x) {
            GI.ui.toast("Avaliação " + v.tipo + " registrada: " + x.score + " (" + x.sev.nome + ").", "success");
            if (x.alertaGestor) GI.ui.toast("Risco " + x.sev.nome.toLowerCase() + ": alerta enviado à gerência do projeto (simulação).", "info", 6000);
            if (aoConcluir) aoConcluir(r.codigo);
            if (x.exigePlano) {
              GI.ui.toast("Risco " + x.sev.nome.toLowerCase() + " sem plano de resposta: defina o plano agora.", "warning", 6000);
              setTimeout(function () { plano(r.codigo, aoConcluir); }, 50);
            }
          });
        }
      });
      return modal;
    });
  }

  /* ======================================================================
     Modal 3: Plano de resposta
     ====================================================================== */
  function tabelaAcoes(lista, comBotao) {
    var acoes = lista.filter(function (a) { return a.ehAcao; });
    var h = acoes.length ? '<div class="table-wrap table-wrap--stack"><table class="table table--stack table--compact"><thead><tr><th>Item</th><th>Ação</th><th>Responsável</th><th>Prevista</th><th>Situação</th></tr></thead><tbody>' +
      acoes.map(function (a) {
        return '<tr><td data-label="Item" class="num">' + U.esc(a.item || "") + '</td><td data-label="Ação">' + U.esc(a.assunto) + '</td><td data-label="Responsável">' + U.esc(U.pessoa(a.responsavelId)) +
          '</td><td data-label="Prevista" class="nowrap">' + F.data(a.replanejada || a.prevista) + '</td><td data-label="Situação">' + U.badge(a.statusRotulo, U.statusAcao(a.status), true) + "</td></tr>";
      }).join("") + "</tbody></table></div>" : '<p class="text-small text-muted">Nenhuma ação vinculada.</p>';
    return (comBotao ? '<div class="toolbar"><button type="button" class="btn btn--secondary btn--sm" data-nova-acao>' + U.icone("plus") + "Nova ação</button></div>" : "") + h;
  }
  function plano(codigo, aoConcluir) {
    return pronto().then(function () { return API.risco(codigo); }).then(function (r) {
      if (!r) return;
      if (!r.ativo) { GI.ui.toast("Risco encerrado não pode ter o plano alterado.", "warning"); return; }
      if (!r.avaliado) { GI.ui.toast("Avalie o risco (inerente) antes de definir o plano de resposta.", "warning"); avaliar(codigo, { tipo: "inerente" }, aoConcluir); return; }
      return GI.api.listar("mudancas", { projetoId: r.projetoId }).then(function (sms) {
        var op = r.natureza === "Oportunidade";
        var legenda = API.legenda();
        var topo = ordemFaixa(r.sevInerente.id) === legenda.length - 1;
        var alvos = legenda.filter(function (f, k) { return op || k <= ordemFaixa(r.sevInerente.id); });
        var proj = U.projeto(r.projetoId) || {};
        var acoesAtual = r.listaAcoes;
        var modal = null;
        function exigeAcao(est) { return est && est !== "Aceitar" && ordemFaixa(r.sevInerente.id) >= ordemFaixa("alto"); }
        function blocoAcoes(est) {
          var n = acoesAtual.filter(function (a) { return a.ehAcao; }).length;
          return tabelaAcoes(acoesAtual, true) + (exigeAcao(est) && !n ? '<div class="alert alert--warning mt-2">' + U.icone("alertTriangle") +
            '<div class="alert__body">Risco ' + U.esc(r.sevInerente.nome) + " exige pelo menos uma ação vinculada. Sem ação, o plano não pode ser salvo.</div></div>" : "") +
            '<p class="text-small text-muted mt-2">As ações são registros da Central de Ações com origem Risco.</p>';
        }
        var campos = [
          { id: "estrategia", rotulo: "Estratégia", tipo: "escolha", obrigatorio: true, largura: "full", valor: r.estrategia,
            opcoes: API.ESTRATEGIAS[r.natureza].map(function (e) { return { valor: e, texto: e }; }),
            ajuda: op ? "Oportunidade: Explorar, Melhorar, Compartilhar ou Aceitar." : "Ameaça: Mitigar, Transferir, Evitar ou Aceitar. Para oportunidade, as opções passam a ser Explorar, Melhorar, Compartilhar e Aceitar." },
          { id: "plano", rotulo: "Plano de resposta", tipo: "textarea", obrigatorio: true, max: 1000, linhas: 4, valor: r.plano || r.respostaProposta || "",
            ajuda: "Descreve o que será feito; a execução vive nas ações. Aceitar exige justificativa; Evitar, a mudança de escopo ou de solução (mínimo de 80 caracteres)." },
          { id: "instrumento", rotulo: "Instrumento da transferência", tipo: "select", obrigatorio: true, valor: r.instrumento,
            opcoes: API.INSTRUMENTOS.map(function (x) { return { valor: x, texto: x }; }), mostrarSe: function (v) { return v.estrategia === "Transferir"; } },
          { id: "smRef", rotulo: "Solicitação de mudança (08)", tipo: "select", obrigatorio: true, valor: r.smRef,
            opcoes: sms.map(function (s) { return { valor: s.codigo, texto: s.codigo + " · " + s.titulo + " (" + s.situacao + ")" }; }).concat([{ valor: "nova", texto: "Registrar nova SM (gera ação na Central)" }]),
            mostrarSe: function (v) { return v.estrategia === "Evitar"; }, largura: "full" },
          { id: "severidadeAlvo", rotulo: "Severidade-alvo", tipo: "select", obrigatorio: true, valor: r.severidadeAlvo || proj.apetiteRisco,
            opcoes: alvos.map(function (f) { return { valor: f.id, texto: f.nome + " (" + f.minimo + " a " + f.maximo + ")" }; }),
            ajuda: op ? "Nível a alcançar com a resposta." : "Não pode ser maior que a severidade inerente (" + r.sevInerente.nome + ")." },
          { id: "prazoAlvo", rotulo: "Prazo para o alvo", tipo: "data", obrigatorio: true, min: somaDias(REF, 1), valor: r.prazoAlvo },
          { id: "custoRespostaCentavos", rotulo: "Custo da resposta", tipo: "moeda", valor: r.custoRespostaCentavos, ajuda: "Em centavos. Comparado ao VME para justificar o tratamento." },
          { id: "responsavelPlanoId", rotulo: "Responsável pelo plano", tipo: "select", obrigatorio: true, valor: r.responsavelPlanoId || r.donoId, opcoes: pessoas(),
            ajuda: "Pode ser diferente do dono do risco." },
          { id: "exigirAprovacao", rotulo: "Requer aprovação da gerência do projeto", tipo: "check", largura: "full", valor: topo || !!(r.aprovacao && r.aprovacao.exigida), desabilitado: topo,
            ajuda: topo ? "Marcado e bloqueado: severidade inerente " + r.sevInerente.nome + "." : "Obrigatório quando a severidade inerente é a mais alta da escala." },
          { id: "custoBeneficio", tipo: "info", rotulo: "Custo x benefício", html: "" },
          { id: "acoes", tipo: "info", rotulo: "Ações vinculadas", html: blocoAcoes(r.estrategia) }
        ];
        modal = GI.form.abrir({
          titulo: "Plano de resposta · " + r.codigo, subtitulo: r.titulo, tamanho: "lg", textoSalvar: "Salvar plano", campos: campos,
          intro: r.respostaProposta && !r.plano ? '<p class="text-small">Resposta proposta no registro de origem: <i>' + U.esc(r.respostaProposta) + "</i></p>" : "",
          aoMudar: function (v, ctx) {
            var reducao = r.vmeInerenteCentavos - r.vmeCentavos, custo = v.custoRespostaCentavos || 0;
            ctx.info("custoBeneficio", '<p class="text-small">VME inerente ' + F.moeda(r.vmeInerenteCentavos) + " · VME atual " + F.moeda(r.vmeCentavos) +
              (r.scoreResidual != null && !op ? " · redução da exposição " + F.moeda(reducao) : "") + (custo ? " · custo da resposta " + F.moeda(custo) : "") + "</p>" +
              (!op && custo && r.scoreResidual != null && custo > reducao ? '<p class="text-small valor--negativo">Custo da resposta maior que a redução do VME: justifique pelo impacto em prazo, SMS, imagem ou obrigação legal.</p>' : ""));
            ctx.info("acoes", blocoAcoes(v.estrategia));
          },
          aoSalvar: function (v) {
            return API.plano(r.codigo, { estrategia: v.estrategia, plano: v.plano, instrumento: v.instrumento, smRef: v.smRef, severidadeAlvo: v.severidadeAlvo,
              prazoAlvo: v.prazoAlvo, custoRespostaCentavos: v.custoRespostaCentavos, responsavelPlanoId: Number(v.responsavelPlanoId), exigirAprovacao: v.exigirAprovacao }).then(function (x) {
              GI.ui.toast("Plano de resposta salvo. Situação: " + x.situacao + ".", "success");
              if (x.aprovacaoPendente) GI.ui.toast("Plano aguardando aprovação da gerência do projeto.", "warning", 6000);
              else if (x.habilitaResidual) GI.ui.toast("Avaliação residual habilitada.", "info");
              if (aoConcluir) aoConcluir(r.codigo);
            });
          }
        });
        modal.el.addEventListener("click", function (ev) {
          if (!ev.target.closest("[data-nova-acao]")) return;
          novaAcao(r.codigo, function () {
            API.risco(r.codigo).then(function (r2) {
              acoesAtual = r2.listaAcoes;
              var w = modal.el.querySelector('[data-campo="acoes"] [data-info]');
              if (w) w.innerHTML = blocoAcoes(modal.ler().estrategia);
              if (aoConcluir) aoConcluir(r.codigo);
            });
          });
        });
        return modal;
      });
    });
  }

  /* Aprovação do plano pela gerência do projeto */
  function aprovarPlano(codigo, aoConcluir) {
    return API.risco(codigo).then(function (r) {
      if (!r || !r.planoPendente) return;
      GI.form.abrir({
        titulo: "Aprovação do plano · " + r.codigo, subtitulo: r.titulo, tamanho: "lg", textoSalvar: "Registrar decisão",
        intro: '<dl class="dl"><dt>Estratégia</dt><dd>' + U.esc(r.estrategia) + "</dd><dt>Plano</dt><dd>" + U.esc(r.plano) + "</dd><dt>Alvo</dt><dd>" + U.esc(r.nomeAlvo) +
          " até " + F.data(r.prazoAlvo) + "</dd><dt>Responsável</dt><dd>" + U.esc(U.pessoa(r.responsavelPlanoId)) + "</dd><dt>Ações vinculadas</dt><dd>" + r.acoes + "</dd></dl>",
        campos: [
          { id: "decisao", rotulo: "Decisão", tipo: "escolha", obrigatorio: true, largura: "full",
            opcoes: [{ valor: "Aprovado", texto: "Aprovar" }, { valor: "Devolvido", texto: "Devolver para revisão" }] },
          { id: "comentario", rotulo: "Comentário", tipo: "textarea", max: 500, ajuda: "Obrigatório ao devolver." }
        ],
        aoSalvar: function (v) {
          return API.aprovarPlano(r.codigo, v).then(function (x) {
            GI.ui.toast(v.decisao === "Aprovado" ? "Plano aprovado. Situação: " + x.situacao + "." : "Plano devolvido ao responsável.", "success");
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }

  /* ======================================================================
     Modal 4: Ação de mitigação (vai para a Central, origem Risco)
     ====================================================================== */
  function novaAcao(codigo, aoConcluir) {
    return Promise.all([API.risco(codigo), pronto()]).then(function (res) {
      var r = res[0];
      if (!r) return;
      if (!r.ativo) { GI.ui.toast("Risco encerrado não recebe novas ações.", "warning"); return; }
      var op = r.natureza === "Oportunidade";
      var item = r.listaAcoes.reduce(function (m, a) { return Math.max(m, Number(a.item) || 0); }, 0) + 1;
      GI.form.abrir({
        titulo: "Nova ação do risco", subtitulo: r.codigo + " · " + r.titulo, tamanho: "lg",
        intro: '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">Esta ação nasce vinculada ao risco (origem Risco) e aparece na Central de Ações. Riscos não geram itens do tipo Informação.</div></div>',
        campos: [
          { id: "item", rotulo: "Item", tipo: "info", html: "<b>" + item + '</b> <small class="text-muted">sequencial dentro do risco</small>' },
          { id: "origem", rotulo: "Origem", tipo: "info", html: U.esc(r.codigo) + " · Ação" },
          { id: "assunto", rotulo: "Assunto", tipo: "texto", obrigatorio: true, max: 255, largura: "full" },
          { id: "descricao", rotulo: "Descrição", tipo: "textarea", max: 500 },
          { id: "solicitanteId", rotulo: "Solicitante", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: GI.api.sessaoAtual().pessoaId },
          { id: "responsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: r.donoId },
          { id: "email", rotulo: "E-mail do responsável", tipo: "info", html: "" },
          { id: "prevista", rotulo: "Data prevista", tipo: "data", obrigatorio: true, min: REF },
          { id: "contribuicao", rotulo: "Contribuição esperada", tipo: "multi",
            opcoes: [{ valor: "probabilidade", texto: op ? "Aumenta a probabilidade" : "Reduz a probabilidade" }, { valor: "impacto", texto: op ? "Aumenta o benefício" : "Reduz o impacto" }],
            ajuda: "Apoio na reavaliação residual: indica qual eixo revisar." }
        ],
        extras: [{ texto: "Salvar e nova", acao: "nova" }],
        aoMudar: function (v, ctx) {
          var p = U.mapas.pessoas[v.responsavelId];
          ctx.info("email", p && p.email ? U.esc(p.email) + '<br><small class="text-muted">Usado no follow-up da Central.</small>' : '<span class="text-muted">sem e-mail cadastrado</span>');
        },
        aoSalvar: function (v, api, acao) {
          return API.novaAcao(r.codigo, { assunto: v.assunto, descricao: v.descricao, solicitanteId: v.solicitanteId, responsavelId: v.responsavelId, prevista: v.prevista,
            contribuicao: { probabilidade: v.contribuicao.indexOf("probabilidade") >= 0, impacto: v.contribuicao.indexOf("impacto") >= 0 } }).then(function (a) {
            GI.ui.toast("Ação " + a.item + " criada na Central de Ações.", "success");
            if (aoConcluir) aoConcluir(r.codigo);
            if (acao === "nova") setTimeout(function () { novaAcao(codigo, aoConcluir); }, 50);
          });
        }
      });
    });
  }

  /* ======================================================================
     Modal 5: Revisão periódica
     ====================================================================== */
  function revisar(codigo, aoConcluir) {
    return Promise.all([API.risco(codigo), pronto()]).then(function (res) {
      var r = res[0];
      if (!r) return;
      if (!r.ativo) { GI.ui.toast("Risco encerrado não recebe revisões.", "warning"); return; }
      if (!r.avaliado) { GI.ui.toast("Avalie o risco antes da primeira revisão.", "warning"); avaliar(codigo, { tipo: "inerente" }, aoConcluir); return; }
      var vig = r.residual || r.inerente, scoreAnt = vig.p * vig.i;
      var rotuloAv = r.residual ? "residual" : "inerente";
      var modal = null, seq = 0, manual = false;
      var cad = param.cadenciaDias;
      modal = GI.form.abrir({
        titulo: "Revisão periódica · " + r.codigo, subtitulo: r.titulo, tamanho: "lg", textoSalvar: "Registrar revisão",
        campos: [
          { id: "data", rotulo: "Data da revisão", tipo: "data", obrigatorio: true, valor: REF, maxData: REF, min: r.ultimaRevisao || r.identificadoEm },
          { id: "situacaoApurada", rotulo: "Situação apurada", tipo: "select", obrigatorio: true, valor: "Sem mudança",
            opcoes: API.APURACOES.map(function (a) { return { valor: a, texto: apurada(a, r.natureza) }; }) },
          { id: "p", rotulo: "Probabilidade atual", tipo: "select", obrigatorio: true, valor: vig.p,
            opcoes: param.probabilidades.map(function (x) { return { valor: x.nivel, texto: x.nivel + " " + x.nome + " (" + x.faixa + ")" }; }) },
          { id: "i", rotulo: "Impacto atual", tipo: "select", obrigatorio: true, valor: vig.i,
            opcoes: [1, 2, 3, 4, 5].map(function (n) { return { valor: n, texto: n + " " + nomeImp(n) }; }) },
          { id: "score", tipo: "info", rotulo: "", html: "" },
          { id: "comentario", rotulo: "Comentário da revisão", tipo: "textarea", obrigatorio: true, max: 1000, linhas: 3, ajuda: "Evidência da revisão; aparece na linha do tempo." },
          { id: "gatilho", rotulo: "Gatilho ocorreu?", tipo: "escolha", obrigatorio: true, opcoes: [{ valor: "sim", texto: "Sim" }, { valor: "nao", texto: "Não" }],
            ajuda: (r.gatilho ? "Gatilho: " + r.gatilho + ". " : "") + "Se sim, o sistema força a reavaliação e marca o risco na pauta de escalonamento." },
          { id: "proximaRevisao", rotulo: "Próxima revisão", tipo: "data", obrigatorio: true, valor: somaDias(REF, r.cadenciaDias || r.cadenciaMaxDias || 30),
            ajuda: "Sugerida pela cadência da severidade (" + Object.keys(cad).map(function (k) { return k + ": " + cad[k] + " dias"; }).join("; ").replace("critico", "crítico") + "). Pode antecipar, nunca postergar." },
          { id: "notificar", rotulo: "Notificar dono e gestor por e-mail", tipo: "check", valor: false, largura: "full" }
        ],
        aoMudar: function (v, ctx) {
          var score = Number(v.p) * Number(v.i);
          if (modal && ["Sem mudança", "Risco reduzido", "Risco agravado"].indexOf(v.situacaoApurada) >= 0 && score) {
            var esperada = score < scoreAnt ? "Risco reduzido" : score > scoreAnt ? "Risco agravado" : "Sem mudança";
            if (esperada !== v.situacaoApurada) { modal.definir({ situacaoApurada: esperada }); return; }
          }
          var n = ++seq;
          API.previa({ p: Number(v.p), i: Number(v.i), riscoVida: r.riscoVida }).then(function (pv) {
            if (n !== seq || !pv.score) return;
            var limite = v.data ? somaDias(v.data, pv.cadenciaDias) : null;
            if (modal && limite && !manual && v.proximaRevisao !== limite && (!v.proximaRevisao || v.proximaRevisao > limite || v.proximaRevisao <= v.data)) { modal.definir({ proximaRevisao: limite }); return; }
            ctx.info("score", '<div class="aval-card"><span class="aval-card__rotulo">Score ' + rotuloAv + " recalculado</span>" +
              '<div class="aval-card__score"><b>' + pv.score + "</b>" + sev(pv.sev, null, r.natureza) + '<span class="text-small text-muted">anterior: ' + scoreAnt +
              (pv.score === scoreAnt ? " (sem mudança)" : pv.score < scoreAnt ? " (redução)" : " (aumento)") + "</span></div>" +
              '<span class="text-small">Cadência da faixa ' + U.esc(pv.sev.nome) + ": " + pv.cadenciaDias + " dias · próxima revisão até " + F.data(limite) + "</span></div>");
          });
        },
        aoSalvar: function (v) {
          return API.revisar(r.codigo, { data: v.data, situacaoApurada: v.situacaoApurada, p: Number(v.p), i: Number(v.i), comentario: v.comentario,
            gatilho: v.gatilho, proximaRevisao: v.proximaRevisao, notificar: v.notificar }).then(function (x) {
            GI.ui.toast("Revisão registrada. Próxima em " + F.data(v.proximaRevisao) + ".", "success");
            if (v.notificar) GI.ui.toast("Simulação: e-mail ao dono e ao gestor. Nada foi enviado no protótipo.", "info");
            if (aoConcluir) aoConcluir(r.codigo);
            if (x.encerrar) setTimeout(function () { encerrar(r.codigo, x.encerrar, aoConcluir); }, 50);
            else if (x.reavaliar) {
              GI.ui.toast("Gatilho ocorreu: reavalie o risco agora (sugestão: subir a probabilidade).", "warning", 6000);
              setTimeout(function () { avaliar(r.codigo, null, aoConcluir); }, 50);
            }
          });
        }
      });
      var prox = modal.el.querySelector('[data-campo="proximaRevisao"] input');
      if (prox) prox.addEventListener("input", function () { manual = true; });
      return modal;
    });
  }

  /* ======================================================================
     Modal 6: Encerramento (e reabertura)
     ====================================================================== */
  function encerrar(codigo, motivo, aoConcluir) {
    if (!API.pode("Gestor")) { GI.ui.toast("Encerrar risco exige papel Gestor. Proponha o encerramento na revisão periódica.", "warning", 6000); return; }
    return Promise.all([API.risco(codigo), API.lista(null), pronto()]).then(function (res) {
      var r = res[0];
      if (!r || !r.ativo) return;
      var op = r.natureza === "Oportunidade";
      var outros = res[1].filter(function (x) { return x.projetoId === r.projetoId && x.codigo !== r.codigo; });
      var abertas = r.listaAcoes.filter(function (a) { return a.ehAcao && a.status !== "concluida"; });
      var mat = function (v) { return v.motivo === "Materializado"; };
      var ameacaMat = function (v) { return !op && v.motivo === "Materializado"; };
      var motivos = {
        "Não se materializou": "Não se materializou (janela de exposição encerrada)",
        "Materializado": op ? "Capturada (benefício obtido)" : "Materializado (virou problema real)",
        "Superado": "Superado pelo andamento do projeto",
        "Transferido": "Transferido por contrato ou seguro",
        "Duplicado": "Duplicado de outro risco"
      };
      GI.form.abrir({
        titulo: "Encerrar risco · " + r.codigo, subtitulo: r.titulo, tamanho: "lg", textoSalvar: "Encerrar risco",
        intro: (abertas.length ? '<div class="alert alert--warning">' + U.icone("alertTriangle") + '<div class="alert__body">' +
          (abertas.length === 1 ? "Existe 1 ação em aberto vinculada a este risco" : "Existem " + abertas.length + " ações em aberto vinculadas a este risco") +
          " (" + abertas.map(function (a) { return "item " + a.item; }).join(", ") + "). Conclua ou cancele antes de encerrar, salvo se o motivo for " + (op ? "Capturada" : "Materializado") + ".</div></div>" : "") +
          '<p class="text-small text-muted">Encerrar tira o risco da carteira ativa e registra a lição aprendida no acervo (08).</p>',
        campos: [
          { id: "motivo", rotulo: "Motivo do encerramento", tipo: "radio", obrigatorio: true, valor: motivo || "", largura: "full",
            opcoes: API.MOTIVOS_ENCERRAMENTO.map(function (k) { return { valor: k, texto: motivos[k] }; }) },
          { id: "data", rotulo: "Data do encerramento", tipo: "data", obrigatorio: true, valor: REF, maxData: REF, min: r.identificadoEm },
          { id: "duplicadoDe", rotulo: "Risco duplicado de", tipo: "select", obrigatorio: true, mostrarSe: function (v) { return v.motivo === "Duplicado"; },
            opcoes: outros.map(function (x) { return { valor: x.codigo, texto: x.codigo + " · " + x.titulo }; }) },
          { id: "impactoRealPrazoDias", rotulo: op ? "Benefício real em prazo (dias)" : "Impacto real em prazo (dias)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 999, valor: 0, mostrarSe: mat,
            ajuda: "Usado para calibrar as escalas em projetos futuros." },
          { id: "impactoRealCustoCentavos", rotulo: op ? "Benefício real em custo" : "Impacto real em custo", tipo: "moeda", obrigatorio: true, valor: 0, mostrarSe: mat },
          { id: "orientacaoMat", tipo: "info", rotulo: "", mostrarSe: ameacaMat,
            html: '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">Risco materializado vira problema: trate por ações na Central e, se exigir alterar escopo, prazo ou custo, por solicitação de mudança (08). As ações em aberto continuam na Central.</div></div>' },
          { id: "gerarAcao", rotulo: "Gerar ação na Central para tratar o problema (origem Risco)", tipo: "check", valor: true, largura: "full", mostrarSe: ameacaMat },
          { id: "acaoAssunto", rotulo: "Assunto da ação", tipo: "texto", obrigatorio: true, max: 255, largura: "full", valor: "Tratar o problema decorrente do risco " + r.codigo,
            mostrarSe: function (v) { return ameacaMat(v) && v.gerarAcao; } },
          { id: "acaoResponsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: r.donoId, mostrarSe: function (v) { return ameacaMat(v) && v.gerarAcao; } },
          { id: "acaoPrevista", rotulo: "Data prevista", tipo: "data", obrigatorio: true, min: REF, valor: somaDias(REF, 7), mostrarSe: function (v) { return ameacaMat(v) && v.gerarAcao; } },
          { id: "abrirSm", rotulo: "Exige alterar escopo, prazo ou custo: registrar solicitação de mudança (08)", tipo: "check", valor: false, largura: "full", mostrarSe: ameacaMat },
          { id: "licao", rotulo: "Lição aprendida", tipo: "textarea", obrigatorio: true, max: 1000, linhas: 3, placeholder: "O que este risco ensina para os próximos projetos",
            ajuda: "Sempre obrigatória, inclusive quando o risco não se materializou. Alimenta o acervo de lições (08)." }
        ],
        aoSalvar: function (v) {
          return API.encerrar(r.codigo, v).then(function (x) {
            GI.ui.toast("Risco encerrado (" + x.situacao + "). Lição " + x.licao + " criada no acervo (08).", "success", 6000);
            if (x.sm) GI.ui.toast("Solicitação de mudança " + x.sm + " registrada no módulo 08.", "info", 6000);
            if (x.acao) GI.ui.toast("Ação " + x.acao + " criada na Central para tratar o problema.", "info", 6000);
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }
  function reabrir(codigo, aoConcluir) {
    if (!API.pode("Gestor")) { GI.ui.toast("Reabrir risco exige papel Gestor.", "warning"); return; }
    GI.form.abrir({
      titulo: "Reabrir risco " + codigo, tamanho: "sm", textoSalvar: "Reabrir",
      campos: [{ id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 500, ajuda: "Grava linha no histórico do risco." }],
      aoSalvar: function (v) {
        return API.reabrir(codigo, v).then(function (x) { GI.ui.toast("Risco reaberto. Situação: " + x.situacao + ".", "success"); if (aoConcluir) aoConcluir(codigo); });
      }
    });
  }

  /* ======================================================================
     Modal 8: Excluir risco (exclusão lógica)
     ====================================================================== */
  function excluir(codigo, aoConcluir) {
    if (!API.pode("Gestor")) { GI.ui.toast("Excluir risco exige papel Gestor.", "warning"); return; }
    return API.risco(codigo).then(function (r) {
      if (!r) return;
      if (!r.ativo) { GI.ui.toast("Risco encerrado não é excluído: já saiu da carteira ativa.", "warning"); return; }
      var abertas = r.listaAcoes.filter(function (a) { return a.ehAcao && a.status !== "concluida"; });
      var m = GI.form.abrir({
        titulo: "Excluir risco", tamanho: "lg", textoSalvar: "Excluir risco", perigo: true,
        intro: "<p><b>" + U.esc(r.codigo) + "</b> · " + U.esc(r.titulo) + '</p><p class="mt-2">Confirma a exclusão deste risco?</p>' +
          '<div class="alert alert--info mt-2">' + U.icone("info") + '<div class="alert__body"><b>A exclusão é lógica:</b> o registro sai das listas e dos indicadores, mas permanece no banco e pode ser recuperado por um Admin. O número consumido não é reaproveitado.</div></div>' +
          (abertas.length ? '<div class="alert alert--warning mt-2">' + U.icone("alertTriangle") + '<div class="alert__body">Risco com ação em aberto não pode ser excluído: ' +
            abertas.map(function (a) { return "item " + U.esc(a.item) + " (" + U.esc(a.assunto) + ")"; }).join("; ") + ".</div></div>" : ""),
        campos: [
          { id: "motivo", rotulo: "Motivo da exclusão", tipo: "select", obrigatorio: true, opcoes: API.MOTIVOS_EXCLUSAO.map(function (x) { return { valor: x, texto: x }; }) },
          { id: "observacao", rotulo: "Observação", tipo: "textarea", max: 500, placeholder: "Detalhe o motivo", ajuda: "Obrigatória quando o motivo for Outro." }
        ],
        aoSalvar: function (v) {
          return API.excluir(r.codigo, v).then(function () { GI.ui.toast("Risco " + r.codigo + " excluído (exclusão lógica).", "success"); if (aoConcluir) aoConcluir(r.codigo); });
        }
      });
      if (abertas.length) { var b = m.el.querySelector(".modal__footer .btn:last-child"); b.disabled = true; b.title = "Conclua ou cancele as ações em aberto"; }
    });
  }

  GI.rsk = {
    pronto: pronto, projeto: projeto, contexto: contexto, sev: sev, scoreCel: scoreCel, situacao: situacao, natureza: natureza, estrategia: estrategia,
    apurada: apurada, cadencia: cadencia, nomeProb: nomeProb, nomeImp: nomeImp, linkFicha: linkFicha, pessoas: pessoas, ordemFaixa: ordemFaixa,
    tabelaAcoes: tabelaAcoes, erroApi: erroApi, somaDias: somaDias,
    novo: novo, editar: editar, avaliar: avaliar, plano: plano, aprovarPlano: aprovarPlano, novaAcao: novaAcao, revisar: revisar,
    encerrar: encerrar, reabrir: reabrir, excluir: excluir,
    param: function () { return param; }, categorias: function () { return categorias; }
  };
})(window.GI = window.GI || {});
