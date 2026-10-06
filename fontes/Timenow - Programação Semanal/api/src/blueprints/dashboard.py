"""The dashboard — the week read as an operation, not as a list.

One endpoint per block instead of one big page, for the same reason as
the schedule screen: changing the contractor filter should redraw the
charts, not the filter bar the person is using.

The charts receive their numbers as a JSON payload embedded in the
fragment and are drawn by ``ds/charts.js``. It is the one deliberate
exception to "the server returns finished HTML": an S-curve that expands
a month on click and redraws on resize needs the series in the browser,
and shipping a static SVG would trade both behaviours for consistency
with a rule that exists to avoid client-side templating — which this is
not. Recorded in docs/ARCHITECTURE.md.
"""

import azure.functions as func

from src.blueprints._comum import com_usuario, registro_do_ambiente_ativo, semana_pedida
from src.core import auth, dados, indicadores, rbac, semanas
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()

SEMANAS_DO_HORIZONTE = 12


def _filtros(req: func.HttpRequest) -> dict:
    return {
        "empresa": (req.params.get("empresa") or "").strip(),
        "local": (req.params.get("local") or "").strip(),
        "encarregado": (req.params.get("encarregado") or "").strip(),
    }


def _horizonte(user: auth.Usuario, semana: str, filtros: dict) -> list[dict]:
    """Every week up to the selected one, so the curve has a past."""
    referencias = semanas.janela_de_semanas(semana, atras=SEMANAS_DO_HORIZONTE, adiante=0)
    atividades: list[dict] = []
    for referencia in referencias:
        atividades.extend(dados.listar_atividades(user, referencia, filtros))
    return atividades


def _contexto(user: auth.Usuario, req: func.HttpRequest) -> dict:
    semana = semana_pedida(req)
    filtros = _filtros(req)
    da_semana = dados.listar_atividades(user, semana, filtros)
    horizonte = _horizonte(user, semana, filtros)
    painel = indicadores.painel(da_semana, horizonte, dados.parametros())
    return {
        "user": user,
        "semana": semana,
        "periodo": semanas.periodo(semana),
        "filtros": filtros,
        "semanas": dados.horizonte_de_semanas(),
        "empresas": dados.listar_empresas(),
        "locais": dados.listar_locais(),
        "encarregados": dados.listar_encarregados(),
        "p": painel,
    }


@bp.route(route="dashboard", methods=["GET"])
@com_usuario(rbac.VER_DASHBOARD)
def painel_completo(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Indicators, curve, breakdowns and the bottleneck list."""
    return AlpineAjaxResponse(
        template_name="dashboard/painel.html",
        context=_contexto(user, req),
        request=req,
    )


@bp.route(route="dashboard-filtros", methods=["GET"])
@com_usuario(rbac.VER_DASHBOARD)
def filtros_do_painel(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    semana = semana_pedida(req)
    return AlpineAjaxResponse(
        template_name="dashboard/filtros.html",
        context={
            "user": user,
            "semana": semana,
            "semanas": dados.horizonte_de_semanas(),
            "filtros": _filtros(req),
            "empresas": dados.listar_empresas(),
            "locais": dados.listar_locais(),
            "encarregados": dados.listar_encarregados(),
        },
        request=req,
    )


@bp.route(route="home-resumo", methods=["GET"])
@com_usuario(rbac.VER)
def resumo_inicial(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """What the home screen leads with: the week, in one glance."""
    semana = semana_pedida(req)
    resumo = dados.resumo_semana(user, semana)
    atividades = dados.listar_atividades(user, semana)
    return AlpineAjaxResponse(
        template_name="home/resumo.html",
        context={
            "user": user,
            "r": resumo,
            "janela": dados.situacao_da_janela(user, semana),
            "status": indicadores.distribuicao_por_situacao(atividades),
            "turnos": indicadores.turnos(atividades),
            "projeto": registro_do_ambiente_ativo().get("projeto", ""),
        },
        request=req,
    )
