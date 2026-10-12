"""Teste de guarda do roteiro manual de aceite (ISSUE-091, D12/Q30/Q31).

O roteiro, em ``docs/ROTEIRO-DE-ACEITE.md``, é o passo a passo com que o dono
aceita o GestNow. Ele tem de cobrir cada módulo e cada tela da lista de
navegação (``api/src/core/navegacao.json``) e as seções das revisões do dono:
a Q30 (o modelo de dados, em ``docs/MODELO-DE-DADOS.md``) e a Q31 (as
divergências, em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``), além das conferências
transversais (exportações, acessibilidade e varredura) e da publicação no
Azure.

Sem banco: o teste só lê arquivos do repositório. Parametrizado por módulo e
por tela, reprova nomeando o que o roteiro não cita; as seções do dono são
conferidas pelas frases que o roteiro cita dos próprios documentos.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]
ROTEIRO = RAIZ_DO_REPOSITORIO / "docs" / "ROTEIRO-DE-ACEITE.md"
NAVEGACAO = RAIZ_DO_REPOSITORIO / "api" / "src" / "core" / "navegacao.json"
MODELO = RAIZ_DO_REPOSITORIO / "docs" / "MODELO-DE-DADOS.md"
DIVERGENCIAS = RAIZ_DO_REPOSITORIO / "docs" / "DIVERGENCIAS-DO-PROTOTIPO.md"

_LISTA = json.loads(NAVEGACAO.read_text(encoding="utf-8"))["modulos"]

# Um caso por módulo e um por tela da lista, nomeados pelo identificador: o
# defeito reprova nomeando só o que falta no roteiro.
MODULOS: tuple[tuple[str, str], ...] = tuple(
    (str(modulo["id"]), str(modulo["titulo"])) for modulo in _LISTA
)
TELAS: tuple[tuple[str, str], ...] = tuple(
    (f"{tela.get('modulo', modulo['id'])}/{tela['id']}", str(tela["titulo"]))
    for modulo in _LISTA
    for tela in modulo["telas"]
)


def _roteiro() -> str:
    return ROTEIRO.read_text(encoding="utf-8")


# ── A cobertura da lista de navegação ─────────────────────────────────────


def test_o_roteiro_existe_e_e_o_do_aceite() -> None:
    roteiro = _roteiro()

    assert "# Roteiro manual de aceite" in roteiro
    assert len(roteiro) > 5_000, "o roteiro está curto demais para cobrir os 10 módulos"


@pytest.mark.parametrize(("modulo", "titulo"), MODULOS, ids=[modulo for modulo, _ in MODULOS])
def test_o_modulo_da_lista_de_navegacao_aparece_no_roteiro(modulo: str, titulo: str) -> None:
    roteiro = _roteiro()

    assert titulo in roteiro, f"o roteiro não cita o módulo {modulo!r} ({titulo!r})"


@pytest.mark.parametrize(("tela", "titulo"), TELAS, ids=[tela for tela, _ in TELAS])
def test_a_tela_da_lista_de_navegacao_aparece_no_roteiro(tela: str, titulo: str) -> None:
    roteiro = _roteiro()

    assert titulo in roteiro, f"o roteiro não cita a tela {tela!r} ({titulo!r})"


# ── As revisões do dono (Q30 e Q31) ───────────────────────────────────────


def test_o_roteiro_tem_as_secoes_de_revisao_do_dono_q30_e_q31() -> None:
    roteiro = _roteiro()
    modelo = MODELO.read_text(encoding="utf-8")
    divergencias = DIVERGENCIAS.read_text(encoding="utf-8")

    assert "Q30" in roteiro, "falta a revisão do modelo de dados (Q30)"
    assert "Q31" in roteiro, "falta a decisão das divergências (Q31)"
    assert "MODELO-DE-DADOS.md" in roteiro
    assert "DIVERGENCIAS-DO-PROTOTIPO.md" in roteiro
    # As frases que o roteiro cita são as dos próprios documentos: se um deles
    # mudar o estado do aceite, o roteiro tem de mudar junto.
    assert "aceito para execução" in modelo
    assert "aceito para execução" in roteiro
    assert "vira issue nova" in modelo
    assert "vira issue nova" in roteiro
    assert "pendente de aceite" in divergencias
    assert "pendente de aceite" in roteiro
    assert "Situação" in roteiro, "o roteiro não explica a coluna Situação das divergências"
    assert '"aceita"' in roteiro, "o roteiro não diz o que marcar na coluna Situação"


# ── As outras entregas do roteiro ─────────────────────────────────────────


def test_o_roteiro_ensina_a_entrar_no_modo_demonstracao() -> None:
    roteiro = _roteiro()

    for termo in ("demonstração", "gestnow_demo_perfil", "gestnow_idioma", "trilho", "Portfólio"):
        assert termo in roteiro, f"o roteiro não ensina a entrada: falta {termo!r}"


def test_o_roteiro_aponta_as_pendencias_de_fonte_e_a_publicacao_no_azure() -> None:
    roteiro = _roteiro()

    assert "PENDENCIAS-DE-FONTE.md" in roteiro
    assert "PUBLICACAO-AZURE.md" in roteiro, "o roteiro não aponta o guia da ISSUE-092"


def test_o_roteiro_aponta_as_conferencias_transversais() -> None:
    roteiro = _roteiro()

    assert "EXPORTACOES.md" in roteiro, "o roteiro não aponta o inventário de exportações"
    assert "ACESSIBILIDADE.md" in roteiro
    assert "npm run varredura" in roteiro, "o roteiro não aponta a varredura de telas"
