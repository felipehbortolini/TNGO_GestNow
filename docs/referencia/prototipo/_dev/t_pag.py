import sys, json, os
os.makedirs("/tmp/gi-shots", exist_ok=True)
from playwright.sync_api import sync_playwright
url = sys.argv[1]; w = int(sys.argv[2]) if len(sys.argv) > 2 else 1440; out = sys.argv[3] if len(sys.argv) > 3 else "/tmp/gi-shots/pag"
acoes = sys.argv[4] if len(sys.argv) > 4 else ""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": w, "height": 900}, accept_downloads=True)
    msgs = []
    pg.on("console", lambda m: msgs.append((m.type, m.text)) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: msgs.append(("pageerror", str(e))))
    pg.on("requestfailed", lambda r: msgs.append(("reqfail", r.url)))
    pg.goto(url); pg.wait_for_timeout(700)
    for a in [x for x in acoes.split(";;") if x]:
        tipo, arg = a.split("=", 1)
        if tipo == "click": pg.click(arg); pg.wait_for_timeout(500)
        elif tipo == "shot": pg.screenshot(path=out + "-" + arg + ".png", full_page=True)
        elif tipo == "vshot": pg.screenshot(path=out + "-" + arg + ".png")
        elif tipo == "fill":
            sel, val = arg.split("|", 1); pg.fill(sel, val); pg.wait_for_timeout(300)
        elif tipo == "eval": print("EVAL", pg.evaluate(arg))
        elif tipo == "select":
            sel, val = arg.split("|", 1); pg.select_option(sel, val); pg.wait_for_timeout(200)
        elif tipo == "goto": pg.goto(arg); pg.wait_for_timeout(700)
        elif tipo == "upload":
            sel, path = arg.split("|", 1); pg.set_input_files(sel, path); pg.wait_for_timeout(1500)
        elif tipo == "download":
            with pg.expect_download(timeout=20000) as d: pg.click(arg)
            print("DOWNLOAD", d.value.suggested_filename); d.value.save_as("/tmp/gi-shots/" + d.value.suggested_filename)
        elif tipo == "wait": pg.wait_for_timeout(int(arg))
        elif tipo == "key": pg.keyboard.press(arg); pg.wait_for_timeout(300)
    info = pg.evaluate("""() => { const de = document.documentElement; const btns=[...document.querySelectorAll('button, .btn')];
      return { overflow: de.scrollWidth > de.clientWidth, notPill: btns.filter(b => parseFloat(getComputedStyle(b).borderTopLeftRadius) < 999).map(b=>b.outerHTML.slice(0,80)),
      pend: document.querySelectorAll('i[data-icon]').length } }""")
    print(json.dumps(info, ensure_ascii=False))
    for m in msgs: print("MSG", m)
    pg.screenshot(path=out + ".png", full_page=True)
    b.close()
