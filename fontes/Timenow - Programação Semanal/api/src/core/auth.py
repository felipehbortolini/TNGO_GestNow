"""Who is calling — resolved from the Azure SWA principal header.

Static Web Apps injects ``x-ms-client-principal`` (base64 JSON) on every
request to ``/api/*``. This module turns it into a :class:`Usuario` with
the permissions already resolved.

**The register of collaborators is the source of truth for access.** The
SWA header proves identity; the register grants the profile. An e-mail
that nobody registered gets in nowhere, even carrying a valid session —
that is what makes the Colaboradores screen a real access control and not
a list of names.

Local mode (``PROGRAMACAO_MODO=demo``, the default outside Azure) skips
the header and signs in as a seeded user, so the folder runs by double
click with no identity provider. It is refused the moment a real data
source is configured.
"""

import base64
import binascii
import json
import os
from dataclasses import dataclass, field

from src.core import rbac

CABECALHO_PRINCIPAL = "x-ms-client-principal"

# Cookie pelo qual a demonstração troca de perfil. Existe para revisar a
# tela como cada papel a vê, sem provisionar cinco contas — e é lido
# APENAS quando não há principal do SWA na requisição.
COOKIE_PERFIL_DEMO = "tn_perfil_demo"

# A identidade fixa da demonstração. Não há provedor de identidade no
# duplo clique, e o contorno antigo (resolver pelo cadastro de
# colaboradores) morreu quando o cadastro passou a viver dentro de um
# ambiente — o seletor roda antes de qualquer ambiente existir.
DEMO_EMAIL = "demo@timenow.local"

# Os ambientes que a demonstração semeia. Dois e não um: a troca de
# ambiente é a tela mais nova da entrega, e com um ambiente só ela seria
# a única que ninguém consegue ver antes de publicar.
AMBIENTES_DEMO = ("demo-obra", "demo-planta")


def eh_ambiente_demo(slug: str) -> bool:
    return (slug or "").strip() in AMBIENTES_DEMO


@dataclass
class Usuario:
    """Authenticated user with permissions already resolved."""

    id: str = ""
    nome: str = ""
    email: str = ""
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    empresa: str = ""
    vinculo: str = "timenow"
    demo: bool = False
    operador: bool = False

    @property
    def perfil(self) -> str:
        return rbac.perfil_principal(self)

    @property
    def perfil_rotulo(self) -> str:
        return rbac.rotulo(self.perfil)

    @property
    def iniciais(self) -> str:
        partes = (self.nome or self.email or "?").strip().split()
        if not partes:
            return "?"
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[-1][0]).upper()

    def pode(self, permissao: str) -> bool:
        return permissao in self.permissions

    def eh_fornecedor(self) -> bool:
        """Contractor users only ever see their own company."""
        return self.vinculo == "fornecedor" and bool(self.empresa)


def modo_demo() -> bool:
    """True when the app may sign users in without an identity provider."""
    return os.environ.get("PROGRAMACAO_MODO", "demo").lower() == "demo"


def operadores_da_configuracao() -> list[str]:
    """The operator e-mails that come from the deployment config.

    ``PROGRAMACAO_OPERADORES``, e-mails separated by ``;``. This is the
    **floor** of decision 11 and the reason it survives revision 3: on a
    clean installation there is an operator before there is a register,
    an erased or corrupted register never leaves the installation without
    a door, and a compromised register cannot manufacture the role that
    sees every client. Nobody demotes these through a screen.

    Empty or absent means "there is no configured operator", never an
    error.
    """
    bruto = os.environ.get("PROGRAMACAO_OPERADORES", "")
    return [pedaco.strip().lower() for pedaco in bruto.split(";") if pedaco.strip()]


def operadores() -> list[str]:
    """Every operator in force — the config floor plus who was promoted.

    Import is local because the register reads the domain facade, which
    reads this module: at module level the three would cycle.
    """
    from src.core import registro

    efetivos = list(operadores_da_configuracao())
    try:
        promovidos = registro.obter().listar_operadores()
    except OSError:
        # Registro ilegível não pode apagar o piso: quem vem da
        # configuração continua entrando, que é o motivo de o piso
        # existir.
        promovidos = []
    for email in promovidos:
        if email not in efetivos:
            efetivos.append(email)
    return efetivos


