from telas import EXPORT

EXTRAS = ["js/pages/governanca/governanca.js"]

def busca(ph, rotulo):
    return ('        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="%s" aria-label="%s"></div>\n' % (ph, rotulo))

FILTROS = '        <button type="button" class="btn btn--secondary" id="btn-filtros"><i data-icon="filter"></i>Filtros</button>\n'

SPECS = [
  { "modulo": "governanca", "tela": "mudancas", "titulo": "Gestão de mudanças", "graficos": True, "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-nova"><i data-icon="plus"></i>Nova solicitação</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar por número, título ou descrição", "Buscar solicitações de mudança") + """        <label class="sr-only" for="f-situacao">Situação</label>
        <select class="select select--curto" id="f-situacao"></select>
""" + FILTROS + """      </div>
      <div class="filter-bar mb-4" id="chips" hidden></div>
      <div class="tabs" role="tablist" data-tabs aria-label="Visões da gestão de mudanças">
        <button type="button" class="tab" role="tab" aria-selected="true" aria-controls="p-registro" id="a-registro"><i data-icon="list"></i>Registro <span class="tab__count" id="n-registro"></span></button>
        <button type="button" class="tab" role="tab" aria-selected="false" aria-controls="p-painel" id="a-painel"><i data-icon="barChart"></i>Painel</button>
      </div>
      <section class="tab-panel" id="p-registro" role="tabpanel" aria-labelledby="a-registro">
        <div class="kpi-grid kpi-grid--3" id="kpis"></div>
        <section class="card card--flush mt-4" aria-labelledby="t-sm">
          <div class="card__header"><div><h2 class="card__title" id="t-sm">Solicitações de mudança</h2><p class="card__subtitle"><span id="contagem"></span> · <span>Impacto em custo e em prazo (dias no caminho crítico) vindo da análise de impacto</span></p></div></div>
          <div id="tabela"></div>
        </section>
      </section>
      <section class="tab-panel" id="p-painel" role="tabpanel" aria-labelledby="a-painel" hidden>
        <div class="kpi-grid" id="kpis-painel"></div>
        <div class="grid grid--2 mt-6">
          <section class="card" aria-labelledby="t-situacao">
            <div class="card__header"><div><h2 class="card__title" id="t-situacao">Mudanças por situação</h2><p class="card__subtitle">Todas as solicitações do projeto</p></div></div>
            <div class="chart"><canvas id="g-situacao"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-origem">
            <div class="card__header"><div><h2 class="card__title" id="t-origem">Pareto por origem</h2><p class="card__subtitle">Quantidade, participação e percentual acumulado</p></div></div>
            <div id="pareto"></div>
          </section>
        </div>
        <div class="grid grid--2 mt-6">
          <section class="card" aria-labelledby="t-valor">
            <div class="card__header"><div><h2 class="card__title" id="t-valor">Valor aprovado acumulado</h2><p class="card__subtitle">Impacto em custo das mudanças aprovadas, pelo mês da decisão</p></div></div>
            <div class="chart"><canvas id="g-valor"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-prazo">
            <div class="card__header"><div><h2 class="card__title" id="t-prazo">Impacto de prazo acumulado</h2><p class="card__subtitle">Dias no caminho crítico das mudanças aprovadas, pelo mês da decisão</p></div></div>
            <div class="chart"><canvas id="g-prazo"></canvas></div>
          </section>
        </div>
        <section class="card mt-6" aria-labelledby="t-tipo">
          <div class="card__header"><div><h2 class="card__title" id="t-tipo">Mudanças por tipo</h2></div></div>
          <div class="chart chart--sm"><canvas id="g-tipo"></canvas></div>
        </section>
      </section>
""" },

  { "modulo": "governanca", "tela": "mudanca", "titulo": "Solicitação de mudança", "extras": EXTRAS,
    "voltar": ("mudancas.html", "Voltar para mudanças"),
    "acoes": EXPORT,
    "corpo": """      <div id="ficha"></div>
""" },

  { "modulo": "governanca", "tela": "licoes", "titulo": "Lições aprendidas", "graficos": True, "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-nova"><i data-icon="plus"></i>Nova lição</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar por palavra-chave, título ou recomendação", "Buscar no acervo de lições") + """        <label class="sr-only" for="f-tipo">Tipo</label>
        <select class="select select--curto" id="f-tipo"></select>
        <label class="sr-only" for="f-situacao">Situação</label>
        <select class="select select--curto" id="f-situacao"></select>
""" + FILTROS + """      </div>
      <div class="filter-bar mb-4" id="chips" hidden></div>
      <div class="tabs" role="tablist" data-tabs aria-label="Visões das lições aprendidas">
        <button type="button" class="tab" role="tab" aria-selected="true" aria-controls="p-acervo" id="a-acervo"><i data-icon="lightbulb"></i>Acervo <span class="tab__count" id="n-acervo"></span></button>
        <button type="button" class="tab" role="tab" aria-selected="false" aria-controls="p-painel" id="a-painel"><i data-icon="barChart"></i>Painel</button>
      </div>
      <section class="tab-panel" id="p-acervo" role="tabpanel" aria-labelledby="a-acervo">
        <p class="text-small text-muted mb-4" id="escopo"></p>
        <div id="kickoff"></div>
        <div class="licao-grid" id="cards"></div>
        <div class="mt-4" id="mais"></div>
      </section>
      <section class="tab-panel" id="p-painel" role="tabpanel" aria-labelledby="a-painel" hidden>
        <div class="kpi-grid" id="kpis-painel"></div>
        <div class="grid grid--2 mt-6">
          <section class="card" aria-labelledby="t-fase">
            <div class="card__header"><div><h2 class="card__title" id="t-fase">Lições por fase</h2><p class="card__subtitle">A repetir e a evitar, no acervo do projeto</p></div></div>
            <div class="chart"><canvas id="g-fase"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-area">
            <div class="card__header"><div><h2 class="card__title" id="t-area">Lições por área de conhecimento</h2></div></div>
            <div class="chart"><canvas id="g-area"></canvas></div>
          </section>
        </div>
        <div class="grid grid--2 mt-6">
          <section class="card card--flush" aria-labelledby="t-sit">
            <div class="card__header"><div><h2 class="card__title" id="t-sit">Lições por situação</h2><p class="card__subtitle">Fluxo de validação: Rascunho, Em validação, Validada e Publicada</p></div></div>
            <div id="t-situacao"></div>
          </section>
          <section class="card card--flush" aria-labelledby="t-reuso">
            <div class="card__header"><div><h2 class="card__title" id="t-reuso">Lições mais reusadas</h2><p class="card__subtitle">Publicadas com aplicação registrada</p></div></div>
            <div id="t-reusadas"></div>
          </section>
        </div>
      </section>
""" },
]
