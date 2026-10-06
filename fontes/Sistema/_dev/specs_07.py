from telas import EXPORT

EXTRAS = ["js/pages/hse/hse.js"]

def busca(ph, rotulo):
    return ('        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="%s" aria-label="%s"></div>\n' % (ph, rotulo))

REFERENCIA = """        <div class="segmented" data-segmented id="f-referencia" role="group" aria-label="Referência da pirâmide">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="bird">Bird</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="heinrich">Heinrich</button>
        </div>
"""

SPECS = [
  { "modulo": "hse", "tela": "painel", "titulo": "Painel HSE", "graficos": True, "extras": ["js/components/analise.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="hse"><i data-icon="clipboardList"></i>Análise do período</button>' + '<a class="btn btn--secondary" id="lnk-ocorrencias" href="ocorrencias.html"><i data-icon="octagonAlert"></i>Ocorrências</a>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <label class="sr-only" for="f-ano">Ano</label>
        <select class="select" id="f-ano"></select>
        <label class="sr-only" for="f-mes">Mês</label>
        <select class="select" id="f-mes"></select>
        <div class="segmented" data-segmented id="f-referencia" role="group" aria-label="Referência da pirâmide">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="bird">Bird</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="heinrich">Heinrich</button>
        </div>
      </div>
      <p class="text-small text-muted mb-4" id="periodo"></p>
      <h2 class="section-title" id="t-kpis-mes">No mês selecionado</h2>
      <div class="kpi-grid" id="kpis-mes"></div>
      <h2 class="section-title mt-6" id="t-kpis-acum">Acumulado</h2>
      <div class="kpi-grid" id="kpis"></div>
      <h2 class="section-title mt-6" id="t-proativos">Indicadores proativos</h2>
      <div class="kpi-grid" id="proativos"></div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-piramide">
          <div class="card__header"><div><h2 class="card__title" id="t-piramide">Pirâmide de segurança</h2>
            <p class="card__subtitle">Mês selecionado e acumulado</p></div></div>
          <div class="pyramid-pair" id="piramides"></div>
          <p class="pyramid-ref" id="nota-piramide"></p>
        </section>
        <section class="card" aria-labelledby="t-evolucao">
          <div class="card__header"><div><h2 class="card__title" id="t-evolucao">Evolução mensal</h2>
            <p class="card__subtitle">Taxa de frequência (TF) e de lesões registráveis (TRIF), por mês com HHT registrado</p></div></div>
          <div class="chart"><canvas id="g-evolucao"></canvas></div>
        </section>
      </div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-area">
          <div class="card__header"><div><h2 class="card__title" id="t-area">Ocorrências por área</h2></div></div>
          <div id="por-area"></div>
        </section>
        <section class="card" aria-labelledby="t-empresa">
          <div class="card__header"><div><h2 class="card__title" id="t-empresa">Ocorrências por empresa</h2></div></div>
          <div id="por-empresa"></div>
        </section>
      </div>

""" },

  { "modulo": "hse", "tela": "ocorrencias", "titulo": "Ocorrências", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-nova"><i data-icon="plus"></i>Nova ocorrência</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar por número, área ou descrição", "Buscar ocorrências") + """        <label class="sr-only" for="f-situacao">Situação</label>
        <select class="select" id="f-situacao"></select>
        <label class="sr-only" for="f-tipo">Tipo</label>
        <select class="select" id="f-tipo"></select>
        <label class="check"><input type="checkbox" id="f-hipo"> Só alto potencial (HiPo)</label>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-oc">
        <div class="card__header"><div><h2 class="card__title" id="t-oc">Ocorrências do projeto</h2><p class="card__subtitle" id="contagem"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "hse", "tela": "inspecoes", "titulo": "Inspeções e observações", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Registrar mês</button>' + EXPORT,
    "corpo": """      <p class="text-small text-muted mb-4">Consolidado mensal de DDS, inspeções de checklist, observações comportamentais e desvios (nível 5 da pirâmide).</p>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-insp">
        <div class="card__header"><div><h2 class="card__title" id="t-insp">Registros mensais</h2><p class="card__subtitle" id="contagem"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "hse", "tela": "analises-risco", "titulo": "Análises de risco (APR/HAZOP)", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo estudo</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar por número, título ou área", "Buscar análises de risco") + """        <label class="sr-only" for="f-tipo">Tipo</label>
        <select class="select" id="f-tipo"></select>
        <label class="check"><input type="checkbox" id="f-abertas"> Só com recomendação aberta</label>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-ar">
        <div class="card__header"><div><h2 class="card__title" id="t-ar">Estudos registrados</h2><p class="card__subtitle" id="contagem"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "hse", "tela": "hht", "titulo": "Horas trabalhadas (HHT)", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Registrar HHT</button>' + EXPORT,
    "corpo": """      <p class="text-small text-muted mb-4">Base de todas as taxas reativas (TF, TRIF, TG); um registro por mês e empresa.</p>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-hht">
        <div class="card__header"><div><h2 class="card__title" id="t-hht">HHT por mês e empresa</h2><p class="card__subtitle" id="contagem"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },
]
