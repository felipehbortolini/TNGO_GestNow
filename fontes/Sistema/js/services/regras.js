/* ==========================================================================
   regras.js | Regras de negócio puras (sem acesso a dados nem à tela).
   Usadas pela fachada api.js e pelas telas. Na fase com backend, as mesmas
   regras passam a ser aplicadas também no servidor (defesa em profundidade).
   Valores financeiros sempre em centavos (inteiros).
   ========================================================================== */
(function (GI) {
  "use strict";

  var DIA = 86400000;

  function data(iso) {
    if (!iso) return null;
    if (iso instanceof Date) return iso;
    var d = new Date(String(iso).length === 10 ? iso + "T00:00:00" : iso);
    return isNaN(d) ? null : d;
  }
  function diasEntre(inicio, fim) {
    var a = data(inicio), b = data(fim);
    return a && b ? Math.round((b - a) / DIA) : null;
  }

  /* Motor de status único da ação (replicado do sistema atual):
     Informação não é ação; com conclusão = Concluída; replanejada ou prevista
     anterior à referência = Atrasada; demais = Em andamento. */
  function statusAcao(acao, referencia) {
    if (!acao) return { chave: "andamento", rotulo: "Em andamento", ehAcao: true };
    if (String(acao.tipo || "").toLowerCase().indexOf("inform") === 0) return { chave: "info", rotulo: "Informação", ehAcao: false };
    if (acao.conclusao) return { chave: "concluida", rotulo: "Concluída", ehAcao: true };
    var base = data(acao.replanejada) || data(acao.prevista);
    if (base && base < data(referencia)) return { chave: "atrasada", rotulo: "Atrasada", ehAcao: true };
    return { chave: "andamento", rotulo: "Em andamento", ehAcao: true };
  }

  /* Severidade do score P x I conforme a escala ativa nos parâmetros */
  function severidade(score, paramRiscos, riscoVida) {
    var escala = paramRiscos.escalas[paramRiscos.escalaAtiva];
    var faixas = escala.faixas.slice().sort(function (a, b) { return b.minimo - a.minimo; });
    if (riscoVida && escala.riscoVidaEhAlto) return faixas[0];
    for (var i = 0; i < faixas.length; i++) if (score >= faixas[i].minimo) return faixas[i];
    return faixas[faixas.length - 1];
  }

  /* Faixa do mapa de calor de desvio de custo (% sobre o orçado atual) */
  function faixaDesvio(pct, limites) {
    var a = Math.abs(pct);
    if (a < limites[0]) return "neutro";
    var n = a > limites[2] ? 3 : a > limites[1] ? 2 : 1;
    return (pct > 0 ? "sobrecusto-" : "economia-") + n;
  }

  /* Taxas HSE (NBR 14280 por padrão): eventos x base / HHT */
  function taxaHSE(eventos, hht, base) {
    return hht > 0 ? eventos * base / hht : null;
  }

  /* Nível da pirâmide de Heinrich/Bird por tipo de ocorrência */
  var NIVEL_PIRAMIDE = {
    "Fatalidade": 1, "Acidente com afastamento": 1,
    "Trabalho restrito": 2, "Tratamento médico": 2, "Primeiros socorros": 2,
    "Dano material": 3, "Quase acidente": 4, "Desvio": 5
  };
  function nivelPiramide(tipo) { return NIVEL_PIRAMIDE[tipo] || null; }

  /* Avaliação da contratada: notas de 1 a 5 por critério, pesos dos parâmetros */
  function avaliarContratada(notas, paramAvaliacao) {
    var soma = 0, pesos = 0, exigePlano = false;
    paramAvaliacao.criterios.forEach(function (c) {
      var n = Number(notas[c.id]);
      if (!n) return;
      soma += n * c.peso; pesos += c.peso;
      if (n <= paramAvaliacao.notaExigePlano) exigePlano = true;
    });
    var nota100 = pesos ? Math.round(soma / pesos / 5 * 100) : null;
    var classe = null;
    paramAvaliacao.classes.slice().sort(function (a, b) { return b.minimo - a.minimo; }).some(function (c) {
      if (nota100 >= c.minimo) { classe = c; return true; }
      return false;
    });
    return { nota: nota100, classe: classe, exigePlano: exigePlano };
  }

  /* Validação dos parâmetros antes de salvar */
  function validarParametros(p) {
    var erros = [];
    var somaPesos = p.avaliacaoContratada.criterios.reduce(function (s, c) { return s + Number(c.peso || 0); }, 0);
    if (somaPesos !== 100) erros.push("A soma dos pesos da avaliação deve ser 100% (atual: " + somaPesos + "%).");
    var minimos = p.avaliacaoContratada.classes.map(function (c) { return Number(c.minimo); });
    for (var i = 1; i < minimos.length; i++) {
      if (minimos[i] >= minimos[i - 1]) { erros.push("As notas mínimas das classes devem ser decrescentes de A para D."); break; }
    }
    var pz = p.hse.prazos;
    if (!(pz.comunicacaoHoras > 0 && pz.investigacaoPreliminarHoras >= pz.comunicacaoHoras && pz.relatorioFinalDias > 0)) {
      erros.push("Prazos de HSE inválidos: a investigação preliminar não pode vencer antes da comunicação.");
    }
    if ([1000000, 200000].indexOf(Number(p.hse.baseTaxa)) < 0) erros.push("Base das taxas de HSE deve ser 1.000.000 (NBR 14280) ou 200.000 (OSHA).");
    var sup = p.suprimentos || {};
    if (sup.pesosMarcos) {
      var somaMarcos = Object.keys(sup.pesosMarcos).reduce(function (s, k) { return s + Number(sup.pesosMarcos[k] || 0); }, 0);
      if (somaMarcos !== 100) erros.push("A soma dos pesos dos marcos do MAS deve ser 100% (atual: " + somaMarcos + "%).");
    }
    if (sup.alcadas) {
      var tetos = sup.alcadas.map(function (a) { return a.ate; });
      var ok = tetos.every(function (v, k) { return k === tetos.length - 1 ? v == null : v > 0 && (k === 0 || v > tetos[k - 1]); });
      if (!ok) erros.push("As alçadas de suprimentos devem ter tetos crescentes e a última sem teto.");
    }
    if (sup.propostasMinimas != null && !(sup.propostasMinimas >= 1)) erros.push("O mínimo de propostas deve ser 1 ou mais.");
    var rk = p.riscos || {};
    if (rk.cadenciaDias) {
      var cad = ["critico", "alto", "moderado", "baixo"].map(function (k) { return rk.cadenciaDias[k]; }).filter(function (v) { return v != null; });
      if (!cad.every(function (v, k) { return v > 0 && (k === 0 || v >= cad[k - 1]); })) erros.push("A cadência de revisão deve crescer da faixa mais grave para a mais leve.");
    }
    if (rk.probabilidades) {
      var med = rk.probabilidades.map(function (x) { return Number(x.mediaPct); });
      if (!med.every(function (v, k) { return v > 0 && v < 100 && (k === 0 || v > med[k - 1]); })) erros.push("As probabilidades médias das faixas devem ser crescentes, entre 0 e 100%.");
    }
    var md = p.mudancas || {};
    if (md.alcadaGerentePctOrcamento != null && !(md.alcadaGerentePctOrcamento > 0 && md.alcadaGerentePctOrcamento <= 10)) erros.push("A alçada do gerente do projeto deve ficar entre 0 e 10% do orçamento.");
    if (md.quorumComite != null && !(md.quorumComite >= 2)) erros.push("O quórum do Comitê de Controle de Mudanças deve ser de 2 ou mais participantes.");
    ["prazoAnaliseDias", "prazoAcoesDias", "ratificacaoDias"].forEach(function (k) {
      if (md[k] != null && !(md[k] >= 1 && md[k] <= 90)) erros.push("Os prazos de mudanças (análise, ações e ratificação) devem ficar entre 1 e 90 dias.");
    });
    var lc = p.licoes || {};
    if (lc.alertaSemRegistroDias != null && !(lc.alertaSemRegistroDias >= 30 && lc.alertaSemRegistroDias <= 365)) erros.push("O alerta de projeto sem lição registrada deve ficar entre 30 e 365 dias.");
    var pr = p.produtividade || {};
    if (pr.jornadaDiariaHoras != null && !(pr.jornadaDiariaHoras >= 4 && pr.jornadaDiariaHoras <= 12)) erros.push("A jornada diária de referência deve ficar entre 4 e 12 horas.");
    ["metaTrabalhandoPct", "metaUtilizacaoPct"].forEach(function (k) {
      if (pr[k] != null && !(pr[k] > 0 && pr[k] <= 100)) erros.push("As metas de produtividade (trabalhando e utilização da jornada) devem ficar entre 0 e 100%.");
    });
    if (pr.aderenciaFaixas && !(pr.aderenciaFaixas[0] > 0 && pr.aderenciaFaixas[1] > pr.aderenciaFaixas[0] && pr.aderenciaFaixas[1] <= 100)) erros.push("As faixas de aderência semanal devem ser crescentes, entre 0 e 100%.");
    if (pr.pfFaixas && !(pr.pfFaixas[0] > 0 && pr.pfFaixas[1] > pr.pfFaixas[0])) erros.push("As faixas do fator de produtividade devem ser crescentes e maiores que zero.");
    if (pr.spiFaixas && !(pr.spiFaixas[0] > 0 && pr.spiFaixas[1] > pr.spiFaixas[0] && pr.spiFaixas[1] <= 1.5)) erros.push("As faixas do SPI de quantidades devem ser crescentes, entre 0 e 1,5.");
    if (pr.atrasoInicioFaixasMin && !(pr.atrasoInicioFaixasMin[0] >= 0 && pr.atrasoInicioFaixasMin[1] > pr.atrasoInicioFaixasMin[0] && pr.atrasoInicioFaixasMin[1] <= 240)) erros.push("As faixas do atraso de início devem ser crescentes, entre 0 e 240 minutos.");
    var hm = (p.hse || {}).metas;
    if (hm && !(hm.observacoesPor10MilHht >= 0 && hm.observacoesPor10MilHht <= 1000 && hm.desviosPor10MilHht >= 0 && hm.desviosPor10MilHht <= 1000)) erros.push("As metas proativas de HSE (observações e desvios por 10 mil HHT) devem ficar entre 0 e 1.000.");
    if (pr.semanasMedia != null && !(pr.semanasMedia >= 1 && pr.semanasMedia <= 12)) erros.push("A janela da média móvel de produtividade deve ficar entre 1 e 12 semanas.");
    var ep = p.eap || {};
    var ct = (p.financeiro || {}).contingencia;
    if (ct && !(ct.toleranciaConsumoPP >= 0 && ct.toleranciaConsumoPP <= 50)) erros.push("A tolerância do consumo da contingência acima do avanço deve ficar entre 0 e 50 p.p.");
    if (ct && !(ct.coberturaMinimaPct >= 0 && ct.coberturaMinimaPct <= 300)) erros.push("A cobertura mínima da exposição a riscos deve ficar entre 0 e 300%.");
    if (ep.faixasDesvioPP && !(ep.faixasDesvioPP[0] > 0 && ep.faixasDesvioPP[1] > ep.faixasDesvioPP[0])) erros.push("As faixas de desvio físico da EAP devem ser crescentes e maiores que zero.");
    if (ep.pesoMaximoPacotePct != null && !(ep.pesoMaximoPacotePct > 0 && ep.pesoMaximoPacotePct <= 100)) erros.push("O peso máximo de um pacote da EAP deve ficar entre 0 e 100%.");
    if (ep.estimadoMaximoPct != null && !(ep.estimadoMaximoPct > 0 && ep.estimadoMaximoPct <= (ep.pesoMaximoPacotePct || 100))) erros.push("O peso máximo de pacote medido por percentual estimado deve ser maior que zero e até o peso máximo do pacote.");
    (ep.modelosEtapas || []).forEach(function (m) {
      var sm = (m.etapas || []).reduce(function (s, e) { return s + Number(e.peso || 0); }, 0);
      if (Math.abs(sm - 100) > 0.001) erros.push("As etapas do modelo " + m.nome + " precisam somar 100 (hoje somam " + sm + ").");
    });
    var ql = p.qualidade || {};
    if (ql.prazoTratamentoDias) {
      var pt = ql.prazoTratamentoDias;
      if (!(pt.critica >= 1 && pt.maior >= pt.critica && pt.menor >= pt.maior && pt.menor <= 180)) erros.push("Os prazos de tratamento da RNC devem crescer da severidade Crítica para a Menor, entre 1 e 180 dias.");
    }
    if (ql.verificacaoEficaciaDias != null && !(ql.verificacaoEficaciaDias >= 0 && ql.verificacaoEficaciaDias <= 180)) erros.push("A espera da verificação de eficácia deve ficar entre 0 e 180 dias.");
    ["metaAprovacaoInspecaoPct", "metaConformidadeAuditoriaPct"].forEach(function (k) {
      if (ql[k] != null && !(ql[k] > 0 && ql[k] <= 100)) erros.push("As metas da qualidade (aprovação em inspeções e conformidade em auditorias) devem ficar entre 0 e 100%.");
    });
    if (ql.notificacaoClienteHoras != null && !(ql.notificacaoClienteHoras >= 0 && ql.notificacaoClienteHoras <= 240)) erros.push("A antecedência da notificação ao cliente deve ficar entre 0 e 240 horas.");
    var pf = p.portfolio || {};
    if (pf.criterios) {
      var somaCrit = pf.criterios.reduce(function (s, c) { return s + Number(c.peso || 0); }, 0);
      if (Math.abs(somaCrit - 100) > 0.001) erros.push("Os pesos dos critérios de ponderação do portfólio devem somar 100% (atual: " + somaCrit + "%).");
      if (pf.criterios.some(function (c) { return !(Number(c.peso) >= 0); })) erros.push("Os pesos dos critérios de ponderação não podem ser negativos.");
    }
    return erros.filter(function (x, k) { return erros.indexOf(x) === k; });
  }

  /* ---------------- Portfólio ----------------
     Ponderação composta dos projetos na carteira. criterios: [{ id, peso (%), fonte }];
     projetos: [{ id, orcamentoCentavos, notas: { idCriterio: 1..5 } }].
     fonte "orcamento": participação do orçamento do projeto no total; "nota": participação da nota.
     Peso do projeto (%) = soma(peso do critério x participação); os pesos somam 100 (maior resto,
     2 casas). Devolve { idProjeto: { peso, partes: { idCriterio: participação % } } }. */
  function ponderarPortfolio(projetos, criterios) {
    var lista = projetos || [], crit = criterios || [];
    var somaCrit = crit.reduce(function (s, c) { return s + Number(c.peso || 0); }, 0) || 1;
    var partes = {};
    lista.forEach(function (p) { partes[p.id] = {}; });
    crit.forEach(function (c) {
      var valor = function (p) { return c.fonte === "orcamento" ? Number(p.orcamentoCentavos) || 0 : Number((p.notas || {})[c.id]) || 0; };
      var total = lista.reduce(function (s, p) { return s + valor(p); }, 0);
      lista.forEach(function (p) { partes[p.id][c.id] = total ? valor(p) / total * 100 : 100 / (lista.length || 1); });
    });
    var brutos = lista.map(function (p) {
      return { chave: p.id, peso: crit.reduce(function (s, c) { return s + Number(c.peso || 0) * partes[p.id][c.id] / 100; }, 0) / somaCrit * 100 };
    });
    var pesos = reescalarPesos(brutos, 100);
    var r = {};
    lista.forEach(function (p) {
      var pt = {};
      Object.keys(partes[p.id]).forEach(function (k) { pt[k] = arred2(partes[p.id][k]); });
      r[p.id] = { peso: pesos[p.id], partes: pt };
    });
    return r;
  }

  /* ---------------- 08 Governança ----------------
     Alçada mínima de decisão da mudança: Gerente do projeto quando o custo (em módulo)
     cabe no percentual do orçamento e o prazo não afeta marco contratual; senão, Comitê. */
  function alcadaMudanca(custoCentavos, orcamentoCentavos, afetaMarcoContratual, pctGerente) {
    var limite = Math.round((orcamentoCentavos || 0) * (pctGerente || 0) / 100);
    var gerente = Math.abs(custoCentavos || 0) <= limite && !afetaMarcoContratual;
    return { alcada: gerente ? "Gerente do projeto" : "Comitê", limiteCentavos: limite };
  }

  /* ---------------- 05 Riscos ----------------
     Score = P x I (1 a 25). Impacto resultante = maior valor entre as dimensões
     avaliadas (regra do pior caso); pode ser elevado, nunca reduzido. */
  function impactoResultante(dimensoes) {
    var vals = Object.keys(dimensoes || {}).map(function (k) { return Number(dimensoes[k]) || 0; });
    return vals.length ? Math.max.apply(null, vals) : 0;
  }
  /* VME em centavos: probabilidade média da faixa x impacto em custo */
  function vme(p, impactoCustoCentavos, probabilidades) {
    var f = (probabilidades || []).filter(function (x) { return x.nivel === p; })[0];
    return f ? Math.round((impactoCustoCentavos || 0) * f.mediaPct / 100) : 0;
  }
  /* Cadência (dias) pela faixa de severidade; a mais longa quando a faixa não tem valor */
  function cadenciaRisco(sevId, cadencias) {
    if (cadencias[sevId]) return cadencias[sevId];
    var v = Object.keys(cadencias).map(function (k) { return cadencias[k]; });
    return Math.max.apply(null, v);
  }
  /* Posição da faixa na escala (0 = mais leve) para comparar severidades */
  function ordemFaixa(sevId, paramRiscos) {
    var f = paramRiscos.escalas[paramRiscos.escalaAtiva].faixas.slice().sort(function (a, b) { return a.minimo - b.minimo; });
    for (var i = 0; i < f.length; i++) if (f[i].id === sevId) return i;
    /* faixa inexistente na escala ativa (ex.: "critico" na CIPM): trata como a mais grave */
    return sevId === "critico" ? f.length - 1 : -1;
  }

  /* ---------------- 04 Suprimentos ---------------- */
  /* Situação de um marco do MAS na data de referência.
     m = { lb, previsao, real, na }. desvio = dias em relação à LB (positivo = atraso).
     na: não se aplica | prazo: realizado até a LB | atraso: realizado depois da LB |
     vencido: sem realização e a previsão (ou a LB) já passou | previsto-atraso: previsão futura depois da LB |
     a-vencer: previsão futura dentro da LB | sem-data: marco ainda sem LB nem previsão. */
  function situacaoMarco(m, referencia) {
    if (!m || m.na) return { chave: "na", desvio: null };
    if (m.real) {
      var d1 = m.lb ? diasEntre(m.lb, m.real) : 0;
      return { chave: d1 > 0 ? "atraso" : "prazo", desvio: d1 };
    }
    var alvo = m.previsao || m.lb;
    if (!alvo) return { chave: "sem-data", desvio: null };
    var d2 = m.lb ? diasEntre(m.lb, alvo) : 0;
    if (data(alvo) < data(referencia)) return { chave: "vencido", desvio: d2, diasVencido: diasEntre(alvo, referencia) };
    return { chave: d2 > 0 ? "previsto-atraso" : "a-vencer", desvio: d2 };
  }
  /* Folga em relação à data necessária na obra (ROS): positivo = sobra; negativo = crítico */
  function folga(ros, previsaoEntrega) { return diasEntre(previsaoEntrega, ros); }
  function faixaFolga(dias, alerta, concluido) {
    if (concluido) return "concluido";
    if (dias == null) return "sem-data";
    return dias < 0 ? "critico" : dias <= alerta ? "atencao" : "ok";
  }
  /* Alçada exigida para aprovar a adjudicação (primeira faixa cujo teto cobre o valor) */
  function alcada(valorCentavos, alcadas) {
    for (var i = 0; i < alcadas.length; i++) if (alcadas[i].ate == null || valorCentavos <= alcadas[i].ate) return alcadas[i];
    return alcadas[alcadas.length - 1];
  }
  /* Equalização: nota comercial = menor preço válido ÷ preço x 100; final ponderada pelos pesos */
  function notaComercial(valor, menorValor) { return valor > 0 ? menorValor / valor * 100 : null; }
  function notaFinal(notaTec, notaCom, pesoTec, pesoCom) {
    return notaTec == null || notaCom == null ? null : (notaTec * pesoTec + notaCom * pesoCom) / (pesoTec + pesoCom);
  }

  /* ---------------- 07 HSE ---------------- */
  /* Classificação fixa da matriz de gravidade x potencial (P x I, escala 1 a 5 cada eixo).
     Mesma nomenclatura e cores das faixas de risco (05), por consistência visual; não depende
     da escala de riscos ativa nos parâmetros (é uma matriz própria do registro de ocorrências). */
  function faixaPotencialHSE(p, i) {
    var score = (Number(p) || 0) * (Number(i) || 0);
    if (score >= 15) return { id: "critico", nome: "Crítico", score: score };
    if (score >= 10) return { id: "alto", nome: "Alto", score: score };
    if (score >= 5) return { id: "moderado", nome: "Moderado", score: score };
    return { id: "baixo", nome: "Baixo", score: score };
  }


  /* ---------------- 02 Produtividade ----------------
     Semanas ISO 8601 (segunda a domingo) no formato "2026-S39". */
  function semanaIso(iso) {
    var d = data(iso);
    if (!d) return null;
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var dia = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - dia);
    var ano = t.getUTCFullYear();
    var n = Math.ceil(((t - Date.UTC(ano, 0, 1)) / DIA + 1) / 7);
    return ano + "-S" + (n < 10 ? "0" : "") + n;
  }
  /* Segunda-feira da semana ISO ("2026-S39" -> "2026-09-21") */
  function inicioSemana(rotulo) {
    var m = /^(\d{4})-S(\d{2})$/.exec(String(rotulo || ""));
    if (!m) return null;
    var ano = Number(m[1]), n = Number(m[2]);
    var jan4 = new Date(Date.UTC(ano, 0, 4));
    var seg = new Date(jan4.getTime() - ((jan4.getUTCDay() || 7) - 1) * DIA + (n - 1) * 7 * DIA);
    return seg.toISOString().slice(0, 10);
  }
  function somarSemanas(rotulo, n) {
    var ini = inicioSemana(rotulo);
    if (!ini) return null;
    var d = new Date(ini + "T12:00:00Z");
    d.setUTCDate(d.getUTCDate() + 7 * n);
    return semanaIso(d.toISOString().slice(0, 10));
  }
  function semanasEntre(ini, fim) {
    var a = inicioSemana(ini), b = inicioSemana(fim);
    return a && b ? Math.round((new Date(b) - new Date(a)) / (7 * DIA)) : null;
  }
  function listaSemanas(ini, fim) {
    var n = semanasEntre(ini, fim), l = [];
    for (var k = 0; n != null && k <= n; k++) l.push(somarSemanas(ini, k));
    return l;
  }
  /* Pesos por semana conforme o perfil de distribuição da linha de base:
     linear (uniforme), curvaS (rampa 20% / pico 60% / desmobilização 20%),
     inicio (concentrado no início) e fim (concentrado no fim). */
  function pesosPerfil(n, perfil) {
    var w = [];
    for (var k = 0; k < n; k++) {
      var x = (k + 0.5) / n;
      if (perfil === "curvaS") w.push(x < 0.2 ? 0.2 + 0.8 * x / 0.2 : x > 0.8 ? 0.2 + 0.8 * (1 - x) / 0.2 : 1);
      else if (perfil === "inicio") w.push(1.6 - 1.2 * x);
      else if (perfil === "fim") w.push(0.4 + 1.2 * x);
      else w.push(1);
    }
    return w;
  }
  /* Distribui o total pelas semanas no perfil escolhido, com "casas" decimais, pelo método
     do maior resto: a soma fecha exatamente com o total da linha de base. */
  function distribuirQuantidade(total, n, perfil, casas) {
    if (!(n > 0)) return [];
    var f = Math.pow(10, casas || 0), unidades = Math.round(total * f);
    var w = pesosPerfil(n, perfil), sw = w.reduce(function (s, x) { return s + x; }, 0);
    var exato = w.map(function (x) { return unidades * x / sw; });
    var base = exato.map(Math.floor);
    var falta = unidades - base.reduce(function (s, x) { return s + x; }, 0);
    exato.map(function (x, k) { return { k: k, r: x - base[k] }; }).sort(function (a, b) { return b.r - a.r || a.k - b.k; })
      .slice(0, falta).forEach(function (o) { base[o.k] += 1; });
    return base.map(function (u) { return u / f; });
  }
  /* "07:45" -> minutos desde 00:00 */
  function minutos(hhmm) {
    var m = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm || ""));
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  }
  function duracaoHoras(ini, fim) {
    var a = minutos(ini), b = minutos(fim);
    return a == null || b == null || b < a ? null : (b - a) / 60;
  }
  /* Faixa de um indicador: "success" | "warning" | "danger".
     maiorMelhor: aderência, % trabalhando; senão (fator de produtividade) menor é melhor. */
  function faixaIndicador(v, faixas, maiorMelhor) {
    if (v == null || isNaN(v)) return null;
    if (maiorMelhor) return v >= faixas[1] ? "success" : v >= faixas[0] ? "warning" : "danger";
    return v <= faixas[0] ? "success" : v <= faixas[1] ? "warning" : "danger";
  }

  /* ---------------- 02 EAP (avanço físico) ----------------
     Critérios de medição do pacote de trabalho. O real é sempre calculado a partir das
     entradas do critério; pacote de planejamento não mede avanço (fica em 0). */
  var CRITERIOS_EAP = ["Etapas", "Unidades", "Marco 0/100", "Marco 50/50", "Percentual estimado"];
  function arred2(v) { return Math.round(v * 100) / 100; }
  function avancoPacoteEap(p) {
    if (!p || p.tipo === "Planejamento") return 0;
    var v = 0;
    switch (p.criterio) {
      case "Etapas": v = (p.etapas || []).reduce(function (s, e) { return s + (Number(e.peso) || 0) * (Number(e.pct) || 0) / 100; }, 0); break;
      case "Unidades": v = p.quantidade > 0 ? Math.min(100, (Number(p.executado) || 0) / p.quantidade * 100) : 0; break;
      case "Marco 0/100": v = p.estado === "Concluído" ? 100 : 0; break;
      case "Marco 50/50": v = p.estado === "Concluído" ? 100 : p.estado === "Iniciado" ? 50 : 0; break;
      case "Percentual estimado": v = Number(p.estimadoPct) || 0; break;
      default: v = 0;
    }
    return arred2(Math.max(0, Math.min(100, v)));
  }
  /* Converte um % acumulado nas entradas do critério (importação do avanço).
     Etapas: preenche em sequência; marcos só aceitam os degraus do critério.
     Devolve { ok, entradas, msg }. */
  function entradasPorPercentual(p, pct) {
    pct = Number(pct);
    if (isNaN(pct) || pct < 0 || pct > 100) return { ok: false, msg: "O avanço precisa ficar entre 0 e 100%." };
    switch (p.criterio) {
      case "Etapas":
        var resto = pct;
        var etapas = (p.etapas || []).map(function (e) {
          var usar = Math.min(e.peso, Math.max(0, resto)); resto -= usar;
          return { nome: e.nome, peso: e.peso, pct: e.peso ? arred2(usar / e.peso * 100) : 0 };
        });
        return { ok: true, entradas: { etapas: etapas } };
      case "Unidades": return { ok: true, entradas: { executado: arred2(p.quantidade * pct / 100) } };
      case "Marco 0/100":
        if (pct !== 0 && pct !== 100) return { ok: false, msg: "Marco 0/100 só aceita 0 ou 100%." };
        return { ok: true, entradas: { estado: pct === 100 ? "Concluído" : "Não iniciado" } };
      case "Marco 50/50":
        if ([0, 50, 100].indexOf(pct) < 0) return { ok: false, msg: "Marco 50/50 só aceita 0, 50 ou 100%." };
        return { ok: true, entradas: { estado: pct === 100 ? "Concluído" : pct === 50 ? "Iniciado" : "Não iniciado" } };
      case "Percentual estimado": return { ok: true, entradas: { estimadoPct: arred2(pct) } };
      default: return { ok: false, msg: "Pacote sem critério de medição." };
    }
  }
  /* Reescala pesos (% do projeto, 2 casas) para que somem "total", pelo maior resto.
     pesos: [{ chave, peso }] -> { chave: peso } */
  function reescalarPesos(pesos, total) {
    var soma = pesos.reduce(function (s, x) { return s + x.peso; }, 0);
    var alvo = Math.round(total * 100);
    var brutos = pesos.map(function (x) { var v = soma ? x.peso / soma * alvo : 0; return { chave: x.chave, base: Math.floor(v), resto: v - Math.floor(v) }; });
    var falta = alvo - brutos.reduce(function (s, x) { return s + x.base; }, 0);
    brutos.slice().sort(function (a, b) { return b.resto - a.resto; }).slice(0, Math.max(0, falta)).forEach(function (x) { x.base += 1; });
    var r = {};
    brutos.forEach(function (x) { r[x.chave] = x.base / 100; });
    return r;
  }
  /* Faixa do desvio físico (real menos previsto, p.p.): "success" | "warning" | "danger" */
  function faixaDesvioFisico(desvioPP, faixas) {
    if (desvioPP == null || isNaN(desvioPP)) return null;
    return desvioPP >= -faixas[0] ? "success" : desvioPP >= -faixas[1] ? "warning" : "danger";
  }

  /* ---------------- Períodos do relato e do relatório gerencial ----------------
     Semanal: semana ISO "2026-S38" (segunda a domingo). Mensal: "2026-08" (mês civil). */
  function isoUtc(d) { return d.toISOString().slice(0, 10); }
  function somarDias(iso, n) { var d = new Date(iso + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return isoUtc(d); }
  function ultimoDiaMes(mes) { var p = mes.split("-").map(Number); return isoUtc(new Date(Date.UTC(p[0], p[1], 0, 12))); }
  function somarMeses(mes, n) { var p = mes.split("-").map(Number); var d = new Date(Date.UTC(p[0], p[1] - 1 + n, 1, 12)); return isoUtc(d).slice(0, 7); }
  function periodoValido(tipo, periodo) {
    return tipo === "Semanal" ? /^\d{4}-S\d{2}$/.test(String(periodo)) && !!inicioSemana(periodo) : tipo === "Mensal" ? /^\d{4}-(0[1-9]|1[0-2])$/.test(String(periodo)) : false;
  }
  /* { inicio, fim } do período (datas ISO) */
  function limitesPeriodo(tipo, periodo) {
    if (!periodoValido(tipo, periodo)) return null;
    if (tipo === "Semanal") { var i = inicioSemana(periodo); return { inicio: i, fim: somarDias(i, 6) }; }
    return { inicio: periodo + "-01", fim: ultimoDiaMes(periodo) };
  }
  function periodoDaData(tipo, iso) { return tipo === "Semanal" ? semanaIso(iso) : String(iso).slice(0, 7); }
  function somarPeriodos(tipo, periodo, n) { return tipo === "Semanal" ? somarSemanas(periodo, n) : somarMeses(periodo, n); }
  /* Períodos do primeiro ao último, em ordem crescente */
  function listaPeriodos(tipo, primeiro, ultimo) {
    var l = [], p = primeiro, guarda = 0;
    while (p && p <= ultimo && guarda++ < 600) { l.push(p); p = somarPeriodos(tipo, p, 1); }
    return l;
  }

  GI.regras = {
    data: data, diasEntre: diasEntre, statusAcao: statusAcao, severidade: severidade,
    faixaDesvio: faixaDesvio, taxaHSE: taxaHSE, nivelPiramide: nivelPiramide,
    avaliarContratada: avaliarContratada, validarParametros: validarParametros,
    situacaoMarco: situacaoMarco, folga: folga, faixaFolga: faixaFolga, alcada: alcada,
    notaComercial: notaComercial, notaFinal: notaFinal,
    impactoResultante: impactoResultante, vme: vme, cadenciaRisco: cadenciaRisco, ordemFaixa: ordemFaixa,
    faixaPotencialHSE: faixaPotencialHSE, alcadaMudanca: alcadaMudanca,
    semanaIso: semanaIso, inicioSemana: inicioSemana, somarSemanas: somarSemanas, semanasEntre: semanasEntre, listaSemanas: listaSemanas,
    pesosPerfil: pesosPerfil, distribuirQuantidade: distribuirQuantidade, minutos: minutos, duracaoHoras: duracaoHoras, faixaIndicador: faixaIndicador,
    CRITERIOS_EAP: CRITERIOS_EAP, avancoPacoteEap: avancoPacoteEap, entradasPorPercentual: entradasPorPercentual, reescalarPesos: reescalarPesos,
    faixaDesvioFisico: faixaDesvioFisico, ponderarPortfolio: ponderarPortfolio,
    periodoValido: periodoValido, limitesPeriodo: limitesPeriodo, periodoDaData: periodoDaData, somarPeriodos: somarPeriodos, listaPeriodos: listaPeriodos,
    somarDias: somarDias, ultimoDiaMes: ultimoDiaMes
  };
})(window.GI = window.GI || {});
