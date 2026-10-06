"""The read-only JSON API — ``/api/dados/v1/*``, a space of its own.

Deliberately NOT a fragment blueprint and NOT behind ``com_usuario``:
the consumer is not the app's browser — the Alpine gate and the SWA
session do not apply here. The credential is the reading token,
presented as bearer, and the token itself resolves the environment: no
cookie, no tab header, and no token ever reaches another environment.

The word ``dados`` is in the path on purpose: no fragment endpoint can
fall into the sessionless space by a naming accident, and the quality
gate scans the registered routes to keep it that way — only GET verbs,
never a write. This is the third conscious exception to "the server
returns finished HTML", recorded in ``docs/ARCHITECTURE.md``.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from datetime import UTC, datetime

import azure.functions as func

from src.core import ambiente, calculos, dados, registro
from src.core.dados import InvalidoError

bp = func.Blueprint()

PREFIXO_BEARER = "bearer "


def _json(resposta: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(resposta, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
    )


def recusa_json(mensagem: str, status_code: int) -> func.HttpResponse:
    """A refusal the consumer can read — JSON, never HTML, never fragment."""
    return _json({"erro": mensagem}, status_code)


def _envelope(token: dict, dados_payload) -> dict:
    escolhido = registro.obter().obter(token["ambiente"]) or {}
    return {
        "ambiente": {
            "id": escolhido.get("id", ""),
            "projeto": escolhido.get("projeto", ""),
            "cliente": escolhido.get("cliente", ""),
        },
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "dados": dados_payload,
    }


def com_token(handler: Callable) -> Callable:
    """The API's seam: bearer in, environment out, always closed.

    Resolves the token through the register port and opens the active
    environment OF THAT TOKEN around the handler — the credential is
    the resolution, never the cookie. Refusals are JSON with a legible
    reason, and even they leave a distinguishable line in the register
    trail.
    """

    @functools.wraps(handler)
    def envolvido(req: func.HttpRequest) -> func.HttpResponse:
        recurso = req.url.split("?", 1)[0]
        autorizacao = req.headers.get("Authorization") or ""

        if not autorizacao.lower().startswith(PREFIXO_BEARER):
            registro.obter().registrar_acesso_api("", "", recurso, recusado="credencial ausente")
            return recusa_json(
                "Credencial ausente — apresente o token como Authorization: Bearer tn_…",
                401,
            )

        valor = autorizacao[len(PREFIXO_BEARER) :].strip()
        try:
            token = registro.obter().verificar_token(valor)
        except InvalidoError as erro:
            partes = valor.split("_")
            prefixo = "_".join(partes[:2]) if valor.startswith("tn_") else ""
            registro.obter().registrar_acesso_api("", prefixo, recurso, recusado=str(erro))
            return recusa_json(str(erro), 401)

        identificador = token.get("ambiente", "")
        escolhido = registro.obter().obter(identificador)
        if not escolhido or escolhido.get("situacao") == "arquivado":
            # Arquivar suspende sem revogar: desarquivar devolve a
            # integração sem reemissão (decisão 13).
            registro.obter().registrar_acesso_api(
                identificador, token.get("prefixo", ""), recurso, recusado="ambiente arquivado"
            )
            return recusa_json("Este ambiente foi arquivado.", 403)

        registro.obter().registrar_acesso_api(identificador, token.get("prefixo", ""), recurso)
        registro.obter().registrar_uso(token.get("prefixo", ""))

        with ambiente.ambiente_ativo(identificador):
            return handler(req, token)

    return envolvido


@bp.route(route="dados/v1/saude", methods=["GET"])
def saude(req: func.HttpRequest) -> func.HttpResponse:
    """The connectivity probe of the space.

    Answers without the Alpine header and without any session cookie —
    the proof that the anonymous release at the border works. It is also
    the first call an integrator makes before wiring a dashboard.
    """
    return _json({"status": "ok"})


# ── Os quatro recursos ────────────────────────────────────────────────────


@bp.route(route="dados/v1/ambiente", methods=["GET"])
@com_token
def recurso_ambiente(req: func.HttpRequest, token: dict) -> func.HttpResponse:
    """The token's environment, and the week the app opens by default."""
    return _json(_envelope(token, {"semana_referencia": dados.semana_padrao()}))


def _semana_pedida(req: func.HttpRequest) -> str:
    """The week filter — optional since revision 4 (empty means every week).

    ``/atividades`` and ``/resumo`` used to refuse without it, on the
    theory that a request without a week would pull the whole base. That
    theory held while the whole base was the thing to avoid; the consumer
    that actually showed up wants exactly that, to build its own
    historical aggregate — so pulling it became the point, not the risk
    (spec revision 4). What still refuses is a malformed value, not an
    absent one.
    """
    return (req.params.get("semana") or "").strip()


