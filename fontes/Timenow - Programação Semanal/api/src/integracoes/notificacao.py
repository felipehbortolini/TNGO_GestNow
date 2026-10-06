"""Aviso por e-mail — o gancho, com o modo seco ligado por padrão.

Portado do projeto anterior e mantido na mesma forma: envio pelo Microsoft
Graph (`/users/{remetente}/sendMail`), autenticação por managed identity do
SWA ou client credentials.

**Nada é enviado enquanto `EMAIL_ATIVO` não for verdadeiro.** Sem a
variável, o módulo registra o que enviaria e devolve sucesso. É o
comportamento certo para um app que roda em demonstração: um gancho de
e-mail ligado por acidente manda mensagem para gente de verdade.

Configuração::

    setx EMAIL_ATIVO      true
    setx EMAIL_REMETENTE  programacao@timenow.com.br
    setx GRAPH_TOKEN      <token>       (provisório — ver `_token`)

Quem chama: ninguém, ainda. A facade é o lugar previsto — depois de
`validar_atividade`, para avisar o fornecedor, e depois de
`registrar_realizado`, para avisar o fiscal. Ficou fora do fluxo desta
entrega porque avisar automaticamente é decisão de processo, não de
código, e ela ainda não foi tomada.
"""

from __future__ import annotations

import logging
import os

GRAPH = "https://graph.microsoft.com/v1.0"

logger = logging.getLogger(__name__)


def ativo() -> bool:
    return os.environ.get("EMAIL_ATIVO", "").strip().lower() in ("true", "1", "sim")


def _token() -> str:
    """Token do Graph. Hoje só lê a variável; trocar por MSAL na ativação."""
    return os.environ.get("GRAPH_TOKEN", "")


def montar_mensagem(
    para: list[str],
    assunto: str,
    corpo_html: str,
    copia: list[str] | None = None,
    anexo: tuple[str, str] | None = None,
) -> dict:
    """O corpo que o Graph espera. Separado do envio para poder ser testado."""
    mensagem: dict = {
        "subject": assunto,
        "body": {"contentType": "HTML", "content": corpo_html},
        "toRecipients": [{"emailAddress": {"address": e}} for e in para],
    }
    if copia:
        mensagem["ccRecipients"] = [{"emailAddress": {"address": e}} for e in copia]
    if anexo:
        nome, conteudo_base64 = anexo
        mensagem["attachments"] = [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": nome,
                "contentType": "application/octet-stream",
                "contentBytes": conteudo_base64,
            }
        ]
    return {"message": mensagem, "saveToSentItems": True}


def enviar(
    para: list[str],
    assunto: str,
    corpo_html: str,
    copia: list[str] | None = None,
    anexo: tuple[str, str] | None = None,
) -> bool:
    """Envia, ou registra o que enviaria quando o modo seco está ligado."""
    if not ativo():
        logger.info("[e-mail em modo seco] para=%s assunto=%s", para, assunto)
        return True

    remetente = os.environ.get("EMAIL_REMETENTE", "")
    if not remetente or not _token():
        logger.warning("EMAIL_ATIVO está ligado, mas falta remetente ou token.")
        return False

    # A chamada HTTP fica para a ativação: hoje o projeto não tem cliente
    # HTTP nas dependências, e acrescentar um que ninguém usa é peso morto
    # no deploy. O corpo já sai pronto para um POST em
    # f"{GRAPH}/users/{remetente}/sendMail".
    corpo = montar_mensagem(para, assunto, corpo_html, copia, anexo)
    logger.warning(
        "Envio real não implementado. Payload pronto com %d destinatário(s) e "
        "%d campo(s) para POST em %s/users/%s/sendMail",
        len(para),
        len(corpo["message"]),
        GRAPH,
        remetente,
    )
    return False
