"""Parameter rules of section 7.4, one function per rule (D5a, D6).

Each rule receives the values of one group and returns the message to show or
``None`` when the boundary holds. ``validate_parameter_group`` maps the failing
rule to the field of the form, so a screen answers 422 with the message next
to the input. The rules are the port of ``GI.regras.validarParametros`` from
the prototype, with the same messages and the same boundaries.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from itertools import pairwise
from typing import Any


def validate_parameter_group(group: str, values: Mapping[str, Any]) -> dict[str, str]:
    """Errors of the group keyed by the field of the form, empty when it holds up."""
    errors: dict[str, str] = {}
    for field, check in _RULES.get(group, ()):
        message = check(values)
        if message:
            errors[field] = message
    return errors


# ── Helpers ──────────────────────────────────────────────────────────────


def _number(value: Any) -> float:
    """A number for comparison; garbage becomes NaN so every boundary fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _text(value: float) -> str:
    """A number as the prototype printed it in messages (no trailing zeros)."""
    return f"{value:g}"


def _dict(values: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    inner = values.get(key)
    return inner if isinstance(inner, Mapping) else {}


def _items(values: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    items = values.get(key)
    if not isinstance(items, Sequence) or isinstance(items, str):
        return []
    return [item for item in items if isinstance(item, Mapping)]


def _bands(values: Mapping[str, Any], key: str) -> tuple[float, float] | None:
    """The first two values of a band, ``None`` when absent and NaN when malformed."""
    bands = values.get(key)
    if bands is None:
        return None
    if isinstance(bands, Sequence) and not isinstance(bands, str) and len(bands) >= 2:
        return (_number(bands[0]), _number(bands[1]))
    return (float("nan"), float("nan"))


def _increasing(numbers: Sequence[float], *, strictly: bool = True) -> bool:
    if strictly:
        return all(current > previous for previous, current in pairwise(numbers))
    return all(current >= previous for previous, current in pairwise(numbers))


# ── 03 Contratos ─────────────────────────────────────────────────────────


def contractor_weight_total_error(values: Mapping[str, Any]) -> str | None:
    """Critérios da avaliação de contratadas somam 100%."""
    total = sum(_number(item.get("peso")) for item in _items(values, "criterios"))
    if total != 100:
        return f"A soma dos pesos da avaliação deve ser 100% (atual: {_text(total)}%)."
    return None


def contractor_class_minimums_error(values: Mapping[str, Any]) -> str | None:
    """Notas mínimas das classes A, B, C e D são estritamente decrescentes."""
    minimums = [_number(item.get("minimo")) for item in _items(values, "classes")]
    if not all(current < previous for previous, current in pairwise(minimums)):
        return "As notas mínimas das classes devem ser decrescentes de A para D."
    return None


# ── 07 HSE ───────────────────────────────────────────────────────────────


def hse_deadlines_error(values: Mapping[str, Any]) -> str | None:
    """Investigação preliminar não vence antes da comunicação; relatório final positivo."""
    deadlines = _dict(values, "prazos")
    communication = _number(deadlines.get("comunicacaoHoras"))
    preliminary = _number(deadlines.get("investigacaoPreliminarHoras"))
    final = _number(deadlines.get("relatorioFinalDias"))
    if not (communication > 0 and preliminary >= communication and final > 0):
        return "Prazos de HSE inválidos: a investigação preliminar não pode vencer antes da comunicação."
    return None


def hse_rate_base_error(values: Mapping[str, Any]) -> str | None:
    """Base das taxas é a NBR 14280 (1.000.000) ou a OSHA (200.000)."""
    if _number(values.get("baseTaxa")) not in (1_000_000, 200_000):
        return "Base das taxas de HSE deve ser 1.000.000 (NBR 14280) ou 200.000 (OSHA)."
    return None


def hse_proactive_targets_error(values: Mapping[str, Any]) -> str | None:
    """Metas proativas por 10 mil HHT ficam entre 0 e 1.000."""
    targets = _dict(values, "metas")
    observations = _number(targets.get("observacoesPor10MilHht"))
    deviations = _number(targets.get("desviosPor10MilHht"))
    if not (0 <= observations <= 1000 and 0 <= deviations <= 1000):
        return "As metas proativas de HSE (observações e desvios por 10 mil HHT) devem ficar entre 0 e 1.000."
    return None


# ── 04 Suprimentos ───────────────────────────────────────────────────────


def mas_weight_total_error(values: Mapping[str, Any]) -> str | None:
    """Pesos dos marcos do MAS somam 100%."""
    total = sum(_number(weight) for weight in _dict(values, "pesosMarcos").values())
    if total != 100:
        return f"A soma dos pesos dos marcos do MAS deve ser 100% (atual: {_text(total)}%)."
    return None


def supply_authority_limits_error(values: Mapping[str, Any]) -> str | None:
    """Alçadas de suprimentos têm tetos crescentes e a última sem teto."""
    limits: list[Any] = [item.get("ate") for item in _items(values, "alcadas")]
    if not limits:
        return None
    last = len(limits) - 1
    valid = all(_limit_holds(limits, index) for index in range(len(limits)))
    if not valid or limits[last] is not None:
        return "As alçadas de suprimentos devem ter tetos crescentes e a última sem teto."
    return None


def _limit_holds(limits: Sequence[Any], index: int) -> bool:
    if index == len(limits) - 1:
        return True
    value = _number(limits[index])
    return value > 0 and (index == 0 or value > _number(limits[index - 1]))


def minimum_proposals_error(values: Mapping[str, Any]) -> str | None:
    """Mínimo de propostas é 1 ou mais, quando informado."""
    proposals = values.get("propostasMinimas")
    if proposals is not None and not _number(proposals) >= 1:
        return "O mínimo de propostas deve ser 1 ou mais."
    return None


# ── 05 Riscos ────────────────────────────────────────────────────────────


def risk_review_cadence_error(values: Mapping[str, Any]) -> str | None:
    """Cadência cresce da faixa mais grave (Crítico) para a mais leve (Baixo)."""
    cadence = _dict(values, "cadenciaDias")
    if not cadence:
        return None
    sequence = [
        _number(cadence.get(key))
        for key in ("critico", "alto", "moderado", "baixo")
        if cadence.get(key) is not None
    ]
    valid = all(value > 0 for value in sequence) and _increasing(sequence, strictly=False)
    if not valid:
        return "A cadência de revisão deve crescer da faixa mais grave para a mais leve."
    return None


def risk_probabilities_error(values: Mapping[str, Any]) -> str | None:
    """Probabilidades médias das faixas são crescentes, entre 0 e 100%."""
    if not values.get("probabilidades"):
        return None
    means = [_number(item.get("mediaPct")) for item in _items(values, "probabilidades")]
    valid = all(0 < mean < 100 for mean in means) and _increasing(means)
    if not valid:
        return "As probabilidades médias das faixas devem ser crescentes, entre 0 e 100%."
    return None


# ── 08 Governança ────────────────────────────────────────────────────────


def change_manager_authority_error(values: Mapping[str, Any]) -> str | None:
    """Alçada do gerente do projeto fica entre 0 e 10% do orçamento."""
    authority = values.get("alcadaGerentePctOrcamento")
    if authority is not None and not 0 < _number(authority) <= 10:
        return "A alçada do gerente do projeto deve ficar entre 0 e 10% do orçamento."
    return None


def change_committee_quorum_error(values: Mapping[str, Any]) -> str | None:
    """Quórum do Comitê de Controle de Mudanças é de 2 ou mais participantes."""
    quorum = values.get("quorumComite")
    if quorum is not None and not _number(quorum) >= 2:
        return "O quórum do Comitê de Controle de Mudanças deve ser de 2 ou mais participantes."
    return None


def change_deadlines_error(values: Mapping[str, Any]) -> str | None:
    """Prazos de análise, ações e ratificação ficam entre 1 e 90 dias."""
    for key in ("prazoAnaliseDias", "prazoAcoesDias", "ratificacaoDias"):
        deadline = values.get(key)
        if deadline is not None and not 1 <= _number(deadline) <= 90:
            return "Os prazos de mudanças (análise, ações e ratificação) devem ficar entre 1 e 90 dias."
    return None


def lessons_alert_error(values: Mapping[str, Any]) -> str | None:
    """Alerta de projeto sem lição registrada fica entre 30 e 365 dias."""
    alert = values.get("alertaSemRegistroDias")
    if alert is not None and not 30 <= _number(alert) <= 365:
        return "O alerta de projeto sem lição registrada deve ficar entre 30 e 365 dias."
    return None


# ── 02 Produtividade ─────────────────────────────────────────────────────


def productivity_workday_error(values: Mapping[str, Any]) -> str | None:
    """Jornada diária de referência fica entre 4 e 12 horas."""
    workday = values.get("jornadaDiariaHoras")
    if workday is not None and not 4 <= _number(workday) <= 12:
        return "A jornada diária de referência deve ficar entre 4 e 12 horas."
    return None


def productivity_targets_error(values: Mapping[str, Any]) -> str | None:
    """Metas de pessoas trabalhando e de utilização da jornada ficam entre 0 e 100%."""
    for key in ("metaTrabalhandoPct", "metaUtilizacaoPct"):
        target = values.get(key)
        if target is not None and not 0 < _number(target) <= 100:
            return "As metas de produtividade (trabalhando e utilização da jornada) devem ficar entre 0 e 100%."
    return None


def productivity_adherence_bands_error(values: Mapping[str, Any]) -> str | None:
    """Faixas da aderência semanal são crescentes, entre 0 e 100%."""
    bands = _bands(values, "aderenciaFaixas")
    if bands is not None:
        first, second = bands
        if not (first > 0 and second > first and second <= 100):
            return "As faixas de aderência semanal devem ser crescentes, entre 0 e 100%."
    return None


def productivity_factor_bands_error(values: Mapping[str, Any]) -> str | None:
    """Faixas do fator de produtividade são crescentes e maiores que zero."""
    bands = _bands(values, "pfFaixas")
    if bands is not None:
        first, second = bands
        if not (first > 0 and second > first):
            return "As faixas do fator de produtividade devem ser crescentes e maiores que zero."
    return None


def productivity_spi_bands_error(values: Mapping[str, Any]) -> str | None:
    """Faixas do SPI de quantidades são crescentes, entre 0 e 1,5."""
    bands = _bands(values, "spiFaixas")
    if bands is not None:
        first, second = bands
        if not (first > 0 and second > first and second <= 1.5):
            return "As faixas do SPI de quantidades devem ser crescentes, entre 0 e 1,5."
    return None


def productivity_start_delay_bands_error(values: Mapping[str, Any]) -> str | None:
    """Faixas do atraso de início são crescentes, entre 0 e 240 minutos."""
    bands = _bands(values, "atrasoInicioFaixasMin")
    if bands is not None:
        first, second = bands
        if not (first >= 0 and second > first and second <= 240):
            return "As faixas do atraso de início devem ser crescentes, entre 0 e 240 minutos."
    return None


def productivity_average_window_error(values: Mapping[str, Any]) -> str | None:
    """Janela da média móvel fica entre 1 e 12 semanas."""
    window = values.get("semanasMedia")
    if window is not None and not 1 <= _number(window) <= 12:
        return "A janela da média móvel de produtividade deve ficar entre 1 e 12 semanas."
    return None


# ── 03 Financeiro ────────────────────────────────────────────────────────


def contingency_consumption_tolerance_error(values: Mapping[str, Any]) -> str | None:
    """Tolerância do consumo da contingência acima do avanço fica entre 0 e 50 p.p."""
    contingency = values.get("contingencia")
    if not isinstance(contingency, Mapping):
        return None
    tolerance = _number(contingency.get("toleranciaConsumoPP"))
    if not 0 <= tolerance <= 50:
        return (
            "A tolerância do consumo da contingência acima do avanço deve ficar entre 0 e 50 p.p."
        )
    return None


def contingency_coverage_error(values: Mapping[str, Any]) -> str | None:
    """Cobertura mínima da exposição a riscos fica entre 0 e 300%."""
    contingency = values.get("contingencia")
    if not isinstance(contingency, Mapping):
        return None
    coverage = _number(contingency.get("coberturaMinimaPct"))
    if not 0 <= coverage <= 300:
        return "A cobertura mínima da exposição a riscos deve ficar entre 0 e 300%."
    return None


# ── 02 EAP ───────────────────────────────────────────────────────────────


def eap_deviation_bands_error(values: Mapping[str, Any]) -> str | None:
    """Faixas do desvio físico são crescentes e maiores que zero."""
    bands = _bands(values, "faixasDesvioPP")
    if bands is not None:
        first, second = bands
        if not (first > 0 and second > first):
            return "As faixas de desvio físico da EAP devem ser crescentes e maiores que zero."
    return None


def eap_package_weight_error(values: Mapping[str, Any]) -> str | None:
    """Peso máximo de um pacote fica entre 0 e 100%."""
    weight = values.get("pesoMaximoPacotePct")
    if weight is not None and not 0 < _number(weight) <= 100:
        return "O peso máximo de um pacote da EAP deve ficar entre 0 e 100%."
    return None


def eap_estimated_weight_error(values: Mapping[str, Any]) -> str | None:
    """Peso máximo com percentual estimado é positivo e até o peso máximo do pacote."""
    estimated = values.get("estimadoMaximoPct")
    if estimated is None:
        return None
    ceiling = _number(values.get("pesoMaximoPacotePct") or 100)
    if not 0 < _number(estimated) <= ceiling:
        return "O peso máximo de pacote medido por percentual estimado deve ser maior que zero e até o peso máximo do pacote."
    return None


def eap_stage_models_error(values: Mapping[str, Any]) -> str | None:
    """As etapas de cada modelo de medição somam 100."""
    for model in _items(values, "modelosEtapas"):
        total = sum(_number(stage.get("peso")) for stage in _items(model, "etapas"))
        if abs(total - 100) > 0.001:
            name = model.get("nome")
            return f"As etapas do modelo {name} precisam somar 100 (hoje somam {_text(total)})."
    return None


# ── 06 Qualidade ─────────────────────────────────────────────────────────


def quality_treatment_deadlines_error(values: Mapping[str, Any]) -> str | None:
    """Prazos de tratamento da RNC crescem de Crítica para Menor, entre 1 e 180 dias."""
    deadlines = values.get("prazoTratamentoDias")
    if not isinstance(deadlines, Mapping):
        return None
    critical = _number(deadlines.get("critica"))
    major = _number(deadlines.get("maior"))
    minor = _number(deadlines.get("menor"))
    valid = critical >= 1 and major >= critical and minor >= major and minor <= 180
    if not valid:
        return "Os prazos de tratamento da RNC devem crescer da severidade Crítica para a Menor, entre 1 e 180 dias."
    return None


def quality_effectiveness_wait_error(values: Mapping[str, Any]) -> str | None:
    """Espera até a verificação de eficácia fica entre 0 e 180 dias."""
    wait = values.get("verificacaoEficaciaDias")
    if wait is not None and not 0 <= _number(wait) <= 180:
        return "A espera da verificação de eficácia deve ficar entre 0 e 180 dias."
    return None


def quality_targets_error(values: Mapping[str, Any]) -> str | None:
    """Metas de aprovação em inspeções e de conformidade em auditorias ficam entre 0 e 100%."""
    for key in ("metaAprovacaoInspecaoPct", "metaConformidadeAuditoriaPct"):
        target = values.get(key)
        if target is not None and not 0 < _number(target) <= 100:
            return "As metas da qualidade (aprovação em inspeções e conformidade em auditorias) devem ficar entre 0 e 100%."
    return None


def quality_client_notice_error(values: Mapping[str, Any]) -> str | None:
    """Antecedência da notificação ao cliente fica entre 0 e 240 horas."""
    notice = values.get("notificacaoClienteHoras")
    if notice is not None and not 0 <= _number(notice) <= 240:
        return "A antecedência da notificação ao cliente deve ficar entre 0 e 240 horas."
    return None


# ── Portfólio ────────────────────────────────────────────────────────────


def portfolio_weights_error(values: Mapping[str, Any]) -> str | None:
    """Pesos dos critérios da carteira somam 100% e não são negativos."""
    if not values.get("criterios"):
        return None
    weights = [_number(item.get("peso")) for item in _items(values, "criterios")]
    total = sum(weights)
    if abs(total - 100) > 0.001:
        return f"Os pesos dos critérios de ponderação do portfólio devem somar 100% (atual: {_text(total)}%)."
    if any(weight < 0 for weight in weights):
        return "Os pesos dos critérios de ponderação não podem ser negativos."
    return None


# ── Registro das regras por grupo ────────────────────────────────────────

# Group -> (form field, rule). The field is the path the screen shows the
# message next to; a rule that fails without a more specific field points at
# the block that caused it.
_RULES: dict[str, tuple[tuple[str, Callable[[Mapping[str, Any]], str | None]], ...]] = {
    "avaliacaoContratada": (
        ("avaliacaoContratada.criterios", contractor_weight_total_error),
        ("avaliacaoContratada.classes", contractor_class_minimums_error),
    ),
    "hse": (
        ("hse.prazos", hse_deadlines_error),
        ("hse.baseTaxa", hse_rate_base_error),
        ("hse.metas", hse_proactive_targets_error),
    ),
    "riscos": (
        ("riscos.cadenciaDias", risk_review_cadence_error),
        ("riscos.probabilidades", risk_probabilities_error),
    ),
    "financeiro": (
        ("financeiro.contingencia.toleranciaConsumoPP", contingency_consumption_tolerance_error),
        ("financeiro.contingencia.coberturaMinimaPct", contingency_coverage_error),
    ),
    "suprimentos": (
        ("suprimentos.pesosMarcos", mas_weight_total_error),
        ("suprimentos.alcadas", supply_authority_limits_error),
        ("suprimentos.propostasMinimas", minimum_proposals_error),
    ),
    "mudancas": (
        ("mudancas.alcadaGerentePctOrcamento", change_manager_authority_error),
        ("mudancas.quorumComite", change_committee_quorum_error),
        ("mudancas.prazos", change_deadlines_error),
    ),
    "licoes": (("licoes.alertaSemRegistroDias", lessons_alert_error),),
    "produtividade": (
        ("produtividade.jornadaDiariaHoras", productivity_workday_error),
        ("produtividade.metas", productivity_targets_error),
        ("produtividade.aderenciaFaixas", productivity_adherence_bands_error),
        ("produtividade.pfFaixas", productivity_factor_bands_error),
        ("produtividade.spiFaixas", productivity_spi_bands_error),
        ("produtividade.atrasoInicioFaixasMin", productivity_start_delay_bands_error),
        ("produtividade.semanasMedia", productivity_average_window_error),
    ),
    "eap": (
        ("eap.faixasDesvioPP", eap_deviation_bands_error),
        ("eap.pesoMaximoPacotePct", eap_package_weight_error),
        ("eap.estimadoMaximoPct", eap_estimated_weight_error),
        ("eap.modelosEtapas", eap_stage_models_error),
    ),
    "qualidade": (
        ("qualidade.prazoTratamentoDias", quality_treatment_deadlines_error),
        ("qualidade.verificacaoEficaciaDias", quality_effectiveness_wait_error),
        ("qualidade.metas", quality_targets_error),
        ("qualidade.notificacaoClienteHoras", quality_client_notice_error),
    ),
    "portfolio": (("portfolio.criterios", portfolio_weights_error),),
}
