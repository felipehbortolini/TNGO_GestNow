"""What every blueprint of this application repeats.

Five things happen at the top of every fragment endpoint: gate the direct
access, resolve the ACTIVE ENVIRONMENT, resolve the user, refuse what the
profile may not do, and turn a domain error into the right status code.
Written once here, each route below is left with only its own subject.

The environment comes before the user, and the order is not negotiable:
the user resolution reads the collaborator register, which now lives
INSIDE an environment — inverted, the order would resolve the person
against the wrong environment.

Naming: the module starts with an underscore because it is not a
blueprint — ``function_app.py`` registers every other module in this
folder, and this one has nothing to register.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from urllib.parse import quote

import azure.functions as func

from src.core import ambiente, auth, calculos, dados, registro
from src.core.responses import AlpineAjaxResponse, is_alpine_request, redirect_to

COOKIE_AMBIENTE = "tn_ambiente"
CABECALHO_AMBIENTE = "X-TN-Ambiente"
PARAMETRO_AMBIENTE = "ambiente"

MENSAGEM_SEM_EMAIL = "A sua sessão do Azure não trouxe um endereço de e-mail."
MENSAGEM_ARQUIVADO = "Este ambiente foi arquivado."
MENSAGEM_ABA_VELHA = "Esta aba está em outro ambiente."
MENSAGEM_SEM_PERMISSAO = "Seu perfil não tem acesso a esta área. Peça a liberação ao administrador."


class AmbienteRecusadoError(Exception):
    """The request's environment did not hold up — the shell must reload.

    Carries the message the selector will show. The one refusal that
    must NOT be painted inside the caller's fragment: the rest of the
    screen would keep showing the matrix of the wrong environment with
    the sidebar naming it.
    """


def _sem_permissao(req: func.HttpRequest, mensagem: str, status: int = 403) -> func.HttpResponse:
    """A guard screen rendered into whatever the caller asked for.

    Uses the caller's ``x-target`` instead of forcing ``app-shell``: a
    refused sidebar must land in the sidebar, not blank the page around
    it. Alpine AJAX empties any declared target missing from the
    response, so answering with the wrong id costs the whole screen.
    """
    return AlpineAjaxResponse(
        template_name="comum/recusado.html",
        context={"mensagem": mensagem},
        request=req,
        status_code=status,
        toast=mensagem,
        toast_tipo="erro",
    )


# ── O ambiente ativo ──────────────────────────────────────────────────────


def _slug_do_cookie(req: func.HttpRequest) -> str:
    bruto = req.headers.get("Cookie") or ""
    for pedaco in bruto.split(";"):
        nome, _, valor = pedaco.strip().partition("=")
        if nome == COOKIE_AMBIENTE:
            return valor.strip()
    return ""


def _slug_declarado(req: func.HttpRequest) -> str:
    """The slug the client SAYS it belongs to — header, then query.

    The header rides every Alpine AJAX request and exists because of
    tabs: a cookie is state per browser, and without the header a tab
    would be silently re-pointed when another tab switches. The two
    downloads and the printable report are real browser navigations
    without the Alpine header; they carry the slug in the query.
    """
    declarado = (req.headers.get(CABECALHO_AMBIENTE) or "").strip()
    if not declarado:
        declarado = (req.params.get(PARAMETRO_AMBIENTE) or "").strip()
    return declarado


def resolver_ambiente(req: func.HttpRequest) -> str:
    """The slug the request runs in, validated against the register.

    The cookie is a hint, never an authorization: the environment must
    exist, be active, and the authenticated e-mail must be a member of
    it — unless it is an operator, who enters every environment
    implicitly. A header (or query) diverging from the cookie refuses:
    that tab was left behind by a switch in another one.

    Raises :class:`AmbienteRecusadoError` with the message the selector will
    show. A request without any choice yet raises with an empty message
    — landing on the selector IS the answer, not an error to explain.
    """
    identidade = auth.identidade_da_requisicao(req)
    if not identidade:
        raise AmbienteRecusadoError(MENSAGEM_SEM_EMAIL)

    slug = _slug_do_cookie(req)
    escolhido = registro.obter().obter(slug) if slug else None
    if not escolhido:
        raise AmbienteRecusadoError("")
    if escolhido.get("situacao") == "arquivado":
        raise AmbienteRecusadoError(MENSAGEM_ARQUIVADO)
    if identidade.email not in escolhido.get("membros", []) and not identidade.operador:
        raise AmbienteRecusadoError(
            f"O e-mail {identidade.email} não consta no registro de ambientes."
        )

    declarado = _slug_declarado(req)
    if declarado and declarado != slug:
        raise AmbienteRecusadoError(MENSAGEM_ABA_VELHA)
    return slug


def _recusa_de_ambiente(mensagem: str) -> func.HttpResponse:
    """An environment refusal reloads the shell — it never paints a fragment.

    Reuses the full reload the fragment gate already triggers; the boot
    runs again and the selector appears with the message. Unsaved work
    in the tab is lost, which is the correct outcome: it belonged to
    another environment.
    """
    destino = "/index.html" + (f"?recusa={quote(mensagem)}" if mensagem else "")
    return redirect_to(destino)


# ── Os dois decoradores ───────────────────────────────────────────────────


def registro_do_ambiente_ativo() -> dict:
    """The active environment's registry record — the name's only source.

    The project and client names live in the register (decision 4), not
    in the environment's parameters. Every screen that names the
    environment reads it from here, so a renamed client changes every
    reader without touching the base.
    """
    return registro.obter().obter(ambiente.slug_ativo()) or {}


def ambientes_da_pessoa(usuario: auth.Usuario) -> list[dict]:
    """The environments one person may enter — the selector's list.

    The operator sees every active one; everybody else sees the active
    environments where the register lists them as member. The sidebar's
    switch and the selector must always agree, so both call this.
    """
    if usuario.operador:
        return [a for a in registro.obter().listar_todos() if a.get("situacao") == "ativo"]
    return registro.obter().listar_por_email(usuario.email)


def com_sessao(handler: Callable) -> Callable:
    """Gate and identity — for what runs WITHOUT an environment.

    The selector and the register administration sit above every
    environment: they cannot resolve the user against a collaborator
    register, because there is no environment to pick it from. So this
    resolves identity only — the e-mail the provider delivered, plus the
    operator marking from the deployment config — and consults nothing
    else. In demo mode the identity is fixed and always operator, since
    the local run has no identity provider at all.
    """

    @functools.wraps(handler)
    def envolvido(req: func.HttpRequest) -> func.HttpResponse:
        if not is_alpine_request(req):
            return redirect_to("/index.html")

        usuario = auth.identidade_da_requisicao(req)
        if not usuario:
            return _sem_permissao(req, MENSAGEM_SEM_EMAIL, status=401)
        return handler(req, usuario)

    return envolvido


def _mensagem_fora_do_cadastro(email: str, slug: str) -> str:
    projeto = "este projeto"
    escolhido = registro.obter().obter(slug)
    if escolhido:
        projeto = escolhido.get("projeto") or projeto
    return f"O e-mail {email} não consta no cadastro de colaboradores de {projeto}."


def com_usuario(
    permissao: str | None = None,
) -> Callable[[Callable], Callable]:
    """Gate, environment, sign in and authorise — in that order.

    Returns a decorator that hands the handler ``(req, user)`` and never
    a half-resolved state: if it runs, the environment is open, the
    caller exists and may do it. The environment stays open exactly for
    the handler's lifetime and is reset afterwards, exception included.
    """

    def decorador(handler: Callable) -> Callable:
        # `functools.wraps` e não atribuição manual de __name__: o modelo
        # V2 do Azure Functions usa o nome da função como nome da rota
        # registrada, e perdê-lo aqui registraria dez rotas chamadas
        # "envolvido".
        @functools.wraps(handler)
        def envolvido(req: func.HttpRequest) -> func.HttpResponse:
            if not is_alpine_request(req):
                return redirect_to("/index.html")

            try:
                slug = resolver_ambiente(req)
            except AmbienteRecusadoError as recusa:
                mensagem = recusa.args[0] if recusa.args else ""
                return _recusa_de_ambiente(mensagem)

            identidade = auth.identidade_da_requisicao(req) or auth.Usuario()
            with ambiente.ambiente_ativo(slug):
                user = auth.usuario_da_requisicao(req)
                if not user:
                    return _sem_permissao(
                        req,
                        _mensagem_fora_do_cadastro(identidade.email, slug),
                        status=401,
                    )

                if permissao and not user.pode(permissao):
                    return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

                return handler(req, user)

        return envolvido

    return decorador


def com_download(
    permissao: str | None = None,
) -> Callable[[Callable], Callable]:
    """Environment and permission for the two downloads — without the gate.

    A download is a real browser navigation: it arrives without the
    Alpine header, and gating it would bounce every click to the shell.
    The environment comes from the query and is checked exactly like
    everywhere else; the permission check stays.
    """

    def decorador(handler: Callable) -> Callable:
        @functools.wraps(handler)
        def envolvido(req: func.HttpRequest) -> func.HttpResponse:
            try:
                slug = resolver_ambiente(req)
            except AmbienteRecusadoError as recusa:
                mensagem = recusa.args[0] if recusa.args else ""
                return _recusa_de_ambiente(mensagem)

            with ambiente.ambiente_ativo(slug):
                user = auth.usuario_da_requisicao(req)
                if not user:
                    return redirect_to("/index.html")
                if permissao and not user.pode(permissao):
                    return func.HttpResponse("Sem permissão para esta operação.", status_code=403)
                return handler(req, user)

        return envolvido

    return decorador


def erro_de_dominio(erro: Exception, req: func.HttpRequest) -> func.HttpResponse:
    """Turn a domain exception into the fragment the screen expects.

    ``RecusadoError`` → 403, ``InvalidoError`` → 422. Both render the same block, so
    the person reads the reason where the action was, not in a toast that
    disappears.
    """
    recusado = isinstance(erro, dados.RecusadoError)
    detalhe = erro.args[0] if erro.args else ""
    mensagens = list(detalhe.values()) if isinstance(detalhe, dict) else [str(detalhe)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": [m for m in mensagens if m]},
        request=req,
        status_code=403 if recusado else 422,
        toast=mensagens[0] if mensagens else "Não foi possível concluir.",
        toast_tipo="erro",
    )


def semana_pedida(req: func.HttpRequest) -> str:
    return (req.params.get("semana") or "").strip() or dados.semana_padrao()


def filtros_pedidos(req: func.HttpRequest) -> dict:
    """The filter set of the schedule screen, read straight from the query."""
    campos = (
        "local",
        "empresa",
        "encarregado",
        "responsavel",
        "situacao",
        "aprovacao",
        "ppc",
        "busca",
        "ordena",
        "ordem",
    )
    return {campo: (req.params.get(campo) or "").strip() for campo in campos}


def dias_do_formulario(form, prefixo: str) -> list[float]:
    """Read ``prefixo_0`` … ``prefixo_6`` out of a submitted form."""
    return calculos.sete_dias([form.get(f"{prefixo}_{i}", "0") for i in range(calculos.NUM_DIAS)])


def campos_do_formulario(form, nomes: tuple[str, ...]) -> dict:
    return {nome: (form.get(nome) or "").strip() for nome in nomes}
