---
title: Workspaces, Mitglieder und Rollen
description: Wie Who2Be Inhalte trennt, wen du einlädst und wer was darf.
section: konto-und-team
order: 10
updated: 2026-10-24
audience: all
---

Alles in Who2Be liegt in einem Workspace: Agenten, Personas, Playbooks, Resources und Rückmeldungen. Ein Workspace gehört zu einer Organisation. So trennst du zum Beispiel Kundensupport und Marketing sauber voneinander.

## Organisation und Workspace [#aufbau]

- **Organisation:** der Rahmen, etwa deine Firma. Mit deinem Konto bekommst du eine persönliche Organisation mit einem ersten Workspace.
- **Workspace:** ein abgeschlossener Bereich mit eigenen Inhalten und eigenen Mitgliedern.

Den Workspace wechselst du oben in der Navigation mit **Workspace wechseln**. Einen neuen legst du dort mit **Workspace anlegen** an oder unter **Einstellungen › Organisation**.

## Rollen [#rollen]

Jedes Mitglied hat in einem Workspace genau eine Rolle:

- **Viewer:** sieht alles, ändert nichts. Viewer können Rückmeldungen geben und den Stand ihrer eigenen Rückmeldungen verfolgen.
- **Editor:** legt Inhalte an, bearbeitet sie und reicht sie zur Freigabe ein.
- **Admin:** gibt Versionen frei und verwaltet Mitglieder und Einladungen.

Das ist ein Vier-Augen-Prinzip: Ein Editor schreibt, ein Admin aktiviert. Eigene Agenten legt deshalb ein Editor oder Admin an. Als Viewer bittest du einen Admin darum.

## Mitglieder einladen [#einladen]

1. Öffne **Einstellungen › Mitglieder**. Die Seite ist nur für Admins.
2. Gib unter **Neues Mitglied einladen** die E-Mail-Adresse ein und wähle die **Rolle**.
3. Klick auf **Einladen**. Die Person erhält einen einmaligen Link, um beizutreten.

Offene Einladungen laufen automatisch ab und lassen sich widerrufen. Im Team-Workspace sehen Eingeladene die Startliste [Erste Schritte](/help/tutorials/getting-started). Die Begrüßung erscheint nur im eigenen persönlichen Workspace.

## Kollegen nur nutzen lassen [#nur-nutzen]

Soll ein Kollege deine Agenten nutzen, aber nichts daran ändern, lädst du ihn mit der Rolle **Viewer** ein (siehe [Mitglieder einladen](#einladen)).

Das kann der Kollege:

- Einen Agenten über einen Connector mit Claude oder einem anderen Client verbinden (siehe [Mit Claude verbinden](/help/connect-claude)) und ihn dort nutzen. Der Agent lädt seine Persona, seine Playbooks und seine Resources und durchsucht sie.
- Alles im Workspace lesen, auch Entwürfe.
- Rückmeldungen geben und ihren Stand verfolgen.

Das kann er nicht:

- Agenten, Personas, Playbooks oder Resources anlegen, ändern oder löschen.
- Versionen aktivieren.
- API-Tokens erstellen oder Mitglieder verwalten.

Im Gespräch mit dem Kollegen darf der Agent sein [Gedächtnis](/help/memory) nutzen und neue Einträge oder Änderungen vorschlagen. Vorschläge für das Agentengedächtnis gehen in die [Freigabe](/help/memory#freigabe) und wirken erst, wenn ein Editor oder Admin sie freigibt. Nur beim Speicher-Modus **Automatisch nach Workspace-Regeln** gilt sofort, was ein Admin dort eingeschaltet hat. In der Web-Oberfläche sieht der Kollege nur sein eigenes Nutzergedächtnis, nicht das Agentengedächtnis.

Der Kollege muss Mitglied desselben Workspace sein. Agenten über Organisationsgrenzen hinweg zu teilen geht noch nicht. Arbeitet der Kollege in einer anderen Organisation, lade ihn deshalb wie oben in einen Workspace deiner Organisation ein. Dann arbeitet ihr in der gemeinsamen Organisation.

## Rolle ändern oder entfernen [#aendern]

In der Mitgliederliste änderst du die Rolle oder entfernst ein Mitglied. Dabei widerruft Who2Be die API-Tokens dieses Mitglieds automatisch. Neue Tokens bekommen die neue Rolle.
