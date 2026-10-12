"""O motor do catálogo PT/EN e a cobertura das chaves usadas (ISSUE-087, D13).

O idioma vive no cookie ``gestnow_idioma`` e o português é a fonte: em pt
``translate`` devolve o texto intacto (nenhum teste antigo muda de expectativa).
A cobertura varre o que as telas marcaram — ``data-i18n*`` das views, ``TN.t``
do JavaScript, ``t('ns', ...)`` dos templates e ``translate``/``_label`` do
Python das áreas — e exige cada chave no catálogo. A colisão que motivou o
catálogo com namespace (``Prazo`` com sentidos diferentes por módulo) também é
um teste: cada módulo tem o seu termo.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import date
from pathlib import Path

import azure.functions as func
import pytest

from src.core import translations

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]
TEMPLATES = RAIZ_DO_REPOSITORIO / "api" / "src" / "templates"
VIEWS = RAIZ_DO_REPOSITORIO / "app" / "_views"
PAGINAS = RAIZ_DO_REPOSITORIO / "app" / "paginas"
DS = RAIZ_DO_REPOSITORIO / "app" / "ds"
MODULOS = RAIZ_DO_REPOSITORIO / "api" / "src" / "modulos"

AREAS = ("inicio", "central_acoes", "governanca", "financeiro")
TEMPLATE_NAMESPACES = (*AREAS, "nav", "comum")

TEMPLATE_CALL = re.compile(r"\bt\(\s*'([a-z_]+)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*\)")
VIEW_ATTR = re.compile(r'data-i18n(?:-title|-aria-label|-placeholder)?="([^"]+)"')
JS_CALL = re.compile(r'TN\.t\(\s*"([a-z_]+)"\s*,\s*"([^"]+)"')
PY_TRANSLATE = re.compile(r'translations\.translate\(\s*"([a-z_]+)"\s*,\s*"((?:[^"\\]|\\.)*)"')
PY_LABEL = re.compile(r'(?<![A-Za-z_])_label\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*idioma\s*\)')


def _request(cookies: dict[str, str] | None = None) -> func.HttpRequest:
    header = "; ".join(f"{name}={value}" for name, value in (cookies or {}).items())
    return func.HttpRequest(
        method="GET",
        url="/api/nav",
        headers={"Cookie": header} if header else {},
        params={},
        route_params={},
        body=b"",
    )


def _in_catalog(namespace: str, text: str) -> bool:
    key = translations.key_of(text)
    return key in translations.CATALOG.get(namespace, {}) or key in translations.CATALOG["comum"]


# ── O motor ──────────────────────────────────────────────────────────────


def test_idioma_sem_cookie_vale_portugues() -> None:
    assert translations.language_of(_request()) == "pt"


def test_idioma_com_valor_invalido_vale_portugues() -> None:
    assert translations.language_of(_request({"gestnow_idioma": "fr"})) == "pt"
    # O valor é comparado sem diferenciar maiúsculas.
    assert translations.language_of(_request({"gestnow_idioma": "EN"})) == "en"


def test_idioma_do_cookie_en() -> None:
    assert translations.language_of(_request({"gestnow_idioma": "en"})) == "en"
    assert translations.language_of(_request({"outro": "1", "gestnow_idioma": "en"})) == "en"


def test_cookie_do_idioma_lembra_a_escolha() -> None:
    header = translations.cookie_header("en", secure=True)

    assert header.startswith("gestnow_idioma=en; Path=/; Max-Age=")
    assert "SameSite=Lax" in header
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "Secure" not in translations.cookie_header("pt", secure=False)


def test_em_portugues_o_texto_volta_intacto() -> None:
    texto = "  Ações atrasadas  "
    assert translations.translate("central_acoes", texto, "pt") == texto
    assert translations.t("governanca", "Solicitação de mudança", "pt") == "Solicitação de mudança"


def test_traducao_normaliza_a_chave_e_cai_no_comum() -> None:
    assert translations.translate("inicio", "  Ações   atrasadas ", "en") == "Late actions"
    # Sem tradução no namespace do módulo, o comum responde.
    assert translations.translate("inicio", "Carregando...", "en") == "Loading..."


def test_sem_traducao_devolve_o_texto_original() -> None:
    texto = "Um texto que nenhum dicionário tem"
    assert translations.translate("inicio", texto, "en") == texto


def test_colisoes_do_dicionario_antigo_nao_aparecem() -> None:
    # Cada módulo tem o seu termo: o catálogo com namespace resolve a colisão.
    assert translations.translate("central_acoes", "Prazo", "en") == "Due date"
    assert translations.translate("governanca", "Prazo", "en") == "Deadline"
    assert translations.translate("financeiro", "Prazo", "en") == "Time"
    assert translations.translate("central_acoes", "Desvio", "en") == "Variance"
    assert translations.translate("governanca", "Desvio", "en") == "Variance"
    assert translations.translate("financeiro", "Emissão", "en") == "Issue date"
    assert translations.translate("governanca", "Emissão", "en") == "Issue"
    assert translations.translate("central_acoes", "Mensal", "en") == "Monthly"
    assert translations.translate("financeiro", "Mensal", "en") == "Monthly"


def test_terminologia_das_siglas() -> None:
    assert translations.translate("inicio", "EAP", "en") == "WBS"
    assert translations.translate("inicio", "EAC", "en") == "CBS"
    assert translations.translate("governanca", "SM", "en") == "CR"
    assert translations.translate("financeiro", "SM", "en") == "SM"
    assert translations.translate("governanca", "FP", "en") == "PF"
    assert translations.translate("governanca", "CP", "en") == "PC"


def test_mes_curto_e_data_seguem_o_idioma() -> None:
    assert translations.mes_curto(9, "pt") == "set"
    assert translations.mes_curto(9, "en") == "Sep"
    assert translations.format_date(date(2026, 9, 25), "pt") == "25/09/2026"
    assert translations.format_date(date(2026, 9, 25), "en") == "09/25/2026"
    assert translations.format_date(None, "en") == ""


def test_rotulos_do_grafico_por_idioma() -> None:
    assert translations.rotulos_do_grafico("pt") == {}
    rotulos = translations.rotulos_do_grafico("en")
    assert rotulos["todos"] == "All"
    assert rotulos["meta"] == "Target"
    assert rotulos["vazio"] == "No data to display."
    mesclado = translations.rotulos_de_grafico("en", {"vazio": "Nenhuma avaliação registrada."})
    assert mesclado["vazio"] == "Nenhuma avaliação registrada."
    assert mesclado["todos"] == "All"
    assert translations.rotulos_de_grafico("pt", {"vazio": "x"}) == {"vazio": "x"}


def test_textos_do_cliente_em_portugues_e_vazio() -> None:
    assert translations.textos_do_cliente("pt") == {}


def test_textos_do_cliente_em_ingles_tem_as_chaves_estaticas() -> None:
    textos = translations.textos_do_cliente("en")

    assert textos["comum"]["Carregando..."] == "Loading..."
    assert textos["graficos"]["Todos"] == "All"
    assert textos["central_acoes"]["Carregando as ações..."] == "Loading the actions..."
    # Toda chave entregue ao cliente existe no catálogo do seu namespace.
    for namespace, entries in textos.items():
        for key, value in entries.items():
            assert value, f"{namespace}:{key} vazio"


# ── A cobertura das chaves usadas ────────────────────────────────────────


def test_toda_chave_dos_templates_tem_traducao() -> None:
    faltando: list[str] = []
    for namespace in TEMPLATE_NAMESPACES:
        for caminho in sorted((TEMPLATES / namespace).rglob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            for found_ns, key in TEMPLATE_CALL.findall(texto):
                if not _in_catalog(found_ns, key):
                    faltando.append(f"{caminho.name}: t('{found_ns}', {key!r})")
    assert faltando == []


def test_toda_chave_das_views_tem_traducao() -> None:
    faltando: list[str] = []
    for area in AREAS:
        for caminho in sorted((VIEWS / area).rglob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            for key in VIEW_ATTR.findall(texto):
                if not _in_catalog(area, key):
                    faltando.append(f"{caminho.name}: data-i18n {key!r}")
    assert faltando == []


def test_toda_chave_do_javascript_tem_traducao() -> None:
    faltando: list[str] = []
    pastas = [DS, *(PAGINAS / area for area in AREAS)]
    for pasta in pastas:
        for caminho in sorted(pasta.rglob("*.js")):
            texto = caminho.read_text(encoding="utf-8")
            for namespace, key in JS_CALL.findall(texto):
                if not _in_catalog(namespace, key):
                    faltando.append(f"{caminho.name}: TN.t('{namespace}', {key!r})")
    assert faltando == []


def test_toda_chave_do_python_das_areas_tem_traducao() -> None:
    faltando: list[str] = []
    for area in AREAS:
        for caminho in sorted((MODULOS / area).glob("*.py")):
            texto = caminho.read_text(encoding="utf-8")
            for namespace, key in PY_TRANSLATE.findall(texto):
                if not _in_catalog(namespace, key):
                    faltando.append(f"{caminho.name}: translate('{namespace}', {key!r})")
            for key in PY_LABEL.findall(texto):
                if not _in_catalog(area, key):
                    faltando.append(f"{caminho.name}: _label({key!r})")
    assert faltando == []


def _constantes_sem_traducao(area: str, caminho: Path) -> list[str]:
    faltando: list[str] = []
    tree = ast.parse(caminho.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if not (target.id.endswith("_MESSAGE") or target.id.endswith("_NOTICE")):
                continue
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                continue
            text = node.value.value
            if len(text) < 6 or " " not in text:
                continue  # um nome de campo, não uma mensagem
            if not _in_catalog(area, text):
                faltando.append(f"{caminho.name}: {target.id} {text!r}")
    return faltando


def test_as_constantes_de_mensagem_das_areas_tem_traducao() -> None:
    faltando = [
        item
        for area in AREAS
        for caminho in sorted((MODULOS / area).glob("*.py"))
        for item in _constantes_sem_traducao(area, caminho)
    ]
    assert faltando == []


def test_a_navegacao_inteira_tem_traducao() -> None:
    """Todos os módulos e telas da lista de navegação, e os rótulos da barra, em inglês."""
    from src.core import navigation

    faltando: list[str] = []
    for module in navigation.modules():
        if not _in_catalog("shell", module.title):
            faltando.append(module.title)
        for screen in module.screens:
            for text in (screen.title, screen.tab_label, screen.group):
                if text and not _in_catalog("shell", text):
                    faltando.append(text)
    assert faltando == []


@pytest.mark.parametrize(
    "key",
    ["Módulos", "Idioma", "Sair", "Escopo", "Perfil (demonstração)", "Portfólio", "projetos"],
)
def test_rotulos_da_barra_lateral_tem_traducao(key: str) -> None:
    assert _in_catalog("shell", key)


def test_o_json_do_catalogo_e_serializavel_e_sem_valor_vazio() -> None:
    payload = json.dumps(translations.CATALOG, ensure_ascii=False)
    assert len(payload) > 1000
    for namespace, entries in translations.CATALOG.items():
        assert entries, namespace
        for key, value in entries.items():
            assert key.strip(), namespace
            assert value.strip(), f"{namespace}:{key}"
