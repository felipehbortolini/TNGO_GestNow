from telas import EXPORT

SPECS = [
  { "modulo": "configuracoes", "tela": "parametros", "titulo": "Parâmetros do sistema",
    "acoes": '<button type="button" class="btn btn--secondary" id="btn-historico"><i data-icon="history"></i>Histórico de versões</button>' + EXPORT,
    "corpo": """      <div class="alert alert--info mb-4">
        <i data-icon="info"></i>
        <div class="alert__body"><b>Acesso restrito a Gestor e Admin.</b> Cada alteração cria uma nova versão com data de vigência, autor e justificativa. Pesos e prazos valem para registros novos; registros já calculados (avaliações, prazos de ocorrências) guardam os parâmetros da época. Critérios de exibição (base das taxas, escala de severidade, faixas) recalculam as telas na hora.</div>
      </div>
      <div id="acesso"></div>
      <section class="card mb-4" aria-labelledby="t-versao">
        <div class="card__header"><div><h2 class="card__title" id="t-versao">Versão vigente</h2><p class="card__subtitle" id="sub-versao"></p></div></div>
        <div class="form-grid" id="versao"></div>
      </section>
      <div class="toolbar">
        <div class="toolbar__search input-icon"><i data-icon="search"></i><input class="input input--pill" type="search" id="busca" placeholder="Buscar parâmetro" aria-label="Buscar parâmetro"></div>
        <label class="sr-only" for="f-modulo">Módulo</label>
        <select class="select" id="f-modulo"></select>
      </div>
      <div class="grid grid--2" id="grupos"></div>
""" },
]
