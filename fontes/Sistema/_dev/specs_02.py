from telas import EXPORT

SPECS = [
  { "modulo": "planejamento", "tela": "eap", "titulo": "EAP", "extras": ["js/components/importar.js", "js/pages/financeiro/financeiro.js"],
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo pacote</button>'
             '<button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar Excel</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar código ou descrição" aria-label="Buscar na EAP"></div>
        <label class="sr-only" for="f-nivel">Mostrar até</label>
        <select class="select" id="f-nivel">
          <option value="1">Mostrar áreas</option>
          <option value="2">Mostrar subáreas</option>
          <option value="3" selected>Mostrar pacotes</option>
        </select>
        <label class="sr-only" for="f-criterio">Critério de medição</label><select class="select" id="f-criterio"></select>
        <label class="sr-only" for="f-situacao">Situação</label>
        <select class="select" id="f-situacao">
          <option value="">Todas as situações</option>
          <option value="atrasado">Desvio fora da faixa</option>
          <option value="vencido">Término vencido</option>
          <option value="planejamento">Pacotes de planejamento</option>
        </select>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-eap">
        <div class="card__header"><div><h2 class="card__title" id="t-eap">Estrutura analítica do projeto</h2><p class="card__subtitle" id="sub-eap"></p></div>
          <div class="btn-group"><button type="button" class="btn btn--secondary btn--sm" id="btn-importar-avanco"><i data-icon="upload"></i>Importar avanço</button><button type="button" class="btn btn--secondary btn--sm" id="btn-colunas"><i data-icon="columns"></i>Colunas</button></div></div>
        <div id="tabela"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-rev">
        <div class="card__header"><div><h2 class="card__title" id="t-rev">Revisões da EAP</h2><p class="card__subtitle">Rev 0 é a linha de base aprovada; estrutura e pesos só mudam por nova revisão, a partir de SM aprovada com impacto em escopo</p></div>
          <button type="button" class="btn btn--secondary btn--sm" id="btn-revisao"><i data-icon="history"></i>Nova revisão</button></div>
        <div id="revisoes"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-des">
        <div class="card__header"><div><h2 class="card__title" id="t-des">Desdobramentos da revisão vigente</h2><p class="card__subtitle" id="sub-des"></p></div>
          <button type="button" class="btn btn--secondary btn--sm" id="btn-desdobrar"><i data-icon="listTree"></i>Desdobrar</button></div>
        <div id="desdobramentos"></div>
      </section>
""" },

  { "modulo": "planejamento", "tela": "curva-s", "titulo": "Curva S", "graficos": True,
    "subtitulo": "Avanço físico acumulado: linha de base, real e tendência.",
    "acoes": '<button type="button" class="btn btn--primary" id="btn-avanco"><i data-icon="plus"></i>Registrar avanço do mês</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid" id="kpis"></div>
      <section class="card mt-6" aria-labelledby="t-curva">
        <div class="card__header"><div><h2 class="card__title" id="t-curva">Curva S física</h2><p class="card__subtitle" id="sub-curva"></p></div></div>
        <div class="chart chart--lg"><canvas id="g-curva"></canvas></div>
      </section>
      <section class="card card--flush mt-4" id="sec-carteira" aria-labelledby="t-carteira" hidden>
        <div class="card__header"><div><h2 class="card__title" id="t-carteira">Composição da carteira</h2><p class="card__subtitle">Peso de cada projeto na Curva S ponderada e contribuição para o desvio da carteira</p></div></div>
        <div id="tabela-carteira"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-periodos">
        <div class="card__header"><div><h2 class="card__title" id="t-periodos">Período a período</h2><p class="card__subtitle">% acumulado e avanço no mês</p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "planejamento", "extras": ["js/components/analise.js"], "tela": "kpis", "titulo": "KPIs", "graficos": True,
    "subtitulo": "Desempenho de prazo do projeto e por área.",
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="planejamento"><i data-icon="clipboardList"></i>Análise do período</button>' + '<button type="button" class="btn btn--primary" id="btn-areas"><i data-icon="edit"></i>Atualizar avanço por área</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid" id="kpis"></div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-spi">
          <div class="card__header"><div><h2 class="card__title" id="t-spi">SPI por mês</h2><p class="card__subtitle">Real acumulado ÷ previsto acumulado (1,00 = no plano)</p></div></div>
          <div class="chart"><canvas id="g-spi"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-desvio">
          <div class="card__header"><div><h2 class="card__title" id="t-desvio">Previsto x real por área</h2><p class="card__subtitle">% de avanço na data de corte</p></div></div>
          <div class="chart"><canvas id="g-areas"></canvas></div>
        </section>
      </div>
      <section class="card card--flush mt-4" aria-labelledby="t-areas">
        <div class="card__header"><div><h2 class="card__title" id="t-areas">Avanço por área</h2><p class="card__subtitle">Pesos somam 100%; a média ponderada fecha com a Curva S</p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "planejamento", "extras": ["js/components/analise.js"], "tela": "relato", "titulo": "Relato do período",
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="planejamento"><i data-icon="clipboardList"></i>Análise do período</button>' + '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo relato</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <div class="segmented" data-segmented id="f-tipo" role="group" aria-label="Tipo de relato">
          <button type="button" class="segmented__opt" aria-pressed="true" data-value="">Todos</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="Semanal">Semanais</button>
          <button type="button" class="segmented__opt" aria-pressed="false" data-value="Mensal">Mensais</button>
        </div>
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar atividade, ponto de atenção ou risco" aria-label="Buscar nos relatos"></div>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-relatos">
        <div class="card__header"><div><h2 class="card__title" id="t-relatos">Relatos registrados</h2><p class="card__subtitle">Um registro semanal e um mensal por período; alimentam a página 2 do Planejamento no relatório gerencial (Início)</p></div></div>
        <div id="tabela"></div>
      </section>
""" },

  { "modulo": "planejamento", "tela": "6wla", "titulo": "6WLA",
    "subtitulo": "Planejamento das próximas 6 semanas: atividades, restrições e responsáveis.",
    "acoes": '<button type="button" class="btn btn--primary" id="btn-atividade"><i data-icon="plus"></i>Nova atividade</button>'
             '<button type="button" class="btn btn--secondary" id="btn-restricao"><i data-icon="flag"></i>Nova restrição</button>' + EXPORT,
    "corpo": """      <div class="kpi-grid" id="kpis"></div>
      <div class="toolbar mt-6">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar atividade, área ou código" aria-label="Buscar atividades"></div>
        <label class="sr-only" for="f-disciplina">Disciplina</label><select class="select" id="f-disciplina"></select>
        <label class="check"><input type="checkbox" id="f-restricao"> Só com restrição aberta</label>
      </div>
      <section class="card card--flush" aria-labelledby="t-grade">
        <div class="card__header"><div><h2 class="card__title" id="t-grade">Grade de 6 semanas</h2><p class="card__subtitle" id="sub-grade"></p></div></div>
        <div id="grade"></div>
      </section>
      <section class="card card--flush mt-4" aria-labelledby="t-restr">
        <div class="card__header"><div><h2 class="card__title" id="t-restr">Restrições</h2><p class="card__subtitle">Tipo, situação e data de remoção; vencida = data necessária passou sem remoção</p></div>
          <div class="segmented" data-segmented id="f-sit-restr" role="group" aria-label="Situação das restrições">
            <button type="button" class="segmented__opt" aria-pressed="true" data-value="abertas">Abertas</button>
            <button type="button" class="segmented__opt" aria-pressed="false" data-value="todas">Todas</button>
          </div></div>
        <div id="restricoes"></div>
      </section>
""" },

  { "modulo": "planejamento", "tela": "programacao-semanal", "titulo": "Programação Semanal", "graficos": True, "extras": ["js/components/importar.js"],
    "subtitulo": "Programação da semana, apontamento do realizado, PPC e aderência.",
    "acoes": '<button type="button" class="btn btn--primary" id="btn-nova-atv"><i data-icon="plus"></i>Nova atividade</button>'
             '<button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar Excel</button>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <label class="sr-only" for="f-semana">Semana</label><select class="select" id="f-semana"></select>
        <div class="toolbar__grow"></div>
        <div class="btn-group" id="fluxo"></div>
      </div>
      <div class="kpi-grid" id="kpis"></div>
      <section class="card card--flush mt-6" aria-labelledby="t-prog">
        <div class="card__header"><div><h2 class="card__title" id="t-prog">Atividades da semana</h2><p class="card__subtitle" id="sub-prog"></p></div></div>
        <div id="tabela"></div>
      </section>
      <div class="grid grid--2 mt-4" id="indicadores">
        <section class="card" aria-labelledby="t-ppc">
          <div class="card__header"><div><h2 class="card__title" id="t-ppc">PPC por área</h2><p class="card__subtitle">Atividades cumpridas ÷ programadas</p></div></div>
          <div class="chart chart--sm"><canvas id="g-ppc"></canvas></div>
        </section>
        <section class="card" aria-labelledby="t-ader">
          <div class="card__header"><div><h2 class="card__title" id="t-ader">Aderência por contratada</h2><p class="card__subtitle">Realizado ÷ previsto por atividade (limitado a 100%), média</p></div></div>
          <div class="chart chart--sm"><canvas id="g-ader"></canvas></div>
        </section>
      </div>
""" },

  { "modulo": "planejamento", "tela": "produtividade", "titulo": "Produtividade", "graficos": True, "extras": ["js/components/importar.js"],
    "subtitulo": "Quantidades da linha de base por semana, horas efetivas de campo e KPIs de performance geral e por empresa.",
    "acoes": EXPORT,
    "corpo": """      <div class="toolbar">
        <label class="sr-only" for="f-empresa">Empresa</label><select class="select" id="f-empresa"></select>
        <label class="sr-only" for="f-corte">Semana de corte</label><select class="select" id="f-corte"></select>
        <p class="text-small text-muted toolbar__grow" id="contexto"></p>
      </div>
      <div class="tabs" data-tabs role="tablist" aria-label="Visões da produtividade">
        <button type="button" class="tab" role="tab" id="aba-qtd" aria-controls="p-qtd" aria-selected="true"><i data-icon="barChart"></i>Quantidades</button>
        <button type="button" class="tab" role="tab" id="aba-horas" aria-controls="p-horas" aria-selected="false"><i data-icon="clock"></i>Horas efetivas</button>
        <button type="button" class="tab" role="tab" id="aba-kpis" aria-controls="p-kpis" aria-selected="false"><i data-icon="gauge"></i>KPIs de performance</button>
      </div>

      <section class="tab-panel" role="tabpanel" id="p-qtd" aria-labelledby="aba-qtd">
        <div class="toolbar">
          <label class="sr-only" for="f-grupo">Grupo</label><select class="select" id="f-grupo"></select>
          <div class="toolbar__grow"></div>
          <div class="btn-group">
            <button type="button" class="btn btn--primary" id="btn-apontar"><i data-icon="edit"></i>Apontar semana</button>
            <button type="button" class="btn btn--secondary" id="btn-novo-item"><i data-icon="plus"></i>Novo item da LB</button>
            <button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar Excel</button>
          </div>
        </div>
        <div class="alert alert--warning mb-4" id="alerta-qtd" hidden></div>
        <div class="kpi-grid kpi-grid--compacto" id="kpis-qtd"></div>
        <h2 class="section-title mt-6" id="t-grupos">Quantidades por grupo</h2>
        <div class="kpi-grid kpi-grid--compacto" id="grupos"></div>
        <div class="grid grid--2 mt-6">
          <section class="card" aria-labelledby="t-semanal">
            <div class="card__header"><div><h2 class="card__title" id="t-semanal">Produção semanal</h2><p class="card__subtitle" id="sub-semanal"></p></div></div>
            <div class="chart"><canvas id="g-semanal"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-acum">
            <div class="card__header"><div><h2 class="card__title" id="t-acum">Avanço acumulado</h2><p class="card__subtitle" id="sub-acum"></p></div></div>
            <div class="chart"><canvas id="g-acum"></canvas></div>
          </section>
        </div>
        <section class="card card--flush mt-4" aria-labelledby="t-itens">
          <div class="card__header"><div><h2 class="card__title" id="t-itens">Plano x realizado por item</h2><p class="card__subtitle" id="sub-itens"></p></div></div>
          <div id="tb-itens"></div>
        </section>
      </section>

      <section class="tab-panel" role="tabpanel" id="p-horas" aria-labelledby="aba-horas" hidden>
        <div class="toolbar">
          <label class="sr-only" for="f-area">Área (CWA)</label><select class="select" id="f-area"></select>
          <label class="sr-only" for="f-encarregado">Encarregado</label><select class="select" id="f-encarregado"></select>
          <label class="sr-only" for="f-periodo">Período</label><select class="select" id="f-periodo"></select>
          <div class="segmented" data-segmented id="f-visao" role="group" aria-label="Visão das horas efetivas">
            <button type="button" class="segmented__opt" aria-pressed="true" data-value="cp">Capacidade produtiva</button>
            <button type="button" class="segmented__opt" aria-pressed="false" data-value="amostragem">Amostragem do trabalho</button>
            <button type="button" class="segmented__opt" aria-pressed="false" data-value="paralisacoes">Paralisações</button>
          </div>
        </div>
        <p class="text-small text-muted mb-4" id="periodo-horas"></p>

        <div id="v-cp">
          <div class="kpi-grid kpi-grid--compacto" id="kpis-cp"></div>
          <section class="card mt-6" aria-labelledby="t-jornada">
            <div class="card__header"><div><h2 class="card__title" id="t-jornada">Jornada média na frente de serviço</h2>
              <p class="card__subtitle">Horários médios registrados pela fiscalização; atraso de início e execução em cada turno</p></div></div>
            <div id="linha-tempo"></div>
          </section>
          <div class="grid grid--2 mt-4">
            <section class="card" aria-labelledby="t-cp-area">
              <div class="card__header"><div><h2 class="card__title" id="t-cp-area">Capacidade produtiva por área</h2><p class="card__subtitle">Horas de execução por dia (média)</p></div></div>
              <div class="chart"><canvas id="g-cp-area"></canvas></div>
            </section>
            <section class="card" aria-labelledby="t-cp-dia">
              <div class="card__header"><div><h2 class="card__title" id="t-cp-dia">Capacidade produtiva por dia</h2><p class="card__subtitle" id="sub-cp-dia"></p></div></div>
              <div class="chart"><canvas id="g-cp-dia"></canvas></div>
            </section>
          </div>
          <section class="card card--flush mt-4" aria-labelledby="t-jornadas">
            <div class="card__header"><div><h2 class="card__title" id="t-jornadas">Registros de jornada</h2><p class="card__subtitle" id="sub-jornadas"></p></div>
              <button type="button" class="btn btn--primary" id="btn-jornada"><i data-icon="plus"></i>Registrar jornada</button></div>
            <div id="tb-jornadas"></div>
          </section>
        </div>

        <div id="v-amostragem" hidden>
          <div class="kpi-grid kpi-grid--compacto" id="kpis-amostra"></div>
          <section class="card mt-6" aria-labelledby="t-amostra-dia">
            <div class="card__header"><div><h2 class="card__title" id="t-amostra-dia">Distribuição por dia</h2><p class="card__subtitle">% de pessoas trabalhando, em trânsito e paradas nas rodadas de observação</p></div></div>
            <div class="chart"><canvas id="g-amostra-dia"></canvas></div>
          </section>
          <div class="grid grid--2 mt-4">
            <section class="card" aria-labelledby="t-mot-par">
              <div class="card__header"><div><h2 class="card__title" id="t-mot-par">Motivos de parada</h2><p class="card__subtitle">Pessoas observadas paradas, por motivo</p></div></div>
              <div id="motivos-parado"></div>
            </section>
            <section class="card" aria-labelledby="t-mot-tra">
              <div class="card__header"><div><h2 class="card__title" id="t-mot-tra">Motivos em trânsito</h2><p class="card__subtitle">Pessoas observadas em trânsito, por motivo</p></div></div>
              <div id="motivos-transito"></div>
            </section>
          </div>
          <section class="card card--flush mt-4" aria-labelledby="t-amostra-emp">
            <div class="card__header"><div><h2 class="card__title" id="t-amostra-emp">Por empresa e encarregado</h2><p class="card__subtitle">Pessoas observadas e distribuição no período</p></div>
              <button type="button" class="btn btn--primary" id="btn-amostra"><i data-icon="plus"></i>Registrar observação</button></div>
            <div id="tb-amostra-emp"></div>
          </section>
          <section class="card card--flush mt-4" aria-labelledby="t-amostras">
            <div class="card__header"><div><h2 class="card__title" id="t-amostras">Rodadas de observação</h2><p class="card__subtitle" id="sub-amostras"></p></div></div>
            <div id="tb-amostras"></div>
          </section>
        </div>

        <div id="v-paralisacoes" hidden>
          <div class="kpi-grid kpi-grid--compacto" id="kpis-par"></div>
          <section class="card card--flush mt-6" aria-labelledby="t-par-area">
            <div class="card__header"><div><h2 class="card__title" id="t-par-area">Por área (CWA)</h2><p class="card__subtitle">Capacidade produtiva, efetivo paralisado (Hhora = pessoas x horas) e máquinas ou equipamentos parados (Mhora = unidades x horas)</p></div></div>
            <div id="tb-par-area"></div>
          </section>
          <div class="grid grid--2 mt-4">
            <section class="card" aria-labelledby="t-par-mot">
              <div class="card__header"><div><h2 class="card__title" id="t-par-mot">Efetivo paralisado por motivo</h2><p class="card__subtitle">Hhora no período</p></div></div>
              <div id="par-motivo"></div>
            </section>
            <section class="card" aria-labelledby="t-par-resp">
              <div class="card__header"><div><h2 class="card__title" id="t-par-resp">Efetivo paralisado por responsabilidade</h2><p class="card__subtitle">Cliente, gerenciadora e terceiros: tempo potencialmente excusável (base de pleito no 03)</p></div></div>
              <div id="par-resp"></div>
            </section>
          </div>
          <section class="card card--flush mt-4" aria-labelledby="t-paral">
            <div class="card__header"><div><h2 class="card__title" id="t-paral">Registros de paralisação</h2><p class="card__subtitle" id="sub-paral"></p></div>
              <button type="button" class="btn btn--primary" id="btn-paralisacao"><i data-icon="plus"></i>Registrar paralisação</button></div>
            <div id="tb-paral"></div>
          </section>
        </div>
      </section>

      <section class="tab-panel" role="tabpanel" id="p-kpis" aria-labelledby="aba-kpis" hidden>
        <p class="text-small text-muted mb-4" id="janela"></p>
        <h2 class="section-title" id="t-perf">Performance geral</h2>
        <div class="kpi-grid kpi-grid--compacto" id="kpis-perf"></div>
        <div class="kpi-grid kpi-grid--compacto mt-4" id="kpis-perf-campo"></div>
        <section class="card card--flush mt-6" aria-labelledby="t-empresas">
          <div class="card__header"><div><h2 class="card__title" id="t-empresas">Performance por empresa</h2><p class="card__subtitle">Indicadores na janela de avaliação; alerta em laranja, atenção em areia</p></div></div>
          <div id="tb-empresas"></div>
        </section>
        <div class="grid grid--2 mt-4">
          <section class="card" aria-labelledby="t-g-pf">
            <div class="card__header"><div><h2 class="card__title" id="t-g-pf">Fator de produtividade por semana</h2><p class="card__subtitle">HH apropriadas ÷ HH ganhas (1,00 = índice orçado; acima é pior)</p></div></div>
            <div class="chart"><canvas id="g-pf"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-g-ader">
            <div class="card__header"><div><h2 class="card__title" id="t-g-ader">Aderência semanal</h2><p class="card__subtitle">Realizado ÷ previsto da LB, em HH ganhas (limitado a 100% por item)</p></div></div>
            <div class="chart"><canvas id="g-ader"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-g-trab">
            <div class="card__header"><div><h2 class="card__title" id="t-g-trab">Pessoas trabalhando por semana</h2><p class="card__subtitle">% na amostragem do trabalho</p></div></div>
            <div class="chart"><canvas id="g-trab"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-g-cp">
            <div class="card__header"><div><h2 class="card__title" id="t-g-cp">Capacidade produtiva por semana</h2><p class="card__subtitle">Horas de execução por dia na frente de serviço (média)</p></div></div>
            <div class="chart"><canvas id="g-cp"></canvas></div>
          </section>
        </div>
        <section class="card mt-4" aria-labelledby="t-defs">
          <div class="card__header"><div><h2 class="card__title" id="t-defs">Como os indicadores são calculados</h2></div></div>
          <dl class="dl" id="definicoes"></dl>
        </section>
      </section>
""" },

  { "modulo": "planejamento", "tela": "punch-list", "titulo": "Punch list", "graficos": True, "extras": ["js/components/importar.js"],
    "subtitulo": "Pendências de completação mecânica e comissionamento por sistema.",
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo item</button>'
             '<button type="button" class="btn btn--secondary" id="btn-importar"><i data-icon="upload"></i>Importar Excel</button>' + EXPORT,
    "corpo": """      <div class="tabs" data-tabs role="tablist" aria-label="Visões da Punch list">
        <button type="button" class="tab" role="tab" id="aba-lista" aria-controls="p-lista" aria-selected="true"><i data-icon="list"></i>Lista</button>
        <button type="button" class="tab" role="tab" id="aba-painel" aria-controls="p-painel" aria-selected="false"><i data-icon="dashboard"></i>Painel</button>
      </div>
      <section class="tab-panel" role="tabpanel" id="p-lista" aria-labelledby="aba-lista">
        <div class="kpi-grid" id="kpis"></div>
        <div class="toolbar mt-6">
          <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar número, descrição ou TAG" aria-label="Buscar itens"></div>
          <button type="button" class="btn btn--secondary" id="btn-filtros"><i data-icon="filter"></i>Filtros</button>
        </div>
        <div class="filter-bar mb-4" id="chips"></div>
        <section class="card card--flush" aria-labelledby="t-lista">
          <div class="card__header"><div><h2 class="card__title" id="t-lista">Itens</h2><p class="card__subtitle" id="contagem"></p></div></div>
          <div id="tabela"></div>
        </section>
      </section>
      <section class="tab-panel" role="tabpanel" id="p-painel" aria-labelledby="aba-painel" hidden>
        <div class="alert alert--warning mb-4" id="alerta-bloqueio" hidden></div>
        <div class="grid grid--2">
          <section class="card" aria-labelledby="t-burn">
            <div class="card__header"><div><h2 class="card__title" id="t-burn">Abertura e fechamento acumulados</h2><p class="card__subtitle">Por semana (burndown)</p></div></div>
            <div class="chart"><canvas id="g-burn"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-aging">
            <div class="card__header"><div><h2 class="card__title" id="t-aging">Tempo em aberto</h2><p class="card__subtitle">Itens abertos por faixa de idade e categoria</p></div></div>
            <div class="chart"><canvas id="g-aging"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-disc">
            <div class="card__header"><div><h2 class="card__title" id="t-disc">Abertos por disciplina</h2><p class="card__subtitle">Por categoria</p></div></div>
            <div class="chart"><canvas id="g-disc"></canvas></div>
          </section>
          <section class="card" aria-labelledby="t-emp">
            <div class="card__header"><div><h2 class="card__title" id="t-emp">Abertos por empresa</h2><p class="card__subtitle">Por categoria</p></div></div>
            <div class="chart"><canvas id="g-emp"></canvas></div>
          </section>
        </div>
        <section class="card card--flush mt-4" aria-labelledby="t-sis">
          <div class="card__header"><div><h2 class="card__title" id="t-sis">Sistemas e liberação por marco</h2><p class="card__subtitle">Sistema com item A aberto fica bloqueado para o marco vinculado</p></div></div>
          <div id="tb-sistemas"></div>
        </section>
      </section>
""" },
]
