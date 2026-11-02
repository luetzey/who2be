"""REST der Werkzeug-Profile pro Agent (ADR-0059 §7, Paket Q2b).

Router-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`). Die Datenhaltung
belegt `test_tool_profile_repository.py` (Q2a); hier geht es um den Weg ueber
HTTP: Rollen (W59-2), `human_only`, den verwalteten Builder, die Fehlercodes
409/422 und das Audit. Kritische Zusicherungen:

- Profile pflegt nur `admin`; `editor`, `viewer` und Agent-Tokens bekommen
  `insufficient_role`. Lesen (Liste, Katalog) darf jedes Mitglied.
- Die Zuordnung am Agenten darf `editor`, aber nur ein Mensch: ein
  agent-gebundener Token bekommt `human_only` (RFC 7807), auch wenn er die
  Rolle editor traegt.
- Der Zuordnungsweg gilt auch fuer den verwalteten Builder (kein
  `managed_aggregate`), sonst liefe P3a beim wichtigsten Profil ins Leere.
- Kern-Werkzeuge sind nicht sperrbar, Namen ausserhalb des Katalogs werden
  abgelehnt, ein zugeordnetes oder mitgeliefertes Profil wird nicht geloescht.
- `whoami` liefert `tool_profile` mit Gruppen und Ausnahmen (§6.1); der Test
  steht hier, nicht in `test_whoami.py`, damit Q2b bei acht Dateien bleibt.
"""

import json
from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from who2be_api.core import rate_limit
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models.tool_profiles import BUILTIN_PROFILES, TOOL_GROUPS, BuiltinProfileKey

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")


@pytest.fixture(autouse=True)
def _no_global_write_limit() -> Iterator[None]:
    # Das slowapi-Schreiblimit ist hier nicht Gegenstand; ein Lauf schreibt
    # mit demselben Admin-Token deutlich mehr als 30 Mal je Minute.
    enabled = rate_limit.limiter.enabled
    rate_limit.limiter.enabled = False
    try:
        yield
    finally:
        rate_limit.limiter.enabled = enabled


class Env:
    def __init__(self, client: TestClient, make_auth: AuthFactory) -> None:
        self.client = client
        self.owner, self.editor, self.viewer = fresh_user_id(), fresh_user_id(), fresh_user_id()
        self.ws = setup_workspace(self.owner)
        for user, role in ((self.editor, "editor"), (self.viewer, "viewer")):
            db_execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3)",
                self.ws,
                user,
                role,
            )
        self.prefix = f"/v1/workspaces/{self.ws}"
        self.admin_h = make_auth(self.owner)
        self.editor_h = make_auth(self.editor)
        self.viewer_h = make_auth(self.viewer)
        agent, self.agent_h = agent_token(
            client, self.prefix, "Q2b-Agent", {}, self.admin_h, role="editor"
        )
        self.agent = UUID(agent)
        builder: UUID = db_fetchval(
            "SELECT id FROM agent WHERE workspace_id = $1 AND is_managed "
            "ORDER BY created_at, id LIMIT 1",
            self.ws,
        )
        self.builder = builder

    def users(self) -> list[UUID]:
        return [self.owner, self.editor, self.viewer]

    def url(self, path: str) -> str:
        return f"{self.prefix}{path}"

    def profiles(self) -> list[dict[str, Any]]:
        res = self.client.get(self.url("/tool-profiles"), headers=self.admin_h)
        assert res.status_code == 200, res.text
        body: list[dict[str, Any]] = res.json()
        return body

    def builtin_id(self, key: BuiltinProfileKey) -> str:
        profile_id: str = next(p["id"] for p in self.profiles() if p["builtin_key"] == key.value)
        return profile_id

    def create(self, name: str, **extra: Any) -> dict[str, Any]:
        res = self.client.post(
            self.url("/tool-profiles"),
            json={"name": name, "groups": ["core", "read"], **extra},
            headers=self.admin_h,
        )
        assert res.status_code == 201, res.text
        body: dict[str, Any] = res.json()
        return body

    def assign(self, agent: UUID, headers: dict[str, str], **body: Any) -> Any:
        return self.client.put(
            self.url(f"/agents/{agent}/tool-profile"), json=body, headers=headers
        )

    def audit(self, action: str) -> int:
        count: int = db_fetchval(
            "SELECT count(*) FROM audit_log WHERE workspace_id = $1 AND action = $2",
            self.ws,
            action,
        )
        return count


@pytest.fixture
def env(make_auth_headers: AuthFactory) -> Iterator[Env]:
    with TestClient(app) as client:
        e = Env(client, make_auth_headers)
        try:
            yield e
        finally:
            cleanup_workspaces(e.users())


def _reason(res: Any, status: int) -> str:
    assert res.status_code == status, res.text
    reason: str = res.json()["reason"]
    return reason


