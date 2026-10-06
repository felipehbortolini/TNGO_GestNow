"""Excel in and Excel out — the model, the reading and the report.

Three jobs, one file because they share a single truth: the column
contract. If the template changes here, the reader and the export change
with it, and there is no second place to forget.

**Reading** is forgiving about presentation and strict about meaning:
accents, casing and column order are normalised; missing data, unknown
registers and inconsistent day sums are reported line by line so the
person fixes the spreadsheet once instead of five times.

**Writing** produces a workbook someone can actually work in — frozen
panes, filters, number formats, a totals row, PPC coloured by band and
page setup that prints. A dump of raw rows is not an export.
"""

from __future__ import annotations

import unicodedata
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from src.core import calculos, semanas

# ── Contrato de colunas do modelo ───────────────────────────────────────

COLUNAS_MODELO = (
    "Item",
    "Semana",
    "ID Exclusiva",
    "Atividade Detalhada",
    "Local",
    "Empresa",
    "Fiscal",
    "Encarregado",
    "Prod. Prevista",
    "Unidade",
    "Prev/Real",
    "2ª",
    "3ª",
    "4ª",
    "5ª",
    "6ª",
    "Sáb",
    "Dom",
)

PRIMEIRO_DIA = 11
OBRIGATORIAS = (
    "Semana",
    "ID Exclusiva",
    "Atividade Detalhada",
    "Local",
    "Empresa",
    "Encarregado",
    "Prod. Prevista",
    "Unidade",
)

# ── Paleta (espelha os tokens do Design System) ─────────────────────────

VERDE = "006457"
VERDE_CLARO = "E6F8F4"
CINZA_LINHA = "F5FAFB"
BRANCO = "FFFFFF"
TEXTO = "2A2A2A"
BORDA = "DEE2E6"

OK = "DDF8F0"
ATENCAO = "FDF8E5"
ERRO = "FAEBEB"

_FONTE_CABECALHO = Font(bold=True, color=BRANCO, size=10, name="Segoe UI")
_FUNDO_CABECALHO = PatternFill("solid", fgColor=VERDE)
_FONTE_TITULO = Font(bold=True, size=14, color=VERDE, name="Segoe UI")
_FONTE_ROTULO = Font(bold=True, size=9, color="767676", name="Segoe UI")
_FONTE_CORPO = Font(size=10, name="Segoe UI")
_FONTE_TOTAL = Font(bold=True, size=10, color=TEXTO, name="Segoe UI")
_CENTRO = Alignment(horizontal="center", vertical="center")
_ESQUERDA = Alignment(horizontal="left", vertical="center", wrap_text=True)
_LINHA_FINA = Side(style="thin", color=BORDA)
_GRADE = Border(left=_LINHA_FINA, right=_LINHA_FINA, top=_LINHA_FINA, bottom=_LINHA_FINA)


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn").strip().lower()


def _numero(valor) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    convertido = calculos.numero(texto, padrao=float("nan"))
    return None if convertido != convertido else convertido


# ── Estilo ──────────────────────────────────────────────────────────────


def _cabecalho(aba: Worksheet, titulos, linha: int = 1, largura: dict | None = None) -> None:
    for coluna, titulo in enumerate(titulos, start=1):
        celula = aba.cell(row=linha, column=coluna, value=titulo)
        celula.font = _FONTE_CABECALHO
        celula.fill = _FUNDO_CABECALHO
        celula.alignment = _CENTRO
        celula.border = _GRADE
    aba.row_dimensions[linha].height = 26
    for coluna, titulo in enumerate(titulos, start=1):
        letra = get_column_letter(coluna)
        aba.column_dimensions[letra].width = (largura or {}).get(titulo, 14)


def _zebrar(aba: Worksheet, primeira: int, ultima: int, colunas: int) -> None:
    fundo = PatternFill("solid", fgColor=CINZA_LINHA)
    for linha in range(primeira, ultima + 1):
        for coluna in range(1, colunas + 1):
            celula = aba.cell(row=linha, column=coluna)
            celula.border = _GRADE
            if not celula.font or celula.font.size is None:
                celula.font = _FONTE_CORPO
            if (linha - primeira) % 2:
                celula.fill = fundo


