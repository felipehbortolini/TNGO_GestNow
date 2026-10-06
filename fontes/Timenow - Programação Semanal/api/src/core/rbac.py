"""Profiles, permission matrix and server-side authorisation.

Authorisation is ALWAYS decided here, in the blueprint, before anything
is rendered. The interface hides buttons for convenience — it never
decides access.

Profiles of the domain:

* **admin**        Gestão Timenow. Support CRUD, registers, import,
                   export, programming windows, people.
* **planejador**   Planejamento Timenow. Reviews, validates, picks the
                   fiscal in charge.
* **fiscal**       Fiscalização Timenow. Approves the reported work.
* **encarregado**  Field crew leader. Answers for one frente: sees the
                   week and reports what was done.
* **fornecedor**   Contractor. Creates and edits inside its window,
                   reports what was done, sees only its own company.
* **visualizador** Read-only, Timenow and client side. Exports.

**Fiscal and Encarregado are also the two register lists.** The activity
form offers exactly the people who carry these profiles. There is no
separate "Cadastros de apoio" list of names to keep in sync — a second
list of the same people is a second list to forget to update, and the
one that goes stale is always the one nobody opens. See
``dados.listar_fiscais`` and ``dados.listar_encarregados``.
"""

# ── Permissões atômicas ────────────────────────────────────────────────
VER = "ver"
EDITAR = "editar"
GERAR = "gerar"
EXPORTAR = "exportar"
VER_DASHBOARD = "ver_dashboard"
VALIDAR = "validar"
REGISTRAR_REALIZADO = "registrar_realizado"
APROVAR_REALIZADO = "aprovar_realizado"
PUBLICAR = "publicar"
IMPORTAR = "importar"
EXCLUIR = "excluir"
VER_PII = "ver_pii"
VER_CONFIGURACOES = "ver_configuracoes"
GERIR_CADASTROS = "gerir_cadastros"
GERIR_JANELAS = "gerir_janelas"
GERIR_COLABORADORES = "gerir_colaboradores"
VER_AUDITORIA = "ver_auditoria"
APLICAR = "aplicar"
GERIR_REGISTRO = "gerir_registro"
CONCEDER_ACESSO = "conceder_acesso"
GERIR_TOKENS = "gerir_tokens"

# As permissões do operador — o papel global que administra o registro de
# ambientes. Elas NÃO entram em nenhum perfil de `PERMISSOES` de propósito:
# o operador não é um perfil do cadastro, vem da configuração da implantação
# (`PROGRAMACAO_OPERADORES`), e o poder de enxergar todos os clientes não
# pode ser fabricado pelo dado. Quem as acrescenta é `auth._marcar_operador`.
PERMISSOES_OPERADOR = {GERIR_REGISTRO, CONCEDER_ACESSO, GERIR_TOKENS}

PERMISSOES: dict[str, set[str]] = {
    "admin": {
        VER,
        EDITAR,
        GERAR,
        EXPORTAR,
        VER_DASHBOARD,
        VALIDAR,
        REGISTRAR_REALIZADO,
        APROVAR_REALIZADO,
        PUBLICAR,
        IMPORTAR,
        EXCLUIR,
        VER_PII,
        VER_CONFIGURACOES,
        GERIR_CADASTROS,
        GERIR_JANELAS,
        GERIR_COLABORADORES,
        VER_AUDITORIA,
        APLICAR,
    },
    "planejador": {
        VER,
        EDITAR,
        GERAR,
        EXPORTAR,
        VER_DASHBOARD,
        VALIDAR,
        PUBLICAR,
        IMPORTAR,
        VER_CONFIGURACOES,
        GERIR_CADASTROS,
        GERIR_JANELAS,
        VER_AUDITORIA,
    },
    "fiscal": {
        VER,
        EDITAR,
        EXPORTAR,
        VER_DASHBOARD,
        APROVAR_REALIZADO,
        VER_CONFIGURACOES,
    },
    # O encarregado responde pela frente em campo: enxerga a semana e
    # reporta o que foi feito. Não cria, não valida, não publica — quem
    # programa é a contratada, quem aprova é o fiscal.
    "encarregado": {VER, REGISTRAR_REALIZADO, EXPORTAR},
    "fornecedor": {VER, EDITAR, GERAR, REGISTRAR_REALIZADO, EXPORTAR},
    "visualizador": {VER, EXPORTAR, VER_DASHBOARD},
}

PERFIS = tuple(PERMISSOES)

