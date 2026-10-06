"""SharePoint Lists — o gancho de persistência corporativa.

Este arquivo é o **ponto de entrada já preparado** para trocar o JSON
local por listas do SharePoint. Ele implementa a mesma porta
(`core.repositorio.Repositorio`), então ligar a integração não toca em
nenhuma tela, blueprint ou regra de domínio:

    setx PROGRAMACAO_ORIGEM sharepoint
    setx SHAREPOINT_SITE_ID  "contoso.sharepoint.com,<guid>,<guid>"
    setx SHAREPOINT_TENANT_ID  "<guid>"
    setx SHAREPOINT_CLIENT_ID  "<guid>"
    setx SHAREPOINT_CLIENT_SECRET  "<segredo>"

O que falta para funcionar está isolado em dois lugares — `_token()` e
`_chamar()`. O resto (mapa de listas, nome de coluna, conversão de tipo)
já está escrito abaixo, porque é a parte que depende de decisão nossa e
não de credencial.

Por que fica pronto e desligado: o mapeamento de colunas é a parte que se
perde entre uma pessoa e outra. Escrito aqui, ele sobrevive à troca de
quem mantém o app; deixado para depois, vira arqueologia.

## Mapa de listas

| Agregado       | Lista SharePoint            | Chave natural          |
|----------------|-----------------------------|------------------------|
| atividades     | `ProgramacaoAtividades`     | `Semana` + `IDExclusiva` |
| janelas        | `ProgramacaoJanelas`        | `Empresa`              |
| colaboradores  | `ProgramacaoColaboradores`  | `Email`                |
| cadastros      | `ProgramacaoCadastros`      | `Tipo` + `Valor`       |
| parâmetros     | `ProgramacaoParametros`     | `Chave`                |
| solicitações   | `ProgramacaoGovernanca`     | `Id`                   |

Os sete dias viajam em colunas próprias (`Prev2a`…`PrevDom`,
`Real2a`…`RealDom`, `Noite2a`…`NoiteDom`) em vez de um JSON em texto:
assim a lista continua filtrável e somável dentro do próprio SharePoint,
que é metade do motivo de usá-lo.
"""

from __future__ import annotations

import os

from src.core.repositorio import Repositorio

GRAPH = "https://graph.microsoft.com/v1.0"
ESCOPO = "https://graph.microsoft.com/.default"

LISTAS = {
    "atividades": "ProgramacaoAtividades",
    "janelas": "ProgramacaoJanelas",
    "colaboradores": "ProgramacaoColaboradores",
    "cadastros": "ProgramacaoCadastros",
    "parametros": "ProgramacaoParametros",
    "solicitacoes": "ProgramacaoGovernanca",
}

# campo do domínio → coluna interna da lista
COLUNAS_ATIVIDADE = {
    "item": "Item",
    "semana": "Semana",
    "id_exclusiva": "IDExclusiva",
    "atividade": "Atividade",
    "local": "Local",
    "empresa": "Empresa",
    "responsavel": "FiscalResponsavel",
    "encarregado": "Encarregado",
    "prod_prevista": "ProdPrevista",
    "unidade": "Unidade",
    "situacao": "Situacao",
    "aprovacao_realizado": "AprovacaoRealizado",
    "observacoes_fornecedor": "ObservacoesFornecedor",
    "comentarios_timenow": "ComentariosTimenow",
    "criado_em": "CriadoEm",
    "criado_por": "CriadoPor",
    "atualizado_em": "AtualizadoEm",
    "atualizado_por": "AtualizadoPor",
}

SUFIXO_DIAS = ("2a", "3a", "4a", "5a", "6a", "Sab", "Dom")

COLUNAS_DIAS = {
    "dias_previsto": tuple(f"Prev{s}" for s in SUFIXO_DIAS),
    "dias_realizado": tuple(f"Real{s}" for s in SUFIXO_DIAS),
    "dias_noite": tuple(f"Noite{s}" for s in SUFIXO_DIAS),
}


def configurado() -> bool:
    """True quando as variáveis mínimas da integração estão definidas."""
    return all(
        os.environ.get(nome)
        for nome in (
            "SHAREPOINT_SITE_ID",
            "SHAREPOINT_TENANT_ID",
            "SHAREPOINT_CLIENT_ID",
        )
    )


def para_lista(atividade: dict) -> dict:
    """Converte uma atividade do domínio nos campos da lista."""
    campos = {
        coluna: atividade.get(chave)
        for chave, coluna in COLUNAS_ATIVIDADE.items()
        if atividade.get(chave) is not None
    }
    for chave, colunas in COLUNAS_DIAS.items():
        valores = atividade.get(chave) or [0.0] * 7
        for i, coluna in enumerate(colunas):
            campos[coluna] = float(valores[i]) if i < len(valores) else 0.0
    return campos


def do_lista(campos: dict) -> dict:
    """Converte os campos da lista de volta para o dicionário do domínio."""
    atividade = {chave: campos.get(coluna) for chave, coluna in COLUNAS_ATIVIDADE.items()}
    for chave, colunas in COLUNAS_DIAS.items():
        atividade[chave] = [float(campos.get(c) or 0) for c in colunas]
    atividade["key"] = (
        f"{str(atividade.get('semana', '')).replace('/', '-')}::{atividade.get('id_exclusiva', '')}"
    )
    return atividade


