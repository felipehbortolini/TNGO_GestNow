"""Masking of personal data — one choke point, applied before rendering.

Only the server decides what a profile may read. A field that leaves this
module masked never existed for the browser, so no amount of poking at
the DOM brings it back.

Today the schedule carries one class of personal data: the e-mail of a
collaborator. It is visible to whoever manages people and masked for
everyone else, which is what keeps the Colaboradores list readable
without publishing the company's address book.
"""

MASCARA = "•••"

CAMPOS_PESSOAIS = ("email", "telefone", "documento")


def mascarar_email(email: str) -> str:
    """``ana.souza@timenow.com.br`` → ``an•••@timenow.com.br``."""
    if not email or "@" not in email:
        return MASCARA
    usuario, dominio = email.split("@", 1)
    visivel = usuario[:2] if len(usuario) > 2 else usuario[:1]
    return f"{visivel}{MASCARA}@{dominio}"


def aplicar(user, registros: list[dict], campos: tuple[str, ...] = CAMPOS_PESSOAIS) -> list[dict]:
    """Return copies with the listed fields masked, unless allowed."""
    from src.core import rbac

    if rbac.pode(user, rbac.VER_PII):
        return registros

    protegidos = []
    for registro in registros:
        copia = dict(registro)
        for campo in campos:
            if not copia.get(campo):
                continue
            copia[campo] = mascarar_email(copia[campo]) if campo == "email" else MASCARA
        protegidos.append(copia)
    return protegidos
