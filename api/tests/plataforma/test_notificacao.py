"""The notification port: simulated by default, Microsoft Graph when on, and no send loses a record.

The seam under test is the facade ``notification.send`` with a session of the
test database. The HTTP seam of the Graph adapter is a fake that records the
calls, and a guard makes any attempt to open a connection fail the test, so
nothing here reaches the network.

Nothing is committed: each test runs in the transaction the ``db_session``
fixture rolls back, except the one that proves the notification rolls back with
the transaction of the request, which owns its own unit of work.
"""

from __future__ import annotations

import http.client
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple
from urllib.parse import parse_qs, unquote

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import config, database, graph_mail, notification, recording
from src.core.errors import InvalidDataError
from src.core.graph_mail import HttpResponse, StdlibHttpClient
from src.core.models import AuditEntry, Client, Notification
from src.core.notification import NotificationRequest
from src.core.responses import cabecalhos_de_toast
from src.modulos.configuracoes.models import Collaborator, Person, Project

# Fake values for the four Graph settings. The credential is the one that must
# never reach the register, the trail, the notice or a repr.
CREDENCIAL_DE_TESTE = "valor-que-nunca-pode-vazar"
CONFIGURACAO_DO_GRAPH = {
    "tenant_id": "tenant-de-teste",
    "client_id": "app-de-teste",
    "client_secret": CREDENCIAL_DE_TESTE,
    "sender": "gestnow@example.invalid",
}

URL_DO_ENTRA = "https://login.microsoftonline.com/tenant-de-teste/oauth2/v2.0/token"
URL_DO_SENDMAIL = "https://graph.microsoft.com/v1.0/users/gestnow@example.invalid/sendMail"


def _resposta_json(status: int, conteudo: dict[str, Any]) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(conteudo).encode())


TOKEN_CONCEDIDO = _resposta_json(200, {"access_token": "token-de-teste", "expires_in": 3599})
ACEITO = HttpResponse(status=202, body=b"")


@dataclass
class Chamada:
    """One POST the adapter made, as the fake saw it."""

    url: str
    headers: dict[str, str]
    body: bytes
    timeout: float


class ClienteHttpFalso:
    """The HTTP seam: answers in order; an exception in the list is raised instead."""

    def __init__(self, *respostas: HttpResponse | Exception) -> None:
        self.chamadas: list[Chamada] = []
        self._respostas = list(respostas)

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> HttpResponse:
        self.chamadas.append(Chamada(url, dict(headers), body, timeout))
        resposta = self._respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


class CanalQueQuebra:
    """A channel with a bug: it raises something that is not a ``DeliveryError``."""

    situation = notification.SENT

    def deliver(self, _request: NotificationRequest) -> None:
        message = "defeito do canal, com um texto que não deve ir para a trilha"
        raise RuntimeError(message)


class FalhaForcadaError(RuntimeError):
    """A failure forced after the send, to prove the notification rolls back with the request."""


class Esperado(NamedTuple):
    """What a failed send must look like: calls made, a piece of the notice and of the error."""

    chamadas: int
    aviso: str
    erro: str


