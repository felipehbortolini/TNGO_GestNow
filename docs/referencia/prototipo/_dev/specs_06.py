from telas import EXPORT

EXTRAS = ["js/pages/qualidade/qualidade.js"]

def busca(ph, rotulo):
    return ('        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="%s" aria-label="%s"></div>\n' % (ph, rotulo))

SPECS = [
  { "modulo": "qualidade", "tela": "painel", "titulo": "Painel da qualidade", "graficos": True, "extras": ["js/components/analise.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="qualidade"><i data-icon="clipboardList"></i>Análise do período</button>' + '<a class="btn btn--secondary" id="lnk-rnc" href="rnc.html"><i data-icon="octagonAlert"></i>Não conformidades</a>' + EXPORT,
    "corpo": """      <div class="kpi-grid" id="kpis"></div>
      <div class="alert alert--warning mt-4" id="alerta-auditorias" hidden></div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-rnc-mes">
          <div class="card__header"><div><h2 class="card__title" id="t-rnc-mes">RNC por mês</h2><p class="card__subtitle">Abertas e encerradas nos últimos 6 meses</p></div></div>
          <div class="chart chart--sm"><canvas id="g-rnc-mes"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-aprov">
          <div class="card__header"><div><h2 class="card__title" id="t-aprov">Aprovação em inspeções</h2><p class="card__subtitle" id="sub-aprov"></p></div></div>
          <div class="chart chart--sm"><canvas id="g-aprov"></canvas></div>
        </section>
      </div>
      <div class="grid grid--2 mt-4">
        <section class="card" aria-labelledby="t-pareto">
          <div class="card__header"><div><h2 class="card__title" id="t-pareto">Pareto de RNC por disciplina</h2><p class="card__subtitle">Quantidade por disciplina, da maior para a menor; canceladas fora</p></div></div>
          <div class="chart chart--sm"><canvas id="g-pareto"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-origem">
          <div class="card__header"><div><h2 class="card__title" id="t-origem">RNC por origem</h2><p class="card__subtitle">Onde a não conformidade foi detectada</p></div></div>
          <div class="chart chart--sm"><canvas id="g-origem"></canvas></div>
        </section>
      </div>
      <section class="card card--flush mt-4" aria-labelledby="t-pauta">
        <div class="card__header"><div><h2 class="card__title" id="t-pauta">Pauta de tratamento</h2><p class="card__subtitle" id="sub-pauta"></p></div></div>
        <div id="pauta"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-empresas">
        <div class="card__header"><div><h2 class="card__title" id="t-empresas">Desempenho da qualidade por empresa</h2><p class="card__subtitle">Inspeções, reprovações, RNC e custo da não qualidade</p></div></div>
        <div id="empresas"></div>
      </section>
""" },

  { "modulo": "qualidade", "tela": "rnc", "titulo": "Não conformidades", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-nova"><i data-icon="plus"></i>Nova RNC</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar número, descrição, origem ou empresa", "Buscar RNC") + """        <label class="sr-only" for="f-situacao">Situação</label>
        <select class="select" id="f-situacao"></select>
        <label class="sr-only" for="f-severidade">Severidade</label>
        <select class="select" id="f-severidade"></select>
        <label class="sr-only" for="f-disciplina">Disciplina</label>
        <select class="select" id="f-disciplina"></select>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-rnc">
        <div class="card__header"><div><h2 class="card__title" id="t-rnc">Relatórios de não conformidade</h2><p class="card__subtitle" id="contagem"></p></div>
          <button type="button" class="btn btn--ghost btn--sm" id="btn-colunas"><i data-icon="columns"></i>Colunas</button></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "qualidade", "tela": "inspecoes", "titulo": "Inspeções e ITP", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-inspecao"><i data-icon="clipboardCheck"></i>Registrar inspeção</button>' +
             '<button type="button" class="btn btn--secondary" id="btn-itp"><i data-icon="plus"></i>Novo ITP</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-itps">
        <div class="card__header"><div><h2 class="card__title" id="t-itps">Planos de inspeção e testes (ITP)</h2><p class="card__subtitle" id="sub-itps"></p></div></div>
        <div id="tabela-itps"></div>
      </section>
      <div class="toolbar mt-6">
""" + busca("Buscar registro, ponto, ITP ou RNC", "Buscar inspeções") + """        <label class="sr-only" for="f-itp">ITP</label>
        <select class="select" id="f-itp"></select>
        <label class="sr-only" for="f-resultado">Resultado</label>
        <select class="select" id="f-resultado"></select>
        <label class="sr-only" for="f-tipo">Tipo de ponto</label>
        <select class="select" id="f-tipo"></select>
      </div>
      <section class="card card--flush" aria-labelledby="t-insp">
        <div class="card__header"><div><h2 class="card__title" id="t-insp">Registros de inspeção</h2><p class="card__subtitle" id="contagem"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "qualidade", "tela": "auditorias", "titulo": "Auditorias", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-nova"><i data-icon="plus"></i>Planejar auditoria</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar número, escopo ou auditado", "Buscar auditorias") + """        <label class="sr-only" for="f-situacao">Situação</label>
        <select class="select" id="f-situacao"></select>
        <label class="sr-only" for="f-tipo">Tipo</label>
        <select class="select" id="f-tipo"></select>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-aud">
        <div class="card__header"><div><h2 class="card__title" id="t-aud">Programa de auditorias</h2><p class="card__subtitle" id="contagem"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },
]
