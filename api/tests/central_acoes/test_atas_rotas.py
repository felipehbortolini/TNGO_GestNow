"""As rotas das atas (ISSUE-021, D14): lista, nova ata com 422 por campo, ficha e retirada recusada.

O handler é chamado com a requisição de Alpine, o seletor da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.central_acoes import minutes_routes, minutes_service, service
from src.modulos.central_acoes.validation import MinutesFilters
from tests.apoio_acoes import REFERENCIA, Cenario, nova_acao
from tests.apoio_atas import criar_ata, criar_unidade

CAMPOS_OBRIGATORIOS = ("data", "tipo_reuniao", "diretoria", "unidade", "elaborado_por", "assunto")


def _requisicao(
    usuario: User,
    *,
    metodo: str = "GET",
    params: Mapping[str, str] | None = None,
    corpo: Sequence[tuple[str, str]] | None = None,
    alvo: str = "atas-conteudo",
) -> func.HttpRequest:
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": alvo,
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/central-acoes/atas",
        headers=headers,
        params=dict(params or {}),
        body=urlencode(list(corpo)).encode() if corpo is not None else b"",
    )


def _chamar(rota: object, requisicao: func.HttpRequest) -> func.HttpResponse:
    return rota.get_user_function()(requisicao)  # type: ignore[attr-defined]


def _formulario_completo(cenario: Cenario, unidade_id: int, **campos: str) -> list[tuple[str, str]]:
    base = {
        "data": (REFERENCIA - timedelta(days=1)).isoformat(),
        "tipo_reuniao": "Planejamento",
        "diretoria": "Diretoria de Projetos",
        "unidade": str(unidade_id),
        "elaborado_por": str(cenario.mario.person_id),
        "assunto": "Planejamento das próximas duas semanas",
        **campos,
    }
    return list(base.items())


def test_a_lista_mostra_so_a_revisao_mais_recente(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    criar_ata(
        sessao, cenario, unidade, number="TN-2026-0100", revision=0, subject="Primeira versão"
    )
    criar_ata(sessao, cenario, unidade, number="TN-2026-0100", revision=1, subject="Versão vigente")

    resposta = _chamar(minutes_routes.list_minutes_screen, _requisicao(cenario.gil))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Versão vigente" in corpo
    assert "Primeira versão" not in corpo
    assert "Gerar nova ata" in corpo


def test_a_lista_vazia_mostra_o_estado_de_origem_e_a_busca_sem_resultado_o_de_filtro(
    sessao: Session, cenario: Cenario
) -> None:
    vazia = (
        _chamar(minutes_routes.list_minutes_screen, _requisicao(cenario.gil)).get_body().decode()
    )
    criar_ata(sessao, cenario, criar_unidade(sessao))
    sem_resultado = (
        _chamar(
            minutes_routes.list_minutes_screen, _requisicao(cenario.gil, params={"busca": "zzz"})
        )
        .get_body()
        .decode()
    )

    assert 'data-estado="vazio-origem"' in vazia
    assert 'data-estado="vazio-filtro"' in sem_resultado


def test_visualizador_ve_a_lista_sem_o_botao_de_nova_ata(sessao: Session, cenario: Cenario) -> None:
    criar_ata(sessao, cenario, criar_unidade(sessao))

    corpo = (
        _chamar(minutes_routes.list_minutes_screen, _requisicao(cenario.vera)).get_body().decode()
    )

    assert "TN-2026-0001" in corpo
    assert "Gerar nova ata" not in corpo


def test_nova_ata_sem_os_campos_obrigatorios_devolve_422_com_uma_mensagem_por_campo(
    cenario: Cenario,
) -> None:
    requisicao = _requisicao(
        cenario.gil,
        metodo="POST",
        params={"projeto": str(cenario.projeto_a.id)},
        corpo=[("assunto", "")],
        alvo="atas-modal-corpo",
    )

    resposta = _chamar(minutes_routes.create_minutes_route, requisicao)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    for campo in CAMPOS_OBRIGATORIOS:
        assert f"nova-ata-erro-{campo}" in corpo, campo


def test_nova_ata_com_assunto_de_151_caracteres_volta_o_formulario_preenchido(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    formulario = _formulario_completo(cenario, unidade.id, assunto="x" * 151)

    resposta = _chamar(
        minutes_routes.create_minutes_route,
        _requisicao(
            cenario.gil,
            metodo="POST",
            params={"projeto": str(cenario.projeto_a.id)},
            corpo=formulario,
            alvo="atas-modal-corpo",
        ),
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "nova-ata-erro-assunto" in corpo
    assert "Diretoria de Projetos" in corpo


def test_nova_ata_gera_o_numero_e_vai_para_a_ficha(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)

    resposta = _chamar(
        minutes_routes.create_minutes_route,
        _requisicao(
            cenario.gil,
            metodo="POST",
            params={"projeto": str(cenario.projeto_a.id)},
            corpo=_formulario_completo(cenario, unidade.id),
            alvo="atas-modal-corpo",
        ),
    )

    assert resposta.status_code == 302
    localizacao = resposta.headers["Location"]
    assert localizacao.startswith("/central-acoes/ata?id=")
    assert f"projeto={cenario.projeto_a.id}" in localizacao
    listagem = _listar(sessao, cenario)
    assert [linha.record.number for linha in listagem] == ["TN-2026-0001"]


def test_no_portfolio_a_nova_ata_pede_o_projeto(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)

    resposta = _chamar(
        minutes_routes.create_minutes_route,
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo=_formulario_completo(cenario, unidade.id),
            alvo="atas-modal-corpo",
        ),
    )

    assert resposta.status_code == 422
    assert _listar(sessao, cenario) == ()


def test_visualizador_nao_gera_ata_pela_rota(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)

    resposta = _chamar(
        minutes_routes.create_minutes_route,
        _requisicao(
            cenario.vera,
            metodo="POST",
            params={"projeto": str(cenario.projeto_a.id)},
            corpo=_formulario_completo(cenario, unidade.id),
            alvo="atas-modal-corpo",
        ),
    )

    assert resposta.status_code == 403


def test_o_formulario_de_nova_ata_traz_o_projeto_e_o_contador(
    sessao: Session, cenario: Cenario
) -> None:
    criar_unidade(sessao)

    resposta = _chamar(
        minutes_routes.new_minutes_form,
        _requisicao(
            cenario.gil, params={"projeto": str(cenario.projeto_a.id)}, alvo="atas-modal-corpo"
        ),
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "TN-ACAO-001" in corpo
    assert 'maxlength="150"' in corpo


def _listar(sessao: Session, cenario: Cenario) -> tuple[minutes_service.MinutesRow, ...]:
    return minutes_service.list_minutes(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=None, source="padrao"),
        filters=MinutesFilters(),
        reference_date=REFERENCIA,
    ).rows


# ── A ficha e a retirada ─────────────────────────────────────────────────────


def _ficha(cenario: Cenario, ata_id: int | str, usuario: User | None = None) -> func.HttpResponse:
    return _chamar(
        minutes_routes.minutes_sheet,
        _requisicao(usuario or cenario.gil, params={"id": str(ata_id)}, alvo="ata-ficha"),
    )


def test_a_ficha_traz_a_faixa_as_duas_abas_e_a_presenca(sessao: Session, cenario: Cenario) -> None:
    ata = criar_ata(sessao, cenario, criar_unidade(sessao), subject="Reunião de teste")

    resposta = _ficha(cenario, ata.id)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "TN-2026-0001 · Rev 0" in corpo
    assert "Dados da Reunião" in corpo
    assert "Lista de Presença" in corpo
    assert "Mário Membro" in corpo
    assert "Buscar convidado" in corpo


def test_a_ficha_de_revisao_anterior_nao_oferece_alteracao(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    antiga = criar_ata(sessao, cenario, unidade, number="TN-2026-0100", revision=0)
    criar_ata(sessao, cenario, unidade, number="TN-2026-0100", revision=1)

    corpo = _ficha(cenario, antiga.id).get_body().decode()

    assert "somente leitura" in corpo
    assert "Buscar convidado" not in corpo


def test_ata_inexistente_ou_sem_id_devolve_404_com_o_aviso(cenario: Cenario) -> None:
    assert _ficha(cenario, 999_999).status_code == 404
    assert _ficha(cenario, "abc").status_code == 404
    assert "Ata não encontrada" in _ficha(cenario, 999_999).get_body().decode()


def _retirar(
    cenario: Cenario, ata: minutes_service.MinutesRecord, person_id: int
) -> func.HttpResponse:
    return _chamar(
        minutes_routes.withdraw_save,
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo=[
                ("id", str(ata.id)),
                ("pessoa", str(person_id)),
                ("versao", str(ata.version)),
                ("aba", "presenca"),
            ],
            alvo="ata-modal-corpo",
        ),
    )


def test_retirar_com_acao_aberta_devolve_422_com_a_mensagem(
    sessao: Session, cenario: Cenario
) -> None:
    ata = criar_ata(
        sessao, cenario, criar_unidade(sessao), participant_ids=(cenario.gil.person_id,)
    )
    service.create_action(
        sessao,
        user=cenario.gil,
        new=nova_acao(
            cenario,
            origin="Ata",
            origin_ref=ata.number,
            ata_id=ata.id,
            responsible_id=cenario.gil.person_id,
        ),
        reference_date=REFERENCIA,
    )

    resposta = _retirar(cenario, ata, cenario.gil.person_id)

    assert resposta.status_code == 422
    assert "1 ação aberta sob sua responsabilidade nesta ata" in resposta.get_body().decode()


def test_retirar_sem_acao_aberta_devolve_a_ficha_atualizada_na_aba_de_presenca(
    sessao: Session, cenario: Cenario
) -> None:
    ata = criar_ata(
        sessao, cenario, criar_unidade(sessao), participant_ids=(cenario.gil.person_id,)
    )

    resposta = _retirar(cenario, ata, cenario.gil.person_id)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "Gil Gestor" not in corpo
    assert 'data-aba="presenca"' in corpo


def test_retirar_com_a_versao_antiga_devolve_409(sessao: Session, cenario: Cenario) -> None:
    ata = criar_ata(
        sessao,
        cenario,
        criar_unidade(sessao),
        participant_ids=(cenario.gil.person_id, cenario.vera.person_id),
    )
    assert _retirar(cenario, ata, cenario.gil.person_id).status_code == 200

    assert _retirar(cenario, ata, cenario.vera.person_id).status_code == 409


def test_visualizador_nao_abre_o_formulario_de_retirada(sessao: Session, cenario: Cenario) -> None:
    ata = criar_ata(sessao, cenario, criar_unidade(sessao))

    resposta = _chamar(
        minutes_routes.withdraw_form,
        _requisicao(
            cenario.vera,
            params={"id": str(ata.id), "pessoa": str(cenario.mario.person_id)},
            alvo="ata-modal-corpo",
        ),
    )

    assert resposta.status_code == 403


def test_o_formulario_de_convidados_lista_quem_ainda_nao_esta_na_ata(
    sessao: Session, cenario: Cenario
) -> None:
    ata = criar_ata(sessao, cenario, criar_unidade(sessao))

    resposta = _chamar(
        minutes_routes.guests_form,
        _requisicao(cenario.gil, params={"id": str(ata.id)}, alvo="ata-modal-corpo"),
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Vera Visualizadora" in corpo
    assert "Mário Membro" not in corpo


def test_adicionar_convidado_sem_escolher_ninguem_devolve_422(
    sessao: Session, cenario: Cenario
) -> None:
    ata = criar_ata(sessao, cenario, criar_unidade(sessao))

    resposta = _chamar(
        minutes_routes.guests_save,
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo=[("id", str(ata.id)), ("versao", str(ata.version))],
            alvo="ata-modal-corpo",
        ),
    )

    assert resposta.status_code == 422


# ── Exportações ──────────────────────────────────────────────────────────────


def test_excel_e_versao_imprimivel_da_lista_e_da_ficha(sessao: Session, cenario: Cenario) -> None:
    ata = criar_ata(sessao, cenario, criar_unidade(sessao))

    excel = _chamar(minutes_routes.minutes_list_excel, _requisicao(cenario.gil))
    imprimivel = _chamar(minutes_routes.minutes_list_printable, _requisicao(cenario.gil))
    ficha_excel = _chamar(
        minutes_routes.minutes_sheet_excel, _requisicao(cenario.gil, params={"id": str(ata.id)})
    )
    ficha_imprimivel = _chamar(
        minutes_routes.minutes_sheet_printable, _requisicao(cenario.gil, params={"id": str(ata.id)})
    )

    assert excel.get_body().startswith(b"PK")
    assert ficha_excel.get_body().startswith(b"PK")
    assert "TN-2026-0001" in imprimivel.get_body().decode()
    assert "Lista de Presença" in ficha_imprimivel.get_body().decode()


def test_no_portfolio_a_lista_e_o_excel_trazem_a_coluna_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    criar_ata(sessao, cenario, criar_unidade(sessao))

    tela = _chamar(minutes_routes.list_minutes_screen, _requisicao(cenario.gil)).get_body().decode()
    imprimivel = (
        _chamar(minutes_routes.minutes_list_printable, _requisicao(cenario.gil)).get_body().decode()
    )

    assert 'scope="col">Projeto<' in tela
    assert "Projeto" in imprimivel