def _preparar_impressao(aba: Worksheet, *, paisagem: bool = True) -> None:
    """Page setup, so the sheet prints as a report and not as a wall."""
    aba.page_setup.orientation = "landscape" if paisagem else "portrait"
    aba.page_setup.fitToWidth = 1
    aba.page_setup.fitToHeight = 0
    # Atribuir o objeto inteiro, e não o atributo: `pageSetUpPr` nasce
    # None numa aba recém-criada, e mexer no atributo dele estouraria.
    aba.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    aba.print_title_rows = "1:1"


# ── Modelo para download ────────────────────────────────────────────────


def gerar_modelo(semana: str, cadastros: dict) -> bytes:
    """The blank template, with the registers embedded as a cheat sheet."""
    wb = Workbook()
    aba = wb.active
    aba.title = "Programacao"

    largura = {
        "Atividade Detalhada": 42,
        "Local": 20,
        "Empresa": 18,
        "Fiscal": 18,
        "Encarregado": 22,
        "ID Exclusiva": 16,
        "Prod. Prevista": 14,
        "Prev/Real": 11,
        "Item": 7,
        "Semana": 12,
    }
    _cabecalho(aba, COLUNAS_MODELO, largura=largura)

    exemplo_prev = [
        "01",
        semana,
        "PS1-ARM-015",
        "Armação das paredes (exemplo — apague esta linha)",
        (cadastros.get("locais") or ["Potato Storage 1"])[0],
        (cadastros.get("empresas") or ["M. Roscoe"])[0],
        (cadastros.get("fiscais") or [""])[0],
        (cadastros.get("encarregados") or ["Encarregado"])[0],
        1000,
        (cadastros.get("unidades") or ["kg"])[0],
        "Prev.",
        180,
        170,
        170,
        160,
        150,
        110,
        60,
    ]
    exemplo_real = [
        "",
        semana,
        "PS1-ARM-015",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "Real.",
        150,
        160,
        120,
        140,
        130,
        0,
        0,
    ]
    aba.append(exemplo_prev)
    aba.append(exemplo_real)
    _zebrar(aba, 2, 3, len(COLUNAS_MODELO))
    aba.freeze_panes = "D2"
    _preparar_impressao(aba)

    ajuda = wb.create_sheet("Como preencher")
    ajuda.column_dimensions["A"].width = 26
    ajuda.column_dimensions["B"].width = 90
    ajuda["A1"] = "Programação Semanal — instruções"
    ajuda["A1"].font = _FONTE_TITULO
    instrucoes = [
        (
            "Uma atividade = duas linhas",
            "A primeira traz Prev. (o que será programado); a segunda, Real. (o que foi executado). A linha Real. é opcional na importação.",
        ),
        ("Semana", f"No formato {semana}. A semana precisa estar liberada para a empresa."),
        ("ID Exclusiva", "Não pode repetir dentro da mesma semana."),
        ("Prod. Prevista", "Precisa bater com a soma dos sete dias, com tolerância de 0,5."),
        (
            "Local, Empresa, Unidade",
            "Precisam existir nos cadastros do sistema — a lista está na aba “Listas válidas”.",
        ),
        ("Colunas", "Não renomeie, não reordene e não insira colunas."),
        ("Números", "Vírgula ou ponto decimal, tanto faz. Deixe vazio o dia sem produção."),
    ]
    for linha, (rotulo, texto) in enumerate(instrucoes, start=3):
        ajuda.cell(row=linha, column=1, value=rotulo).font = _FONTE_ROTULO
        celula = ajuda.cell(row=linha, column=2, value=texto)
        celula.alignment = _ESQUERDA
        celula.font = _FONTE_CORPO

    listas = wb.create_sheet("Listas válidas")
    nomes = ("locais", "empresas", "unidades", "fiscais", "encarregados")
    _cabecalho(
        listas,
        [n.capitalize() for n in nomes],
        largura=dict.fromkeys([n.capitalize() for n in nomes], 24),
    )
    for coluna, nome in enumerate(nomes, start=1):
        for linha, valor in enumerate(cadastros.get(nome) or [], start=2):
            celula = listas.cell(row=linha, column=coluna, value=valor)
            celula.font = _FONTE_CORPO
            celula.border = _GRADE

    return _bytes(wb)


