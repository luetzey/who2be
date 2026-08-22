# Plan — Consent: gelockten Agenten verständlich ausweisen (#405)

_Erstellt: 2026-08-22 16:00 · Branch: `claude/amazing-bardeen-u3gwoj` (neu ab `main`)_

## Befund (aus dem Security-Review zu #404, verifiziert)

`OAuthConsentPage` lädt die Agentenliste ausschließlich für
`me.default_workspace_id` (`OAuthConsentPage.tsx:40,48`). Das serverseitige Gate
`_resolve_agent_membership` (`oauth_service.py:233-253`) sucht dagegen über
**alle** Memberships des Users. Liegt der per Hard-Lock gebundene Agent in einem
Nicht-Default-Workspace, laufen zwei Pfade schief:

1. **Rohe UUID.** `lockedAgent?.name ?? lockedAgentId` (Zeile 136) fällt auf die
   UUID zurück — der User bestätigt eine Bindung, die er nicht lesen kann. Der
   Workspace wird nirgends genannt.
2. **Zweite Facette, im Review nicht erwähnt:** Hat der Default-Workspace *gar
   keine* Agenten, greift `agents.length === 0` (Zeile 122) und die Karte zeigt
   „Keine Agenten in diesem Workspace" — **ohne Buttons**. Der Consent ist dann
   nicht nur unklar, sondern schlicht nicht durchführbar, obwohl der Agent
   existiert und der User berechtigt ist.

Dazu bleibt der Approve-Button aktiv, auch wenn der gelockte Agent gar nicht
auflösbar ist (`disabled={submitting || selectedAgentId === ''}`, Zeile 166) —
der Server antwortet dann mit 403, der User sieht nur „Autorisierung
fehlgeschlagen".

**Warum jetzt:** Vor #406 kam der Agent-Hint praktisch nie am Consent an, der
Hard-Lock war ein toter Pfad. Seit der Pfad-Bindung ist er der Normalfall.

**Einordnung:** Consent-Klarheit, keine Rechteausweitung. Die Rolle im
ausgestellten Token ist die eigene Membership-Rolle des Users im Ziel-Workspace,
`redirect_uri` bleibt gewhitelistet, der Ziel-Host wird angezeigt.

## Design-Weiche — woher kommen Agent-Name und Workspace?

### Option A — Auflösung über den signierten Blob (Empfehlung)

Neuer Endpunkt auf der bestehenden OAuth-Fläche, z. B.
`POST /oauth/consent/preview`: nimmt denselben HMAC-signierten Request-Blob,
löst den Agenten über **exakt** `_resolve_agent_membership` auf und liefert
Agent-Name + Workspace-Name — oder ein klares „nicht auflösbar".

- Pro: autoritativ — dieselbe Funktion, die später über Erfolg/403 entscheidet;
  eine Anfrage; **keine neue Lesefläche**: der Endpunkt verrät nur, was der User
  ohnehin gerade autorisieren soll, und der Trust-Anker bleibt der signierte
  Blob (kein Agent-ID-Parameter ⇒ kein IDOR-Vektor).
- Contra: ein Endpunkt mehr; `/oauth/*` ist bereits nicht workspace-scoped, also
  kein Bruch mit der `/v1/workspaces/{ws_id}/…`-Regel, aber es ist Backend-Arbeit
  und damit sicherheitsrelevant (Review nötig).

### Option B — `GET /v1/me/agents` (workspace-übergreifende Agentenliste)

- Pro: auch anderswo nützlich; rein additiv.
- Contra: legt eine **allgemeine** workspace-übergreifende Lesefläche an, wo das
  Problem nur einen einzigen, ohnehin bekannten Agenten braucht. Mehr Angriffs-
  und Pflegefläche als die Aufgabe rechtfertigt.

### Option C — rein im Frontend

`MeRead` trägt bereits **alle** Workspaces des Users samt Namen
(`me.organizations[].workspaces[]`). Die Consent-Seite könnte den gelockten
Agenten in den übrigen Workspaces nachladen, wenn er im Default fehlt.

- Pro: keine Backend-Änderung, kein Review-Bedarf, nutzt vorhandene Daten.
- Contra: dupliziert die Auflösungslogik im Client und kann von
  `_resolve_agent_membership` abweichen (dort greift `tenant_scope`/RLS); bis zu
  N Requests; und die Anzeige wäre eine *Vermutung* über das, was der Server
  gleich entscheidet, statt seiner Antwort.

**Empfehlung: A.** Der Consent ist der Moment, in dem ein User eine
Sicherheitsentscheidung trifft — was dort steht, sollte aus derselben Quelle
kommen, die die Entscheidung durchsetzt, nicht aus einer Rekonstruktion daneben.

