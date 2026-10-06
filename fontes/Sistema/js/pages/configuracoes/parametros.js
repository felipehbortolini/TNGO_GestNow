/* ==========================================================================
   Configurações > Parâmetros do sistema (Gestor e Admin)
   Grupos por módulo com os valores vigentes; edição por grupo em modal com justificativa
   obrigatória (cada gravação cria nova versão com vigência e autor); histórico de versões
   com as alterações entre versões. Validação e gravação só em GI.api.salvarParametros
   (GI.regras.validarParametros); a tela monta o objeto novo a partir dos campos.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var par = null, historico = [], filtro = { busca: "", modulo: "" }, podeEditar = false, tGrupos = {};

  /* ---------------- Caminhos (a.b.0.c) ---------------- */
  function ler(obj, caminho) { return caminho.split(".").reduce(function (o, k) { return o == null ? undefined : o[k]; }, obj); }
  function gravar(obj, caminho, valor) {
    var p = caminho.split("."), o = obj;
    for (var i = 0; i < p.length - 1; i++) { if (o[p[i]] == null) o[p[i]] = /^\d+$/.test(p[i + 1]) ? [] : {}; o = o[p[i]]; }
    o[p[p.length - 1]] = valor;
  }
  function idCampo(c) { return c.replace(/\./g, "__"); }

  /* ---------------- Definição dos grupos ----------------
     Campo: { caminho, rotulo, tipo: "numero"|"moeda"|"select"|"texto", unidade, min, max, passo, opcoes, somente } */
  function grupos(p) {
    var g = [];
    var ac = p.avaliacaoContratada;
    g.push({ id: "contratadas", modulo: "03", nome: "Avaliação de contratadas", onde: "03 Contratos, 04 Fornecedores", nota: "Pesos somam 100%; notas mínimas decrescentes de A para D.",
      campos: ac.criterios.map(function (c, k) { return { caminho: "avaliacaoContratada.criterios." + k + ".peso", rotulo: "Peso: " + c.nome, tipo: "numero", unidade: "%", min: 0, max: 100 }; })
        .concat(ac.classes.map(function (c, k) { return { caminho: "avaliacaoContratada.classes." + k + ".minimo", rotulo: "Nota mínima da classe " + c.classe + " (" + c.descricao + ")", tipo: "numero", min: 0, max: 100, somente: k === ac.classes.length - 1 }; }))
        .concat([{ caminho: "avaliacaoContratada.notaExigePlano", rotulo: "Nota de critério que exige evidência e plano de melhoria (igual ou abaixo)", tipo: "numero", min: 1, max: 4 },
          { caminho: "claims.prazoNotificacaoPadraoDias", rotulo: "Prazo contratual padrão de notificação de claim", tipo: "numero", unidade: "dias", min: 1, max: 180 }]) });
    g.push({ id: "financeiro", modulo: "03", nome: "Financeiro", onde: "03 Mapa de controle, EAC e Contingência", nota: "Faixas crescentes do mapa de calor do desvio da projeção sobre o orçado; alertas da contingência.",
      campos: [0, 1, 2].map(function (k) { return { caminho: "financeiro.faixasDesvio." + k, rotulo: "Faixa " + (k + 1) + " do mapa de calor", tipo: "numero", unidade: "%", min: 0, max: 100, passo: 0.5 }; }).concat([
        { caminho: "financeiro.contingencia.toleranciaConsumoPP", rotulo: "Contingência: tolerância do consumo acima do avanço físico", tipo: "numero", unidade: "p.p.", min: 0, max: 50, passo: 1 },
        { caminho: "financeiro.contingencia.coberturaMinimaPct", rotulo: "Contingência: cobertura mínima da exposição a riscos", tipo: "numero", unidade: "%", min: 0, max: 300, passo: 5 }]) });
    var su = p.suprimentos;
    var NOMES_MARCOS = { requisicao: "Requisição", rfx: "Emissão da RFx", propostas: "Propostas recebidas", eqTecnica: "Equalização técnica", eqComercial: "Equalização comercial",
      adjudicacao: "Aprovação / adjudicação", pedido: "Pedido ou contrato", documentos: "Documentos do fornecedor", fabricacao: "Fabricação", inspecao: "Inspeção / FAT", embarque: "Embarque", entrega: "Entrega" };
    g.push({ id: "suprimentos", modulo: "04", nome: "Suprimentos", onde: "04 Processos, Diligenciamento e MAS", nota: "Alçadas com tetos crescentes (a última sem teto); pesos dos marcos do MAS somam 100%.",
      campos: [{ caminho: "suprimentos.propostasMinimas", rotulo: "Propostas mínimas por processo", tipo: "numero", min: 1, max: 10 },
        { caminho: "suprimentos.folgaAlertaDias", rotulo: "Folga de alerta em relação ao ROS", tipo: "numero", unidade: "dias", min: 0, max: 60 }]
        .concat(su.alcadas.filter(function (a) { return a.ate != null; }).map(function (a, k) { return { caminho: "suprimentos.alcadas." + k + ".ate", rotulo: "Alçada: " + a.papel + " até", tipo: "moeda" }; }))
        .concat(Object.keys(su.pesosMarcos).map(function (k) { return { caminho: "suprimentos.pesosMarcos." + k, rotulo: "Peso do marco: " + (NOMES_MARCOS[k] || k), tipo: "numero", unidade: "%", min: 0, max: 100 }; })) });
    var rk = p.riscos;
    g.push({ id: "riscos", modulo: "05", nome: "Riscos", onde: "05 Riscos e Início", nota: "Trocar a escala muda a contagem de riscos críticos em todo o sistema. Cadência crescente da faixa mais grave para a mais leve; probabilidades médias crescentes.",
      campos: [{ caminho: "riscos.escalaAtiva", rotulo: "Escala de severidade ativa", tipo: "select", opcoes: Object.keys(rk.escalas).map(function (k) { return { valor: k, texto: rk.escalas[k].nome }; }) }]
        .concat([["critico", "Crítico"], ["alto", "Alto"], ["moderado", "Moderado"], ["baixo", "Baixo"]].map(function (x) { return { caminho: "riscos.cadenciaDias." + x[0], rotulo: "Cadência máxima de revisão: " + x[1], tipo: "numero", unidade: "dias", min: 1, max: 365 }; }))
        .concat(rk.probabilidades.map(function (x, k) { return { caminho: "riscos.probabilidades." + k + ".mediaPct", rotulo: "Probabilidade média: " + x.nome + " (" + x.faixa + ")", tipo: "numero", unidade: "%", min: 1, max: 99 }; }))
        .concat([{ caminho: "riscos.pautaDiasAntesDoPrazo", rotulo: "Pauta: dias antes do prazo do alvo", tipo: "numero", unidade: "dias", min: 1, max: 180 },
          { caminho: "riscos.revisaoAlertaDias", rotulo: "Alerta de revisão próxima", tipo: "numero", unidade: "dias", min: 1, max: 90 }]) });
    g.push({ id: "qualidade", modulo: "06", nome: "Qualidade", onde: "06 Gestão da Qualidade", nota: "Prazos de tratamento crescentes da severidade Crítica para a Menor.",
      campos: [["critica", "Crítica"], ["maior", "Maior"], ["menor", "Menor"]].map(function (x) { return { caminho: "qualidade.prazoTratamentoDias." + x[0], rotulo: "Prazo de tratamento da RNC: " + x[1], tipo: "numero", unidade: "dias", min: 1, max: 180 }; })
        .concat([{ caminho: "qualidade.verificacaoEficaciaDias", rotulo: "Espera até a verificação de eficácia", tipo: "numero", unidade: "dias", min: 0, max: 180 },
          { caminho: "qualidade.metaAprovacaoInspecaoPct", rotulo: "Meta de aprovação em inspeções", tipo: "numero", unidade: "%", min: 1, max: 100 },
          { caminho: "qualidade.metaConformidadeAuditoriaPct", rotulo: "Meta de conformidade em auditorias", tipo: "numero", unidade: "%", min: 1, max: 100 },
          { caminho: "qualidade.notificacaoClienteHoras", rotulo: "Antecedência da notificação ao cliente (pontos H e W)", tipo: "numero", unidade: "horas", min: 0, max: 240 }]) });
    g.push({ id: "hse", modulo: "07", nome: "HSE", onde: "07 HSE e Início", nota: "A investigação preliminar não pode vencer antes da comunicação.",
      campos: [{ caminho: "hse.baseTaxa", rotulo: "Base das taxas", tipo: "select", opcoes: [{ valor: 1000000, texto: "1.000.000 HHT (NBR 14280)" }, { valor: 200000, texto: "200.000 HHT (OSHA)" }] },
        { caminho: "hse.prazos.comunicacaoHoras", rotulo: "Prazo de comunicação", tipo: "numero", unidade: "horas", min: 1, max: 240 },
        { caminho: "hse.prazos.investigacaoPreliminarHoras", rotulo: "Prazo da investigação preliminar", tipo: "numero", unidade: "horas", min: 1, max: 720 },
        { caminho: "hse.prazos.relatorioFinalDias", rotulo: "Prazo do relatório final (LTI e HiPo)", tipo: "numero", unidade: "dias", min: 1, max: 180 },
        { caminho: "hse.referenciaPiramide", rotulo: "Referência da pirâmide", tipo: "select", opcoes: [{ valor: "bird", texto: "Bird (1:10:30:600)" }, { valor: "heinrich", texto: "Heinrich (1:29:300)" }] },
        { caminho: "hse.metas.observacoesPor10MilHht", rotulo: "HSE: meta de observações comportamentais por 10 mil HHT", tipo: "numero", min: 0, max: 1000 },
        { caminho: "hse.metas.desviosPor10MilHht", rotulo: "HSE: meta de relato de desvios por 10 mil HHT", tipo: "numero", min: 0, max: 1000 }] });
    var ep = p.eap;
    g.push({ id: "planejamento", modulo: "02", nome: "Planejamento", onde: "02 EAP, Produtividade e Punch list", nota: "Faixas crescentes; cada modelo de etapas da EAP soma 100.",
      campos: [{ caminho: "punch.agingFaixas.0", rotulo: "Punch list: faixa 1 do tempo em aberto", tipo: "numero", unidade: "dias", min: 1, max: 365 },
        { caminho: "punch.agingFaixas.1", rotulo: "Punch list: faixa 2 do tempo em aberto", tipo: "numero", unidade: "dias", min: 1, max: 365 },
        { caminho: "produtividade.jornadaDiariaHoras", rotulo: "Produtividade: jornada diária de referência", tipo: "numero", unidade: "h", min: 4, max: 12, passo: 0.1 },
        { caminho: "produtividade.metaTrabalhandoPct", rotulo: "Produtividade: meta de pessoas trabalhando", tipo: "numero", unidade: "%", min: 1, max: 100 },
        { caminho: "produtividade.metaUtilizacaoPct", rotulo: "Produtividade: meta de utilização da jornada", tipo: "numero", unidade: "%", min: 1, max: 100 },
        { caminho: "produtividade.aderenciaFaixas.0", rotulo: "Produtividade: aderência semanal, alerta abaixo de", tipo: "numero", unidade: "%", min: 1, max: 100 },
        { caminho: "produtividade.aderenciaFaixas.1", rotulo: "Produtividade: aderência semanal, no plano a partir de", tipo: "numero", unidade: "%", min: 1, max: 100 },
        { caminho: "produtividade.pfFaixas.0", rotulo: "Produtividade: fator de produtividade no orçado até", tipo: "numero", min: 0.5, max: 3, passo: 0.01 },
        { caminho: "produtividade.pfFaixas.1", rotulo: "Produtividade: fator de produtividade em atenção até", tipo: "numero", min: 0.5, max: 3, passo: 0.01 },
        { caminho: "produtividade.spiFaixas.0", rotulo: "Produtividade: SPI de quantidades em alerta abaixo de", tipo: "numero", min: 0.1, max: 1.5, passo: 0.01 },
        { caminho: "produtividade.spiFaixas.1", rotulo: "Produtividade: SPI de quantidades no plano a partir de", tipo: "numero", min: 0.1, max: 1.5, passo: 0.01 },
        { caminho: "produtividade.atrasoInicioFaixasMin.0", rotulo: "Produtividade: atraso médio de início no plano até", tipo: "numero", unidade: "min", min: 0, max: 240 },
        { caminho: "produtividade.atrasoInicioFaixasMin.1", rotulo: "Produtividade: atraso médio de início em alerta acima de", tipo: "numero", unidade: "min", min: 0, max: 240 },
        { caminho: "produtividade.semanasMedia", rotulo: "Produtividade: janela da média móvel", tipo: "numero", unidade: "semanas", min: 1, max: 12 },
        { caminho: "eap.faixasDesvioPP.0", rotulo: "EAP: desvio físico em atenção até", tipo: "numero", unidade: "p.p.", min: 0.5, max: 50, passo: 0.5 },
        { caminho: "eap.faixasDesvioPP.1", rotulo: "EAP: desvio físico em alerta acima de", tipo: "numero", unidade: "p.p.", min: 0.5, max: 50, passo: 0.5 },
        { caminho: "eap.pesoMaximoPacotePct", rotulo: "EAP: peso máximo de um pacote", tipo: "numero", unidade: "%", min: 1, max: 100 },
        { caminho: "eap.estimadoMaximoPct", rotulo: "EAP: peso máximo com percentual estimado", tipo: "numero", unidade: "%", min: 0.5, max: 100, passo: 0.5 }]
        .concat(ep.modelosEtapas.reduce(function (a, m, k) {
          return a.concat(m.etapas.map(function (e, j) { return { caminho: "eap.modelosEtapas." + k + ".etapas." + j + ".peso", rotulo: "EAP, modelo " + m.nome + ": " + e.nome, tipo: "numero", unidade: "%", min: 0, max: 100 }; }));
        }, [])) });
    g.push({ id: "governanca", modulo: "08", nome: "Governança", onde: "08 Mudanças e Lições", nota: "Alçada do gerente entre 0 e 10% do orçamento; prazos entre 1 e 90 dias.",
      campos: [{ caminho: "mudancas.alcadaGerentePctOrcamento", rotulo: "Alçada do gerente do projeto (sem impacto em marco contratual)", tipo: "numero", unidade: "% do orçamento", min: 0.1, max: 10, passo: 0.1 },
        { caminho: "mudancas.prazoAnaliseDias", rotulo: "Prazo da análise de impacto", tipo: "numero", unidade: "dias", min: 1, max: 90 },
        { caminho: "mudancas.quorumComite", rotulo: "Quórum do Comitê de Controle de Mudanças", tipo: "numero", unidade: "participantes", min: 2, max: 15 },
        { caminho: "mudancas.prazoAcoesDias", rotulo: "Prazo das ações de implementação", tipo: "numero", unidade: "dias", min: 1, max: 90 },
        { caminho: "mudancas.ratificacaoDias", rotulo: "Ratificação da mudança emergencial", tipo: "numero", unidade: "dias", min: 1, max: 90 },
        { caminho: "licoes.alertaSemRegistroDias", rotulo: "Alerta de projeto sem lição registrada", tipo: "numero", unidade: "dias", min: 30, max: 365 }] });
    g.push({ id: "portfolio", modulo: "PF", nome: "Portfólio", onde: "Início, Curvas S e índices da carteira", nota: "Pesos dos critérios somam 100%; as notas dos projetos ficam na Ponderação do Início.",
      campos: p.portfolio.criterios.map(function (c, k) { return { caminho: "portfolio.criterios." + k + ".peso", rotulo: "Peso: " + c.nome, tipo: "numero", unidade: "%", min: 0, max: 100 }; }) });
    return g;
  }
  var NOME_MODULO = { "02": "02 Planejamento", "03": "03 Gestão Financeira", "04": "04 Suprimentos", "05": "05 Gestão de Riscos", "06": "06 Gestão da Qualidade",
    "07": "07 HSE", "08": "08 Governança", "PF": "Portfólio" };

  function rotulos() {
    var m = {};
    grupos(par).forEach(function (g) { g.campos.forEach(function (c) { m[c.caminho] = { grupo: g.nome, rotulo: c.rotulo, campo: c }; }); });
    return m;
  }
  function exibir(c, v) {
    if (v == null || v === "") return "·";
    if (c.tipo === "moeda") return F.moeda(v);
    if (c.tipo === "select") { var o = (c.opcoes || []).filter(function (x) { return String(x.valor) === String(v); })[0]; return o ? o.texto : String(v); }
    return F.num(v, Math.round(v) === v ? 0 : 2) + (c.unidade ? " " + c.unidade : "");
  }

  /* ---------------- Render ---------------- */
  function renderVersao() {
    document.getElementById("sub-versao").textContent = "Versão " + par.versao + " vigente desde " + F.data(par.vigenciaInicio);
    document.getElementById("versao").innerHTML = [
      ["Versão", "v" + par.versao], ["Vigência", "desde " + F.data(par.vigenciaInicio)], ["Alterada por", par.alteradoPor || "·"],
      ["Justificativa", par.justificativa || "Versão inicial"], ["Versões anteriores", F.num(historico.length)]
    ].map(function (x) { return '<div class="field"><span class="field__label">' + U.esc(x[0]) + "</span><div>" + U.esc(x[1]) + "</div></div>"; }).join("");
  }
  function passa(c, g) {
    if (filtro.modulo && g.modulo !== filtro.modulo) return false;
    return !filtro.busca || U.contem([c.rotulo, g.nome, c.caminho].join(" "), filtro.busca);
  }
  function renderGrupos() {
    var el = document.getElementById("grupos"), html = "";
    var lista = grupos(par);
    lista.forEach(function (g) {
      var vis = g.campos.filter(function (c) { return passa(c, g); });
      if (!vis.length) return;
      html += '<section class="card card--flush" aria-labelledby="t-g-' + g.id + '"><div class="card__header"><div><h2 class="card__title" id="t-g-' + g.id + '">' + U.esc(g.nome) +
        '</h2><p class="card__subtitle">' + U.esc(NOME_MODULO[g.modulo] + " · usado em " + g.onde + ". " + g.nota) + "</p></div>" +
        (podeEditar ? '<button type="button" class="btn btn--secondary btn--sm" data-editar="' + g.id + '">' + U.icone("edit") + "Editar</button>" : "") +
        '</div><div id="tg-' + g.id + '"></div></section>';
    });
    el.innerHTML = html || U.vazio("Nenhum parâmetro encontrado com os filtros atuais.", "search");
    tGrupos = {};
    lista.forEach(function (g) {
      var vis = g.campos.filter(function (c) { return passa(c, g); });
      if (!vis.length) return;
      tGrupos[g.id] = GI.tabela.criar("tg-" + g.id, {
        porPagina: 0, compacta: true, legenda: g.nome,
        colunas: [
          { id: "rotulo", titulo: "Parâmetro" },
          { id: "valor", titulo: "Valor vigente", classe: "num nowrap", valor: function (c) { return exibir(c, ler(par, c.caminho)); } }
        ]
      });
      tGrupos[g.id].atualizar(vis);
    });
    GI.ui.init(el);
  }

  /* ---------------- Edição ---------------- */
  function editar(id) {
    var g = grupos(par).filter(function (x) { return x.id === id; })[0];
    if (!g) return;
    var campos = g.campos.map(function (c) {
      var v = ler(par, c.caminho);
      var f = { id: idCampo(c.caminho), rotulo: c.rotulo + (c.unidade ? " (" + c.unidade + ")" : ""), obrigatorio: true, desabilitado: !!c.somente,
        ajuda: c.somente ? "Valor fixo (base da escala)." : "" };
      if (c.tipo === "select") return Object.assign(f, { tipo: "select", opcoes: c.opcoes, valor: String(v) });
      if (c.tipo === "moeda") return Object.assign(f, { tipo: "moeda", valor: v });
      return Object.assign(f, { tipo: "numero", valor: v, min: c.min, maxNumero: c.max, passo: c.passo || 1 });
    });
    campos.push({ id: "justificativa", rotulo: "Justificativa da alteração", tipo: "textarea", obrigatorio: true, max: 400, largura: "full",
      ajuda: "Obrigatória: vira a justificativa da nova versão (mínimo de 10 caracteres)." });
    GI.form.abrir({
      titulo: "Editar parâmetros · " + g.nome, subtitulo: "A gravação cria a versão " + (par.versao + 1) + " com vigência a partir de " + F.data(GI.api.referencia()),
      tamanho: g.campos.length > 10 ? "xl" : "lg", colunas: g.campos.length > 10 ? 3 : 2, textoSalvar: "Gravar nova versão",
      intro: '<p class="text-small text-muted mb-4">' + U.esc(g.nota) + "</p>",
      campos: campos,
      aoSalvar: function (v) {
        var novos = JSON.parse(JSON.stringify(par)), mudou = [];
        g.campos.forEach(function (c) {
          if (c.somente) return;
          var nv = v[idCampo(c.caminho)];
          if (c.tipo === "select") { var antigo = ler(par, c.caminho); nv = typeof antigo === "number" ? Number(nv) : nv; }
          if (String(nv) !== String(ler(par, c.caminho))) mudou.push(c);
          gravar(novos, c.caminho, nv);
        });
        if (!mudou.length) return Promise.reject({ erros: [{ msg: "Nenhum valor foi alterado." }] });
        var trocaEscala = mudou.some(function (c) { return c.caminho === "riscos.escalaAtiva"; });
        var confirmar = trocaEscala ? GI.modal.confirm({ title: "Trocar a escala de severidade",
          message: "A troca muda as faixas e a contagem de riscos críticos em todo o sistema (05 e Início). Confirma?" }) : Promise.resolve(true);
        return confirmar.then(function (ok) {
          if (!ok) return Promise.reject({ erros: [{ msg: "Troca de escala cancelada." }] });
          return GI.api.salvarParametros(novos, v.justificativa).then(function (r) {
            GI.ui.toast("Versão " + r.versao + " gravada: " + U.plural(mudou.length, "parâmetro alterado", "parâmetros alterados") + ".", "success", 6000);
            return carregar();
          });
        });
      }
    });
  }

  /* ---------------- Histórico ---------------- */
  function plano(obj, pref, out) {
    out = out || {};
    Object.keys(obj || {}).forEach(function (k) {
      if (["versao", "vigenciaInicio", "vigenciaFim", "alteradoPor", "justificativa"].indexOf(k) >= 0 && !pref) return;
      var c = pref ? pref + "." + k : k, v = obj[k];
      if (v && typeof v === "object") plano(v, c, out); else out[c] = v;
    });
    return out;
  }
  function diferencas(antes, depois) {
    var a = plano(antes), d = plano(depois), r = rotulos(), lista = [];
    Object.keys(Object.assign({}, a, d)).forEach(function (c) {
      if (String(a[c]) === String(d[c])) return;
      var info = r[c];
      lista.push({ grupo: info ? info.grupo : "Outros", parametro: info ? info.rotulo : c, de: info ? exibir(info.campo, a[c]) : String(a[c] == null ? "·" : a[c]),
        para: info ? exibir(info.campo, d[c]) : String(d[c] == null ? "·" : d[c]) });
    });
    return lista;
  }
  function versoes() {
    var todas = historico.concat([par]).slice().sort(function (x, y) { return y.versao - x.versao; });
    return todas.map(function (v, k) { var ant = todas[k + 1]; return { v: v, alteracoes: ant ? diferencas(ant, v) : [] }; });
  }
  function abrirHistorico() {
    var corpo = document.createElement("div");
    corpo.innerHTML = '<div id="t-versoes"></div><div id="det-versao" class="mt-4"></div>';
    var m = GI.modal.create({ title: "Histórico de versões", subtitle: "Quem alterou, quando e por quê", size: "xl", body: corpo, buttons: [{ label: "Fechar", variant: "secondary" }] });
    var lista = versoes();
    GI.tabela.criar("t-versoes", {
      porPagina: 0, compacta: true, legenda: "Versões dos parâmetros",
      colunas: [
        { id: "versao", titulo: "Versão", valor: function (x) { return x.v.versao; }, html: function (x) { return "<b>v" + x.v.versao + "</b>" + (x.v === par ? " " + U.badge("Vigente", "success") : ""); } },
        { id: "vigencia", titulo: "Vigência", valor: function (x) { return x.v.vigenciaInicio; }, html: function (x) { return U.esc(F.data(x.v.vigenciaInicio) + (x.v.vigenciaFim ? " a " + F.data(x.v.vigenciaFim) : " em diante")); } },
        { id: "autor", titulo: "Alterada por", valor: function (x) { return x.v.alteradoPor || ""; } },
        { id: "justificativa", titulo: "Justificativa", valor: function (x) { return x.v.justificativa || "Versão inicial"; } },
        { id: "alteracoes", titulo: "Alterações", tipo: "num", valor: function (x) { return x.alteracoes.length; } }
      ],
      acoes: function (x) { return x.alteracoes.length ? '<button type="button" class="btn btn--ghost btn--sm" data-versao="' + x.v.versao + '">' + U.icone("eye") + "Ver</button>" : ""; }
    }).atualizar(lista);
    corpo.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-versao]"); if (!b) return;
      var x = lista.filter(function (y) { return String(y.v.versao) === b.getAttribute("data-versao"); })[0];
      document.getElementById("det-versao").innerHTML = '<h3 class="section-title">Alterações da v' + x.v.versao + '</h3><div id="t-alt"></div>';
      GI.tabela.criar("t-alt", { porPagina: 0, compacta: true, legenda: "Alterações",
        colunas: [{ id: "grupo", titulo: "Grupo" }, { id: "parametro", titulo: "Parâmetro" }, { id: "de", titulo: "Antes" }, { id: "para", titulo: "Depois" }] }).atualizar(x.alteracoes);
    });
    GI.ui.init(m.el);
  }

  /* ---------------- Carga ---------------- */
  function carregar() {
    return Promise.all([GI.api.parametros(), GI.api.historicoParametros()]).then(function (r) {
      par = JSON.parse(JSON.stringify(r[0])); historico = r[1] || [];
      renderVersao(); renderGrupos();
    });
  }

  GI.exportar.registrar(function () {
    var linhas = [];
    grupos(par).forEach(function (g) { g.campos.forEach(function (c) { linhas.push([g.nome, c.rotulo, exibir(c, ler(par, c.caminho)), NOME_MODULO[g.modulo]]); }); });
    var hist = versoes().map(function (x) { return ["v" + x.v.versao, F.data(x.v.vigenciaInicio) + (x.v.vigenciaFim ? " a " + F.data(x.v.vigenciaFim) : ""), x.v.alteradoPor || "", x.v.justificativa || "Versão inicial", String(x.alteracoes.length)]; });
    return {
      titulo: "Parâmetros do sistema", subtitulo: "Versão " + par.versao + " vigente desde " + F.data(par.vigenciaInicio), arquivo: "parametros-v" + par.versao, orientacao: "l",
      blocos: [
        { tipo: "tabela", titulo: "Parâmetros vigentes", dados: { colunas: [{ titulo: "Grupo" }, { titulo: "Parâmetro" }, { titulo: "Valor" }, { titulo: "Módulo" }], bruto: linhas, texto: linhas } },
        { tipo: "tabela", titulo: "Histórico de versões", dados: { colunas: [{ titulo: "Versão" }, { titulo: "Vigência" }, { titulo: "Alterada por" }, { titulo: "Justificativa" }, { titulo: "Alterações" }], bruto: hist, texto: hist } }
      ]
    };
  });

  GI.util.pronto().then(function () {
    var s = GI.api.sessaoAtual();
    podeEditar = ["Gestor", "Admin"].indexOf(s.papelCodigo) >= 0;
    if (!podeEditar) document.getElementById("acesso").innerHTML = '<div class="alert alert--warning mb-4">' + U.icone("lock") + '<div class="alert__body">Seu papel permite só consultar os parâmetros.</div></div>';
    var fm = document.getElementById("f-modulo");
    fm.innerHTML = U.opcoes(Object.keys(NOME_MODULO).sort().map(function (k) { return { valor: k, texto: NOME_MODULO[k] }; }), "", "Módulo: todos");
    fm.addEventListener("change", function () { filtro.modulo = fm.value; renderGrupos(); });
    var b = document.getElementById("busca");
    b.addEventListener("input", U.debounce(function () { filtro.busca = b.value.trim(); renderGrupos(); }, 200));
    document.getElementById("grupos").addEventListener("click", function (ev) { var e = ev.target.closest("[data-editar]"); if (e) editar(e.getAttribute("data-editar")); });
    document.getElementById("btn-historico").addEventListener("click", abrirHistorico);
    return carregar();
  });
})(window.GI = window.GI || {});