# ── Leitura ─────────────────────────────────────────────────────────────


def _cabecalho_valido(linha) -> bool:
    if not linha or len(linha) < len(COLUNAS_MODELO):
        return False
    return all(
        _sem_acento(linha[i]) == _sem_acento(esperado) for i, esperado in enumerate(COLUNAS_MODELO)
    )


class _Conferencia:
    """Estado da leitura de uma planilha, linha a linha.

    Existe como classe e não como um punhado de variáveis soltas porque a
    conferência precisa lembrar de três coisas entre uma linha e outra: a
    atividade "Prev." corrente, para casar com a "Real." de baixo; as IDs
    já vistas em cada semana, para acusar duplicidade; e as listas
    válidas dos cadastros. Passar isso adiante deixaria toda assinatura
    com cinco parâmetros.
    """

    def __init__(self, cadastros: dict):
        self.validos = {
            nome: {_sem_acento(v) for v in (cadastros.get(nome) or [])}
            for nome in ("locais", "empresas", "unidades", "fiscais", "encarregados")
        }
        self.canonicos = {
            nome: {_sem_acento(v): v for v in (cadastros.get(nome) or [])} for nome in self.validos
        }
        self.linhas: list[dict] = []
        self.erros: list[dict] = []
        self.avisos: list[dict] = []
        self.corrente: dict | None = None
        self.vistos: dict[str, set[str]] = {}

    # -- conversões ---------------------------------------------------
    def _canonico(self, texto: list[str], coluna: str, chave: str) -> str:
        """Devolve o valor exatamente como está no cadastro.

        A pessoa digita "potato storage 1" e o cadastro guarda
        "Potato Storage 1". Gravar o que veio da planilha criaria um
        segundo valor que não casa com nenhum filtro.
        """
        valor = texto[COLUNAS_MODELO.index(coluna)]
        return self.canonicos[chave].get(_sem_acento(valor), valor)

    # -- validação de uma linha "Prev." -------------------------------
    def _obrigatorios(self, texto: list[str]) -> list[tuple[str, str]]:
        return [
            (coluna, f"{coluna} não pode ficar em branco.")
            for posicao, coluna in enumerate(COLUNAS_MODELO)
            if coluna in OBRIGATORIAS and not texto[posicao]
        ]

    def _do_cadastro(self, texto: list[str]) -> list[tuple[str, str]]:
        recusas = []
        for coluna, chave in (
            ("Local", "locais"),
            ("Empresa", "empresas"),
            ("Unidade", "unidades"),
            ("Fiscal", "fiscais"),
        ):
            valor = texto[COLUNAS_MODELO.index(coluna)]
            if valor and _sem_acento(valor) not in self.validos[chave]:
                recusas.append((coluna, f"“{valor}” não está no cadastro de {chave}."))
        return recusas

    @staticmethod
    def _quantidades(prevista: float | None, dias: list[float]) -> list[tuple[str, str]]:
        recusas = []
        if prevista is None:
            recusas.append(("Prod. Prevista", "Produção prevista precisa ser um número."))
        elif prevista <= 0:
            recusas.append(("Prod. Prevista", "Produção prevista precisa ser maior que zero."))

        soma = round(sum(dias), 2)
        if soma <= 0:
            recusas.append(("Programação diária", "Distribua a produção ao longo dos sete dias."))
        elif prevista is not None and abs(soma - prevista) > 0.51:
            recusas.append(
                (
                    "Programação diária",
                    f"A soma dos dias ({soma:g}) não bate com a produção prevista ({prevista:g}).",
                )
            )
        return recusas

    def _identificacao(self, texto: list[str]) -> list[tuple[str, str]]:
        semana, id_exclusiva = texto[1], texto[2]
        recusas = []
        if semana and not semanas.inicio(semana):
            recusas.append(
                ("Semana", f"“{semana}” não é uma semana válida. Use o formato S.30/2026.")
            )
        if semana and id_exclusiva:
            ja_vistos = self.vistos.setdefault(semana, set())
            if id_exclusiva in ja_vistos:
                recusas.append(
                    (
                        "ID Exclusiva",
                        f"“{id_exclusiva}” aparece duas vezes na semana {semana}.",
                    )
                )
            ja_vistos.add(id_exclusiva)
        return recusas

    def _conferir(
        self, texto: list[str], prevista: float | None, dias: list[float], numero_linha: int
    ) -> list[dict]:
        """Four passes over one row: filled in, known, adds up, unique."""
        recusas = [
            *self._obrigatorios(texto),
            *self._identificacao(texto),
            *self._do_cadastro(texto),
            *self._quantidades(prevista, dias),
        ]
        return [
            {"linha": numero_linha, "campo": campo, "mensagem": mensagem}
            for campo, mensagem in recusas
        ]

    # -- os três tipos de linha ---------------------------------------
    def previsto(
        self, texto: list[str], prevista: float | None, dias: list[float], numero_linha: int
    ) -> None:
        recusas = self._conferir(texto, prevista, dias, numero_linha)
        self.corrente = {
            "linha_previsto": numero_linha,
            "linha_realizado": None,
            "semana": texto[1],
            "id_exclusiva": texto[2],
            "atividade": texto[3],
            "local": self._canonico(texto, "Local", "locais"),
            "empresa": self._canonico(texto, "Empresa", "empresas"),
            "responsavel": self._canonico(texto, "Fiscal", "fiscais"),
            "encarregado": self._canonico(texto, "Encarregado", "encarregados"),
            "prod_prevista": prevista if prevista is not None else 0.0,
            "unidade": self._canonico(texto, "Unidade", "unidades"),
            "dias_previsto": dias,
            "dias_realizado": [0.0] * calculos.NUM_DIAS,
            "erros": [r["mensagem"] for r in recusas],
            "valida": not recusas,
        }
        self.linhas.append(self.corrente)
        self.erros.extend(recusas)

    def realizado(self, texto: list[str], dias: list[float], numero_linha: int) -> None:
        if self.corrente and self.corrente["id_exclusiva"] == texto[2]:
            self.corrente["dias_realizado"] = dias
            self.corrente["linha_realizado"] = numero_linha
            return
        self.avisos.append(
            {
                "linha": numero_linha,
                "mensagem": (
                    "Linha “Real.” sem a linha “Prev.” correspondente logo acima — ignorada."
                ),
            }
        )

    def ignorada(self, texto: list[str], numero_linha: int) -> None:
        self.avisos.append(
            {
                "linha": numero_linha,
                "mensagem": (
                    f"A coluna Prev/Real traz “{texto[10]}”. Use Prev. ou Real. — linha ignorada."
                ),
            }
        )


