"""Governança — the flow seen from above, plus the change-request queue.

The schedule screen answers "what is in this week". This one answers "who
is holding the line": which contractor is still drafting, which fiscal has
approvals waiting, which window is open right now.

It also carries the **Request → Apply** queue: published schedules and
approved reports stop being editable, and sometimes have to change anyway.
Without a queue that turns into a phone call to the administrator, who
edits it directly and leaves no trace. Here the request is written down —
who asked, why, and who decided.
"""

import contextlib

import azure.functions as func

from src.blueprints._comum import com_usuario, erro_de_dominio
from src.core import auditoria, auth, dados, rbac
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()


def _fila(req: func.HttpRequest, user: auth.Usuario, toast: str = "") -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name="governanca/pedidos.html",
        context={"user": user, **dados.listar_pedidos(user)},
        request=req,
        toast=toast or None,
    )


@bp.route(route="governanca", methods=["GET"])
@com_usuario(rbac.VER)
def painel(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name="governanca/painel.html",
        context={"user": user, "g": dados.governanca(user)},
        request=req,
    )


@bp.route(route="governanca-trilha", methods=["GET"])
@com_usuario(rbac.VER_AUDITORIA)
def trilha(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The audit trail — who changed what, and when."""
    limite = 40
    with contextlib.suppress(ValueError):
        limite = min(int(req.params.get("limite") or limite), 200)
    return AlpineAjaxResponse(
        template_name="governanca/trilha.html",
        context={"user": user, "eventos": auditoria.recentes(limite)},
        request=req,
    )


# ── Fila de pedidos de alteração ────────────────────────────────────────


@bp.route(route="pedidos", methods=["GET"])
@com_usuario(rbac.VER)
def pedidos(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The queue: what is waiting for a decision, and what was decided."""
    return _fila(req, user)


@bp.route(route="pedido", methods=["POST"])
@com_usuario(rbac.VER)
def abrir_pedido(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Ask for a change on an item that is already closed for editing."""
    form = req.form
    try:
        pedido = dados.pedir_alteracao(
            user,
            (req.params.get("chave") or form.get("chave") or "").strip(),
            (form.get("motivo") or "").strip(),
        )
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar(
        "pedido",
        user.email,
        f"pediu alteração em {pedido['id_exclusiva']}",
        {"key": pedido["key"], "semana": pedido["semana"]},
    )
    return _fila(req, user, toast=f"Pedido registrado para {pedido['id_exclusiva']}.")


@bp.route(route="pedido-decidir", methods=["POST"])
@com_usuario(rbac.APLICAR)
def decidir_pedido(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Apply or refuse. Applying reopens the item and records the decision."""
    form = req.form
    aplicar = (form.get("decisao") or "") == "aplicar"
    try:
        pedido = dados.resolver_pedido(
            user,
            (form.get("id") or "").strip(),
            aplicar=aplicar,
            resposta=(form.get("resposta") or "").strip(),
        )
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar(
        "pedido",
        user.email,
        f"{pedido['situacao']} o pedido de {pedido['id_exclusiva']}",
        {"key": pedido["key"]},
    )
    return _fila(
        req,
        user,
        toast=(
            f"{pedido['id_exclusiva']} liberado para alteração."
            if aplicar
            else f"Pedido de {pedido['id_exclusiva']} recusado."
        ),
    )
