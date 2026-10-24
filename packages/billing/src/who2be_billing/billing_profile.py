"""Rechnungsdaten je Organisation (ADR-0061 §10, Paket R1; Datenschutz §9).

Drei Teile, alle billing-only (ADR-0029):

- **Validierung** (`BillingProfileInput`): Pflichtfelder je Kundentyp, Land
  nach ISO 3166-1, USt-IdNr. in Normalform und passend zum Land. Der Client
  prueft dieselben Regeln vorab, verbindlich ist dieser Teil.
- **VIES-Pruefung** (`ViesVatChecker`): fragt die REST-Schnittstelle der
  EU-Kommission mit hartem Timeout. Ausfall, Timeout oder eine
  Dienst-Fehlermeldung ergeben **„ungeprueft“** und blockieren das Speichern
  nicht (ADR-0061 §6). Nur eine klare Antwort „gueltig“/„ungueltig“ zaehlt.
- **Repository** (`PgBillingProfileRepository`): eine Zeile je Org in
  `billing_profile` (Migration `billing_0109`). Die Zeile faellt per
  `ON DELETE CASCADE` mit der Organisation.

Beispiele in Tests und Doku verwenden nur Platzhalter, keine echten Adressen
oder USt-IdNr. (oeffentliches Repo, ADR-0061 §9).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Protocol
from uuid import UUID

import asyncpg
import httpx
from pydantic import BaseModel, BeforeValidator, Field, model_validator

from who2be_billing.tax import EU_COUNTRIES, CustomerType, VatStatus

logger = logging.getLogger(__name__)

#: ISO-3166-1-alpha-2-Codes, die als Rechnungsland zulaessig sind. Quelle:
#: `iso3166.tab` der IANA-Zeitzonen-Datenbank (Stand 2026). Der Client bekommt
#: die Liste ueber `GET .../billing/profile` mit — eine Quelle fuer beide Seiten.
COUNTRY_CODES: tuple[str, ...] = tuple(
    """
    AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS
    BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE
    EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM
    HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC
    LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA
    NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW
    SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO
    TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
    """.split()
)
_COUNTRY_SET = frozenset(COUNTRY_CODES)

#: Laenderpraefix der USt-IdNr. je Rechnungsland, wo er vom ISO-Code abweicht.
#: Griechenland fuehrt in VIES `EL`, nicht `GR`.
_VAT_PREFIX_OVERRIDES = {"GR": "EL"}

#: Normalform einer USt-IdNr.: zwei Buchstaben Laenderpraefix plus 2–13 Zeichen.
VAT_ID_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,13}$")

_SEPARATORS = re.compile(r"[\s.\-]")


def vat_prefix(country: str) -> str:
    """Laenderpraefix der USt-IdNr. fuer ein Rechnungsland."""
    return _VAT_PREFIX_OVERRIDES.get(country, country)


def normalize_vat_id(raw: str) -> str:
    """Grossbuchstaben, ohne Leerzeichen, Punkte und Bindestriche."""
    return _SEPARATORS.sub("", raw).upper()


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _upper(value: object) -> object:
    value = _blank_to_none(value)
    return value.upper() if isinstance(value, str) else value


def _vat(value: object) -> object:
    value = _blank_to_none(value)
    return normalize_vat_id(value) if isinstance(value, str) else value


_OptText100 = Annotated[
    Annotated[str, Field(max_length=100)] | None, BeforeValidator(_blank_to_none)
]
_OptText200 = Annotated[
    Annotated[str, Field(max_length=200)] | None, BeforeValidator(_blank_to_none)
]


class BillingProfileInput(BaseModel):
    """Eingabe des Formulars. Leere Strings gelten als nicht angegeben."""

    customer_type: CustomerType
    given_name: _OptText100 = None
    family_name: _OptText100 = None
    company_name: _OptText200 = None
    street: Annotated[str, BeforeValidator(_blank_to_none), Field(min_length=1, max_length=200)]
    postal_code: Annotated[str, BeforeValidator(_blank_to_none), Field(min_length=1, max_length=20)]
    city: Annotated[str, BeforeValidator(_blank_to_none), Field(min_length=1, max_length=100)]
    country: Annotated[str, BeforeValidator(_upper), Field(min_length=2, max_length=2)]
    vat_id: Annotated[Annotated[str, Field(max_length=15)] | None, BeforeValidator(_vat)] = None

    @model_validator(mode="after")
    def _rules_per_customer_type(self) -> BillingProfileInput:
        if self.country not in _COUNTRY_SET:
            raise ValueError("country: unbekannter Laendercode (ISO 3166-1 alpha-2).")
        if self.customer_type == "consumer":
            if self.given_name is None or self.family_name is None:
                raise ValueError("given_name/family_name: fuer Privatkunden Pflicht.")
            if self.vat_id is not None:
                raise ValueError("vat_id: nur fuer Geschaeftskunden.")
        elif self.company_name is None:
            raise ValueError("company_name: fuer Geschaeftskunden Pflicht.")
        if self.vat_id is not None:
            if self.country not in EU_COUNTRIES:
                raise ValueError("vat_id: nur fuer Rechnungsadressen in der EU.")
            if not VAT_ID_PATTERN.fullmatch(self.vat_id):
                raise ValueError("vat_id: ungueltiges Format.")
            if not self.vat_id.startswith(vat_prefix(self.country)):
                raise ValueError("vat_id: Laenderpraefix passt nicht zum Land der Adresse.")
        return self


class BillingProfile(BillingProfileInput):
    """Gespeicherter Stand mit Pruefergebnis der USt-IdNr."""

    vat_status: VatStatus | None = None
    vat_checked_at: datetime | None = None
    updated_at: datetime | None = None


# --- VIES ------------------------------------------------------------------------

#: REST-Schnittstelle von VIES (EU-Kommission), ohne Schluessel.
VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"

#: Harte Obergrenze fuer die Pruefung. VIES antwortet meist in unter einer
#: Sekunde; was laenger dauert, wird „ungeprueft“ statt das Speichern zu bremsen.
VIES_TIMEOUT_SECONDS = 5.0


class VatChecker(Protocol):
    """Port fuer die Pruefung einer USt-IdNr. (Tests setzen einen Fake ein)."""

    async def check(self, vat_id: str) -> VatStatus: ...


@dataclass(frozen=True)
class ViesVatChecker:
    """Prueft eine USt-IdNr. bei VIES. Jeder Fehler ergibt `unchecked`."""

    url: str = VIES_URL
    timeout: float = VIES_TIMEOUT_SECONDS
    transport: httpx.AsyncBaseTransport | None = None

    async def check(self, vat_id: str) -> VatStatus:
        body = {"countryCode": vat_id[:2], "vatNumber": vat_id[2:]}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(self.url, json=body)
            if response.status_code != httpx.codes.OK:
                logger.info("VIES nicht verfuegbar: HTTP %s", response.status_code)
                return "unchecked"
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Timeout, Netzfehler oder kein JSON. Bewusst ohne Nummer im Log.
            logger.info("VIES nicht erreichbar: %s", type(exc).__name__)
            return "unchecked"
        return _vies_status(payload)


def _vies_status(payload: object) -> VatStatus:
    """Liest das Ergebnis aus einer VIES-Antwort.

    Nur `valid` als echter Boolean zaehlt. `userError` traegt bei einer
    gelungenen Pruefung `VALID` bzw. `INVALID`; jeder andere Wert
    (`MS_UNAVAILABLE`, `TIMEOUT`, `SERVICE_UNAVAILABLE` …) heisst, dass gar nicht
    geprueft wurde. „Nicht geprueft“ als „ungueltig“ zu speichern, waere eine
    falsche Aussage in den Rechnungsdaten.
    """
    if not isinstance(payload, dict):
        return "unchecked"
    user_error = payload.get("userError")
    if user_error not in (None, "VALID", "INVALID"):
        return "unchecked"
    valid = payload.get("valid")
    if valid is True:
        return "valid"
    if valid is False:
        return "invalid"
    return "unchecked"


# --- Repository ------------------------------------------------------------------

_COLUMNS = (
    "customer_type, given_name, family_name, company_name, street, postal_code, city, "
    "country, vat_id, vat_status, vat_checked_at, updated_at"
)

_UPSERT_SQL = f"""
INSERT INTO billing_profile (org_id, customer_type, given_name, family_name, company_name,
                             street, postal_code, city, country, vat_id, vat_status,
                             vat_checked_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, now())