def _fatal(mensagem: str, avisos: list[dict] | None = None) -> dict:
    return {"linhas": [], "erros": [], "avisos": avisos or [], "fatal": mensagem}


def _abrir(conteudo: bytes) -> list[tuple] | None:
    """Every row of the first sheet, or None when the file is not one."""
    try:
        wb = load_workbook(BytesIO(conteudo), read_only=True, data_only=True)
    except Exception:  # arquivo corrompido levanta qualquer coisa
        return None
    aba = wb[wb.sheetnames[0]]
    linhas = list(aba.iter_rows(values_only=True))
    wb.close()
    return linhas


def _localizar_cabecalho(linhas: list[tuple]) -> int | None:
    for i, linha in enumerate(linhas):
        if linha and _sem_acento(linha[0]) == "item" and _cabecalho_valido(linha):
            return i
    return None


def ler_planilha(conteudo: bytes, cadastros: dict) -> dict:
    """Parse and validate an uploaded workbook.

    Returns ``{"linhas": [...], "erros": [...], "avisos": [...], "fatal": str}``
    where every entry carries the spreadsheet row number, so the person can
    jump straight to the cell that is wrong.
    """
    conteudo_linhas = _abrir(conteudo)
    if conteudo_linhas is None:
        return _fatal("O arquivo não é uma planilha .xlsx válida. Baixe o modelo e tente de novo.")

    indice = _localizar_cabecalho(conteudo_linhas)
    if indice is None:
        return _fatal(
            "As colunas não estão no padrão do modelo. Baixe o modelo atual, "
            "cole os dados nele e reenvie — não renomeie nem reordene colunas."
        )

    conferencia = _Conferencia(cadastros)

    for deslocamento, bruta in enumerate(conteudo_linhas[indice + 1 :], start=1):
        numero_linha = indice + deslocamento + 1
        if not bruta or not any(str(v or "").strip() for v in bruta):
            continue

        texto = [str(v or "").strip() for v in bruta] + [""] * len(COLUNAS_MODELO)
        dias = [
            (_numero(bruta[i]) if i < len(bruta) else None) or 0.0
            for i in range(PRIMEIRO_DIA, PRIMEIRO_DIA + calculos.NUM_DIAS)
        ]
        tipo = _sem_acento(texto[10])

        if tipo.startswith("real"):
            conferencia.realizado(texto, dias, numero_linha)
        elif tipo.startswith("prev"):
            prevista = _numero(bruta[8]) if len(bruta) > 8 else None
            conferencia.previsto(texto, prevista, dias, numero_linha)
        else:
            conferencia.ignorada(texto, numero_linha)

    if not conferencia.linhas and not conferencia.erros:
        return _fatal("Nenhuma linha “Prev.” encontrada na planilha.", conferencia.avisos)

    return {
        "linhas": conferencia.linhas,
        "erros": conferencia.erros,
        "avisos": conferencia.avisos,
        "fatal": "",
    }