def operadores_com_origem() -> list[dict]:
    """Every operator with where it came from — the screen needs both.

    Only the promoted ones can be demoted, so a screen that cannot tell
    the two apart would offer an inert button and lie about what it can
    do (revision 3, item 2).
    """
    da_configuracao = operadores_da_configuracao()
    linhas = [{"email": email, "origem": "configuracao"} for email in da_configuracao]
    for email in operadores():
        if email not in da_configuracao:
            linhas.append({"email": email, "origem": "registro"})
    return linhas


def eh_operador(email: str) -> bool:
    return (email or "").strip().lower() in operadores()


def conta_pessoas_com_acesso(colaboradores: list[dict]) -> int:
    """Collaborators plus the operators absent from them — the true count.

    An operator already in the register counts once. The count is what
    the environment listing and the Collaboradores screen must agree on.
    """
    emails = {(c.get("email") or "").strip().lower() for c in colaboradores}
    extras = sum(1 for operador in operadores() if operador not in emails)
    return len(colaboradores) + extras


def colaboradores_com_operadores(colaboradores: list[dict]) -> list[dict]:
    """The access list as it must be shown: the register plus the
    operators absent from it, marked ``"operador": True``.

    An operator who is also in the register appears once, with the
    register's profile and the marking. The synthetic rows never touch
    the register — the client's list stays the client's own.
    """
    linhas = [dict(c) for c in colaboradores]
    for linha in linhas:
        if eh_operador(linha.get("email", "")):
            linha["operador"] = True
    presentes = {(c.get("email") or "").strip().lower() for c in linhas}
    for email in operadores():
        if email in presentes:
            continue
        linhas.append(
            {
                "nome": email,
                "email": email,
                "perfil": "admin",
                "vinculo": "timenow",
                "empresa": "",
                "ativo": True,
                "operador": True,
                "sintetico": True,
            }
        )
    return linhas


def membros_com_operadores(membros: list[str]) -> list[dict]:
    """The member list of an environment as it must be shown: the
    register's e-mails plus the operators, marked and synthetic.

    The member screen lists who may enter (layer 1); omitting the
    operators would make it lie — they enter every environment
    implicitly, without ever being granted.
    """
    linhas = [{"email": email, "operador": eh_operador(email)} for email in membros]
    presentes = {linha["email"] for linha in linhas}
    for email in operadores():
        if email not in presentes:
            linhas.append({"email": email, "operador": True, "sintetico": True})
    return linhas


def _claim(dados: dict, tipo: str) -> str:
    for claim in dados.get("claims") or []:
        if claim.get("typ") == tipo:
            return claim.get("val") or ""
    return ""


