"""Glossário de siglas (ISSUE-009, HU-018): o CONTEXT.md é a fonte única.

A extração pega os termos que são siglas e o significado palavra por palavra; o
arquivo ``glossario.json`` é a cópia que viaja com a API (só ``api/`` vai ao
Azure) e este teste falha quando ela deixa de bater com o CONTEXT.md. A rota
``/api/glossario`` entrega o resultado ao shell.
"""

from __future__ import annotations

from pathlib import Path

import azure.functions as func
import pytest

from src.blueprints.nav import glossary
from src.core import glossary as glossario
from tests.html_tags import find_all, parse_tags

CONTEXT = Path(__file__).resolve().parents[3] / "CONTEXT.md"

EXEMPLO = """\
# Glossário

## Custos

**EAP** — Estrutura Analítica do Projeto. Decompõe o escopo em áreas,
subáreas e pacotes.

**EV** — Valor Agregado; **PV** — Valor Planejado; **AC** — Custo Real.
São valores acumulados na data de corte.

**SPI de custo** — índice de prazo do valor agregado.
**SPI físico** — avanço real dividido pelo previsto.

**ROS** — *Required On Site*. Data em que o item é necessário no local.

**HiPo** — ocorrência de alto potencial.

**Semana ISO** — período de segunda a domingo.

**Programação Semanal** — compromisso de uma contratada para uma semana.

**Design System** (DS) — `app/ds/`. A única fonte visual.

Texto solto que não abre uma entrada, com SPI no meio.
"""


def test_extrai_as_siglas_e_o_significado_palavra_por_palavra() -> None:
    parsed = glossario.parse_context(EXEMPLO)

    por_sigla = {(item.abbreviation, item.term): item.meaning for item in parsed.abbreviations}
    assert por_sigla[("EAP", "EAP")] == (
        "Estrutura Analítica do Projeto. Decompõe o escopo em áreas, subáreas e pacotes."
    )
    assert por_sigla[("EV", "EV")] == "Valor Agregado"
    assert por_sigla[("PV", "PV")] == "Valor Planejado"
    assert por_sigla[("AC", "AC")] == "Custo Real. São valores acumulados na data de corte."


def test_sigla_com_qualificador_pertence_a_sigla_e_mostra_todas_as_entradas() -> None:
    parsed = glossario.parse_context(EXEMPLO)

    entradas = parsed.meanings_of("SPI")
    assert [item.term for item in entradas] == ["SPI de custo", "SPI físico"]
    assert entradas[0].meaning == "Índice de prazo do valor agregado."


def test_tira_a_marcacao_e_aceita_sigla_com_minuscula() -> None:
    parsed = glossario.parse_context(EXEMPLO)

    assert parsed.meanings_of("ROS")[0].meaning == (
        "Required On Site. Data em que o item é necessário no local."
    )
    assert parsed.meanings_of("HiPo")[0].meaning == "Ocorrência de alto potencial."


def test_termo_que_nao_e_sigla_fica_de_fora_menos_a_notacao_da_semana() -> None:
    parsed = glossario.parse_context(EXEMPLO)

    siglas = {item.abbreviation for item in parsed.abbreviations}
    assert siglas == {"EAP", "EV", "PV", "AC", "SPI", "ROS", "HiPo"}
    assert [(item.kind, item.term) for item in parsed.patterns] == [("semana", "Semana ISO")]
    assert parsed.patterns[0].meaning == "Período de segunda a domingo."


def test_arquivo_do_glossario_esta_em_dia_com_o_contexto() -> None:
    do_contexto = glossario.parse_context(CONTEXT.read_text(encoding="utf-8"))

    assert glossario.load_glossary() == do_contexto, (
        "glossario.json ficou diferente do CONTEXT.md. "
        "Rode: api/.venv/bin/python scripts/generate_glossary.py"
    )


@pytest.mark.parametrize("sigla", ["SPI", "CPI", "VME", "RNC", "TF"])
def test_siglas_da_historia_18_tem_significado(sigla: str) -> None:
    entradas = glossario.load_glossary().meanings_of(sigla)

    assert entradas
    assert all(item.meaning for item in entradas)


def test_semana_s39_e_explicada_pelo_termo_semana_iso() -> None:
    notacoes = {item.kind: item for item in glossario.load_glossary().patterns}

    assert notacoes["semana"].term == "Semana ISO"
    assert "segunda a domingo" in notacoes["semana"].meaning


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_rota_do_glossario_entrega_siglas_e_notacoes_ocultas() -> None:
    resposta = glossary(
        func.HttpRequest(
            method="GET",
            url="/api/glossario",
            headers={"X-Alpine-Request": "true", "X-Alpine-Target": "glossario"},
            params={},
            route_params={},
            body=b"",
        )
    )

    assert resposta.status_code == 200
    tags = parse_tags(resposta.get_body().decode())
    raiz = next(tag for tag in tags if tag.attrs.get("id") == "glossario")
    assert "hidden" in raiz.attrs
    termos = find_all(tags, "dt")
    spi = [t.clean_text() for t in termos if t.attrs.get("data-sigla") == "SPI"]
    assert spi == ["SPI de custo", "SPI físico"]
    assert [t.attrs["data-padrao"] for t in termos if "data-padrao" in t.attrs] == ["semana"]


def test_rota_do_glossario_sem_o_cabecalho_do_alpine_redireciona_para_o_shell() -> None:
    resposta = glossary(
        func.HttpRequest(
            method="GET", url="/api/glossario", headers={}, params={}, route_params={}, body=b""
        )
    )

    assert resposta.status_code == 302
    assert resposta.headers.get("Location") == "/index.html"
