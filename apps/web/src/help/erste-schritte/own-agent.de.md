---
title: Eigenen Agenten bauen
description: Lass dir vom Builder im Chat einen Agenten bauen, oder leg ihn selbst an.
section: erste-schritte
order: 40
updated: 2026-10-23
audience: all
---

Dein eigener Agent entsteht am einfachsten im Gespräch mit dem Builder. Du sagst, wofür er da sein soll, der Builder stellt Rückfragen und legt alles in Who2Be an. Voraussetzung: Der Builder ist schon verbunden, siehe [Mit Claude verbinden](/help/connect-claude).

## Mit dem Builder im Chat [#mit-dem-builder]

1. Öffne in Claude einen neuen Chat mit dem Builder.
2. Beschreib in ein, zwei Sätzen, was dein Agent tun soll. Zum Beispiel:

```
Bau mir in Who2Be einen Agenten für Kundenanfragen per E-Mail. Frag mich vorher, was du wissen musst.
```

3. Beantworte die Rückfragen. Je konkreter du bist, desto besser passt der Agent.
4. Der Builder legt Persona, Playbooks und den Agenten in Who2Be an. Erlaube dafür die Werkzeug-Aufrufe, wenn Claude fragt.

Danach findest du den neuen Agenten unter **Agenten**.

## Selbst anlegen [#formular]

Du kannst einen Agenten auch ohne Builder anlegen:

1. Klick unter **Agenten** auf **Neuen Agenten erstellen**. Who2Be öffnet gleich **Einstellungen › Konfiguration**, der Cursor steht im Feld **Persona**.
2. Gib ihm einen Namen und wähle eine **Persona** und einen **System-Prompt**. Dann **Speichern**.
3. Die Persona muss aktiv sein. Solange etwas fehlt, zeigt Who2Be „Noch nicht aktivierbar“ und nennt, was fehlt.
4. Ist alles gesetzt, fragt Who2Be „Agent jetzt aktivieren?“. Mit **Aktivieren** ist er sofort abrufbar, und du landest im Überblick bei der Karte **Verbindung**. Mit **Später** bleibt er deaktiviert; den Status änderst du dann unter **Einstellungen**.

## Den neuen Agenten verbinden [#verbinden]

Jeder Agent hat seine eigene Verbindung. Öffne den neuen Agenten, geh in die Karte **Verbindung** und verbinde ihn wie den Builder. Schreib dann den Test-Satz:

```
Wer bist du? Lade deine Persona aus Who2Be.
```

Lädt der neue Agent seine Persona, ist der Schritt „Eigenen Agenten bauen“ im Tutorial [Erste Schritte](/help/tutorials/getting-started#build-own-agent) erledigt.

Nutzt du Claude Free, ist dort nur ein eigener Connector erlaubt. Entferne dann vorher den Builder in Claude.

## Gute Agenten bauen [#tipps]

- **Ein Zweck je Agent.** Lieber zwei kleine Agenten als einer für alles.
- **Beispiele nennen.** Sag dem Builder, wie eine gute Antwort aussieht.
- **Klein anfangen.** Ergänze Playbooks erst, wenn eine Aufgabe öfter vorkommt.