# ── Exportação ──────────────────────────────────────────────────────────


def _bytes(wb: Workbook) -> bytes:
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _aba_capa(
    wb: Workbook,
    semana: str,
    resumo: dict,
    emissao: tuple[str, str],
    identificacao: tuple[str, str],
) -> None:
    aba = wb.create_sheet("Resumo", 0)
    aba.sheet_view.showGridLines = False
    aba.column_dimensions["A"].width = 30
    aba.column_dimensions["B"].width = 26
    aba.column_dimensions["C"].width = 26
    aba.column_dimensions["D"].width = 26

    projeto, cliente = identificacao
    aba["A1"] = projeto or "Programação Semanal de Serviços"
    aba["A1"].font = Font(bold=True, size=18, color=VERDE, name="Segoe UI")
    aba["A2"] = f"{semana} · {semanas.periodo(semana)}"
    if cliente:
        aba["A2"] = f"{aba['A2'].value} · {cliente}"
    aba["A2"].font = Font(size=11, color="767676", name="Segoe UI")
    aba["A3"] = f"Emitido em {emissao[1]} por {emissao[0]}"
    aba["A3"].font = Font(size=9, color="767676", name="Segoe UI")

    indicadores = [
        ("Aderência geral", f"{resumo['aderencia']:.1f}%", f"meta {resumo['meta_aderencia']:.0f}%"),
        ("PPC médio", f"{resumo['ppc_medio']:.1f}%", f"meta {resumo['meta_ppc']:.0f}%"),
        ("Atividades", resumo["total_atividades"], "na semana"),
        ("Contratadas", resumo["empresas_ativas"], "com programação"),
        ("Frentes", resumo["frentes_ativas"], "ativas"),
        ("Realizados pendentes", resumo["situacao"]["pendentes"], "aguardando o fiscal"),
    ]
    linha = 5
    for rotulo, valor, nota in indicadores:
        aba.cell(row=linha, column=1, value=rotulo).font = _FONTE_ROTULO
        celula = aba.cell(row=linha, column=2, value=valor)
        celula.font = Font(bold=True, size=13, color=TEXTO, name="Segoe UI")
        aba.cell(row=linha, column=3, value=nota).font = Font(
            size=9, color="767676", name="Segoe UI"
        )
        linha += 1

    linha += 1
    aba.cell(row=linha, column=1, value="Situação da programação").font = _FONTE_TITULO
    linha += 1
    for rotulo, chave in (
        ("Em elaboração", "em_elaboracao"),
        ("Validada", "validada"),
        ("Publicada", "publicada"),
        ("Realizado aprovado", "aprovadas"),
        ("Sem realizado", "sem_realizado"),
    ):
        aba.cell(row=linha, column=1, value=rotulo).font = _FONTE_ROTULO
        aba.cell(row=linha, column=2, value=resumo["situacao"][chave]).font = _FONTE_CORPO
        linha += 1


