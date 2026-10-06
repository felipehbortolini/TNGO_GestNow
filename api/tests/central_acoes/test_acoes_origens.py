"""Origem das ações (ISSUE-019, D9, HU-055): o link de volta e a reação de cada módulo.

Dois registros da plataforma, os dois com o mesmo desenho do registro de anexos: o **tipo de
link** (cada módulo registra o seu; quem ainda não chegou aparece só com a referência, sem
âncora) e a **reação** (como o módulo da origem responde a um replanejamento ou a uma conclusão).
Cada teste usa um registro isolado.
"""

from __future__ import annotations

import pytest

from src.core import origin_links
from src.core.origin_links import OriginLinkType, OriginRef
from src.modulos.central_acoes import origins
from src.modulos.central_acoes.origins import ActionEvent


@pytest.fixture(autouse=True)
def registros_isolados(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um registro de links e um de reações vazios para cada teste."""
    monkeypatch.setattr(origin_links, "_TYPES", {})
    monkeypatch.setattr(origins, "_REACTIONS", {})


def _tipo(kind: str = "Risco") -> OriginLinkType:
    return OriginLinkType(
        kind=kind,
        build=lambda ref: origin_links.link_to_screen("central_acoes/ata", codigo=ref.reference),
    )


# ── O link de origem ─────────────────────────────────────────────────────────


def test_tipo_registrado_resolve_para_o_endereco_da_tela() -> None:
    origin_links.register(_tipo("Ata"))

    link = origin_links.resolve("Ata", "TN-2026-0028", record_id=1)

    assert link.reference == "TN-2026-0028"
    assert link.url == "/central-acoes/ata?codigo=TN-2026-0028"
    assert link.has_link is True


def test_tipo_que_ainda_nao_existe_mostra_a_referencia_sem_link() -> None:
    link = origin_links.resolve("Risco", "RSK-TN-2026-0001")

    assert link.reference == "RSK-TN-2026-0001"
    assert link.url is None
    assert link.has_link is False


def test_referencia_vazia_nao_gera_link_nem_quebra() -> None:
    origin_links.register(_tipo("Ata"))

    assert origin_links.resolve("Ata", None).url is None
    assert origin_links.resolve("Ata", "   ").reference == ""


def test_o_construtor_recebe_o_tipo_a_referencia_e_o_id() -> None:
    recebidos: list[OriginRef] = []

    def construir(ref: OriginRef) -> str | None:
        recebidos.append(ref)
        return None

    origin_links.register(OriginLinkType(kind="RNC", build=construir))

    link = origin_links.resolve("RNC", " RNC-1 ", record_id=9)

    assert recebidos == [OriginRef(kind="RNC", reference="RNC-1", record_id=9)]
    assert link.url is None


def test_o_construtor_que_nao_conhece_o_registro_deixa_so_o_texto() -> None:
    origin_links.register(OriginLinkType(kind="HSE", build=lambda _ref: None))

    assert origin_links.resolve("HSE", "OCR-1").has_link is False


def test_dois_modulos_nao_dividem_o_mesmo_tipo() -> None:
    origin_links.register(_tipo("Risco"))

    with pytest.raises(ValueError, match="já está registrado"):
        origin_links.register(OriginLinkType(kind="Risco", build=lambda _ref: None))


def test_registrar_o_mesmo_tipo_de_novo_nao_faz_nada() -> None:
    tipo = _tipo("Risco")
    origin_links.register(tipo)
    origin_links.register(tipo)

    assert origin_links.registered() == [tipo]
    assert origin_links.find("Risco") is tipo
    assert origin_links.find("Mudança") is None


def test_link_para_tela_que_nao_esta_na_navegacao_nao_gera_endereco() -> None:
    assert origin_links.link_to_screen("tela/inexistente") is None


def test_link_para_tela_sem_parametros_e_o_caminho_publico() -> None:
    assert origin_links.link_to_screen("central_acoes/atas") == "/central-acoes/atas"


def test_o_parametro_do_link_vai_codificado() -> None:
    endereco = origin_links.link_to_screen("central_acoes/ata", codigo="A B&C")

    assert endereco == "/central-acoes/ata?codigo=A+B%26C"


# ── A reação de cada módulo ──────────────────────────────────────────────────


def test_a_reacao_registrada_recebe_o_evento() -> None:
    chamadas: list[ActionEvent] = []

    def reagir(_session: object, _user: object, _action: object, event: ActionEvent) -> None:
        chamadas.append(event)

    origins.register_reaction("Risco", reagir)
    acao = type("Acao", (), {"origin": "Risco"})()

    origins.react(None, None, acao, ActionEvent.REPLANNED)  # type: ignore[arg-type]
    origins.react(None, None, acao, ActionEvent.COMPLETED)  # type: ignore[arg-type]

    assert chamadas == [ActionEvent.REPLANNED, ActionEvent.COMPLETED]
    assert origins.reaction_for("Risco") is reagir


def test_origem_sem_reacao_nao_exige_nada_da_central() -> None:
    acao = type("Acao", (), {"origin": "Contrato"})()

    origins.react(None, None, acao, ActionEvent.COMPLETED)  # type: ignore[arg-type]

    assert origins.reaction_for("Contrato") is None


def test_so_as_dez_origens_registram_reacao() -> None:
    with pytest.raises(ValueError, match="não é uma origem de ação"):
        origins.register_reaction("Pendências", lambda *_args: None)


def test_uma_origem_nao_tem_duas_reacoes() -> None:
    origins.register_reaction("RNC", lambda *_args: None)

    with pytest.raises(ValueError, match="já tem uma reação"):
        origins.register_reaction("RNC", lambda *_args: None)


def test_a_punch_list_e_tratada_na_origem() -> None:
    assert frozenset({"Punch list"}) == origins.TREATED_AT_SOURCE