PERFIL_LABELS = {
    "admin": "Administrador",
    "planejador": "Planejador",
    "fiscal": "Fiscal",
    "encarregado": "Encarregado",
    "fornecedor": "Fornecedor",
    "visualizador": "Visualizador",
}

PERFIL_DESCRICAO = {
    "admin": "Acesso total: cadastros, janelas, colaboradores e auditoria.",
    "planejador": "Valida a programação, define o fiscal e publica a semana.",
    "fiscal": "Aprova o realizado das atividades sob sua responsabilidade.",
    "encarregado": "Responde pela frente em campo e reporta o realizado.",
    "fornecedor": "Programa e reporta o realizado da própria empresa.",
    "visualizador": "Somente leitura, com exportação.",
}

VINCULOS = ("timenow", "fornecedor", "cliente")

VINCULO_LABELS = {
    "timenow": "Timenow",
    "fornecedor": "Empresa contratada",
    "cliente": "Cliente",
}

# Só estes dois perfis administram pessoas. A separação da subaba
# Colaboradores existe por causa desta linha: quem entra em Configurações
# não entra necessariamente aqui.
PERFIS_QUE_GERENCIAM_PESSOAS = ("admin",)


def resolve(perfis: list[str]) -> set[str]:
    """Union of the permissions of every profile the user carries."""
    permissoes: set[str] = set()
    for perfil in perfis or []:
        permissoes |= PERMISSOES.get(perfil, set())
    return permissoes


def pode(user, permissao: str) -> bool:
    return bool(user) and permissao in (getattr(user, "permissions", None) or set())


def qualquer(user, *permissoes: str) -> bool:
    return any(pode(user, p) for p in permissoes)


def rotulo(perfil: str) -> str:
    return PERFIL_LABELS.get(perfil, perfil or "—")


def rotulo_vinculo(vinculo: str) -> str:
    return VINCULO_LABELS.get(vinculo, vinculo or "—")


# ── O próximo passo do fluxo ────────────────────────────────────────────

# A fila do trabalho de uma atividade, na ordem em que ela anda:
#
#     elaborar → validar → lançar o realizado → aprovar → publicar
#
# Cada degrau tem um dono diferente, e é raro alguém carregar dois
# seguidos. É por isso que "a próxima ação" quase sempre resolve para uma
# só, e é o que permite promovê-la a botão em vez de deixar todas no
# menu.


def proxima_acao(user, atividade) -> str:
    """The one thing this person should do to this activity, right now.

    Devolve ``validar``, ``aprovar``, ``lancar``, ``publicar`` ou ``ver``.

    Casa o perfil com o estado: o fiscal vê "Aprovar" onde a contratada
    vê "Lançar", e os dois viram "Publicar" quando o realizado já foi
    aprovado e só falta liberar a semana. Quem não tem permissão de
    nenhum degrau — o visualizador — cai em ``ver``, que é de fato tudo o
    que ele faz.

    **A ordem dos testes é a do fluxo, não a da conveniência.** Aprovar é
    conferido antes de lançar porque, quando já existe realizado parado
    esperando o fiscal, o passo seguinte é a aprovação — inclusive para
    um administrador, que consegue fazer os dois. Na ordem inversa o
    botão do administrador ofereceria "lançar" sobre um lançamento que já
    está pronto e na fila.

    Não substitui nenhuma verificação: o botão que sai daqui aponta para
    o mesmo endpoint que o menu, e cada endpoint decide o acesso por
    conta própria. Isto é ordenação de interface, não autorização.
    """
    situacao = atividade.get("situacao")
    aprovacao = atividade.get("aprovacao_realizado")
    tem_realizado = bool(atividade.get("tem_realizado"))
    em_elaboracao = situacao == "em_elaboracao"

    if pode(user, VALIDAR) and em_elaboracao:
        return "validar"
    if (
        pode(user, APROVAR_REALIZADO)
        and not em_elaboracao
        and aprovacao == "pendente"
        and tem_realizado
    ):
        return "aprovar"
    if pode(user, REGISTRAR_REALIZADO) and not em_elaboracao and aprovacao != "aprovado":
        return "lancar"
    if pode(user, PUBLICAR) and situacao == "validada" and aprovacao == "aprovado":
        return "publicar"
    return "ver"


def perfil_principal(user) -> str:
    for perfil in getattr(user, "roles", None) or []:
        if perfil in PERMISSOES:
            return perfil
    return ""