## Arbeitspakete (bei Zustimmung zu A)

### WP1 — Backend: Consent-Preview (sicherheitsrelevant → `security-reviewer`)
`services/oauth_service.py` (Preview-Methode auf Basis von
`_resolve_agent_membership`), `routers/oauth.py` (Endpunkt),
`packages/models/oauth.py` (Request-/Response-Modell).
Verhalten: kein Hint im Blob ⇒ „kein Lock" (Frontend zeigt die Auswahl wie
bisher); Hint vorhanden und auflösbar ⇒ Name + Workspace; Hint vorhanden, aber
in keinem Workspace des Users ⇒ explizit „nicht auflösbar", **kein** 403 (der
Consent ist noch nicht abgeschickt — es ist eine Anzeige, kein Versuch).
Rate-Limit wie bei den übrigen OAuth-Endpunkten.
Tests: `apps/api/tests/test_oauth.py` — alle drei Fälle, plus manipulierter Blob
⇒ Signaturfehler.

### WP2 — Web: Consent zeigt Name + Workspace, sperrt bei Unauflösbarkeit
`features/auth/pages/OAuthConsentPage.tsx`, i18n `de.json`/`en.json`.
Beim Hard-Lock die Preview ziehen statt die Workspace-Agentenliste zu
durchsuchen; Name + Workspace anzeigen; bei „nicht auflösbar" den
Approve-Button sperren und den Grund nennen. Die `agents.length === 0`-Sperre
darf den Lock-Fall **nicht** mehr blockieren (Facette 2).
Tests: gelockt + auflösbar, gelockt + fremder Workspace (Sperre + Meldung),
ungelockt (Dropdown wie bisher).

### WP3 — Doku
ADR-0036-Addendum (Consent-Preview), CHANGELOG, STATE.