def _aba_programacao(wb: Workbook, semana: str, atividades: list[dict]) -> None:
    aba = wb.create_sheet("Programação")
    titulos = (
        "Item",
        "ID Exclusiva",
        "Atividade",
        "Local",
        "Empresa",
        "Encarregado",
        "Fiscal",
        "Prev/Real",
        *calculos.DIAS_ROTULO,
        "Total",
        "Unidade",
        "PPC %",
        "Situação",
        "Realizado",
    )
    largura = {
        "Atividade": 46,
        "Local": 20,
        "Empresa": 18,
        "Encarregado": 22,
        "Fiscal": 18,
        "ID Exclusiva": 16,
        "Situação": 15,
        "Realizado": 13,
        "Prev/Real": 10,
        "Item": 7,
        "Total": 12,
        "Unidade": 10,
        "PPC %": 9,
    }
    _cabecalho(aba, titulos, largura=largura)

    linha = 2
    for a in atividades:
        comum = [
            a.get("item"),
            a.get("id_exclusiva"),
            a.get("atividade"),
            a.get("local"),
            a.get("empresa"),
            a.get("encarregado"),
            a.get("responsavel") or "—",
        ]
        aba.append(
            [
                *comum,
                "Previsto",
                *a["dias_previsto"],
                a["total_previsto"],
                a.get("unidade"),
                None,
                calculos.situacao_label(a.get("situacao", "")),
                calculos.aprovacao_label(a.get("aprovacao_realizado", "")),
            ]
        )
        aba.append(
            [
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "Realizado",
                *a["dias_total"],
                a["total_realizado"],
                a.get("unidade"),
                round(a.get("ppc", 0), 1),
                "",
                "",
            ]
        )
        for deslocamento in (0, 1):
            aba.cell(row=linha + deslocamento, column=3).alignment = _ESQUERDA
        aba.merge_cells(start_row=linha, start_column=1, end_row=linha + 1, end_column=1)
        aba.merge_cells(start_row=linha, start_column=2, end_row=linha + 1, end_column=2)
        aba.merge_cells(start_row=linha, start_column=3, end_row=linha + 1, end_column=3)
        linha += 2

    ultima = linha - 1
    if ultima >= 2:
        _zebrar(aba, 2, ultima, len(titulos))
        coluna_ppc = titulos.index("PPC %") + 1
        letra = get_column_letter(coluna_ppc)
        faixa = f"{letra}2:{letra}{ultima}"
        aba.conditional_formatting.add(
            faixa,
            CellIsRule(
                operator="greaterThanOrEqual", formula=["80"], fill=PatternFill("solid", fgColor=OK)
            ),
        )
        aba.conditional_formatting.add(
            faixa,
            CellIsRule(
                operator="between",
                formula=["60", "79.999"],
                fill=PatternFill("solid", fgColor=ATENCAO),
            ),
        )
        aba.conditional_formatting.add(
            faixa,
            CellIsRule(
                operator="lessThan", formula=["60"], fill=PatternFill("solid", fgColor=ERRO)
            ),
        )

        total = ultima + 1
        aba.cell(row=total, column=3, value=f"Total da semana {semana}").font = _FONTE_TOTAL
        primeira_dia = titulos.index("2ª") + 1
        for coluna in range(primeira_dia, primeira_dia + 8):
            letra_coluna = get_column_letter(coluna)
            celula = aba.cell(row=total, column=coluna)
            celula.value = f"=SUM({letra_coluna}2:{letra_coluna}{ultima})"
            celula.font = _FONTE_TOTAL
            celula.fill = PatternFill("solid", fgColor=VERDE_CLARO)

        aba.auto_filter.ref = f"A1:{get_column_letter(len(titulos))}{ultima}"

    aba.freeze_panes = "D2"
    _preparar_impressao(aba)