# ------------------------------------------------------------------ Lesen


def test_viewer_liest_profile_und_katalog(env: Env) -> None:
    res = env.client.get(env.url("/tool-profiles"), headers=env.viewer_h)
    assert res.status_code == 200, res.text
    body = res.json()
    # Die vier mitgelieferten Profile in Lieferreihenfolge, Namen nach DE-Workspace.
    assert [p["builtin_key"] for p in body] == [key.value for key in BUILTIN_PROFILES]
    assert [p["name"] for p in body] == ["Lesen", "Autor", "Kurator", "Builder"]
    builder = body[-1]
    assert builder["groups"] == [
        g.value for g in BUILTIN_PROFILES[BuiltinProfileKey.builder].groups
    ]
    assert "workarea_read" in builder["groups"]  # W59-4
    # Der verwaltete Builder haengt am Profil „Builder“ (W59-3 = A).
    assert builder["agent_count"] >= 1

    res = env.client.get(env.url("/tool-profiles/catalog"), headers=env.viewer_h)
    assert res.status_code == 200, res.text
    catalog = res.json()
    assert [g["key"] for g in catalog["groups"]] == [g.value for g in TOOL_GROUPS]
    assert catalog["core_tools"] == ["ping", "whoami", "report_problem"]

    # Agent-Tokens lesen ebenfalls (kein Recht, nur Workspace-Konfiguration).
    assert env.client.get(env.url("/tool-profiles"), headers=env.agent_h).status_code == 200


# ------------------------------------------------------------------ Pflegen (admin)


def test_profile_pflegt_nur_admin(env: Env) -> None:
    body = {"name": "Recherche", "groups": ["core", "read"]}
    for headers in (env.editor_h, env.viewer_h, env.agent_h):
        res = env.client.post(env.url("/tool-profiles"), json=body, headers=headers)
        assert _reason(res, 403) == "insufficient_role"

    created = env.create("Recherche", tools=["read_artifact"], description="Nur lesen")
    assert created["builtin_key"] is None
    assert created["tools"] == ["read_artifact"]
    assert created["agent_count"] == 0
    profile = created["id"]

    update = {"name": "Recherche plus", "groups": ["core", "read", "workarea_read"]}
    for headers in (env.editor_h, env.viewer_h, env.agent_h):
        res = env.client.put(env.url(f"/tool-profiles/{profile}"), json=update, headers=headers)
        assert _reason(res, 403) == "insufficient_role"
        res = env.client.delete(env.url(f"/tool-profiles/{profile}"), headers=headers)
        assert _reason(res, 403) == "insufficient_role"
    reset_target = env.builtin_id(BuiltinProfileKey.read)
    res = env.client.post(env.url(f"/tool-profiles/{reset_target}/reset"), headers=env.editor_h)
    assert _reason(res, 403) == "insufficient_role"

    res = env.client.put(env.url(f"/tool-profiles/{profile}"), json=update, headers=env.admin_h)
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Recherche plus"
    assert res.json()["groups"] == ["core", "read", "workarea_read"]
    assert res.json()["tools"] == []

    assert env.audit("tool_profile.created") == 1
    assert env.audit("tool_profile.updated") == 1


def test_profil_namen_und_katalog_werden_geprueft(env: Env) -> None:
    env.create("Eigenes")
    c = env.client
    # Name je Workspace eindeutig, ohne Gross/Klein.
    res = c.post(env.url("/tool-profiles"), json={"name": "eigenes"}, headers=env.admin_h)
    assert _reason(res, 409) == "tool_profile_name_conflict"
    assert res.json()["params"] == {"name": "eigenes"}

    res = c.post(
        env.url("/tool-profiles"),
        json={"name": "X", "groups": ["gibts_nicht"]},
        headers=env.admin_h,
    )
    assert _reason(res, 422) == "unknown_tool_group"
    assert res.json()["params"] == {"groups": "gibts_nicht"}

    res = c.post(
        env.url("/tool-profiles"), json={"name": "X", "tools": ["gibts_nicht"]}, headers=env.admin_h
    )
    assert _reason(res, 422) == "unknown_tool"
    assert res.json()["params"] == {"tools": "gibts_nicht"}

    res = c.put(env.url(f"/tool-profiles/{uuid4()}"), json={"name": "Neu"}, headers=env.admin_h)
    assert _reason(res, 404) == "tool_profile_not_found"

    # Umbenennen auf den Namen eines anderen Profils.
    builder = env.builtin_id(BuiltinProfileKey.builder)
    res = c.put(env.url(f"/tool-profiles/{builder}"), json={"name": "EIGENES"}, headers=env.admin_h)
    assert _reason(res, 409) == "tool_profile_name_conflict"


