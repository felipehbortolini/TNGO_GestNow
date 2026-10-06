"""One activity — the drawers and every transition of the flow.

Each mutation answers with the same multi-target fragment: the drawer
(empty on success, re-rendered with the errors on 422), the indicator
strip and the matrix. That is what keeps the screen coherent after a
save without the page having to reload — and it is the reason the drawer
is a target and not a free-floating overlay.

The activity key travels in the query string, never in the path. It
carries ``::`` and comes from a field the person types, and a path
segment would drag URL encoding into every route, every template and the
local development server.
"""

import azure.functions as func

from src.blueprints._comum import (
    campos_do_formulario,
    com_usuario,
    dias_do_formulario,
    erro_de_dominio,
    filtros_pedidos,
    semana_pedida,
)
from src.blueprints.programacao import contexto_da_tabela, contexto_do_resumo
from src.core import auditoria, auth, calculos, dados, rbac, semanas
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()

CAMPOS_ATIVIDADE = (
    "id_exclusiva",
    "atividade",
    "local",
    "empresa",
    "encarregado",
    "responsavel",
    "unidade",
    "prod_prevista",
    "observacoes",
    "semana",
)


def _chave(req: func.HttpRequest) -> str:
    return (req.params.get("chave") or "").strip()


def _resposta_da_tela(
    req: func.HttpRequest,
    user: auth.Usuario,
    *,
    painel: tuple[str, dict] | None = None,
    toast: str = "",
    status: int = 200,
) -> func.HttpResponse:
    """The three blocks the screen expects back from any mutation.

    ``painel`` é o par (template, contexto) do drawer, e viaja junto
    porque um sem o outro não renderiza nada: passá-los separados
    permitiria o estado meio-preenchido que não existe.
    Sem ``painel``, o drawer volta vazio — que é como ele se fecha.
    """
    template, contexto = painel or (None, {})
    return AlpineAjaxResponse(
        template_name="programacao/multi.html",
        context={
            "incluir_drawer": True,
            "drawer": template,
            **contexto,
            **contexto_do_resumo(user, req),
            **contexto_da_tabela(user, req),
        },
        request=req,
        status_code=status,
        toast=toast or None,
    )


def _contexto_form(user: auth.Usuario, atividade: dict, semana: str, erros: dict) -> dict:
    empresas = [user.empresa] if user.eh_fornecedor() else dados.listar_empresas()
    return {
        "user": user,
        "atividade": atividade,
        "nova": not atividade.get("key"),
        "semana": semana,
        "periodo": semanas.periodo(semana),
        "datas": semanas.datas_dos_dias(semana),
        "proximo_item": atividade.get("item") or dados.proximo_item(semana),
        "locais": dados.listar_locais(),
        "empresas": empresas,
        "unidades": dados.listar_unidades(),
        "encarregados": dados.listar_encarregados(),
        "fiscais": dados.listar_fiscais(),
        "erros": erros or {},
        "filtros": {},
    }


# ── Abertura dos painéis ────────────────────────────────────────────────


