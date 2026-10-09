"""Os links de origem que chegam ao risco (ISSUE-064/065/067, D9, HU-055).

A origem ``Risco`` está registrada na plataforma desde a fatia do registro e resolve para a ficha
do risco; a ficha lista as ações da Central com essa origem e o código da origem viaja com a
referência. O teste confirma o registro e o link resolvido, para a costura da Central não ficar
sem cobertura.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from src.core import origin_links
from src.modulos.riscos import ficha_service, service
from src.modulos.riscos.validation import ActionInput
from tests.apoio_riscos import REFERENCIA, Cenario, nova_avaliacao, novo_risco


def test_a_origem_risco_resolve_para_a_ficha(sessao: Session, cenario: Cenario) -> None:
    codigo = service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario), reference_date=REFERENCIA
    ).code

    tipo = origin_links.find("Risco")
    assert tipo is not None, "a origem Risco foi registrada na fatia do registro (064)"

    link = origin_links.resolve("Risco", codigo)
    assert link.reference == codigo
    assert link.url is not None
    assert f"/riscos/ficha?codigo={codigo}" in link.url

    assert origin_links.resolve("Risco", None).has_link is False, "sem referência, sem link"


def test_a_acao_da_central_de_origem_risco_aparece_na_ficha(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario), reference_date=REFERENCIA
    ).code
    service.assess_risk(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=nova_avaliacao(probability=2, impact=2, dimensions={"prazo": 2}),
        reference_date=REFERENCIA,
    )
    ficha_service.create_risk_action(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=ActionInput(
            subject="Contratar a consultoria ambiental",
            requester_id=cenario.mario.person_id,
            responsible_id=cenario.mario.person_id,
            planned_date=REFERENCIA + timedelta(days=5),
        ),
        reference_date=REFERENCIA,
    )

    sheet = ficha_service.find_risk_sheet(
        sessao, user=cenario.mario, code=codigo, reference_date=REFERENCIA
    )
    assert sheet is not None
    assert len(sheet.actions) == 1, "a ficha lê as ações pela fachada da Central"
    assert "/central-acoes/acoes?busca=" in sheet.actions[0].url
