/* ==========================================================================
   governanca.js | Apoio comum às telas do módulo 08 Governança (GI.gov)

   GI.gov.pronto()                 -> Promise (cadastros e parâmetros de 08)
   GI.gov.projeto(aoTrocar)        -> id do projeto (?projeto= ou atual); preenche #f-projeto
   GI.gov.situacaoSm(t) / prioridade(t) / custo(c) / prazo(d) / etapas(s)
   GI.gov.situacaoLicao(t) / tipoLicao(t) / linkOrigemLicao(l)
   GI.gov.chips(el, filtro, rotulos, aoRemover) / filtros(cfg)
   Modais de mudança: novaMudanca, editarMudanca, iniciarAnalise, analise, decidir,
     reapresentar, iniciarImplementacao, encerrar, cancelar; botoesSm(s) e acaoSm(nome, codigo, cb)
   Modais de lição: novaLicao, editarLicao, enviarLicao, validarLicao, publicarLicao,
     aplicarLicao, verLicao
   Regras, alçada e integrações ficam em GI.api.governanca; a tela só exibe.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, API = GI.api.governanca;
  var REF = GI.api.referencia();
  var param = null, carregando = null, seq = 0;

  function pronto() {
    if (!carregando) {
      carregando = Promise.all([U.pronto(), GI.api.parametros()]).then(function (r) {
        param = { mudancas: r[1].mudancas || {}, licoes: r[1].licoes || {} };
        return param;
      });
    }
    return carregando;
  }
  function erroApi(e) { GI.ui.toast((e && e.erros ? e.erros.map(function (x) { return x.msg || x; }).join(" ") : String(e)), "warning", 7000); }
  function somarDias(iso, n) { var d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); }

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
  function pessoas() {
    return Object.keys(U.mapas.pessoas).map(function (k) { var p = U.mapas.pessoas[k]; return { valor: k, texto: p.nome + " (" + p.funcao + ")" }; })
      .sort(function (a, b) { return a.texto.localeCompare(b.texto); });
  }
  function projetos() {
    return Object.keys(U.mapas.projetos).map(function (k) { var p = U.mapas.projetos[k]; return { valor: k, texto: p.codigo + " " + p.nome }; });
  }
  function lista(v) { return v.map(function (x) { return { valor: x, texto: x }; }); }
  function alerta(tipo, html, icone) {
    return '<div class="alert alert--' + tipo + ' mb-4">' + U.icone(icone || (tipo === "info" ? "info" : tipo === "success" ? "checkCircle" : "alertTriangle")) + '<div class="alert__body">' + html + "</div></div>";
  }
  function campoInfo(rotulo, html) { return '<div class="field"><span class="field__label">' + U.esc(rotulo) + "</span><div>" + (html || "·") + "</div></div>"; }

  /* ---------------- Formatação ---------------- */
  var TIPO_SIT_SM = { "Registrada": "neutral", "Em análise de impacto": "info", "Aguardando comitê": "purple", "Aprovada": "success", "Aprovada com condições": "success",
    "Rejeitada": "danger", "Adiada": "warning", "Em implementação": "info", "Encerrada": "primary", "Cancelada": "neutral" };
  function situacaoSm(t) { return U.badge(t, TIPO_SIT_SM[t] || "neutral", true); }
  function prioridade(t) { return t === "Normal" ? '<span class="text-small text-muted">Normal</span>' : U.badge(t, t === "Emergencial" ? "danger" : "warning"); }
  /* Custo: sem cor (a mudança aprovada não é sobrecusto); redução em verde-água. Prazo: atraso em laranja. */
  function custo(c) {
    if (c == null) return '<span class="text-small text-muted">a analisar</span>';
    if (!c) return '<span class="text-muted">R$ 0</span>';
    return '<span class="' + (c < 0 ? "valor--economia" : "") + '">' + (c > 0 ? "+" : "") + U.esc(F.moeda(c)) + "</span>";
  }
  function prazo(d) {
    if (d == null) return '<span class="text-small text-muted">a analisar</span>';
    if (!d) return '<span class="text-muted">0 dias</span>';
    return '<span class="' + (d > 0 ? "valor--negativo" : "valor--positivo") + '">' + (d > 0 ? "+" : "") + U.esc(U.plural(d, "dia")) + "</span>";
  }
  /* Etapas do fluxo (stepper) */
  function etapas(s) {
    var fim = s.situacao === "Rejeitada" ? "Rejeitada" : s.situacao === "Cancelada" ? "Cancelada" : "Encerramento";
    return '<ol class="stepper stepper--sm" aria-label="Etapas da mudança">' + API.ETAPAS.map(function (e, i) {
      var nome = i === 4 ? fim : e;
      var terminal = ["Rejeitada", "Encerrada", "Cancelada"].indexOf(s.situacao) >= 0;
      var cls = i < s.etapa || (terminal && i === 4) ? "is-done" : i === s.etapa ? "is-current" : "";
      return '<li class="step ' + cls + '"' + (cls === "is-current" ? ' aria-current="step"' : "") + '><span class="step__dot" aria-hidden="true"></span><span class="step__label">' + U.esc(nome) + "</span></li>";
    }).join("") + "</ol>";
  }

  var TIPO_SIT_LIC = { "Rascunho": "neutral", "Em validação": "warning", "Validada": "info", "Publicada": "success" };
  function situacaoLicao(t) { return U.badge(t, TIPO_SIT_LIC[t] || "neutral", true); }
  function tipoLicao(t) { return U.badge(t, t === "A repetir" ? "success" : "danger"); }
  /* Vínculo ao registro de origem (rastreabilidade) */
  function linkOrigemLicao(l) {
    var r = l.origemRef;
    if (!r) return null;
    switch (l.origemTipo) {
      case "Ata (01)": return l.ataId ? U.tela("central-acoes", "ata", { id: l.ataId }) : U.tela("central-acoes", "atas");
      case "Punch list (02)": return U.tela("planejamento", "punch-list", { item: r });
      case "Contrato ou claim (03)": return r.indexOf("CT-") === 0 ? U.tela("financeiro", "contrato", { numero: r }) : U.tela("financeiro", "contratos", { busca: r });
      case "Suprimentos (04)": return r.indexOf("PED-") === 0 ? U.tela("suprimentos", "diligenciamento", { pedido: r }) : U.tela("suprimentos", "plano-compras", { busca: r });
      case "Risco encerrado (05)": return U.tela("riscos", "ficha", { codigo: r });
      case "RNC (06)": return U.tela("qualidade", "rnc", { busca: r });
      case "Ocorrência HSE (07)": return U.tela("hse", "ocorrencias", { busca: r });
      case "Mudança (08)": return U.tela("governanca", "mudanca", { codigo: r });
      default: return null;
    }
  }
  function origemHtml(l) {
    var h = linkOrigemLicao(l);
    return U.esc(l.origemTipo) + (l.origemRef ? " · " + (h ? '<a href="' + h + '">' + U.esc(l.origemRef) + "</a>" : U.esc(l.origemRef)) : "");
  }

  /* ---------------- Filtros em modal e chips ---------------- */
  function chips(el, filtro, rotulos, aoRemover) {
    var ks = Object.keys(rotulos).filter(function (k) { return filtro[k]; });
    el.innerHTML = ks.map(function (k) {
      var v = rotulos[k].texto ? rotulos[k].texto(filtro[k]) : filtro[k];
      return '<span class="chip"><span class="chip__label">' + U.esc(rotulos[k].nome) + ": " + U.esc(v) + '</span><button type="button" class="chip__remove" data-chip="' + k + '" aria-label="Remover filtro ' + U.esc(rotulos[k].nome) + '">' + U.icone("x") + "</button></span>";
    }).join("") + (ks.length > 1 ? '<button type="button" class="btn btn--ghost btn--sm" data-chip="*">Limpar filtros</button>' : "");
    el.hidden = !ks.length;
    el.onclick = function (ev) {
      var b = ev.target.closest("[data-chip]");
      if (!b) return;
      var k = b.getAttribute("data-chip");
      if (k === "*") ks.forEach(function (x) { filtro[x] = null; }); else filtro[k] = null;
      aoRemover();
    };
  }
  /* cfg: { titulo, campos:[{ id, rotulo, opcoes }], filtro, aoAplicar } */
  function filtros(cfg) {
    return GI.form.abrir({
      titulo: cfg.titulo || "Filtros", tamanho: "lg", textoSalvar: "Aplicar",
      campos: cfg.campos.map(function (c) { return { id: c.id, rotulo: c.rotulo, tipo: "select", vazio: c.vazio || "Todos", opcoes: c.opcoes, valor: cfg.filtro[c.id] || "" }; }),
      extras: [{ texto: "Limpar", acao: function (m) { var v = {}; cfg.campos.forEach(function (c) { v[c.id] = ""; }); m.definir(v); } }],
      aoSalvar: function (v) { cfg.campos.forEach(function (c) { cfg.filtro[c.id] = v[c.id] || null; }); cfg.aoAplicar(); }
    });
  }

  /* ======================================================================
     Mudanças (SM)
     ====================================================================== */
  var FLUXO_SM = "Registrada &rarr; Em análise de impacto &rarr; Aguardando comitê &rarr; Aprovada, Aprovada com condições, Rejeitada ou Adiada &rarr; Em implementação &rarr; Encerrada.";

  /* Itens de custo (nível 3) da EAC do projeto, para as transferências do remanejamento */
  function folhasEac(projetoId) {
    return GI.api.financeiro.mapaControle(projetoId).then(function (m) { return m.itens.filter(function (x) { return x.nivel === 3; }); }).catch(function () { return []; });
  }
  /* Saldos das reservas do projeto (para a SM de liberação) */
  function saldosReservas(projetoId, exceto) {
    var c = API.saldoReserva(projetoId, "Contingência", exceto), g = API.saldoReserva(projetoId, "Gerencial", exceto);
    return c ? "Saldo da reserva de contingência: " + F.moeda(c.saldo) + ". Saldo da reserva gerencial: " + F.moeda(g ? g.saldo : 0) + "." : "O projeto não tem reservas constituídas.";
  }
  function camposSm(s, folhas, projetoId) {
    var emerg = function (v) { return v.prioridade === "Emergencial"; };
    var reman = function (v) { return v.tipo === API.TIPO_REMANEJAMENTO; };
    var liber = function (v) { return v.tipo === API.TIPO_LIBERACAO; };
    var pid = s ? s.projetoId : projetoId;
    var opFolhas = (folhas || []).map(function (x) { return { valor: x.codigo, texto: x.codigo + " " + x.descricao }; });
    var novos = (s && s.remanejamentos || []).filter(function (t) { return t.novoItem; }).map(function (t) { return { valor: t.destino, texto: t.destino + " " + t.novoItem.descricao + " (item novo)" }; });
    return [
      { id: "titulo", rotulo: "Título", tipo: "texto", obrigatorio: true, max: 150, largura: "full", valor: s ? s.titulo : "" },
      { id: "tipo", rotulo: "Tipo", tipo: "select", obrigatorio: true, opcoes: lista(API.TIPOS), valor: s ? s.tipo : "" },
      { id: "origem", rotulo: "Origem", tipo: "select", obrigatorio: true, opcoes: lista(API.ORIGENS.concat(s && API.ORIGENS.indexOf(s.origem) < 0 ? [s.origem] : [])), valor: s ? s.origem : "" },
      { id: "prioridade", rotulo: "Prioridade", tipo: "escolha", obrigatorio: true, largura: "full", valor: s ? s.prioridade : "Normal",
        opcoes: [{ valor: "Normal", texto: "Normal", sub: "fluxo completo" }, { valor: "Urgente", texto: "Urgente", sub: "próxima reunião do comitê" },
          { valor: "Emergencial", texto: "Emergencial", sub: "pode executar antes, com ratificação" }] },
      { id: "dataSolicitacao", rotulo: "Data da solicitação", tipo: "data", obrigatorio: true, valor: s ? s.dataSolicitacao : REF, maxData: REF },
      { id: "solicitanteId", rotulo: "Solicitante", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: s ? s.solicitanteId : API.sessaoPessoa() },
      { id: "descricao", rotulo: "Descrição e justificativa", tipo: "textarea", obrigatorio: true, max: 1000, linhas: 4, valor: s ? s.descricao : "",
        ajuda: "O que muda, por que e o que acontece se a mudança não for feita." },
      { id: "execucaoAntecipada", rotulo: "A execução começou antes da decisão do comitê (emergência)", tipo: "check", mostrarSe: emerg, valor: !!(s && s.emergencia) },
      { id: "inicioEmergencia", rotulo: "Início da execução", tipo: "data", obrigatorio: true, maxData: REF, valor: s && s.emergencia ? s.emergencia.inicio : REF,
        mostrarSe: function (v) { return emerg(v) && v.execucaoAntecipada; } },
      { id: "justificativaEmergencia", rotulo: "Justificativa da emergência", tipo: "textarea", obrigatorio: true, max: 500, linhas: 2, valor: s && s.emergencia ? s.emergencia.justificativa : "",
        mostrarSe: function (v) { return emerg(v) && v.execucaoAntecipada; }, ajuda: "Risco à segurança, ao meio ambiente ou à continuidade que impedia esperar o comitê." },
      { id: "remanejamentos", rotulo: "Transferências entre itens da EAC (03)", tipo: "repetir", rotuloItem: "Transferência", textoAdicionar: "Adicionar transferência",
        minimo: 1, maximo: 10, mostrarSe: reman, valor: s && s.remanejamentos ? s.remanejamentos.map(function (t) { return { origem: t.origem, destino: t.destino, valorCentavos: t.valorCentavos }; }) : [{}],
        ajuda: "O total do orçamento não muda. A origem cede saldo ainda não comprometido; a aprovação desta SM aplica a transferência na EAC.",
        itens: [
          { id: "origem", rotulo: "Origem", tipo: "select", obrigatorio: true, opcoes: opFolhas },
          { id: "destino", rotulo: "Destino", tipo: "select", obrigatorio: true, opcoes: opFolhas.concat(novos) },
          { id: "valorCentavos", rotulo: "Valor", tipo: "moeda", obrigatorio: true }
        ] },
      { id: "liberacaoReserva", rotulo: "Reserva a liberar", tipo: "select", obrigatorio: true, mostrarSe: liber, valor: s && s.liberacao ? s.liberacao.reserva : "",
        opcoes: [{ valor: "Contingência", texto: "Reserva de contingência" }, { valor: "Gerencial", texto: "Reserva gerencial" }] },
      { id: "liberacaoValor", rotulo: "Valor a liberar", tipo: "moeda", obrigatorio: true, mostrarSe: liber, valor: s && s.liberacao ? s.liberacao.valorCentavos : "",
        ajuda: (pid != null ? saldosReservas(pid, s ? s.codigo : null) + " " : "") + "Saldo que não será mais necessário (risco encerrado, fase concluída ou encerramento): sai da reserva e do orçamento do projeto. Decisão do Comitê (patrocinador)." },
      { id: "anexos", rotulo: "Anexos (desenhos, propostas, estimativas)", tipo: "arquivo", multiplo: true, aceitar: ["pdf", "jpg", "jpeg", "png", "xlsx", "docx", "dwg"] }
    ];
  }
  function novaMudanca(projetoId, aoConcluir) {
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar solicitações de mudança.", "warning"); return; }
    if (projetoId == null) { U.noProjeto("nova", "Nova solicitação de mudança"); return; }
    return Promise.all([pronto(), folhasEac(projetoId)]).then(function (r) {
      return GI.form.abrir({
        titulo: "Nova solicitação de mudança", tamanho: "lg", textoSalvar: "Registrar solicitação",
        intro: alerta("info", "Toda mudança de escopo, prazo, custo, qualidade ou contrato nasce como solicitação formal; nada altera linha de base sem SM aprovada. Fluxo: " + FLUXO_SM +
          " O MOC de segurança de processo não é tratado aqui."),
        campos: camposSm(null, r[1], projetoId),
        aoSalvar: function (v) {
          var d = Object.assign({ projetoId: projetoId }, v);
          return API.salvarMudanca(d).then(function (r) {
            GI.ui.toast("Solicitação " + r.codigo + " registrada.", "success");
            (r.avisos || []).forEach(function (a) { GI.ui.toast(a, "warning", 8000); });
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }
  function editarMudanca(codigo, aoConcluir) {
    return API.mudanca(codigo).then(function (s) {
      if (!s) return GI.ui.toast("Solicitação não encontrada.", "warning");
      return folhasEac(s.projetoId).then(function (folhas) { return GI.form.abrir({
        titulo: "Editar solicitação · " + s.codigo, subtitulo: s.situacao, tamanho: "lg",
        campos: camposSm(s, folhas).filter(function (c) { return c.id !== "anexos"; }),
        aoSalvar: function (v) {
          return API.salvarMudanca(Object.assign({ codigo: codigo }, v)).then(function (r) {
            GI.ui.toast("Solicitação atualizada.", "success");
            (r.avisos || []).forEach(function (a) { GI.ui.toast(a, "warning", 8000); });
            if (aoConcluir) aoConcluir(codigo);
          });
        }
      }); });
    });
  }
  function iniciarAnalise(codigo, aoConcluir) {
    return Promise.all([API.mudanca(codigo), pronto()]).then(function (r) {
      var s = r[0];
      if (!s) return GI.ui.toast("Solicitação não encontrada.", "warning");
      var proj = U.projeto(s.projetoId) || {};
      return GI.form.abrir({
        titulo: "Iniciar análise de impacto · " + s.codigo, subtitulo: s.titulo, textoSalvar: "Iniciar análise",
        intro: '<p class="text-small text-muted">A análise é obrigatória antes da decisão: escopo, prazo, custo, qualidade, riscos, SMS e contrato.</p>',
        campos: [
          { id: "responsavelId", rotulo: "Responsável pela análise", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: proj.gerenteId },
          { id: "prazo", rotulo: "Prazo da análise", tipo: "data", obrigatorio: true, min: REF, valor: somarDias(REF, param.mudancas.prazoAnaliseDias || 10),
            ajuda: "Padrão: " + (param.mudancas.prazoAnaliseDias || 10) + " dias (parâmetro)." }
        ],
        aoSalvar: function (v) {
          return API.iniciarAnalise(codigo, v).then(function () { GI.ui.toast("Análise de impacto iniciada.", "success"); if (aoConcluir) aoConcluir(codigo); });
        }
      });
    });
  }
  function analise(codigo, aoConcluir) {
    return Promise.all([API.mudanca(codigo), pronto()]).then(function (r) {
      var s = r[0];
      if (!s) return GI.ui.toast("Solicitação não encontrada.", "warning");
      var im = s.impacto || {};
      var revisao = s.situacao !== "Em análise de impacto";
      var semImp = ["Sem impacto"];
      function alcadaInfo(v) {
        var ex = API.alcadaExigida(s.projetoId, Math.max(Math.abs(v.custoCentavos || 0), s.remanejamentoTotal || 0), v.afetaMarcoContratual);
        return '<span class="text-small">' + U.esc("Alçada mínima: " + ex.alcada + ". Até " + F.moeda(ex.limiteCentavos) + " (" + F.num(param.mudancas.alcadaGerentePctOrcamento || 1) +
          "% do orçamento) e sem impacto em marco contratual, decide o gerente do projeto; acima, o Comitê. A alçada pode ser elevada, nunca rebaixada.") + "</span>";
      }
      return GI.form.abrir({
        titulo: "Análise de impacto · " + s.codigo, subtitulo: s.titulo, tamanho: "lg", textoSalvar: revisao ? "Salvar revisão" : "Concluir e enviar para decisão",
        intro: (revisao ? alerta("warning", "Solicitação já enviada para decisão: a revisão fica registrada no histórico.") : "") +
          (s.liberacao ? alerta("info", "<b>Liberação de reserva</b>: " + U.esc(F.moeda(s.liberacao.valorCentavos)) + " da reserva " + (s.liberacao.reserva === "Gerencial" ? "gerencial" : "de contingência") +
            ". Impacto em custo zero (o orçado da EAC não muda); decisão do Comitê.") : "") +
          (s.remanejamentoTotal ? alerta("info", "<b>Remanejamento de orçamento</b>: " + U.esc(U.plural(s.remanejamentosDetalhe.length, "transferência", "transferências")) + " de " + U.esc(F.moeda(s.remanejamentoTotal)) +
            " entre itens da EAC. Impacto em custo zero (o total não muda); a alçada considera o valor remanejado. A aprovação aplica na EAC.") : "") +
          '<p class="text-small text-muted">Custo em reais (negativo para redução). Prazo em dias corridos no caminho crítico (negativo para antecipação). Informe "Sem impacto" nas dimensões não afetadas.</p>',
        campos: [
          { id: "custoCentavos", rotulo: "Impacto em custo", tipo: "moeda", obrigatorio: true, valor: im.custoCentavos != null ? im.custoCentavos : (s.remanejamentoTotal ? 0 : "") },
          { id: "prazoDias", rotulo: "Impacto em prazo (dias no caminho crítico)", tipo: "numero", obrigatorio: true, min: -365, maxNumero: 365, valor: im.prazoDias != null ? im.prazoDias : "" },
          { id: "afetaMarcoContratual", rotulo: "Afeta marco contratual (prazo de entrega ao cliente ou de contrato)", tipo: "check", largura: "full", valor: !!im.afetaMarcoContratual },
          { id: "alcadaInfo", tipo: "info", html: "" },
          { id: "alcada", rotulo: "Alçada de decisão", tipo: "escolha", obrigatorio: true, valor: s.alcada || "", opcoes: [
            { valor: "Gerente do projeto", texto: "Gerente do projeto" }, { valor: "Comitê", texto: "Comitê de Controle de Mudanças", sub: "patrocinador, cliente, planejamento e custos" }] },
          { id: "fonteRecurso", rotulo: "Fonte do recurso", tipo: "select", obrigatorio: true, opcoes: lista(API.FONTES), valor: s.fonteRecurso || "",
            mostrarSe: function (v) { return v.custoCentavos > 0; },
            ajuda: s.contingencia ? "Saldo da reserva de contingência: " + F.moeda(s.contingencia.saldo) + " de " + F.moeda(s.contingencia.total) + "." : "" },
          { id: "escopo", rotulo: "Escopo", tipo: "texto", obrigatorio: true, max: 300, largura: "full", sugestoes: semImp, valor: im.escopo || "" },
          { id: "qualidade", rotulo: "Qualidade e especificação", tipo: "texto", obrigatorio: true, max: 300, largura: "full", sugestoes: semImp, valor: im.qualidade || "" },
          { id: "riscos", rotulo: "Riscos novos ou alterados (05)", tipo: "texto", obrigatorio: true, max: 300, largura: "full", sugestoes: semImp, valor: im.riscos || "",
            ajuda: "Cite os códigos (ex.: RSK-TN-2026-0003) para a revisão na aprovação." },
          { id: "sms", rotulo: "SMS", tipo: "texto", obrigatorio: true, max: 300, largura: "full", sugestoes: semImp, valor: im.sms || "" },
          { id: "contrato", rotulo: "Contrato", tipo: "texto", obrigatorio: true, max: 300, largura: "full", sugestoes: semImp, valor: im.contrato || "",
            ajuda: "Aditivo previsto (ex.: Aditivo CT-2026-012) ou Sem impacto." },
          { id: "eacItens", rotulo: "Itens da EAC afetados (03)", tipo: "texto", max: 120, valor: (im.eacItens || []).join(", "), placeholder: "1.2.1, 2.1.4",
            ajuda: "Códigos de itens de custo (nível 3), separados por vírgula." },
          { id: "atividades", rotulo: "Atividades do cronograma afetadas (02)", tipo: "texto", max: 200, valor: im.atividades || "" }
        ],
        extras: revisao ? [] : [{ texto: "Salvar rascunho", acao: "rascunho" }],
        aoMudar: function (v, ctx) { ctx.info("alcadaInfo", alcadaInfo(v)); },
        aoSalvar: function (v, api, acao) {
          var enviar = !revisao && acao !== "rascunho";
          return API.salvarAnalise(codigo, v, enviar).then(function (r) {
            GI.ui.toast(enviar ? "Análise concluída; solicitação enviada para decisão (" + v.alcada + ")." : "Análise de impacto salva.", "success", 6000);
            (r.avisos || []).forEach(function (a) { GI.ui.toast(a, "warning", 8000); });
            if (aoConcluir) aoConcluir(codigo);
          });
        }
      });
    });
  }
  function decidir(codigo, aoConcluir) {
    return Promise.all([API.mudanca(codigo), pronto(), GI.api.listar("atas")]).then(function (r) {
      var s = r[0], atas = r[2];
      if (!s) return GI.ui.toast("Solicitação não encontrada.", "warning");
      if (!API.pode("Gestor")) return GI.ui.toast("Registrar a decisão exige papel Gestor (secretaria do Comitê ou gerente do projeto).", "warning");
      var proj = U.projeto(s.projetoId) || {};
      var comite = s.alcada === "Comitê";
      var sug = s.acoesSugeridas || [];
      var aprova = function (v) { return v.resultado === "Aprovada" || v.resultado === "Aprovada com condições"; };
      var atasProj = atas.filter(function (a) { return a.projetoId === s.projetoId; }).sort(function (a, b) { return a.data < b.data ? 1 : -1; });
      var vistas = {};
      atasProj = atasProj.filter(function (a) { if (vistas[a.numero]) return false; vistas[a.numero] = true; return true; });
      var resumo = '<div class="form-grid mb-4">' + campoInfo("Alçada", U.esc(s.alcada)) + campoInfo("Impacto em custo", custo(s.custoCentavos)) +
        campoInfo("Impacto em prazo", prazo(s.prazoDias)) + campoInfo("Fonte do recurso", U.esc(s.fonteRecurso || "sem custo")) + "</div>" +
        (s.liberacao ? alerta("info", "<b>Liberação de reserva</b>: " + U.esc(F.moeda(s.liberacao.valorCentavos)) + " da reserva " + (s.liberacao.reserva === "Gerencial" ? "gerencial" : "de contingência") + ". A aprovação reduz o saldo da reserva e o orçamento do projeto; o saldo é conferido de novo.") : "") +
        (s.remanejamentoTotal ? alerta("info", "<b>Remanejamento na EAC</b>: " + U.esc(s.remanejamentosDetalhe.map(function (t) { return F.moeda(t.valorCentavos) + " de " + t.origem + " para " + t.destino + (t.novoItem ? " (item novo)" : ""); }).join("; ")) +
          ". A aprovação aplica as transferências na EAC; o saldo livre é conferido de novo.") : "") +
        (s.fonteRecurso === "Reserva de contingência" && s.contingencia ? '<p class="text-small text-muted mb-4">Saldo da reserva de contingência antes desta SM: ' + U.esc(F.moeda(s.contingencia.saldo)) + ".</p>" : "") +
        (s.emergencia ? alerta("warning", "<b>Ratificação de mudança emergencial</b> executada desde " + F.data(s.emergencia.inicio) + ".") : "");
      var part = comite ? [proj.gerenteId, API.sessaoPessoa()] : [proj.gerenteId];
      return GI.form.abrir({
        titulo: (comite ? "Decisão do comitê · " : "Decisão do gerente do projeto · ") + s.codigo, subtitulo: s.titulo, tamanho: "lg", textoSalvar: "Registrar decisão",
        intro: resumo,
        campos: [
          { id: "resultado", rotulo: "Decisão", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: [
            { valor: "Aprovada", texto: "Aprovada" }, { valor: "Aprovada com condições", texto: "Aprovada com condições" },
            { valor: "Rejeitada", texto: "Rejeitada" }, { valor: "Adiada", texto: "Adiada", sub: "volta à pauta" }] },
          { id: "data", rotulo: "Data da decisão", tipo: "data", obrigatorio: true, valor: REF, min: s.impacto && s.impacto.dataAnalise, maxData: REF },
          { id: "ataId", rotulo: "Ata da reunião (01)", tipo: "select", vazio: "Sem ata vinculada", opcoes: atasProj.map(function (a) { return { valor: a.id, texto: a.numero + " · " + F.data(a.data) + " · " + a.tipoReuniao }; }) },
          { id: "participantesIds", rotulo: comite ? "Participantes do comitê (quórum de " + (param.mudancas.quorumComite || 3) + ")" : "Decisor (gerente do projeto)", tipo: "multi", obrigatorio: true,
            opcoes: pessoas(), valor: part.filter(Boolean).map(String) },
          { id: "justificativa", rotulo: "Justificativa da decisão", tipo: "textarea", obrigatorio: true, max: 600, linhas: 3 },
          { id: "condicoes", rotulo: "Condições", tipo: "textarea", obrigatorio: true, max: 600, linhas: 2, mostrarSe: function (v) { return v.resultado === "Aprovada com condições"; } },
          { id: "reapresentarEm", rotulo: "Reapresentar em", tipo: "data", obrigatorio: true, min: REF, mostrarSe: function (v) { return v.resultado === "Adiada"; } },
          { id: "acoes", rotulo: "Ações de implementação a criar na Central (origem Mudança)", tipo: "multi", mostrarSe: function (v) { return aprova(v) && sug.length; },
            opcoes: sug.map(function (a) { return { valor: a.chave, texto: a.assunto + " · " + U.pessoa(a.responsavelId) }; }), valor: sug.map(function (a) { return a.chave; }) },
          { id: "prevista", rotulo: "Data prevista das ações", tipo: "data", obrigatorio: true, min: REF, valor: somarDias(REF, param.mudancas.prazoAcoesDias || 15),
            mostrarSe: function (v) { return aprova(v) && sug.length && v.acoes && v.acoes.length; } }
        ],
        aoSalvar: function (v) {
          if (v.ataId) v.ataId = Number(v.ataId);
          return API.decidir(codigo, v).then(function (res) {
            GI.ui.toast("Decisão registrada: " + v.resultado + "." + (res.acoes ? " " + U.plural(res.acoes, "ação criada", "ações criadas") + " na Central." : ""), "success", 6000);
            if (aprova(v) && s.custoCentavos) GI.ui.toast("Custo aprovado: gere a nova revisão da EAC em 03 Gestão Financeira.", "info", 8000);
            if (aprova(v) && s.liberacao) GI.ui.toast("Liberação de " + F.moeda(s.liberacao.valorCentavos) + " registrada na reserva (03 Contingência).", "info", 8000);
            if (aprova(v) && s.remanejamentoTotal) GI.ui.toast("Remanejamento de " + F.moeda(s.remanejamentoTotal) + " aplicado na EAC (03).", "info", 8000);
            if (aoConcluir) aoConcluir(codigo);
          });
        }
      });
    });
  }
  function confirmar(titulo, mensagem, fn, sucesso, aoConcluir, codigo) {
    GI.modal.confirm({ title: titulo, message: mensagem }).then(function (ok) {
      if (!ok) return;
      fn().then(function () { GI.ui.toast(sucesso, "success"); if (aoConcluir) aoConcluir(codigo); }).catch(erroApi);
    });
  }
  function reapresentar(codigo, aoConcluir) {
    confirmar("Reapresentar solicitação", "Reapresentar a " + codigo + " para decisão? A decisão de adiamento fica no histórico.", function () { return API.reapresentar(codigo); },
      "Solicitação reapresentada para decisão.", aoConcluir, codigo);
  }
  function iniciarImplementacao(codigo, aoConcluir) {
    confirmar("Iniciar implementação", "Confirma o início da implementação da " + codigo + "? As ações de implementação ficam na Central de Ações.", function () { return API.iniciarImplementacao(codigo); },
      "Implementação iniciada.", aoConcluir, codigo);
  }
  function encerrar(codigo, aoConcluir) {
    return Promise.all([API.mudanca(codigo), pronto()]).then(function (r) {
      var s = r[0];
      if (!s) return GI.ui.toast("Solicitação não encontrada.", "warning");
      var im = s.impacto || {};
      var exCron = !!im.prazoDias, exCont = !!im.contrato && !/^sem impacto$/i.test(im.contrato), exRisc = !!im.riscos && !/^sem impacto$/i.test(im.riscos);
      function linha(ok, texto) { return '<li class="feed__item' + (ok ? "" : " feed__item--warning") + '"><span class="feed__icon">' + U.icone(ok ? "checkCircle" : "alertTriangle") + '</span><span class="feed__body">' + texto + "</span></li>"; }
      var conf = '<ul class="feed mb-4">' +
        linha(!s.acoesAbertas, s.acoesTotal ? (s.acoesAbertas ? U.esc(U.plural(s.acoesAbertas, "ação de implementação em aberto", "ações de implementação em aberto")) + " na Central" : "Ações de implementação concluídas (" + s.acoesTotal + ")") : "Sem ações de implementação vinculadas") +
        (s.exigeEac ? linha(s.eacRevisao != null, s.eacRevisao != null ? "Custo incorporado à EAC na Rev " + s.eacRevisao : "Custo ainda não incorporado à EAC (03 Gestão Financeira > EAC > Nova revisão)") : "") +
        (s.exigeEap ? linha(s.eapRevisao != null, s.eapRevisao != null ? "Escopo incorporado à EAP na Rev " + s.eapRevisao : "Escopo ainda não incorporado à EAP (02 Planejamento > EAP > Nova revisão)") : "") +
        (s.aditivos.length ? linha(true, "Aditivos vinculados: " + U.esc(s.aditivos.map(function (a) { return a.contrato + " " + a.numero; }).join(", "))) : "") +
        "</ul>";
      var bloqueio = s.acoesAbertas || (s.exigeEac && s.eacRevisao == null) || (s.exigeEap && s.eapRevisao == null);
      return GI.form.abrir({
        titulo: "Encerrar mudança · " + s.codigo, subtitulo: s.titulo, tamanho: "lg", textoSalvar: "Encerrar mudança",
        intro: '<h3 class="section-title">Conferência das linhas de base</h3>' + conf + (bloqueio ? alerta("warning", "Há pendências que impedem o encerramento; o sistema vai recusar enquanto existirem.") : ""),
        campos: [
          { id: "cronograma", rotulo: "Linha de base do cronograma e Curva S física atualizadas (02)", tipo: "check", largura: "full", mostrarSe: function () { return exCron; } },
          { id: "contrato", rotulo: "Aditivo contratual formalizado (03)", tipo: "check", largura: "full", mostrarSe: function () { return exCont; } },
          { id: "riscos", rotulo: "Riscos afetados revisados no registro (05)", tipo: "check", largura: "full", mostrarSe: function () { return exRisc; } },
          { id: "data", rotulo: "Data do encerramento", tipo: "data", obrigatorio: true, valor: REF, min: s.implementacao && s.implementacao.inicio, maxData: REF },
          { id: "observacao", rotulo: "Observações", tipo: "textarea", max: 500, linhas: 2 },
          { id: "registrarLicao", rotulo: "Registrar lição aprendida desta mudança (08)", tipo: "check", largura: "full" },
          { id: "licaoTitulo", rotulo: "Título da lição", tipo: "texto", obrigatorio: true, max: 150, largura: "full", valor: s.titulo, mostrarSe: function (v) { return v.registrarLicao; } },
          { id: "licaoTipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, mostrarSe: function (v) { return v.registrarLicao; },
            opcoes: [{ valor: "A repetir", texto: "A repetir", sub: "boa prática" }, { valor: "A evitar", texto: "A evitar", sub: "problema" }] },
          { id: "licaoFase", rotulo: "Fase", tipo: "select", obrigatorio: true, opcoes: lista(API.FASES), valor: "Construção", mostrarSe: function (v) { return v.registrarLicao; } },
          { id: "licaoDisciplina", rotulo: "Disciplina", tipo: "texto", max: 60, sugestoes: API.disciplinas(), mostrarSe: function (v) { return v.registrarLicao; } },
          { id: "licaoRecomendacao", rotulo: "Recomendação", tipo: "textarea", obrigatorio: true, max: 1000, linhas: 3, mostrarSe: function (v) { return v.registrarLicao; } }
        ],
        aoSalvar: function (v) {
          return API.encerrar(codigo, v).then(function (res) {
            GI.ui.toast("Mudança encerrada." + (res.licao ? " Lição " + res.licao + " criada em Rascunho." : ""), "success", 6000);
            if (aoConcluir) aoConcluir(codigo);
          });
        }
      });
    });
  }
  function cancelar(codigo, aoConcluir) {
    return GI.form.abrir({
      titulo: "Cancelar solicitação · " + codigo, textoSalvar: "Cancelar solicitação", perigo: true,
      intro: '<p class="text-small text-muted">Cancelamento a pedido do solicitante. A solicitação fica no registro com a justificativa.</p>',
      campos: [{ id: "justificativa", rotulo: "Justificativa do cancelamento", tipo: "textarea", obrigatorio: true, max: 500, linhas: 3 }],
      aoSalvar: function (v) {
        return API.cancelar(codigo, v).then(function () { GI.ui.toast("Solicitação cancelada.", "success"); if (aoConcluir) aoConcluir(codigo); });
      }
    });
  }

  /* Botões do fluxo conforme a situação e o papel. principal: próximo passo recomendado */
  function botoesSm(s, compacto) {
    var b = [], membro = API.pode("Membro"), gestor = API.pode("Gestor");
    function btn(acao, icone, texto, primario) {
      return '<button type="button" class="btn ' + (compacto ? "btn--ghost btn--sm" : primario ? "btn--primary" : "btn--secondary") + '" data-sm-acao="' + acao + '" data-codigo="' + U.esc(s.codigo) + '">' + U.icone(icone) + U.esc(texto) + "</button>";
    }
    if (s.situacao === "Registrada" && membro) b.push(btn("iniciarAnalise", "fileSearch", "Iniciar análise", true));
    if (s.situacao === "Em análise de impacto" && membro) b.push(btn("analise", "gauge", "Análise de impacto", true));
    if (s.situacao === "Aguardando comitê" && gestor) b.push(btn("decidir", "gavel", "Registrar decisão", true));
    if (s.situacao === "Adiada" && membro) b.push(btn("reapresentar", "refresh", "Reapresentar", true));
    if ((s.situacao === "Aprovada" || s.situacao === "Aprovada com condições") && membro) b.push(btn("iniciarImplementacao", "arrowRight", "Iniciar implementação", true));
    if (s.situacao === "Em implementação" && gestor) b.push(btn("encerrar", "lock", "Encerrar", !s.acoesAbertas));
    if (compacto) return b.join("");
    if ((s.situacao === "Aguardando comitê" || s.situacao === "Adiada") && membro) b.push(btn("analise", "gauge", "Revisar análise"));
    if ((s.situacao === "Registrada" || s.situacao === "Em análise de impacto") && membro) b.push(btn("editar", "edit", "Editar"));
    if (["Registrada", "Em análise de impacto", "Aguardando comitê", "Adiada"].indexOf(s.situacao) >= 0 && (gestor || (membro && s.solicitanteId === API.sessaoPessoa()))) b.push(btn("cancelar", "x", "Cancelar"));
    return b.join("");
  }
  var ACOES_SM = { iniciarAnalise: iniciarAnalise, analise: analise, decidir: decidir, reapresentar: reapresentar, iniciarImplementacao: iniciarImplementacao,
    encerrar: encerrar, editar: editarMudanca, cancelar: cancelar };
  function acaoSm(nome, codigo, cb) { var f = ACOES_SM[nome]; if (f) f(codigo, cb); }

  /* ======================================================================
     Lições aprendidas
     ====================================================================== */
  function camposLicao(l) {
    var o = l || {};
    return [
      { id: "titulo", rotulo: "Título", tipo: "texto", obrigatorio: true, max: 150, largura: "full", valor: o.titulo || "" },
      { id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, valor: o.tipo || "", opcoes: [
        { valor: "A repetir", texto: "A repetir", sub: "boa prática" }, { valor: "A evitar", texto: "A evitar", sub: "problema" }] },
      { id: "aplicabilidade", rotulo: "Aplicabilidade", tipo: "escolha", obrigatorio: true, valor: o.aplicabilidade || "Projeto", opcoes: [
        { valor: "Projeto", texto: "Projeto", sub: "restrita a este projeto" }, { valor: "Corporativa", texto: "Corporativa", sub: "compartilhar com a organização" }] },
      { id: "fase", rotulo: "Fase", tipo: "select", obrigatorio: true, opcoes: lista(API.FASES), valor: o.fase || "" },
      { id: "area", rotulo: "Área de conhecimento", tipo: "select", obrigatorio: true, opcoes: lista(API.AREAS), valor: o.area || "" },
      { id: "disciplina", rotulo: "Disciplina", tipo: "texto", obrigatorio: true, max: 60, sugestoes: API.disciplinas(), valor: o.disciplina || "" },
      { id: "origemTipo", rotulo: "Origem", tipo: "select", obrigatorio: true, opcoes: lista(API.ORIGENS_LICAO), valor: o.origemTipo || "" },
      { id: "origemRef", rotulo: "Número do registro de origem", tipo: "texto", obrigatorio: true, max: 40, placeholder: "RSK-TN-2026-0003", valor: o.origemRef || "",
        mostrarSe: function (v) { return API.exigeRefOrigem(v.origemTipo); }, ajuda: "Vínculo rastreável: o registro precisa existir no módulo de origem." },
      { id: "aconteceu", rotulo: "O que aconteceu", tipo: "textarea", obrigatorio: true, max: 1000, linhas: 3, valor: o.aconteceu || "" },
      { id: "causa", rotulo: "Causa", tipo: "textarea", obrigatorio: true, max: 600, linhas: 2, valor: o.causa || "" },
      { id: "impactoPrazoDias", rotulo: "Impacto em prazo (dias)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 999, valor: o.impactoPrazoDias != null ? o.impactoPrazoDias : 0 },
      { id: "impactoCustoCentavos", rotulo: "Impacto em custo", tipo: "moeda", obrigatorio: true, valor: o.impactoCustoCentavos != null ? o.impactoCustoCentavos : 0 },
      { id: "recomendacao", rotulo: "Recomendação", tipo: "textarea", obrigatorio: true, max: 1000, linhas: 3, valor: o.recomendacao || "",
        ajuda: "O que fazer (ou não fazer) nos próximos projetos, de forma acionável." },
      { id: "palavrasChave", rotulo: "Palavras-chave (separadas por vírgula)", tipo: "texto", obrigatorio: true, max: 200, largura: "full", valor: (o.palavrasChave || []).join(", ") }
    ];
  }
  function novaLicao(projetoId, aoConcluir) {
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar lições.", "warning"); return; }
    if (projetoId == null) { U.noProjeto("nova", "Nova lição aprendida"); return; }
    return pronto().then(function () {
      return GI.form.abrir({
        titulo: "Nova lição aprendida", tamanho: "lg", textoSalvar: "Salvar rascunho",
        intro: '<p class="text-small text-muted">Registro contínuo, em qualquer fase. Fluxo: Rascunho &rarr; Em validação &rarr; Validada &rarr; Publicada no acervo (validação pelo PMO ou gerência do projeto).</p>',
        campos: camposLicao(null),
        extras: [{ texto: "Salvar e enviar para validação", acao: "enviar" }],
        aoSalvar: function (v, api, acao) {
          return API.salvarLicao(Object.assign({ projetoId: projetoId }, v), acao === "enviar").then(function (r) {
            GI.ui.toast("Lição " + r.codigo + (acao === "enviar" ? " enviada para validação." : " salva em Rascunho."), "success");
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }
  function editarLicao(codigo, aoConcluir) {
    return API.licao(codigo).then(function (l) {
      if (!l) return GI.ui.toast("Lição não encontrada.", "warning");
      return GI.form.abrir({
        titulo: "Editar lição · " + l.codigo, subtitulo: l.situacao, tamanho: "lg", textoSalvar: "Salvar rascunho",
        intro: l.devolucao ? alerta("warning", "<b>Devolvida pelo validador</b> em " + F.data(l.devolucao.data) + ": " + U.esc(l.devolucao.comentario)) : "",
        campos: camposLicao(l),
        extras: [{ texto: "Salvar e enviar para validação", acao: "enviar" }],
        aoSalvar: function (v, api, acao) {
          return API.salvarLicao(Object.assign({ codigo: codigo }, v), acao === "enviar").then(function () {
            GI.ui.toast(acao === "enviar" ? "Lição enviada para validação." : "Lição salva.", "success");
            if (aoConcluir) aoConcluir(codigo);
          });
        }
      });
    });
  }
  function enviarLicao(codigo, aoConcluir) {
    confirmar("Enviar para validação", "Enviar a lição " + codigo + " para validação do PMO ou da gerência do projeto?", function () { return API.enviarValidacao(codigo); },
      "Lição enviada para validação.", aoConcluir, codigo);
  }
  function validarLicao(codigo, aoConcluir) {
    return API.licao(codigo).then(function (l) {
      if (!l) return GI.ui.toast("Lição não encontrada.", "warning");
      return GI.form.abrir({
        titulo: "Validação · " + l.codigo, subtitulo: l.titulo, tamanho: "lg", textoSalvar: "Registrar validação",
        intro: '<div class="form-grid mb-4">' + campoInfo("Tipo", tipoLicao(l.tipo)) + campoInfo("Autor", U.esc(U.pessoa(l.autorId))) + campoInfo("Fase e área", U.esc(l.fase + " · " + l.area)) +
          campoInfo("Origem", origemHtml(l)) + "</div><p class=\"mb-4\"><b>Recomendação.</b> " + U.esc(l.recomendacao) + "</p>",
        campos: [
          { id: "resultado", rotulo: "Resultado", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: [
            { valor: "Validada", texto: "Validar" }, { valor: "Publicada", texto: "Validar e publicar", sub: "entra no acervo" }, { valor: "Devolvida", texto: "Devolver ao autor", sub: "volta a Rascunho" }] },
          { id: "aplicabilidade", rotulo: "Aplicabilidade", tipo: "escolha", obrigatorio: true, valor: l.aplicabilidade, largura: "full",
            mostrarSe: function (v) { return v.resultado !== "Devolvida"; }, opcoes: [
              { valor: "Projeto", texto: "Projeto", sub: "restrita a este projeto" }, { valor: "Corporativa", texto: "Corporativa", sub: "compartilhar com a organização" }] },
          { id: "comentario", rotulo: "Comentário", tipo: "textarea", max: 500, linhas: 3, ajuda: "Obrigatório ao devolver: diga o que precisa ser ajustado." }
        ],
        validar: function (v) { return v.resultado === "Devolvida" && (!v.comentario || v.comentario.length < 10) ? [{ campo: "comentario", msg: "Explique ao autor o que ajustar (mínimo de 10 caracteres)." }] : []; },
        aoSalvar: function (v) {
          return API.validarLicao(codigo, v).then(function (r) {
            GI.ui.toast(r.situacao === "Rascunho" ? "Lição devolvida ao autor." : r.situacao === "Publicada" ? "Lição validada e publicada no acervo." : "Lição validada.", "success");
            if (aoConcluir) aoConcluir(codigo);
          });
        }
      });
    });
  }
  function publicarLicao(codigo, aoConcluir) {
    confirmar("Publicar no acervo", "Publicar a lição " + codigo + " no acervo? Ela passa a compor o acervo do projeto (e o da organização, se Corporativa).", function () { return API.publicarLicao(codigo); },
      "Lição publicada no acervo.", aoConcluir, codigo);
  }
  function aplicarLicao(codigo, projetoId, aoConcluir) {
    return Promise.all([API.licao(codigo), GI.api.riscos.categorias(), pronto()]).then(function (r) {
      var l = r[0], cats = r[1];
      if (!l) return GI.ui.toast("Lição não encontrada.", "warning");
      var proj = U.projeto(projetoId) || {};
      return GI.form.abrir({
        titulo: "Aplicar em projeto · " + l.codigo, subtitulo: l.titulo, tamanho: "lg", textoSalvar: "Registrar aplicação",
        intro: '<p class="mb-4"><b>Recomendação.</b> ' + U.esc(l.recomendacao) + "</p>",
        campos: [
          { id: "projetoId", rotulo: "Projeto", tipo: "select", obrigatorio: true, opcoes: projetos(), valor: projetoId },
          { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: REF, maxData: REF },
          { id: "como", rotulo: "Como a lição será aplicada", tipo: "textarea", obrigatorio: true, max: 600, linhas: 3 },
          { id: "gerar", rotulo: "Gerar", tipo: "radio", obrigatorio: true, valor: "acao", largura: "full", opcoes: [
            { valor: "nada", texto: "Só registrar o reuso" }, { valor: "acao", texto: "Criar ação na Central de Ações (origem Lição)" },
            { valor: "risco", texto: l.tipo === "A evitar" ? "Registrar ameaça no registro de riscos (05)" : "Registrar oportunidade no registro de riscos (05)" }] },
          { id: "responsavelId", rotulo: "Responsável pela ação", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: proj.gerenteId, mostrarSe: function (v) { return v.gerar === "acao"; } },
          { id: "prevista", rotulo: "Data prevista", tipo: "data", obrigatorio: true, min: REF, valor: somarDias(REF, 30), mostrarSe: function (v) { return v.gerar === "acao"; } },
          { id: "categoria", rotulo: "Categoria (RBS)", tipo: "select", obrigatorio: true, mostrarSe: function (v) { return v.gerar === "risco"; },
            opcoes: cats.map(function (c) { var t = c.grupo + " > " + c.nome; return { valor: t, texto: t }; }) },
          { id: "donoId", rotulo: "Dono do risco", tipo: "select", obrigatorio: true, opcoes: pessoas(), valor: proj.gerenteId, mostrarSe: function (v) { return v.gerar === "risco"; } }
        ],
        aoSalvar: function (v) {
          return API.aplicarLicao(codigo, v).then(function (res) {
            GI.ui.toast("Aplicação registrada." + (res.acao ? " Ação criada na Central." : "") + (res.risco ? " Risco " + res.risco + " registrado." : ""), "success", 6000);
            if (aoConcluir) aoConcluir(codigo);
          });
        }
      });
    });
  }
  /* Botões do fluxo da lição */
  function botoesLicao(l, compacto) {
    var b = [], membro = API.pode("Membro"), gestor = API.pode("Gestor"), eu = API.sessaoPessoa();
    function btn(acao, icone, texto, primario) {
      return '<button type="button" class="btn ' + (compacto ? "btn--ghost btn--sm" : primario ? "btn--primary" : "btn--secondary") + '" data-lic-acao="' + acao + '" data-codigo="' + U.esc(l.codigo) + '">' + U.icone(icone) + U.esc(texto) + "</button>";
    }
    var autorOuGestor = gestor || (membro && l.autorId === eu);
    if (l.situacao === "Rascunho" && autorOuGestor) { b.push(btn("enviar", "send", "Enviar para validação", true)); b.push(btn("editar", "edit", "Editar")); }
    if (l.situacao === "Em validação" && gestor && l.autorId !== eu) b.push(btn("validar", "checkCircle", "Validar", true));
    if (l.situacao === "Validada" && gestor) b.push(btn("publicar", "upload", "Publicar", true));
    if (l.situacao === "Publicada" && membro) b.push(btn("aplicar", "target", "Aplicar em projeto", true));
    return b.join("");
  }
  function verLicao(codigo, projetoId, aoConcluir) {
    return API.licao(codigo).then(function (l) {
      if (!l) return GI.ui.toast("Lição não encontrada.", "warning");
      var n = ++seq;
      var corpo = document.createElement("div");
      corpo.innerHTML = '<div class="form-grid mb-4">' +
        campoInfo("Situação", situacaoLicao(l.situacao)) + campoInfo("Tipo", tipoLicao(l.tipo)) +
        campoInfo("Fase", U.esc(l.fase)) + campoInfo("Área de conhecimento", U.esc(l.area)) +
        campoInfo("Disciplina", U.esc(l.disciplina)) + campoInfo("Aplicabilidade", U.esc(l.aplicabilidade)) +
        campoInfo("Origem", origemHtml(l)) + campoInfo("Projeto", U.esc(l.projetoCodigo)) +
        campoInfo("Autor", U.esc(U.pessoa(l.autorId))) + campoInfo("Registrada em", F.data(l.data)) +
        campoInfo("Impacto", U.esc(U.plural(l.impactoPrazoDias || 0, "dia")) + " · " + U.esc(F.moeda(l.impactoCustoCentavos || 0))) +
        campoInfo("Reusos", F.num(l.reusos)) + "</div>" +
        (l.devolucao && l.situacao === "Rascunho" ? alerta("warning", "<b>Devolvida pelo validador</b> em " + F.data(l.devolucao.data) + ": " + U.esc(l.devolucao.comentario)) : "") +
        '<dl class="dl mb-4"><dt>O que aconteceu</dt><dd>' + U.esc(l.aconteceu) + "</dd><dt>Causa</dt><dd>" + U.esc(l.causa) + "</dd><dt>Recomendação</dt><dd><b>" + U.esc(l.recomendacao) + "</b></dd>" +
        "<dt>Palavras-chave</dt><dd>" + (l.palavrasChave || []).map(function (p) { return U.badge(p, "neutral"); }).join(" ") + "</dd></dl>" +
        (l.aplicacoes.length ? '<h3 class="section-title">Aplicações registradas</h3><div id="t-apl-' + n + '" class="mb-4"></div>' : "") +
        '<h3 class="section-title">Histórico</h3><div id="t-hlic-' + n + '"></div>';
      var botoes = [{ label: "Fechar", variant: "secondary" }];
      var acoes = { enviar: "Enviar para validação", editar: "Editar", validar: "Validar", publicar: "Publicar", aplicar: "Aplicar em projeto" };
      var tmp = document.createElement("div"); tmp.innerHTML = botoesLicao(l);
      Array.prototype.forEach.call(tmp.querySelectorAll("[data-lic-acao]"), function (b) {
        var a = b.getAttribute("data-lic-acao");
        botoes.push({ label: acoes[a], variant: b.classList.contains("btn--primary") ? "primary" : "secondary", onClick: function (api) { api.close(); acaoLicao(a, codigo, projetoId, aoConcluir); } });
      });
      var m = GI.modal.create({ title: "Lição " + l.codigo, subtitle: l.titulo, size: "lg", body: corpo, buttons: botoes });
      if (l.aplicacoes.length) {
        GI.tabela.criar("t-apl-" + n, {
          porPagina: 0, compacta: true, legenda: "Aplicações da lição",
          colunas: [
            { id: "data", titulo: "Data", tipo: "data" },
            { id: "projeto", titulo: "Projeto", valor: function (a) { var p = U.projeto(a.projetoId); return p ? p.codigo : ""; } },
            { id: "como", titulo: "Como" },
            { id: "gerado", titulo: "Gerado", valor: function (a) { return a.riscoRef || (a.acaoItem ? "Ação " + a.acaoItem : ""); },
              html: function (a) { return a.riscoRef ? '<a href="' + U.tela("riscos", "ficha", { codigo: a.riscoRef }) + '">' + U.esc(a.riscoRef) + "</a>" : a.acaoItem ? '<a href="' + U.tela("central-acoes", "acoes", { busca: l.codigo, status: "todos" }) + '">Ação ' + U.esc(a.acaoItem) + "</a>" : "·"; } }
          ]
        }).atualizar(l.aplicacoes);
      }
      GI.tabela.criar("t-hlic-" + n, {
        porPagina: 10, legenda: "Histórico da lição", compacta: true, ordem: { coluna: "quando", direcao: "desc" },
        colunas: [
          { id: "quando", titulo: "Quando", classe: "nowrap", valor: function (h) { return h.quando; }, html: function (h) { return F.data(h.quando.slice(0, 10)) + " " + h.quando.slice(11, 16); } },
          { id: "quem", titulo: "Quem", valor: function (h) { return h.porId ? U.pessoa(h.porId) : ""; } },
          { id: "texto", titulo: "O que aconteceu" }
        ]
      }).atualizar(l.historicoExibicao);
      GI.ui.init(m.el);
      return m;
    });
  }
  function acaoLicao(nome, codigo, projetoId, cb) {
    if (nome === "ver") verLicao(codigo, projetoId, cb);
    else if (nome === "editar") editarLicao(codigo, cb);
    else if (nome === "enviar") enviarLicao(codigo, cb);
    else if (nome === "validar") validarLicao(codigo, cb);
    else if (nome === "publicar") publicarLicao(codigo, cb);
    else if (nome === "aplicar") aplicarLicao(codigo, projetoId, cb);
  }

  GI.gov = {
    pronto: pronto, projeto: projeto, pessoas: pessoas, erroApi: erroApi, alerta: alerta, campoInfo: campoInfo,
    situacaoSm: situacaoSm, prioridade: prioridade, custo: custo, prazo: prazo, etapas: etapas,
    situacaoLicao: situacaoLicao, tipoLicao: tipoLicao, linkOrigemLicao: linkOrigemLicao, origemHtml: origemHtml,
    chips: chips, filtros: filtros,
    novaMudanca: novaMudanca, botoesSm: botoesSm, acaoSm: acaoSm,
    novaLicao: novaLicao, botoesLicao: botoesLicao, acaoLicao: acaoLicao, verLicao: verLicao,
    param: function () { return param; }
  };
})(window.GI = window.GI || {});
