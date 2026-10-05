from telas import EXPORT

EXTRAS = ["js/pages/riscos/riscos.js"]

def aval(padrao="residual"):
    return ("""        <div class="segmented" data-segmented id="f-aval" role="group" aria-label="Avaliação exibida">
          <button type="button" class="segmented__opt" aria-pressed="%s" data-value="inerente">Inerente</button>
          <button type="button" class="segmented__opt" aria-pressed="%s" data-value="residual">Residual</button>
        </div>
""" % ("true" if padrao == "inerente" else "false", "true" if padrao == "residual" else "false"))

SPECS = [
  { "modulo": "riscos", "tela": "registro", "titulo": "Registro de riscos", "extras": EXTRAS,
    "acoes": '<button type="button" class="btn btn--primary" id="btn-novo"><i data-icon="plus"></i>Novo risco</button>'
             '<a class="btn btn--secondary" id="lnk-matriz" href="matriz.html"><i data-icon="matrix"></i>Matriz 5x5</a>' + EXPORT,
    "corpo": """      <div class="toolbar">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar por número, título, causa ou dono" aria-label="Buscar riscos"></div>
        <button type="button" class="btn btn--secondary" id="btn-filtros"><i data-icon="filter"></i>Filtros</button>
""" + aval() + """        <button type="button" class="btn btn--ghost" id="btn-atualizar" title="Refaz a consulta com os filtros atuais"><i data-icon="refresh"></i>Atualizar</button>
      </div>
      <div id="contexto"></div>
      <div class="kpi-grid" id="kpis"></div>
      <div id="aviso" class="mt-4"></div>
      <div class="filter-bar mt-4" id="chips"></div>
      <section class="card card--flush mt-4" aria-labelledby="t-reg">
        <div class="card__header"><div><h2 class="card__title" id="t-reg">Registro de riscos</h2><p class="card__subtitle" id="contagem"></p></div>
          <button type="button" class="btn btn--ghost btn--sm" id="btn-colunas"><i data-icon="columns"></i>Colunas</button></div>
        <div id="tabela" class="tabela-riscos"></div>
      </section>
""" },

  { "modulo": "riscos", "tela": "matriz", "titulo": "Matriz de riscos 5x5", "extras": EXTRAS,
    "acoes": '<a class="btn btn--secondary" id="lnk-registro" href="registro.html"><i data-icon="list"></i>Registro</a>' + EXPORT,
    "corpo": """      <div class="toolbar">
""" + aval() + """        <label class="sr-only" for="f-natureza">Natureza</label>
        <select class="select" id="f-natureza">
          <option value="">Natureza: todas</option>
          <option value="Ameaça">Somente ameaças</option>
          <option value="Oportunidade">Somente oportunidades</option>
        </select>
      </div>
      <div id="contexto"></div>
      <div class="grid grid--sidebar">
        <section class="card" aria-labelledby="t-mat">
          <div class="card__header"><div><h2 class="card__title" id="t-mat">Distribuição por probabilidade e impacto</h2>
            <p class="card__subtitle" id="sub-mat"></p></div></div>
          <p class="text-small text-muted mb-4">Cada célula mostra a quantidade de riscos e os números. Clique na célula para abrir o registro já filtrado.</p>
          <div id="matriz"></div>
          <div class="mt-4" id="legenda"></div>
          <p class="text-small text-muted" id="nota-mat"></p>
        </section>
        <section class="card" aria-labelledby="t-mov">
          <div class="card__header"><div><h2 class="card__title" id="t-mov">Movimentação inerente para residual</h2>
            <p class="card__subtitle">Eficácia do plano de resposta</p></div></div>
          <div id="mov"></div>
          <p class="text-small text-muted mt-4" id="nota-mov"></p>
        </section>
      </div>
""" },

  { "modulo": "riscos", "tela": "ficha", "titulo": "Ficha do risco", "extras": EXTRAS,
    "voltar": ("registro.html", "Voltar para Registro"),
    "acoes": EXPORT,
    "corpo": """      <div id="ficha"></div>
""" },

  { "modulo": "riscos", "tela": "painel", "titulo": "Painel de riscos", "graficos": True, "extras": ["js/components/analise.js"] + EXTRAS,
    "acoes": '<button type="button" class="btn btn--secondary" data-analise="riscos"><i data-icon="clipboardList"></i>Análise do período</button>' + '<a class="btn btn--secondary" id="lnk-registro" href="registro.html"><i data-icon="list"></i>Registro</a>' + EXPORT,
    "corpo": """      <p class="text-small text-muted mb-4" id="escopo"></p>
      <div class="kpi-grid" id="kpis"></div>
      <div class="grid grid--2 mt-6">
        <section class="card" aria-labelledby="t-cat">
          <div class="card__header"><div><h2 class="card__title" id="t-cat">Exposição por categoria (RBS)</h2>
            <p class="card__subtitle">Soma do score residual das ameaças ativas; clique para abrir o registro filtrado</p></div></div>
          <div id="categorias"></div>
        </section>
        <section class="card" aria-labelledby="t-evo">
          <div class="card__header"><div><h2 class="card__title" id="t-evo">Evolução da exposição total</h2>
            <p class="card__subtitle">Score residual somado das ameaças, por mês (fotografia mensal; mês corrente recalculado)</p></div></div>
          <div class="chart"><canvas id="g-evolucao"></canvas></div>
        </section>
      </div>
      <section class="card card--flush mt-4" aria-labelledby="t-pauta">
        <div class="card__header"><div><h2 class="card__title" id="t-pauta">Pauta de escalonamento</h2>
          <p class="card__subtitle" id="sub-pauta"></p></div>
          <button type="button" class="btn btn--secondary btn--sm" id="btn-email"><i data-icon="mail"></i>Enviar por e-mail</button></div>
        <div id="pauta"></div>
      </section>
""" },
]
