"""Waechter: jedes Entitlement-Feld geht den ganzen Weg (Bericht W8/P3, Option A).

**Warum dieser Test existiert.** Ein neues Pro-Feature kostet in diesem Repo
keine Architekturarbeit, sondern eine Checkliste: 22 Kern-Dateien, davon 13 mit
ein bis sechs geaenderten Zeilen. Das Problem ist nicht der Aufwand, sondern die
fehlende Rueckmeldung. Eine Messung mit sechs gezielten Auslassungen
(`/home/luetzey/recherche/pro-feature-architektur-2026-09-24.md` §3.3) hat
gezeigt: **vier von sechs liefen durch die volle Suite, ruff und mypy — gruen.**

Die subtilste davon (M4): `PgEntitlementRepository` verlangt pro neuem Feld
**vier** Aenderungen in einer Datei (SELECT, INSERT-Spalten,
`ON CONFLICT DO UPDATE`, Journal-INSERT). Drei davon sind reine Wiederholung.
Vergisst man das Feld nur im `ON CONFLICT DO UPDATE`, schreibt der **erste**
Insert korrekt und kein Test merkt etwas — der Fehler tritt erst beim zweiten
Webhook derselben Org auf, also beim Upgrade eines Bestandskunden.

Dieser Test macht die Kette laut. Er prueft **nicht** Verhalten, sondern
Vollstaendigkeit: dass jedes deklarierte Feld an den Stellen bekannt ist, die es
kennen muessen. Kein zentrales Register, keine Abstraktionsschicht — bewusst
(Bericht §6): der Weg ist nicht zu kompliziert, er ist zu still.

**Was der Test NICHT leistet:** nichts an der Durchsetzung. Er sichert die
Definitions-, Persistenz- und Anzeigeseite, nicht die Wirkung eines Gates. Das
Router-seitige Gegenstueck ist `apps/api/tests/test_gate_inventory.py`.

**Warum diese Datei unter `packages/billing/tests/` liegt, obwohl sie
ueberwiegend Kern-Code prueft:** Zusicherung 2 braucht die `META_*`-Keys aus
`who2be_billing.plans`. Unter `apps/api/tests/` wuerde sie in einem Lauf ohne
`--group billing` (On-Prem-Kern, CLAUDE.md) an der Collection scheitern oder
einen Skip brauchen — und ein uebersprungener Test ist laut CONTRIBUTING kein
bestandener (Skip-Budget 0). Der `conftest.py` dieses Verzeichnisses regelt den
Fall sauber; `test_workspace_quota_downgrade_chain.py` liegt aus demselben Grund
hier und importiert ebenso Kern-Module.
"""

from __future__ import annotations

import inspect
import re
from uuid import UUID

import pytest

from who2be_api.licensing.entitlement import Entitlement
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository
from who2be_api.routers.entitlement import EntitlementInfo
from who2be_billing import plans as plans_module
from who2be_billing.plans import FREE_PLAN, PRO_PLAN

# --- Feld-Klassifikation -----------------------------------------------------
# Jedes Feld von `Entitlement` muss in genau einer dieser beiden Listen stehen.
# Ein neues Feld, das in keiner steht, bricht `test_every_field_is_classified` —
# und zwar auch dann, wenn es nicht `*_quota*` heisst. Genau das ist der Punkt:
# eine Namenskonvention als einziges Erkennungsmerkmal waere ein Waechter, der
# beim uebernaechsten Feature schweigt (Bericht §6, Option A, „Risiko").

# Obergrenzen, die den vollen Weg gehen muessen: Persistenz (vier SQL-Fragmente)
# + Provider-Metadatum (`META_*` in plans.py, in `Plan.metadata()`) + Anzeige
# (`EntitlementInfo`).
QUOTA_FIELDS = (
    "mcp_monthly_quota",
    "mcp_rate_per_min",
    "token_quota",
    "storage_quota_bytes",
    "workspace_quota",
)

# Felder, die KEINE Obergrenze sind und deshalb kein Plan-Metadatum brauchen.
# Jeder Eintrag mit Begruendung — wer hier etwas eintraegt, soll es begruenden
# muessen statt es nur wegzuschieben:
#   status      — Zugriffs-Wahrheit (`is_active`), kommt aus dem Ereignis, nicht
#                 aus dem Tarif.
#   features    — Feature-Codes; im Metadatum als `license_policy` (eine
#                 whitespace-separierte Liste, kein Feld-gleicher Key).
#   expires_at  — Ablauffrist aus dem Anbieter-Ereignis (#452), keine Menge.
#   grace_until — reines Dunning-Signal fuer das Banner, steuert nichts.
NON_QUOTA_FIELDS = (
    "status",
    "features",
    "expires_at",
    "grace_until",
)

# Feste, bedeutungslose Org-ID: `Plan.metadata()` verlangt eine, der Test prueft
# aber nur die Schluessel, nicht den Wert.
_ANY_ORG = UUID("00000000-0000-0000-0000-000000000001")


def _upsert_source() -> str:
    return inspect.getsource(PgEntitlementRepository.upsert)


def _sql_only(source: str) -> str:
    """Nur die SQL-String-Literale eines Quelltext-Abschnitts.

    Ohne diesen Filter wuerde die Pruefung ins Leere greifen: unmittelbar hinter
    jeder Query steht die Python-Argumentliste (`entitlement.workspace_quota,`),
    und ein dort noch vorhandener Feldname liesse eine fehlende SQL-Spalte als
    „vorhanden\" durchgehen. Genau das hat die Rot-Probe zu M4 zuerst gezeigt.
    """
    return "\n".join(line for line in source.splitlines() if line.strip().startswith('"'))


