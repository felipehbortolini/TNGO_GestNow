"""Aplica a carga do modo configurado ao banco local (ISSUE-008).

Em demonstração, escreve a base convertida dos mocks do protótipo com as
datas deslocadas para hoje; em produção, nasce a base vazia com o primeiro
Admin de ``GESTNOW_ADMIN_EMAIL`` e os parâmetros iniciais. É idempotente:
rodar de novo não duplica nada. O ``run.bat`` chama este script depois de
preparar o banco; nunca imprime senha nem URL de conexão.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(API_DIR))

from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from src.carga import ProductionStartError, run_for_mode  # noqa: E402
from src.core import calendario, config, database  # noqa: E402
from src.core.errors import InvalidDataError  # noqa: E402


def main() -> int:
    config.load_local_settings()
    try:
        mode = config.app_mode()
    except config.InvalidApplicationModeError as error:
        print(f"ERRO: {error}")
        return 1

    print(f"Modo do app: {mode} (variavel {config.APP_MODE_VARIABLE})")
    try:
        with database.unidade_de_trabalho() as session:
            written = run_for_mode(session, reference_date=calendario.today())
    except database.DatabaseNotConfiguredError:
        print(f"ERRO: a variavel {database.DATABASE_URL_VARIABLE} nao esta definida.")
        print("Rode o run.bat para preparar o banco local.")
        return 1
    except ProductionStartError as error:
        print(f"ERRO: {error}")
        return 1
    except InvalidDataError as error:
        print(f"ERRO: {error}")
        return 1
    except SQLAlchemyError:
        print("ERRO: nao foi possivel gravar a carga no banco.")
        print("Confira se o servico do Postgres esta rodando e rode o run.bat de novo.")
        return 1

    _report(mode, written)
    return 0


def _report(mode: str, written: list[str]) -> None:
    if mode == config.DEMONSTRATION:
        if written:
            print(f"  carga de demonstracao aplicada: {', '.join(written)}")
        else:
            print("  carga de demonstracao ja aplicada; nada foi duplicado")
        return
    print("  base de producao pronta: primeiro Admin e parametros iniciais")


if __name__ == "__main__":
    sys.exit(main())
