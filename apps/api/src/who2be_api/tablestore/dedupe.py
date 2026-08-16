"""Deterministischer Zeilen-Hash fuer den idempotenten Import (ADR-0049).

Spec K: der Dedupe-Schluessel eines Kontoauszugs sind z. B. Datum, Betrag,
Verwendungszweck und Konto — WELCHE Spalten das sind, entscheidet der
Katalog (`wa_table.dedupe_columns`, Postgres); diese Funktion ist generisch
und kanonisiert nur. Der Hash landet als `_dedupe_hash` (UNIQUE) in der
Area-SQLite; `INSERT OR IGNORE` macht den Doppel-Import zum No-op
(engine.insert_rows meldet inserted/skipped).

Kanonisierungs-Kontrakt (dokumentiert, weil der Hash ueber Prozesse und
Releases hinweg stabil bleiben MUSS — sonst bricht die Idempotenz):

- Werte in der Reihenfolge von `dedupe_columns`; die Key-Reihenfolge des
  Row-Dicts ist irrelevant, fehlende Spalten zaehlen als ``None``.
- Jeder Wert wird mit Typ-Tag laengenpraefix-codiert (``{len}:{tag}:{wert}``)
  — Feldgrenzen sind damit eindeutig (kein Separator-Kollisionsrisiko) und
  ``None`` ist von ``""`` unterscheidbar.
- Strings: NFC-normalisiert + getrimmt (``"  Miete "`` == ``"Miete"``).
- Zahlen: ueber `Decimal` normalisiert und als Plain-String repraesentiert —
  ``10``, ``10.0`` und ``Decimal("10.00")`` hashen gleich; ``bool`` wird VOR
  ``int`` erkannt und als eigener Typ getaggt.
- ``date``/``datetime``: ISO-8601 (`isoformat`).
- Alles andere: ``str(wert)``, behandelt wie ein String (Fallback).
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal


def _canonical_number(value: int | float | Decimal) -> str:
    """Plain-Dezimaldarstellung ohne Trailing-Zeros/Exponent (``10.50`` → ``10.5``)."""
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    if decimal_value == 0:
        # Deckt 0, -0.0 und 0.00 ab — `normalize()` wuerde "-0" liefern.
        return "0"
    return format(decimal_value.normalize(), "f")


def _canonical_part(value: object) -> bytes:
    """Ein Wert als typ-getaggter, laengenpraefix-codierter Baustein."""
    if value is None:
        tagged = "n:"
    elif isinstance(value, bool):
        # bool VOR int/float pruefen — bool ist int-Subklasse.
        tagged = f"b:{int(value)}"
    elif isinstance(value, int | float | Decimal):
        tagged = f"d:{_canonical_number(value)}"
    elif isinstance(value, datetime | date):
        # datetime ist date-Subklasse; beide via isoformat().
        tagged = f"t:{value.isoformat()}"
    elif isinstance(value, str):
        tagged = f"s:{unicodedata.normalize('NFC', value).strip()}"
    else:
        tagged = f"s:{unicodedata.normalize('NFC', str(value)).strip()}"
    raw = tagged.encode("utf-8")
    return f"{len(raw)}:".encode() + raw


def row_hash(row: Mapping[str, object], dedupe_columns: Sequence[str]) -> str:
    """SHA-256-Hexdigest ueber die kanonisierte Zeile (ADR-0049, Entscheidung 5).

    `dedupe_columns` bestimmt Auswahl UND Reihenfolge der gehashten Werte —
    die Reihenfolge ist Teil des Kontrakts und kommt aus dem Katalog
    (`wa_table.dedupe_columns`), nie aus dem Row-Dict.
    """
    if not dedupe_columns:
        raise ValueError("dedupe_columns darf nicht leer sein (ADR-0049: UNIQUE _dedupe_hash).")
    digest = hashlib.sha256()
    for column in dedupe_columns:
        digest.update(_canonical_part(row.get(column)))
    return digest.hexdigest()
