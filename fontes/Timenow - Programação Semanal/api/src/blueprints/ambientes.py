"""The environment selector — and the operator area that administers it.

The selector is the first screen after SSO: one box per environment the
caller may enter. Choosing writes the environment cookie and reloads to
the destination the boot preserved.

The operator area lives INSIDE the selector — decision 17: the register
administration is not the Configurações screen, which keeps being the
administration of THAT environment. Every route here runs on
``com_sessao``: before any environment exists there is no collaborator
register to consult, and the only rule the screen applies is the one the
port already enforces.
"""

from __future__ import annotations

from datetime import datetime

import azure.functions as func

from src.blueprints._comum import (
    MENSAGEM_SEM_PERMISSAO,
    _recusa_de_ambiente,
    _sem_permissao,
    ambientes_da_pessoa,
    com_sessao,
)
from src.core import ambiente, auth, dados, rbac, registro, repositorio
from src.core.dados import InvalidoError
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()

ROTULOS_ABAS = (
    ("/api/ambientes-administracao", "Ambientes", "table"),
    ("/api/ambientes-criar", "Criar ambiente", "add"),
    ("/api/ambientes-tokens", "Tokens", "key"),
    ("/api/ambientes-operadores", "Operadores", "shield"),
)


def _abas(ativa: str) -> list[dict]:
    return [
        {"href": href, "rotulo": rotulo, "icone": icone, "ativa": href.endswith(ativa)}
        for href, rotulo, icone in ROTULOS_ABAS
    ]


def _exigir_operador(usuario: auth.Usuario) -> bool:
    return usuario.pode(rbac.GERIR_REGISTRO)


# ── O seletor ─────────────────────────────────────────────────────────────


