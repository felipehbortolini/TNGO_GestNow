/* ==========================================================================
   hse.js | Apoio comum às telas do módulo 07 HSE (GI.hse)

   GI.hse.pronto()                 -> Promise (cadastros e parâmetros de HSE)
   GI.hse.projeto(aoTrocar)        -> id do projeto (?projeto= ou atual); preenche #f-projeto
   GI.hse.situacaoOcorrencia(t) / nivelBadge(x) / potencial(faixa, p, i)
   GI.hse.pessoas() / empresas()
   Modais: novaOcorrencia, investigarOcorrencia, novaAcaoCorretiva, iniciarTratamento,
           encerrarOcorrencia, verOcorrencia, novoEstudo, verEstudo,
           registrarHht, registrarMes (inspeções/observações/DDS)
   Regras e cálculos ficam em GI.api.hse; a tela só exibe o que a api devolve.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, API = GI.api.hse;
  var REF = GI.api.referencia();
  var param = null, carregando = null, seqTabela = 0;

  function pronto() {
    if (!carregando) {
      carregando = Promise.all([U.pronto(), GI.api.parametros()]).then(function (r) {
        param = r[1].hse;
        return param;
      });
    }
    return carregando;
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

  function pessoas() {
    return Object.keys(U.mapas.pessoas).map(function (k) { var p = U.mapas.pessoas[k]; return { valor: k, texto: p.nome + " (" + p.funcao + ")" }; })
      .sort(function (a, b) { return a.texto.localeCompare(b.texto); });
  }
  function empresas() {
    return Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; })
      .sort(function (a, b) { return a.texto.localeCompare(b.texto); });
  }
  function ultimosMeses(n) {
    var d = new Date(REF + "T00:00:00"), lista = [];
    for (var i = 0; i < (n || 15); i++) {
      lista.unshift(d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0"));
      d.setMonth(d.getMonth() - 1);
    }
    return lista;
  }

  /* ---------------- Formatação ---------------- */
  var TIPO_SITUACAO_OC = { "Registrada": "neutral", "Em investigação": "warning", "Ações definidas": "info", "Em tratamento": "info", "Encerrada": "success" };
  function situacaoOcorrencia(t) { return U.badge(t, TIPO_SITUACAO_OC[t] || "neutral", true); }
  var COR_NIVEL = { 1: "danger", 2: "warning", 3: "purple", 4: "info" };
  function nivelBadge(x) {
    if (x.ambiental) return U.badge("Ambiental", "neutral");
    return U.badge("N" + x.nivel + " · " + x.nivelNome, COR_NIVEL[x.nivel] || "neutral");
  }
  function potencial(faixa, p, i) {
    if (!faixa) return '<span class="text-small text-muted">·</span>';
    return '<span class="sev sev--' + U.esc(faixa.id) + '"><b>' + (p * i) + "</b> " + U.esc(faixa.nome) + '</span> <small class="text-muted">P' + p + " x I" + i + "</small>";
  }
  function prazoBadge(ok, textoOk, textoFora) {
    return ok ? U.badge(textoFora || "Fora do prazo", "danger") : (textoOk ? U.badge(textoOk, "success") : "");
  }
  var GRAVIDADE_REAL = [
    { valor: 1, numero: 1, texto: "Sem lesão", sub: "dano leve ou nenhum" },
    { valor: 2, numero: 2, texto: "Lesão leve", sub: "ou dano moderado" },
    { valor: 3, numero: 3, texto: "Lesão moderada", sub: "ou dano considerável" },
    { valor: 4, numero: 4, texto: "Lesão grave", sub: "com afastamento" },
    { valor: 5, numero: 5, texto: "Fatalidade", sub: "" }
  ];
  var PROB_HSE = [
    { valor: 1, numero: 1, texto: "Muito baixa", sub: "raramente ocorre" },
    { valor: 2, numero: 2, texto: "Baixa", sub: "já ocorreu antes" },
    { valor: 3, numero: 3, texto: "Média", sub: "pode ocorrer" },
    { valor: 4, numero: 4, texto: "Alta", sub: "ocorre com frequência" },
    { valor: 5, numero: 5, texto: "Muito alta", sub: "condição recorrente" }
  ];
  var IMP_HSE = [
    { valor: 1, numero: 1, texto: "Leve", sub: "primeiros socorros" },
    { valor: 2, numero: 2, texto: "Moderado", sub: "tratamento médico" },
    { valor: 3, numero: 3, texto: "Sério", sub: "afastamento" },
    { valor: 4, numero: 4, texto: "Grave", sub: "invalidez" },
    { valor: 5, numero: 5, texto: "Catastrófico", sub: "fatalidade" }
  ];
  var TIPOS_COM_FUNCAO = ["Fatalidade", "Acidente com afastamento", "Trabalho restrito", "Tratamento médico", "Primeiros socorros"];
  var TIPOS_LTI = ["Fatalidade", "Acidente com afastamento"];

  function campoInfo(rotulo, html) { return '<div class="field"><span class="field__label">' + U.esc(rotulo) + "</span><div>" + (html || "") + "</div></div>"; }
  function historicoTabela(idEl, lista) {
    var t = GI.tabela.criar(idEl, {
      porPagina: 10, legenda: "Histórico", compacta: true, ordem: { coluna: "quando", direcao: "desc" },
      colunas: [
        { id: "quando", titulo: "Quando", classe: "nowrap", valor: function (h) { return h.quando; },
          html: function (h) { return F.data(h.quando.slice(0, 10)) + (h.quando.length > 10 ? " " + h.quando.slice(11, 16) : ""); },
          exportar: function (h) { return F.data(h.quando.slice(0, 10)); } },
        { id: "quem", titulo: "Quem", valor: function (h) { return h.porId ? U.pessoa(h.porId) : ""; } },
        { id: "texto", titulo: "O que aconteceu" }
      ]
    });
    t.atualizar(lista || []);
    return t;
  }

  /* ======================================================================
     Ocorrências: registro, investigação, ações, tratamento e encerramento
     ====================================================================== */
  function ambiental(v) { return v.tipo === "Ambiental"; }
  function comFuncao(v) { return !ambiental(v) && TIPOS_COM_FUNCAO.indexOf(v.tipo) >= 0; }
  function ehLTI(v) { return !ambiental(v) && TIPOS_LTI.indexOf(v.tipo) >= 0; }

  function novaOcorrencia(projetoId, aoConcluir) {
    if (projetoId == null) { GI.util.noProjeto("nova", "Nova ocorrência"); return; }
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar ocorrências.", "warning"); return; }
    return pronto().then(function () {
      var TIPOS = [].concat(API.TIPOS_PIRAMIDE[1], API.TIPOS_PIRAMIDE[2], API.TIPOS_PIRAMIDE[3], API.TIPOS_PIRAMIDE[4], ["Ambiental"]);
      var campos = [
        { id: "data", rotulo: "Data do evento", tipo: "data", obrigatorio: true, valor: REF, maxData: REF },
        { id: "hora", rotulo: "Hora (HH:MM)", tipo: "texto", obrigatorio: true, max: 5, placeholder: "14:30" },
        { id: "area", rotulo: "Área / local", tipo: "texto", obrigatorio: true, max: 80, largura: "full" },
        { id: "empresaId", rotulo: "Empresa (contratada)", tipo: "select", obrigatorio: true, opcoes: empresas() },
        { id: "tipo", rotulo: "Tipo de ocorrência", tipo: "select", obrigatorio: true, opcoes: TIPOS.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "subtipo", rotulo: "Subtipo ambiental", tipo: "select", obrigatorio: true, opcoes: API.SUBTIPOS_AMBIENTAL.map(function (s) { return { valor: s, texto: s }; }), mostrarSe: ambiental },
        { id: "severidadeAmbiental", rotulo: "Severidade", tipo: "escolha", obrigatorio: true, opcoes: API.SEVERIDADES_AMBIENTAL.map(function (s) { return { valor: s, texto: s }; }), mostrarSe: ambiental, largura: "full" },
        { id: "descricao", rotulo: "Descrição do ocorrido", tipo: "textarea", obrigatorio: true, max: 500, linhas: 3, largura: "full", mostrarSe: function (v) { return !ambiental(v); } },
        { id: "funcao", rotulo: "Função da pessoa envolvida", tipo: "texto", max: 60, mostrarSe: comFuncao, ajuda: "Sem nome (LGPD); dados pessoais e médicos ficam fora do registro geral." },
        { id: "pessoasEnvolvidas", rotulo: "Pessoas envolvidas", tipo: "numero", min: 0, maxNumero: 20, valor: 0, mostrarSe: function (v) { return !ambiental(v); } },
        { id: "gravidadeReal", rotulo: "Gravidade real observada", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: GRAVIDADE_REAL, mostrarSe: function (v) { return !ambiental(v); } },
        { id: "potencialP", rotulo: "Probabilidade potencial (de recorrência)", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: PROB_HSE, mostrarSe: function (v) { return !ambiental(v); } },
        { id: "potencialI", rotulo: "Impacto potencial", tipo: "escolha", obrigatorio: true, largura: "full", opcoes: IMP_HSE, mostrarSe: function (v) { return !ambiental(v); } },
        { id: "hipo", rotulo: "Marcar como alto potencial (HiPo)", tipo: "check", mostrarSe: function (v) { return !ambiental(v); } },
        { id: "diasPerdidos", rotulo: "Dias perdidos", tipo: "numero", min: 0, maxNumero: 365, valor: 0, mostrarSe: ehLTI },
        { id: "diasDebitados", rotulo: "Dias debitados", tipo: "numero", min: 0, maxNumero: 365, valor: 0, mostrarSe: ehLTI },
        { id: "cat", rotulo: "Comunicação legal (CAT) aplicável", tipo: "check", mostrarSe: comFuncao },
        { id: "causaImediata", rotulo: "Causa imediata", tipo: "select", obrigatorio: true, opcoes: API.CAUSAS_IMEDIATAS.map(function (c) { return { valor: c, texto: c }; }), mostrarSe: function (v) { return !ambiental(v); } },
        { id: "comunicacaoHoras", rotulo: "Horas até a comunicação formal", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 200, valor: 0,
          ajuda: "Prazo de comunicação: " + param.prazos.comunicacaoHoras + " horas a partir do evento." },
        { id: "evidencias", rotulo: "Evidências (fotos, relatório)", tipo: "arquivo", multiplo: true, aceitar: ["jpg", "jpeg", "png", "pdf"] }
      ];
      return GI.form.abrir({
        titulo: "Nova ocorrência", tamanho: "lg",
        intro: '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">Fluxo: Registrada &rarr; Em investigação &rarr; Ações definidas &rarr; Em tratamento &rarr; Encerrada. O nível 5 (desvios) não tem registro individual; vem de Inspeções e observações.</div></div>',
        campos: campos,
        validar: function (v) {
          var erros = [];
          if (v.hora && !/^([01]\d|2[0-3]):[0-5]\d$/.test(v.hora)) erros.push({ campo: "hora", msg: "Use o formato HH:MM (ex.: 14:30)." });
          return erros;
        },
        aoSalvar: function (v) {
          return API.salvarOcorrencia({
            projetoId: projetoId, dataHora: v.data + "T" + v.hora, area: v.area, empresaId: v.empresaId, tipo: v.tipo,
            subtipo: v.subtipo, severidadeAmbiental: v.severidadeAmbiental, descricao: v.descricao, funcao: v.funcao,
            pessoasEnvolvidas: v.pessoasEnvolvidas, gravidadeReal: v.gravidadeReal, potencialP: v.potencialP, potencialI: v.potencialI,
            hipo: v.hipo, diasPerdidos: v.diasPerdidos, diasDebitados: v.diasDebitados, cat: v.cat, causaImediata: v.causaImediata,
            comunicacaoHoras: v.comunicacaoHoras
          }).then(function (r) {
            GI.ui.toast("Ocorrência " + r.codigo + " registrada.", "success");
            (r.avisos || []).forEach(function (a) { GI.ui.toast(a, "warning", 7000); });
            if (aoConcluir) aoConcluir(r.codigo);
          });
        }
      });
    });
  }

  function investigar(codigo, aoConcluir) {
    return API.ocorrencia(codigo).then(function (o) {
      if (!o) { GI.ui.toast("Ocorrência não encontrada.", "warning"); return; }
      if (o.situacao !== "Registrada") { GI.ui.toast("Esta ocorrência já foi investigada.", "info"); return; }
      return GI.form.abrir({
        titulo: "Investigar ocorrência · " + o.codigo, subtitulo: o.tipo + " · " + o.area, tamanho: "lg", textoSalvar: "Registrar investigação",
        intro: '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">Prazo de investigação preliminar: ' + param.prazos.investigacaoPreliminarHoras +
          " horas a partir do evento (" + F.data(o.dataHora) + ").</div></div>",
        campos: [
          { id: "metodo", rotulo: "Método de investigação", tipo: "escolha", obrigatorio: true, largura: "full",
            opcoes: API.METODOS_INVESTIGACAO.map(function (m) { return { valor: m, texto: m }; }) },
          { id: "causaRaiz", rotulo: "Causa raiz", tipo: "textarea", obrigatorio: true, max: 800, linhas: 4, largura: "full" },
          { id: "data", rotulo: "Data da investigação", tipo: "data", obrigatorio: true, valor: REF, min: o.dataHora.slice(0, 10), maxData: REF }
        ],
        aoSalvar: function (v) {
          return API.investigar(o.codigo, v).then(function (r) {
            GI.ui.toast("Investigação registrada." + (r.foraDoPrazo ? " Atenção: fora do prazo preliminar." : ""), r.foraDoPrazo ? "warning" : "success", 6000);
            if (aoConcluir) aoConcluir(o.codigo);
          });
        }
      });
    });
  }

  function novaAcaoCorretiva(codigo, aoConcluir) {
    return API.ocorrencia(codigo).then(function (o) {
      if (!o) { GI.ui.toast("Ocorrência não encontrada.", "warning"); return; }
      if (o.situacao === "Registrada") { GI.ui.toast("Investigue a ocorrência antes de definir as ações.", "warning"); return; }
      if (o.situacao === "Encerrada") { GI.ui.toast("Ocorrência encerrada não recebe novas ações.", "warning"); return; }
      return GI.form.abrir({
        titulo: "Ação corretiva · " + o.codigo, subtitulo: o.tipo + " · " + o.area, tamanho: "lg",
        intro: '<p class="text-small text-muted">Esta ação nasce vinculada à ocorrência (origem HSE) e aparece na Central de Ações.</p>',
        campos: [
          { id: "assunto", rotulo: "Assunto", tipo: "texto", obrigatorio: true, max: 255, largura: "full" },
          { id: "descricao", rotulo: "Descrição", tipo: "textarea", max: 500 },
          { id: "responsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: pessoas() },
          { id: "prevista", rotulo: "Data prevista", tipo: "data", obrigatorio: true, min: REF }
        ],
        extras: [{ texto: "Salvar e nova", acao: "nova" }],
        aoSalvar: function (v, api, acao) {
          return API.definirAcoes(o.codigo, [{ assunto: v.assunto, descricao: v.descricao, responsavelId: v.responsavelId, prevista: v.prevista }]).then(function () {
            GI.ui.toast("Ação corretiva criada na Central.", "success");
            if (aoConcluir) aoConcluir(o.codigo);
            if (acao === "nova") setTimeout(function () { novaAcaoCorretiva(codigo, aoConcluir); }, 50);
          });
        }
      });
    });
  }

  function iniciarTratamento(codigo, aoConcluir) {
    GI.modal.confirm({ title: "Iniciar tratamento", message: "Confirma o início do tratamento da ocorrência " + codigo + "?" }).then(function (ok) {
      if (!ok) return;
      API.iniciarTratamento(codigo).then(function () {
        GI.ui.toast("Tratamento iniciado.", "success");
        if (aoConcluir) aoConcluir(codigo);
      }).catch(erroApi);
    });
  }

  function encerrarOcorrencia(codigo, aoConcluir) {
    return API.ocorrencia(codigo).then(function (o) {
      if (!o) { GI.ui.toast("Ocorrência não encontrada.", "warning"); return; }
      if (o.situacao !== "Em tratamento") { GI.ui.toast("Só é possível encerrar depois de iniciado o tratamento.", "warning"); return; }
      return GI.form.abrir({
        titulo: "Encerrar ocorrência · " + o.codigo, subtitulo: o.tipo + " · " + o.area, tamanho: "lg", textoSalvar: "Encerrar",
        intro: o.acoesAbertas ? '<div class="alert alert--warning">' + U.icone("alertTriangle") + '<div class="alert__body">' +
          U.plural(o.acoesAbertas, "ação corretiva em aberto", "ações corretivas em aberto") + ". Conclua-as antes de encerrar.</div></div>" : "",
        campos: [
          { id: "eficacia", rotulo: "Verificação de eficácia", tipo: "textarea", obrigatorio: true, max: 600, linhas: 3, largura: "full",
            ajuda: "Descreva como foi verificada a eficácia das ações corretivas." },
          { id: "data", rotulo: "Data do encerramento", tipo: "data", obrigatorio: true, valor: REF, min: o.dataHora.slice(0, 10), maxData: REF }
        ],
        aoSalvar: function (v) {
          return API.encerrarOcorrencia(o.codigo, v).then(function (r) {
            GI.ui.toast("Ocorrência encerrada." + (r.relatorioForaDoPrazo ? " Atenção: relatório final fora do prazo." : ""), r.relatorioForaDoPrazo ? "warning" : "success", 6000);
            if (aoConcluir) aoConcluir(o.codigo);
          });
        }
      });
    });
  }

  function verOcorrencia(codigo) {
    return API.ocorrencia(codigo).then(function (o) {
      if (!o) { GI.ui.toast("Ocorrência não encontrada.", "warning"); return; }
      var tid = "t-hist-oc-" + (++seqTabela);
      var corpo = document.createElement("div");
      corpo.innerHTML = '<div class="form-grid mb-4">' +
        campoInfo("Situação", situacaoOcorrencia(o.situacao)) +
        campoInfo("Nível", nivelBadge(o)) +
        campoInfo("Data / hora", F.data(o.dataHora) + " " + o.dataHora.slice(11, 16)) +
        campoInfo("Área", U.esc(o.area)) +
        campoInfo("Empresa", U.esc(U.empresa(o.empresaId))) +
        (o.ambiental
          ? campoInfo("Subtipo", U.esc(o.subtipo)) + campoInfo("Severidade", U.esc(o.severidadeAmbiental))
          : campoInfo("Gravidade real", GRAVIDADE_REAL[o.gravidadeReal - 1] ? GRAVIDADE_REAL[o.gravidadeReal - 1].texto : "") +
            campoInfo("Potencial", potencial(o.potencialFaixa, o.potencial.p, o.potencial.i))) +
        (o.hipo ? campoInfo("Alto potencial", U.badge("HiPo", "danger")) : "") +
        (o.funcao ? campoInfo("Função envolvida", U.esc(o.funcao)) : "") +
        (o.causaImediata ? campoInfo("Causa imediata", U.esc(o.causaImediata)) : "") +
        campoInfo("Comunicação", o.prazoComunicacao ? (o.prazoComunicacao.horas + "h" + (o.prazoComunicacao.foraDoPrazo ? " · " + U.badge("Fora do prazo", "danger") : " · " + U.badge("No prazo", "success"))) : "·") +
        "</div>" +
        (o.descricao ? "<p class=\"mb-4\">" + U.esc(o.descricao) + "</p>" : "") +
        (o.investigacao ? '<div class="alert mb-4">' + U.icone("fileSearch") + '<div class="alert__body"><b>Investigação (' + U.esc(o.investigacao.metodo) + ")</b>: " + U.esc(o.investigacao.causaRaiz) + "</div></div>" : "") +
        (o.encerramento ? '<div class="alert alert--success mb-4">' + U.icone("checkCircle") + '<div class="alert__body"><b>Eficácia verificada</b>: ' + U.esc(o.encerramento.eficacia) + "</div></div>" : "") +
        (o.acoesLista && o.acoesLista.length ? '<h3 class="section-title">Ações corretivas</h3><div id="t-acoes-oc-' + seqTabela + '" class="mb-4"></div>' : "") +
        '<h3 class="section-title">Histórico</h3><div id="' + tid + '"></div>';
      var mostrarNivel = !o.ambiental && o.nivelNome && o.nivelNome !== o.tipo;
      var m = GI.modal.create({ title: "Ocorrência " + o.codigo, subtitle: o.tipo + (mostrarNivel ? " · " + o.nivelNome : ""), size: "lg", body: corpo, buttons: [{ label: "Fechar", variant: "secondary" }] });
      if (o.acoesLista && o.acoesLista.length) {
        GI.tabela.criar("t-acoes-oc-" + seqTabela, {
          porPagina: 0, compacta: true, legenda: "Ações corretivas",
          colunas: [
            { id: "assunto", titulo: "Assunto", valor: function (a) { return a.assunto; } },
            { id: "responsavel", titulo: "Responsável", valor: function (a) { return U.pessoa(a.responsavelId); } },
            { id: "prevista", titulo: "Prevista", tipo: "data", valor: function (a) { return a.replanejada || a.prevista; } },
            { id: "status", titulo: "Status", valor: function (a) { return a.statusRotulo; }, html: function (a) { return U.badge(a.statusRotulo, U.statusAcao(a.status)); } }
          ]
        }).atualizar(o.acoesLista);
      }
      historicoTabela(tid, o.historicoExibicao);
      GI.ui.init(m.el);
      return m;
    });
  }

  /* ======================================================================
     Análises de risco: APR/JSA e HAZOP
     ====================================================================== */
  function novoEstudo(projetoId, aoConcluir) {
    if (projetoId == null) { GI.util.noProjeto("novo", "Nova análise de risco"); return; }
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar estudos.", "warning"); return; }
    var opPessoas = pessoas();
    function linhaHtml(i) {
      return '<div class="rec-row" data-rec>' +
        '<div class="form-grid">' +
        '<div class="field field--full"><label class="field__label">Recomendação ' + (i + 1) + '</label><textarea class="textarea" data-rec-desc rows="2" maxlength="300"></textarea></div>' +
        '<div class="field"><label class="field__label">Responsável</label><select class="select" data-rec-resp>' + U.opcoes(opPessoas, "", "Selecione...") + "</select></div>" +
        '<div class="field"><label class="field__label">Prazo</label><input class="input" type="date" data-rec-prazo min="' + REF + '"></div>' +
        '<div class="field field--full"><button type="button" class="btn btn--ghost btn--sm" data-rec-remover>' + U.icone("x") + "Remover</button></div>" +
        "</div></div>";
    }
    var recomendacoesHtml = '<div id="rec-lista">' + linhaHtml(0) + '</div>' +
      '<button type="button" class="btn btn--secondary btn--sm mt-2" id="rec-add">' + U.icone("plus") + "Adicionar recomendação</button>";
    var seq = 1;
    var m = GI.form.abrir({
      titulo: "Novo estudo (APR/JSA ou HAZOP)", tamanho: "lg",
      campos: [
        { id: "tipo", rotulo: "Tipo de estudo", tipo: "escolha", obrigatorio: true, valor: "APR", largura: "full",
          opcoes: [{ valor: "APR", texto: "APR / JSA" }, { valor: "HAZOP", texto: "HAZOP" }] },
        { id: "area", rotulo: "Área", tipo: "texto", obrigatorio: true, max: 80 },
        { id: "data", rotulo: "Data do estudo", tipo: "data", obrigatorio: true, valor: REF, maxData: REF },
        { id: "titulo", rotulo: "Título do estudo", tipo: "texto", obrigatorio: true, max: 150, largura: "full" },
        { id: "participantesIds", rotulo: "Participantes", tipo: "multi", obrigatorio: true, opcoes: opPessoas, largura: "full" },
        { id: "recomendacoes", rotulo: "Recomendações", tipo: "info", html: recomendacoesHtml, largura: "full" }
      ],
      aoSalvar: function (v) {
        var recs = Array.prototype.map.call(m.el.querySelectorAll(".rec-row"), function (row) {
          return { descricao: row.querySelector("[data-rec-desc]").value.trim(), responsavelId: row.querySelector("[data-rec-resp]").value, prazo: row.querySelector("[data-rec-prazo]").value };
        }).filter(function (r) { return r.descricao; });
        if (!recs.length) return Promise.reject({ erros: ["Inclua ao menos uma recomendação."] });
        return API.salvarAnaliseRisco({ projetoId: projetoId, tipo: v.tipo, area: v.area, titulo: v.titulo, data: v.data, participantesIds: v.participantesIds, recomendacoes: recs }).then(function (r) {
          GI.ui.toast("Estudo " + r.codigo + " registrado.", "success");
          if (aoConcluir) aoConcluir(r.codigo);
        });
      }
    });
    m.el.querySelector("#rec-add").addEventListener("click", function () {
      m.el.querySelector("#rec-lista").insertAdjacentHTML("beforeend", linhaHtml(seq++));
      if (GI.ui) GI.ui.init(m.el);
    });
    m.el.addEventListener("click", function (ev) {
      var rm = ev.target.closest("[data-rec-remover]");
      if (rm) { var linhas = m.el.querySelectorAll(".rec-row"); if (linhas.length > 1) rm.closest(".rec-row").remove(); }
    });
    return m;
  }

  function fecharRecPrompt(codigo, indice, aoConcluir) {
    GI.form.abrir({
      titulo: "Fechar recomendação", tamanho: "sm", textoSalvar: "Fechar",
      campos: [
        { id: "data", rotulo: "Data de conclusão", tipo: "data", obrigatorio: true, valor: REF, maxData: REF },
        { id: "evidencia", rotulo: "Evidência", tipo: "textarea", max: 300, linhas: 2, ajuda: "Opcional." }
      ],
      aoSalvar: function (v) {
        return API.fecharRecomendacao(codigo, indice, v).then(function () {
          GI.ui.toast("Recomendação fechada.", "success");
          if (aoConcluir) aoConcluir();
        });
      }
    });
  }

  function verEstudo(codigo, aoConcluir) {
    return API.analiseRisco(codigo).then(function (a) {
      if (!a) { GI.ui.toast("Estudo não encontrado.", "warning"); return; }
      var tid = "t-rec-" + (++seqTabela);
      var corpo = document.createElement("div");
      corpo.innerHTML = '<div class="form-grid mb-4">' +
        campoInfo("Tipo", U.badge(a.tipo === "HAZOP" ? "HAZOP" : "APR / JSA", a.tipo === "HAZOP" ? "purple" : "info")) +
        campoInfo("Área", U.esc(a.area)) + campoInfo("Data", F.data(a.data)) +
        campoInfo("Participantes", a.participantesIds.map(function (id) { return U.esc(U.pessoa(id)); }).join(", ")) +
        "</div>" + '<div id="' + tid + '"></div>';
      var m = GI.modal.create({ title: a.codigo + " · " + a.titulo, subtitle: a.tipo + " · " + a.area, size: "xl", body: corpo, buttons: [{ label: "Fechar", variant: "secondary" }] });
      GI.tabela.criar(tid, {
        porPagina: 0, compacta: true, legenda: "Recomendações",
        colunas: [
          { id: "descricao", titulo: "Recomendação", valor: function (r) { return r.descricao; } },
          { id: "responsavel", titulo: "Responsável", valor: function (r) { return U.pessoa(r.responsavelId); } },
          { id: "prazo", titulo: "Prazo", tipo: "data", valor: function (r) { return r.prazo; } },
          { id: "situacao", titulo: "Situação", valor: function (r) { return r.situacao; },
            html: function (r) { return U.badge(r.situacao, r.situacao === "Fechada" ? "success" : (r.prazo < REF ? "danger" : "warning")); } }
        ],
        acoes: function (r) {
          var i = a.recomendacoes.indexOf(r), html = "";
          if (r.situacao !== "Fechada") html += '<button type="button" class="btn btn--ghost btn--sm" data-fechar-rec="' + i + '">' + U.icone("checkCircle") + "Fechar</button>";
          if (!r.acaoCriada) html += '<button type="button" class="btn btn--ghost btn--sm" data-criar-acao-rec="' + i + '">' + U.icone("actions") + "Criar ação</button>";
          return html || '<span class="text-small text-muted">·</span>';
        }
      }).atualizar(a.recomendacoes);
      corpo.addEventListener("click", function (ev) {
        var f = ev.target.closest("[data-fechar-rec]");
        if (f) { fecharRecPrompt(a.codigo, Number(f.getAttribute("data-fechar-rec")), function () { m.close(); verEstudo(a.codigo, aoConcluir); if (aoConcluir) aoConcluir(a.codigo); }); return; }
        var c = ev.target.closest("[data-criar-acao-rec]");
        if (c) {
          API.criarAcaoRecomendacao(a.codigo, Number(c.getAttribute("data-criar-acao-rec"))).then(function () {
            GI.ui.toast("Ação criada na Central.", "success");
            m.close(); verEstudo(a.codigo, aoConcluir);
            if (aoConcluir) aoConcluir(a.codigo);
          }).catch(erroApi);
        }
      });
      GI.ui.init(m.el);
      return m;
    });
  }

  /* ======================================================================
     HHT (horas trabalhadas) e Inspeções / observações / DDS (mensal)
     ====================================================================== */
  function registrarHht(projetoId, registro, aoConcluir) {
    if (projetoId == null) { GI.util.noProjeto("novo", "Registrar HHT"); return; }
    if (typeof registro === "function") { aoConcluir = registro; registro = null; }
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar HHT.", "warning"); return; }
    var meses = ultimosMeses(15);
    GI.form.abrir({
      titulo: "Registrar HHT do mês", tamanho: "md", subtitulo: "Grava (ou atualiza) o mês e a empresa informados",
      campos: [
        { id: "mes", rotulo: "Mês", tipo: "select", obrigatorio: true, opcoes: meses.map(function (m) { return { valor: m, texto: U.mesCurto(m) + "/" + m.slice(0, 4) }; }),
          valor: registro ? registro.mes : REF.slice(0, 7), desabilitado: !!registro },
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: empresas(), valor: registro ? String(registro.empresaId) : "", desabilitado: !!registro },
        { id: "efetivoMedio", rotulo: "Efetivo médio", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 5000, valor: registro ? registro.efetivoMedio : undefined },
        { id: "hht", rotulo: "Horas-homem trabalhadas (HHT)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 999999, valor: registro ? registro.hht : undefined }
      ],
      aoSalvar: function (v) {
        return API.salvarHht({ projetoId: projetoId, mes: registro ? registro.mes : v.mes, empresaId: registro ? registro.empresaId : v.empresaId, efetivoMedio: v.efetivoMedio, hht: v.hht }).then(function (r) {
          GI.ui.toast(r.novo ? "HHT registrado." : "HHT atualizado.", "success");
          if (aoConcluir) aoConcluir();
        });
      }
    });
  }

  function registrarMes(projetoId, registro, aoConcluir) {
    if (projetoId == null) { GI.util.noProjeto("novo", "Registrar mês"); return; }
    if (!API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar estes dados.", "warning"); return; }
    var meses = ultimosMeses(15);
    GI.form.abrir({
      titulo: "Registrar mês (DDS, inspeções e observações)", tamanho: "md", subtitulo: "Consolidado do mês; grava (ou atualiza) o total informado",
      campos: [
        { id: "mes", rotulo: "Mês", tipo: "select", obrigatorio: true, opcoes: meses.map(function (m) { return { valor: m, texto: U.mesCurto(m) + "/" + m.slice(0, 4) }; }), valor: registro ? registro.mes : REF.slice(0, 7), desabilitado: !!registro },
        { id: "ddsProgramados", rotulo: "DDS programados", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 2000, valor: registro ? registro.ddsProgramados : 0 },
        { id: "ddsRealizados", rotulo: "DDS realizados", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 2000, valor: registro ? registro.ddsRealizados : 0 },
        { id: "itensInspecionados", rotulo: "Itens de checklist inspecionados", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 20000, valor: registro ? registro.itensInspecionados : 0 },
        { id: "itensConformes", rotulo: "Itens conformes", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 20000, valor: registro ? registro.itensConformes : 0 },
        { id: "observacoes", rotulo: "Observações comportamentais", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 5000, valor: registro ? registro.observacoes : 0 },
        { id: "desvios", rotulo: "Desvios (atos e condições inseguras)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 5000, valor: registro ? registro.desvios : 0,
          ajuda: "Nível 5 da pirâmide de segurança." }
      ],
      aoSalvar: function (v) {
        return API.salvarHseMensal({ projetoId: projetoId, mes: registro ? registro.mes : v.mes, ddsProgramados: v.ddsProgramados, ddsRealizados: v.ddsRealizados,
          itensInspecionados: v.itensInspecionados, itensConformes: v.itensConformes, observacoes: v.observacoes, desvios: v.desvios }).then(function (r) {
          GI.ui.toast(r.novo ? "Mês registrado." : "Mês atualizado.", "success");
          if (aoConcluir) aoConcluir();
        });
      }
    });
  }

  GI.hse = {
    pronto: pronto, projeto: projeto, pessoas: pessoas, empresas: empresas, ultimosMeses: ultimosMeses, erroApi: erroApi,
    situacaoOcorrencia: situacaoOcorrencia, nivelBadge: nivelBadge, potencial: potencial, prazoBadge: prazoBadge,
    GRAVIDADE_REAL: GRAVIDADE_REAL, campoInfo: campoInfo,
    novaOcorrencia: novaOcorrencia, investigar: investigar, novaAcaoCorretiva: novaAcaoCorretiva,
    iniciarTratamento: iniciarTratamento, encerrarOcorrencia: encerrarOcorrencia, verOcorrencia: verOcorrencia,
    novoEstudo: novoEstudo, verEstudo: verEstudo, fecharRecPrompt: fecharRecPrompt,
    registrarHht: registrarHht, registrarMes: registrarMes
  };
})(window.GI = window.GI || {});