def _sql_fragments() -> dict[str, str]:
    """Die vier SQL-Fragmente, in denen jedes persistierte Feld vorkommen muss.

    Bewusst eine Quelltext-Pruefung: die Queries sind inline-Strings, es gibt
    keine Spaltenliste als Datenstruktur, die man auslesen koennte. Der Test
    zerlegt sie an ihren Ankern und prueft je Fragment — so nennt die
    Fehlermeldung nicht nur das Feld, sondern die Stelle.
    """
    fetch_src = inspect.getsource(PgEntitlementRepository.fetch)
    upsert_src = _upsert_source()

    select_start = fetch_src.index("SELECT ")
    select_end = fetch_src.index("FROM org_entitlement")
    insert_start = upsert_src.index("INSERT INTO org_entitlement")
    conflict_start = upsert_src.index("ON CONFLICT (org_id) DO UPDATE SET")
    journal_start = upsert_src.index("INSERT INTO entitlement_history")

    return {
        "SELECT (fetch)": fetch_src[select_start:select_end],
        "INSERT-Spaltenliste (upsert)": _sql_only(upsert_src[insert_start:conflict_start]),
        "ON CONFLICT DO UPDATE (upsert)": _sql_only(upsert_src[conflict_start:journal_start]),
        "Journal-INSERT entitlement_history (upsert)": _sql_only(upsert_src[journal_start:]),
    }


def test_every_field_is_classified() -> None:
    """Kein Entitlement-Feld darf unklassifiziert bleiben.

    Die Waechterwirkung dieses Tests haengt an dieser Zusicherung: ein neues
    Feld, das der Autor hier nicht eintraegt, faellt sofort auf — statt still
    an allen weiteren Pruefungen vorbeizulaufen, weil es kein `*_quota*`-Muster
    trifft.
    """
    declared = set(Entitlement.model_fields)
    classified = set(QUOTA_FIELDS) | set(NON_QUOTA_FIELDS)

    unclassified = sorted(declared - classified)
    assert not unclassified, (
        f"Neue(s) Entitlement-Feld(er) {unclassified} ist/sind in diesem Test nicht "
        "klassifiziert. Trage es in QUOTA_FIELDS ein (dann prueft der Test Persistenz, "
        "Plan-Metadatum und Anzeige mit) oder in NON_QUOTA_FIELDS mit Begruendung."
    )

    stale = sorted(classified - declared)
    assert not stale, (
        f"{stale} steht in der Klassifikation, ist aber kein Entitlement-Feld mehr. "
        "Eintrag entfernen."
    )

    overlap = sorted(set(QUOTA_FIELDS) & set(NON_QUOTA_FIELDS))
    assert not overlap, f"{overlap} steht in beiden Listen — genau eine ist richtig."


@pytest.mark.parametrize("field", sorted(Entitlement.model_fields))
def test_field_appears_in_all_four_sql_fragments(field: str) -> None:
    """Jedes persistierte Feld steht in allen vier SQL-Fragmenten (Mutation M4).

    Drei der vier Vorkommen sind Wiederholung; eines zu vergessen ist fuer alle
    anderen Tests folgenlos, weil der erste Insert dann korrekt schreibt und nur
    das Fortschreiben beim zweiten Ereignis fehlt.
    """
    missing = [
        label
        for label, fragment in _sql_fragments().items()
        if not re.search(rf"\b{field}\b", fragment)
    ]
    assert not missing, (
        f"`{field}` fehlt in {len(missing)} der vier SQL-Fragmente von "
        f"PgEntitlementRepository: {missing}. Ein fehlendes "
        "`ON CONFLICT DO UPDATE` schreibt das Feld beim Upgrade eines "
        "Bestandskunden nie fort (Bericht W8/P3, Mutation M4)."
    )


@pytest.mark.parametrize("field", QUOTA_FIELDS)
def test_quota_field_has_plan_metadata_key(field: str) -> None:
    """Jedes Quota-Feld hat einen `META_*`-Key und erscheint in `Plan.metadata()`.

    Der Pull-Adapter liest die Obergrenze aus der Provider-Metadata zurueck;
    fehlt der Key, buchen zahlende Orgs den Tarif, bekommen die Zahl aber nie.
    """
    const_name = f"META_{field.upper()}"
    assert hasattr(plans_module, const_name), (
        f"`{const_name}` fehlt in who2be_billing.plans — das Quota-Feld "
        f"`{field}` hat damit keinen Metadaten-Schluessel."
    )
    assert getattr(plans_module, const_name) == field, (
        f"`{const_name}` muss den Feldnamen `{field}` tragen; der Pull-Adapter "
        "liest die Metadata unter genau diesem Schluessel zurueck."
    )

    for plan in (FREE_PLAN, PRO_PLAN):
        metadata = plan.metadata(org_id=_ANY_ORG)
        assert field in metadata, (
            f"`{field}` fehlt in Plan.metadata() von `{plan.code}` — der gebuchte "
            "Tier uebertraegt die Obergrenze dann nicht an den Zahlungsanbieter."
        )


@pytest.mark.parametrize("field", QUOTA_FIELDS)
def test_quota_field_is_visible_in_entitlement_info(field: str) -> None:
    """Jedes Quota-Feld erscheint im `EntitlementInfo`-Modell (Web-Anzeige).

    Ein Kontingent, das nur gilt, aber nirgends steht, ist fuer den Kunden ein
    unerklaerter 402.
    """
    assert field in EntitlementInfo.model_fields, (
        f"`{field}` fehlt in EntitlementInfo (routers/entitlement.py) — die "
        "Web-UI kann die Grenze dann nicht anzeigen."
    )