@bp.route(route="ambientes-seletor", methods=["GET"])
@com_sessao
def seletor(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    """The selector fragment: one box per environment, or the explanation.

    The selector is the permanent landing screen (revision 3, item 3):
    every new visit chooses, **including whoever has a single
    environment**. The auto-entry that used to skip this screen is gone
    on purpose — the click that "has no alternative" stopped being a
    nuisance and became the conscious confirmation of which client the
    person is about to work on.
    """
    destino = (req.params.get("destino") or "").strip()
    recusa = (req.params.get("recusa") or "").strip()

    return AlpineAjaxResponse(
        template_name="ambientes/seletor.html",
        context={
            "ambientes": ambientes_da_pessoa(usuario),
            "destino": destino,
            "recusa": recusa,
            "operador": usuario.operador,
            "seguro": not auth.modo_demo(),
        },
        request=req,
        root_class="content",
    )


@bp.route(route="ambiente-escolher", methods=["POST"])
@com_sessao
def escolher(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    """Validate one choice and point the reload at the preserved destination.

    The cookie itself is written by the client — the same readable-by-JS
    mechanism as the demo profile cookie (decision 5, annotated in
    revision 2.1). Here the choice is checked against the register: the
    environment exists, is active, and the caller may enter it.
    """
    identificador = (req.form.get("ambiente") or "").strip()
    destino = (req.form.get("destino") or "").strip()

    escolhido = registro.obter().obter(identificador)
    if not escolhido or escolhido.get("situacao") != "ativo":
        return _recusa_de_ambiente("Escolha inválida de ambiente.")

    # A entrada reconcilia o índice com o cadastro daquele ambiente
    # (revisão 3, item 1). Vem ANTES da conferência de propósito: um
    # índice que divergiu — base editada à mão, gravação interrompida,
    # ambiente criado antes de o pertencimento mudar de casa — não pode
    # trancar do lado de fora quem está cadastrado lá dentro.
    with ambiente.ambiente_ativo(identificador):
        dados.sincronizar_acesso(usuario.email)

    pode_entrar = any(a.get("id") == identificador for a in ambientes_da_pessoa(usuario))
    if not pode_entrar:
        return _recusa_de_ambiente("Escolha inválida de ambiente.")

    if not destino.startswith("/") or destino.startswith("//"):
        destino = "/"
    return func.HttpResponse(status_code=302, headers={"Location": destino})


# ── A área do operador ────────────────────────────────────────────────────


def _pessoas_com_acesso(identificador: str) -> int:
    with ambiente.ambiente_ativo(identificador):
        colaboradores = repositorio.obter().listar_colaboradores()
    return auth.conta_pessoas_com_acesso(colaboradores)


@bp.route(route="ambientes-administracao", methods=["GET"])
@com_sessao
def administracao(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    """Every environment of the installation, active and archived alike.

    The count of people with access includes the operators — the screen
    must not lie about who has the most power. The operator enters every
    environment implicitly, so an environment nobody was granted still
    shows at least the operator count.
    """
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)
    return _listagem(req, usuario)


def _listagem(
    req: func.HttpRequest,
    usuario: auth.Usuario,
    toast: str = "",
) -> func.HttpResponse:
    linhas = []
    for ambiente_registrado in registro.obter().listar_todos():
        linhas.append(
            {
                **ambiente_registrado,
                "pessoas": _pessoas_com_acesso(ambiente_registrado["id"]),
            }
        )
    return AlpineAjaxResponse(
        template_name="ambientes/lista.html",
        context={"usuario": usuario, "abas": _abas("ambientes-administracao"), "ambientes": linhas},
        request=req,
        root_class="content",
        toast=toast or None,
    )


# ── Criar ambiente pela tela ─────────────────────────────────────────────


@bp.route(route="ambientes-criar", methods=["GET"])
@com_sessao
def criar_form(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    bases = [a for a in registro.obter().listar_todos() if a.get("situacao") == "ativo"]
    return AlpineAjaxResponse(
        template_name="ambientes/criar.html",
        context={
            "usuario": usuario,
            "abas": _abas("ambientes-criar"),
            "bases": bases,
            "valores": {},
            "erros": {},
        },
        request=req,
        root_class="content",
    )


@bp.route(route="ambientes-criar", methods=["POST"])
@com_sessao
def criar_env(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    """Create one environment — the SAME function the command line calls.

    No rule lives here: validation, slug format, the clone list and the
    creator-as-admin are all inside ``registro.criar_ambiente``. The
    screen only translates the port's refusal into the form again.
    """
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    form = req.form
    identificador = (form.get("identificador") or "").strip()
    projeto = (form.get("projeto") or "").strip()
    cliente = (form.get("cliente") or "").strip()
    base = (form.get("base") or "").strip() or None

    try:
        registro.criar_ambiente(identificador, projeto, cliente, usuario.email, base=base)
    except InvalidoError as erro:
        bases = [a for a in registro.obter().listar_todos() if a.get("situacao") == "ativo"]
        return AlpineAjaxResponse(
            template_name="ambientes/criar.html",
            context={
                "usuario": usuario,
                "abas": _abas("ambientes-criar"),
                "bases": bases,
                "valores": {
                    "identificador": identificador,
                    "projeto": projeto,
                    "cliente": cliente,
                    "base": base or "",
                },
                "erros": {"geral": str(erro)},
            },
            request=req,
            root_class="content",
            status_code=422,
            toast=str(erro),
            toast_tipo="erro",
        )

    return _listagem(req, usuario, toast=f"Ambiente “{identificador}” criado.")


# ── Membros de um ambiente ───────────────────────────────────────────────


@bp.route(route="ambientes-membros", methods=["GET"])
@com_sessao
def membros(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)
    identificador = (req.params.get("ambiente") or "").strip()
    return _membros(req, usuario, identificador)


def _membros(
    req: func.HttpRequest,
    usuario: auth.Usuario,
    identificador: str,
    toast: str = "",
) -> func.HttpResponse:
    escolhido = registro.obter().obter(identificador)
    if not escolhido:
        return _recusa_de_ambiente("Ambiente não encontrado.")

    linhas = auth.membros_com_operadores(escolhido.get("membros", []))
    return AlpineAjaxResponse(
        template_name="ambientes/membros.html",
        context={
            "usuario": usuario,
            "abas": _abas(""),
            "ambiente": escolhido,
            "membros": linhas,
            "erros": {},
        },
        request=req,
        root_class="content",
        toast=toast or None,
    )


@bp.route(route="ambientes-membro-conceder", methods=["POST"])
@com_sessao
def conceder_membro(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    identificador = (req.form.get("ambiente") or "").strip()
    email = (req.form.get("email") or "").strip()
    try:
        registro.obter().conceder(identificador, email, usuario.email)
    except InvalidoError as erro:
        return _membros_com_erro(req, usuario, identificador, str(erro))
    return _membros(req, usuario, identificador, toast=f"Acesso de {email} concedido.")


@bp.route(route="ambientes-membro-revogar", methods=["POST"])
@com_sessao
def revogar_membro(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    identificador = (req.form.get("ambiente") or "").strip()
    email = (req.form.get("email") or "").strip().lower()
    if auth.eh_operador(email):
        return _membros_com_erro(
            req,
            usuario,
            identificador,
            "Operadores da Timenow entram em todo ambiente e não são revogados pelo registro.",
        )
    try:
        registro.obter().revogar(identificador, email, usuario.email)
    except InvalidoError as erro:
        return _membros_com_erro(req, usuario, identificador, str(erro))
    return _membros(req, usuario, identificador, toast=f"Acesso de {email} revogado.")


def _membros_com_erro(
    req: func.HttpRequest,
    usuario: auth.Usuario,
    identificador: str,
    mensagem: str,
) -> func.HttpResponse:
    escolhido = registro.obter().obter(identificador) or {}
    return AlpineAjaxResponse(
        template_name="ambientes/membros.html",
        context={
            "usuario": usuario,
            "abas": _abas(""),
            "ambiente": escolhido,
            "membros": auth.membros_com_operadores(escolhido.get("membros", [])),
            "erros": {"geral": mensagem},
        },
        request=req,
        root_class="content",
        status_code=422,
        toast=mensagem,
        toast_tipo="erro",
    )


# ── Tokens de leitura ─────────────────────────────────────────────────────


def _uso_rotulo(iso: str) -> str:
    """The last use as the screen reads it — hour precision, by design.

    The stored stamp is amortized to one rewrite an hour (decision 25),
    so seconds would be a lie of precision.
    """
    if not iso:
        return "nunca usado"
    try:
        momento = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:16]
    return momento.strftime("%d/%m/%Y às %Hh")


@bp.route(route="ambientes-tokens", methods=["GET"])
@com_sessao
def tokens(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)
    return _tokens(req, usuario)


def _tokens(
    req: func.HttpRequest,
    usuario: auth.Usuario,
    *,
    novo_valor: str = "",
    erros: dict | None = None,
    toast: str = "",
) -> func.HttpResponse:
    ativos = [a for a in registro.obter().listar_todos() if a.get("situacao") == "ativo"]
    linhas = []
    for ambiente_registrado in registro.obter().listar_todos():
        for token in registro.obter().listar_tokens(ambiente_registrado["id"]):
            emitido_em = token.get("emitido_em", "")
            linhas.append(
                {
                    **token,
                    "ambiente": ambiente_registrado["id"],
                    "emitido_rotulo": _uso_rotulo(emitido_em) if emitido_em else "—",
                    "uso_rotulo": _uso_rotulo(token.get("ultimo_uso", "")),
                    "validade": token.get("validade") or "—",
                }
            )
    return AlpineAjaxResponse(
        template_name="ambientes/tokens.html",
        context={
            "usuario": usuario,
            "abas": _abas("ambientes-tokens"),
            "ambientes": ativos,
            "tokens": linhas,
            "novo_valor": novo_valor,
            "erros": erros or {},
        },
        request=req,
        root_class="content",
        toast=toast or None,
    )


@bp.route(route="ambientes-token-emitir", methods=["POST"])
@com_sessao
def emitir_token(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    identificador = (req.form.get("ambiente") or "").strip()
    rotulo = (req.form.get("rotulo") or "").strip()
    validade = (req.form.get("validade") or "").strip()
    try:
        emitido = registro.obter().emitir_token(
            identificador, rotulo, usuario.email, validade=validade
        )
    except InvalidoError as erro:
        return _tokens(req, usuario, erros={"geral": str(erro)}, toast=str(erro))

    return _tokens(
        req,
        usuario,
        novo_valor=emitido["valor"],
        toast="Token emitido. Copie o valor agora — ele não será exibido de novo.",
    )


@bp.route(route="ambientes-token-revogar", methods=["POST"])
@com_sessao
def revogar_token(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    identificador = (req.form.get("ambiente") or "").strip()
    prefixo = (req.form.get("prefixo") or "").strip()
    try:
        registro.obter().revogar_token(identificador, prefixo, usuario.email)
    except InvalidoError as erro:
        return _tokens(req, usuario, erros={"geral": str(erro)}, toast=str(erro))
    return _tokens(req, usuario, toast=f"Token “{prefixo}” revogado — para na próxima requisição.")


# ── Arquivar e desarquivar ───────────────────────────────────────────────


@bp.route(route="ambientes-arquivar", methods=["POST"])
@com_sessao
def arquivar(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    identificador = (req.form.get("ambiente") or "").strip()
    try:
        registro.obter().arquivar(identificador, usuario.email)
    except InvalidoError as erro:
        return _recusa_de_ambiente(str(erro))
    return _listagem(req, usuario, toast=f"Ambiente “{identificador}” arquivado.")


@bp.route(route="ambientes-desarquivar", methods=["POST"])
@com_sessao
def desarquivar(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    identificador = (req.form.get("ambiente") or "").strip()
    try:
        registro.obter().desarquivar(identificador, usuario.email)
    except InvalidoError as erro:
        return _recusa_de_ambiente(str(erro))
    return _listagem(req, usuario, toast=f"Ambiente “{identificador}” desarquivado.")


# ── Operadores da instalação ─────────────────────────────────────────────
#
# A variável de ambiente continua sendo o PISO (decisão 11): sempre existe
# operador, mesmo com o registro vazio ou corrompido, e ninguém o remove
# por aqui. Acima dela, esta tela promove e rebaixa os adicionais — e
# mostra a origem de cada um, porque só os do registro podem cair. Uma
# tela que não distinguisse as duas origens ofereceria um botão inerte e
# mentiria sobre o que consegue fazer (revisão 3, item 2).


def _operadores(
    req: func.HttpRequest,
    usuario: auth.Usuario,
    toast: str = "",
    erro: str = "",
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name="ambientes/operadores.html",
        context={
            "usuario": usuario,
            "abas": _abas("ambientes-operadores"),
            "operadores": auth.operadores_com_origem(),
            "erros": {"geral": erro} if erro else {},
        },
        request=req,
        root_class="content",
        toast=toast or None,
        toast_tipo="erro" if erro else "ok",
    )


@bp.route(route="ambientes-operadores", methods=["GET"])
@com_sessao
def operadores(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)
    return _operadores(req, usuario)


@bp.route(route="ambientes-operador-promover", methods=["POST"])
@com_sessao
def promover_operador(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    email = (req.form.get("email") or "").strip()
    try:
        registro.obter().promover_operador(email, usuario.email)
    except InvalidoError as invalido:
        return _operadores(req, usuario, erro=str(invalido))
    return _operadores(req, usuario, toast=f"{email} agora é operador da instalação.")


@bp.route(route="ambientes-operador-rebaixar", methods=["POST"])
@com_sessao
def rebaixar_operador(req: func.HttpRequest, usuario: auth.Usuario) -> func.HttpResponse:
    if not _exigir_operador(usuario):
        return _sem_permissao(req, MENSAGEM_SEM_PERMISSAO)

    email = (req.form.get("email") or "").strip()
    try:
        registro.obter().rebaixar_operador(email, usuario.email)
    except InvalidoError as invalido:
        return _operadores(req, usuario, erro=str(invalido))
    return _operadores(req, usuario, toast=f"{email} deixou de ser operador.")