@dataclass(frozen=True)
class Cenario:
    """A collaborator who asks for the notification and the project it belongs to."""

    autor: Collaborator
    projeto: Project


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start with e-mail off and no Graph setting, whatever the developer's machine has."""
    for variavel in (config.EMAIL_SENDING_VARIABLE, *graph_mail.VARIABLES.values()):
        monkeypatch.delenv(variavel, raising=False)


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test, loudly, if anything tries to open a connection.

    ``pytest.fail`` is not an ``Exception``, so the port's last-resort handler
    cannot swallow it and turn the attempt into a recorded failure.
    """

    def proibido(*_args: object, **_kwargs: object) -> None:
        pytest.fail("O teste tentou abrir uma conexão de rede.")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", proibido)
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", proibido)


@pytest.fixture
def log_do_envio(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> pytest.LogCaptureFixture:
    """Capture what the port logs.

    The session fixture runs the migrations in-process, and Alembic's
    ``fileConfig`` disables every logger that already exists. This one is
    switched back on for the test, so the log can be asserted.
    """
    monkeypatch.setattr(notification.logger, "disabled", False)
    caplog.set_level(logging.INFO, logger=notification.logger.name)
    return caplog


@pytest.fixture
def envio_ligado(monkeypatch: pytest.MonkeyPatch) -> None:
    """E-mail sending on and the four Graph settings filled with fake values."""
    monkeypatch.setenv(config.EMAIL_SENDING_VARIABLE, config.EMAIL_SENDING_ON)
    for atributo, variavel in graph_mail.VARIABLES.items():
        monkeypatch.setenv(variavel, CONFIGURACAO_DO_GRAPH[atributo])


@pytest.fixture
def cenario(db_session: Session) -> Cenario:
    pessoa = Person(name="Ana Souza", email="ana.souza@example.invalid")
    gerente = Person(name="Gerente do projeto", email="gerente@example.invalid")
    cliente = Client(name="Cliente de teste", active=True)
    db_session.add_all([pessoa, gerente, cliente])
    db_session.flush()
    autor = Collaborator(person_id=pessoa.id, general_profile="Membro", bond="Timenow")
    projeto = Project(
        client_id=cliente.id, manager_id=gerente.id, code="TN-2026-013", name="Projeto de teste"
    )
    db_session.add_all([autor, projeto])
    db_session.flush()
    return Cenario(autor=autor, projeto=projeto)


def _pedido(cenario: Cenario, **mudancas: Any) -> NotificationRequest:
    valores: dict[str, Any] = {
        "kind": notification.FOLLOW_UP,
        "project_id": cenario.projeto.id,
        "recipients": ["responsavel@example.invalid"],
        "subject": "Follow-up das ações",
        "body": "Você tem 3 ações em aberto.",
        "reference_entity": "acao",
        "reference_record_id": 77,
    }
    return NotificationRequest(**{**valores, **mudancas})


def _enviar_pelo_graph(
    session: Session, cenario: Cenario, http: ClienteHttpFalso, **mudancas: Any
) -> notification.NotificationOutcome:
    """Send through the Graph channel the environment selects, with the fake HTTP client."""
    return notification.send(
        session,
        user_id=cenario.autor.id,
        request=_pedido(cenario, **mudancas),
        channel=notification.configured_channel(http_client=http),
    )


def _trilha(session: Session, notification_id: int) -> list[AuditEntry]:
    return list(
        session.scalars(
            select(AuditEntry)
            .where(AuditEntry.entity == "notificacao", AuditEntry.record_id == notification_id)
            .order_by(AuditEntry.id)
        )
    )


def _contar(session: Session, modelo: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(modelo)) or 0


def _gravar_registro_de_origem(session: Session, cenario: Cenario) -> int:
    """Stands for the record that asked for the notification (an action, a risk, a schedule)."""
    origem = recording.create(
        session, user_id=cenario.autor.id, record=Client(name="Registro de origem", active=True)
    )
    return origem.id


def _origem_existe(session: Session, origem_id: int) -> bool:
    achados = session.scalar(select(func.count()).select_from(Client).where(Client.id == origem_id))
    trilha = session.scalar(
        select(func.count())
        .select_from(AuditEntry)
        .where(AuditEntry.entity == "cliente", AuditEntry.record_id == origem_id)
    )
    return achados == 1 and trilha == 1


# ── Desligada: o envio é simulado ────────────────────────────────────────


def test_desligada_a_notificacao_deixa_linha_na_trilha_e_avisa_simulado(
    db_session: Session, cenario: Cenario
) -> None:
    pedido = _pedido(cenario, recipients=["a@example.invalid", "b@example.invalid"])

    saida = notification.send(db_session, user_id=cenario.autor.id, request=pedido)

    assert saida.situation == "simulado"
    assert "simulado" in saida.notice.lower()
    assert saida.toast_kind == "aviso"
    assert saida.error is None

    registro = db_session.get(Notification, saida.notification_id)
    assert registro is not None
    assert (registro.kind, registro.channel, registro.situation) == (
        "follow_up",
        "email",
        "simulado",
    )
    assert registro.recipients == "a@example.invalid, b@example.invalid"
    assert registro.subject == "Follow-up das ações"
    assert registro.body == "Você tem 3 ações em aberto."
    assert (registro.reference_entity, registro.reference_record_id) == ("acao", 77)

    linhas = _trilha(db_session, saida.notification_id)
    assert len(linhas) == 1
    linha = linhas[0]
    assert (linha.action, linha.user_id, linha.project_id) == (
        "criado",
        cenario.autor.id,
        cenario.projeto.id,
    )
    assert linha.after is not None
    assert linha.after["destinatarios"] == "a@example.invalid, b@example.invalid"
    assert linha.after["assunto"] == "Follow-up das ações"
    assert linha.after["situacao"] == "simulado"
    assert "erro" not in linha.after


def test_o_aviso_simulado_viaja_no_toast_da_resposta(db_session: Session, cenario: Cenario) -> None:
    saida = notification.send(db_session, user_id=cenario.autor.id, request=_pedido(cenario))

    cabecalhos = cabecalhos_de_toast(saida.notice, saida.toast_kind)

    assert unquote(cabecalhos["X-TN-Toast"]) == saida.notice
    assert "simulado" in unquote(cabecalhos["X-TN-Toast"]).lower()
    assert cabecalhos["X-TN-Toast-Tipo"] == "aviso"


def test_o_envio_simulado_registra_no_log_so_o_tipo_e_a_contagem(
    db_session: Session, cenario: Cenario, log_do_envio: pytest.LogCaptureFixture
) -> None:
    notification.send(db_session, user_id=cenario.autor.id, request=_pedido(cenario))

    assert "Envio de e-mail simulado (follow_up, 1 destinatário(s))" in log_do_envio.text
    assert "responsavel@example.invalid" not in log_do_envio.text


@pytest.mark.parametrize(
    "tipo", [notification.FOLLOW_UP, notification.RISK_AGENDA, notification.TREASURY]
)
def test_os_tres_envios_do_prototipo_passam_pela_mesma_porta(
    db_session: Session, cenario: Cenario, tipo: str
) -> None:
    saida = notification.send(
        db_session, user_id=cenario.autor.id, request=_pedido(cenario, kind=tipo)
    )

    registro = db_session.get(Notification, saida.notification_id)
    assert registro is not None
    assert registro.kind == tipo
    assert saida.situation == "simulado"


# ── A variável de ambiente escolhe o canal ───────────────────────────────


def test_nomes_das_variaveis_sao_os_documentados_no_readme() -> None:
    assert config.EMAIL_SENDING_VARIABLE == "GESTNOW_ENVIO_EMAIL"
    assert graph_mail.VARIABLES == {
        "tenant_id": "GESTNOW_GRAPH_TENANT_ID",
        "client_id": "GESTNOW_GRAPH_CLIENT_ID",
        "client_secret": "GESTNOW_GRAPH_CLIENT_SECRET",
        "sender": "GESTNOW_GRAPH_REMETENTE",
    }


@pytest.mark.parametrize("valor", [None, "desligado", "  DESLIGADO "])
def test_sem_a_variavel_ou_desligada_o_canal_e_o_simulado(
    monkeypatch: pytest.MonkeyPatch, valor: str | None
) -> None:
    if valor is not None:
        monkeypatch.setenv(config.EMAIL_SENDING_VARIABLE, valor)

    assert config.email_sending() == config.EMAIL_SENDING_OFF
    assert isinstance(notification.configured_channel(), notification.SimulatedChannel)


@pytest.mark.usefixtures("envio_ligado")
def test_ligada_a_variavel_escolhe_o_canal_do_graph() -> None:
    canal = notification.configured_channel(http_client=ClienteHttpFalso())

    assert isinstance(canal, graph_mail.GraphMailChannel)


def test_valor_desconhecido_falha_alto_e_nada_e_gravado(
    db_session: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.EMAIL_SENDING_VARIABLE, "talvez")

    with pytest.raises(config.InvalidEmailSendingError, match="GESTNOW_ENVIO_EMAIL"):
        notification.send(db_session, user_id=cenario.autor.id, request=_pedido(cenario))

    assert _contar(db_session, Notification) == 0


# ── Ligada: o Microsoft Graph recebe destinatários, assunto e corpo ──────


@pytest.mark.usefixtures("envio_ligado")
def test_ligada_a_porta_chama_o_graph_com_destinatarios_assunto_e_corpo(
    db_session: Session, cenario: Cenario
) -> None:
    http = ClienteHttpFalso(TOKEN_CONCEDIDO, ACEITO)
    corpo = "Risco RSK-0003: revisão vencida.\nAção: aprovar o plano de resposta."

    saida = _enviar_pelo_graph(
        db_session,
        cenario,
        http,
        kind=notification.RISK_AGENDA,
        recipients=["gerente@example.invalid", "pmo@example.invalid"],
        subject="Pauta de escalonamento",
        body=corpo,
    )

    token, envio = http.chamadas
    assert token.url == URL_DO_ENTRA
    assert token.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert parse_qs(token.body.decode()) == {
        "client_id": ["app-de-teste"],
        "client_secret": [CREDENCIAL_DE_TESTE],
        "scope": ["https://graph.microsoft.com/.default"],
        "grant_type": ["client_credentials"],
    }

    assert envio.url == URL_DO_SENDMAIL
    assert envio.headers["Authorization"] == "Bearer token-de-teste"
    assert envio.headers["Content-Type"] == "application/json"
    assert json.loads(envio.body) == {
        "message": {
            "subject": "Pauta de escalonamento",
            "body": {"contentType": "Text", "content": corpo},
            "toRecipients": [
                {"emailAddress": {"address": "gerente@example.invalid"}},
                {"emailAddress": {"address": "pmo@example.invalid"}},
            ],
        },
        "saveToSentItems": True,
    }
    assert token.timeout == envio.timeout == graph_mail.REQUEST_TIMEOUT_SECONDS

    assert saida.situation == "enviado"
    assert saida.toast_kind == "ok"
    assert saida.notice == "E-mail enviado a 2 destinatários."
    registro = db_session.get(Notification, saida.notification_id)
    assert registro is not None
    assert (registro.situation, registro.kind) == ("enviado", "pauta_riscos")
    linha = _trilha(db_session, saida.notification_id)[0]
    assert linha.after is not None
    assert linha.after["situacao"] == "enviado"
    assert linha.after["destinatarios"] == "gerente@example.invalid, pmo@example.invalid"
    assert "erro" not in linha.after
    assert CREDENCIAL_DE_TESTE not in json.dumps(linha.after)


@pytest.mark.usefixtures("envio_ligado")
def test_ligada_por_configuracao_o_envio_nao_pede_mudanca_de_codigo(
    db_session: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same call as the simulated send: only the environment changed, down to the real client."""
    http = ClienteHttpFalso(TOKEN_CONCEDIDO, ACEITO)
    monkeypatch.setattr(
        StdlibHttpClient, "post", lambda _self, url, **kwargs: http.post(url, **kwargs)
    )

    saida = notification.send(db_session, user_id=cenario.autor.id, request=_pedido(cenario))

    assert saida.situation == "enviado"
    assert [chamada.url for chamada in http.chamadas] == [URL_DO_ENTRA, URL_DO_SENDMAIL]
    assert saida.notice == "E-mail enviado a 1 destinatário."


