# _dev: ferramentas de desenvolvimento

Não fazem parte do protótipo (nenhuma tela carrega estes arquivos). Precisam de Python 3 e, para os testes, do Playwright com Chromium (`pip install playwright` e `playwright install chromium`).

| Arquivo | Uso |
|---|---|
| `telas.py` | Gerador das páginas completas. `python3 telas.py specs_01.py specs_02.py specs_03.py specs_04.py specs_05.py specs_06.py specs_07.py specs_08.py specs_config.py` reescreve as HTML dos módulos descritos (cabeçalho, barra da página, corpo e scripts) |
| `specs_01.py` a `specs_08.py`, `specs_config.py` | Descrição das telas de cada módulo e de Configurações > Parâmetros (título, ações da barra, corpo, gráficos, scripts extras) |
| `crawl.py` | Abre todas as páginas (inclusive `relatorio.html`) em 360 e 1440px e aponta erros de console, links quebrados, botões fora do formato pílula e rolagem horizontal |
| `t_pag.py` | Teste de uma página com roteiro de ações: `python3 t_pag.py "file:///.../modulos/x/y.html" 1440 /tmp/gi-shots/y "click=#btn;;shot=a"` |
| `coleta_en.py` | Em inglês, abre as páginas, abas e modais e lista os textos ainda em português: `python3 coleta_en.py "modulos/x/y.html,modulos/x/z.html"` |

Os caminhos são relativos: a raiz do protótipo é a pasta acima de `_dev`.
