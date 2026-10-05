# Gerador das telas completas (etapa 5). Cada tela: cabeçalho, abas do módulo,
# corpo (contêineres) e scripts. O conteúdo é montado pelo JS da tela.
import os, html, importlib.util, sys, glob

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do protótipo (pasta acima de _dev)
MODULOS = {
  "central-acoes": ("01", "Central de Ações", "actions"),
  "planejamento": ("02", "Planejamento", "curve"),
  "financeiro": ("03", "Gestão Financeira", "money"),
  "suprimentos": ("04", "Suprimentos", "cart"),
  "riscos": ("05", "Gestão de Riscos", "alertTriangle"),
  "qualidade": ("06", "Gestão da Qualidade", "shieldCheck"),
  "hse": ("07", "HSE", "hardHat"),
  "governanca": ("08", "Governança", "landmark"),
  "configuracoes": ("", "Configurações", "sliders"),
}
I18N = ["js/i18n.js", "js/i18n/en.js", "js/siglas.js"]
DADOS = ["data/mock-config.js", "data/mock-base.js", "data/mock-central.js", "data/mock-planejamento.js",
  "data/mock-financeiro.js", "data/mock-suprimentos.js", "data/mock-riscos.js", "data/mock-qualidade.js",
  "data/mock-hse.js", "data/mock-governanca.js", "data/mock-portfolio.js", "js/services/regras.js", "js/services/api.js"]
COMPONENTES = ["js/components/icons.js", "js/components/ui.js", "js/components/modal.js", "js/components/comum.js",
  "js/components/tabela.js", "js/components/exportar.js", "js/components/formulario.js", "js/components/upload.js"]

def e(t): return html.escape(t, quote=True)

def pagina(s):
    mod, tela = s["modulo"], s["tela"]
    num, nome, ic = MODULOS[mod]
    root = "../../"
    eyebrow = (num + " " if num else "") + nome
    graficos = s.get("graficos", False)
    scripts = [root + x for x in I18N] + [root + x for x in DADOS]
    if graficos: scripts.append(root + "assets/vendor/chart.umd.min.js")
    scripts += [root + x for x in COMPONENTES]
    if graficos: scripts.append(root + "js/components/charts.js")
    scripts += [root + x for x in s.get("extras", [])]
    scripts.append(root + "js/layout.js")
    scripts.append(root + "js/pages/" + mod + "/" + tela + ".js")
    acoes = s.get("acoes", "")
    if s.get("voltar"):
        esquerda = '<a class="btn btn--secondary" href="%s"><i data-icon="chevronLeft"></i>%s</a>' % (s["voltar"][0], e(s["voltar"][1]))
    else:
        esquerda = '<nav data-module-tabs></nav>'
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(s['titulo'])} · {e(nome)} | Gestão Integrada AMT</title>
  <link rel="icon" type="image/png" href="{root}assets/logos/timenow-icone.png">
  <link rel="stylesheet" href="{root}css/fonts.css">
  <link rel="stylesheet" href="{root}css/tokens.css">
  <link rel="stylesheet" href="{root}css/layout.css">
  <link rel="stylesheet" href="{root}css/components.css">
</head>
<body data-root="{root}" data-page="{mod}/{tela}">
<div class="app">
  <main class="app-main" id="conteudo">
    <div class="container">

      <h1 class="sr-only" id="titulo">{e(s['titulo'])}</h1>
      <div class="page-bar">
        {esquerda}
        <div class="page-actions" id="acoes-pagina">{acoes}</div>
      </div>

{s['corpo'].rstrip()}

    </div>
  </main>
</div>

""" + "\n".join('<script src="%s"></script>' % x for x in scripts) + "\n</body>\n</html>\n"

EXPORT = ('<button type="button" class="btn btn--secondary" data-exportar="excel" title="Exportar Excel"><i data-icon="fileSheet"></i><span><span class="btn__prefixo">Exportar </span>Excel</span></button>'
          '<button type="button" class="btn btn--secondary" data-exportar="pdf" title="Exportar PDF"><i data-icon="filePdf"></i><span><span class="btn__prefixo">Exportar </span>PDF</span></button>')

def gerar(specs):
    for s in specs:
        rel = f"modulos/{s['modulo']}/{s['tela']}.html"
        open(os.path.join(RAIZ, rel), "w", encoding="utf-8").write(pagina(s))
        print("gerada", rel)

if __name__ == "__main__":
    # python3 telas.py specs_01.py [specs_02.py ...]
    for arq in sys.argv[1:]:
        sp = importlib.util.spec_from_file_location("m", arq); m = importlib.util.module_from_spec(sp)
        sys.modules["telas"] = sys.modules[__name__]
        sp.loader.exec_module(m)
        gerar(m.SPECS)
