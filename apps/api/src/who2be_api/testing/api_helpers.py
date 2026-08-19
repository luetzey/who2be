"""Geteilte Test-Helfer fuer die Integrationstests der API.

Der Platz neben `workspace_setup` ist bewusst: das `testing`-Paket ist im
Repo schon die Heimat der Test-Helfer, wird nur von Tests importiert und
ist fuer mypy UND pytest aufloesbar — ein Modul im Test-Ordner waere es
nur fuer pytest.

Warum ein Modul und keine Fixtures: diese Helfer brauchen den `TestClient`,
den jeder Test selbst als Kontextmanager aufmacht (`with TestClient(app) as
client`). Eine Fixture koennte ihn nicht einfangen — sie muesste ihn ohnehin
als Parameter nehmen und waere dann nur eine Funktion mit Umweg. Der zentrale
`conftest.py` bleibt zustaendig fuer das, was echtes Setup braucht
(JWT-Secret, Migrationen, Auth-Header-Factory).

Anlass (2026-08-19): `_agent_token` lag in **15 Testdateien** vor, in **fuenf
verschiedenen Fassungen** — mit und ohne `role`, `prefix` vs. `base_prefix`,
zwei davon gaben nur die Header statt `(agent_id, headers)` zurueck. Jede
Kopie war fuer ihren Testfall plausibel; in Summe gab es keine gemeinsame
Wahrheit mehr darueber, wie ein Agent-Token im Test entsteht. Der
`conftest.py` haelt die Regel seit dem TST-10-Audit fest — „der Bestand wird
inkrementell abgebaut, nicht vermehrt"; hier wird sie eingeloest.

Die Helfer `assert`en ihre eigenen Vorbedingungen (201 beim Anlegen): schlaegt
das Setup fehl, soll der Test dort scheitern und nicht erst spaeter an einer
verwirrenden Stelle.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings


def agent_token(
    client: TestClient,
    prefix: str,
    name: str,
    policy: dict[str, object],
    auth: dict[str, str],
    *,
    role: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Legt einen Agenten an und bindet einen Token daran.

    Rueckgabe ist IMMER `(agent_id, headers)` — die ID braucht man fuer
    Grants, die Header fuer den Aufruf. `role` pinnt die Rolle am Token
    (Default: die des anlegenden Menschen).
    """
    agent = client.post(
        f"{prefix}/agents", json={"name": name, "tool_policy": policy}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    agent_id: str = agent.json()["id"]
    body: dict[str, object] = {"name": name, "agent_id": agent_id}
    if role is not None:
        body["role"] = role
    token = client.post(f"{prefix}/tokens", json=body, headers=auth)
    assert token.status_code == 201, token.text
    return agent_id, {"Authorization": f"Bearer {token.json()['token']}"}


def shared_area(client: TestClient, prefix: str, auth: dict[str, str], name: str) -> str:
    """Legt eine SHARED WorkArea an und liefert ihre ID."""
    created = client.post(f"{prefix}/work-areas", json={"name": name}, headers=auth)
    assert created.status_code == 201, created.text
    area_id: str = created.json()["id"]
    return area_id


def grant(
    client: TestClient, prefix: str, auth: dict[str, str], area_id: str, agent_id: str, level: str
) -> None:
    """Setzt den Area-Grant eines Agenten (`read` | `write`)."""
    res = client.put(
        f"{prefix}/work-areas/{area_id}/grants/{agent_id}", json={"level": level}, headers=auth
    )
    assert res.status_code == 200, res.text


def db_fetchval(sql: str, *args: object) -> Any:
    """Direkter DB-Read fuer Zustands-Assertions (Superuser, an RLS vorbei).

    Bewusst OHNE jsonb-Codec: die Connection liefert genau das, was in der
    Spalte steht — nur so lassen sich Kodierungs-Fragen ueberhaupt pruefen
    (s. `test_jsonb_bindings`).
    """

    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def db_execute(sql: str, *args: object) -> None:
    """Direkter DB-Write — stellt Altbestand nach bzw. faehrt eine Migration."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    asyncio.run(_run())
