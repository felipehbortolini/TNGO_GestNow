from telas import EXPORT

EXTRAS = ["js/pages/suprimentos/suprimentos.js"]
BTN_COLUNAS = '<button type="button" class="btn btn--secondary btn--sm" id="btn-colunas"><i data-icon="columns"></i>Colunas</button>'

def busca(ph, rotulo):
    return ('        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="%s" aria-label="%s"></div>\n' % (ph, rotulo))

SPECS = [
  { "modulo": "suprimentos", "tela": "painel", "titulo": "Painel de suprimentos", "graficos": True, "extras": ["js/components/analise.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="suprimentos"><i data-icon="clipboardList"></i>Análise do período</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid kpi-grid--3" id="kpis"></div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-contr">
          <div class="card__header"><div><h2 class="card__title" id="t-contr">Curva de contratação</h2><p class="card__subtitle">Pacotes adjudicados acumulados: plano de compras x realizado</p></div></div>
          <div class="chart"><canvas id="g-contratacao"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-avanco">
          <div class="card__header"><div><h2 class="card__title" id="t-avanco">Avanço físico de suprimentos</h2><p class="card__subtitle" id="sub-avanco"></p></div></div>
          <div class="chart"><canvas id="g-avanco"></canvas></div>
        </section>
      </div>
      <div class="grid grid--2 mt-4">
        <section class="card" aria-labelledby="t-saving">
          <div class="card__header"><div><h2 class="card__title" id="t-saving">Saving acumulado</h2><p class="card__subtitle">Sobre a estimativa e na negociação, pelo mês da adjudicação</p></div></div>
          <div class="chart"><canvas id="g-saving"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-etapas">
          <div class="card__header"><div><h2 class="card__title" id="t-etapas">Pacotes por etapa</h2><p class="card__subtitle">Situação atual do plano de compras</p></div></div>
          <div class="chart"><canvas id="g-etapas"></canvas></div>
        </section>
      </div>
      <section class="card card--flush mt-4" aria-labelledby="t-folga">
        <div class="card__header"><div><h2 class="card__title" id="t-folga">Pedidos por folga em relação ao ROS</h2><p class="card__subtitle" id="sub-folga"></p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "suprimentos", "tela": "plano-compras", "titulo": "Plano de compras", "extras": ["js/components/importar.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo pacote</button>'
             '<button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar Excel</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar código, escopo ou item da EAC", "Buscar no plano de compras") + """        <label class="sr-only" for="f-tipo">Tipo</label><select class="select" id="f-tipo"></select>
        <label class="check"><input type="checkbox" id="f-lli"> Só itens de longo prazo (LLI)</label>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-plano">
        <div class="card__header"><div><h2 class="card__title" id="t-plano">Pacotes de compra</h2><p class="card__subtitle" id="sub-plano"></p></div>
          """ + BTN_COLUNAS + """</div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "suprimentos", "tela": "processos", "titulo": "Processos de compra", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-requisicao"><i data-icon="filePlus"></i>Nova requisição</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar pacote, RFx ou fornecedor", "Buscar processos") + """        <div class="segmented" data-segmented id="f-situacao" role="group" aria-label="Processos exibidos">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="andamento">Em andamento</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="todos">Todos</button>
        </div>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-proc">
        <div class="card__header"><div><h2 class="card__title" id="t-proc">Processos de compra (RFx)</h2><p class="card__subtitle" id="sub-proc"></p></div></div>
        <div id="tabela"></div>
      </section>
      <section class="card mt-4" id="detalhe" aria-labelledby="t-det" hidden>
        <div class="card__header"><div><h2 class="card__title" id="t-det"></h2><p class="card__subtitle" id="sub-det"></p></div>
          <div class="btn-group" id="fluxo"></div></div>
        <ol class="stepper stepper--rfx" id="etapas" aria-label="Etapas do processo de compra"></ol>
        <div id="resumo-det"></div>
        <div class="mt-6"><h3 class="section-title">Mapa de equalização</h3></div>
        <p class="text-small text-muted mb-4" id="sub-eq"></p>
        <div id="t-equalizacao"></div>
        <div class="mt-6"><h3 class="section-title">Histórico do processo</h3></div>
        <div id="historico"></div>
      </section>
""" },

  { "modulo": "suprimentos", "tela": "mas", "titulo": "Mapa de Suprimentos (MAS)", "extras": EXTRAS,
    "acoes": EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar pacote, escopo ou fornecedor", "Buscar no MAS") + """        <button type="button" class="btn btn--secondary" id="btn-filtros"><i data-icon="filter"></i>Filtros</button>
        <div class="segmented" data-segmented id="f-modo" role="group" aria-label="Conteúdo das células">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="datas">Datas</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="desvio">Desvio em dias</button>
        </div>
        <div class="segmented" data-segmented id="f-fase" role="group" aria-label="Marcos exibidos">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="todos">Todos</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="aquisicao">Aquisição</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="fabricacao" title="Fabricação e entrega">Fabricação</button>
        </div>
      </div>
      <div class="filter-bar" id="chips"></div>
      <div class="kpi-grid kpi-grid--3" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-mas">
        <div class="card__header"><div><h2 class="card__title" id="t-mas">Mapa de Suprimentos</h2><p class="card__subtitle" id="sub-mas"></p><div class="mt-2" id="legenda"></div></div></div>
        <div id="grade"></div>
      </section>
""" },

  { "modulo": "suprimentos", "tela": "diligenciamento", "titulo": "Diligenciamento e recebimento", "extras": ["js/components/importar.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar do ERP</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar pedido, fornecedor ou descrição", "Buscar pedidos") + """        <div class="segmented" data-segmented id="f-situacao" role="group" aria-label="Pedidos exibidos">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="abertos">Em aberto</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="todos">Todos</button>
        </div>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <div id="pendencias" class="mt-6"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-ped">
        <div class="card__header"><div><h2 class="card__title" id="t-ped">Pedidos em diligenciamento</h2><p class="card__subtitle" id="sub-ped"></p></div></div>
        <div id="tabela"></div>
      </section>
      <section class="card card--flush mt-4" id="detalhe" aria-labelledby="t-det" hidden>
        <div class="card__header"><div><h2 class="card__title" id="t-det"></h2><p class="card__subtitle" id="sub-det"></p></div>
          <div class="btn-group" id="acoes-det"></div></div>
        <div id="t-marcos"></div>
        <div class="card__footer" id="rodape-det"></div>
      </section>
""" },

  { "modulo": "suprimentos", "tela": "fornecedores", "titulo": "Fornecedores", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo fornecedor</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + busca("Buscar empresa ou categoria", "Buscar fornecedores") + """        <label class="sr-only" for="f-situacao">Situação</label><select class="select" id="f-situacao"></select>
        <label class="sr-only" for="f-categoria">Categoria</label><select class="select" id="f-categoria"></select>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-forn">
        <div class="card__header"><div><h2 class="card__title" id="t-forn">Fornecedores e contratadas</h2><p class="card__subtitle">Nota de desempenho vinda das avaliações de contrato (03) e entrega no prazo dos pedidos (04)</p></div>
          """ + BTN_COLUNAS + """</div>
        <div id="tabela"></div>
      </section>
""" },
]
