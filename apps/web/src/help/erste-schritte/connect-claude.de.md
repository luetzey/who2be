---
title: Mit Claude verbinden
description: Ein Klick, eine Bestätigung, ein Test-Satz.
section: erste-schritte
order: 20
updated: 2026-10-22
audience: all
---

Damit Claude deinen Agenten nutzen kann, trägst du ihn einmal als Connector in Claude ein. Who2Be füllt dafür alles vor. Du brauchst etwa zwei Minuten.

## Schritt für Schritt [#schritte]

1. Öffne unter **Agents** deinen Agenten, zum Beispiel den Builder. Im Tab **Überblick** steht die Karte **Verbindung**.
2. Wähle bei „Wo nutzt du deine Agenten?“ **Claude** und klick auf **Mit Claude verbinden**. Claude öffnet sich in einem neuen Tab, Name und Adresse sind schon ausgefüllt.
3. Klick in Claude auf **Hinzufügen** und dann auf **Verbinden**.
4. Who2Be fragt, ob Claude diesen Agenten nutzen darf. Bestätige das.
5. Schreib in Claude in einem neuen Chat den Test-Satz und erlaube den Werkzeug-Aufruf, wenn Claude fragt.

## Der Test-Satz [#test]

```
Wer bist du? Lade deine Persona aus Who2Be.
```

Lädt der Agent seine Persona, zeigt Who2Be die Verbindung als **Verbunden**. Im Tutorial „Erste Schritte“ hakt sich der Schritt von selbst ab. Du kannst die Who2Be-Seite dabei offen lassen.

## Von Hand eintragen [#von-hand]

Klappt der Knopf nicht, öffne in der Karte **Verbindung** den Aufklapper „Klappt der Knopf nicht? Von Hand eintragen“. Dort stehen **Name** und **Server-URL** zum Kopieren.

In Claude gehst du auf **Einstellungen › Connectors › Eigenen Connector hinzufügen** und fügst beides ein. Auf dem iPhone öffnet der Knopf den Dialog manchmal nicht. Dann hilft dieser Weg.

## Team- und Enterprise-Pläne [#team-plan]

In Claude-Plänen für Teams und Unternehmen fügt meist der Owner der Claude-Organisation die Connectors hinzu. Schick ihm Name und Server-URL aus der Karte **Verbindung**.

## Wenn es nicht klappt [#troubleshooting]

- **Kein Haken nach dem Test-Satz:** Prüfe, ob du den Satz in einem neuen Chat geschrieben und den Werkzeug-Aufruf erlaubt hast. Nach zwei Minuten bietet Who2Be dir „Ja, weiter“ an, falls der Agent geantwortet hat.
- **Claude zeigt einen Anmeldefehler:** Entferne den Connector in Claude und verbinde ihn neu. Who2Be fragt dann noch einmal nach deiner Bestätigung.
- **Der Agent ist nicht bereit:** Statt des Knopfs steht dann, was fehlt, zum Beispiel eine aktive Persona. Behebe das zuerst.
- **Claude Free:** Dort ist nur ein eigener Connector erlaubt. Ist schon einer eingetragen, entferne ihn vorher.

Mit Claude Code, Cursor oder VS Code geht es ähnlich, siehe [Andere Programme verbinden](/help/connect-other-clients).
