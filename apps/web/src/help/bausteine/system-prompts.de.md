---
title: System-Prompts und Platzhalter
description: Die Vorlage, die ein Agent bei jedem Start liest, und welche Platzhalter du darin nutzen kannst.
section: bausteine
order: 40
updated: 2026-10-23
audience: all
---

Ein System-Prompt ist die Vorlage, die dein Agent bei jedem Start liest. Er führt Persona, Playbooks und Resources zusammen. Du findest alle Vorlagen in der Navigation unter **System-Prompts**. Jeder Agent nutzt genau einen System-Prompt.

## Aufbau [#aufbau]

- **Identität:** Name und Beschreibung. Beides erscheint in der Vorlagen-Liste und bei der Auswahl am Agenten.
- **Inhalt:** der Text, den der Agent liest. Tippe `/` für Blöcke und Platzhalter.

Viele Agenten können dieselbe Vorlage nutzen. Was je Agent anders ist, kommt aus seiner [Persona](/help/persona).

## Was ein Platzhalter ist [#was-ist-ein-platzhalter]

Ein Platzhalter steht im Text als kleine Kapsel. Wenn der Agent die Vorlage abruft, ersetzt Who2Be ihn durch echten Inhalt, zum Beispiel den Namen der Persona oder den Text eines Playbooks. So bleibt der Prompt kurz und immer aktuell.

Einfügen: Tippe im Editor `/` und wähle den Platzhalter aus dem Menü.

## Alle Platzhalter [#placeholders]

- **Playbook:** bettet ein Playbook fest ein. Es wird bei jedem Start mitgeladen.
- **Resource:** verweist auf eine bestimmte Resource.
- **Externes Tool:** bindet ein externes Tool über seinen Alias ein, siehe [Werkzeuge](/help/tools#externe-tools).
- **Persona-Feld:** bettet Name, Beschreibung, das ganze Profil, nur den Profil-Inhalt oder nur die Modi ein.
- **Persona laden (MCP):** bettet keinen Inhalt ein. Der Agent wird angewiesen, seine Persona beim Start mit `get_persona` selbst zu laden und ihre Modi anzuwenden.
- **Datum:** das aktuelle Datum, als ISO-Datum oder lesbar.
- **Playbook-Katalog:** Tabelle der zugeordneten Playbooks mit Name, Trigger, Aufruf und Beschreibung. Der Agent weiß dadurch, was er wann mit `fetch_playbook` laden kann. Wahlweise alle oder nur die mit Trigger.
- **Resource-Katalog:** Tabelle der Resources im Workspace, auf Wunsch nach Tag gefiltert.
- **MCP-Tools:** Liste der Werkzeuge mit Aufruf und Kurzbeschreibung. Schreib dazu, in welcher Reihenfolge der Agent sie nutzen soll, etwa „zuerst `list_triggers`, dann `fetch_playbook`“.
- **Gedächtnis:** ein Hinweis zum Gedächtnis, passend zur Einstellung des Agenten.

## Versionen und Aktivieren [#versionen]

Jede Änderung erzeugt eine neue Version, zuerst als Entwurf. Ein Entwurf wirkt noch nicht. Bist du fertig, klickst du auf **Zur Freigabe einreichen**. Ein Admin prüft die Version und klickt auf **Aktivieren** oder schickt sie mit **Zurück in den Entwurf** zurück. Erst die aktive Version nutzt der Agent.

## Tipps [#tipps]

- **Persona laden (MCP)** hält die Vorlage schlank, weil die Persona erst zur Laufzeit kommt.
- Bette Playbooks nur fest ein, wenn der Agent sie wirklich immer braucht. Sonst reicht der Playbook-Katalog, siehe [Playbooks](/help/playbooks#laden).
- Nachschlagewissen gehört in [Resources](/help/resources), nicht in den Prompt.
