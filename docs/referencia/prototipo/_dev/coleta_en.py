# Coleta textos não traduzidos em EN (página + modais abertos por botões e abas)
import sys, re, json
from playwright.sync_api import sync_playwright
import os
BASE = "file://" + os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
JS = """(raiz) => { const out = new Set(); const root = raiz ? (document.querySelector('.modal:not([hidden]) .modal__dialog') || document.body) : document.body;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const p = n.parentElement; if (!p || p.closest('script,style,textarea,[data-sem-traducao],.app-sidebar')) continue;
    const t = n.nodeValue.replace(/\\s+/g,' ').trim(); if (t) out.add(t); }
  root.querySelectorAll('[aria-label],[title],[placeholder],[data-label]').forEach(el => ['aria-label','title','placeholder','data-label'].forEach(a => { const v = el.getAttribute(a); if (v) out.add(v); }));
  root.querySelectorAll('option').forEach(o => out.add(o.textContent.trim()));
  return [...out]; }"""
PT = re.compile(r"[ãõçáéíóúâêôàÁÉÍÓÚÇ]|\b(de|da|do|das|dos|em|com|para|por|não|sem|até|na|no|nas|nos|ao|mês|dias?|itens|registros?|abert[oa]s?|atrasad[oa]s?|previsto|realizado|Novo|Nova|Buscar|Exportar|Importar|Salvar|Voltar|Filtros?|Cancelar|Selecione|Valor|Data|Contrato|Contratos|Marco|Situação|Tipo|Nota|Orçado|Saldo|Mostrar|Enviar|Fechar|Aplicar|Colunas|Total|Revisão|Remanejar|Pacote|Item|Motivo|Evento|Período)\b")
achados = {}
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("try { localStorage.setItem('gi.idioma','en'); } catch(e) {}")
    pg = ctx.new_page(); erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    def colher(onde, raiz=False):
        for t in pg.evaluate(JS, raiz):
            if PT.search(t): achados.setdefault(t, onde)
    for rel in sys.argv[1].split(","):
        pg.goto(BASE + rel); pg.wait_for_timeout(900); colher(rel)
        tabs = pg.evaluate("() => [...document.querySelectorAll('main [role=tab]')].map((t,i)=>{t.setAttribute('data-scan-tab',i);return i})")
        for i in tabs:
            try: pg.click("[data-scan-tab='%d']" % i, timeout=1500); pg.wait_for_timeout(300); colher(rel + " aba")
            except Exception: pass
        sels = pg.evaluate("() => [...document.querySelectorAll('main button:not([data-exportar]):not([role=tab]):not(.th-sort):not([data-pagina])')].filter(b=>b.offsetParent).map((b,i)=>{ b.setAttribute('data-scan', i); return i; })")
        for i in sels:
            try:
                pg.click("[data-scan='%d']" % i, timeout=1500); pg.wait_for_timeout(400)
                if pg.query_selector(".modal:not([hidden])"):
                    colher(rel + " modal", True)
                    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
                    if pg.query_selector(".modal:not([hidden])"): pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
            except Exception as ex: pass
    b.close()
for t, o in achados.items(): print(o, "|", t[:160])
print("ERROS", erros)
