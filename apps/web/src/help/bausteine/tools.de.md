---
title: Werkzeuge
description: Was dein Agent in Who2Be tun darf und wie du externe Tools einbindest.
section: bausteine
order: 50
updated: 2026-10-22
audience: all
---

Dein Agent spricht mit Who2Be über Werkzeuge (MCP-Tools). Mit ihnen lädt er seine Persona, sucht Playbooks und meldet Rückmeldungen. Auf dieser Seite steht, welche Werkzeuge es gibt, wie du sie freigibst und wie du Werkzeuge anderer Dienste einbindest.

## Was ein Agent damit kann [#faehigkeiten]

- **Lesen:** seine Persona laden, den Playbook-Katalog sehen, ein Playbook oder einen Block einer Resource nachladen, im Inhalt suchen.
- **Melden:** sagen, welches Playbook er genutzt hat und ob es geholfen hat, und Situationen als Rückmeldung melden.
- **Merken:** Einträge für sein Gedächtnis vorschlagen. Sie wirken erst nach deiner Freigabe, je nach Einstellung des Agenten.
- **Schreiben (nur wenn freigegeben):** Personas, Playbooks oder Resources anlegen und ändern. Der Builder nutzt das, um Agenten für dich zu bauen.

Typische Namen sind `get_persona`, `list_triggers`, `fetch_playbook` und `fetch_resource`. Die vollständige Liste fügst du mit `/` als „MCP-Tools“ in einen System-Prompt ein.

## Rechte festlegen [#rechte]

Auf der Seite deines Agenten unter **Einstellungen › Werkzeuge & Rechte** legst du fest, was er darf:

- Standardmäßig liest ein Agent nur, was ihm zugewiesen ist, und darf nichts verändern.
- Mit einem Preset setzt du die Schreibrechte in einem Schritt: **Nur lesen**, **Editor ohne Freigabe** oder **Editor mit Freigabe**.
- Einzelne Häkchen kannst du danach weiter ändern.

Gesperrte Werkzeuge lehnt der Server ab. Der Agent sieht in seinem Prompt nur die Werkzeuge, die er nutzen darf.

## Externe Tools [#externe-tools]

Unter **Externe Tools** hinterlegst du Werkzeuge anderer Dienste, zum Beispiel einer Aufgabenliste. Jedes externe Tool bekommt einen festen **Alias** wie `todo`. Playbooks und Personas verweisen auf den Alias, nicht auf den Dienst.

Wechselst du später den Dienst, änderst du nur das externe Tool. Alle Verweise bleiben gültig. Zu jedem Tool kannst du Nutzungshinweise und einen Fallback-Hinweis hinterlegen, falls der Dienst nicht verbunden ist.

Den Verweis setzt du mit `/` im [Playbook](/help/playbooks) oder in der [Persona](/help/persona).
