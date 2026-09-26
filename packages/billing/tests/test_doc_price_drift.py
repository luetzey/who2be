"""Drift-Guard: Preisangaben in Doku und Frontend gegen `plans.py`.

Dasselbe Muster wie `packages/models/tests/test_doc_tool_count.py`: eine
durchgesetzte Quelle, mehrere nach aussen sichtbare Wiederholungen, die an
keiner Pruefung hingen.

`PRO_PLAN.price_eur` ist die fuehrende Quelle des Pro-Preises (der Checkout
schreibt genau diesen String an Mollie, `mollie.py:451`). Wiederholt wird er
in der Tarif-Tabelle von `docs/licensing/plans.md`, im Analysepapier
`docs/cloud-hosting-owner-guide.md` und — als JS-Zahl — in der `TIERS`-Liste
des Billing-Panels, weil das Backend den Preis nicht mitliefert
(`BillingPanel.tsx`, Kommentar ueber `TIERS`). Befund 2026-09-25: alle vier
Stellen trugen 29 €, obwohl der Owner 9,99 € entschieden hatte — genau der
Drift, den dieser Guard ab jetzt rot macht.

Zwei Arten von Pruefung, absichtlich getrennt:

* **Anker** (`test_price_anchor_*`) — eine bekannte Stelle nennt exakt den
  Preis aus `plans.py`. Jeder Anker prueft zuerst, dass sein Muster ueberhaupt
  noch trifft: ein stumm durchlaufender Guard ist schlimmer als keiner.
* **Scan** (`test_no_unknown_euro_amount`) — *jeder* Euro-Betrag in den
  Preis-tragenden Dateien muss ein bekannter Betrag sein. Das fangt die neue
  Fundstelle, die noch niemand als Anker kennt.

Der Scan sucht bewusst nach dem Betrag, nicht nach der Formulierung. Die erste
Fassung traf nur die Kurzform „<Betrag> €/Mon…" und liess damit jede Prosaform
durch („49 € im Monat", „49 EUR pro Monat", „49 € monatlich", „zahlt heute
49 €"). Zwei solcher Saetze stehen real im Analysepapier und hingen an keiner
Pruefung. Eine Formulierungs-Liste waere immer unvollstaendig gewesen; die
Menge der erlaubten Betraege dagegen ist klein, vollstaendig aufzaehlbar und
haengt an `plans.py`.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from who2be_billing.plans import FREE_PLAN, PRO_PLAN

_REPO_ROOT = Path(__file__).resolve().parents[3]

_PLANS_DOC = "docs/licensing/plans.md"
_OWNER_GUIDE = "docs/cloud-hosting-owner-guide.md"
_BILLING_PANEL = "apps/web/src/features/billing/components/BillingPanel.tsx"

# Der Team-Tarif ist ein VORSCHLAG des Analysepapiers, kein gebuchter Plan --
# er steht deshalb nicht in `plans.py` und braucht hier einen Freibrief.
# Verschwindet das Papier (Karte t_2ef0060d), fliegt der Eintrag mit raus.
_PROPOSED_TEAM_PRICE_EUR = Decimal("99")

# Das Analysepapier rechnet den Gebuehrenunterschied Merchant-of-Record vs.
# Mollie als Monatsbetrag aus (§Finanzen): 50 Kunden x Pro-Preis x (5 % - 1,8 %),
# auf ganze Euro gerundet. Bewusst GERECHNET statt als Zahl erlaubt: aendert der
# Pro-Preis, muss diese abgeleitete Zahl im Papier mitwandern, sonst bricht der
# Test genau dort. Verschwindet die Passage, fliegt die Konstante mit raus.
_MOR_CUSTOMERS = Decimal("50")
_MOR_FEE_SPREAD = Decimal("0.05") - Decimal("0.018")


# Punkt ohne Komma ist zweideutig: deutsche Tausendertrennung („9.990 €") oder
# englischer Dezimalpunkt („9.99 EUR"). Entschieden wird an der Stelligkeit der
# Gruppen: genau drei Ziffern hinter jedem Punkt und hoechstens drei davor ist
# Tausendertrennung, alles andere ein Dezimalpunkt. Damit wird „9.990" zu 9990
# statt zu 9,99 — vorher kollabierten genau die Tausenderbetraege, deren
# Punktform auf einen erlaubten Preis faellt (9.990 -> Pro, 99.000 -> Team),
# still auf gruen.
_THOUSANDS_GROUPED = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


def _eur(value: str) -> Decimal:
    """„9,99" / „9.99" / „9.990" / „1.234,56" / „0" -> Decimal.

    Deutsche Doku, englischer Code — beide Notationen laufen durch dieselbe
    Funktion: die Doku schreibt „9,99 €", `plans.py` den Mollie-String „9.99".

    Ein Komma ist eindeutig: es ist der Dezimaltrenner, Punkte davor sind
    Tausender. Ohne Komma entscheidet `_THOUSANDS_GROUPED`.

    Die Zweideutigkeit, die bleibt: ein dreistelliger Nachkommateil ohne Komma
    („1.234") wird als Tausender gelesen, nicht als Betrag mit drei
    Nachkommastellen. Das ist fuer Euro-Betraege die richtige Seite des Irrtums
    — Cent-Betraege haben zwei Nachkommastellen, nicht drei — und im Zweifel die
    sichere: die Tausender-Lesart ergibt die groessere Zahl und faellt damit
    eher aus der Liste der erlaubten Preise, macht den Guard also rot statt
    stumm.
    """
    if "," in value:
        return Decimal(value.replace(".", "").replace(",", "."))
    if _THOUSANDS_GROUPED.match(value):
        return Decimal(value.replace(".", ""))
    return Decimal(value)


def _read(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


# `_eur()` traegt die gesamte Betragslogik dieses Guards — beide Pruefarten
# vergleichen ihre Funde ueber sie. Bis 2026-09-26 wurde sie nur indirekt ueber
# die Doku-Dateien geprueft; eine Fehl-Lesart blieb damit still, solange keine
# Doku-Zeile sie ausloeste. Der Tabellentest ist die guenstigere Absicherung.
_EUR_PARSING = (
    # Deutsche Doku-Notation.
    ("0", "0"),
    ("99", "99"),
    ("9,99", "9.99"),
    ("1.234,56", "1234.56"),
    ("1.234.567,89", "1234567.89"),
    # Mollie-/JS-Notation aus `plans.py` bzw. `BillingPanel.tsx` — Punkt als
    # Dezimaltrenner, zwei Nachkommastellen.
    ("9.99", "9.99"),
    ("12.50", "12.50"),
    # Deutsche Tausendertrennung ohne Komma: der Fall, der vorher auf einen
    # erlaubten Preis kollabierte.
    ("9.990", "9990"),
    ("99.000", "99000"),
    ("1.000", "1000"),
    ("100.000", "100000"),
    ("1.234", "1234"),
)


@pytest.mark.parametrize(("raw", "expected"), _EUR_PARSING, ids=[raw for raw, _ in _EUR_PARSING])
def test_eur_reads_german_and_mollie_notation(raw: str, expected: str) -> None:
    assert _eur(raw) == Decimal(expected)


def test_eur_does_not_collapse_thousands_onto_allowed_prices() -> None:
    """Die Rot-Probe als Behauptung: Tausenderform != Tarifpreis.

    Beide Betraege liefen gruen durch, solange der Punkt ohne Komma als
    Dezimaltrenner gelesen wurde: „9.990 €" wurde zum Pro-Preis, „99.000 €" zum
    Team-Vorschlag. Ein `assert _eur(...) == Decimal(...)` allein wuerde das
    nicht sichern — `Decimal("99.000") == Decimal("99")` ist wahr, die falsche
    Lesart haette also eine naive Gleichheitspruefung passiert.

    Nicht dabei: „0.000 €". Das ist in beiden Lesarten null und bleibt damit
    zu Recht erlaubt — kein Fall fuer diese Unterscheidung.
    """
    assert _eur("9.990") != _eur(PRO_PLAN.price_eur)
    assert _eur("99.000") != _PROPOSED_TEAM_PRICE_EUR


# Je Eintrag: Datei + Muster mit EINER Gruppe, die den Betrag traegt.
_PRICE_ANCHORS = (
    # Tarif-Tabelle: "| Pro  | 9,99 €/Monat   | 100.000 ..."
    (_PLANS_DOC, re.compile(r"^\|\s*Pro\s*\|\s*([\d.,]+)\s*€/Monat", re.MULTILINE)),
    # Panel-Stammdaten: "{ code: 'pro', name: 'Pro', priceEur: 9.99, ..."
    (_BILLING_PANEL, re.compile(r"code:\s*'pro'.*?priceEur:\s*([\d.]+)")),
)


@pytest.mark.parametrize(
    ("relative_path", "pattern"),
    _PRICE_ANCHORS,
    ids=[relative_path for relative_path, _ in _PRICE_ANCHORS],
)
def test_price_anchor_matches_plans_py(relative_path: str, pattern: re.Pattern[str]) -> None:
    matches = pattern.findall(_read(relative_path))
    assert matches, (
        f"{relative_path}: Muster {pattern.pattern!r} trifft nicht mehr. Entweder "
        "wurde die Preisangabe umformuliert (dann das Muster hier nachziehen) oder "
        "sie ist entfallen (dann den Eintrag aus `_PRICE_ANCHORS` entfernen) — ein "
        "stumm durchlaufender Guard ist schlimmer als keiner."
    )

    expected = _eur(PRO_PLAN.price_eur)
    documented = {_eur(value) for value in matches}
    assert documented == {expected}, (
        f"{relative_path} nennt {sorted(str(v) for v in documented)} € als "
        f"Pro-Preis, `PRO_PLAN.price_eur` ist {PRO_PLAN.price_eur} €. `plans.py` "
        "gilt: die Zahl in der Datei nachziehen, nicht den Test."
    )


# Jeder Euro-Betrag, egal wie er formuliert ist: "9,99 €/Monat", "99 €/Mon",
# "49 € im Monat", "49 € monatlich", "zahlt heute 9,99 €", "49 EUR pro Monat",
# "| Free | 0 € |". Absichtlich KEINE Liste von Zeitraum-Formulierungen: die
# waere immer unvollstaendig (genau daran ist die erste Fassung gescheitert),
# waehrend die Menge der erlaubten Betraege endlich und an `plans.py` gehaengt
# ist. Der Betrag endet auf einer Ziffer, damit Satzzeichen ("9,99 €.") nicht
# in die Gruppe rutschen.
_EURO_AMOUNT = re.compile(r"(\d(?:[\d.,]*\d)?)\s*(?:€|EUR\b)")


@pytest.mark.parametrize("relative_path", (_PLANS_DOC, _OWNER_GUIDE))
def test_no_unknown_euro_amount(relative_path: str) -> None:
    allowed = {
        _eur(FREE_PLAN.price_eur),
        _eur(PRO_PLAN.price_eur),
        _PROPOSED_TEAM_PRICE_EUR,
        # Abgeleiteter Differenzbetrag, kein Tarifpreis — aber ebenfalls
        # preisabhaengig, deshalb gerechnet statt festgeschrieben.
        (_MOR_CUSTOMERS * _eur(PRO_PLAN.price_eur) * _MOR_FEE_SPREAD).quantize(Decimal("1")),
    }

    found = {_eur(value) for value in _EURO_AMOUNT.findall(_read(relative_path))}
    assert found, (
        f"{relative_path}: kein einziger Euro-Betrag gefunden. Entweder ist "
        "die Datei umformuliert (Muster `_EURO_AMOUNT` nachziehen) oder sie traegt "
        "keine Preise mehr (dann aus der Parametrisierung entfernen)."
    )

    unknown = found - allowed
    assert not unknown, (
        f"{relative_path} nennt {sorted(str(v) for v in unknown)} € — "
        f"bekannt sind nur {sorted(str(v) for v in allowed)} € (Free/Pro aus "
        "`plans.py`, Team als Vorschlag des Analysepapiers, dazu der gerechnete "
        "MoR-Differenzbetrag). Entweder ist der Preis gedriftet (Datei "
        "nachziehen) oder es gibt einen neuen Tarif (dann zuerst `plans.py`, "
        "dann diesen Test)."
    )


def test_pro_tariff_row_promises_only_enforced_features() -> None:
    """Die Tarifzeile darf nur Feature-Codes nennen, die auch gegatet sind.

    `composite_playbooks`, `agents` und `audit_export` werden nirgends im Repo
    per `has_feature()` geprueft; die eigene Doku nennt sie deshalb „kein
    Leistungsversprechen" (`docs/licensing/plans.md`, §Zur Features-Spalte).
    Sie bleiben im Datenmodell und in der Mollie-Metadata — aber nicht in
    einer Tarifdarstellung. Nur `core` ist wirksam.
    """
    row = re.search(r"^\|\s*Pro\s*\|.*$", _read(_PLANS_DOC), re.MULTILINE)
    assert row, (
        f"{_PLANS_DOC}: die Pro-Tarifzeile ist nicht mehr auffindbar. Tabelle "
        "umgebaut? Dann dieses Muster nachziehen."
    )

    ungated = ("composite_playbooks", "agents", "audit_export")
    named = [code for code in ungated if code in row.group(0)]
    assert not named, (
        f"{_PLANS_DOC}: die Pro-Tarifzeile nennt {named} als Feature. Diese Codes "
        "sind nirgends gegatet und damit kein Leistungsversprechen — sie gehoeren "
        "in die Metadata-Beispiele, nicht in die Tarif-Tabelle."
    )
    assert "`core`" in row.group(0), (
        f"{_PLANS_DOC}: die Pro-Tarifzeile nennt `core` nicht mehr. `core` ist der "
        "einzige wirksame Code und muss stehen bleiben."
    )