## DoD
- Python: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`,
  `uv run pytest -q`
- Web: `npm run lint`, `npx tsc -b`, `npm run test:coverage`, `npm run build`
- `security-reviewer` über WP1 gelaufen, Befunde behoben.
- Draft-PR.

## Anti-Scope
- Keine Änderung an der Hard-Lock-Semantik oder am autoritativen Gate.
- Kein workspace-übergreifender Agent-Katalog (Option B).
- Kein Workspace-Wechsel im Consent — der Agent bleibt durch die URL bestimmt.

## Entscheidung (User, 2026-08-22): Option A

### Vertrag zwischen WP1 und WP2 (vorab festgelegt, damit beide parallel laufen)

`POST /oauth/consent/preview` — eingeloggter User (JWT), Rate-Limit wie die
übrigen OAuth-Endpunkte.

**Request:** `{ "request": "<signierter Blob>" }`

**Response `OAuthConsentPreview`:**

```jsonc
{
  "locked": true,                 // trägt der Blob einen Agent-Hint?
  "agent": {                      // null ⇒ nicht auflösbar (bei locked=false immer null)
    "id": "…",
    "name": "Coder",
    "workspace_id": "…",
    "workspace_name": "Who2Be"
  }
}
```

**Vier Fälle:**

| Blob | Antwort | Frontend |
| --- | --- | --- |
| Signatur ungültig / abgelaufen | `400` (`OAuthError`) | Fehlermeldung, kein Consent möglich |
| kein Agent-Hint | `{locked: false, agent: null}` | Dropdown wie bisher |
| Hint, in einem Workspace des Users | `{locked: true, agent: {…}}` | Name + Workspace, Approve aktiv |
| Hint, in keinem Workspace des Users | `{locked: true, agent: null}` | Grund nennen, Approve gesperrt |

Der vierte Fall ist bewusst **kein 403**: der Consent wurde noch nicht
abgeschickt, es ist eine Anzeige, kein Autorisierungsversuch. Das 403 bleibt am
`POST /oauth/consent`, wo die Entscheidung tatsächlich fällt.

`client_name` und Redirect-Host liest das Frontend weiterhin selbst aus dem
Blob (dokumentiert als reine UI-Vorschau) — die Preview dupliziert sie nicht.

---

# Übergabe-Bericht (2026-08-22, vor dem PR)

## (a) Betroffene Software-Elemente

Ripgrep-Rückwärtssuche über `apps/` und `packages/`, nicht aus dem Kontextfenster.

**DIREKT:**

| Symbol | Aufrufer |
| --- | --- |
| `consent_preview` (Service) | `routers/oauth.py:199` |
| `get_consent_principal` / `ConsentPrincipal` | `routers/oauth.py:168` (`consent`) **und** `:188` (`consent/preview`) |
| `PgOAuthRepository.agent_display` | `oauth_service._agent_display` — einziger Aufrufer |
| `oauthConsentPreview` (Web) | `OAuthConsentPage.tsx:66` |
| `OAuthConsentApprove.agent_id` (jetzt optional) | `routers/oauth.py:175` → `consent()` |

**TRANSITIV:** Jeder Consent-Durchlauf — also jedes Verbinden eines
MCP-Connectors. `OAuthConsentPage` hängt jetzt an zwei Effekten statt einem;
`listAgents` wird im Lock-Fall nicht mehr aufgerufen.

**VERMUTET — ausdrücklich unsicher:** Der Auth-Fix ändert das Verhalten eines
**bestehenden** Endpunkts (`POST /oauth/consent` weist `w2b_`-Tokens jetzt mit
401 ab). Statisch ist kein Aufrufer erkennbar, der das täte — der Consent ist
eine Browser-Seite mit Supabase-JWT. Ein externes Skript oder ein Integrationsweg
außerhalb dieses Repos, der maschinell consentet, würde brechen. Genau dieser
Weg war die Lücke; der Bruch wäre gewollt, sollte aber bekannt sein.

## (b) Rest-Test-Liste

**Diff-Coverage:** Erstmals in dieser Session mit echter DB gemessen (PostgreSQL
16 + pgvector im Container): **1741 passed, 0 skipped**, Gesamt-Coverage
**91,21 %** — `Required test coverage of 85% reached`. Web: **1011 Tests / 180
Dateien**, Branches 80,99 % (Floor 79).

Abgedeckt: alle vier Preview-Fälle DB-frei, Existenz-Orakel-Vergleich
byte-genau, manipulierter/abgelaufener Blob, `w2b_`-Token gegen beide
Consent-Endpunkte (der Regressionstest schlägt gegen den alten Code fehl —
mit entschärftem Guard liefert der alte Pfad weiterhin 200 + Auth-Code), die
drei `agent_id`-Fälle, sowie die drei Web-Zustände (gelockt auflösbar, gelockt
unauflösbar, ungelockt) inkl. „`listAgents` wird im Lock-Fall nicht gerufen".

**Von keinem Test abgedeckt:**

- Der reale Consent gegen einen echten LLM-Client mit einem Agenten aus einem
  **Nicht-Default-Workspace**. **Manuell zu prüfen:** Connector-URL eines
  Agenten aus einem zweiten Workspace verbinden — es muss Name + Workspace
  erscheinen und der Consent durchlaufen, auch wenn der Default-Workspace leer
  ist.
- Der `access_denied`-Redirect beim Ablehnen im Fall „gelockt, nicht auflösbar"
  ist serverseitig getestet, aber nicht end-to-end gegen einen echten Client.
- Ob irgendwo außerhalb dieses Repos ein maschineller Consent existiert, der
  jetzt 401 bekommt (siehe VERMUTET oben) — nur durch Betrieb feststellbar.

Verhaltens-neutral und deshalb nicht gelistet: Docstrings, Kommentare, i18n,
der Repository-Umzug von `_agent_display` (reiner Struktur-Umzug, identische
Testzahlen).

## (c) Security-Review

`security-reviewer` über das Paket gelaufen. Kernansprüche bestätigt: kein
Existenz-Orakel (auch nicht über Timing — identische Round-Trip-Zahl in beiden
stummen Fällen, Rest-Unterschied bei SNR ~1:1000 nicht nutzbar), kein IDOR über
selbst beschaffte Blobs, `tenant_scope` korrekt platziert und für die ganze
Query wirksam, kein Leak über den `JOIN workspace`, kein XSS, Hard-Lock und
Audience-Kette unverändert.

Drei Befunde, alle behoben:

- **HOCH, vorbestehend** — `/oauth/consent` akzeptierte `w2b_`-Tokens ⇒
  Privilege Escalation (`viewer` → `admin`, plus Workspace-/Policy-Pin-Escape,
  plus revocation-resistente Refresh-Kette). Selbst am Code verifiziert.
- **MITTEL, neu** — der Preview ignorierte denselben Token-Pin. Gleicher Fix.
- **NIEDRIG, neu** — „Ablehnen" scheiterte an 422, weil `agent_id` Pflicht war.

Zwei Hinweise bewusst offengelassen: der Preview schreibt keinen Audit-Eintrag
(reiner Read; ein `w2b_`-Token am Consent ist jetzt aber ein starker
Missbrauchs-Indikator und wäre ein sinnvolles Signal), und zwei kleine
Divergenzen zwischen Preview und autoritativem Pfad (nicht-kanonische UUID,
`resource`-Prüfung) — beide folgenlos, im Docstring vermerkt.
