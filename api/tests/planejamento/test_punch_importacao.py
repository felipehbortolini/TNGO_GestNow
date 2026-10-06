"""Importação da Punch list (ISSUE-049, D12): conferir não grava, confirmar grava só as válidas.

O importador é percorrido como a tela o usa: a conferência linha a linha (``check``) e a
confirmação (``confirm``), que escreve pela fachada, e por isso cada linha vira um item com a
sua ação na Central, como o formulário.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import importing
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.importing import Confirmation, ImportContext, Upload, digest_of
from src.modulos.central_acoes.models import Action
from src.modulos.planejamento import punch_importers as importers
from src.modulos.planejamento.models import PunchItem
from tests.apoio_6wla import HOJE, Cadastro
from tests.apoio_punch import CenarioPunch, montar_cenario
from tests.importadores_de_teste import planilha

CABECALHO = (
    "Sistema",
    "Subsistema",
    "TAG",
    "Disciplina",
    "Categoria",
    "Marco",
    "Origem",
    "Descrição",
    "Empresa",
    "Responsável",
    "Prazo",
)


@pytest.fixture
def cenario(sessao: Session, cadastro: Cadastro) -> CenarioPunch:
    """O cadastro do 6WLA com a numeração do projeto e dois sistemas."""
    return montar_cenario(sessao, cadastro)


def _linha(**mudancas: object) -> list[object]:
    base: dict[str, object] = {
        "Sistema": "210",
        "Subsistema": "Tubulação",
        "TAG": "310-P-030",
        "Disciplina": "Tubulação",
        "Categoria": "B",
        "Marco": "Aceite provisório",
        "Origem": "Walkdown",
        "Descrição": "Isolamento térmico incompleto",
        "Empresa": "Montadora Alfa",
        "Responsável": "Maria Responsável",
        "Prazo": date(2026, 10, 15),
    }
    base.update(mudancas)
    return [base[titulo] for titulo in CABECALHO]


def _arquivo(*linhas: list[object]) -> Upload:
    return Upload("punch.xlsx", planilha(linhas, cabecalho=CABECALHO))


def _contexto(cenario: CenarioPunch) -> ImportContext:
    return ImportContext(user=cenario.executante, scope=cenario.escopo, reference_date=HOJE)


def _itens(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(PunchItem)) or 0


def _acoes(session: Session) -> int:
    consulta = select(func.count()).select_from(Action).where(Action.origin == "Punch list")
    return session.scalar(consulta) or 0


def test_o_importador_se_registra_uma_vez_e_o_modelo_traz_as_onze_colunas() -> None:
    importers.register_importers()
    importers.register_importers()
    importador = importing.require(importers.KEY)
    assert [coluna.header for coluna in importador.columns] == list(CABECALHO)


def test_conferir_diz_o_que_cada_linha_fara_e_nao_grava(
    sessao: Session, cenario: CenarioPunch
) -> None:
    importador = importers.punch_importer()
    arquivo = _arquivo(
        _linha(),
        _linha(Sistema="999"),
        _linha(Empresa="Empresa fantasma"),
    )

    previa = importing.check(
        sessao, importer=importador, upload=arquivo, context=_contexto(cenario)
    )

    assert len(previa.writable_rows) == 1
    assert len(previa.error_rows) == 2
    problemas = " ".join(" ".join(item.problems) for item in previa.error_rows)
    assert "o sistema não está no cadastro do projeto" in problemas
    assert "a empresa não está no cadastro" in problemas
    assert "Categoria" not in problemas
    assert _itens(sessao) == 0
    assert _acoes(sessao) == 0


def test_confirmar_grava_so_as_linhas_validas_e_cada_uma_gera_a_acao(
    sessao: Session, cenario: CenarioPunch
) -> None:
    importador = importers.punch_importer()
    arquivo = _arquivo(_linha(), _linha(Sistema="999"), _linha(TAG="310-P-031"))

    resultado = importing.confirm(
        sessao,
        importer=importador,
        upload=arquivo,
        context=_contexto(cenario),
        confirmation=Confirmation(checked_digest=digest_of(arquivo), acknowledged=True),
    )

    assert len(resultado.written) == 2
    assert len(resultado.skipped) == 1
    assert _itens(sessao) == 2
    assert _acoes(sessao) == 2
    codigos = sessao.scalars(select(PunchItem.code).order_by(PunchItem.id)).all()
    assert list(codigos) == ["PL-TN-2026-0001", "PL-TN-2026-0002"]
    primeiro = sessao.scalars(select(PunchItem).order_by(PunchItem.id)).first()
    assert primeiro is not None
    assert primeiro.identified_by_id == cenario.executante.person_id
    assert primeiro.opened_on == HOJE


def test_com_erro_a_confirmacao_pede_ciencia_e_sem_ela_nada_grava(
    sessao: Session, cenario: CenarioPunch
) -> None:
    importador = importers.punch_importer()
    arquivo = _arquivo(_linha(), _linha(Sistema="999"))

    with pytest.raises(InvalidDataError):
        importing.confirm(
            sessao,
            importer=importador,
            upload=arquivo,
            context=_contexto(cenario),
            confirmation=Confirmation(checked_digest=digest_of(arquivo), acknowledged=False),
        )

    assert _itens(sessao) == 0


def test_importar_no_portfolio_e_recusado_com_a_mensagem_do_escopo(
    sessao: Session, cenario: CenarioPunch
) -> None:
    contexto = ImportContext(user=cenario.executante, scope=cenario.portfolio, reference_date=HOJE)
    with pytest.raises(InvalidDataError):
        importing.check(
            sessao,
            importer=importers.punch_importer(),
            upload=_arquivo(_linha()),
            context=contexto,
        )


def test_visualizador_nao_importa(sessao: Session, cenario: CenarioPunch) -> None:
    contexto = ImportContext(user=cenario.visualizador, scope=cenario.escopo, reference_date=HOJE)
    with pytest.raises(AccessDeniedError):
        importing.check(
            sessao,
            importer=importers.punch_importer(),
            upload=_arquivo(_linha()),
            context=contexto,
        )