@pytest.mark.usefixtures("envio_ligado")
def test_o_tenant_e_o_remetente_vao_codificados_na_url(
    db_session: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(graph_mail.VARIABLES["tenant_id"], "diretorio com espaço/../x")
    monkeypatch.setenv(graph_mail.VARIABLES["sender"], "caixa do app@example.invalid")
    http = ClienteHttpFalso(TOKEN_CONCEDIDO, ACEITO)

    _enviar_pelo_graph(db_session, cenario, http)

    token, envio = http.chamadas
    assert token.url == (
        "https://login.microsoftonline.com/diretorio%20com%20espa%C3%A7o%2F..%2Fx/oauth2/v2.0/token"
    )
    assert envio.url == (
        "https://graph.microsoft.com/v1.0/users/caixa%20do%20app@example.invalid/sendMail"
    )


# ── Falha do envio: fica na trilha e o registro de origem permanece ──────


@pytest.mark.usefixtures("envio_ligado")
def test_falha_do_graph_fica_na_trilha_e_nao_desfaz_o_registro_de_origem(
    db_session: Session, cenario: Cenario
) -> None:
    origem_id = _gravar_registro_de_origem(db_session, cenario)
    recusa = _resposta_json(
        403, {"error": {"code": "ErrorAccessDenied", "message": "Access is denied."}}
    )

    saida = _enviar_pelo_graph(
        db_session,
        cenario,
        ClienteHttpFalso(TOKEN_CONCEDIDO, recusa),
        reference_entity="cliente",
        reference_record_id=origem_id,
    )
    db_session.commit()  # what the route's unit of work does when the handler returns

    assert saida.situation == "erro"
    assert saida.toast_kind == "erro"
    assert "HTTP 403" in saida.notice
    assert saida.notice.endswith("O registro foi mantido e a falha ficou na trilha de auditoria.")
    assert saida.error is not None
    assert "ErrorAccessDenied" in saida.error
    assert "Access is denied." in saida.error

    linha = _trilha(db_session, saida.notification_id)[0]
    assert linha.after is not None
    assert linha.after["situacao"] == "erro"
    assert linha.after["erro"] == saida.error
    assert linha.after["destinatarios"] == "responsavel@example.invalid"
    assert linha.after["assunto"] == "Follow-up das ações"

    # The record that asked for the notification, its own trail line and the
    # register of the failed send all committed together.
    assert _origem_existe(db_session, origem_id)
    registro = db_session.get(Notification, saida.notification_id)
    assert registro is not None
    assert registro.situation == "erro"
    assert registro.reference_record_id == origem_id


@pytest.mark.usefixtures("envio_ligado")
@pytest.mark.parametrize(
    ("respostas", "esperado"),
    [
        pytest.param(
            [
                _resposta_json(
                    401,
                    {
                        "error": "invalid_client",
                        "error_description": "AADSTS7000215: Invalid client secret.\r\nTrace ID: x",
                    },
                )
            ],
            Esperado(
                1,
                "Microsoft Entra recusou as credenciais do app (HTTP 401)",
                "invalid_client: AADSTS7000215: Invalid client secret. Trace ID: x",
            ),
            id="entra_recusa_as_credenciais",
        ),
        pytest.param(
            [_resposta_json(200, {"token_type": "Bearer"})],
            Esperado(1, "não devolveu o token de acesso", ""),
            id="entra_responde_sem_token",
        ),
        pytest.param(
            [HttpResponse(status=200, body=b"<html>portal de login</html>")],
            Esperado(1, "não devolveu o token de acesso", ""),
            id="entra_responde_algo_que_nao_e_json",
        ),
        pytest.param(
            [TOKEN_CONCEDIDO, HttpResponse(status=502, body=b"<html>Bad Gateway</html>")],
            Esperado(2, "Microsoft Graph recusou o envio (HTTP 502)", ""),
            id="graph_responde_html_de_proxy",
        ),
        pytest.param(
            [TOKEN_CONCEDIDO, _resposta_json(429, {"error": {"code": "TooManyRequests"}})],
            Esperado(2, "Microsoft Graph recusou o envio (HTTP 429)", "TooManyRequests"),
            id="graph_limita_a_taxa",
        ),
        pytest.param(
            [TimeoutError("timed out")],
            Esperado(1, "sem resposta da Microsoft dentro do tempo limite", ""),
            id="entra_nao_responde",
        ),
        pytest.param(
            [TOKEN_CONCEDIDO, ConnectionResetError("rede caiu")],
            Esperado(
                2,
                "falha de rede ao falar com a Microsoft",
                "ConnectionResetError: rede caiu",
            ),
            id="rede_cai_no_envio",
        ),
        pytest.param(
            [TOKEN_CONCEDIDO, http.client.IncompleteRead(b"par")],
            Esperado(2, "falha de rede ao falar com a Microsoft", "IncompleteRead"),
            id="resposta_cortada_ao_meio",
        ),
    ],
)
def test_toda_falha_do_envio_vira_erro_na_trilha_sem_perder_o_registro(
    db_session: Session,
    cenario: Cenario,
    respostas: list[HttpResponse | Exception],
    esperado: Esperado,
) -> None:
    origem_id = _gravar_registro_de_origem(db_session, cenario)
    http = ClienteHttpFalso(*respostas)

    saida = _enviar_pelo_graph(db_session, cenario, http)
    db_session.commit()

    assert saida.situation == "erro"
    assert saida.toast_kind == "erro"
    assert esperado.aviso in saida.notice
    assert len(http.chamadas) == esperado.chamadas
    linha = _trilha(db_session, saida.notification_id)[0]
    assert linha.after is not None
    assert linha.after["situacao"] == "erro"
    assert esperado.erro in linha.after["erro"]
    assert _origem_existe(db_session, origem_id)
    assert CREDENCIAL_DE_TESTE not in json.dumps(linha.after) + saida.notice


def test_configuracao_incompleta_e_falha_registrada_com_os_nomes_e_sem_chamar_o_graph(
    db_session: Session, cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.EMAIL_SENDING_VARIABLE, config.EMAIL_SENDING_ON)
    monkeypatch.setenv(graph_mail.VARIABLES["tenant_id"], "tenant-de-teste")
    monkeypatch.setenv(graph_mail.VARIABLES["client_secret"], CREDENCIAL_DE_TESTE)
    http = ClienteHttpFalso()

    saida = _enviar_pelo_graph(db_session, cenario, http)

    assert saida.situation == "erro"
    assert http.chamadas == []
    assert saida.error is not None
    assert "GESTNOW_GRAPH_CLIENT_ID" in saida.error
    assert "GESTNOW_GRAPH_REMETENTE" in saida.error
    assert "GESTNOW_GRAPH_TENANT_ID" not in saida.error
    assert CREDENCIAL_DE_TESTE not in saida.error + saida.notice


def test_defeito_inesperado_do_canal_tambem_nao_perde_o_registro(
    db_session: Session, cenario: Cenario, log_do_envio: pytest.LogCaptureFixture
) -> None:
    origem_id = _gravar_registro_de_origem(db_session, cenario)

    saida = notification.send(
        db_session,
        user_id=cenario.autor.id,
        request=_pedido(cenario),
        channel=CanalQueQuebra(),
    )
    db_session.commit()

    assert saida.situation == "erro"
    assert saida.notice.startswith(notification.UNEXPECTED_FAILURE)
    # The class name is enough in the trail; the traceback is for the log.
    assert saida.error is not None
    assert "RuntimeError" in saida.error
    assert "não deve ir para a trilha" not in saida.error
    assert "defeito do canal" in log_do_envio.text
    assert _origem_existe(db_session, origem_id)


@pytest.mark.usefixtures("envio_ligado")
def test_mensagem_longa_do_graph_e_cortada_antes_de_chegar_a_trilha(
    db_session: Session, cenario: Cenario
) -> None:
    gigante = {"error": {"code": "Gigante", "message": "palavra " * 2000}}
    http = ClienteHttpFalso(TOKEN_CONCEDIDO, _resposta_json(400, gigante))

    saida = _enviar_pelo_graph(db_session, cenario, http)

    assert saida.error is not None
    assert saida.error.startswith("O e-mail não foi enviado: o Microsoft Graph recusou o envio")
    assert "Gigante: palavra" in saida.error
    assert len(saida.error) < 100 + graph_mail.MAX_DETAIL_CHARS


@pytest.mark.usefixtures("envio_ligado")
def test_mensagem_longa_de_rede_e_cortada_no_limite_da_trilha(
    db_session: Session, cenario: Cenario
) -> None:
    http = ClienteHttpFalso(TOKEN_CONCEDIDO, OSError("x" * 5000))

    saida = _enviar_pelo_graph(db_session, cenario, http)

    assert saida.error is not None
    assert len(saida.error) == notification.MAX_TRAIL_ERROR_CHARS


# ── A notificação entra na transação da requisição ───────────────────────


def test_notificacao_e_desfeita_junto_com_a_transacao_quando_o_fluxo_falha_depois() -> None:
    notificacao_id = 0

    with pytest.raises(FalhaForcadaError), database.unidade_de_trabalho() as session:
        pessoa = Person(name="Autora", email="autora-rollback@example.invalid")
        gerente = Person(name="Gerente", email="gerente-rollback@example.invalid")
        cliente = Client(name="Cliente do rollback", active=True)
        session.add_all([pessoa, gerente, cliente])
        session.flush()
        autor = Collaborator(person_id=pessoa.id, general_profile="Membro", bond="Timenow")
        projeto = Project(
            client_id=cliente.id,
            manager_id=gerente.id,
            code="TN-2026-913",
            name="Projeto do rollback",
        )
        session.add_all([autor, projeto])
        session.flush()
        saida = notification.send(
            session,
            user_id=autor.id,
            request=NotificationRequest(
                kind=notification.TREASURY,
                project_id=projeto.id,
                recipients=["tesouraria@example.invalid"],
                subject="Cronograma de desembolso",
                body="Segue o cronograma.",
            ),
        )
        notificacao_id = saida.notification_id
        assert _trilha(session, notificacao_id)
        raise FalhaForcadaError

    with database.new_session() as session:
        assert _contar(session, Notification) == 0
        assert _trilha(session, notificacao_id) == []


# ── O pedido é conferido antes de qualquer envio ─────────────────────────


def test_pedido_sem_destinatario_e_recusado_e_nada_e_gravado(
    db_session: Session, cenario: Cenario
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        notification.send(
            db_session, user_id=cenario.autor.id, request=_pedido(cenario, recipients=[])
        )

    assert recusa.value.messages() == ["Informe ao menos um destinatário."]
    assert _contar(db_session, Notification) == 0


@pytest.mark.parametrize(
    "endereco",
    [
        "sem-arroba",
        "a@b",
        "a b@example.invalid",
        "a@@example.invalid",
        "<a@example.invalid>",
        "a@example.invalid, b@example.invalid",
        "a@example.invalid\r\nBcc: alguem@example.invalid",
        "",
        "   ",
        f"{'x' * 250}@example.invalid",
    ],
)
def test_destinatario_com_email_invalido_e_recusado(
    db_session: Session, cenario: Cenario, endereco: str
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        notification.send(
            db_session,
            user_id=cenario.autor.id,
            request=_pedido(cenario, recipients=["ok@example.invalid", endereco]),
        )

    assert recusa.value.messages()[0].startswith("E-mail de destinatário inválido:")
    assert _contar(db_session, Notification) == 0


def test_assunto_e_corpo_em_branco_sao_recusados_com_uma_mensagem_por_campo(
    db_session: Session, cenario: Cenario
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        notification.send(
            db_session,
            user_id=cenario.autor.id,
            request=_pedido(cenario, subject=" \n ", body="   "),
        )

    assert recusa.value.detail == {
        "destinatarios": "",
        "assunto": "Informe o assunto da notificação.",
        "corpo": "Informe o corpo da notificação.",
    }


def test_destinatarios_repetidos_valem_uma_vez_e_o_assunto_vira_uma_linha(
    db_session: Session, cenario: Cenario
) -> None:
    pedido = _pedido(
        cenario,
        recipients=[" Ana@Example.invalid ", "ana@example.invalid", "b@example.invalid"],
        subject="  Pauta\n de   riscos  ",
        body="\n  Corpo com margem.  \n",
    )

    saida = notification.send(db_session, user_id=cenario.autor.id, request=pedido)

    registro = db_session.get(Notification, saida.notification_id)
    assert registro is not None
    assert registro.recipients == "Ana@Example.invalid, b@example.invalid"
    assert registro.subject == "Pauta de riscos"
    assert registro.body == "Corpo com margem."
    assert saida.situation == "simulado"


def test_destinatarios_numa_string_e_defeito_de_quem_chama(
    db_session: Session, cenario: Cenario
) -> None:
    with pytest.raises(TypeError, match="lista de endereços"):
        notification.send(
            db_session,
            user_id=cenario.autor.id,
            request=_pedido(cenario, recipients="ana@example.invalid"),
        )

    assert _contar(db_session, Notification) == 0


def test_tipo_de_notificacao_desconhecido_e_defeito_de_quem_chama(
    db_session: Session, cenario: Cenario
) -> None:
    with pytest.raises(ValueError, match="Tipo de notificação desconhecido"):
        notification.send(
            db_session, user_id=cenario.autor.id, request=_pedido(cenario, kind="propaganda")
        )

    assert _contar(db_session, Notification) == 0


# ── A configuração do Graph não vaza ─────────────────────────────────────


@pytest.mark.usefixtures("envio_ligado")
def test_o_segredo_nao_aparece_na_representacao_das_configuracoes() -> None:
    configuracao = graph_mail.GraphSettings.from_environment()

    assert configuracao.client_secret == CREDENCIAL_DE_TESTE
    assert CREDENCIAL_DE_TESTE not in repr(configuracao)
    assert configuracao.missing_variables() == []


# ── O cliente HTTP real, sem rede ────────────────────────────────────────


class Conexoes:
    """What the fake connections saw, and how they answer."""

    def __init__(self) -> None:
        self.abertas: list[ConexaoFalsa] = []
        self.resposta = (202, b"")
        self.falha: Exception | None = None


class ConexaoFalsa:
    """Stands for ``http.client.HTTPSConnection``: records what it was asked and answers."""

    def __init__(self, conexoes: Conexoes, host: str, port: int | None, timeout: float) -> None:
        self._conexoes = conexoes
        self.host, self.port, self.timeout = host, port, timeout
        self.pedido: tuple[str, str, bytes, dict[str, str]] | None = None
        self.fechada = False
        conexoes.abertas.append(self)

    def request(self, method: str, url: str, *, body: bytes, headers: dict[str, str]) -> None:
        if self._conexoes.falha is not None:
            raise self._conexoes.falha
        self.pedido = (method, url, body, headers)

    def getresponse(self) -> ConexaoFalsa:
        return self

    @property
    def status(self) -> int:
        return self._conexoes.resposta[0]

    def read(self, limite: int) -> bytes:
        return self._conexoes.resposta[1][:limite]

    def close(self) -> None:
        self.fechada = True


@pytest.fixture
def conexoes(monkeypatch: pytest.MonkeyPatch) -> Conexoes:
    registro = Conexoes()
    monkeypatch.setattr(
        http.client,
        "HTTPSConnection",
        lambda host, port=None, *, timeout: ConexaoFalsa(registro, host, port, timeout),
    )
    return registro


def test_cliente_real_envia_post_https_e_devolve_o_status_e_o_corpo(conexoes: Conexoes) -> None:
    conexoes.resposta = (403, b'{"error": {"code": "ErrorAccessDenied"}}')

    resposta = StdlibHttpClient().post(
        "https://graph.microsoft.com/v1.0/users/a@example.invalid/sendMail?x=1",
        headers={"Content-Type": "application/json"},
        body=b"{}",
        timeout=7,
    )

    assert resposta == HttpResponse(status=403, body=b'{"error": {"code": "ErrorAccessDenied"}}')
    (conexao,) = conexoes.abertas
    assert (conexao.host, conexao.port, conexao.timeout) == ("graph.microsoft.com", None, 7)
    assert conexao.pedido == (
        "POST",
        "/v1.0/users/a@example.invalid/sendMail?x=1",
        b"{}",
        {"Content-Type": "application/json"},
    )
    assert conexao.fechada


def test_cliente_real_le_so_o_limite_da_resposta(conexoes: Conexoes) -> None:
    conexoes.resposta = (200, b"x" * (graph_mail.MAX_RESPONSE_BYTES + 10))

    resposta = StdlibHttpClient().post("https://exemplo.invalid/", headers={}, body=b"", timeout=1)

    assert len(resposta.body) == graph_mail.MAX_RESPONSE_BYTES


def test_cliente_real_fecha_a_conexao_quando_o_envio_falha(conexoes: Conexoes) -> None:
    conexoes.falha = ConnectionRefusedError("recusada")

    with pytest.raises(ConnectionRefusedError):
        StdlibHttpClient().post("https://exemplo.invalid/", headers={}, body=b"", timeout=1)

    assert conexoes.abertas[0].fechada


@pytest.mark.parametrize(
    "url", ["http://graph.microsoft.com/v1.0/x", "ftp://exemplo.invalid/x", "x"]
)
def test_cliente_real_recusa_endereco_que_nao_e_https(conexoes: Conexoes, url: str) -> None:
    with pytest.raises(ValueError, match="https"):
        StdlibHttpClient().post(url, headers={}, body=b"", timeout=1)

    assert conexoes.abertas == []