ON CONFLICT (org_id) DO UPDATE SET
    customer_type = EXCLUDED.customer_type,
    given_name = EXCLUDED.given_name,
    family_name = EXCLUDED.family_name,
    company_name = EXCLUDED.company_name,
    street = EXCLUDED.street,
    postal_code = EXCLUDED.postal_code,
    city = EXCLUDED.city,
    country = EXCLUDED.country,
    vat_id = EXCLUDED.vat_id,
    vat_status = EXCLUDED.vat_status,
    vat_checked_at = EXCLUDED.vat_checked_at,
    updated_at = now()
RETURNING {_COLUMNS}
"""  # noqa: S608 — _COLUMNS ist eine Konstante, keine Eingabe


class BillingProfileRepository(Protocol):
    async def get(self, org_id: UUID) -> BillingProfile | None: ...

    async def save(
        self,
        org_id: UUID,
        data: BillingProfileInput,
        vat_status: VatStatus | None,
        vat_checked_at: datetime | None,
    ) -> BillingProfile: ...


class PgBillingProfileRepository:
    """asyncpg-Implementierung (RLS ueber `app.current_org`; der Worker liest ohne Scope)."""

    def __init__(self, pool: asyncpg.Pool | asyncpg.Connection) -> None:
        self._pool = pool

    async def update_vat_status(
        self, org_id: UUID, vat_id: str, status: VatStatus, checked_at: datetime
    ) -> None:
        """Nachgepruefter VIES-Stand (Rechnungs-Worker, R2b).

        Nur wenn die Nummer noch dieselbe ist: hat die Org sie inzwischen
        geaendert, gehoert das Ergebnis nicht mehr zu ihr.
        """
        await self._pool.execute(
            "UPDATE billing_profile SET vat_status = $3, vat_checked_at = $4 "
            "WHERE org_id = $1 AND vat_id = $2",
            org_id,
            vat_id,
            status,
            checked_at,
        )

    async def get(self, org_id: UUID) -> BillingProfile | None:
        row = await self._pool.fetchrow(
            f"SELECT {_COLUMNS} FROM billing_profile WHERE org_id = $1",  # noqa: S608
            org_id,
        )
        return BillingProfile.model_validate(dict(row)) if row is not None else None

    async def save(
        self,
        org_id: UUID,
        data: BillingProfileInput,
        vat_status: VatStatus | None,
        vat_checked_at: datetime | None,
    ) -> BillingProfile:
        row = await self._pool.fetchrow(
            _UPSERT_SQL,
            org_id,
            data.customer_type,
            data.given_name,
            data.family_name,
            data.company_name,
            data.street,
            data.postal_code,
            data.city,
            data.country,
            data.vat_id,
            vat_status,
            vat_checked_at,
        )
        assert row is not None  # RETURNING liefert bei INSERT/UPDATE immer eine Zeile
        return BillingProfile.model_validate(dict(row))


# --- Anwendungsfall --------------------------------------------------------------


async def save_billing_profile(
    repo: BillingProfileRepository,
    checker: VatChecker,
    org_id: UUID,
    data: BillingProfileInput,
    *,
    now: datetime | None = None,
) -> BillingProfile:
    """Speichert die Rechnungsdaten und prueft die USt-IdNr. bei Bedarf.

    VIES wird nur gefragt, wenn sich die Nummer geaendert hat oder der letzte
    Stand nicht „gueltig“ war. Eine bereits gueltige, unveraenderte Nummer
    behaelt Pruefstand und Pruefzeitpunkt, damit ein Adress-Tippfehler keinen
    neuen VIES-Aufruf ausloest.
    """
    if data.vat_id is None:
        return await repo.save(org_id, data, None, None)
    previous = await repo.get(org_id)
    if previous is not None and previous.vat_id == data.vat_id and previous.vat_status == "valid":
        return await repo.save(org_id, data, "valid", previous.vat_checked_at)
    status: VatStatus = await checker.check(data.vat_id)
    checked_at = (now or datetime.now(tz=UTC)) if status != "unchecked" else None
    return await repo.save(org_id, data, status, checked_at)
