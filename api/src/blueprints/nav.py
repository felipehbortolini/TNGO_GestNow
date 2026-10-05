"""Navigation blueprint — renders the sidebar as a server fragment.

The sidebar replaced the horizontal navbar (decision D1): the 300px
sidebar is the Timenow standard shell. The pattern is unchanged — the
server still owns the links, so navigation can vary by role without
touching the shell.

Add a page: append one entry to ``NAV_ITEMS``. The icon name must exist
in ``app/ds/icons.js``.
"""

import azure.functions as func

from src.core.responses import (
    AlpineAjaxResponse,
    is_alpine_request,
    redirect_to,
)

bp = func.Blueprint()

SECTION_TITLE = "Timenow GestNow"

NAV_ITEMS = [
    {"href": "/_views/home.html", "rotulo": "Início", "icone": "layers"},
]


@bp.route(route="nav", methods=["GET"])
def main_nav(req: func.HttpRequest) -> func.HttpResponse:
    """Return the sidebar fragment."""
    if not is_alpine_request(req):
        return redirect_to("/index.html")

    return AlpineAjaxResponse(
        template_name="nav/sidebar.html",
        context={"secao": SECTION_TITLE, "itens": NAV_ITEMS},
        request=req,
    )
