---
title: Playbooks
description: Wiederholbare Abläufe, die dein Agent bei Bedarf lädt.
section: bausteine
order: 20
updated: 2026-10-22
audience: all
---

Ein Playbook beschreibt, wie dein Agent eine bestimmte Aufgabe erledigt. Vom kurzen Textbaustein bis zum mehrstufigen Ablauf mit Verzweigungen. Du findest alle Playbooks in der Navigation unter **Playbooks**.

## Aufbau [#aufbau]

- **Identität:** Name, Typ und eine kurze Beschreibung.
- **Inhalt:** das eigentliche Playbook, zum Beispiel „Schritt 1: Kunde begrüßen. Schritt 2: Identität prüfen. Schritt 3: Link senden.“ Mit `/` fügst du Verweise auf andere Playbooks, Resources und externe Tools ein.
- **Trigger:** Stichwörter, bei denen der Agent dieses Playbook laden soll.
- **Tags:** für Suche und Filter.

## Typen [#typen]

Der Typ hilft dir beim Ordnen und dem Agenten beim Einordnen:

- **Workflow:** mehrstufiger Ablauf mit Verzweigungen.
- **Checklist:** Prüfliste vor einem Schritt.
- **FAQ:** Sammlung aus Fragen und Antworten.
- **Snippet:** kurzer, wiederverwendbarer Textbaustein.

Dazu kommen einzelne Prompts und mehrteilige Handlungsanweisungen.

## Wie der Agent Playbooks nutzt [#laden]

Der Agent lädt nicht alle Playbooks auf einmal. Er sieht einen Katalog mit Namen, Triggern und Beschreibung und holt sich das passende Playbook, wenn ein Trigger fällt. So bleibt sein Kontext klein.

Ein Playbook kann auch fest an eine [Persona](/help/persona) gebunden sein, etwa an einen Modus. Dann gehört es zu dieser Rolle.

## Zusammengesetzte Playbooks [#composite]

Ein Playbook kann andere Playbooks enthalten. Das nennt Who2Be **Composite**. Der Agent arbeitet die Teil-Playbooks der Reihe nach ab. So pflegst du einen Baustein einmal und nutzt ihn in mehreren Abläufen.

## Versionen [#versionen]

Jede Änderung erzeugt eine neue Version, alte Versionen bleiben erhalten. Erst eine aktive Version lädt der Agent. Wissen, auf das ein Playbook verweist, liegt am besten in einer [Resource](/help/resources).
