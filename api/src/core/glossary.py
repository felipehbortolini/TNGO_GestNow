"""The glossary of siglas, extracted from CONTEXT.md and served to the shell (HU-018).

CONTEXT.md is the single source of the product vocabulary: every entry is a
paragraph that opens with ``**TERM** — definition``. The terms that are siglas
(SPI, CPI, VME, RNC, TF...) feed the hint the shell shows on hover; the
definition is the meaning, word for word.

Only ``api/`` is deployed to Azure, where the file at the repository root does
not exist. ``scripts/generate_glossary.py`` therefore writes the extraction to
``glossario.json`` beside this module, and a test fails when that file stops
matching CONTEXT.md: the source stays one, and the copy that travels with the
API cannot go stale unnoticed. To add a sigla, add the entry to CONTEXT.md and
run the script.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

GLOSSARY_FILE = Path(__file__).with_name("glossario.json")

# Entries open a paragraph: ``**TERM** — definition``. Several entries may share
# one paragraph (``**EV** — Valor Agregado; **PV** — Valor Planejado``), and an
# optional ``(SIGLA)`` between the term and the dash is tolerated.
_ENTRY_START = re.compile(r"\*\*([^*\n]+?)\*\*(?:\s+\([^)\n]*\))?\s+—\s+")

# The first token of a sigla: a capital followed by up to seven letters, at
# least two of them capitals (EAP, SPI, HiPo; never "Semana" or "Blueprint").
_SIGLA_TOKEN = re.compile(r"[A-Z][A-Za-z]{1,7}")
_MIN_CAPITALS = 2

# Terms that are not siglas but explain a notation: the week written ``S39``.
PATTERN_TERMS: Mapping[str, str] = {"Semana ISO": "semana"}


@dataclass(frozen=True)
class Abbreviation:
    """A sigla and the glossary entry it comes from (``SPI`` → ``SPI de custo``)."""

    abbreviation: str
    term: str
    meaning: str


@dataclass(frozen=True)
class PatternTerm:
    """A notation (``S39``) explained by a glossary term (``Semana ISO``)."""

    kind: str
    term: str
    meaning: str


@dataclass(frozen=True)
class Glossary:
    """What the shell needs to explain a sigla."""

    abbreviations: tuple[Abbreviation, ...]
    patterns: tuple[PatternTerm, ...]

    def meanings_of(self, abbreviation: str) -> tuple[Abbreviation, ...]:
        """Every entry of a sigla: ``SPI`` has two (de custo and físico), and both are shown."""
        return tuple(item for item in self.abbreviations if item.abbreviation == abbreviation)


# ── Extraction ───────────────────────────────────────────────────────────


def parse_context(markdown: str) -> Glossary:
    """Extract the siglas, and the terms behind the notations, from the text of CONTEXT.md."""
    abbreviations: list[Abbreviation] = []
    patterns: list[PatternTerm] = []
    for paragraph in _paragraphs(markdown):
        for term, meaning in _entries(paragraph):
            abbreviation = _abbreviation_of(term)
            if abbreviation is not None:
                abbreviations.append(Abbreviation(abbreviation, term, meaning))
            elif term in PATTERN_TERMS:
                patterns.append(PatternTerm(PATTERN_TERMS[term], term, meaning))
    return Glossary(abbreviations=tuple(abbreviations), patterns=tuple(patterns))


def _paragraphs(markdown: str) -> Iterator[str]:
    """Paragraphs that open an entry, each on one line."""
    for block in re.split(r"\n\s*\n", markdown):
        text = " ".join(line.strip() for line in block.strip().splitlines())
        if text.startswith("**"):
            yield text


def _entries(paragraph: str) -> Iterator[tuple[str, str]]:
    """The ``(term, meaning)`` pairs of a paragraph; each meaning runs to the next entry."""
    starts = list(_ENTRY_START.finditer(paragraph))
    if not starts or starts[0].start() != 0:
        return
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(paragraph)
        yield start.group(1).strip(), _clean(paragraph[start.end() : end])


def _clean(meaning: str) -> str:
    """Plain text: no markdown emphasis or code, no trailing ``;``, first letter capital."""
    plain = re.sub(r"[*`]", "", meaning)
    plain = re.sub(r"\s+", " ", plain).strip().rstrip(";").strip()
    return plain[:1].upper() + plain[1:]


def _abbreviation_of(term: str) -> str | None:
    """The sigla a term is spelled by, or ``None`` when the term is not one.

    ``EAP`` and ``HiPo`` are siglas; ``SPI de custo`` and ``SPI físico`` belong
    to the sigla ``SPI``; ``Semana ISO`` and ``Programação Semanal`` are not.
    """
    first, *rest = term.split()
    capitals = sum(1 for letter in first if letter.isupper())
    if not _SIGLA_TOKEN.fullmatch(first) or capitals < _MIN_CAPITALS:
        return None
    return first if all(word[:1].islower() for word in rest) else None


# ── The file that travels with the API ───────────────────────────────────


def to_data(glossary: Glossary) -> dict[str, Any]:
    """The glossary as the JSON file keeps it (Portuguese keys, like every data file)."""
    return {
        "siglas": [
            {"sigla": item.abbreviation, "termo": item.term, "significado": item.meaning}
            for item in glossary.abbreviations
        ],
        "padroes": [
            {"padrao": item.kind, "termo": item.term, "significado": item.meaning}
            for item in glossary.patterns
        ],
    }


def from_data(data: Mapping[str, Any]) -> Glossary:
    """Read the glossary back from the shape ``to_data`` writes."""
    return Glossary(
        abbreviations=tuple(
            Abbreviation(item["sigla"], item["termo"], item["significado"])
            for item in data["siglas"]
        ),
        patterns=tuple(
            PatternTerm(item["padrao"], item["termo"], item["significado"])
            for item in data["padroes"]
        ),
    )


@cache
def load_glossary() -> Glossary:
    """The glossary the API serves, read once from ``glossario.json``."""
    return from_data(json.loads(GLOSSARY_FILE.read_text(encoding="utf-8")))


def write_glossary(glossary: Glossary, path: Path = GLOSSARY_FILE) -> None:
    """Write the glossary file; ``scripts/generate_glossary.py`` is the only caller."""
    text = json.dumps(to_data(glossary), ensure_ascii=False, indent=2)
    path.write_text(f"{text}\n", encoding="utf-8")
