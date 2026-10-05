from telas import EXPORT

SPECS = [
  { "modulo": "central-acoes", "tela": "acoes", "titulo": "Ações",
    "subtitulo": "Ações de todas as origens, com status calculado na data de referência.",
    "acoes": '<button type="button" class="btn btn--secondary" id="btn-followup"><i data-icon="mail"></i>Enviar follow-up</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid kpi-grid--4" id="kpis"></div>

      <div class="toolbar mt-6">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar assunto, referência ou responsável" aria-label="Buscar nas ações"></div>
        <button type="button" class="btn btn--secondary" id="btn-filtros"><i data-icon="filter"></i>Filtros</button>
        <div class="segmented" data-segmented id="visao" role="group" aria-label="Forma de visualização">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="lista"><i data-icon="list"></i>Lista</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="kanban"><i data-icon="kanban"></i>Kanban</button>
        </div>
      </div>
      <div class="filter-bar mb-4" id="chips"></div>

      <section class="card card--flush" id="painel-lista" aria-labelledby="t-lista">
        <div class="card__header">
          <div><h2 class="card__title" id="t-lista">Lista de ações</h2><p class="card__subtitle" id="contagem"></p></div>
          <button type="button" class="btn btn--ghost btn--sm" id="btn-colunas"><i data-icon="columns"></i>Colunas</button>
        </div>
        <div id="tabela"></div>
      </section>

      <section id="painel-kanban" hidden aria-label="Ações por status">
        <div class="kanban" id="kanban"></div>
      </section>
""" },

  { "modulo": "central-acoes", "tela": "dashboard", "titulo": "Dashboards e KPIs", "graficos": True,
    "subtitulo": "Indicadores do motor de status único (Concluída, Atrasada, Em andamento).",
    "acoes": EXPORT,
    "corpo": """      <div class="toolbar">
        <label class="sr-only" for="f-origem">Origem</label>
        <select class="select" id="f-origem"></select>
      </div>

      <div class="kpi-grid" id="kpis"></div>

      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-origem">
          <div class="card__header"><div><h2 class="card__title" id="t-origem">Status por origem</h2><p class="card__subtitle">Somente itens do tipo Ação</p></div></div>
          <div class="chart"><canvas id="g-origem"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-resp">
          <div class="card__header"><div><h2 class="card__title" id="t-resp">Ações abertas por responsável</h2><p class="card__subtitle">Em dia e atrasadas</p></div></div>
          <div class="chart"><canvas id="g-resp"></canvas></div>
        </section>
      </div>

      <section class="card mt-4" id="sec-projeto" aria-labelledby="t-projeto" hidden>
        <div class="card__header"><div><h2 class="card__title" id="t-projeto">Status por projeto</h2><p class="card__subtitle">Portfólio: ações de cada projeto da carteira</p></div></div>
        <div class="chart chart--sm"><canvas id="g-projeto"></canvas></div>
      </section>

      <section class="card mt-4" aria-labelledby="t-mes">
        <div class="card__header"><div><h2 class="card__title" id="t-mes">Previstas x concluídas por mês</h2><p class="card__subtitle">Previstas pela data vigente (replanejada, quando houver); concluídas pela data de conclusão</p></div></div>
        <div class="chart chart--sm"><canvas id="g-mes"></canvas></div>
      </section>

      <section class="card card--flush mt-4" aria-labelledby="t-ranking">
        <div class="card__header"><div><h2 class="card__title" id="t-ranking">Desempenho por responsável</h2><p class="card__subtitle">Ordenado pelo número de ações atrasadas</p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "central-acoes", "tela": "atas", "titulo": "Atas",
    "subtitulo": "Localizador de atas do projeto. Mostra só a revisão mais recente de cada ata.",
    "acoes": '<button type="button" class="btn btn--primary" id="btn-nova"><i data-icon="filePlus"></i>Gerar nova ata</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar número ou assunto" aria-label="Buscar atas"></div>
      </div>

      <section class="card card--flush" aria-labelledby="t-atas">
        <div class="card__header"><div><h2 class="card__title" id="t-atas">Atas</h2><p class="card__subtitle" id="contagem"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "central-acoes", "tela": "ata", "titulo": "Ata", "sem_abas": True,
    "subtitulo": "Dados da reunião, lista de presença, anotações e ações.",
    "voltar": ("atas.html", "Voltar para Atas"), "acoes": "",
    "corpo": """      <div id="ata"></div>
""" },
]
