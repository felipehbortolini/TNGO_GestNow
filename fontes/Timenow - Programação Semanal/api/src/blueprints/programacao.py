"""The schedule screen — window banner, filters, indicators and matrix.

Four fragments, four addresses, because they change for different
reasons: the banner follows the clock, the filters follow the registers,
and the indicators and the matrix follow the data. Loading them
separately is what lets a filter redraw the table without rebuilding the
page around it.
"""

import azure.functions as func

from src.blueprints._comum import com_usuario, filtros_pedidos, semana_pedida
from src.core import auth, calculos, dados, rbac, semanas
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()


def contexto_da_tabela(user: auth.Usuario, req: func.HttpRequest) -> dict:
    semana = semana_pedida(req)
    filtros = filtros_pedidos(req)
    atividades = dados.listar_atividades(user, semana, filtros)
    todas = dados.listar_atividades(user, semana)
    return {
        "user": user,
        "semana": semana,
        "periodo": semanas.periodo(semana),
        "datas": semanas.datas_dos_dias(semana),
        "atividades": atividades,
        "filtros": filtros,
        "filtrando": any(
            filtros.get(c)
            for c in (
                "local",
                "empresa",
                "encarregado",
                "responsavel",
                "situacao",
                "aprovacao",
                "ppc",
                "busca",
            )
        ),
        "total_na_semana": len(todas),
        "janela": dados.situacao_da_janela(user, semana),
    }


def contexto_do_resumo(user: auth.Usuario, req: func.HttpRequest) -> dict:
    semana = semana_pedida(req)
    atividades = dados.listar_atividades(user, semana)
    config = dados.parametros()
    return {
        "user": user,
        "semana": semana,
        "total": len(atividades),
        "aderencia": calculos.aderencia_geral(atividades),
        "ppc_medio": calculos.ppc_medio(atividades),
        "meta_aderencia": calculos.numero(config.get("meta_aderencia"), 60.0),
        "situacao": dados.contagem_por_situacao(atividades),
        "filtros": filtros_pedidos(req),
    }


@bp.route(route="programacao", methods=["GET"])
@com_usuario(rbac.VER)
def tabela(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Indicators and matrix together — the pair every filter refreshes."""
    return AlpineAjaxResponse(
        template_name="programacao/multi.html",
        context={
            "incluir_drawer": False,
            **contexto_do_resumo(user, req),
            **contexto_da_tabela(user, req),
        },
        request=req,
    )


@bp.route(route="programacao-resumo", methods=["GET"])
@com_usuario(rbac.VER)
def resumo(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The KPI strip on its own — used by the first paint."""
    return AlpineAjaxResponse(
        template_name="programacao/resumo.html",
        context=contexto_do_resumo(user, req),
        request=req,
    )


@bp.route(route="programacao-filtros", methods=["GET"])
@com_usuario(rbac.VER)
def filtros(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The toolbar: week, search and the refinement panel."""
    semana = semana_pedida(req)
    return AlpineAjaxResponse(
        template_name="programacao/filtros.html",
        context={
            "user": user,
            "semana": semana,
            "semanas": dados.horizonte_de_semanas(),
            "periodo": semanas.periodo(semana),
            "filtros": filtros_pedidos(req),
            "locais": dados.listar_locais(),
            "empresas": dados.listar_empresas(),
            "encarregados": dados.listar_encarregados(),
            "fiscais": dados.listar_fiscais(),
            "janela": dados.situacao_da_janela(user, semana),
        },
        request=req,
    )


@bp.route(route="programacao-janela", methods=["GET"])
@com_usuario(rbac.VER)
def aviso_de_janela(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Whether this user may write to this week, and why."""
    semana = semana_pedida(req)
    return AlpineAjaxResponse(
        template_name="programacao/janela.html",
        context={
            "user": user,
            "semana": semana,
            "periodo": semanas.periodo(semana),
            "janela": dados.situacao_da_janela(user, semana),
        },
        request=req,
    )