def _aba_quebra(wb: Workbook, titulo: str, rotulo: str, grupos: list[dict]) -> None:
    aba = wb.create_sheet(titulo)
    titulos = (
        rotulo,
        "Atividades",
        "Previsto",
        "Realizado",
        "Aderência %",
        "PPC médio %",
        "Pendências",
    )
    _cabecalho(aba, titulos, largura={rotulo: 30})
    for grupo in grupos:
        aba.append(
            [
                grupo["chave"],
                grupo["atividades"],
                grupo["total_previsto"],
                grupo["total_realizado"],
                grupo["aderencia"],
                grupo["ppc"],
                grupo["pendentes"],
            ]
        )
    if grupos:
        _zebrar(aba, 2, len(grupos) + 1, len(titulos))
    _preparar_impressao(aba, paisagem=False)


def _aba_curva(wb: Workbook, curva: list[dict]) -> None:
    aba = wb.create_sheet("Curva S")
    titulos = (
        "Semana",
        "Período",
        "Base %",
        "Previsto %",
        "Realizado %",
        "Base acum. %",
        "Previsto acum. %",
        "Realizado acum. %",
    )
    _cabecalho(aba, titulos, largura={"Período": 24, "Semana": 14})
    for ponto in curva:
        aba.append(
            [
                ponto["semana"],
                ponto["periodo"],
                ponto["base"],
                ponto["previsto"],
                ponto["realizado"],
                ponto["baseAcumulado"],
                ponto["previstoAcumulado"],
                ponto["realizadoAcumulado"],
            ]
        )
    if curva:
        _zebrar(aba, 2, len(curva) + 1, len(titulos))
    _preparar_impressao(aba, paisagem=False)


def _aba_diario(wb: Workbook, por_dia: list[dict]) -> None:
    aba = wb.create_sheet("Dia a dia")
    titulos = (
        "Dia",
        "Previsto",
        "Realizado dia",
        "Realizado noite",
        "Realizado total",
        "Aderência %",
    )
    _cabecalho(aba, titulos, largura={"Dia": 14})
    for dia in por_dia:
        total = round(dia["dia"] + dia["noite"], 2)
        aderencia = round(total / dia["previsto"] * 100, 1) if dia["previsto"] else 0
        aba.append([dia["nome"], dia["previsto"], dia["dia"], dia["noite"], total, aderencia])
    _zebrar(aba, 2, len(por_dia) + 1, len(titulos))
    _preparar_impressao(aba, paisagem=False)


def exportar_semana(
    semana: str,
    atividades: list[dict],
    resumo: dict,
    curva: list[dict],
    emissao: tuple[str, str],
    *,
    identificacao: tuple[str, str] = ("", ""),
) -> bytes:
    """The full weekly workbook: summary, matrix, breakdowns and curve.

    ``emissao`` é o par (quem emitiu, quando) — os dois só existem juntos,
    no rodapé da capa, e separá-los em dois parâmetros criava a chance de
    trocar a ordem sem o verificador perceber. ``identificacao`` é o par
    (projeto, cliente) vindo do registro de ambientes, dono dos nomes.
    """
    wb = Workbook()
    wb.remove(wb.active)

    _aba_capa(wb, semana, resumo, emissao, identificacao)
    _aba_programacao(wb, semana, atividades)
    _aba_quebra(wb, "Por contratada", "Contratada", calculos.quebrar_por(atividades, "empresa"))
    _aba_quebra(wb, "Por frente", "Frente", calculos.quebrar_por(atividades, "local"))
    _aba_quebra(
        wb, "Por encarregado", "Encarregado", calculos.quebrar_por(atividades, "encarregado")
    )
    _aba_diario(wb, calculos.por_dia(atividades))
    _aba_curva(wb, curva)

    wb.properties.title = f"Programação Semanal {semana}"
    wb.properties.creator = "Timenow Engenharia"
    return _bytes(wb)