class IntegracaoIndisponivelError(RuntimeError):
    """A integração está selecionada mas ainda não foi ligada."""


class RepositorioSharePoint(Repositorio):
    """Implementação da porta sobre listas do SharePoint.

    Cada método abaixo é uma chamada ao Graph com o mapa de colunas já
    resolvido. O que impede de rodar hoje é o `_token()`; enquanto ele
    não existir, a classe recusa a operação com uma mensagem que diz
    exatamente o que configurar, em vez de falhar com 500 no meio da tela.
    """

    def __init__(self) -> None:
        self.site = os.environ.get("SHAREPOINT_SITE_ID", "")

    # -- ligação ----------------------------------------------------
    def _token(self) -> str:
        raise IntegracaoIndisponivelError(
            "A integração com o SharePoint está selecionada "
            "(PROGRAMACAO_ORIGEM=sharepoint) mas a aquisição de token ainda "
            "não foi implementada. Ligue-a em api/src/integracoes/sharepoint.py "
            "com DefaultAzureCredential ou MSAL, ou volte para "
            "PROGRAMACAO_ORIGEM=json."
        )

    def _chamar(self, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
        raise IntegracaoIndisponivelError(
            f"Chamada {metodo} {caminho} não executada: integração desligada. "
            f"Corpo pronto com {len(corpo or {})} campo(s)."
        )

    def _url(self, agregado: str, sufixo: str = "") -> str:
        return f"{GRAPH}/sites/{self.site}/lists/{LISTAS[agregado]}/items{sufixo}"

    # -- atividades -------------------------------------------------
    def listar_atividades(self, semana: str | None = None) -> list[dict]:
        filtro = (
            f"?expand=fields&$filter=fields/Semana eq '{semana}'" if semana else "?expand=fields"
        )
        resposta = self._chamar("GET", self._url("atividades", filtro))
        return [do_lista(item.get("fields", {})) for item in resposta.get("value", [])]

    def obter_atividade(self, chave: str) -> dict | None:
        for atividade in self.listar_atividades():
            if atividade.get("key") == chave:
                return atividade
        return None

    def gravar_atividade(self, atividade: dict) -> dict:
        self._chamar("POST", self._url("atividades"), {"fields": para_lista(atividade)})
        return atividade

    def remover_atividade(self, chave: str) -> bool:
        self._chamar("DELETE", self._url("atividades", f"/{chave}"))
        return True

    def proximo_item(self, semana: str) -> int:
        return len(self.listar_atividades(semana)) + 1

    def nova_sequencia(self) -> str:
        raise IntegracaoIndisponivelError("Sequência precisa de coluna calculada na lista.")

    # -- cadastros --------------------------------------------------
    def listar_cadastro(self, nome: str) -> list[str]:
        filtro = f"?expand=fields&$filter=fields/Tipo eq '{nome}'"
        resposta = self._chamar("GET", self._url("cadastros", filtro))
        return [i["fields"].get("Valor", "") for i in resposta.get("value", [])]

    def gravar_cadastro(self, nome: str, valores: list[str]) -> list[str]:
        for valor in valores:
            self._chamar("POST", self._url("cadastros"), {"fields": {"Tipo": nome, "Valor": valor}})
        return valores

    # -- janelas ----------------------------------------------------
    def listar_janelas(self) -> list[dict]:
        resposta = self._chamar("GET", self._url("janelas", "?expand=fields"))
        return [i.get("fields", {}) for i in resposta.get("value", [])]

    def gravar_janela(self, janela: dict) -> dict:
        self._chamar("POST", self._url("janelas"), {"fields": janela})
        return janela

    # -- colaboradores ----------------------------------------------
    def listar_colaboradores(self) -> list[dict]:
        resposta = self._chamar("GET", self._url("colaboradores", "?expand=fields"))
        return [i.get("fields", {}) for i in resposta.get("value", [])]

    def gravar_colaborador(self, colaborador: dict) -> dict:
        self._chamar("POST", self._url("colaboradores"), {"fields": colaborador})
        return colaborador

    def remover_colaborador(self, email: str) -> bool:
        self._chamar("DELETE", self._url("colaboradores", f"/{email}"))
        return True

    # -- parâmetros --------------------------------------------------
    def obter_parametros(self) -> dict:
        resposta = self._chamar("GET", self._url("parametros", "?expand=fields"))
        return {
            i["fields"].get("Chave"): i["fields"].get("Valor") for i in resposta.get("value", [])
        }

    def gravar_parametros(self, parametros: dict) -> dict:
        for chave, valor in parametros.items():
            self._chamar(
                "POST",
                self._url("parametros"),
                {"fields": {"Chave": chave, "Valor": valor}},
            )
        return parametros

    # -- governança --------------------------------------------------
    def listar_solicitacoes(self) -> list[dict]:
        resposta = self._chamar("GET", self._url("solicitacoes", "?expand=fields"))
        return [i.get("fields", {}) for i in resposta.get("value", [])]

    def gravar_solicitacao(self, solicitacao: dict) -> dict:
        self._chamar("POST", self._url("solicitacoes"), {"fields": solicitacao})
        return solicitacao
