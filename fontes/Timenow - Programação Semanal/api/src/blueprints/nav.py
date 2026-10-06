"""Sidebar — the navigation, built per profile on the server.

The server owns the links because the menu is part of the authorisation
surface: a contractor never sees "Configurações", and the item is absent
from the DOM rather than hidden by CSS. Adding a page is one entry in
``ITENS`` plus the permission that unlocks it.
"""

import azure.functions as func

from src.blueprints._comum import ambientes_da_pessoa, com_usuario, registro_do_ambiente_ativo
from src.core import auth, dados, rbac
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()

SECAO = "Programação semanal"

ITENS = (
    {"href": "/_views/home.html", "rotulo": "Início", "icone": "home", "permissao": rbac.VER},
    {
        "href": "/_views/programacao.html",
        "rotulo": "Programação",
        "icone": "table",
        "permissao": rbac.VER,
    },
    {
        "href": "/_views/dashboard.html",
        "rotulo": "Dashboard",
        "icone": "chart",
        "permissao": rbac.VER_DASHBOARD,
    },
    {
        "href": "/_views/importar.html",
        "rotulo": "Importar planilha",
        "icone": "upload",
        "permissao": rbac.IMPORTAR,
    },
    {
        "href": "/_views/governanca.html",
        "rotulo": "Governança",
        "icone": "shield",
        "permissao": rbac.VER,
    },
    {
        "href": "/_views/configuracoes.html",
        "rotulo": "Configurações",
        "icone": "gear",
        "permissao": rbac.VER_CONFIGURACOES,
    },
)


@bp.route(route="nav", methods=["GET"])
@com_usuario()
def main_nav(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Return the sidebar fragment, filtered by what the profile may open.

    The strip names the active environment from the register — the one
    source of the project name, so the sidebar never disagrees with the
    selector. Whoever may enter more than one environment gets the
    switch here; whoever has one does not receive the control at all.
    """
    itens = [item for item in ITENS if user.pode(item["permissao"])]

    projeto = registro_do_ambiente_ativo().get("projeto", "")

    trocaveis = ambientes_da_pessoa(user)
    return AlpineAjaxResponse(
        template_name="nav/sidebar.html",
        context={
            "secao": SECAO,
            "itens": itens,
            "user": user,
            "projeto": projeto,
            "trocaveis": trocaveis,
            "pode_trocar": len(trocaveis) > 1,
            "seguro": not auth.modo_demo(),
        },
        request=req,
    )


@bp.route(route="perfil-demo", methods=["GET"])
@com_usuario()
def perfil_demo(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """List the seeded profiles so a local run can be reviewed as each one.

    Only answers in demo mode. With a real identity provider the profile
    comes from the register and there is nothing to choose.

    Decorated like every other endpoint that reads the base: the register
    of collaborators now lives inside an environment, and without the
    decorator this one asks for it with no environment open — which fails
    closed, as it should.
    """
    if not auth.modo_demo():
        return AlpineAjaxResponse(template_name="comum/vazio.html", context={}, request=req)
    return AlpineAjaxResponse(
        template_name="nav/perfil_demo.html",
        context={
            "colaboradores": dados.listar_colaboradores(),
            "atual": user,
        },
        request=req,
    )
