"""Laengen-Richtwerte fuer Agent-Inhalte und die weiche Warnung (ADR-0063).

Einzige Quelle der Zahlen im Code. Die Agent-Bau-Konventionen des Builders
(Abschnitt "Laengen & Wohin", Anker `res-conv-h-laengen`) nennen dieselben
Werte fuer den Builder; `test_content_budgets` haelt beide gleich.

Die Richtwerte sind **keine Grenze**: gespeichert wird immer. Liegt ein
geschriebener Inhalt ueber der Warnschwelle, traegt die Schreibantwort des
Markdown-Wegs einen `LengthHint` mit Messwert, Richtwert und einer kurzen
Zeile fuer den Schreibenden. Missbrauchsschutz ist die bestehende
Feldgrenze des Markdown-Wegs (200 000 Zeichen je Feld, `content_markdown`).

Gezaehlt werden Woerter im Markdown-Text (Normalform nach ADR-0058) ohne
Codebloecke und ohne Ueberschriften-Anker ` [#id]`. Ein Wort ist eine durch
Leerraum getrennte Folge mit mindestens einem Buchstaben oder einer Ziffer;
reine Markdown-Zeichen (`-`, `#`, `|`, `---`) zaehlen nicht.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

LengthElement = Literal[
    "profile", "mode", "mode_count", "playbook_body", "playbook_summary", "resource_section"
]
LengthUnit = Literal["words", "chars", "count"]


@dataclass(frozen=True)
class Budget:
    """Ein Richtwert: `target` ist das Ziel, `warn` die Warnschwelle.

    `strict` heisst: gewarnt wird erst ueber `warn` (Resource-Abschnitt
    "ueber 600 Woerter"), sonst ab `warn` ("Warnung ab 600").
    """

    target: int | None
    warn: int
    unit: LengthUnit
    strict: bool = False

    def exceeded(self, value: int) -> bool:
        return value > self.warn if self.strict else value >= self.warn


#: Owner-Entscheidung 2026-10-22 (W2), ADR-0063 Abschnitt 2.
PERSONA_PROFILE = Budget(target=400, warn=600, unit="words")
PERSONA_MODE = Budget(target=150, warn=250, unit="words")
PERSONA_MODE_COUNT = Budget(target=3, warn=5, unit="count")
PLAYBOOK_BODY = Budget(target=1_000, warn=1_500, unit="words")
PLAYBOOK_SUMMARY = Budget(target=300, warn=500, unit="chars")
RESOURCE_SECTION = Budget(target=None, warn=600, unit="words", strict=True)

#: Inhalts-Startlast (`get_persona` ohne Gedaechtnis), in KB. Nur Richtwert
#: fuer Builder und Messung; die Schreibantwort prueft ihn nicht.
STARTLOAD_AGENT_KB = Budget(target=5, warn=8, unit="count")
STARTLOAD_BUILDER_KB = Budget(target=6, warn=9, unit="count")

BUDGETS: dict[LengthElement, Budget] = {
    "profile": PERSONA_PROFILE,
    "mode": PERSONA_MODE,
    "mode_count": PERSONA_MODE_COUNT,
    "playbook_body": PLAYBOOK_BODY,
    "playbook_summary": PLAYBOOK_SUMMARY,
    "resource_section": RESOURCE_SECTION,
}


class LengthHint(BaseModel):
    """Weicher Laengen-Hinweis in einer Schreibantwort (ADR-0063).

    `target` ist der Richtwert (`null` bei der Resource: nur Warnschwelle),
    `ref` der Modusname bzw. der Anker des Resource-Abschnitts.
    """

    element: LengthElement
    ref: str | None = None
    value: int
    unit: LengthUnit
    target: int | None
    warn: int
    message: str


# --- Zaehlen -----------------------------------------------------------------

_FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
_ANCHOR_ID = r"[A-Za-z0-9_.:-]+"
_ANCHOR_RE = re.compile(r"[ \t]\[#" + _ANCHOR_ID + r"\][ \t]*$")
_HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]+(.*)$")
_WORD_RE = re.compile(r"\S+")
_ALNUM_RE = re.compile(r"[^\W_]")


def _prose_lines(markdown: str) -> Iterable[str]:
    """Zeilen ausserhalb von Codebloecken, Anker entfernt."""
    fence: str | None = None
    for line in markdown.splitlines():
        match = _FENCE_RE.match(line)
        if fence is not None:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            continue
        if match:
            fence = match.group(1)
            continue
        yield _ANCHOR_RE.sub("", line)


def count_words(markdown: str) -> int:
    """Woerter im Markdown-Text ohne Codebloecke und Anker (ADR-0063 Abschnitt 3)."""
    return sum(
        1
        for line in _prose_lines(markdown)
        for token in _WORD_RE.findall(line)
        if _ALNUM_RE.search(token)
    )


@dataclass(frozen=True)
class Section:
    """Ein Resource-Abschnitt: Ueberschrift bis zur naechsten Ueberschrift."""

    anchor: str | None
    title: str
    words: int


def sections(markdown: str) -> list[Section]:
    """Zerlegt Markdown an jeder Ueberschrift (jede Ebene) in Abschnitte.

    Der Text vor der ersten Ueberschrift ist ein eigener Abschnitt ohne Anker.
    Die Ueberschrift selbst zaehlt nicht mit. Unterabschnitte zaehlen getrennt,
    damit ein langer Abschnitt nicht zusaetzlich ueber seine
    Eltern-Ueberschrift gemeldet wird.
    """
    out: list[Section] = []
    anchor: str | None = None
    title = ""
    lines: list[str] = []
    fence: str | None = None

    def flush() -> None:
        words = count_words("\n".join(lines))
        if words or anchor is not None:
            out.append(Section(anchor=anchor, title=title, words=words))

    for line in markdown.splitlines():
        match = _FENCE_RE.match(line)
        if fence is None and not match:
            heading = _HEADING_RE.match(line)
            if heading:
                flush()
                found = re.search(r"\[#(" + _ANCHOR_ID + r")\][ \t]*$", line)
                anchor = found.group(1) if found else ""
                title = _ANCHOR_RE.sub("", heading.group(1)).strip()
                lines = []
                continue
        if fence is not None:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
        elif match:
            fence = match.group(1)
        lines.append(line)
    flush()
    return out


# --- Hinweise ----------------------------------------------------------------


def _num(value: int, locale: str) -> str:
    """Tausender mit Leerzeichen (DE, "1 450") bzw. Komma (EN, "1,450")."""
    text = f"{value:,}"
    return text.replace(",", " ") if locale == "de" else text


_TEXT: dict[str, dict[LengthElement, str]] = {
    "de": {
        "profile": (
            "Profil {v} Wörter, Richtwert {t}. Abläufe und Nachschlagewissen "
            "in Playbook/Resource auslagern?"
        ),
        "mode": "Modus „{r}“ {v} Wörter, Richtwert {t}. Arbeitsschritte in ein Playbook auslagern?",
        "mode_count": "{v} Modi, Richtwert {t}. Modi zusammenlegen oder als Playbook führen?",
        "playbook_body": (
            "Playbook {v} Wörter, Richtwert {t}. Teilen oder Nachschlagewissen "
            "in eine Resource auslagern?"
        ),
        "playbook_summary": (
            "Beschreibung und Trigger {v} Zeichen, Richtwert {t}. "
            "Kürzen, sie stehen in jedem Katalog."
        ),
        "resource_section": (
            "Abschnitt „{r}“ {v} Wörter, Warnschwelle {w}. In Unterabschnitte gliedern?"
        ),
    },
    "en": {
        "profile": (
            "Profile {v} words, guide value {t}. Move procedures and reference "
            "knowledge into a playbook/resource?"
        ),
        "mode": "Mode '{r}' {v} words, guide value {t}. Move the steps into a playbook?",
        "mode_count": "{v} modes, guide value {t}. Merge modes or run them as playbooks?",
        "playbook_body": (
            "Playbook {v} words, guide value {t}. Split it or move reference "
            "knowledge into a resource?"
        ),
        "playbook_summary": (
            "Description and triggers {v} characters, guide value {t}. "
            "Shorten them, every catalogue lists them."
        ),
        "resource_section": (
            "Section '{r}' {v} words, warning threshold {w}. Split it into subsections?"
        ),
    },
}


def _hint(
    element: LengthElement,
    value: int,
    locale: str,
    ref: str | None = None,
    label: str | None = None,
) -> LengthHint:
    budget = BUDGETS[element]
    loc = "de" if locale == "de" else "en"
    message = _TEXT[loc][element].format(
        v=_num(value, loc),
        t=_num(budget.target, loc) if budget.target is not None else "",
        w=_num(budget.warn, loc),
        r=label or ref or "",
    )
    return LengthHint(
        element=element,
        ref=ref,
        value=value,
        unit=budget.unit,
        target=budget.target,
        warn=budget.warn,
        message=message,
    )


def persona_hints(
    profile: str, modes: Iterable[tuple[str, Iterable[str]]], locale: str
) -> list[LengthHint]:
    """Profil, jeder Modus (alle Textfelder zusammen) und die Zahl der Modi."""
    hints: list[LengthHint] = []
    words = count_words(profile)
    if PERSONA_PROFILE.exceeded(words):
        hints.append(_hint("profile", words, locale))
    mode_list = list(modes)
    for name, texts in mode_list:
        mode_words = sum(count_words(text) for text in texts)
        if PERSONA_MODE.exceeded(mode_words):
            hints.append(_hint("mode", mode_words, locale, ref=name))
    if PERSONA_MODE_COUNT.exceeded(len(mode_list)):
        hints.append(_hint("mode_count", len(mode_list), locale))
    return hints


def playbook_hints(
    body: str, description: str, triggers: str | None, locale: str
) -> list[LengthHint]:
    """Playbook-Body in Woertern, Beschreibung und Trigger zusammen in Zeichen."""
    hints: list[LengthHint] = []
    words = count_words(body)
    if PLAYBOOK_BODY.exceeded(words):
        hints.append(_hint("playbook_body", words, locale))
    chars = len(description) + len(triggers or "")
    if PLAYBOOK_SUMMARY.exceeded(chars):
        hints.append(_hint("playbook_summary", chars, locale))
    return hints


def resource_hints(body: str, locale: str) -> list[LengthHint]:
    """Jeder Resource-Abschnitt ueber der Warnschwelle; die Resource selbst hat keine Grenze."""
    return [
        _hint(
            "resource_section",
            section.words,
            locale,
            ref=section.anchor or None,
            label=section.title or None,
        )
        for section in sections(body)
        if RESOURCE_SECTION.exceeded(section.words)
    ]


# --- Web-Konstante (B5) --------------------------------------------------------

#: Ablageort der erzeugten Konstante fuer den Web-Laengenzaehler (ADR-0063 Abschnitt 4).
WEB_CONSTANT_PATH = "apps/web/src/components/editor/contentBudgets.generated.ts"


def typescript_constant() -> str:
    """Die Richtwerte als TypeScript-Modul fuer den Web-Laengenzaehler.

    Das Web fuehrt keine zweite Liste von Hand: die Datei unter
    `WEB_CONSTANT_PATH` ist die Ausgabe dieser Funktion, ein Test haelt beide
    gleich. Neu erzeugen mit `uv run python -m who2be_models.content_budgets`.
    """
    lines = [
        "// ERZEUGT aus packages/models/src/who2be_models/content_budgets.py (ADR-0063).",
        "// Nicht von Hand aendern. Neu erzeugen im Repo-Root mit:",
        "//   uv run python -m who2be_models.content_budgets",
        "// test_content_budgets.py haelt diese Datei gleich mit den Python-Werten.",
        "",
        "export interface ContentBudget {",
        "  /** Richtwert (Ziel); `null`: nur Warnschwelle. */",
        "  target: number | null",
        "  /** Warnschwelle. */",
        "  warn: number",
        "  unit: 'words' | 'chars' | 'count'",
        "  /** `true`: gewarnt wird erst ueber `warn`, sonst ab `warn`. */",
        "  strict: boolean",
        "}",
        "",
        "export const CONTENT_BUDGETS = {",
    ]
    for element, budget in BUDGETS.items():
        target = "null" if budget.target is None else str(budget.target)
        strict = "true" if budget.strict else "false"
        lines.append(
            f"  {element}: {{ target: {target}, warn: {budget.warn}, "
            f"unit: '{budget.unit}', strict: {strict} }},"
        )
    lines += [
        "} as const satisfies Record<string, ContentBudget>",
        "",
        "export type ContentBudgetElement = keyof typeof CONTENT_BUDGETS",
        "",
    ]
    return "\n".join(lines)


def _write_web_constant() -> None:  # pragma: no cover - Entwickler-Kommando
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    (root / WEB_CONSTANT_PATH).write_text(typescript_constant(), encoding="utf-8")
    print(f"geschrieben: {WEB_CONSTANT_PATH}")


__all__ = [
    "BUDGETS",
    "WEB_CONSTANT_PATH",
    "PERSONA_MODE",
    "PERSONA_MODE_COUNT",
    "PERSONA_PROFILE",
    "PLAYBOOK_BODY",
    "PLAYBOOK_SUMMARY",
    "RESOURCE_SECTION",
    "STARTLOAD_AGENT_KB",
    "STARTLOAD_BUILDER_KB",
    "Budget",
    "LengthElement",
    "LengthHint",
    "LengthUnit",
    "Section",
    "count_words",
    "persona_hints",
    "playbook_hints",
    "resource_hints",
    "sections",
    "typescript_constant",
]


if __name__ == "__main__":  # pragma: no cover
    _write_web_constant()