def test_mitgeliefertes_profil_anpassen_und_zuruecksetzen(env: Env) -> None:
    c = env.client
    read = env.builtin_id(BuiltinProfileKey.read)
    res = c.put(
        env.url(f"/tool-profiles/{read}"),
        json={"name": "Nur Lesen", "description": "angepasst", "groups": ["core"]},
        headers=env.admin_h,
    )
    assert res.status_code == 200, res.text
    assert res.json()["builtin_key"] == "read"

    res = c.post(env.url(f"/tool-profiles/{read}/reset"), headers=env.admin_h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Lesen"
    assert body["description"] == ""
    assert body["groups"] == [g.value for g in BUILTIN_PROFILES[BuiltinProfileKey.read].groups]
    assert env.audit("tool_profile.reset") == 1

    custom = env.create("Eigenes")["id"]
    res = c.post(env.url(f"/tool-profiles/{custom}/reset"), headers=env.admin_h)
    assert _reason(res, 409) == "tool_profile_not_builtin"
    res = c.post(env.url(f"/tool-profiles/{uuid4()}/reset"), headers=env.admin_h)
    assert _reason(res, 404) == "tool_profile_not_found"


def test_loeschen_nur_eigene_und_freie_profile(env: Env) -> None:
    c = env.client
    builder = env.builtin_id(BuiltinProfileKey.builder)
    res = c.delete(env.url(f"/tool-profiles/{builder}"), headers=env.admin_h)
    assert _reason(res, 409) == "tool_profile_builtin"

    custom = env.create("Eigenes")["id"]
    assert env.assign(env.agent, env.editor_h, tool_profile_id=custom).status_code == 200
    res = c.delete(env.url(f"/tool-profiles/{custom}"), headers=env.admin_h)
    assert _reason(res, 409) == "tool_profile_in_use"
    assert res.json()["params"] == {"agent_count": 1}

    # Zurueck auf „Alle“, dann ist das Profil frei.
    assert env.assign(env.agent, env.editor_h, tool_profile_id=None).status_code == 200
    res = c.delete(env.url(f"/tool-profiles/{custom}"), headers=env.admin_h)
    assert res.status_code == 204, res.text
    assert env.audit("tool_profile.deleted") == 1
    res = c.delete(env.url(f"/tool-profiles/{custom}"), headers=env.admin_h)
    assert _reason(res, 404) == "tool_profile_not_found"


# ------------------------------------------------------------------ Zuordnen (editor, Mensch)


def test_editor_ordnet_zu_und_audit_haelt_alt_und_neu(env: Env) -> None:
    custom = env.create("Eigenes")["id"]
    res = env.assign(
        env.agent,
        env.editor_h,
        tool_profile_id=custom,
        tools_added=["read_artifact"],
        tools_removed=["search"],
    )
    assert res.status_code == 200, res.text
    agent = res.json()
    assert agent["id"] == str(env.agent)
    assert agent["tool_profile_id"] == custom
    assert agent["tools_added"] == ["read_artifact"]
    assert agent["tools_removed"] == ["search"]

    detail = json.loads(
        db_fetchval(
            "SELECT detail::text FROM audit_log WHERE workspace_id = $1 "
            "AND action = 'agent.tool_profile_changed' AND target = $2",
            env.ws,
            str(env.agent),
        )
    )
    assert detail == {
        "old": {"tool_profile_id": None, "tools_added": [], "tools_removed": []},
        "new": {
            "tool_profile_id": custom,
            "tools_added": ["read_artifact"],
            "tools_removed": ["search"],
        },
    }

    # Derselbe Stand noch einmal: kein zweiter Audit-Eintrag.
    again = env.assign(
        env.agent,
        env.editor_h,
        tool_profile_id=custom,
        tools_added=["read_artifact"],
        tools_removed=["search"],
    )
    assert again.status_code == 200, again.text
    assert env.audit("agent.tool_profile_changed") == 1

    # „Alle außer X“: kein Profil, nur Sperre.
    res = env.assign(env.agent, env.editor_h, tools_removed=["search"])
    assert res.status_code == 200, res.text
    assert res.json()["tool_profile_id"] is None


def test_zuordnung_nur_durch_menschen(env: Env) -> None:
    # Der Agent-Token traegt die Rolle editor — die Bindung ist das Hindernis.
    res = env.assign(env.agent, env.agent_h, tool_profile_id=None)
    assert res.status_code == 403, res.text
    assert res.headers["content-type"].startswith("application/problem+json")
    assert res.json()["reason"] == "human_only"
    assert res.json()["actionable_by"] == "human"
    assert "tool_request" in res.json()["detail"]

    res = env.assign(env.agent, env.viewer_h, tool_profile_id=None)
    assert _reason(res, 403) == "insufficient_role"
    assert env.audit("agent.tool_profile_changed") == 0


def test_zuordnung_prueft_eingaben(env: Env) -> None:
    res = env.assign(env.agent, env.editor_h, tools_removed=["whoami", "search", "ping"])
    assert _reason(res, 422) == "core_tool_not_removable"
    assert res.json()["params"] == {"tools": "whoami, ping"}

    res = env.assign(env.agent, env.editor_h, tools_added=["gibts_nicht"])
    assert _reason(res, 422) == "unknown_tool"

    res = env.assign(env.agent, env.editor_h, tool_profile_id=str(uuid4()))
    assert _reason(res, 404) == "tool_profile_not_found"

    res = env.assign(uuid4(), env.editor_h, tool_profile_id=None)
    assert _reason(res, 404) == "agent_not_found"


def test_profil_eines_fremden_workspace_ist_unbekannt(
    env: Env, make_auth_headers: AuthFactory
) -> None:
    other_owner = fresh_user_id()
    other_ws = setup_workspace(other_owner)
    try:
        foreign = db_fetchval(
            "SELECT id FROM tool_profile WHERE workspace_id = $1 AND builtin_key = 'read'",
            other_ws,
        )
        res = env.assign(env.agent, env.editor_h, tool_profile_id=str(foreign))
        assert _reason(res, 404) == "tool_profile_not_found"
        res = env.client.put(
            env.url(f"/tool-profiles/{foreign}"), json={"name": "Fremd"}, headers=env.admin_h
        )
        assert _reason(res, 404) == "tool_profile_not_found"
    finally:
        cleanup_workspaces([other_owner])


def test_verwalteter_builder_laesst_sich_zuordnen(env: Env) -> None:
    builder_profile = env.builtin_id(BuiltinProfileKey.builder)
    before = env.client.get(env.url(f"/agents/{env.builder}"), headers=env.editor_h)
    assert before.status_code == 200, before.text
    assert before.json()["is_managed"] is True
    assert before.json()["tool_profile_id"] == builder_profile

    # W59-3: ein Mensch stellt den Builder auf „Alle“ zurueck — trotz Builder-Lock.
    res = env.assign(env.builder, env.editor_h, tool_profile_id=None)
    assert res.status_code == 200, res.text
    assert res.json()["tool_profile_id"] is None
    assert res.json()["is_managed"] is True

    # Und wieder auf „Builder“ mit freigegebenem Werkzeug (P3a).
    res = env.assign(
        env.builder, env.editor_h, tool_profile_id=builder_profile, tools_added=["create_artifact"]
    )
    assert res.status_code == 200, res.text
    assert res.json()["tools_added"] == ["create_artifact"]


# ------------------------------------------------------------------ whoami (§6.1)


def test_whoami_liefert_das_profil(env: Env) -> None:
    """`whoami.tool_profile`: Gruppen und Ausnahmen, nie die ausgerechnete Liste.

    Hier statt in `test_whoami.py`, damit Q2b bei acht Dateien bleibt
    (ADR-0059 §10). Der verwaltete Builder steht auf „Builder“ (W59-3 = A,
    inkl. `workarea_read` nach W59-4). Auf „Alle“ liefert `whoami` `None`,
    „Alle“ mit Sperre `id=None` und nur die Ausnahme. Menschen haben kein Profil.
    """
    c = env.client
    token = c.post(
        env.url("/tokens"), json={"name": "mcp", "agent_id": str(env.builder)}, headers=env.admin_h
    )
    assert token.status_code == 201, token.text
    builder_h = {"Authorization": f"Bearer {token.json()['token']}"}

    def grant(headers: dict[str, str]) -> Any:
        res = c.get(env.url("/whoami"), headers=headers)
        assert res.status_code == 200, res.text
        return res.json()["tool_profile"]

    current = grant(builder_h)
    assert current == {
        "id": env.builtin_id(BuiltinProfileKey.builder),
        "name": "Builder",
        "groups": [g.value for g in BUILTIN_PROFILES[BuiltinProfileKey.builder].groups],
        "tools": [],
        "tools_added": [],
        "tools_removed": [],
    }
    assert "workarea_read" in current["groups"]

    # Menschen und Agenten auf „Alle“ ohne Ausnahmen: keine Einschraenkung.
    assert grant(env.admin_h) is None
    assert grant(env.agent_h) is None

    assert env.assign(env.builder, env.editor_h, tool_profile_id=None).status_code == 200
    assert grant(builder_h) is None

    res = env.assign(env.builder, env.editor_h, tools_removed=["search"])
    assert res.status_code == 200, res.text
    assert grant(builder_h) == {
        "id": None,
        "name": "",
        "groups": [],
        "tools": [],
        "tools_added": [],
        "tools_removed": ["search"],
    }
