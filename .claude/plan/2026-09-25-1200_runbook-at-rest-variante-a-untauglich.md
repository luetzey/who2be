# RUNBOOK: falsche At-Rest-Aussage entfernen, Firewall-Ebene richtigstellen

Karte: `t_87ed8580` (W8/M5+M1). Basis: `origin/main` @ `53c4b854`.

## 1 — Eigene Verifikation der beiden Befunde

**Befund 1 — At-Rest (bestaetigt).** `deploy/hetzner/RUNBOOK.md:702` behauptet:
„Hetzner Cloud Volumes werden serverseitig at-Rest verschluesselt (LUKS auf der
Plattform-Ebene)." Hetzners eigene TOMs sagen das Gegenteil, woertlich:

> | Encryption of Data (at rest) | Client’s responsibility |

Quelle: Hetzner Docs, „Technical and Organizational Measures", Abschnitt
*Confidentiality*, ID GE-68A66, „Last change on 2025-04-01" —
<https://docs.hetzner.com/general/security-and-identify/technical-and-organizational-measures/>,
abgerufen 2026-09-25. Dieselbe Tabelle ordnet Dedicated- und Cloud-Server
ausdruecklich dem Kunden zu („You/the Client are completely responsible for the
management, maintenance and security of the server"); die einzige
Server-seitige Ausnahme betrifft *Backups* bei **Managed Servers**, nicht
Cloud Volumes.

⇒ Variante A hat keinen tragfaehigen Nachweis. Die dort geforderte
„Encryption-Eigenschaft in der Hetzner-Console" existiert fuer Cloud Volumes
nicht — der Leser sucht einen Beleg, den es nicht gibt, und startet im Zweifel
unverschluesselt.

**Befund 2 — Firewall (bestaetigt).** `RUNBOOK.md:89-91` fuehrt die
Cloud-Firewall als „zusaetzlich/alternativ" zu `ufw`. Docker dokumentiert
woertlich:

> When you publish a container's ports using Docker, traffic to and from that
> container gets diverted before it goes through the ufw firewall settings.
> […] Packets are routed before the firewall rules can be applied, effectively
> ignoring your firewall configuration.

Quelle: Docker Docs, „Packet filtering and firewalls", Abschnitt *Docker and
ufw* — <https://docs.docker.com/engine/network/packet-filtering-firewalls/>,
abgerufen 2026-09-25. ⇒ „alternativ" ist falsch: `ufw` allein schuetzt
veroeffentlichte Container-Ports nicht.

## 2 — Entscheidung: Variante A kennzeichnen statt loeschen

Auf Variante A wird an vier weiteren Stellen verwiesen
(`RUNBOOK.md:759/765`, `deploy/hetzner/README.md:396`,
`docs/cloud-hosting-owner-guide.md:131`). Ein stilles Loeschen laesst den
Leser, der die Variante aus einem aelteren Stand oder aus einem Verweis kennt,
ohne Korrektur zurueck — er haelt sie weiter fuer gueltig. Der Abschnitt bleibt
deshalb stehen, aber als **„Variante A — NICHT VERWENDEN"** mit dem woertlichen
Hetzner-Zitat als Begruendung. Gleichzeitig entfallen seine operativen Teile
(Verifikations-Kommandos, Akzeptanzkriterium, Console-Beleg-Platzhalter), damit
sie niemand mehr abhaken kann. Uebrig bleibt genau ein gangbarer Weg: LUKS.

## 3 — Trefferliste der Gegensuche (vollstaendig)

Gesucht wurde repo-weit nach `verschl(ue|ü)ssel` im Umfeld von
Volume/Hetzner/Disk/at-Rest, nach `Variante A`, `ufw` und `Cloud-Firewall`.

| # | Stelle | Befund | Aktion |
|---|---|---|---|
| 1 | `deploy/hetzner/RUNBOOK.md:702-723` | die falsche Aussage selbst | umgeschrieben zu „NICHT VERWENDEN" + Zitat |
| 2 | `deploy/hetzner/RUNBOOK.md:759-761` | Verifikationsblock fuer Variante A | entfernt |
| 3 | `deploy/hetzner/RUNBOOK.md:764-767` | Akzeptanzkriterium nennt Variante A als gueltig | auf LUKS reduziert |
| 4 | `deploy/hetzner/RUNBOOK.md:698` | „zwei betrieblich uebliche Wege … genau einen waehlen" | auf „genau ein gueltiger Weg" korrigiert |
| 5 | `deploy/hetzner/RUNBOOK.md:16` | Inhaltsverzeichnis „LUKS/verschl. Hetzner-Volume" | auf LUKS reduziert |
| 6 | `deploy/hetzner/RUNBOOK.md:44-47` | Provisioning Schritt 1: „Bei Variante B (LUKS)" — bedingt | unbedingt formuliert |
| 7 | `deploy/hetzner/RUNBOOK.md:671-673` (Protokoll-Tabelle) | Spalte „Variante (A/B)" | Spalte entfaellt |
| 8 | `deploy/hetzner/README.md:395-401` | „entweder verschluesseltes Hetzner-Volume (Plattform-LUKS) oder LUKS" | auf LUKS reduziert |
| 9 | `docs/cloud-hosting-owner-guide.md:131-136` | stellt Variante A als die bequemere dar | korrigiert |
| 10 | `docs/compliance/c5-mapping.md:19` | verweist nur aufs RUNBOOK, keine eigene Aussage | keine Aenderung noetig |
| 11 | `docs/compliance/vvt.md:190` | reiner Verweis | keine Aenderung noetig |
| 12 | `docs/cloud-hosting-owner-guide.md:497` | „Verschluesselung ist auf Volume-Ebene (LUKS)" — bereits korrekt | keine Aenderung noetig |
| 13 | `deploy/hetzner/RUNBOOK.md:83-91` | Firewall „zusaetzlich/alternativ" | Cloud-Firewall als empfohlene Ebene + Docker/`ufw`-Grund |
| 14 | `docs/cloud-hosting-owner-guide.md:155-157` | „Zusaetzlich … nicht nur UFW" — Richtung stimmt, Grund fehlt | Docker/`ufw`-Grund ergaenzt |
| 15 | `docs/cloud-local-smoke.md`, `docs/cloud-prod-smoke.md`, `docs/oauth-e2e-dokploy.md`, `changelog.d/w8p1-*` | „Variante A" in anderem Kontext (Pro-Entitlement, OAuth) | nicht betroffen |
| 16 | `.claude/plan/2026-06-05-1311_*` | historisches Planpapier, Zeitdokument | bewusst unveraendert |

## 4 — Reihenfolge in der Checkliste

Bisher stand die Verschluesselung nur als Aufzaehlungspunkt in
„Schritt 1 — Box anlegen" und, bedingt formuliert, als Nebensatz. Wer die
Provisioning-Schritte 1–7 von oben abarbeitet, kommt bei Schritt 6 zum
Repo-Clone und danach zum Bring-up, ohne je einen Schritt „Verschluesselung"
gesehen zu haben. ⇒ Eigener, nummerierter **Schritt 3b** zwischen Docker (3)
und Firewall (4), mit dem Grund daneben (danach nur mit Downtime + Restore
nachholbar). Nummern 4–7 bleiben unveraendert, damit alle Querverweise
(`README.md`, `Provisioning §7`, Erstinbetriebnahme-Punkt 0/6) weiter stimmen.

## 5 — Verifikation

- `uv run python scripts/changelog_fragments.py check`
- Markdown-Ankerziele der geaenderten Verweise gegengelesen
- `pytest` (Doku-Guards im Repo)
