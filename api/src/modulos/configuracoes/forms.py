"""Metadados dos grupos e campos da tela Parâmetros (ISSUE-076, D6).

Porte de ``grupos(p)`` e do ``exibir(c, v)`` do protótipo: os grupos por módulo,
os campos de cada um (tipo, unidade, limites, opções e o que é somente leitura) e
como um valor vigente se lê e se grava. As listas dinâmicas — critérios e classes
da avaliação, alçadas e pesos dos marcos de suprimentos, probabilidades dos
riscos, modelos de etapas da EAP e critérios do portfólio — saem dos valores
vigentes, como no protótipo; por isso tudo aqui é função dos valores, nunca
constante. O caminho de um campo é o da folha no payload
(``riscos.probabilidades.0.mediaPct``) e o seu id no formulário troca os pontos
por ``__``. A gravação recebe o formulário de volta por esses ids e devolve os
payloads por grupo de origem, prontos para ``service.save_parameter_group``.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from src.core.export_document import ValueKind, format_value
from src.core.import_values import convert, normalize_text, number_of
from src.core.money import format_brl
from src.core.spreadsheet_reader import RawCell

NUMERO = "numero"
MOEDA = "moeda"
SELECT = "select"
TEXTO = "texto"

SOMENTE_BASE = "Valor fixo (base da escala)."
SOMENTE_CADASTRO = "Lista fixa do cadastro."
SCALE_CHANGE_MESSAGE = (
    "A troca da escala de severidade muda as faixas e a contagem de riscos críticos em todo o "
    "sistema. Marque a confirmação para gravar."
)
JUSTIFICATION_MESSAGE = "Informe a justificativa da alteração (mínimo de 10 caracteres)."
NO_CHANGE_MESSAGE = "Nenhum valor foi alterado."
NUMBER_MESSAGE = "Informe um número."
INTEGER_MESSAGE = "Informe um número inteiro."
MONEY_MESSAGE = "Informe um valor em reais (ex.: 1.234,56)."
OPTION_MESSAGE = "Escolha uma das opções."

# Os nomes dos módulos do filtro, como o protótipo os lia; "CF" (Configurações) é
# o módulo do grupo Anexos, que o protótipo não mostrava e o GestNow versiona (D5a).
MODULE_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "02": "02 Planejamento",
        "03": "03 Gestão Financeira",
        "04": "04 Suprimentos",
        "05": "05 Gestão de Riscos",
        "06": "06 Gestão da Qualidade",
        "07": "07 HSE",
        "08": "08 Governança",
        "CF": "Configurações",
        "PF": "Portfólio",
    }
)

MODULE_OPTIONS: tuple[tuple[str, str], ...] = tuple(sorted(MODULE_NAMES.items()))

# O grupo da tela agrega um ou mais grupos de parâmetros do serviço; a gravação
# cria versão só para os grupos de origem cujos valores mudaram.
GROUP_SOURCES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "contratadas": ("avaliacaoContratada", "claims"),
        "financeiro": ("financeiro",),
        "suprimentos": ("suprimentos",),
        "riscos": ("riscos",),
        "qualidade": ("qualidade",),
        "hse": ("hse",),
        "planejamento": ("punch", "produtividade", "eap"),
        "governanca": ("mudancas", "licoes"),
        "portfolio": ("portfolio",),
        "anexos": ("anexos",),
    }
)

SCREEN_GROUP_OF: Mapping[str, str] = MappingProxyType(
    {
        service_group: screen_group
        for screen_group, service_groups in GROUP_SOURCES.items()
        for service_group in service_groups
    }
)

GROUP_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "contratadas": "Avaliação de contratadas",
        "financeiro": "Financeiro",
        "suprimentos": "Suprimentos",
        "riscos": "Riscos",
        "qualidade": "Qualidade",
        "hse": "HSE",
        "planejamento": "Planejamento",
        "governanca": "Governança",
        "portfolio": "Portfólio",
        "anexos": "Anexos",
    }
)

MARCO_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "requisicao": "Requisição",
        "rfx": "Emissão da RFx",
        "propostas": "Propostas recebidas",
        "eqTecnica": "Equalização técnica",
        "eqComercial": "Equalização comercial",
        "adjudicacao": "Aprovação / adjudicação",
        "pedido": "Pedido ou contrato",
        "documentos": "Documentos do fornecedor",
        "fabricacao": "Fabricação",
        "inspecao": "Inspeção / FAT",
        "embarque": "Embarque",
        "entrega": "Entrega",
    }
)


@dataclass(frozen=True)
class FieldOption:
    """Uma opção de um campo de escolha: o valor que a gravação usa e o texto que a pessoa lê."""

    valor: Any
    texto: str


@dataclass(frozen=True)
class ParameterField:
    """Um campo editável (ou somente leitura) de um grupo da tela."""

    caminho: str
    rotulo: str
    tipo: str
    unidade: str = ""
    minimo: float | None = None
    maximo: float | None = None
    passo: float | None = None
    opcoes: tuple[FieldOption, ...] = ()
    somente: bool = False
    ajuda: str = ""

    @property
    def field_id(self) -> str:
        """O id do campo no formulário: o caminho com ``__`` no lugar dos pontos."""
        return self.caminho.replace(".", "__")

    @property
    def grupo_parametro(self) -> str:
        """O grupo de parâmetros de origem: a raiz do caminho (``riscos.escalaAtiva`` -> riscos)."""
        return self.caminho.split(".", 1)[0]


@dataclass(frozen=True)
class ParameterGroupForm:
    """Um grupo da tela: os metadados do protótipo e os seus campos."""

    id: str
    modulo: str
    nome: str
    onde: str
    nota: str
    campos: tuple[ParameterField, ...]

    @property
    def modulo_nome(self) -> str:
        return MODULE_NAMES.get(self.modulo, self.modulo)


@dataclass(frozen=True)
class FieldLabel:
    """O rótulo de um caminho para o diff do histórico: o grupo da tela, o rótulo e o campo."""

    grupo: str
    rotulo: str
    campo: ParameterField


@dataclass(frozen=True)
class FieldView:
    """Um campo do formulário com o valor vigente (ou o que a pessoa digitou) pronto para o input."""

    campo: ParameterField
    input_value: str


@dataclass(frozen=True)
class ParsedGroupForm:
    """O que a gravação de um grupo carrega: os payloads por origem, os campos que mudaram e os erros."""

    values: Mapping[str, Mapping[str, Any]]
    changed: tuple[ParameterField, ...]
    errors: Mapping[str, str]


def group_forms(values: Mapping[str, Mapping[str, Any]]) -> tuple[ParameterGroupForm, ...]:
    """Os grupos da tela, construídos dos valores vigentes, na ordem do protótipo."""
    avaliacao = values.get("avaliacaoContratada") or {}
    suprimentos = values.get("suprimentos") or {}
    riscos = values.get("riscos") or {}
    eap = values.get("eap") or {}
    portfolio = values.get("portfolio") or {}
    return (
        _contratadas(avaliacao),
        _financeiro(),
        _suprimentos(suprimentos),
        _riscos(riscos),
        _qualidade(),
        _hse(),
        _planejamento(eap),
        _governanca(),
        _portfolio(portfolio),
        _anexos(),
    )


def find_group(groups: tuple[ParameterGroupForm, ...], group_id: str) -> ParameterGroupForm | None:
    """O grupo da tela com o id, ou ``None`` quando não existe."""
    return next((group for group in groups if group.id == group_id), None)


def group_sources(group_id: str) -> tuple[str, ...]:
    """Os grupos de parâmetros de origem de um grupo da tela, na ordem da gravação."""
    return GROUP_SOURCES.get(group_id, ())


def labels(values: Mapping[str, Mapping[str, Any]]) -> dict[str, FieldLabel]:
    """O rótulo de cada caminho, para o histórico mostrar o antes e o depois pelo nome do campo."""
    return {
        field.caminho: FieldLabel(group.nome, field.rotulo, field)
        for group in group_forms(values)
        for field in group.campos
    }


# ── Leitura e escrita por caminho ────────────────────────────────────────


def value_at(values: Mapping[str, Any], path: str) -> Any:
    """O valor de um caminho com índice (``suprimentos.alcadas.0.ate``), ou ``None`` fora da árvore."""
    current: Any = values
    for segment in path.split("."):
        if isinstance(current, list):
            if not segment.isdigit() or int(segment) >= len(current):
                return None
            current = current[int(segment)]
        elif isinstance(current, Mapping):
            current = current.get(segment)
        else:
            return None
    return current


def write_at(values: dict[str, Any], path: str, value: Any) -> None:
    """Grava o valor no caminho, criando os dicionários e as listas que faltarem (como o protótipo)."""
    segments = path.split(".")
    current: Any = values
    for index, segment in enumerate(segments[:-1]):
        following = segments[index + 1]
        if isinstance(current, list):
            position = int(segment)
            while len(current) <= position:
                current.append(None)
            if current[position] is None:
                current[position] = [] if following.isdigit() else {}
            current = current[position]
        else:
            child = current.get(segment)
            if child is None:
                child = [] if following.isdigit() else {}
                current[segment] = child
            current = child
    last = segments[-1]
    if isinstance(current, list):
        position = int(last)
        while len(current) <= position:
            current.append(None)
        current[position] = value
    else:
        current[last] = value


def leaf_values(values: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """As folhas de um payload pelo caminho com índice, na ordem da travessia (o diff do histórico)."""
    rows: dict[str, Any] = {}
    for key, value in values.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            rows.update(leaf_values(value, path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                item_path = f"{path}.{index}"
                if isinstance(item, Mapping):
                    rows.update(leaf_values(item, item_path))
                else:
                    rows[item_path] = item
        else:
            rows[path] = value
    return rows


# ── Exibição e formulário ────────────────────────────────────────────────


def exibir(field: ParameterField, value: Any) -> str:
    """O valor como a pessoa o lê: opção do select, moeda por extenso, número com unidade e ``·`` vazio."""
    if value is None or value == "":
        return "·"
    if field.tipo == MOEDA:
        return format_brl(int(value))
    if field.tipo == SELECT:
        return _option_text(field, value)
    if field.tipo == TEXTO:
        return _text_value(value)
    number = float(value)
    digits = 0 if number == int(number) else 2
    unit = f" {field.unidade}" if field.unidade else ""
    return f"{format_value(ValueKind.DECIMAL, value, digits)}{unit}"


def _option_text(field: ParameterField, value: Any) -> str:
    for option in field.opcoes:
        if str(option.valor) == str(value):
            return option.texto
    return str(value)


def _text_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def input_text(field: ParameterField, value: Any) -> str:
    """O valor vigente como o input do formulário o mostra: moeda em reais, número sem zeros à toa."""
    if value is None:
        return ""
    if field.tipo == MOEDA:
        return format_brl(int(value))
    if field.tipo == SELECT:
        return str(value)
    if field.tipo == TEXTO:
        return _text_value(value)
    return _number_text(value)


def _number_text(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def field_views(
    group: ParameterGroupForm,
    values: Mapping[str, Mapping[str, Any]],
    form: Mapping[str, str] | None = None,
) -> tuple[FieldView, ...]:
    """Os campos do grupo com o valor vigente no input; a recusa devolve o que a pessoa digitou."""
    typed = form or {}
    return tuple(
        FieldView(
            campo=field,
            input_value=typed.get(
                field.field_id, input_text(field, value_at(values, field.caminho))
            ),
        )
        for field in group.campos
    )


# ── Gravação ─────────────────────────────────────────────────────────────


def parse_money(text: str) -> int | None:
    """Os centavos de um valor escrito em reais (``1.234,56``), ou ``None`` quando não é um."""
    if not text.strip():
        return None
    converted = convert(RawCell(value=text), ValueKind.MONEY)
    value = converted.value
    return value if converted.problem is None and isinstance(value, int) else None


def parse_field_value(field: ParameterField, text: str, *, current: Any) -> tuple[Any, str | None]:
    """O valor digitado no tipo do campo e, quando não serve, a mensagem do campo."""
    if field.tipo == SELECT:
        return _selected_option(field, text)
    if field.tipo == MOEDA:
        cents = parse_money(text)
        return (cents, None) if cents is not None else (None, MONEY_MESSAGE)
    number = number_of(text)
    if number is None:
        return None, NUMBER_MESSAGE
    if isinstance(current, int) and not isinstance(current, bool):
        if number != number.to_integral_value():
            return None, INTEGER_MESSAGE
        return int(number), None
    return float(number), None


def _selected_option(field: ParameterField, text: str) -> tuple[Any, str | None]:
    for option in field.opcoes:
        if str(option.valor) == text:
            return option.valor, None
    return None, OPTION_MESSAGE


def parse_group_form(
    group: ParameterGroupForm,
    current: Mapping[str, Mapping[str, Any]],
    form: Mapping[str, str],
) -> ParsedGroupForm:
    """Lê o formulário do grupo: os payloads por origem, os campos que mudaram e os erros por caminho."""
    payloads: dict[str, Any] = {
        service_group: deepcopy(dict(current.get(service_group) or {}))
        for service_group in group_sources(group.id)
    }
    errors: dict[str, str] = {}
    changed: list[ParameterField] = []
    for field in group.campos:
        if field.somente:
            continue
        text = (form.get(field.field_id) or "").strip()
        actual = value_at(current, field.caminho)
        value, problem = parse_field_value(field, text, current=actual)
        if problem is not None:
            errors[field.caminho] = problem
            continue
        if not same_value(value, actual):
            changed.append(field)
        write_at(payloads, field.caminho, value)
    if len((form.get("justificativa") or "").strip()) < 10:
        errors["justificativa"] = JUSTIFICATION_MESSAGE
    if (
        group.id == "riscos"
        and any(field.caminho == "riscos.escalaAtiva" for field in changed)
        and (form.get("confirmar_escala") or "") != "sim"
    ):
        errors["riscos.escalaAtiva"] = SCALE_CHANGE_MESSAGE
    return ParsedGroupForm(values=payloads, changed=tuple(changed), errors=errors)


def same_value(left: Any, right: Any) -> bool:
    """Se dois valores são o mesmo, com número comparado como número (``25`` vale ``25.0``)."""
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return float(left) == float(right)
    return left == right


# ── Construção dos grupos ────────────────────────────────────────────────


def _map(values: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    inner = values.get(key)
    return inner if isinstance(inner, Mapping) else {}


def _rows(values: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    items = values.get(key)
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, Mapping)]


def _text_of(values: Mapping[str, Any], key: str) -> str:
    return str(values.get(key, ""))


def _contratadas(avaliacao: Mapping[str, Any]) -> ParameterGroupForm:
    fields: list[ParameterField] = []
    for index, criterio in enumerate(_rows(avaliacao, "criterios")):
        fields.append(
            ParameterField(
                caminho=f"avaliacaoContratada.criterios.{index}.peso",
                rotulo=f"Peso: {_text_of(criterio, 'nome')}",
                tipo=NUMERO,
                unidade="%",
                minimo=0,
                maximo=100,
            )
        )
    classes = _rows(avaliacao, "classes")
    for index, classe in enumerate(classes):
        last = index == len(classes) - 1
        fields.append(
            ParameterField(
                caminho=f"avaliacaoContratada.classes.{index}.minimo",
                rotulo=(
                    f"Nota mínima da classe {_text_of(classe, 'classe')} "
                    f"({_text_of(classe, 'descricao')})"
                ),
                tipo=NUMERO,
                minimo=0,
                maximo=100,
                somente=last,
                ajuda=SOMENTE_BASE if last else "",
            )
        )
    fields.append(
        ParameterField(
            caminho="avaliacaoContratada.notaExigePlano",
            rotulo="Nota de critério que exige evidência e plano de melhoria (igual ou abaixo)",
            tipo=NUMERO,
            minimo=1,
            maximo=4,
        )
    )
    fields.append(
        ParameterField(
            caminho="claims.prazoNotificacaoPadraoDias",
            rotulo="Prazo contratual padrão de notificação de claim",
            tipo=NUMERO,
            unidade="dias",
            minimo=1,
            maximo=180,
        )
    )
    return ParameterGroupForm(
        id="contratadas",
        modulo="03",
        nome=GROUP_NAMES["contratadas"],
        onde="03 Contratos, 04 Fornecedores",
        nota="Pesos somam 100%; notas mínimas decrescentes de A para D.",
        campos=tuple(fields),
    )


def _financeiro() -> ParameterGroupForm:
    fields = [
        ParameterField(
            caminho=f"financeiro.faixasDesvio.{index}",
            rotulo=f"Faixa {index + 1} do mapa de calor",
            tipo=NUMERO,
            unidade="%",
            minimo=0,
            maximo=100,
            passo=0.5,
        )
        for index in range(3)
    ]
    fields.append(
        ParameterField(
            caminho="financeiro.contingencia.toleranciaConsumoPP",
            rotulo="Contingência: tolerância do consumo acima do avanço físico",
            tipo=NUMERO,
            unidade="p.p.",
            minimo=0,
            maximo=50,
            passo=1,
        )
    )
    fields.append(
        ParameterField(
            caminho="financeiro.contingencia.coberturaMinimaPct",
            rotulo="Contingência: cobertura mínima da exposição a riscos",
            tipo=NUMERO,
            unidade="%",
            minimo=0,
            maximo=300,
            passo=5,
        )
    )
    return ParameterGroupForm(
        id="financeiro",
        modulo="03",
        nome=GROUP_NAMES["financeiro"],
        onde="03 Mapa de controle, EAC e Contingência",
        nota=(
            "Faixas crescentes do mapa de calor do desvio da projeção sobre o orçado; "
            "alertas da contingência."
        ),
        campos=tuple(fields),
    )


def _suprimentos(suprimentos: Mapping[str, Any]) -> ParameterGroupForm:
    fields = [
        ParameterField(
            caminho="suprimentos.propostasMinimas",
            rotulo="Propostas mínimas por processo",
            tipo=NUMERO,
            minimo=1,
            maximo=10,
        ),
        ParameterField(
            caminho="suprimentos.folgaAlertaDias",
            rotulo="Folga de alerta em relação ao ROS",
            tipo=NUMERO,
            unidade="dias",
            minimo=0,
            maximo=60,
        ),
    ]
    alcadas = [item for item in _rows(suprimentos, "alcadas") if item.get("ate") is not None]
    for index, alcada in enumerate(alcadas):
        fields.append(
            ParameterField(
                caminho=f"suprimentos.alcadas.{index}.ate",
                rotulo=f"Alçada: {_text_of(alcada, 'papel')} até",
                tipo=MOEDA,
            )
        )
    for chave in _map(suprimentos, "pesosMarcos"):
        fields.append(
            ParameterField(
                caminho=f"suprimentos.pesosMarcos.{chave}",
                rotulo=f"Peso do marco: {MARCO_NAMES.get(chave, chave)}",
                tipo=NUMERO,
                unidade="%",
                minimo=0,
                maximo=100,
            )
        )
    return ParameterGroupForm(
        id="suprimentos",
        modulo="04",
        nome=GROUP_NAMES["suprimentos"],
        onde="04 Processos, Diligenciamento e MAS",
        nota=(
            "Alçadas com tetos crescentes (a última sem teto); pesos dos marcos do MAS somam 100%."
        ),
        campos=tuple(fields),
    )


def _riscos(riscos: Mapping[str, Any]) -> ParameterGroupForm:
    escalas = _map(riscos, "escalas")
    options = tuple(
        FieldOption(valor=chave, texto=str(escala.get("nome", chave)))
        for chave, escala in escalas.items()
    )
    fields = [
        ParameterField(
            caminho="riscos.escalaAtiva",
            rotulo="Escala de severidade ativa",
            tipo=SELECT,
            opcoes=options,
        )
    ]
    for chave, nome in (
        ("critico", "Crítico"),
        ("alto", "Alto"),
        ("moderado", "Moderado"),
        ("baixo", "Baixo"),
    ):
        fields.append(
            ParameterField(
                caminho=f"riscos.cadenciaDias.{chave}",
                rotulo=f"Cadência máxima de revisão: {nome}",
                tipo=NUMERO,
                unidade="dias",
                minimo=1,
                maximo=365,
            )
        )
    for index, probabilidade in enumerate(_rows(riscos, "probabilidades")):
        fields.append(
            ParameterField(
                caminho=f"riscos.probabilidades.{index}.mediaPct",
                rotulo=(
                    f"Probabilidade média: {_text_of(probabilidade, 'nome')} "
                    f"({_text_of(probabilidade, 'faixa')})"
                ),
                tipo=NUMERO,
                unidade="%",
                minimo=1,
                maximo=99,
            )
        )
    fields.append(
        ParameterField(
            caminho="riscos.pautaDiasAntesDoPrazo",
            rotulo="Pauta: dias antes do prazo do alvo",
            tipo=NUMERO,
            unidade="dias",
            minimo=1,
            maximo=180,
        )
    )
    fields.append(
        ParameterField(
            caminho="riscos.revisaoAlertaDias",
            rotulo="Alerta de revisão próxima",
            tipo=NUMERO,
            unidade="dias",
            minimo=1,
            maximo=90,
        )
    )
    return ParameterGroupForm(
        id="riscos",
        modulo="05",
        nome=GROUP_NAMES["riscos"],
        onde="05 Riscos e Início",
        nota=(
            "Trocar a escala muda a contagem de riscos críticos em todo o sistema. Cadência "
            "crescente da faixa mais grave para a mais leve; probabilidades médias crescentes."
        ),
        campos=tuple(fields),
    )


def _qualidade() -> ParameterGroupForm:
    fields = [
        ParameterField(
            caminho=f"qualidade.prazoTratamentoDias.{chave}",
            rotulo=f"Prazo de tratamento da RNC: {nome}",
            tipo=NUMERO,
            unidade="dias",
            minimo=1,
            maximo=180,
        )
        for chave, nome in (("critica", "Crítica"), ("maior", "Maior"), ("menor", "Menor"))
    ]
    fields.extend(
        [
            ParameterField(
                caminho="qualidade.verificacaoEficaciaDias",
                rotulo="Espera até a verificação de eficácia",
                tipo=NUMERO,
                unidade="dias",
                minimo=0,
                maximo=180,
            ),
            ParameterField(
                caminho="qualidade.metaAprovacaoInspecaoPct",
                rotulo="Meta de aprovação em inspeções",
                tipo=NUMERO,
                unidade="%",
                minimo=1,
                maximo=100,
            ),
            ParameterField(
                caminho="qualidade.metaConformidadeAuditoriaPct",
                rotulo="Meta de conformidade em auditorias",
                tipo=NUMERO,
                unidade="%",
                minimo=1,
                maximo=100,
            ),
            ParameterField(
                caminho="qualidade.notificacaoClienteHoras",
                rotulo="Antecedência da notificação ao cliente (pontos H e W)",
                tipo=NUMERO,
                unidade="horas",
                minimo=0,
                maximo=240,
            ),
        ]
    )
    return ParameterGroupForm(
        id="qualidade",
        modulo="06",
        nome=GROUP_NAMES["qualidade"],
        onde="06 Gestão da Qualidade",
        nota="Prazos de tratamento crescentes da severidade Crítica para a Menor.",
        campos=tuple(fields),
    )


def _hse() -> ParameterGroupForm:
    return ParameterGroupForm(
        id="hse",
        modulo="07",
        nome=GROUP_NAMES["hse"],
        onde="07 HSE e Início",
        nota="A investigação preliminar não pode vencer antes da comunicação.",
        campos=(
            ParameterField(
                caminho="hse.baseTaxa",
                rotulo="Base das taxas",
                tipo=SELECT,
                opcoes=(
                    FieldOption(valor=1_000_000, texto="1.000.000 HHT (NBR 14280)"),
                    FieldOption(valor=200_000, texto="200.000 HHT (OSHA)"),
                ),
            ),
            ParameterField(
                caminho="hse.prazos.comunicacaoHoras",
                rotulo="Prazo de comunicação",
                tipo=NUMERO,
                unidade="horas",
                minimo=1,
                maximo=240,
            ),
            ParameterField(
                caminho="hse.prazos.investigacaoPreliminarHoras",
                rotulo="Prazo da investigação preliminar",
                tipo=NUMERO,
                unidade="horas",
                minimo=1,
                maximo=720,
            ),
            ParameterField(
                caminho="hse.prazos.relatorioFinalDias",
                rotulo="Prazo do relatório final (LTI e HiPo)",
                tipo=NUMERO,
                unidade="dias",
                minimo=1,
                maximo=180,
            ),
            ParameterField(
                caminho="hse.referenciaPiramide",
                rotulo="Referência da pirâmide",
                tipo=SELECT,
                opcoes=(
                    FieldOption(valor="bird", texto="Bird (1:10:30:600)"),
                    FieldOption(valor="heinrich", texto="Heinrich (1:29:300)"),
                ),
            ),
            ParameterField(
                caminho="hse.metas.observacoesPor10MilHht",
                rotulo="HSE: meta de observações comportamentais por 10 mil HHT",
                tipo=NUMERO,
                minimo=0,
                maximo=1000,
            ),
            ParameterField(
                caminho="hse.metas.desviosPor10MilHht",
                rotulo="HSE: meta de relato de desvios por 10 mil HHT",
                tipo=NUMERO,
                minimo=0,
                maximo=1000,
            ),
        ),
    )


def _planejamento(eap: Mapping[str, Any]) -> ParameterGroupForm:
    fields = [
        ParameterField(
            caminho="punch.agingFaixas.0",
            rotulo="Punch list: faixa 1 do tempo em aberto",
            tipo=NUMERO,
            unidade="dias",
            minimo=1,
            maximo=365,
        ),
        ParameterField(
            caminho="punch.agingFaixas.1",
            rotulo="Punch list: faixa 2 do tempo em aberto",
            tipo=NUMERO,
            unidade="dias",
            minimo=1,
            maximo=365,
        ),
        ParameterField(
            caminho="produtividade.jornadaDiariaHoras",
            rotulo="Produtividade: jornada diária de referência",
            tipo=NUMERO,
            unidade="h",
            minimo=4,
            maximo=12,
            passo=0.1,
        ),
        ParameterField(
            caminho="produtividade.metaTrabalhandoPct",
            rotulo="Produtividade: meta de pessoas trabalhando",
            tipo=NUMERO,
            unidade="%",
            minimo=1,
            maximo=100,
        ),
        ParameterField(
            caminho="produtividade.metaUtilizacaoPct",
            rotulo="Produtividade: meta de utilização da jornada",
            tipo=NUMERO,
            unidade="%",
            minimo=1,
            maximo=100,
        ),
        ParameterField(
            caminho="produtividade.aderenciaFaixas.0",
            rotulo="Produtividade: aderência semanal, alerta abaixo de",
            tipo=NUMERO,
            unidade="%",
            minimo=1,
            maximo=100,
        ),
        ParameterField(
            caminho="produtividade.aderenciaFaixas.1",
            rotulo="Produtividade: aderência semanal, no plano a partir de",
            tipo=NUMERO,
            unidade="%",
            minimo=1,
            maximo=100,
        ),
        ParameterField(
            caminho="produtividade.pfFaixas.0",
            rotulo="Produtividade: fator de produtividade no orçado até",
            tipo=NUMERO,
            minimo=0.5,
            maximo=3,
            passo=0.01,
        ),
        ParameterField(
            caminho="produtividade.pfFaixas.1",
            rotulo="Produtividade: fator de produtividade em atenção até",
            tipo=NUMERO,
            minimo=0.5,
            maximo=3,
            passo=0.01,
        ),
        ParameterField(
            caminho="produtividade.spiFaixas.0",
            rotulo="Produtividade: SPI de quantidades em alerta abaixo de",
            tipo=NUMERO,
            minimo=0.1,
            maximo=1.5,
            passo=0.01,
        ),
        ParameterField(
            caminho="produtividade.spiFaixas.1",
            rotulo="Produtividade: SPI de quantidades no plano a partir de",
            tipo=NUMERO,
            minimo=0.1,
            maximo=1.5,
            passo=0.01,
        ),
        ParameterField(
            caminho="produtividade.atrasoInicioFaixasMin.0",
            rotulo="Produtividade: atraso médio de início no plano até",
            tipo=NUMERO,
            unidade="min",
            minimo=0,
            maximo=240,
        ),
        ParameterField(
            caminho="produtividade.atrasoInicioFaixasMin.1",
            rotulo="Produtividade: atraso médio de início em alerta acima de",
            tipo=NUMERO,
            unidade="min",
            minimo=0,
            maximo=240,
        ),
        ParameterField(
            caminho="produtividade.semanasMedia",
            rotulo="Produtividade: janela da média móvel",
            tipo=NUMERO,
            unidade="semanas",
            minimo=1,
            maximo=12,
        ),
        ParameterField(
            caminho="eap.faixasDesvioPP.0",
            rotulo="EAP: desvio físico em atenção até",
            tipo=NUMERO,
            unidade="p.p.",
            minimo=0.5,
            maximo=50,
            passo=0.5,
        ),
        ParameterField(
            caminho="eap.faixasDesvioPP.1",
            rotulo="EAP: desvio físico em alerta acima de",
            tipo=NUMERO,
            unidade="p.p.",
            minimo=0.5,
            maximo=50,
            passo=0.5,
        ),
        ParameterField(
            caminho="eap.pesoMaximoPacotePct",
            rotulo="EAP: peso máximo de um pacote",
            tipo=NUMERO,
            unidade="%",
            minimo=1,
            maximo=100,
        ),
        ParameterField(
            caminho="eap.estimadoMaximoPct",
            rotulo="EAP: peso máximo com percentual estimado",
            tipo=NUMERO,
            unidade="%",
            minimo=0.5,
            maximo=100,
            passo=0.5,
        ),
    ]
    for index, modelo in enumerate(_rows(eap, "modelosEtapas")):
        for position, etapa in enumerate(_rows(modelo, "etapas")):
            fields.append(
                ParameterField(
                    caminho=f"eap.modelosEtapas.{index}.etapas.{position}.peso",
                    rotulo=(f"EAP, modelo {_text_of(modelo, 'nome')}: {_text_of(etapa, 'nome')}"),
                    tipo=NUMERO,
                    unidade="%",
                    minimo=0,
                    maximo=100,
                )
            )
    return ParameterGroupForm(
        id="planejamento",
        modulo="02",
        nome=GROUP_NAMES["planejamento"],
        onde="02 EAP, Produtividade e Punch list",
        nota="Faixas crescentes; cada modelo de etapas da EAP soma 100.",
        campos=tuple(fields),
    )


def _governanca() -> ParameterGroupForm:
    return ParameterGroupForm(
        id="governanca",
        modulo="08",
        nome=GROUP_NAMES["governanca"],
        onde="08 Mudanças e Lições",
        nota="Alçada do gerente entre 0 e 10% do orçamento; prazos entre 1 e 90 dias.",
        campos=(
            ParameterField(
                caminho="mudancas.alcadaGerentePctOrcamento",
                rotulo="Alçada do gerente do projeto (sem impacto em marco contratual)",
                tipo=NUMERO,
                unidade="% do orçamento",
                minimo=0.1,
                maximo=10,
                passo=0.1,
            ),
            ParameterField(
                caminho="mudancas.prazoAnaliseDias",
                rotulo="Prazo da análise de impacto",
                tipo=NUMERO,
                unidade="dias",
                minimo=1,
                maximo=90,
            ),
            ParameterField(
                caminho="mudancas.quorumComite",
                rotulo="Quórum do Comitê de Controle de Mudanças",
                tipo=NUMERO,
                unidade="participantes",
                minimo=2,
                maximo=15,
            ),
            ParameterField(
                caminho="mudancas.prazoAcoesDias",
                rotulo="Prazo das ações de implementação",
                tipo=NUMERO,
                unidade="dias",
                minimo=1,
                maximo=90,
            ),
            ParameterField(
                caminho="mudancas.ratificacaoDias",
                rotulo="Ratificação da mudança emergencial",
                tipo=NUMERO,
                unidade="dias",
                minimo=1,
                maximo=90,
            ),
            ParameterField(
                caminho="licoes.alertaSemRegistroDias",
                rotulo="Alerta de projeto sem lição registrada",
                tipo=NUMERO,
                unidade="dias",
                minimo=30,
                maximo=365,
            ),
        ),
    )


def _portfolio(portfolio: Mapping[str, Any]) -> ParameterGroupForm:
    fields = [
        ParameterField(
            caminho=f"portfolio.criterios.{index}.peso",
            rotulo=f"Peso: {_text_of(criterio, 'nome')}",
            tipo=NUMERO,
            unidade="%",
            minimo=0,
            maximo=100,
        )
        for index, criterio in enumerate(_rows(portfolio, "criterios"))
    ]
    return ParameterGroupForm(
        id="portfolio",
        modulo="PF",
        nome=GROUP_NAMES["portfolio"],
        onde="Início, Curvas S e índices da carteira",
        nota="Pesos dos critérios somam 100%; as notas dos projetos ficam na Ponderação do Início.",
        campos=tuple(fields),
    )


def _anexos() -> ParameterGroupForm:
    return ParameterGroupForm(
        id="anexos",
        modulo="CF",
        nome=GROUP_NAMES["anexos"],
        onde="Envio e download de anexos em todos os módulos",
        nota=(
            "Limite e tipos do próximo envio; o download confere a permissão do registro de "
            "origem (D5a)."
        ),
        campos=(
            ParameterField(
                caminho="anexos.tamanhoMaximoMb",
                rotulo="Tamanho máximo do arquivo",
                tipo=NUMERO,
                unidade="MB",
                minimo=1,
                maximo=100,
            ),
            ParameterField(
                caminho="anexos.tiposAceitos",
                rotulo="Tipos aceitos",
                tipo=TEXTO,
                somente=True,
                ajuda=SOMENTE_CADASTRO,
            ),
        ),
    )


def matches(group: ParameterGroupForm, field: ParameterField, search: str) -> bool:
    """Se o campo passa na busca, como o ``passa`` do protótipo (rótulo, grupo e caminho)."""
    if not search:
        return True
    haystack = f"{field.rotulo} {group.nome} {field.caminho}"
    return normalize_text(search) in normalize_text(haystack)
