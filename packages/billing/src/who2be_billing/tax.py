"""Steuerfall einer Rechnung als reine Funktion (ADR-0061 §5, §6).

Keine I/O, keine Umgebung, keine Uhr: die beiden Schalter
(`WHO2BE_INVOICE_TAX_MODE`, `WHO2BE_INVOICE_PRICE_BASIS`) kommen als Argumente
herein. Wer sie liest und wann, entscheidet der Aufrufer (R2). So bleibt jede
Zeile der Tabelle in `tests/test_tax.py` ohne Setup pruefbar.

> **Keine Steuer- oder Rechtsberatung.** Die Tabelle ist die Arbeitsannahme aus
> ADR-0061 §6 und **mit dem Steuerberater zu bestaetigen**. Deshalb steht sie
> hier an einer Stelle und nicht verstreut im Webhook-Pfad.

Zwei Faelle stellen keine Rechnung aus, sondern halten sie zurueck (`hold`):

- **Ohne Steuermodus** (ADR-0061 §3, „fail closed“): eine Rechnung mit
  geratener Steuer liesse sich ueber die Mollie-API nicht stornieren.
- **EU-B2B mit ungepruefter USt-IdNr.** (Weiche W61-3, Option A, vom PM als
  Annahme bestaetigt): Reverse Charge oder 19 % haengt am Pruefergebnis. Die
  Nachpruefung und die Obergrenze von 72 Stunden baut R2.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

TaxMode = Literal["regular", "small_business"]
PriceBasis = Literal["net", "gross"]
CustomerType = Literal["business", "consumer"]
VatStatus = Literal["valid", "invalid", "unchecked"]
VatMode = Literal["exclusive", "inclusive"]
InvoiceLocale = Literal["de_DE", "en_GB"]
MemoKey = Literal["reverse_charge", "not_taxable_domestic", "small_business"]
HoldReason = Literal["tax_mode_missing", "vat_id_unchecked"]

#: Sitzland des Betreibers. Steuerlich der Ankerpunkt aller Zeilen in §6.
HOME_COUNTRY = "DE"

#: Regelsteuersatz in DE (§12 Abs. 1 UStG). Als String-Decimal, weil Mollie
#: `vatRate` als String mit zwei Nachkommastellen erwartet.
STANDARD_RATE = Decimal("19.00")
ZERO_RATE = Decimal("0.00")

#: EU-Mitgliedstaaten nach ISO 3166-1 alpha-2 (Land der Rechnungsadresse).
EU_COUNTRIES: frozenset[str] = frozenset(
    {
        "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
        "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
    }
)  # fmt: skip

#: Laender, deren Empfaenger eine deutschsprachige Rechnung bekommen (ADR-0061 §3).
_GERMAN_LOCALE_COUNTRIES: frozenset[str] = frozenset({"DE", "AT", "CH", "LI"})

#: Vermerke auf der Rechnung (Mollie-Feld `memo`). **Mit Steuerberater zu
#: bestaetigen** (ADR-0061 §6, Arbeitsfassungen). Sie stehen bewusst im Code,
#: damit eine Aenderung durch ein Review geht.
MEMO_TEXTS: dict[MemoKey, dict[InvoiceLocale, str]] = {
    "reverse_charge": {
        "de_DE": "Steuerschuldnerschaft des Leistungsempfängers.",
        "en_GB": "Reverse charge: VAT to be accounted for by the recipient.",
    },
    "not_taxable_domestic": {
        "de_DE": "Nicht im Inland steuerbare Leistung.",
        "en_GB": "Service not subject to German VAT.",
    },
    "small_business": {
        "de_DE": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
        "en_GB": "No VAT is charged under section 19 of the German VAT Act (small business).",
    },
}


@dataclass(frozen=True)
class TaxInput:
    """Was die Steuerfunktion braucht: Schalter plus Rechnungsdaten der Org."""

    tax_mode: TaxMode | None
    price_basis: PriceBasis
    country: str
    customer_type: CustomerType
    vat_id: str | None = None
    vat_status: VatStatus | None = None


@dataclass(frozen=True)
class TaxDecision:
    """Steuerfall einer Rechnung (ADR-0061 §6).

    Bei `action == "hold"` sind alle anderen Felder ausser `hold_reason`
    bedeutungslos und stehen auf neutralen Werten; der Aufrufer stellt keine
    Rechnung aus.
    """

    action: Literal["issue", "hold"]
    hold_reason: HoldReason | None
    vat_rate: Decimal
    vat_mode: VatMode
    recipient_type: CustomerType
    include_vat_number: bool
    memo_key: MemoKey | None


def invoice_locale(country: str) -> InvoiceLocale:
    """Sprache der Rechnung: `de_DE` fuer DE, AT, CH, LI, sonst `en_GB`."""
    return "de_DE" if country in _GERMAN_LOCALE_COUNTRIES else "en_GB"


def memo_text(key: MemoKey, locale: InvoiceLocale) -> str:
    """Vermerk fuer `memo` in der Sprache der Rechnung."""
    return MEMO_TEXTS[key][locale]


def _vat_mode(price_basis: PriceBasis) -> VatMode:
    return "exclusive" if price_basis == "net" else "inclusive"


def _issue(
    data: TaxInput,
    rate: Decimal,
    *,
    include_vat_number: bool = False,
    memo_key: MemoKey | None = None,
) -> TaxDecision:
    return TaxDecision(
        action="issue",
        hold_reason=None,
        vat_rate=rate,
        vat_mode=_vat_mode(data.price_basis),
        recipient_type=data.customer_type,
        include_vat_number=include_vat_number,
        memo_key=memo_key,
    )


def _hold(data: TaxInput, reason: HoldReason) -> TaxDecision:
    return TaxDecision(
        action="hold",
        hold_reason=reason,
        vat_rate=ZERO_RATE,
        vat_mode=_vat_mode(data.price_basis),
        recipient_type=data.customer_type,
        include_vat_number=False,
        memo_key=None,
    )


def decide_tax(data: TaxInput) -> TaxDecision:
    """Bildet Schalter und Rechnungsdaten auf den Steuerfall ab (ADR-0061 §6)."""
    if data.tax_mode is None:
        return _hold(data, "tax_mode_missing")

    has_vat_id = data.customer_type == "business" and data.vat_id is not None

    if data.tax_mode == "small_business":
        # Jede Rechnung 0 %, `vatNumber` wie angegeben, kein Reverse Charge.
        return _issue(data, ZERO_RATE, include_vat_number=has_vat_id, memo_key="small_business")

    if data.country == HOME_COUNTRY:
        return _issue(data, STANDARD_RATE)

    if data.country in EU_COUNTRIES:
        if data.customer_type == "consumer":
            # Unter der EU-Schwelle bleibt der Leistungsort in DE; die Schwelle
            # ueberwacht der Betreiber, nicht Who2Be (ADR-0061 §6).
            return _issue(data, STANDARD_RATE)
        if has_vat_id and data.vat_status == "valid":
            return _issue(data, ZERO_RATE, include_vat_number=True, memo_key="reverse_charge")
        if has_vat_id and data.vat_status == "unchecked":
            return _hold(data, "vat_id_unchecked")
        # USt-IdNr. ungueltig oder fehlt: wie B2C, Empfaenger bleibt `business`.
        return _issue(data, STANDARD_RATE)

    # Drittland, B2B und B2C: in DE nicht steuerbar.
    return _issue(data, ZERO_RATE, memo_key="not_taxable_domestic")