@bp.route(route="atividade-form", methods=["GET"])
@com_usuario(rbac.EDITAR)
def formulario(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The create/edit drawer."""
    chave = _chave(req)
    semana = semana_pedida(req)

    if chave:
        atividade = dados.obter_atividade(user, chave)
        if not atividade:
            return erro_de_dominio(dados.InvalidoError("Atividade não encontrada."), req)
        semana = atividade["semana"]
        if atividade["situacao"] == "publicada" and not user.pode(rbac.PUBLICAR):
            return erro_de_dominio(
                dados.RecusadoError("Programação publicada não pode ser editada."), req
            )
    else:
        if not user.pode(rbac.GERAR):
            return erro_de_dominio(dados.RecusadoError("Seu perfil não cria programação."), req)
        liberado, motivo = dados.pode_programar(user, semana)
        if not liberado:
            return erro_de_dominio(dados.RecusadoError(motivo), req)
        atividade = {
            "dias_previsto": [0.0] * calculos.NUM_DIAS,
            "empresa": user.empresa if user.eh_fornecedor() else "",
        }

    return AlpineAjaxResponse(
        template_name="atividade/form.html",
        context=_contexto_form(user, atividade, semana, {}),
        request=req,
    )


@bp.route(route="atividade-realizado", methods=["GET"])
@com_usuario(rbac.REGISTRAR_REALIZADO)
def realizado_form(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The reporting drawer — the screen most people touch."""
    atividade = dados.obter_atividade(user, _chave(req))
    if not atividade:
        return erro_de_dominio(dados.InvalidoError("Atividade não encontrada."), req)
    if atividade["aprovacao_realizado"] == "aprovado":
        return erro_de_dominio(
            dados.RecusadoError("O realizado já foi aprovado e não pode ser alterado."), req
        )
    if atividade["situacao"] == "em_elaboracao":
        return erro_de_dominio(
            dados.RecusadoError(
                "Esta programação ainda não foi validada pelo planejador. "
                "O realizado só é aceito depois da validação."
            ),
            req,
        )

    config = dados.parametros()
    return AlpineAjaxResponse(
        template_name="atividade/realizado.html",
        context={
            "user": user,
            "atividade": atividade,
            "semana": atividade["semana"],
            "datas": semanas.datas_dos_dias(atividade["semana"]),
            "limite_desvio": calculos.numero(config.get("limite_desvio_justificativa"), 15.0),
            "exige_justificativa": bool(config.get("exige_justificativa_desvio")),
            "erros": {},
        },
        request=req,
    )


@bp.route(route="atividade-validar", methods=["GET"])
@com_usuario(rbac.VALIDAR)
def validar_form(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    atividade = dados.obter_atividade(user, _chave(req))
    if not atividade:
        return erro_de_dominio(dados.InvalidoError("Atividade não encontrada."), req)
    return AlpineAjaxResponse(
        template_name="atividade/validar.html",
        context={
            "user": user,
            "atividade": atividade,
            "fiscais": dados.listar_fiscais(),
            "erros": {},
        },
        request=req,
    )


@bp.route(route="atividade-aprovar", methods=["GET"])
@com_usuario(rbac.APROVAR_REALIZADO)
def aprovar_form(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    atividade = dados.obter_atividade(user, _chave(req))
    if not atividade:
        return erro_de_dominio(dados.InvalidoError("Atividade não encontrada."), req)
    return AlpineAjaxResponse(
        template_name="atividade/aprovar.html",
        context={
            "user": user,
            "atividade": atividade,
            "datas": semanas.datas_dos_dias(atividade["semana"]),
            "erros": {},
        },
        request=req,
    )


@bp.route(route="atividade-detalhe", methods=["GET"])
@com_usuario(rbac.VER)
def detalhe(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Read-only panel: the whole activity plus its trail."""
    atividade = dados.obter_atividade(user, _chave(req))
    if not atividade:
        return erro_de_dominio(dados.InvalidoError("Atividade não encontrada."), req)
    return AlpineAjaxResponse(
        template_name="atividade/detalhe.html",
        context={
            "user": user,
            "atividade": atividade,
            "datas": semanas.datas_dos_dias(atividade["semana"]),
            "eventos": auditoria.recentes(20, chave=atividade["key"]),
        },
        request=req,
    )


# ── Transições ──────────────────────────────────────────────────────────


@bp.route(route="atividade", methods=["POST"])
@com_usuario(rbac.EDITAR)
def salvar(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Create or update, and hand the screen back consistent."""
    chave = _chave(req)
    form = req.form
    payload = campos_do_formulario(form, CAMPOS_ATIVIDADE)
    payload["dias_previsto"] = dias_do_formulario(form, "dias_previsto")
    semana = payload.get("semana") or semana_pedida(req)

    try:
        if chave:
            atividade = dados.salvar_atividade(user, chave, payload)
            auditoria.registrar(
                "editar",
                user.email,
                atividade["id_exclusiva"],
                {"key": atividade["key"], "semana": atividade["semana"]},
            )
            mensagem = f"Atividade {atividade['id_exclusiva']} atualizada."
        else:
            atividade = dados.criar_atividade(user, payload)
            auditoria.registrar(
                "criar",
                user.email,
                atividade["id_exclusiva"],
                {"key": atividade["key"], "semana": atividade["semana"]},
            )
            mensagem = f"Atividade {atividade['id_exclusiva']} criada."
    except dados.InvalidoError as erro:
        detalhe_erro = erro.args[0] if erro.args else {}
        erros = detalhe_erro if isinstance(detalhe_erro, dict) else {"_": str(detalhe_erro)}
        atual = dados.obter_atividade(user, chave) if chave else {}
        return _resposta_da_tela(
            req,
            user,
            painel=(
                "atividade/_form.html",
                _contexto_form(user, {**(atual or {}), **payload}, semana, erros),
            ),
            toast="Confira os campos destacados.",
            status=422,
        )
    except dados.RecusadoError as erro:
        return erro_de_dominio(erro, req)

    return _resposta_da_tela(req, user, toast=mensagem)


@bp.route(route="atividade-realizado", methods=["POST"])
@com_usuario(rbac.REGISTRAR_REALIZADO)
def salvar_realizado(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    chave = _chave(req)
    form = req.form
    try:
        atividade = dados.registrar_realizado(
            user,
            chave,
            dias_do_formulario(form, "dias_realizado"),
            dias_do_formulario(form, "dias_noite"),
            (form.get("observacoes") or "").strip(),
        )
    except dados.InvalidoError as erro:
        return _resposta_do_realizado(req, user, chave, erro)
    except dados.RecusadoError as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar(
        "realizado",
        user.email,
        atividade["id_exclusiva"],
        {"key": atividade["key"], "ppc": atividade["ppc"]},
    )
    return _resposta_da_tela(
        req,
        user,
        toast=(
            f"Realizado de {atividade['id_exclusiva']} registrado — PPC de {atividade['ppc']:.0f}%."
        ),
    )


def _resposta_do_realizado(
    req: func.HttpRequest, user: auth.Usuario, chave: str, erro: Exception
) -> func.HttpResponse:
    """422 of the reporting drawer, with the typed values kept."""
    atividade = dados.obter_atividade(user, chave) or {}
    detalhe_erro = erro.args[0] if erro.args else {}
    erros = detalhe_erro if isinstance(detalhe_erro, dict) else {"_": str(detalhe_erro)}
    form = req.form
    atividade["dias_realizado"] = dias_do_formulario(form, "dias_realizado")
    atividade["dias_noite"] = dias_do_formulario(form, "dias_noite")
    atividade["observacoes_fornecedor"] = (form.get("observacoes") or "").strip()
    calculos.preencher_calculados(atividade)
    config = dados.parametros()
    return _resposta_da_tela(
        req,
        user,
        painel=(
            "atividade/_realizado.html",
            {
                "atividade": atividade,
                "datas": semanas.datas_dos_dias(atividade.get("semana", "")),
                "limite_desvio": calculos.numero(config.get("limite_desvio_justificativa"), 15.0),
                "exige_justificativa": bool(config.get("exige_justificativa_desvio")),
                "erros": erros,
            },
        ),
        toast="Confira o lançamento antes de salvar.",
        status=422,
    )


@bp.route(route="atividade-validar", methods=["POST"])
@com_usuario(rbac.VALIDAR)
def salvar_validacao(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    form = req.form
    try:
        atividade = dados.validar_atividade(
            user,
            _chave(req),
            (form.get("responsavel") or "").strip(),
            (form.get("comentarios") or "").strip(),
        )
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar(
        "validar",
        user.email,
        atividade["id_exclusiva"],
        {"key": atividade["key"], "fiscal": atividade["responsavel"]},
    )
    return _resposta_da_tela(
        req,
        user,
        toast=f"{atividade['id_exclusiva']} validada para {atividade['responsavel']}.",
    )


@bp.route(route="atividade-aprovar", methods=["POST"])
@com_usuario(rbac.APROVAR_REALIZADO)
def salvar_aprovacao(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    form = req.form
    try:
        atividade = dados.aprovar_realizado(
            user, _chave(req), (form.get("comentarios") or "").strip()
        )
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar("aprovar", user.email, atividade["id_exclusiva"], {"key": atividade["key"]})
    return _resposta_da_tela(req, user, toast=f"Realizado de {atividade['id_exclusiva']} aprovado.")


@bp.route(route="atividade-reabrir", methods=["POST"])
@com_usuario(rbac.APROVAR_REALIZADO)
def reabrir(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    # O motivo pode chegar pelo corpo ou pela consulta: a reabertura é
    # disparada de um painel de leitura, que não tem formulário próprio.
    motivo = (req.form.get("motivo") or req.params.get("motivo") or "").strip()
    try:
        atividade = dados.reabrir_realizado(user, _chave(req), motivo)
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar("reabrir", user.email, atividade["id_exclusiva"], {"key": atividade["key"]})
    return _resposta_da_tela(req, user, toast=f"Realizado de {atividade['id_exclusiva']} reaberto.")


@bp.route(route="atividade-publicar", methods=["POST"])
@com_usuario(rbac.PUBLICAR)
def publicar(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    try:
        atividade = dados.publicar_atividade(user, _chave(req))
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar(
        "publicar", user.email, atividade["id_exclusiva"], {"key": atividade["key"]}
    )
    return _resposta_da_tela(req, user, toast=f"{atividade['id_exclusiva']} publicada.")


@bp.route(route="atividade-excluir", methods=["POST"])
@com_usuario(rbac.EXCLUIR)
def excluir(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    try:
        atividade = dados.excluir_atividade(user, _chave(req))
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar("excluir", user.email, atividade["id_exclusiva"], {"key": atividade["key"]})
    return _resposta_da_tela(req, user, toast=f"{atividade['id_exclusiva']} excluída.", status=200)


@bp.route(route="atividade-publicar-semana", methods=["POST"])
@com_usuario(rbac.PUBLICAR)
def publicar_semana(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Publish every validated activity of the week in one action.

    Publishing one by one is the kind of repetition that gets abandoned
    halfway, leaving a week half published — which reads as a data
    problem and is really a workflow problem.
    """
    semana = semana_pedida(req)
    filtros = filtros_pedidos(req)
    publicadas = 0
    for atividade in dados.listar_atividades(user, semana, filtros):
        if atividade["situacao"] != "validada":
            continue
        try:
            dados.publicar_atividade(user, atividade["key"])
            publicadas += 1
        except (dados.InvalidoError, dados.RecusadoError):
            continue

    auditoria.registrar(
        "publicar", user.email, f"{publicadas} atividade(s) em {semana}", {"semana": semana}
    )
    mensagem = (
        f"{publicadas} programação(ões) publicada(s)."
        if publicadas
        else "Nenhuma programação validada aguardando publicação."
    )
    return _resposta_da_tela(req, user, toast=mensagem)