def _principal(req) -> dict | None:
    """Decode the SWA principal header. None when absent or malformed."""
    bruto = req.headers.get(CABECALHO_PRINCIPAL)
    if not bruto:
        return None
    try:
        return json.loads(base64.b64decode(bruto).decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None


def _do_cadastro(email: str, nome_fallback: str = "") -> Usuario | None:
    """Build the user from the collaborator register, or refuse."""
    from src.core import dados

    cadastro = dados.colaborador_por_email(email)
    if not cadastro:
        return None

    perfil = cadastro.get("perfil") or "visualizador"
    if not cadastro.get("ativo", True):
        return None

    usuario = Usuario(
        id=cadastro.get("id", "") or email,
        nome=cadastro.get("nome") or nome_fallback or email,
        email=email,
        roles=[perfil],
        permissions=rbac.resolve([perfil]),
        empresa=cadastro.get("empresa", ""),
        vinculo=cadastro.get("vinculo", "timenow"),
    )
    return _marcar_operador(usuario)


def _marcar_operador(usuario: Usuario) -> Usuario:
    """An operator carries the global powers in every environment.

    The register still decides the profile — an operator who is also a
    fiscal of a project enters as fiscal. This marking only adds what
    the deployment config grants, and it is the flag the screens use to
    show the non-removable "Operador Timenow" row.
    """
    if eh_operador(usuario.email):
        usuario.operador = True
        usuario.permissions |= rbac.PERMISSOES_OPERADOR
    return usuario


def _como_operador(email: str, nome_fallback: str = "") -> Usuario:
    """The synthetic user of an operator absent from the register.

    Built in memory, never written to the client's collaborator list:
    the operator enters every environment implicitly, and the register
    of each environment stays the client's own list. The profile is
    admin, Timenow side. Marked unconditionally: the callers only call
    this when the e-mail IS an operator — either from the deployment
    config, or the fixed demo identity.
    """
    usuario = Usuario(
        id=f"operador:{email}",
        nome=nome_fallback or email,
        email=email,
        roles=["admin"],
        permissions=rbac.resolve(["admin"]),
        vinculo="timenow",
    )
    usuario.operador = True
    usuario.permissions |= rbac.PERMISSOES_OPERADOR
    return usuario


def resolver_por_email(email: str, nome_fallback: str = "") -> Usuario | None:
    """The two-layer resolution for one e-mail, inside the active environment.

    Register first — it decides the profile. An operator who is not in
    the register still enters, as the synthetic admin. Everybody else
    is refused, SSO session or not.
    """
    usuario = _do_cadastro(email, nome_fallback)
    if usuario is not None:
        return usuario
    if eh_operador(email):
        return _como_operador(email, nome_fallback)
    return None


def identidade_da_requisicao(req) -> Usuario | None:
    """Who the identity provider says — without touching any register.

    The selector and the register administration run before any
    environment exists, so this is identity only: e-mail, name, and the
    operator marking from the deployment config. In demo mode the
    identity is fixed and always operator — the local run has no
    identity provider, and the old fallback (the collaborator register)
    died when the register moved inside the environments.
    """
    principal = _principal(req)
    if principal is None and modo_demo():
        return _como_operador(DEMO_EMAIL, "Demonstração")
    if principal is None:
        return None

    email = (
        _claim(principal, "email")
        or _claim(principal, "preferred_username")
        or principal.get("userDetails")
        or ""
    ).lower()
    if not email:
        return None

    usuario = Usuario(id=email, nome=principal.get("userDetails") or email, email=email)
    return _marcar_operador(usuario)


def _usuario_demo(pedido: str = "") -> Usuario | None:
    """Seeded sign-in for the local, no-SSO run.

    ``pedido`` accepts an e-mail or a profile name: the switcher sends the
    e-mail, because three contractors share the profile ``fornecedor``
    and choosing by profile would always land on the same one.
    """
    if not modo_demo():
        return None

    from src.core import dados

    colaboradores = dados.listar_colaboradores()
    alvo = (pedido or "").strip().lower()
    escolhido = (
        next((c for c in colaboradores if (c.get("email") or "").lower() == alvo), None)
        or next((c for c in colaboradores if c.get("perfil") == alvo), None)
        or next((c for c in colaboradores if c.get("perfil") == "admin"), None)
        or (colaboradores[0] if colaboradores else None)
    )
    if not escolhido:
        return None

    usuario = _do_cadastro(escolhido["email"])
    if usuario:
        usuario.demo = True
    return usuario


def _perfil_do_cookie(req) -> str:
    bruto = req.headers.get("Cookie") or ""
    for pedaco in bruto.split(";"):
        nome, _, valor = pedaco.strip().partition("=")
        if nome == COOKIE_PERFIL_DEMO:
            return valor.strip()
    return ""


def usuario_da_requisicao(req) -> Usuario | None:
    """Resolve the caller. None means "no access" — never a blank user."""
    principal = _principal(req)

    if principal is None:
        return _usuario_demo(_perfil_do_cookie(req) if modo_demo() else "")

    email = (
        _claim(principal, "email")
        or _claim(principal, "preferred_username")
        or principal.get("userDetails")
        or ""
    ).lower()
    if not email:
        return None

    return resolver_por_email(email, principal.get("userDetails", ""))
