import os, glob, json, sys
QS = sys.argv[1] if len(sys.argv) > 1 else ""  # ex.: "?projeto=2" (escopo); sem argumento, escopo padrão (Portfólio)
from urllib.parse import urlparse, unquote
from playwright.sync_api import sync_playwright
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
paginas = [os.path.join(RAIZ, "index.html"), os.path.join(RAIZ, "styleguide.html"), os.path.join(RAIZ, "relatorio.html")] + sorted(glob.glob(RAIZ + "/modulos/**/*.html", recursive=True))
quebrados, erros, sem_ativo, resultados = [], [], [], {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (360, 768, 1440):
        pg = b.new_page(viewport={"width": w, "height": 850})
        msgs = []
        pg.on("pageerror", lambda e: msgs.append(("pageerror", str(e))))
        pg.on("console", lambda m: msgs.append((m.type, m.text)) if m.type in ("error", "warning") else None)
        pg.on("requestfailed", lambda r: msgs.append(("reqfail", r.url)))
        for arq in paginas:
            msgs.clear()
            pg.goto("file://" + arq + QS); pg.wait_for_timeout(250)
            info = pg.evaluate("""() => {
              const de = document.documentElement;
              const btns = [...document.querySelectorAll('button, .btn')];
              return {
                hrefs: [...document.querySelectorAll('a[href]')].map(a => a.href),
                overflow: de.scrollWidth > de.clientWidth,
                notPill: btns.filter(b => parseFloat(getComputedStyle(b).borderTopLeftRadius) < 999).length,
                ativo: !!document.querySelector('.app-sidebar .is-active'),
                contexto: (document.querySelector('.app-header__context') || {}).textContent || '',
                abas: document.querySelectorAll('[data-module-tabs] .tab').length,
                iconesPendentes: document.querySelectorAll('i[data-icon]').length
              };
            }""")
            rel = os.path.relpath(arq, RAIZ)
            for h in info["hrefs"]:
                u = urlparse(h)
                if u.scheme == "file":
                    alvo = unquote(u.path)
                    if not os.path.exists(alvo): quebrados.append((rel, h))
            if info["overflow"] or info["notPill"] or info["iconesPendentes"]:
                erros.append((w, rel, info["overflow"], info["notPill"], info["iconesPendentes"]))
            for m in msgs: erros.append((w, rel, m))
            if w == 1440: resultados[rel] = (info["ativo"], info["contexto"], info["abas"])
        pg.close()
    b.close()
print("paginas", len(paginas))
print("links quebrados", quebrados)
print("problemas", erros)
for k, v in resultados.items():
    if not v[0] or not v[1]: print("SEM ATIVO/CONTEXTO", k, v)
print(json.dumps({k: v for k, v in list(resultados.items())[:6]}, ensure_ascii=False))
