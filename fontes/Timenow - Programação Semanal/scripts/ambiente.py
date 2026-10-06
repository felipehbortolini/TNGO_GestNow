"""Administração do registro de ambientes por linha de comando.

A Fase 1 administra sem tela: criar, conceder, revogar, arquivar,
desarquivar e listar, chamando exatamente as mesmas funções que a tela
da Fase 2 vai chamar — a porta do registro e a criação com clonagem. A
regra nasce e roda aqui; a tela depois só desenha.

    api/.venv/Scripts/python.exe scripts/ambiente.py criar --id suzano-mucuri `
        --projeto "Programação Suzano Mucuri" --cliente "Suzano S.A." --base mccain
    api/.venv/Scripts/python.exe scripts/ambiente.py conceder --id suzano-mucuri `
        --email fulano@timenow.com.br
    api/.venv/Scripts/python.exe scripts/ambiente.py listar

Também serve para preparar demonstração e consertar o registro sem
editar JSON à mão — onde um slug digitado errado criaria uma pasta
fantasma silenciosamente.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "api"))

from src.core import ambiente, auth, registro, repositorio  # noqa: E402
from src.core.dados import InvalidoError  # noqa: E402


def _falhar(erro: InvalidoError) -> int:
    print(f"Erro: {erro}", file=sys.stderr)
    return 1


def criar(args) -> int:
    try:
        criado = registro.criar_ambiente(
            args.id, args.projeto, args.cliente, args.ator, base=args.base
        )
    except InvalidoError as erro:
        return _falhar(erro)
    print(f"Ambiente “{criado['id']}” criado: {criado['projeto']} — {criado['cliente']}.")
    if args.base:
        print(f"Unidades e parâmetros herdados de “{args.base}”.")
    return 0


def conceder(args) -> int:
    try:
        registro.obter().conceder(args.id, args.email, args.ator)
    except InvalidoError as erro:
        return _falhar(erro)
    print(f"Acesso de {args.email} ao ambiente “{args.id}” concedido.")
    return 0


def revogar(args) -> int:
    try:
        registro.obter().revogar(args.id, args.email, args.ator)
    except InvalidoError as erro:
        return _falhar(erro)
    print(f"Acesso de {args.email} ao ambiente “{args.id}” revogado.")
    return 0


def arquivar(args) -> int:
    try:
        registro.obter().arquivar(args.id, args.ator)
    except InvalidoError as erro:
        return _falhar(erro)
    print(f"Ambiente “{args.id}” arquivado.")
    return 0


def desarquivar(args) -> int:
    try:
        registro.obter().desarquivar(args.id, args.ator)
    except InvalidoError as erro:
        return _falhar(erro)
    print(f"Ambiente “{args.id}” desarquivado.")
    return 0


def _pessoas_com_acesso(identificador: str) -> int:
    with ambiente.ambiente_ativo(identificador):
        colaboradores = repositorio.obter().listar_colaboradores()
    return auth.conta_pessoas_com_acesso(colaboradores)


def listar(args) -> int:
    ambientes = registro.obter().listar_todos()
    if not ambientes:
        print("Nenhum ambiente no registro.")
        return 0
    colunas = ("id", "projeto", "cliente", "situação", "pessoas")
    print("  ".join(f"{c:<30}" for c in colunas))
    for ambiente in ambientes:
        pessoas = _pessoas_com_acesso(ambiente["id"])
        linha = (
            ambiente["id"],
            ambiente["projeto"],
            ambiente["cliente"],
            ambiente["situacao"],
            str(pessoas),
        )
        print("  ".join(f"{v:<30}" for v in linha))
    return 0


def _analisar() -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description="Administração do registro de ambientes.")
    ator = argparse.ArgumentParser(add_help=False)
    ator.add_argument("--ator", default="", help="quem executa (para a trilha do registro)")
    sub = analisador.add_subparsers(dest="comando", required=True)

    criar_cmd = sub.add_parser("criar", parents=[ator], help="cria um ambiente novo")
    criar_cmd.add_argument("--id", required=True, help="identificador (slug, imutável)")
    criar_cmd.add_argument("--projeto", required=True, help="nome do projeto")
    criar_cmd.add_argument("--cliente", required=True, help="nome do cliente")
    criar_cmd.add_argument("--base", default=None, help="ambiente do qual herdar unidades e parâmetros")
    criar_cmd.set_defaults(func=criar)

    conceder_cmd = sub.add_parser("conceder", parents=[ator], help="concede acesso a um e-mail")
    conceder_cmd.add_argument("--id", required=True)
    conceder_cmd.add_argument("--email", required=True)
    conceder_cmd.set_defaults(func=conceder)

    revogar_cmd = sub.add_parser("revogar", parents=[ator], help="revoga o acesso de um e-mail")
    revogar_cmd.add_argument("--id", required=True)
    revogar_cmd.add_argument("--email", required=True)
    revogar_cmd.set_defaults(func=revogar)

    arquivar_cmd = sub.add_parser("arquivar", parents=[ator], help="suspende um ambiente sem apagar nada")
    arquivar_cmd.add_argument("--id", required=True)
    arquivar_cmd.set_defaults(func=arquivar)

    desarquivar_cmd = sub.add_parser("desarquivar", parents=[ator], help="devolve um ambiente arquivado")
    desarquivar_cmd.add_argument("--id", required=True)
    desarquivar_cmd.set_defaults(func=desarquivar)

    sub.add_parser("listar", help="lista todos os ambientes").set_defaults(func=listar)
    return analisador.parse_args()


if __name__ == "__main__":
    argumentos = _analisar()
    sys.exit(argumentos.func(argumentos))
