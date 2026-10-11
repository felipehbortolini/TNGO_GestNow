"""As rotas do Início (ISSUE-079 e ISSUE-080): o fragmento, os perfis, o Excel, o imprimível e a ponderação.

A rota roda na transação do teste (``sessao_das_rotas``), em modo demonstração, e a requisição
é montada como o shell a envia: cabeçalho do Alpine AJAX, cookie do seletor de perfil e o
escopo no parâmetro ``projeto``. O Visualizador vê o resumo; o Fornecedor, que não alcança o
módulo (D7), recebe 403. A carteira aparece no Portfólio; o modal da ponderação abre para quem
vê a tela, e a prévia e a gravação são do Gestor ou Admin (Membro recebe 403). A data de
referência é a de hoje (``calendario.today()``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.core import calendario
from src.core.auth import DEMO_COOKIE
from src.core.export_document import ValueKind, format_value
from src.modulos.configuracoes import service as configuracoes
from src.modulos.inicio import routes
from tests.identidades import requisicao
from tests.inicio.conftest import Cenario, Demonstracao

HOME_TARGET = "inicio-conteudo"
PONDERATION_TARGET = "ponderacao-modal"
PONDERATION_TARGETS = "ponderacao-modal carteira-conteudo"
CABECALHO_AUSENTE = "cabeçalho não encontrado: {title}"


def _requisicao(
    caminho: str,
    *,
    colaborador_id: int,
    params: dict[str, str] | None = None,
    alvo: str = HOME_TARGET,
    metodo: str = "GET",
    corpo: Mapping[str, str | Iterable[str]] | None = None,
):
    return requisicao(
        caminho,
        metodo=metodo,
        cookies={DEMO_COOKIE: str(colaborador_id)},
        params=params,
        alvo=alvo,
        corpo=corpo,
    )


def _header_row(sheet: Worksheet, title: str) -> int:
    for row in sheet.iter_rows(min_row=1, max_row=30):
        if any(cell.value == title for cell in row):
            return row[0].row
    raise AssertionError(CABECALHO_AUSENTE.format(title=title))


def test_a_rota_do_resumo_responde_o_fragmento_no_alvo(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    resposta = routes.home_view(
        _requisicao(
            "/api/inicio/resumo",
            colaborador_id=demonstracao.admin.id,
            params={"projeto": str(demonstracao.project_id)},
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert 'id="inicio-conteudo"' in corpo
    assert "TN-2026-014 · Construção de uma nova fábrica" in corpo
    assert f"Data de referência {format_value(ValueKind.DATE, calendario.today())}" in corpo
    assert "Orçamento R$ 44,6 mi" in corpo
    assert "Ações atrasadas" in corpo
    assert "Não conformidades abertas" in corpo
    assert "Pontos de atenção" in corpo
    assert "CLM-TN-2026-0003 notificado fora do prazo contratual" in corpo
    assert "Sistema 210 Moagem bloqueado por item A" in corpo
    assert "Módulos" in corpo
    assert corpo.count("home__modulo--") == 8, "os oito cards dos módulos"
    assert 'data-tn-excel="/api/inicio/resumo/excel"' in corpo
    assert 'data-tn-pdf="/api/inicio/resumo/imprimivel"' in corpo
    assert 'href="/central-acoes/acoes?status=atrasada"' in corpo


def test_o_portfolio_da_rota_traz_a_etiqueta_do_portfolio(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    resposta = routes.home_view(
        _requisicao("/api/inicio/resumo", colaborador_id=demonstracao.admin.id)
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Portfólio de projetos · 3 projetos" in corpo
    assert "Orçamento R$ 70,2 mi" in corpo
    assert "TN-2026-014 · Contratar consultoria credenciada" in corpo


def test_os_perfis_do_projeto_veem_o_resumo(cenario: Cenario) -> None:
    for perfil in ("Visualizador", "Membro", "Gestor"):
        resposta = routes.home_view(
            _requisicao(
                "/api/inicio/resumo",
                colaborador_id=cenario.colaboradores[perfil],
                params={"projeto": str(cenario.project.id)},
            )
        )
        assert resposta.status_code == 200, perfil
        assert "Indicadores-chave por módulo" in resposta.get_body().decode(), perfil


def test_o_fornecedor_nao_alcanca_o_inicio(cenario: Cenario) -> None:
    resposta = routes.home_view(
        _requisicao(
            "/api/inicio/resumo",
            colaborador_id=cenario.colaboradores["Fornecedor"],
            params={"projeto": str(cenario.project.id)},
        )
    )

    assert resposta.status_code == 403
    assert "Programação Semanal" in resposta.get_body().decode()


def test_o_excel_do_resumo_traz_o_resumo_a_atencao_e_os_modulos(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    resposta = routes.home_excel(
        _requisicao(
            "/api/inicio/resumo/excel",
            colaborador_id=demonstracao.admin.id,
            params={"projeto": str(demonstracao.project_id)},
        )
    )

    assert resposta.status_code == 200
    assert resposta.headers.get("Content-Type", "").startswith("application/vnd.openxmlformats")
    pasta = load_workbook(BytesIO(resposta.get_body()))
    assert set(pasta.sheetnames) >= {"Resumo", "Pontos de atenção", "Módulos"}

    resumo = pasta["Resumo"]
    indicadores = [cell.value for row in resumo.iter_rows() for cell in row]
    assert "01 Central de Ações · Ações atrasadas" in indicadores
    assert "07 HSE · Dias sem acidente com afastamento" in indicadores

    atencao = pasta["Pontos de atenção"]
    header = _header_row(atencao, "Ponto de atenção")
    colunas = [cell.value for cell in atencao[header]]
    assert colunas == ["Módulo", "Nível", "Ponto de atenção", "Detalhe"]
    assert atencao.page_setup.orientation == "landscape"

    modulos = pasta["Módulos"]
    header = _header_row(modulos, "Módulo")
    assert [cell.value for cell in modulos[header]] == ["Módulo", "Descrição", "Selos"]


def test_o_imprimivel_do_resumo_sai_em_a4(demonstracao: Demonstracao, sessao_das_rotas) -> None:
    del sessao_das_rotas
    resposta = routes.home_printable(
        _requisicao(
            "/api/inicio/resumo/imprimivel",
            colaborador_id=demonstracao.admin.id,
            params={"projeto": str(demonstracao.project_id)},
            alvo="folha-impressao",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "folha--a4" in corpo
    assert "Resumo do projeto" in corpo
    assert "01 Central de Ações · Ações atrasadas" in corpo
    assert "Pontos de atenção" in corpo


# ── A carteira e a ponderação (ISSUE-080) ────────────────────────────────


def test_o_portfolio_da_rota_traz_a_carteira_entre_os_kpis_e_a_atencao(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    resposta = routes.home_view(
        _requisicao("/api/inicio/resumo", colaborador_id=demonstracao.admin.id)
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Carteira de projetos" in corpo
    assert corpo.index("home__kpis") < corpo.index("Carteira de projetos")
    assert corpo.index("Carteira de projetos") < corpo.index("Pontos de atenção")
    assert 'id="carteira-conteudo"' in corpo
    assert "55,36%" in corpo and "29,34%" in corpo and "15,30%" in corpo
    assert "100,00%" in corpo, "o rodapé fecha o peso em 100%"
    assert "data-ponderacao" in corpo, "o botão da ponderação aparece para o Gestor ou Admin"
    assert 'href="/inicio/home?projeto=' in corpo, "o Abrir troca o escopo"


def test_o_modal_da_ponderacao_responde_o_formulario(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    resposta = routes.ponderation_modal(
        _requisicao(
            "/api/inicio/ponderacao",
            colaborador_id=demonstracao.admin.id,
            alvo=PONDERATION_TARGET,
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert 'id="ponderacao-modal"' in corpo
    assert 'action="/api/inicio/ponderacao/gravar"' in corpo
    assert 'name="peso_valor"' in corpo and 'value="60"' in corpo
    assert 'name="peso_estrategico"' in corpo and 'name="peso_complexidade"' in corpo
    assert 'name="nota_' in corpo
    assert "Gravar ponderação" in corpo and "Prévia" in corpo


def test_o_modal_do_membro_e_somente_leitura(cenario: Cenario) -> None:
    resposta = routes.ponderation_modal(
        _requisicao(
            "/api/inicio/ponderacao",
            colaborador_id=cenario.colaboradores["Membro"],
            alvo=PONDERATION_TARGET,
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Somente Gestor ou Admin altera a ponderação da carteira." in corpo
    assert "Gravar ponderação" not in corpo
    assert "Prévia" not in corpo, "o membro não vê os botões da prévia e da gravação"


def test_o_membro_recebe_403_na_previa_e_na_gravacao(cenario: Cenario) -> None:
    membro = cenario.colaboradores["Membro"]
    pesos = {"peso_valor": "60", "peso_estrategico": "25", "peso_complexidade": "15"}

    previa = routes.ponderation_preview(
        _requisicao(
            "/api/inicio/ponderacao/previa",
            colaborador_id=membro,
            alvo=PONDERATION_TARGET,
            metodo="POST",
            corpo=pesos,
        )
    )
    gravacao = routes.ponderation_save(
        _requisicao(
            "/api/inicio/ponderacao/gravar",
            colaborador_id=membro,
            alvo=PONDERATION_TARGETS,
            metodo="POST",
            corpo={**pesos, "justificativa": "Justificativa com mais de dez caracteres."},
        )
    )

    for resposta in (previa, gravacao):
        assert resposta.status_code == 403
        assert "exige o perfil" in resposta.get_body().decode()


def test_o_gestor_grava_a_ponderacao_e_a_resposta_fecha_o_modal(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    projetos = configuracoes.list_projects(demonstracao.session)
    corpo: dict[str, str] = {
        "peso_valor": "50",
        "peso_estrategico": "30",
        "peso_complexidade": "20",
        "justificativa": "Revisão da ponderação aprovada no comitê de outubro.",
    }
    for projeto in projetos:
        corpo[f"nota_{projeto.id}_estrategico"] = "5"
        corpo[f"nota_{projeto.id}_complexidade"] = "1"

    resposta = routes.ponderation_save(
        _requisicao(
            "/api/inicio/ponderacao/gravar",
            colaborador_id=demonstracao.admin.id,
            alvo=PONDERATION_TARGETS,
            metodo="POST",
            corpo=corpo,
        )
    )

    assert resposta.status_code == 200
    fragmento = resposta.get_body().decode()
    assert 'data-ponderacao-salva="sim"' in fragmento
    assert 'id="ponderacao-modal"' in fragmento
    assert 'id="carteira-conteudo"' in fragmento
    assert "55,36%" not in fragmento, "a carteira volta com a ponderação nova"
    assert resposta.headers.get("X-TN-Toast"), "o toast de sucesso viaja no cabeçalho"


def test_o_excel_do_portfolio_traz_a_carteira_como_primeira_tabela(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    resposta = routes.home_excel(
        _requisicao("/api/inicio/resumo/excel", colaborador_id=demonstracao.admin.id)
    )

    assert resposta.status_code == 200
    pasta = load_workbook(BytesIO(resposta.get_body()))
    assert list(pasta.sheetnames) == [
        "Resumo",
        "Carteira de projetos",
        "Pontos de atenção",
        "Módulos",
    ]

    carteira = pasta["Carteira de projetos"]
    header = _header_row(carteira, "Peso na carteira")
    colunas = [cell.value for cell in carteira[header]]
    assert colunas[:3] == ["Projeto", "Peso na carteira", "Orçamento vigente"]
    assert colunas[-1] == "Situação"
    assert carteira.cell(row=carteira.max_row, column=1).value == "Portfólio"


def test_o_imprimivel_do_portfolio_traz_a_carteira(
    demonstracao: Demonstracao, sessao_das_rotas
) -> None:
    del sessao_das_rotas
    resposta = routes.home_printable(
        _requisicao(
            "/api/inicio/resumo/imprimivel",
            colaborador_id=demonstracao.admin.id,
            alvo="folha-impressao",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Resumo do portfólio" in corpo
    assert "Carteira de projetos" in corpo
    assert corpo.index("Carteira de projetos") < corpo.index("Pontos de atenção")
    assert "55,36%" in corpo and "29,34%" in corpo and "15,30%" in corpo
    assert "Portfólio" in corpo
