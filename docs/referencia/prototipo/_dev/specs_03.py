from telas import EXPORT

NIVEL = """        <label class="sr-only" for="f-nivel">Mostrar até</label>
        <select class="select" id="f-nivel">
          <option value="1">Mostrar pacotes</option>
          <option value="2">Mostrar subpacotes</option>
          <option value="3" selected>Mostrar itens</option>
        </select>"""

EXTRAS = ["js/pages/financeiro/financeiro.js"]
BTN_COLUNAS = '<button type="button" class="btn btn--secondary btn--sm" id="btn-colunas"><i data-icon="columns"></i>Colunas</button>'

SPECS = [
  { "modulo": "financeiro", "tela": "eac", "titulo": "EAC", "extras": ["js/components/importar.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo item</button>'
             '<button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar Excel</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar código ou descrição" aria-label="Buscar na EAC"></div>
""" + NIVEL + """
        <label class="sr-only" for="f-tipo">Tipo de custo</label><select class="select" id="f-tipo"></select>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-eac">
        <div class="card__header"><div><h2 class="card__title" id="t-eac">Estrutura analítica de custos</h2><p class="card__subtitle" id="sub-eac"></p></div>
          """ + BTN_COLUNAS + """</div>
        <div id="tabela"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-rev">
        <div class="card__header"><div><h2 class="card__title" id="t-rev">Revisões do orçamento</h2><p class="card__subtitle">Rev 0 é a linha de base aprovada; o total só muda por nova revisão, a partir de SM aprovada</p></div>
          <button type="button" class="btn btn--secondary btn--sm" id="btn-revisao"><i data-icon="history"></i>Nova revisão</button></div>
        <div id="revisoes"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-rem">
        <div class="card__header"><div><h2 class="card__title" id="t-rem">Remanejamentos da revisão vigente</h2><p class="card__subtitle" id="sub-rem"></p></div>
          <button type="button" class="btn btn--secondary btn--sm" id="btn-remanejar"><i data-icon="swap"></i>Remanejar</button></div>
        <div id="remanejamentos"></div>
      </section>
""" },

  { "modulo": "financeiro", "tela": "mapa-controle", "titulo": "Mapa de controle", "extras": ["js/components/importar.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar custos</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar código ou descrição" aria-label="Buscar no mapa de controle"></div>
""" + NIVEL + """
        <label class="check"><input type="checkbox" id="f-desvio"> Só com desvio</label>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <div class="alert mt-4" id="reservas" hidden></div>
      <section class="card card--flush mt-6" aria-labelledby="t-mapa">
        <div class="card__header"><div><h2 class="card__title" id="t-mapa">Mapa de controle da EAC</h2><p class="card__subtitle" id="sub-mapa"></p><div class="mt-2" id="legenda"></div></div>
          """ + BTN_COLUNAS + """</div>
        <div id="tabela"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-top">
        <div class="card__header"><div><h2 class="card__title" id="t-top">Maiores sobrecustos</h2><p class="card__subtitle">Itens com projeção no término acima do orçado atual</p></div></div>
        <div id="top"></div>
      </section>
""" },

  { "modulo": "financeiro", "tela": "desembolso", "titulo": "Cronograma de desembolso", "graficos": True, "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" id="btn-enviar"><i data-icon="send"></i>Enviar à tesouraria</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <label class="sr-only" for="f-nivel">Mostrar até</label>
        <select class="select" id="f-nivel">
          <option value="1">Mostrar pacotes</option>
          <option value="2" selected>Mostrar subpacotes</option>
          <option value="3">Mostrar itens</option>
        </select>
      </div>
      <div class="kpi-grid kpi-grid--4" id="kpis"></div>
      <section class="card mt-6" aria-labelledby="t-hist">
        <div class="card__header"><div><h2 class="card__title" id="t-hist">Desembolso mensal</h2><p class="card__subtitle" id="sub-hist"></p></div></div>
        <div class="chart chart--lg"><canvas id="g-mensal"></canvas></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-grade">
        <div class="card__header"><div><h2 class="card__title" id="t-grade">Saldo a pagar por mês</h2><p class="card__subtitle">Valores em R$ mil · saldo = projeção no término menos realizado, distribuído pelo perfil da projeção</p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "financeiro", "tela": "kpis", "titulo": "KPIs de custo", "graficos": True, "extras": ["js/components/analise.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="financeiro"><i data-icon="clipboardList"></i>Análise do período</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid kpi-grid--3" id="kpis"></div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-ind">
          <div class="card__header"><div><h2 class="card__title" id="t-ind">CPI e SPI por mês</h2><p class="card__subtitle">1,00 = no plano; abaixo de 1,00 = acima do custo ou atrasado</p></div></div>
          <div class="chart"><canvas id="g-indices"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-va">
          <div class="card__header"><div><h2 class="card__title" id="t-va">Valor agregado acumulado</h2><p class="card__subtitle">Planejado (PV), agregado (EV) e custo real (AC)</p></div></div>
          <div class="chart"><canvas id="g-va"></canvas></div>
        </section>
      </div>
      <section class="card card--flush mt-4" id="sec-projetos" aria-labelledby="t-projetos" hidden>
        <div class="card__header"><div><h2 class="card__title" id="t-projetos">Desempenho de custo por projeto</h2><p class="card__subtitle">Portfólio: índices de cada projeto na data de corte; a carteira soma EV, PV e AC</p></div></div>
        <div id="tabela-projetos"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-corte">
        <div class="card__header"><div><h2 class="card__title" id="t-corte">Valor agregado na data de corte</h2><p class="card__subtitle" id="sub-corte"></p></div></div>
        <div id="resumo"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-periodos">
        <div class="card__header"><div><h2 class="card__title" id="t-periodos">Período a período</h2><p class="card__subtitle">Valores acumulados até cada mês</p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "financeiro", "tela": "curva-s", "titulo": "Curva S financeira", "graficos": True, "extras": ["js/components/analise.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="financeiro"><i data-icon="clipboardList"></i>Análise do período</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid kpi-grid--4" id="kpis"></div>
      <section class="card mt-6" aria-labelledby="t-curva">
        <div class="card__header"><div><h2 class="card__title" id="t-curva">Curva S financeira (CAPEX)</h2><p class="card__subtitle" id="sub-curva"></p></div></div>
        <div class="chart chart--lg"><canvas id="g-curva"></canvas></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-periodos">
        <div class="card__header"><div><h2 class="card__title" id="t-periodos">Período a período</h2><p class="card__subtitle">Valores em R$ mil</p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "financeiro", "tela": "contingencia", "titulo": "Contingência", "graficos": True, "extras": EXTRAS,
    "acoes": '<a class="btn btn--secondary" id="btn-sm" href="#"><i data-icon="fileText"></i>Solicitar uso (SM)</a>' + EXPORT,
    "corpo": """      <div class="alert alert--info" id="regra">
        <i data-icon="info"></i>
        <div class="alert__body">Reserva de contingência cobre riscos identificados (05) e integra a linha de base de custo; a reserva gerencial cobre o imprevisto e só o Comitê (patrocinador) libera. Nenhum valor sai das reservas sem SM aprovada (08): consumo pela fonte da reserva; saldo que não será usado volta ao patrocinador pela SM "Liberação de reserva".</div>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <div class="alert alert--warning mt-4" id="alertas" hidden></div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-burn">
          <div class="card__header"><div><h2 class="card__title" id="t-burn">Saldo da contingência</h2><p class="card__subtitle" id="sub-burn"></p></div></div>
          <div class="chart"><canvas id="g-burn"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-base">
          <div class="card__header"><div><h2 class="card__title" id="t-base">Linha de base de custo e reservas</h2><p class="card__subtitle">Orçado da EAC mais o saldo da contingência; a reserva gerencial fica fora da linha de base</p></div></div>
          <div id="composicao"></div>
        </section>
      </div>
      <section class="card card--flush mt-4" aria-labelledby="t-proj" id="sec-proj" hidden>
        <div class="card__header"><div><h2 class="card__title" id="t-proj">Reservas por projeto</h2><p class="card__subtitle">Consumo comparado ao avanço físico real e cobertura da exposição a riscos</p></div></div>
        <div id="projetos"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-mov">
        <div class="card__header"><div><h2 class="card__title" id="t-mov">Extrato de movimentos</h2><p class="card__subtitle">Constituição na linha de base, consumos por SM aprovada e pedidos em análise (ainda sem efeito no saldo)</p></div></div>
        <div id="movimentos"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-rsk">
        <div class="card__header"><div><h2 class="card__title" id="t-rsk">Ameaças ativas e cobertura</h2><p class="card__subtitle" id="sub-rsk"></p></div></div>
        <div id="riscos"></div>
      </section>
""" },

  { "modulo": "financeiro", "tela": "contratos", "titulo": "Contratos", "extras": EXTRAS,
    "acoes": EXPORT,
    "corpo": """      <div class="kpi-grid kpi-grid--3" id="kpis"></div>
      <div class="toolbar mt-6">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar número, contratada ou descrição" aria-label="Buscar nos contratos"></div>
        <label class="sr-only" for="f-contrato">Contrato</label><select class="select" id="f-contrato"></select>
      </div>
      <div class="tabs" role="tablist" data-tabs aria-label="Registros da administração contratual">
        <button type="button" class="tab" role="tab" aria-selected="true" aria-controls="p-contratos" id="a-contratos"><i data-icon="fileContract"></i>Contratos <span class="tab__count" id="n-contratos"></span></button>
        <button type="button" class="tab" role="tab" aria-selected="false" aria-controls="p-claims" id="a-claims"><i data-icon="gavel"></i>Claims <span class="tab__count" id="n-claims"></span></button>
        <button type="button" class="tab" role="tab" aria-selected="false" aria-controls="p-eot" id="a-eot"><i data-icon="calendar"></i>Extensões de prazo <span class="tab__count" id="n-eot"></span></button>
        <button type="button" class="tab" role="tab" aria-selected="false" aria-controls="p-marcos" id="a-marcos"><i data-icon="flag"></i>Marcos de pagamento <span class="tab__count" id="n-marcos"></span></button>
        <button type="button" class="tab" role="tab" aria-selected="false" aria-controls="p-aval" id="a-aval"><i data-icon="star"></i>Avaliações <span class="tab__count" id="n-aval"></span></button>
      </div>
      <section class="tab-panel card card--flush" id="p-contratos" role="tabpanel" aria-labelledby="a-contratos">
        <div class="card__header"><div><h2 class="card__title">Contratos</h2><p class="card__subtitle" id="sub-contratos"></p></div></div>
        <div id="t-contratos"></div>
      </section>
      <section class="tab-panel card card--flush" id="p-claims" role="tabpanel" aria-labelledby="a-claims" hidden>
        <div class="card__header"><div><h2 class="card__title">Claims</h2><p class="card__subtitle" id="sub-claims"></p></div></div>
        <div id="t-claims"></div>
      </section>
      <section class="tab-panel card card--flush" id="p-eot" role="tabpanel" aria-labelledby="a-eot" hidden>
        <div class="card__header"><div><h2 class="card__title">Extensões de prazo</h2><p class="card__subtitle" id="sub-eot"></p></div></div>
        <div id="t-eot"></div>
      </section>
      <section class="tab-panel card card--flush" id="p-marcos" role="tabpanel" aria-labelledby="a-marcos" hidden>
        <div class="card__header"><div><h2 class="card__title">Marcos de pagamento</h2><p class="card__subtitle" id="sub-marcos"></p></div></div>
        <div id="t-marcos"></div>
      </section>
      <section class="tab-panel card card--flush" id="p-aval" role="tabpanel" aria-labelledby="a-aval" hidden>
        <div class="card__header"><div><h2 class="card__title">Avaliações de desempenho</h2><p class="card__subtitle" id="sub-aval"></p></div></div>
        <div id="t-aval"></div>
      </section>
""" },

  { "modulo": "financeiro", "tela": "contrato", "titulo": "Contrato", "graficos": True, "extras": EXTRAS,
    "voltar": ("contratos.html", "Voltar para Contratos"),
    "acoes": EXPORT,
    "corpo": """      <div id="faixa"></div>
      <div class="kpi-grid kpi-grid--4 mt-4" id="kpis"></div>
      <div class="tabs mt-6" role="tablist" data-tabs aria-label="Seções do contrato" id="abas"></div>
      <div id="paineis"></div>
""" },
]
