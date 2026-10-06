"""Ativos da exportação (ISSUE-017, D12): as cores e o logo do Excel vêm do Design System.

Só ``api/`` vai para o Azure, onde ``app/ds/tokens.css`` não existe. O servidor leva
consigo uma cópia das cores (``tokens_ds.json``) e do logo (``logo_timenow.png``), que
``scripts/generate_ds_assets.py`` escreve. O teste de paridade falha quando qualquer das
cópias deixa de bater com o Design System: a fonte continua uma só, e a cópia que viaja
com a API não envelhece em silêncio. O resto confere a leitura do ``tokens.css`` e que
nenhuma biblioteca de PDF entrou no servidor nem no navegador.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.core import design_tokens

RAIZ = Path(__file__).resolve().parents[3]
TOKENS_CSS = RAIZ / "app" / "ds" / "tokens.css"
LOGO_DO_DESIGN_SYSTEM = RAIZ / "app" / "ds" / "assets" / "favicon-timenow.png"
COMO_ATUALIZAR = "rode api/.venv/bin/python scripts/generate_ds_assets.py"

# O PDF é a impressão do navegador (decisão do dono do produto, 05/10/2026).
BIBLIOTECAS_DE_PDF = (
    "reportlab",
    "weasyprint",
    "fpdf",
    "fpdf2",
    "pypdf",
    "pypdf2",
    "pdfkit",
    "xhtml2pdf",
    "pdfminer",
    "jspdf",
    "pdfmake",
    "html2pdf",
    "pdf-lib",
    "pdfjs-dist",
    "wkhtmltopdf",
    "puppeteer",
    "playwright",
)
MANIFESTOS = ("api/pyproject.toml", "api/requirements.txt", "api/uv.lock", "package.json")


# ── A cópia que viaja com a API bate com o Design System ─────────────────


def test_o_arquivo_de_cores_da_api_e_o_tokens_css_de_hoje() -> None:
    do_design_system = design_tokens.parse_css(TOKENS_CSS.read_text(encoding="utf-8"))
    do_arquivo = design_tokens.from_data(
        json.loads(design_tokens.TOKENS_FILE.read_text(encoding="utf-8"))
    )

    assert do_arquivo == do_design_system, f"tokens_ds.json está defasado: {COMO_ATUALIZAR}"


def test_o_logo_do_excel_e_o_logo_do_design_system() -> None:
    copia = design_tokens.LOGO_FILE.read_bytes()

    assert copia == LOGO_DO_DESIGN_SYSTEM.read_bytes(), f"logo defasado: {COMO_ATUALIZAR}"
    assert copia[:8] == b"\x89PNG\r\n\x1a\n"


def test_cada_cor_pedida_ao_modulo_e_a_do_tokens_css() -> None:
    do_design_system = design_tokens.parse_css(TOKENS_CSS.read_text(encoding="utf-8"))

    for token, valor in do_design_system.colors.items():
        assert design_tokens.color(token) == valor.removeprefix("#"), token
    assert design_tokens.font_name() == do_design_system.font


def test_token_que_nao_e_cor_do_tokens_css_falha_alto() -> None:
    for desconhecido in ("--nao-existe", "--space-lg", "--font"):
        with pytest.raises(design_tokens.UnknownTokenError, match=re.escape(desconhecido)):
            design_tokens.color(desconhecido)


# ── Como o tokens.css é lido ─────────────────────────────────────────────


def test_le_so_as_cores_em_hexadecimal_e_as_escreve_em_seis_digitos_maiusculos() -> None:
    css = """
    :root {
      --verde-500: #00a793;
      --curto: #abc;
      --com-espaco : #FFFFFF ;
      --espaco-lg: 16px;
      --composta: var(--verde-500);
      --transparente: rgba(0, 0, 0, .5);
      --com-alfa: #11223344;
      /* --comentada: #ffffff; */
      --font: "Segoe UI", system-ui, sans-serif;
      --font-label: "Montserrat", sans-serif;
    }
    """

    tokens = design_tokens.parse_css(css)

    assert tokens.colors == {
        "--verde-500": "#00A793",
        "--curto": "#AABBCC",
        "--com-espaco": "#FFFFFF",
    }
    assert tokens.font == "Segoe UI"


def test_sem_fonte_com_aspas_a_fonte_fica_vazia() -> None:
    tokens = design_tokens.parse_css(":root { --font: system-ui, sans-serif; --a: #000; }")

    assert tokens.font == ""
    assert tokens.colors == {"--a": "#000000"}


def test_o_arquivo_de_cores_vai_e_volta_sem_perder_nada(tmp_path: Path) -> None:
    tokens = design_tokens.parse_css(TOKENS_CSS.read_text(encoding="utf-8"))
    arquivo = tmp_path / "tokens.json"

    design_tokens.write_tokens(tokens, arquivo)

    texto = arquivo.read_text(encoding="utf-8")
    assert texto.endswith("}\n")
    assert set(json.loads(texto)) == {"descricao", "fonte", "cores"}
    assert design_tokens.from_data(json.loads(texto)) == tokens


# ── Nenhuma biblioteca de PDF ────────────────────────────────────────────


def test_nenhuma_biblioteca_de_pdf_foi_adicionada_ao_servidor_nem_ao_navegador() -> None:
    texto = " ".join(
        (RAIZ / manifesto).read_text(encoding="utf-8").lower() for manifesto in MANIFESTOS
    )

    achadas = [
        nome
        for nome in BIBLIOTECAS_DE_PDF
        if re.search(rf"(?<![\w-]){re.escape(nome)}(?![\w-])", texto)
    ]

    assert achadas == []


def test_nenhum_arquivo_de_pdf_foi_vendorizado_no_app() -> None:
    arquivos = [caminho for caminho in (RAIZ / "app").rglob("*") if caminho.is_file()]

    com_pdf = [caminho.name for caminho in arquivos if "pdf" in caminho.name.lower()]

    assert com_pdf == []
