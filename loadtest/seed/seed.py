#!/usr/bin/env python3
"""Seed fuer die Belastungstest-Suite: nur synthetische Daten (ADR-0062, W6).

Legt ueber die oeffentliche API Organisationen, Workspaces, eine aktive Persona,
aktive Playbooks und Resources, je Workspace einen Agenten mit agent-gebundenen
`w2b_`-Tokens sowie Redakteurs-JWTs an und schreibt alles, was die k6-Szenarien
brauchen, in eine JSON-Datei (`--out`). Keine Prod-Kopie, keine echten Personen:
Namen und Texte entstehen aus einem festen Vokabular.

Stdlib-only (wie `scripts/gen_test_jwt.py`), damit es auf dem Lastgenerator ohne
uv laeuft.

Anmeldung: In der Cloud gibt es nur OAuth, das laesst sich nicht belasten. Das
Skript signiert deshalb Test-JWTs mit dem `JWT_SECRET` der TESTUMGEBUNG
(Bericht §4.2). Jeder Aufruf traegt ein eigenes JWT (`session_id` je Token):
so faellt der Seed nicht in das Schreiblimit je Token. Das geht nur mit dem
Test-Secret; gegen eine Umgebung mit unbekanntem Secret schlaegt schon der
erste Aufruf mit 401 fehl.

Schutz: Abbruch, wenn `--api-url` auf who2be.de zeigt oder
`W2B_LOADTEST_CONFIRM=synthetic-non-production` fehlt (dieselbe Regel wie
`loadtest/lib/common.js`).

Beispiele:
    W2B_LOADTEST_CONFIRM=synthetic-non-production JWT_SECRET=... \\
        python3 loadtest/seed/seed.py --api-url http://localhost:8000 \\
        --profile smoke --out loadtest/results.local/seed.json
    python3 loadtest/seed/seed.py owners --run-id lt1 --profile full
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

PRODUCTION_DOMAIN = "who2be.de"
CONFIRM_VALUE = "synthetic-non-production"
SEED_MARKER = "who2be-loadtest-seed"
# Fester Namensraum: dieselbe `--run-id` ergibt dieselben Besitzer-UUIDs. Das
# braucht der Pro-Override in der Cloud-Testumgebung (Allowlist vorab setzen).
OWNER_NAMESPACE = uuid.UUID("6f1d6c52-5d0e-4c1f-9a51-3b8c2a7e9d10")

# Gleiches Vokabular wie loadtest/lib/common.js: die Suche trifft Inhalte.
VOCABULARY = [
    "ablauf", "agent", "analyse", "angebot", "antwort", "archiv", "aufgabe", "bericht",
    "checkliste", "daten", "dokument", "entwurf", "freigabe", "gespraech", "hinweis", "kunde",
    "leitfaden", "meldung", "notiz", "pruefung", "qualitaet", "regel", "schritt", "termin",
    "uebergabe", "version", "vorlage", "werkzeug", "zusammenfassung", "ziel",
]  # fmt: skip


@dataclass(frozen=True)
class Profile:
    orgs: int
    workspaces_per_org: int
    playbooks: int
    resources: int
    editors: int
    agent_tokens: int


# `full` entspricht Bericht §4.2: 5 Orgs, 50 Workspaces, 2 000 Playbooks und
# 2 000 Resources, 200 Agent-Tokens.
PROFILES = {
    "smoke": Profile(1, 1, 8, 8, 2, 2),
    "full": Profile(5, 10, 40, 40, 4, 4),
}


class SeedError(RuntimeError):
    pass


# --- Prod-Schutz --------------------------------------------------------------


def host_of(url: str) -> str | None:
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return parsed.hostname.lower().rstrip(".")


def unsafe_target_reasons(api_url: str, confirm: str | None) -> list[str]:
    reasons = []
    if confirm != CONFIRM_VALUE:
        reasons.append(f"W2B_LOADTEST_CONFIRM ist nicht gesetzt (erwartet: {CONFIRM_VALUE}).")
    host = host_of(api_url)
    if host is None:
        reasons.append(f"--api-url ist keine http(s)-URL: {api_url}")
    elif host == PRODUCTION_DOMAIN or host.endswith(f".{PRODUCTION_DOMAIN}"):
        reasons.append(f"--api-url zeigt auf die Produktion ({host}). Nie gegen Prod seeden.")
    return reasons


# --- JWT ----------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_jwt(secret: str, sub: str, ttl: int) -> str:
    """HS256-JWT wie `scripts/gen_test_jwt.py`, plus `aal2` und eigene Session-Id.

    `aal2` erspart dem Seed den TOTP-Weg fuer Admin-Aktionen; er ist nur mit dem
    Test-Secret moeglich. `session_id` macht jedes Token eindeutig.
    """
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "role": "authenticated",
        "aal": "aal2",
        "session_id": str(uuid.uuid4()),
        "email": f"lt-{sub[:8]}@loadtest.who2be.dev",
        "iat": now,
        "exp": now + ttl,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}."
        f"{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    )
    sig = hmac.new(secret.encode(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


# --- API ----------------------------------------------------------------------


class Api:
    def __init__(self, base_url: str, secret: str, ttl: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.ttl = ttl
        self.requests = 0

    def call(self, method: str, path: str, sub: str, body: Any = None) -> Any:
        """Ein Aufruf mit frischem JWT; wiederholt bei 429/503 mit Backoff."""
        data = None if body is None else json.dumps(body).encode()
        for attempt in range(6):
            request = urllib.request.Request(
                f"{self.base_url}{path}",
                data=data,
                method=method,
                headers={
                    "Authorization": f"Bearer {sign_jwt(self.secret, sub, 300)}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            self.requests += 1
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:500]
                if exc.code in (429, 503) and attempt < 5:
                    time.sleep(2**attempt)
                    continue
                raise SeedError(f"{method} {path} -> {exc.code}: {detail}") from exc
        raise SeedError(f"{method} {path}: Wiederholungen erschoepft")


# --- Synthetische Inhalte -----------------------------------------------------


def words(rng: random.Random, count: int) -> str:
    return " ".join(rng.choice(VOCABULARY) for _ in range(count))


def blocks(rng: random.Random, prefix: str, paragraphs: int) -> list[dict[str, Any]]:
    """BlockNote-Bloecke: abwechselnd Ueberschrift und Absatz (Anker fuer block_ids)."""
    result: list[dict[str, Any]] = []
    for i in range(paragraphs):
        if i % 3 == 0:
            result.append(
                {
                    "id": f"{prefix}-h{i}",
                    "type": "heading",
                    "props": {"level": 2},
                    "content": [{"type": "text", "text": words(rng, 4).title(), "styles": {}}],
                    "children": [],
                }
            )
        result.append(
            {
                "id": f"{prefix}-p{i}",
                "type": "paragraph",
                "props": {},
                "content": [{"type": "text", "text": words(rng, 60), "styles": {}}],
                "children": [],
            }
        )
    return result


def activate(api: Api, sub: str, base: str, kind: str, entity_id: str, version: int) -> None:
    for target in ("review", "active"):
        api.call(
            "POST",
            f"{base}/{kind}/{entity_id}/versions/{version}/transition",
            sub,
            {"to": target},
        )


def seed_playbook(api: Api, sub: str, base: str, rng: random.Random, name: str) -> str:
    prefix = f"pb{rng.randrange(10**9)}"
    created = api.call(
        "POST",
        f"{base}/playbooks",
        sub,
        {
            "name": name,
            "content": {
                "description": words(rng, 18),
                # ca. 3-4 KB je Playbook: realistische Prozedur-Groesse
                "body": json.dumps(blocks(rng, prefix, 6)),
                "type": "workflow",
                "tags": ["loadtest", rng.choice(VOCABULARY)],
                "triggers": f"{words(rng, 2)}, {words(rng, 2)}",
            },
        },
    )
    activate(api, sub, base, "playbooks", created["id"], created["current_version"])
    return str(created["id"])


def seed_resource(api: Api, sub: str, base: str, rng: random.Random, name: str) -> str:
    created = api.call(
        "POST",
        f"{base}/resources",
        sub,
        {
            "name": name,
            "content": {
                "description": words(rng, 18),
                "blocks": blocks(rng, f"rs{rng.randrange(10**9)}", 9),
                "tags": ["loadtest", rng.choice(VOCABULARY)],
            },
        },
    )
    activate(api, sub, base, "resources", created["id"], created["current_version"])
    return str(created["id"])


def seed_workspace(
    api: Api, owner: str, ws_id: str, profile: Profile, rng: random.Random, pool: ThreadPoolExecutor
) -> dict[str, Any]:
    base = f"/v1/workspaces/{ws_id}"
    label = ws_id[:8]
    playbook_ids = list(
        pool.map(
            lambda i: seed_playbook(api, owner, base, random.Random(f"{ws_id}-pb-{i}"),
                                    f"LT Playbook {label} {i:03d}"),
            range(profile.playbooks),
        )
    )  # fmt: skip
    resource_ids = list(
        pool.map(
            lambda i: seed_resource(api, owner, base, random.Random(f"{ws_id}-rs-{i}"),
                                    f"LT Resource {label} {i:03d}"),
            range(profile.resources),
        )
    )  # fmt: skip
    persona = api.call(
        "POST",
        f"{base}/personas",
        owner,
        {
            "name": f"LT Persona {label}",
            "content": {
                "description": words(rng, 18),
                "content": {"description": words(rng, 10), "blocks": blocks(rng, "ps", 6)},
                "tags": ["loadtest"],
            },
        },
    )
    activate(api, owner, base, "personas", persona["id"], persona["current_version"])
    api.call(
        "PUT",
        f"{base}/personas/{persona['id']}/playbooks",
        owner,
        {"playbook_ids": playbook_ids[: min(20, len(playbook_ids))]},
    )
    agent = api.call(
        "POST",
        f"{base}/agents",
        owner,
        {
            "name": f"LT Agent {label}",
            "persona_id": persona["id"],
            # Lesen im ganzen Workspace: der Lasttest misst Kapazitaet, nicht
            # die Zuordnung. Ingest (T6) braucht workarea_write.
            "tool_policy": {
                "playbook_read": "all",
                "resource_read": "all",
                "workarea_write": True,
            },
        },
    )
    agent_tokens = [
        api.call(
            "POST",
            f"{base}/tokens",
            owner,
            {"name": f"lt-agent-{i}", "agent_id": agent["id"]},
        )["token"]
        for i in range(profile.agent_tokens)
    ]
    # Redakteure: je einer ein eigenes Playbook und ein eigenes JWT (Sub des
    # Besitzers, aber eigene Session) — das Schreiblimit gilt je Token.
    editors = []
    for i in range(profile.editors):
        playbook_id = seed_playbook(
            api, owner, base, random.Random(f"{ws_id}-ed-{i}"), f"LT Redaktion {label} {i:02d}"
        )
        editors.append({"jwt": sign_jwt(api.secret, owner, api.ttl), "playbook_id": playbook_id})
    return {
        "id": ws_id,
        "org_owner": owner,
        "persona_id": persona["id"],
        "agent_id": agent["id"],
        "playbook_ids": playbook_ids,
        "resource_ids": resource_ids,
        "agent_tokens": agent_tokens,
        "editors": editors,
    }


def owner_ids(run_id: str, profile: Profile) -> list[str]:
    return [str(uuid.uuid5(OWNER_NAMESPACE, f"{run_id}:owner:{i}")) for i in range(profile.orgs)]


def seed(args: argparse.Namespace) -> dict[str, Any]:
    profile = PROFILES[args.profile]
    api = Api(args.api_url, args.secret, args.ttl_hours * 3600)
    workspaces: list[dict[str, Any]] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        for org_index, owner in enumerate(owner_ids(args.run_id, profile)):
            rng = random.Random(f"{args.run_id}-{org_index}")
            # Erster /v1/me-Aufruf legt Personal-Org + Workspace an (lazy seed).
            api.call("GET", "/v1/me", owner)
            slug = f"lt-{args.run_id}-{org_index}"
            org = api.call(
                "POST",
                "/v1/organizations",
                owner,
                {"name": f"LT Org {args.run_id} {org_index}", "slug": slug},
            )
            ws_ids = [str(ws["id"]) for ws in api.call(
                "GET", f"/v1/organizations/{org['id']}/workspaces", owner)]  # fmt: skip
            for ws_index in range(len(ws_ids), profile.workspaces_per_org):
                created = api.call(
                    "POST",
                    f"/v1/organizations/{org['id']}/workspaces",
                    owner,
                    {"name": f"LT WS {ws_index:02d}", "slug": f"lt-ws-{ws_index:02d}"},
                )
                ws_ids.append(str(created["id"]))
            for ws_id in ws_ids[: profile.workspaces_per_org]:
                if args.pro_override:
                    api.call(
                        "POST",
                        f"/v1/workspaces/{ws_id}/billing/override",
                        owner,
                        {"plan": "pro", "days": 2, "reason": "Belastungstest, synthetische Daten"},
                    )
                workspaces.append(seed_workspace(api, owner, ws_id, profile, rng, pool))
                print(f"  Workspace {len(workspaces)} fertig ({api.requests} Aufrufe)", flush=True)
    return {
        "generator": SEED_MARKER,
        "synthetic": True,
        "run_id": args.run_id,
        "profile": args.profile,
        "api_url": api.base_url,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed_seconds": round(time.monotonic() - started, 1),
        "seed_requests": api.requests,
        "workspaces": workspaces,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthetische Seed-Daten fuer loadtest/.")
    parser.add_argument("command", nargs="?", default="seed", choices=("seed", "owners"))
    parser.add_argument("--api-url", default=os.environ.get("BASE_URL", ""))
    parser.add_argument("--secret", default=os.environ.get("JWT_SECRET", ""))
    parser.add_argument("--profile", default="smoke", choices=sorted(PROFILES))
    parser.add_argument("--run-id", default=time.strftime("%Y%m%d%H%M"))
    parser.add_argument("--out", default="loadtest/results.local/seed.json")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--ttl-hours", type=int, default=12)
    parser.add_argument(
        "--pro-override",
        action="store_true",
        help="Cloud-Testumgebung: jeden Workspace per Betreiber-Override auf Pro heben "
        "(Besitzer-UUIDs vorher mit `owners` in WHO2BE_BILLING_OVERRIDE_OPERATORS setzen).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "owners":
        print(",".join(owner_ids(args.run_id, PROFILES[args.profile])))
        return 0
    reasons = unsafe_target_reasons(args.api_url, os.environ.get("W2B_LOADTEST_CONFIRM"))
    if not args.secret:
        reasons.append("JWT-Secret der Testumgebung fehlt (--secret oder $JWT_SECRET).")
    if reasons:
        print("Seed abgebrochen:\n- " + "\n- ".join(reasons), file=sys.stderr)
        return 2
    try:
        result = seed(args)
    except SeedError as exc:
        print(f"Seed fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    # Die Datei enthaelt gueltige Test-Tokens: nur fuer den Besitzer lesbar,
    # schon beim Anlegen (kein Fenster mit 0644).
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)
    os.chmod(args.out, 0o600)
    count = len(result["workspaces"])
    print(f"Seed fertig: {count} Workspaces, {result['seed_requests']} Aufrufe -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