def _atividades_pedidas(req: func.HttpRequest) -> list[dict]:
    """The rows both ``/atividades`` and ``/geral`` share.

    Semana optional (revision 4), plus the three filters. Split out so
    ``/geral`` reuses exactly this — same rows, same filters — instead of
    a second copy that could drift from the first.
    """
    semana = _semana_pedida(req)
    filtros = {
        campo: (req.params.get(campo) or "").strip() for campo in ("empresa", "local", "situacao")
    }
    return (
        dados.listar_atividades(None, semana, filtros)
        if semana
        else dados.listar_todas_atividades(None, filtros)
    )


@bp.route(route="dados/v1/atividades", methods=["GET"])
@com_token
def recurso_atividades(req: func.HttpRequest, token: dict) -> func.HttpResponse:
    """This week's activities, or every week's when ``semana`` is absent.

    The numbers come from the facade exactly as the screen sees them —
    the API reimplements no calculation. Filters: empresa, local,
    situação, and the now-optional semana.
    """
    return _json(_envelope(token, _atividades_pedidas(req)))


@bp.route(route="dados/v1/geral", methods=["GET"])
@com_token
def recurso_geral(req: func.HttpRequest, token: dict) -> func.HttpResponse:
    """The same rows as ``/atividades``, with the environment on each one.

    For consumers combining SEVERAL environments' responses into one
    table outside the app — Power BI, a warehouse — where the envelope's
    single ``ambiente`` block gets lost the moment two calls are stacked
    (spec revision 5). ``/atividades`` stays lean for the one-environment
    case; this pays the repetition on purpose.

    The token is still bound to one environment (decision 22 does not
    change): this never reads more than ``/atividades`` already would,
    it only repeats what the envelope already says on every line.
    """
    escolhido = registro.obter().obter(token["ambiente"]) or {}
    linhas = [
        {
            **atividade,
            "ambiente_id": escolhido.get("id", ""),
            "ambiente_projeto": escolhido.get("projeto", ""),
            "ambiente_cliente": escolhido.get("cliente", ""),
        }
        for atividade in _atividades_pedidas(req)
    ]
    return _json(_envelope(token, linhas))


@bp.route(route="dados/v1/resumo", methods=["GET"])
@com_token
def recurso_resumo(req: func.HttpRequest, token: dict) -> func.HttpResponse:
    """One week's summary, or the whole environment's when ``semana`` is absent.

    The per-week shape is the facade's ``resumo_semana`` unchanged — same
    numbers the home screen leads with. The all-time shape is assembled
    here from the same domain functions (``calculos.aderencia_geral``,
    ``ppc_medio``, ``quebrar_por``, ``dados.contagem_por_situacao``), never
    reimplemented: it is the one thing the per-week shape has that
    genuinely does not generalize. ``por_dia`` groups by weekday index
    (0-6) *within one week* — bucketing every Monday of every week
    together under one label would misrepresent dates that have nothing
    to do with each other, so the all-time shape omits it rather than
    compute something that looks like data and is not (revision 4).
    """
    semana = _semana_pedida(req)

    if semana:
        resumo = dados.resumo_semana(None, semana)
        atividades = dados.listar_atividades(None, semana)
        total_previsto = sum(a.get("total_previsto") or 0 for a in atividades)
        total_realizado = sum(a.get("total_realizado") or 0 for a in atividades)
        return _json(
            _envelope(
                token,
                {
                    "semana": resumo["semana"],
                    "periodo": resumo["periodo"],
                    "aderencia": resumo["aderencia"],
                    "faixa_aderencia": calculos.faixa(resumo["aderencia"]),
                    "ppc_medio": resumo["ppc_medio"],
                    "faixa_ppc": calculos.faixa(resumo["ppc_medio"]),
                    "total_previsto": total_previsto,
                    "total_realizado": total_realizado,
                    "total_atividades": resumo["total_atividades"],
                    "situacao": resumo["situacao"],
                    "por_dia": resumo["por_dia"],
                    "por_empresa": resumo["por_empresa"],
                },
            )
        )

    atividades = dados.listar_todas_atividades(None)
    aderencia = calculos.aderencia_geral(atividades)
    ppc_medio = calculos.ppc_medio(atividades)
    total_previsto = sum(a.get("total_previsto") or 0 for a in atividades)
    total_realizado = sum(a.get("total_realizado") or 0 for a in atividades)
    return _json(
        _envelope(
            token,
            {
                "semana": None,
                "periodo": None,
                "aderencia": aderencia,
                "faixa_aderencia": calculos.faixa(aderencia),
                "ppc_medio": ppc_medio,
                "faixa_ppc": calculos.faixa(ppc_medio),
                "total_previsto": total_previsto,
                "total_realizado": total_realizado,
                "total_atividades": len(atividades),
                "situacao": dados.contagem_por_situacao(atividades),
                "por_empresa": calculos.quebrar_por(atividades, "empresa"),
            },
        )
    )


@bp.route(route="dados/v1/cadastros", methods=["GET"])
@com_token
def recurso_cadastros(req: func.HttpRequest, token: dict) -> func.HttpResponse:
    """Locais, empresas e unidades do ambiente do token."""
    return _json(_envelope(token, dados.cadastros()))
