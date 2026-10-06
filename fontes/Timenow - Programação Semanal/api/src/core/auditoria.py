"""Append-only trail of everything that changed the schedule.

One line of JSON per event, in ``data/<ambiente>/auditoria.jsonl`` —
one trail per environment, resolved from the same active-environment
context as the persistence port. Append-only because an audit trail
that can be edited is not one — and because a single
``open(..., "a")`` never has to read the previous content, which is
what keeps it cheap enough to call on every mutation.

Reading is deliberately narrow: the screen only ever asks for the last N
events, optionally about one activity. Nobody paginates an audit trail on
a construction site.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.core import ambiente
from src.core.repositorio import diretorio_de_dados

ACOES = {
    "criar": "Criou a atividade",
    "editar": "Editou a atividade",
    "excluir": "Excluiu a atividade",
    "realizado": "Registrou o realizado",
    "validar": "Validou a programação",
    "aprovar": "Aprovou o realizado",
    "reabrir": "Reabriu o realizado",
    "publicar": "Publicou a programação",
    "importar": "Importou da planilha",
    "exportar": "Exportou os dados",
    "janela": "Alterou a janela de programação",
    "cadastro": "Alterou um cadastro de apoio",
    "colaborador": "Alterou um colaborador",
    "parametros": "Alterou os parâmetros do projeto",
}


def _arquivo() -> Path:
    """The trail file of the active environment.

    Resolves ``data/<slug>/auditoria.jsonl`` from the active environment
    and raises ``SemAmbienteError`` outside one — a trail never writes
    without knowing whose it is, and never lands on the root of
    ``data/``.
    """
    caminho = diretorio_de_dados() / ambiente.slug_ativo() / "auditoria.jsonl"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def registrar(acao: str, ator: str, resumo: str, contexto: dict | None = None) -> None:
    """Record one event. Never raises — an audit failure must not block work."""
    evento = {
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "acao": acao,
        "rotulo": ACOES.get(acao, acao),
        "ator": ator,
        "resumo": resumo,
        "contexto": contexto or {},
    }
    try:
        with _arquivo().open("a", encoding="utf-8") as trilha:
            trilha.write(json.dumps(evento, ensure_ascii=False) + "\n")
    except OSError:
        # Trilha indisponível não pode derrubar a operação que ela observa.
        return


def recentes(limite: int = 60, chave: str = "") -> list[dict]:
    """Last events, newest first. ``chave`` narrows to one activity."""
    try:
        linhas = _arquivo().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    eventos = []
    for linha in reversed(linhas):
        if not linha.strip():
            continue
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if chave and evento.get("contexto", {}).get("key") != chave:
            continue
        eventos.append(evento)
        if len(eventos) >= limite:
            break
    return eventos
