"""Fehlercodes in API-Antworten — der Vertrag aus ADR-0051 (#436, W0 von #402).

Drei Ebenen, weil der Vertrag drei Zusagen macht:

1. **Migrierte Stellen** tragen `reason` zusaetzlich zu `detail` — gegen eine
   echte DB, weil ein 404 auf einen unbekannten Agenten sonst gar nicht
   entsteht (`WHO2BE_REQUIRE_DB=1` macht ein fehlendes Postgres zum Fehler
   statt zum Skip, ADR-0041).
2. **Nicht migrierte Stellen** sind unveraendert — das ist die eigentliche
   Risiko-Zusage der Welle: `detail` bleibt Wort fuer Wort, es kommt kein
   Feld dazu, der Content-Type wechselt nicht. Ohne diesen Test faellt eine
   versehentliche Verbreiterung erst beim Client auf.
3. **Der Handler selbst** — `params`, Header und die Abgrenzung zur
   RFC-7807-Serialisierung der Gates. Ohne DB.

Zur Serialisierungs-Frage: `ApiProblem` (Gates, ``application/problem+json``)
und `ApiErrorBody` (alles uebrige, ``application/json``) bleiben zwei Huellen
um EIN Vokabular. `test_gate_error_keeps_rfc7807_shape` haelt fest, dass diese
Welle die Gate-Antworten nicht angefasst hat.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext, require_write_rate
from who2be_api.main import _on_api_error, _on_api_gate_error, app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import AgentToolPolicy, WorkspaceRole

AuthFactory = Callable[[UUID], dict[str, str]]


# --- 1. Migrierte Stellen: `reason` liegt im Body ---------------------------


@pytest.mark.integration
def test_unknown_agent_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """Der Pilot-Fall aus dem Issue: unbekannter Agent => 404 + `agent_not_found`."""
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/agents/{uuid4()}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    # Additiv: derselbe Content-Type und dasselbe `detail` wie vor der Welle.
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Agent nicht gefunden.", "reason": "agent_not_found"}


@pytest.mark.integration
def test_last_workspace_delete_409_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """Der letzte Workspace einer Organization ist geschuetzt (409).

    `setup_workspace` legt eine Personal-Org mit genau einem Workspace an —
    dessen Loeschung ist damit garantiert der Grenzfall.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.delete(
                f"/v1/workspaces/{workspace_id}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 409
    body = resp.json()
    assert body["reason"] == "last_workspace_undeletable"
    assert body["detail"] == (
        "Der letzte Workspace einer Organization kann nicht geloescht werden."
    )


@pytest.mark.integration
def test_disabled_agent_render_409_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W1 (#482): Render eines deaktivierten Agenten => 409 + `agent_disabled`.

    Ein frisch angelegter Agent ist eine Huelle im Status `disabled` — der Fall
    ist damit ohne Zusatz-Setup erreichbar. Der Test haelt beides fest: den
    neuen `reason` UND das WOERTLICH unveraenderte `detail`. Genau das ist die
    Zusage der Welle — sie ergaenzt ein Feld, sie formuliert nichts um.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)
            created = client.post(
                f"/v1/workspaces/{workspace_id}/agents",
                json={"name": "Deaktivierte Huelle"},
                headers=headers,
            )
            assert created.status_code == 201, created.text
            agent_id = created.json()["id"]
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/agents/{agent_id}/render",
                headers=headers,
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Agent ist deaktiviert.", "reason": "agent_disabled"}


@pytest.mark.integration
def test_unknown_kb_node_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W4 (#484): unbekannter KB-Node => 404 + `kb_node_not_found`.

    Der 404 ist hier bewusst ein Nicht-Existenz-Orakel-Schutz: unbekannt und
    unsichtbar sehen fuer den Aufrufer gleich aus. Genau deshalb braucht der
    MCP-Client den `reason` — der deutsche Prosa-Text sagt ihm nichts.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/kb/nodes/{uuid4()}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    # Gleichheit statt Teilmenge: sie belegt `detail` WOERTLICH unveraendert
    # und zugleich, dass ausser `reason` kein Feld dazugekommen ist.
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "KB-Node nicht gefunden.", "reason": "kb_node_not_found"}


@pytest.mark.integration
def test_unknown_work_area_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W4 (#484): unbekannte Area => 404 + `area_not_found`.

    Zweite Stelle derselben Welle, aber ein anderer Weg durch den Code: der
    Grund entsteht im Service (`_require_shared_area`), nicht im Router — die
    Welle deckt beide Schichten ab.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/work-areas/{uuid4()}/grants",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Area nicht gefunden.", "reason": "area_not_found"}


@pytest.mark.integration
def test_unknown_external_tool_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W5 (#485): unbekanntes externes Tool => 404 + `external_tool_not_found`.

    Gleichheit statt Teilmenge — sie belegt `detail` WOERTLICH unveraendert und
    zugleich, dass ausser `reason` kein Feld dazugekommen ist.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/external_tools/{uuid4()}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {
        "detail": "Externes Tool nicht gefunden.",
        "reason": "external_tool_not_found",
    }


@pytest.mark.integration
def test_unknown_system_prompt_template_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W5 (#485): unbekanntes Template => 404 + `system_prompt_template_not_found`."""
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/system-prompts/{uuid4()}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    assert resp.json() == {
        "detail": "System-Prompt-Template nicht gefunden.",
        "reason": "system_prompt_template_not_found",
    }


@pytest.mark.integration
def test_unknown_playbook_and_resource_usages_404_carry_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W5 (#485): die beiden Backlink-Pfade => 404 + `playbook_not_found`/`resource_not_found`.

    Zwei Gruende in einem Setup: der Reverse-Lookup ist derselbe Service, die
    Fehler trennen aber sauber nach Achse — genau das soll ein MCP-Client
    unterscheiden koennen, ohne den deutschen Prosa-Text zu parsen.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)
            playbook = client.get(
                f"/v1/workspaces/{workspace_id}/playbooks/{uuid4()}/usages", headers=headers
            )
            resource = client.get(
                f"/v1/workspaces/{workspace_id}/resources/{uuid4()}/usages", headers=headers
            )
    finally:
        cleanup_workspaces([user_id])

    assert playbook.status_code == 404
    assert playbook.json() == {
        "detail": "Playbook nicht gefunden.",
        "reason": "playbook_not_found",
    }
    assert resource.status_code == 404
    assert resource.json() == {
        "detail": "Resource nicht gefunden.",
        "reason": "resource_not_found",
    }


@pytest.mark.integration
def test_unknown_feedback_target_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W5 (#485): Feedback zu einem unbekannten Element => 404 + `feedback_element_not_found`.

    Der Grund heisst bewusst `element` und nicht `target`: dieselbe Stelle
    deckt auch den unbekannten Feedback-EINTRAG ab (Triage, Detailsicht) —
    ein `feedback_target_not_found` waere dort gelogen.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/feedback/persona/{uuid4()}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    assert resp.json() == {
        "detail": "Element nicht gefunden.",
        "reason": "feedback_element_not_found",
    }


@pytest.mark.integration
def test_duplicate_alias_and_slug_409_carry_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W5 (#485): die beiden Namensraum-Konflikte => 409 + je eigener `reason`.

    Alias (externes Tool) und Slug (Template) sind zwei Namensraeume, nicht
    einer — deshalb zwei Gruende statt eines geteilten `slug_conflict`, dessen
    generischer Locale-Text beide Meldungen verwaessert haette.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    base = f"/v1/workspaces/{workspace_id}"
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)
            first = client.post(
                f"{base}/external_tools", json={"name": "Kalender"}, headers=headers
            )
            assert first.status_code == 201, first.text
            alias = client.post(
                f"{base}/external_tools", json={"name": "Kalender"}, headers=headers
            )

            body = {"name": "Mein Template", "content": {"description": "", "body": "Hi"}}
            created = client.post(f"{base}/system-prompts", json=body, headers=headers)
            assert created.status_code == 201, created.text
            slug = client.post(f"{base}/system-prompts", json=body, headers=headers)
    finally:
        cleanup_workspaces([user_id])

    assert alias.status_code == 409
    assert alias.json() == {
        "detail": "Ein externes Tool mit diesem Alias existiert bereits.",
        "reason": "external_tool_alias_conflict",
    }
    assert slug.status_code == 409
    assert slug.json() == {
        "detail": "Ein Template mit diesem Slug existiert bereits.",
        "reason": "system_prompt_template_slug_conflict",
    }


@pytest.mark.integration
def test_invalid_against_param_422_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W5 (#485): kaputter `against`-Parameter => 422 + `invalid_against_param`.

    Der Grund ist bewusst domaenenfrei benannt: derselbe Wortlaut steht heute
    in vier Services (Persona/Playbook/Resource/Template). Spaetere Wellen
    koennen ihn verlustfrei wiederverwenden — der Locale-Text ist wortgleich
    zum `detail`.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    base = f"/v1/workspaces/{workspace_id}/system-prompts"
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)
            created = client.post(
                base,
                json={"name": "Diff-Ziel", "content": {"description": "", "body": "Hi"}},
                headers=headers,
            )
            assert created.status_code == 201, created.text
            resp = client.get(
                f"{base}/{created.json()['id']}/versions/1/diff?against=uebermorgen",
                headers=headers,
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 422
    assert resp.json() == {
        "detail": "Ungueltiger 'against'-Parameter; erwartet 'active' oder eine Versions-Nummer.",
        "reason": "invalid_against_param",
    }


@pytest.mark.integration
def test_unknown_invitation_accept_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W3 (#486): unbekannter Einladungs-Token => 404 + `invitation_not_found`.

    Der Einladungs-Pfad aus AK 5. Gleichheit statt Teilmenge: sie belegt
    zugleich, dass `detail` WOERTLICH steht und ausser `reason` kein Feld
    dazugekommen ist.
    """
    user_id = fresh_user_id()
    setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/v1/invitations/gibt-es-nicht/accept",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Einladung nicht gefunden.", "reason": "invitation_not_found"}


@pytest.mark.integration
def test_workspace_create_unknown_org_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W3 (#486): Workspace-Anlage in fremder/unbekannter Org => 404.

    Unbekannt und "nicht Mitglied" fallen bewusst auf denselben Grund
    zusammen — die Trennung waere ein Enumerations-Kanal auf fremde Orgs.
    """
    user_id = fresh_user_id()
    setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/v1/organizations/{uuid4()}/workspaces",
                json={"name": "Zweitraum", "slug": "zweitraum"},
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    assert resp.json() == {
        "detail": "Organization nicht gefunden.",
        "reason": "organization_not_found",
    }


@pytest.mark.integration
def test_duplicate_workspace_slug_409_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W3 (#486): belegter Workspace-Slug => 409 + `workspace_slug_conflict`.

    Der zweite Workspace-Pfad aus AK 5, und der interessantere: 409 statt 404,
    und der Grund trennt die Slug-Kollision von `organization_slug_conflict`
    aus demselben Onboarding-Fluss.
    """
    user_id = fresh_user_id()
    setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)
            orgs = client.get("/v1/organizations", headers=headers)
            assert orgs.status_code == 200, orgs.text
            org_id = orgs.json()[0]["id"]
            # `ensure_personal_workspace` seedet den Slug `personal` — ein
            # zweiter mit demselben Slug verletzt `(org_id, slug)`.
            resp = client.post(
                f"/v1/organizations/{org_id}/workspaces",
                json={"name": "Nochmal Personal", "slug": "personal"},
                headers=headers,
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 409
    assert resp.json() == {
        "detail": "Workspace-Slug ist in dieser Organization vergeben.",
        "reason": "workspace_slug_conflict",
    }


@pytest.mark.integration
def test_unknown_persona_playbook_and_resource_404_carry_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W2 (#483): je ein Lesepfad pro Entitaet => 404 + eigener `reason`.

    Die drei inhaltstragenden Aggregate in einem Setup — genau die Pfade, die
    ein Nutzer im Editor am haeufigsten trifft. Gleichheit statt Teilmenge:
    sie belegt `detail` WOERTLICH unveraendert und zugleich, dass ausser
    `reason` kein Feld dazugekommen ist.

    `playbook_not_found`/`resource_not_found` sind hier WIEDERVERWENDET (seit
    W5, damals die Backlink-Pfade): der Wortlaut ist identisch, also gehoert
    beides auf denselben Grund. Ein Zwilling haette zwei Locale-Keys fuer
    denselben Satz erzeugt — und der uebersetzte Text gewinnt gegen `detail`.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    base = f"/v1/workspaces/{workspace_id}"
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)
            persona = client.get(f"{base}/personas/{uuid4()}", headers=headers)
            playbook = client.get(f"{base}/playbooks/{uuid4()}", headers=headers)
            resource = client.get(f"{base}/resources/{uuid4()}", headers=headers)
    finally:
        cleanup_workspaces([user_id])

    assert persona.status_code == 404
    assert persona.headers["content-type"].startswith("application/json")
    assert persona.json() == {"detail": "Persona nicht gefunden.", "reason": "persona_not_found"}
    assert playbook.status_code == 404
    assert playbook.json() == {
        "detail": "Playbook nicht gefunden.",
        "reason": "playbook_not_found",
    }
    assert resource.status_code == 404
    assert resource.json() == {
        "detail": "Resource nicht gefunden.",
        "reason": "resource_not_found",
    }


@pytest.mark.integration
def test_duplicate_resource_slug_409_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W2 (#483): belegter Resource-Slug => 409 + `resource_slug_conflict`.

    Ein eigener Grund statt eines geteilten `slug_conflict`: der Slug-Konflikt
    hat in Workspace, Organisation, Template und Resource jeweils einen eigenen
    Wortlaut. Ein Sammelgrund haette alle vier auf einen generischen
    Locale-Text gezogen.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    base = f"/v1/workspaces/{workspace_id}/resources"
    body = {"name": "Runbook", "content": {"description": "", "blocks": [], "tags": []}}
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)
            first = client.post(base, json=body, headers=headers)
            assert first.status_code == 201, first.text
            resp = client.post(base, json=body, headers=headers)
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 409
    assert resp.json() == {
        "detail": "Eine Resource mit diesem Slug existiert bereits.",
        "reason": "resource_slug_conflict",
    }


@pytest.mark.integration
def test_composition_cycles_409_carry_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """W2 (#483, AK 5): beide Zyklus-Guards => 409 + `composition_cycle`.

    Playbook- und Resource-Composition teilen sich den Grund, weil sie sich
    schon das `detail` teilen — zwei Gruende waeren zwei Locale-Keys fuer
    denselben Satz. Der bestehende Client-Key `common.errors.cycleRejected`
    bleibt unangetastet: die UI verzweigt dort auf den Status 409, nicht auf
    den `reason`, und wuerde von einer Umbenennung still gebrochen.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    base = f"/v1/workspaces/{workspace_id}"
    pb_body = {
        "name": "Zyklus-Playbook",
        "content": {"description": "d", "body": "1. Step.", "type": "workflow", "tags": []},
    }
    res_body = {"name": "Zyklus-Resource", "content": {"description": "", "blocks": [], "tags": []}}
    try:
        with TestClient(app) as client:
            headers = make_auth_headers(user_id)

            pb_a = client.post(
                f"{base}/playbooks", json={**pb_body, "name": "PB-A"}, headers=headers
            )
            pb_b = client.post(
                f"{base}/playbooks", json={**pb_body, "name": "PB-B"}, headers=headers
            )
            assert pb_a.status_code == 201, pb_a.text
            assert pb_b.status_code == 201, pb_b.text
            a_id, b_id = pb_a.json()["id"], pb_b.json()["id"]
            forward = client.put(
                f"{base}/playbooks/{a_id}/composes",
                json={"child_ids": [b_id]},
                headers=headers,
            )
            assert forward.status_code == 200, forward.text
            playbook_cycle = client.put(
                f"{base}/playbooks/{b_id}/composes",
                json={"child_ids": [a_id]},
                headers=headers,
            )

            res_a = client.post(
                f"{base}/resources", json={**res_body, "name": "Res-A"}, headers=headers
            )
            res_b = client.post(
                f"{base}/resources", json={**res_body, "name": "Res-B"}, headers=headers
            )
            assert res_a.status_code == 201, res_a.text
            assert res_b.status_code == 201, res_b.text
            ra_id, rb_id = res_a.json()["id"], res_b.json()["id"]
            res_forward = client.put(
                f"{base}/resources/{ra_id}/sub_resources",
                json={"links": [{"child_id": rb_id, "position": 0, "link_scope": "resource"}]},
                headers=headers,
            )
            assert res_forward.status_code == 200, res_forward.text
            resource_cycle = client.put(
                f"{base}/resources/{rb_id}/sub_resources",
                json={"links": [{"child_id": ra_id, "position": 0, "link_scope": "resource"}]},
                headers=headers,
            )
    finally:
        cleanup_workspaces([user_id])

    expected = {
        "detail": "Verknuepfung wuerde einen Zyklus erzeugen.",
        "reason": "composition_cycle",
    }
    assert playbook_cycle.status_code == 409, playbook_cycle.text
    assert playbook_cycle.json() == expected
    assert resource_cycle.status_code == 409, resource_cycle.text
    assert resource_cycle.json() == expected


def test_missing_db_pool_503_carries_reason(
    patched_jwt_secret: str, make_auth_headers: AuthFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kein Pool => 503 + `db_unavailable`.

    Bewusst ohne DB: der Fall IST die fehlende DB. `get_pool` wirft
    `RuntimeError`, wenn der Lifespan keinen Pool aufbauen konnte — genau das
    wird hier erzwungen, statt auf einen kaputten Testlauf zu warten.
    """
    import who2be_api.core.security as security_module

    def _no_pool() -> asyncpg.Pool:
        raise RuntimeError("Datenbank-Pool ist nicht initialisiert.")

    monkeypatch.setattr(security_module, "get_pool", _no_pool)

    with TestClient(app) as client:
        resp = client.get(
            f"/v1/workspaces/{uuid4()}/agents",
            headers=make_auth_headers(fresh_user_id()),
        )

    assert resp.status_code == 503
    assert resp.json() == {"detail": "Datenbank nicht verfuegbar.", "reason": "db_unavailable"}


# --- 1b. Auth, Token, OAuth, Limits (W6, #487) ------------------------------
#
# Die einzige Welle mit Sicherheitsbezug. Der `reason` darf hier NICHT feiner
# aufloesen als der bestehende `detail`-Text — sonst wird aus einem stabilen
# Fehlercode ein Enumerations-Orakel.

_CREDENTIALS_BODY = {
    "detail": "Ungueltige oder fehlende Anmeldedaten.",
    "reason": "invalid_credentials",
}


def _jwt_with(secret: str, **claims: object) -> str:
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def test_all_authentication_failures_share_one_reason(patched_jwt_secret: str) -> None:
    """AK 4: fuenf verschiedene Ursachen, EIN Grund — kein Enumerations-Orakel.

    Fehlender Header, kaputter Bearer, falsch signiertes JWT, nicht erlaubte
    `role` und ein unbrauchbares `sub` liefern heute denselben Status, denselben
    Text und denselben `WWW-Authenticate`-Header. Genau deshalb teilen sie sich
    auch den `reason`: waere er feiner, koennte ein Angreifer aus dem Code
    ablesen, WORAN die Anmeldung gescheitert ist. Der Test faellt, sobald eine
    Call-Site anfaengt, ihren eigenen Grund zu setzen.
    """
    path = f"/v1/workspaces/{uuid4()}/agents"
    fremd = _jwt_with("ein-ganz-anderes-secret-0123456789")
    service_role = _jwt_with(patched_jwt_secret, role="service_role")
    kaputtes_sub = _jwt_with(patched_jwt_secret, sub="keine-uuid")
    cases = {
        "kein Header": {},
        "kein JWT": {"Authorization": "Bearer nicht-mal-ein-jwt"},
        "falsches Secret": {"Authorization": f"Bearer {fremd}"},
        "verbotene role": {"Authorization": f"Bearer {service_role}"},
        "kaputtes sub": {"Authorization": f"Bearer {kaputtes_sub}"},
    }

    with TestClient(app) as client:
        responses = {name: client.get(path, headers=headers) for name, headers in cases.items()}

    for name, resp in responses.items():
        assert resp.status_code == 401, f"{name}: {resp.text}"
        assert resp.json() == _CREDENTIALS_BODY, name
        assert resp.headers["www-authenticate"] == "Bearer", name


@pytest.mark.integration
def test_unknown_api_token_is_indistinguishable_from_a_missing_one(
    patched_jwt_secret: str, migrated_db: None
) -> None:
    """Der Token-Pfad braucht die DB — und muss trotzdem gleich antworten.

    Ein unbekannter (oder widerrufener) `w2b_`-Token laeuft durch den
    Repository-Lookup, ein fehlender Header nicht. Beide enden bei demselben
    Body: sonst verriete der Grund, ob ein Token-Hash existiert.
    """
    path = f"/v1/workspaces/{uuid4()}/agents"
    with TestClient(app) as client:
        unknown = client.get(path, headers={"Authorization": "Bearer w2b_gibt-es-nicht"})
        missing = client.get(path)

    assert unknown.status_code == missing.status_code == 401
    assert unknown.json() == missing.json() == _CREDENTIALS_BODY
    assert unknown.headers["www-authenticate"] == "Bearer"


def test_write_rate_limit_429_carries_reason_and_params() -> None:
    """AK 6: `reason` **und** das Limit als `params`; `detail` woertlich wie vorher.

    Die erreichte Grenze gehoert in die Daten, nicht in den Locale-Key — sonst
    braucht jede konfigurierte Rate ihre eigene Uebersetzung. Kein DB-Bedarf:
    das Sliding-Window ist In-Memory und wird ueber eine frische `agent_id`
    isoliert.
    """
    ctx = WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=True,
        agent_id=uuid4(),
        tool_policy=AgentToolPolicy(write_rate_limit=1),
    )
    mini = FastAPI()
    mini.add_exception_handler(ApiError, _on_api_error)

    @mini.post("/write")
    def write() -> dict[str, bool]:
        require_write_rate(ctx)
        return {"ok": True}

    with TestClient(mini, raise_server_exceptions=False) as client:
        assert client.post("/write").status_code == 200
        blocked = client.post("/write")

    assert blocked.status_code == 429
    assert blocked.json() == {
        "detail": "Schreib-Rate-Limit dieses Agenten erreicht — bitte spaeter erneut versuchen.",
        "reason": "write_rate_limited",
        "params": {"limit": 1},
    }


@pytest.mark.integration
def test_unknown_token_404_and_invalid_cursor_422_carry_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """Die beiden Bestands-Pfade der Welle, die die Web-UI wirklich sieht.

    Der Keyset-Cursor sass bis W2 unter dem Waechter fuer *nicht* migrierte
    Stellen (`test_unmigrated_error_body_is_unchanged`); der ist in W2 auf den
    `locale`-Filter umgezogen, weil der Cursor zu dieser Welle gehoert.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    auth = make_auth_headers(user_id)
    try:
        with TestClient(app) as client:
            renamed = client.patch(
                f"/v1/workspaces/{workspace_id}/tokens/{uuid4()}",
                json={"name": "neu"},
                headers=auth,
            )
            cursor = client.get(
                f"/v1/workspaces/{workspace_id}/personas?cursor=kein-gueltiger-cursor",
                headers=auth,
            )
    finally:
        cleanup_workspaces([user_id])

    assert renamed.status_code == 404, renamed.text
    assert renamed.json() == {"detail": "Token nicht gefunden.", "reason": "token_not_found"}
    assert cursor.status_code == 422, cursor.text
    assert cursor.json() == {"detail": "Ungueltiger Cursor.", "reason": "invalid_cursor"}


# --- 2. Nicht migrierte Stellen: byte-identisch zu vorher -------------------


@pytest.mark.integration
def test_unmigrated_error_body_is_unchanged(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """Eine Stelle, die noch KEINE Welle angefasst hat, traegt kein `reason`.

    Die Zusage jeder Welle ist Additivitaet an ihren Stellen — nicht ein neues
    Feld ueberall. Faellt dieser Test, hat jemand entweder den Handler zu breit
    registriert oder `HTTPException` global ersetzt.

    Der Waechter sass bis W2 (#483) auf dem Persona-404; seit dieser Welle
    traegt der einen `reason`. Er zeigt jetzt auf den `locale`-Filter
    (`core/locale.py`) — eine Datei, die in **keiner** Bestandstabelle der
    sechs Wellen steht. Der naheliegende Ersatz waere der Keyset-Cursor
    gewesen; der gehoert aber zu W6 (#487) und haette denselben Umzug in der
    naechsten Welle noch einmal erzwungen.

    Der Test muss end-to-end gegen `app` laufen, nicht gegen eine Mini-App:
    er warnt davor, dass jemand den Handler in `main.py` zu breit registriert
    — und genau diese Registrierung sieht eine selbstgebaute App nicht.

    Wenn #402 vollstaendig ist, gibt es keine unmigrierte Stelle mehr. Dann
    wird dieser Test entweder synthetisch (eigene Route, die eine nackte
    `HTTPException` wirft) oder er faellt weg — er hat dann seinen Zweck
    ueberlebt.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/personas?locale=123",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 422
    assert resp.json() == {"detail": "Ungueltiger locale-Parameter: '123'."}


# --- 3. Handler-Ebene: params, Header, Abgrenzung zu RFC 7807 --------------


def _mini_app(error: ApiError) -> TestClient:
    mini = FastAPI()
    mini.add_exception_handler(ApiError, _on_api_error)

    @mini.get("/boom")
    def boom() -> None:
        raise error

    return TestClient(mini, raise_server_exceptions=False)


def test_handler_omits_params_when_absent() -> None:
    """Ohne Platzhalter kein leeres Feld — sonst traegt jede Antwort Ballast."""
    with _mini_app(
        ApiError(status_code=404, detail="Agent nicht gefunden.", reason="agent_not_found")
    ) as client:
        resp = client.get("/boom")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Agent nicht gefunden.", "reason": "agent_not_found"}


def test_handler_passes_params_through() -> None:
    """`params` transportiert die Werte, die der Client in den Text interpoliert."""
    with _mini_app(
        ApiError(
            status_code=413,
            detail="Datei zu gross (max. 10 MB).",
            reason="ingest_too_large",
            params={"limit": "10 MB", "size": 42},
        )
    ) as client:
        resp = client.get("/boom")

    assert resp.status_code == 413
    assert resp.json()["params"] == {"limit": "10 MB", "size": 42}


def test_handler_keeps_http_exception_headers() -> None:
    """`ApiError` ist eine `HTTPException` — ihre Header duerfen nicht verloren gehen.

    Sonst braeche die erste migrierte 401-Stelle den Auth-Flow: ohne
    `WWW-Authenticate` weiss der Client nicht, wie er sich anmelden soll.
    """
    with _mini_app(
        ApiError(
            status_code=401,
            detail="Nicht authentifiziert.",
            reason="mfa_required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    ) as client:
        resp = client.get("/boom")

    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_gate_error_keeps_rfc7807_shape() -> None:
    """Die Gate-Serialisierung ist von dieser Welle unberuehrt.

    Zwei Huellen, ein Vokabular: hier `application/problem+json` mit `title`
    und `actionable_by`, beim schlanken Body nicht. Wuerde der neue Handler
    auch `ApiGateError` greifen, faende man es hier.
    """
    mini = FastAPI()
    mini.add_exception_handler(ApiGateError, _on_api_gate_error)
    mini.add_exception_handler(ApiError, _on_api_error)

    @mini.get("/gate")
    def gate() -> None:
        raise ApiGateError(
            status=403,
            reason="insufficient_role",
            actionable_by="human",
            detail="Diese Aktion erfordert mindestens die Rolle 'admin'.",
        )

    with TestClient(mini, raise_server_exceptions=False) as client:
        resp = client.get("/gate")

    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["reason"] == "insufficient_role"
    assert body["actionable_by"] == "human"
    assert "title" in body


def test_pilot_reasons_are_part_of_the_one_vocabulary() -> None:
    """Die drei Pilot-Gruende stehen in `ProblemReason`, nicht in einem zweiten Enum.

    Das ist die Owner-Entscheidung vom 2026-09-06 (Weg B) als Test: taucht
    irgendwann ein paralleler `ErrorCode`-Enum auf, laufen die beiden Listen
    auseinander — dieser Test haelt fest, wo die Gruende hingehoeren.
    """
    from typing import get_args

    from who2be_models.errors import ProblemReason

    reasons = set(get_args(ProblemReason))
    assert {"agent_not_found", "db_unavailable", "last_workspace_undeletable"} <= reasons
