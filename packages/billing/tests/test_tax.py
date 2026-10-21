"""Steuerfunktion (ADR-0061 §6): eine Zeile je Tabellenfall.

Die Tabelle ist eine Arbeitsannahme, mit dem Steuerberater zu bestaetigen. Die
Tests halten fest, dass der Code genau die Tabelle der ADR umsetzt — aendert
der Steuerberater eine Zeile, aendern sich ADR, Funktion und die passende
Zeile hier gemeinsam.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from who2be_billing.tax import (
    MEMO_TEXTS,
    TaxDecision,
    TaxInput,
    decide_tax,
    invoice_locale,
    memo_text,
)

# Platzhalter-Nummern, keine echten USt-IdNr. (oeffentliches Repo).
_AT_VAT = "ATU00000000"
_FR_VAT = "FR00000000000"


def _decide(**kwargs: object) -> TaxDecision:
    base: dict[str, object] = {"tax_mode": "regular", "price_basis": "net"}
    base.update(kwargs)
    return decide_tax(TaxInput(**base))  # type: ignore[arg-type]


# (Fall, Eingabe, erwarteter Satz, Empfaenger, vatNumber auf der Rechnung, memo)
_REGULAR_ROWS: list[tuple[str, dict[str, object], str, str, bool, str | None]] = [
    ("DE B2B", {"country": "DE", "customer_type": "business"}, "19.00", "business", False, None),
    ("DE B2C", {"country": "DE", "customer_type": "consumer"}, "19.00", "consumer", False, None),
    (
        "EU B2B, USt-IdNr. per VIES gueltig",
        {"country": "AT", "customer_type": "business", "vat_id": _AT_VAT, "vat_status": "valid"},
        "0.00",
        "business",
        True,
        "reverse_charge",
    ),
    (
        "EU B2B, USt-IdNr. ungueltig",
        {"country": "AT", "customer_type": "business", "vat_id": _AT_VAT, "vat_status": "invalid"},
        "19.00",
        "business",
        False,
        None,
    ),
    (
        "EU B2B, USt-IdNr. fehlt",
        {"country": "FR", "customer_type": "business"},
        "19.00",
        "business",
        False,
        None,
    ),
    ("EU B2C", {"country": "FR", "customer_type": "consumer"}, "19.00", "consumer", False, None),
    (
        "Drittland B2B",
        {"country": "CH", "customer_type": "business"},
        "0.00",
        "business",
        False,
        "not_taxable_domestic",
    ),
    (
        "Drittland B2C",
        {"country": "US", "customer_type": "consumer"},
        "0.00",
        "consumer",
        False,
        "not_taxable_domestic",
    ),
]


@pytest.mark.parametrize(
    ("case", "data", "rate", "recipient", "with_vat_number", "memo"),
    _REGULAR_ROWS,
    ids=[row[0] for row in _REGULAR_ROWS],
)
def test_regular_mode_follows_the_adr_table(
    case: str,
    data: dict[str, object],
    rate: str,
    recipient: str,
    with_vat_number: bool,
    memo: str | None,
) -> None:
    decision = _decide(**data)
    assert decision.action == "issue", case
    assert decision.hold_reason is None
    assert decision.vat_rate == Decimal(rate)
    assert decision.recipient_type == recipient
    assert decision.include_vat_number is with_vat_number
    assert decision.memo_key == memo


def test_eu_b2b_with_unchecked_vat_id_holds_the_invoice() -> None:
    """W61-3 Option A: weder Reverse Charge noch 19 %, bis VIES geantwortet hat."""
    decision = _decide(
        country="AT", customer_type="business", vat_id=_AT_VAT, vat_status="unchecked"
    )
    assert decision.action == "hold"
    assert decision.hold_reason == "vat_id_unchecked"
    assert decision.memo_key is None
    assert decision.include_vat_number is False


def test_missing_tax_mode_holds_every_invoice() -> None:
    """Ohne Steuermodus keine Rechnung (ADR-0061 §3, fail closed) — auch fuer DE."""
    decision = _decide(tax_mode=None, country="DE", customer_type="consumer")
    assert decision.action == "hold"
    assert decision.hold_reason == "tax_mode_missing"


def test_unchecked_vat_id_outside_the_eu_does_not_hold() -> None:
    """Die Rueckhaltung gilt nur fuer EU-B2B; ein Drittland ist ohnehin 0 %."""
    decision = _decide(
        country="CH", customer_type="business", vat_id="CHE000000000", vat_status="unchecked"
    )
    assert decision.action == "issue"
    assert decision.memo_key == "not_taxable_domestic"


def test_domestic_business_with_vat_id_still_pays_german_vat() -> None:
    """Eine deutsche USt-IdNr. aendert fuer einen Kunden in DE nichts."""
    decision = _decide(
        country="DE", customer_type="business", vat_id="DE000000000", vat_status="valid"
    )
    assert decision.vat_rate == Decimal("19.00")
    assert decision.memo_key is None


@pytest.mark.parametrize(
    ("data", "with_vat_number"),
    [
        ({"country": "DE", "customer_type": "consumer"}, False),
        ({"country": "AT", "customer_type": "business", "vat_id": _AT_VAT,
          "vat_status": "unchecked"}, True),
        ({"country": "US", "customer_type": "business"}, False),
    ],
)  # fmt: skip
def test_small_business_mode_is_always_zero_with_its_memo(
    data: dict[str, object], with_vat_number: bool
) -> None:
    """§19 UStG: 0 %, Vermerk Kleinunternehmer, kein Reverse Charge, keine Rueckhaltung."""
    decision = _decide(tax_mode="small_business", **data)
    assert decision.action == "issue"
    assert decision.vat_rate == Decimal("0.00")
    assert decision.memo_key == "small_business"
    assert decision.include_vat_number is with_vat_number


@pytest.mark.parametrize(("basis", "mode"), [("net", "exclusive"), ("gross", "inclusive")])
def test_price_basis_maps_to_mollie_vat_mode(basis: str, mode: str) -> None:
    assert _decide(price_basis=basis, country="DE", customer_type="consumer").vat_mode == mode


def test_unknown_fr_vat_id_is_treated_like_a_missing_one() -> None:
    decision = _decide(country="FR", customer_type="business", vat_id=_FR_VAT, vat_status="invalid")
    assert decision.vat_rate == Decimal("19.00")
    assert decision.include_vat_number is False


@pytest.mark.parametrize(
    ("country", "locale"),
    [("DE", "de_DE"), ("AT", "de_DE"), ("CH", "de_DE"), ("LI", "de_DE"), ("FR", "en_GB"),
     ("US", "en_GB")],
)  # fmt: skip
def test_invoice_locale(country: str, locale: str) -> None:
    assert invoice_locale(country) == locale


def test_every_memo_has_both_languages() -> None:
    for key, texts in MEMO_TEXTS.items():
        assert set(texts) == {"de_DE", "en_GB"}, key
        assert all(text.strip() for text in texts.values()), key
    assert memo_text("reverse_charge", "de_DE").startswith("Steuerschuldnerschaft")
